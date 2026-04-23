# CLI 参考

> **Showcase note**：本仓 CLI 不包含 `upstream` 子命令树（多上游接入 / drift / reimport 在 private core）。
> `role mark-enhanced` / `unmark-enhanced` 保留了入口但 runtime 会 ImportError——这两条是 reimport
> 护城河的一部分，showcase 没有上游不需要用。

所有命令统一入口 `python3 cli.py <group> <subcommand> [flags]` 或 `rolecore <group> <subcommand> [flags]`（pip install 之后）。下文省略前缀。

## 命令树一览

```
role       create / get / list / update / set-latest / promote / gate
           deprecate / delete / validate / versions
search     (单维：group / tags / keyword)
find       (三维融合检索)
export     (prompt / json / markdown)
assemble   (装配执行 prompt)
registry   stats / rebuild-index / dump / verify / resync
review     prompt / run / apply / status
# upstream   list / info / import / import-all / reimport / reimport-all / drift    (private core only)
```

## role — 角色 CRUD

### `role create --file <yaml> [--version 1] [--author system]`
从 YAML 文件创建新角色。首次入库默认 `v1`。

### `role get --id <role_id> [--version latest] [--full]`
查看角色摘要，`--full` 打印完整 YAML。

### `role list [--group <g>] [--status live]`
按 group 和状态过滤。`--status` 可以是 `raw_imported/normalized/curated/official/archived/live/all`，`live` = 非 archived。

### `role update --id <role_id> --file <yaml> [--version <N>] [--desc ...]`
建立新版本。不传 `--version` 会自动递增。会刷新 registry checksum。

### `role set-latest --id <role_id> --version <N>`
把 `latest` 指针移到指定版本（用于回滚）。

### `role promote --id <role_id> --to <normalized|curated|official|archived>`
晋升状态。单向前进（除 `archived`），跳级允许但 gate 必须过：
- `→ curated`：`meta.review.verdict` 必须是 `approved`
- `→ official`：10 项结构门槛（见 [concepts.md](concepts.md)）

### `role gate --id <role_id>`
干跑 official gate，打印缺口。不修改状态。exit 1 如果有缺口。

### `role mark-enhanced --id <role_id> --fields '<dot.path,dot.path2>'`
把字段登记进 `meta.source.enhanced_fields`——下次 `upstream reimport` 不会被覆盖。常见用法：
```bash
role mark-enhanced --id engineering.backend_architect --fields 'mission.summary,identity.positioning'
```

### `role unmark-enhanced --id <role_id> --fields '...'`
反向操作。

### `role deprecate --id <role_id>`
**遗留命令**。新代码请用 `role promote --to archived`。

### `role delete --id <role_id> [--version <N>]`
不传 `--version` 删除所有版本 + 注销 registry。

### `role validate --file <yaml>`
只校验 schema 合法性，不入库。

### `role versions --id <role_id>`
列角色的所有历史版本。

## search — 单维检索

```bash
search --group engineering
search --tags python,backend --tag-match all
search --keyword 架构
search --list-groups        # 枚举所有 group
search --list-tags          # 枚举所有 tag
```

`--status` 默认 `active`（≈ live）。`--tag-match` ∈ `any|all`。

## find — 三维融合检索

```bash
find "<query>" [--top-k 5] [--status official] [--json]
```

在三个维度（`job` / `tech` / `specialty`）上分别跑加权打分，返回每维 top-K 和一个 triad（三维最佳组合）。`--status ''` 取消状态过滤。

```bash
find "Python 后端 高级开发"
find "spatial computing AR" --json --top-k 3
```

评分权重见 [architecture.md](architecture.md)。

## export — 导出

```bash
export --id <role_id> --format prompt|json|markdown [--output <path>]
export --group engineering --format markdown --output ./out.md   # 批量
```

批量写盘时会在文件名尾部自动追加 `_<role_id>`。`--format prompt` 是默认。

## assemble — 装配执行上下文

把角色 + 任务 + 目标 + 额外 context 组合成可直接喂 LLM 的 prompt：

```bash
assemble --id engineering.backend_architect \
    --task "设计订单服务" \
    --goal "支持 10k QPS" \
    --context '{"tech_stack":"Go+Postgres"}' \
    --format prompt
```

`--context` 是 JSON。`--output` 写盘，否则 stdout。

## registry — 注册表维护

### `registry stats`
总览：状态分布直方图 / group 数 / tag 数。

### `registry rebuild-index`
仅重建 `tag_index`。

### `registry dump [--format json|yaml]`
把整个 registry 打印到 stdout，便于 pipe 到 `jq` / `grep`。

### `registry verify`
校验 registry 里登记的每个 YAML 文件都物理存在。exit 1 如果有缺文件。

### `registry resync`
**关键兜底命令**。从每份 YAML 重新拉 `name_cn / name_en / domain / tags / status` 回填到 registry，并刷新 checksum。用于修复直写 YAML（绕过 `update_role`）留下的漂移。

```bash
cp registry/registry.json registry/registry.json.bak-pre-resync-$(date +%Y%m%d-%H%M%S)
python3 cli.py registry resync
```

## review — LLM 质量复核

详细工作流见 [reviewer.md](reviewer.md)。

### `review prompt --id <role_id> [--output <path>]`
**离线模式**：生成 5 维评审 prompt（system + user），贴到任意 LLM（Claude/GPT/本地模型）都能跑。

### `review run --id <role_id> [--force]`
**在线模式**：调 Anthropic API。需要 `ANTHROPIC_API_KEY`。跑完自动挂到 `meta.review`。

### `review apply --id <role_id> (--from-file <resp.txt> | --verdict <v> --score <n> [...])`
把手工或外部 LLM 的评审结果挂到角色上。两种输入方式二选一：
- `--from-file`：外部 LLM 的原始响应（会自动解析 JSON）
- 手工：`--verdict approved|needs_work|rejected --score 1-5 --strengths "a|b" --issues "c|d" --fix-hints "e"`

### `review status [--status official] [--show-samples]`
汇总评审状态：verdict 分布 / score 分布 / unreviewed 数量。

## upstream — 上游源管理 *(private core)*

多上游接入（`agency-agents / 0xfurai / VoltAgent / wshobson`）的 `list / info / import / import-all / reimport / reimport-all / drift` 子命令树在 private core 仓。showcase 的 registry 已经是**预导入**好的 105 条 approved 快照，不需要这些子命令就能直接用。

## 退出码约定

| exit | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 通用错误（参数错 / 角色不存在 / gate 失败 / registry 校验失败 / review 失败） |
| 2 | `find` 三维全 miss；`review run` 缺 API key |

## 常用组合式

```bash
# 手写一个角色到 official
vim my-role.yaml
rolecore role validate --file my-role.yaml
rolecore role create --file my-role.yaml
rolecore role gate --id <id>                   # 看缺口
rolecore role promote --id <id> --to normalized
rolecore review prompt --id <id>               # 离线跑复核，贴 LLM
rolecore review apply --id <id> --from-file response.txt
rolecore role promote --id <id> --to curated
rolecore role promote --id <id> --to official

# 日常检索
rolecore find "python backend api"            # 三维融合
rolecore assemble --id <id> --task "..." --goal "..."

# 健康巡检
rolecore registry stats
rolecore registry verify
```
