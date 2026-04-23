# 扩展指南

三条主要扩展路径：**手写一个角色** / **加一个新 group** / **接一个新上游源**。

## 手写一个角色

适用场景：上游都没有合适的模板，你要从零起一个。

### 1. 起草 YAML

从现有官方角色 copy 一份当模板：

```bash
cp roles/engineering/backend_architect/v1.yaml roles/engineering/my_new_role/v1.yaml
$EDITOR roles/engineering/my_new_role/v1.yaml
```

必填九个 section（`meta / identity / mission / boundaries / io / behavior / workflows / capabilities / evaluation`）。完整 schema 见 `rolecore/utils/schema_validator.py::SECTION_RULES`。

关键字段：
- `meta.role_id` = `<group>.<role_name>`（必须和文件路径匹配）
- `meta.version` = `"1"`
- `meta.status` = `"raw_imported"` 起步
- `identity.name_cn` — 人工确权，不能空
- `meta.source` — 手写角色可以完全省略，或写 `{"type": "manual"}`

### 2. 校验 + 入库

```bash
python3 cli.py role validate --file roles/engineering/my_new_role/v1.yaml
python3 cli.py role create --file roles/engineering/my_new_role/v1.yaml
```

`create` 会写 YAML + 注册 registry + 刷 checksum。**不要**直接把文件 drop 进 `roles/` 目录然后手改 registry——checksum 会漂。

### 3. 过 gate → 晋升

```bash
python3 cli.py role gate --id engineering.my_new_role     # 看缺口
# 补完到过 gate
python3 cli.py role promote --id engineering.my_new_role --to normalized
python3 cli.py review prompt --id engineering.my_new_role # 跑复核（离线或 live）
python3 cli.py review apply --id engineering.my_new_role --from-file review.txt
python3 cli.py role promote --id engineering.my_new_role --to curated
python3 cli.py role promote --id engineering.my_new_role --to official
```

详细流程见 [reviewer.md](reviewer.md)。

## 加一个新 group

**先想清楚属于哪一维**：岗位（job） / 技术栈（tech） / 专业特长（specialty）。新维度不要随便加——三维拓扑是产品层约定，加第四维要更新 CLI、fusion search 文案、README 所有地方。

### 1. 注册到 fusion search

`rolecore/core/fusion_search.py`：

```python
JOB_GROUPS = frozenset({..., "your_new_group"})
# 或
TECH_GROUPS = frozenset({..., "your_new_group"})
# 或
SPECIALTY_GROUPS = frozenset({..., "your_new_group"})
```

`_AXIS_OF_GROUP` 在模块加载时自动从三个 frozenset 构建，不需要手动维护。

### 2. 让 schema validator 接受新 group

schema validator **不限制** `meta.group` 的取值（只检查非空字符串），所以直接放新组的 YAML 就能过 schema。但 `create_role` 会校验 `meta.role_id` 以 `<group>.` 开头——保证一致就行。

### 3.（可选）在上游路由表里登记

如果新 group 有对应的上游来源（比如新起一个目录），必须在路由表里登记，否则 `catalog.py` 的硬 KeyError 会挡住导入。见下一节。

## 接一个新上游源

**三个要改的地方**，缺一不可：

### 1. 在 `catalog.py` 加一个 `_scan_<source>` 函数

照抄现有的 `_scan_0xfurai` / `_scan_voltagent` / `_scan_wshobson` 之一做结构参考。扫描职责：

- 遍历上游目录下的 `.md` 文件
- 提取 `role_name`（从 frontmatter 或文件名）
- 通过**路由表**把原始 category 映射到 RoleCore 的三维 group（`rc_group`）
- 组装 entry dict：

```python
{
    "role_id": f"{rc_group}.{role_name_normalized}",
    "name_en": "...",
    "group": "<原始 group 字符串，用于 debug>",
    "rc_group": "<RoleCore group>",
    "role_name": "<normalized>",
    "domain": "...",
    "file_path": "...",
    "description": "...",
    "source": "<your-source-id>",   # ← importer dispatch 靠这个
}
```

**把新路由表定义为模块级 dict**，并在 scan 函数里用 `ROUTE[key]` 而不是 `ROUTE.get(key)`——**我们要硬 KeyError**。历史上这条是治理不变量 #3：未登记的条目必须崩，不允许静默进错组。

在 `scan_upstream()` 入口加调用：

```python
def scan_upstream(upstream_dir: str) -> list:
    return (
        _scan_agency_agents(upstream_dir)
        + _scan_0xfurai(upstream_dir)
        + _scan_voltagent(upstream_dir)
        + _scan_wshobson(upstream_dir)
        + _scan_your_source(upstream_dir)   # ← 新增
    )
```

