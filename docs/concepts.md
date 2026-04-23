# 核心概念

## 为什么要有 RoleCore

LLM agent 的"角色"很容易写得很漂亮但不能落地——positioning 一段空话、workflow 泛泛而谈、
评价指标写了等于没写。RoleCore 把角色当成**资产**来管：结构化、版本化、有治理、有复核、
支持跨多个上游源统一收编。

## 角色资产 = 一个 YAML

每个角色是一份 `roles/<group>/<role_name>/v<N>.yaml`。Schema 强制九个顶层 section：

```yaml
meta:         # role_id / version / group / tags / status / source / review
identity:     # name_cn / name_en / domain / positioning
mission:      # summary / core_accountability[]
boundaries:   # can_do[] / cannot_do[] / escalate_when[]
io:           # inputs[] / outputs[]
behavior:     # communication_style / risk_preference / decision_approach / collaboration_mode
workflows:    # [{name, steps[]}]
capabilities: # tools[] / knowledge[] / context_requirements[] / runtime_conditions[]
evaluation:   # metrics[] / success_criteria[]
```

完整 schema 校验规则在 `rolecore/utils/schema_validator.py::SECTION_RULES`。

## 五级生命周期

```
raw_imported → normalized → curated → official → archived
```

| 状态 | 语义 | 谁能进 |
|---|---|---|
| `raw_imported` | 刚从上游 parser 出炉，结构对了但内容没过人工 | parser 自动填 |
| `normalized` | 已做字段补全 / 归一化，但没评审 | 手工 / 脚本 |
| `curated` | 通过 LLM 或人工的**内容质量**复核 | **gate**：挂 `meta.review.verdict == "approved"` |
| `official` | 通过结构性**硬门槛**，可上线 | **gate**：`OfficialGateValidator.check()` 返回空 |
| `archived` | 退役 | 任何状态都可归档 |

**晋升规则**：只能前进，不能倒退（archive 除外）；跳级允许但 gate 必须通过。

晋升命令：
```bash
python3 cli.py role promote --id <role_id> --to <status>
```

## 两道 gate

### Official gate（结构性十项）

`OfficialGateValidator.check()` 检查：

1. `identity.name_cn` 非空 ← **人工确权硬门槛**
2. `identity.positioning` ≥ 60 字
3. `mission.summary` ≥ 80 字
4. `mission.core_accountability` ≥ 3 条真实条目
5. `boundaries.can_do` ≥ 3 条
6. `boundaries.cannot_do` ≥ 1 条
7. `behavior.communication_style` ≥ 30 字且非占位符
8. `workflows` 至少一条 ≥ 3 步的真工作流
9. `evaluation.metrics` ≥ 2 条
10. `evaluation.success_criteria` ≥ 2 条

"真实条目"会过滤掉 importer 留下的占位符（如 `"execute tasks within defined role scope"`），
清单在 `_PLACEHOLDER_PATTERNS`。

### Curated gate（内容质量）

晋升到 `curated` 前必须在 `meta.review` 里挂一条 verdict 为 `approved` 的评审记录。

复核评 5 维：**Coherence / Specificity / Actionability / Boundaries / Evaluation**。
verdict ∈ {`approved`, `needs_work`, `rejected`}，score ∈ 1-5。详见 [reviewer.md](reviewer.md)。

## 三维拓扑

RoleCore 现有 31 个 group，按**上游来源**天然划成三维：

### 岗位维度（14 groups，来自 agency-agents）

偏"人 + 职能"视角：`engineering`, `marketing`, `sales`, `product`, `project_management`,
`academic`, `paid_media`, `game_development`, `spatial_computing`, `strategy`, `support`,
`testing`, `ecommerce`, `specialized`

### 技术栈维度（7 groups，来自 0xfurai）

偏"用什么技术"视角：`language`, `framework`, `database`, `data_ml`, `infrastructure`,
`integration`, `tooling`

### 专业特长维度（10 groups，来自 VoltAgent + wshobson）

偏"哪条专业线"视角：`core_dev`, `language_specialist`, `infra_ops`, `quality_security`,
`data_ai`, `dev_exp`, `specialized_v`, `biz_product`, `meta_orchestration`, `research`

### 三维融合检索

`rolecore find "<query>"` 会同时在三个轴上找最匹配的角色，返回 triad：

```
$ rolecore find "Python 后端 高级开发"
  岗位    : engineering.backend_architect        后端架构师
  技术栈   : language.python                      Python 专家
  专业特长  : language_specialist.python_pro       Python 高级开发
```

实现见 `rolecore/core/fusion_search.py`；评分权重和排序 tiebreak 见 [architecture.md](architecture.md)。

## 治理不变量（违反必炸）

### 1. `identity.name_cn` 必须人工确权

- Parser **绝不**自动填 `name_cn`；机器建议写 `meta.source.name_cn_suggested`
- Official gate 把这条当硬门槛
- 这是为了确保每个中文名都有过一次人类的眼

### 2. 直写 YAML 必须配套刷 checksum

绕过 `update_role` 直接走 `role_store.write_role` 的路径，**必须**接着调
`_refresh_version_checksum(entry_dict, version)`，否则 registry 的 checksum 会漂。

历史上 Phase 2.5 就是被 143/143 漂移教做人才加的这条规则。

配套工具：`python3 cli.py registry resync` 可以一次性修复所有 `name_cn/name_en/domain/tags/status`
的 registry ↔ YAML 漂移，并刷新 checksum。

### 3. 路由表必须硬报错

新加上游源 → 新技术/新 plugin/新 category → 必须在
`ZXF_ROUTE` / `WSHOB_ROUTE` / `VOLT_GROUP_FROM_CATEGORY` 里登记。
未登记的条目会抛 `KeyError`，逼迫人显式做路由决策——绝不让"新东西静默进错组"。

### 4. `meta.source.enhanced_fields` 是 reimport 的护城河

人工增强过的字段（比如手改的 `mission.summary`）要登记在 `enhanced_fields` 里。
`upstream reimport` 重新跑 parser 后，会把 enhanced_fields 里的每条 dot-path 从旧版本恢复回来。

用 `python3 cli.py role mark-enhanced --id X --fields 'mission.summary,identity.positioning'` 登记。

## Registry ↔ YAML 双轨

- **YAML**（`roles/<group>/<role>/v<N>.yaml`）：**真源**
- **registry.json**：索引 + 去规范化缓存（name_cn / name_en / domain / tags / status / checksum）

两者理应同步，但只有 YAML 是真的。`registry verify` 校验文件都在；`registry resync` 把 registry
重新从 YAML 拉一遍；checksum 漂移是 bug，不是功能。

每次重要操作前建议备份：

```bash
cp registry/registry.json registry/registry.json.bak-<tag>-$(date +%Y%m%d-%H%M%S)
```

## 下一步

- 要怎么检索 / 增删改 / 复核 / 同步 → [cli.md](cli.md)
- 怎么接新上游 / 写自定义 parser → [extending.md](extending.md)
- 怎么跑 LLM 复核 → [reviewer.md](reviewer.md)
- 系统内部怎么分层 → [architecture.md](architecture.md)
- 日常怎么运营 → [operations.md](operations.md)
