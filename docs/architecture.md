# 架构

## 分层总览

```
┌──────────────────────────────────────────────────────────────┐
│ CLI (cli.py)                                                 │
│  role / search / find / export / assemble / registry         │
│  review / upstream                                           │
└──────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│ core/                                                        │
│  RoleManager      写路径 + 状态机 + gate                     │
│  SearchEngine     单维检索（group/tag/keyword）              │
│  FusionSearchEngine  三维加权融合检索                        │
│  Reviewer         LLM 质量复核（prompt 构造 + 解析 + 挂载）   │
│  Assembler        role + task + context → 执行 prompt        │
└──────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│ storage/                                                     │
│  RoleStore        读写 roles/<group>/<role>/v<N>.yaml        │
│  RegistryStore    读写 registry/registry.json                │
└──────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│ upstream/            models/           utils/                │
│  catalog             RoleAsset         schema_validator      │
│  importer(*)         RegistryEntry     path_utils            │
│  reimporter          AssemblyContext   version_utils         │
│  drift                                                       │
└──────────────────────────────────────────────────────────────┘

exporters/  prompt / json / markdown — 纯数据→字符串，无副作用
```

## 模块职责

### `core/role_manager.py` — RoleManager
**写路径唯一入口**。所有合法修改都要走这里，因为它负责：

- `create_role / update_role` — schema 校验 → 写 YAML → 刷 registry
- `promote_status` — 五级状态机 + 两道 gate（official / curated）
- `mark_enhanced_fields / unmark_enhanced_fields` — 维护 `meta.source.enhanced_fields`
- `resync_entry_from_yaml` — 从 YAML 回拉 registry 去规范化字段
- `_refresh_version_checksum` — 私有 helper，保证所有直写 YAML 的路径都刷 checksum

**核心契约**：只要 YAML 被修改，checksum 就必须跟着刷。如果新加一条写路径绕过了 `update_role`，必须显式调 `_refresh_version_checksum(entry_dict, version)`。违反这条会在 registry 里留下 checksum 漂移，`registry verify` 发现不了（它只看文件存在），要靠 `registry resync` 兜底。

### `core/search_engine.py` — SearchEngine
单维检索：按 `group` / `tags` / `keyword` 过滤 registry。**只读**，不查 YAML（所有字段都从 registry 拿，所以 registry denormalization 漂了会直接影响结果）。

### `core/fusion_search.py` — FusionSearchEngine
三维加权融合：

| 字段 | 权重 | 备注 |
|---|---|---|
| `name_cn` | 4.0 | 中文名最重 |
| `name_en` | 3.0 | |
| `domain` | 2.0 | |
| `tags` | 1.5 | |
| `role_id_tail` | 1.0 | `engineering.backend_architect` 的 `backend_architect` 部分 |
| 多 token 全覆盖 | +0.5 | 鼓励精确匹配 |

group → axis 路由是三个 `frozenset`（JOB_GROUPS / TECH_GROUPS / SPECIALTY_GROUPS）。每维独立取 top-K 并组成 triad。

排序 tiebreak：`(-score, len(role_id_tail), role_id)`——score 相同时**更短的 role_id 尾部胜出**（canonical 偏好，避免 `core_dev.temporal_python_pro` 盖住 `language_specialist.python_pro`）。

### `core/reviewer.py` — Reviewer
- `REVIEW_SYSTEM_PROMPT` — 5 维评审 rubric（Coherence / Specificity / Actionability / Boundaries / Evaluation）
- `build_user_prompt(role_data)` — 塞 YAML（剔除 `meta.source`）
- `run_live(role_id)` — 调 Anthropic API
- `parse_review_response(text)` — 正则抽 JSON + 字段验证
- `attach_record / attach_manual` — 写入 `meta.review`
- `get_review_record(role_data)` — 独立 helper，被 `promote_status` 的 curated gate 调

### `core/assembler.py` — Assembler
`role + task + goal + context → AssemblyContext`，调用 exporter 产出最终 prompt。纯 orchestration，不触碰存储。

### `storage/role_store.py` — RoleStore
- `read_role / write_role / list_roles / delete_role`
- 路径约定：`roles/<group>/<role_name>/v<N>.yaml`
- **只管文件 I/O，不管 registry**。任何人直接调 `write_role` 都会绕过 checksum 刷新——这是 Phase 2.5 的 143/143 漂移事故来源。

### `storage/registry_store.py` — RegistryStore
`registry/registry.json` 的结构：

```json
{
  "roles": {
    "<role_id>": {
      "role_id": "...",
      "name_cn": "...", "name_en": "...", "domain": "...",
      "tags": [...],
      "latest_version": "N",
      "meta": {"status": "official", ...},
      "versions": {
        "1": {
          "file_path": ".../v1.yaml",
          "checksum": "sha256:...",
          "created_at": "..."
        }
      }
    }
  },
  "groups": {"engineering": ["role_id1", ...]},
  "tag_index": {"python": ["role_id1", ...]},
  "metadata": {"updated_at": "..."}
}
```

去规范化字段（`name_cn / name_en / domain / tags`、`meta.status`）是 YAML 的缓存副本。`save()` 自动盖 `metadata.updated_at`。

**隐藏的坑**：`_empty_registry()` 是**工厂函数**不是模块级常量——历史上用 `_EMPTY_REGISTRY` dict 浅拷贝导致跨测试实例共享嵌套 dict，第一个测试污染后续测试。**不要**回退成常量。

### `upstream/catalog.py` — 上游扫描
`scan_upstream(path)` 聚合四个源：