### 2. 写一个 `importer_<source>.py`

职责：把一个 upstream `.md` 文件 → schema-合法的 role_data dict。

入口签名约定：

```python
def md_to_rolecore_<source>(file_path: str, rc_group: str, role_name: str) -> dict:
    ...
```

返回的 dict 必须：
- 九个 section 齐全
- `meta.role_id = f"{rc_group}.{role_name}"`
- `meta.version = "1"`
- `meta.status = "raw_imported"`
- `identity.name_cn = ""` ← **绝不自动填**
- `meta.source.name_cn_suggested`（可选）给机器建议
- `meta.source.upstream_hash = _file_sha256(file_path)` ← drift 检测靠这个
- `meta.source.enhanced_fields = []`

**最简骨架**：

```python
from .importer import _file_sha256, _read_md

def md_to_rolecore_your_source(file_path, rc_group, role_name):
    md = _read_md(file_path)
    role_id = f"{rc_group}.{role_name}"
    return {
        "meta": {
            "role_id": role_id,
            "version": "1",
            "group": rc_group,
            "tags": [...],
            "status": "raw_imported",
            "source": {
                "type": "upstream/your-source",
                "upstream_file": file_path,
                "upstream_hash": _file_sha256(file_path),
                "imported_at": datetime.utcnow().isoformat() + "Z",
                "enhanced_fields": [],
                "name_cn_suggested": "...",  # 可选机器建议
            },
        },
        "identity": {"name_cn": "", "name_en": md["frontmatter"]["name"],
                     "domain": "...", "positioning": "..."},
        "mission": {...},
        "boundaries": {...},
        "io": {...},
        "behavior": {...},
        "workflows": [...],
        "capabilities": {...},
        "evaluation": {...},
    }
```

Schema 校验在 `RoleManager.create_role` 里跑，所以进来的 dict 必须完全合法。**每一个占位符字段都不会过 official gate**——这不是 bug，是设计：rubbish in, rubbish out，gate 会把你挡在 official 之外。

### 3. 在 `importer.py::md_to_rolecore_for_entry` 加 dispatch 分支

```python
def md_to_rolecore_for_entry(entry: dict) -> dict:
    src = entry.get("source", "agency-agents")
    if src == "your-source-id":
        from .importer_your_source import md_to_rolecore_your_source
        return md_to_rolecore_your_source(
            entry["file_path"], entry["rc_group"], entry["role_name"]
        )
    # ... 既有分支
```

### 4. 测试 + 首次导入

写一个 `tests/test_parser_your_source.py`，照抄 `tests/test_parsers.py`。至少一个真实 upstream fixture，断言：
- 返回 dict 过 `SchemaValidator`
- `identity.name_cn == ""`（治理不变量）
- `meta.source.source` 标识正确
- `meta.source.upstream_hash` 非空

跑：

```bash
pytest tests/test_parser_your_source.py -v
```

首次全量导入：

```bash
python3 cli.py upstream list | head                  # 确认 catalog 能扫到
python3 cli.py upstream import --id <some_role_id>   # 先试一个
python3 cli.py upstream import-all --dry-run         # 预览
python3 cli.py upstream import-all                   # 正式
python3 cli.py registry stats                        # 看状态分布
```

然后走 name_cn 人工确权 → promote 到 normalized/curated/official，见 reviewer.md。

## 扩展时的反模式（别犯）

1. **别在 parser 里自动填 `identity.name_cn`**。即使能从 frontmatter 推断中文名，也写到 `name_cn_suggested`。治理不变量 #1。
2. **别用 `.get()` 把路由表 miss 变成静默降级**。`ROUTE[key]` 硬崩是 feature。
3. **别绕过 `RoleManager.create_role/update_role` 直接写 YAML**。必须调，除非你同步手工调 `_refresh_version_checksum`。
4. **别 `git add registry/registry.json` 后忘了看 diff**。registry 是缓存，应该由 YAML 推出；diff 里如果出现未来去掉也没事的噪声字段，说明上游写路径漏刷了。
5. **别把新 parser 的 bug 用 reimport 推到全量**。先 `--dry-run`，再抽样 `upstream reimport --id <one>` 看结果，最后才 `reimport-all`。

## 相关文档

- [concepts.md](concepts.md) — 治理不变量全文
- [architecture.md](architecture.md) — 核心契约和数据流
- [reviewer.md](reviewer.md) — 复核流程细节
- [operations.md](operations.md) — 运营手册（drift 监控 / 备份）