| 函数 | 源 | group 路由 |
|---|---|---|
| `_scan_agency_agents` | agency-agents | 目录 → `rc_group`（保留原名） |
| `_scan_0xfurai` | 0xfurai/claude-code-subagents | `ZXF_ROUTE` |
| `_scan_voltagent` | VoltAgent/subagents | `VOLT_GROUP_FROM_CATEGORY` |
| `_scan_wshobson` | wshobson/agents | `WSHOB_ROUTE` |

每条 entry 带 `source` 字段，后续 dispatcher 按 source 选 parser。**三张路由表是硬 KeyError 策略**：新增上游 / 新技术 / 新 category 必须登记，否则直接崩——避免静默进错组。

### `upstream/importer*.py` — parsers
- `importer.py` — agency-agents parser + `md_to_rolecore_for_entry(entry)` dispatcher
- `importer_0xfurai.py`
- `importer_voltagent.py`
- `importer_wshobson.py`

每个 parser 返回一个 schema-合法的 role_data dict。`meta.source` 块登记 upstream 路径 + `upstream_hash`（SHA-256）+ `enhanced_fields = []`。

**Parser 绝不自动填 `identity.name_cn`**——机器建议写到 `meta.source.name_cn_suggested`。这是治理不变量 #1。

### `upstream/reimporter.py`
`reimport_role(upstream_file, group, role_name, existing_data, force)` → `(merged_data, changed)`：

1. 比对新旧 upstream hash，未变且非 force → `changed=False`
2. 读现有 `meta.source.enhanced_fields`
3. 跑 parser 产出新 data
4. 把 enhanced_fields 里每条 dot-path 从 existing 数据拷回 new data
5. 写回 merged

这是**保护人工增强字段**不被重 import 冲掉的唯一机制。

### `upstream/drift.py` — 漂移扫描
纯只读。遍历 registry + catalog 做双向比对，产出三类：

```python
@dataclass
class DriftEntry:
    role_id: str
    reason: str
    upstream_file: str | None
    current_hash: str | None
    stored_hash: str | None
    enhanced_fields: list[str]
    upstream_repo: str
```

- Pass 1（registry → catalog）：找 drifted + missing_upstream
- Pass 2（catalog → registry）：找 unregistered

没有 `meta.source.upstream_hash` 的角色（手写角色 / agentforge）被跳过，不会污染报告。

### `models/role.py` — RoleAsset dataclass
九个 section 一一对应 dataclass 字段。`RoleMeta.review` 是 first-class 字段（Phase 4 新增），`to_dict()` 空时不发出（向后兼容历史 YAML）。

## 数据流

### 写路径（典型：`role create`）

```
YAML file
  └─▶ SchemaValidator.validate()
        └─▶ RoleStore.write_role()                         # 落盘
              └─▶ RegistryStore.save_entry()               # 注册
                    └─▶ _refresh_version_checksum()        # SHA-256
```

### 读路径（典型：`find`）

```
query string
  └─▶ tokenize
        └─▶ FusionSearchEngine.find()
              └─▶ RegistryStore.load()                     # 只读 JSON
                    └─▶ per-axis score + sort
                          └─▶ triad 合成
```

### Upstream reimport 路径

```
catalog scan
  └─▶ parser (md → role_data)
        └─▶ reimport_role()                                # merge enhanced_fields
              └─▶ RoleManager.update_role()                # 新版本
                    └─▶ RoleStore.write_role + Registry.save
```

## 核心契约

1. **YAML 是真源，registry 是缓存**。冲突时信 YAML。`registry resync` 是唯一正确的兜底动作。
2. **任何写 YAML 的路径都必须刷 checksum**。直接调 `RoleStore.write_role` 的代码必须配套 `_refresh_version_checksum`。
3. **`identity.name_cn` 绝不自动填**。parser 只写 `meta.source.name_cn_suggested`。
4. **路由表 miss 必须崩**。`ZXF_ROUTE / WSHOB_ROUTE / VOLT_GROUP_FROM_CATEGORY` 的 KeyError 是 feature。
5. **Promote 只前进**（除 archived）。curated 要 review=approved，official 要 10 项门槛全过。
6. **Enhanced fields 必须登记**。手改过的字段如果不进 `meta.source.enhanced_fields`，下次 reimport 会被吃掉。

## 可扩展点

- **新上游源**：新 `_scan_<source>` + 新 `importer_<source>.py` + `md_to_rolecore_for_entry` dispatcher 加分支 + 新路由表（如果需要新 group）。详见 [extending.md](extending.md)。
- **新 gate 项**：改 `OfficialGateValidator.check()`。
- **新评审维度**：改 `REVIEW_SYSTEM_PROMPT` + `ReviewRecord` 字段。
- **新检索轴**：新 axis frozenset + 改 `FIELD_WEIGHTS` 或加字段（慎重——三维拓扑是产品层约定）。

## 目录到职责速查

| 改什么 | 动哪里 |
|---|---|
| 加字段 | `models/role.py` + `utils/schema_validator.py::SECTION_RULES` |
| 改 gate 规则 | `core/role_manager.py::OfficialGateValidator` |
| 改检索权重 | `core/fusion_search.py::FIELD_WEIGHTS` |
| 新上游 parser | `upstream/importer_<x>.py` + `catalog.py::_scan_<x>` + `importer.py::md_to_rolecore_for_entry` |
| 改评审 prompt | `core/reviewer.py::REVIEW_SYSTEM_PROMPT` |
| 改 CLI | `cli.py` + `dispatch` 表 |
| 改导出格式 | `exporters/<format>_exporter.py` |
