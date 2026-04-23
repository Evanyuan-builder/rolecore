# 质量复核工作流

`meta.review` 是 first-class 字段，由 `rolecore/core/reviewer.py` 维护。复核的存在是为了堵住**「结构合法但内容空洞」**的角色混进 official——official gate 只管结构，curated gate 管内容。

## 五维评审 rubric

LLM 或人类评审按这五维打分：

| 维度 | 看什么 |
|---|---|
| **Coherence** | identity / mission / boundaries / workflows 讲的是同一个角色还是拼凑的 |
| **Specificity** | 内容是针对这个角色的，还是哪个角色都能套的 boilerplate |
| **Actionability** | workflow 步骤具体到 LLM 不用猜就能照做 |
| **Boundaries** | can_do / cannot_do 现实且不跟 positioning 打架 |
| **Evaluation** | metrics / success_criteria 反映这个角色真的在做的事 |

完整 prompt 在 `REVIEW_SYSTEM_PROMPT`（`rolecore/core/reviewer.py`）。

## verdict 语义

| verdict | 含义 | 能晋升 `curated` 吗 |
|---|---|---|
| `approved` | 内容过关，production-ready | ✅ |
| `needs_work` | 可救，但有具体缺口 | ❌ |
| `rejected` | 太泛 / 互相矛盾 / 低信噪比 | ❌ |

rubric 明确要求 LLM **对 `approved` 吝啬**——看到占位符文字 / 套模板 workflow / 模糊 metric 默认打 `needs_work`。

`score` 是 1-5 的整数（5=excellent，1=unusable）。**gate 只看 verdict**，score 是辅助排序。

## 三种运行方式

### 方式 A：离线（推荐默认）

```bash
python3 cli.py review prompt --id engineering.backend_architect
```

打印 system + user prompt 到 stdout，你贴到任意 LLM（Claude Web / ChatGPT / 本地模型）。LLM 返回 JSON 后：

```bash
# 把 LLM 的完整响应存成文件
$EDITOR /tmp/review.txt

python3 cli.py review apply --id engineering.backend_architect --from-file /tmp/review.txt
```

`--from-file` 会自动容错代码围栏 / 前后多余说明，只抽 JSON 主体。

### 方式 B：在线（需要 API key）

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python3 cli.py review run --id engineering.backend_architect
```

跑完直接挂 `meta.review`，无需 `apply`。需要 `anthropic` SDK：`pip install anthropic`。

### 方式 C：手工评审

人评的时候：

```bash
python3 cli.py review apply --id engineering.backend_architect \
    --verdict needs_work \
    --score 3 \
    --strengths "positioning 清晰|workflow 步骤明确" \
    --issues "evaluation.metrics 过于模糊|cannot_do 只有一条" \
    --fix-hints "补一条可量化 metric（p95 延迟）|补充至少两条 cannot_do" \
    --reviewer "m2ultra"
```

`|` 分隔列表。`--reviewer` 标注评审人（默认 `human`）。

## `meta.review` 结构

一次评审后 YAML 里会多出这块：

```yaml
meta:
  review:
    verdict: approved
    score: 5
    strengths:
      - positioning 清晰精准
      - workflow 三阶段分解合理
    issues: []
    fix_hints: []
    reviewer_model: claude-opus-4-7
    reviewed_at: '2026-04-22T12:34:56Z'
    prompt_version: v1
```

`prompt_version` 是评审 rubric 的版本号——如果未来改了 `REVIEW_SYSTEM_PROMPT`，旧评审不会自动失效，但你可以用这个字段筛出该重跑的。

## curated gate

`RoleManager.promote_status(role_id, "curated")` 内部检查：

```python
record = get_review_record(role_data)
if not record:
    raise ValueError(f"Role '{role_id}' has no review record...")
if record.verdict != "approved":
    raise ValueError(f"Role '{role_id}' review verdict is '{record.verdict}'...")
```

所以晋升路径是：

```
raw_imported / normalized
  └─▶ review prompt|run|apply    （挂 verdict=approved）
        └─▶ role promote --to curated
              └─▶ role promote --to official   （10 项结构门槛）
```

注意：**现存的 489 个 official 角色没有被回溯要求复核**。curated gate 只作用于未来的 `→ curated` 晋升。如果你想给所有 official 补复核，用批量流程（见下）。

## 批量复核流程

没有一键「review all」，因为跑一次 LLM 不便宜且值得人眼过一遍。推荐半自动：

```bash
# 1. 挑一批候选（比如某 group 里所有 normalized）
python3 cli.py role list --group engineering --status normalized

# 2. 批量生成 prompt 到文件夹
mkdir -p /tmp/reviews
for id in $(python3 cli.py role list --group engineering --status normalized | awk 'NR>2 {print $1}'); do
    python3 cli.py review prompt --id $id --output /tmp/reviews/$id.md
done

# 3. 人工用 Claude / GPT 批量跑，把响应存回 /tmp/reviews/$id.response.txt

# 4. 批量 apply
for id in $(ls /tmp/reviews/ | grep '.response.txt$' | sed 's/.response.txt//'); do
    python3 cli.py review apply --id $id --from-file /tmp/reviews/$id.response.txt
done

# 5. 看结果分布
python3 cli.py review status --status normalized --show-samples

# 6. 批量晋升 approved 的
for id in $(python3 cli.py review status --status normalized --show-samples | grep approved); do
    python3 cli.py role promote --id $id --to curated
done
```

或者用 `review run` 在线跑（需要 API key，成本 ~$0.01/角色）。

## `review status` 命令

看整体评审状态：

```bash
python3 cli.py review status                      # 全部
python3 cli.py review status --status official    # 只看 official
python3 cli.py review status --show-samples       # 列几个 role_id 样本
```

输出示例：

```
Review status across 493 role(s)
  approved     12
  needs_work    3
  rejected      0
  unreviewed  478

Score distribution:
  5⭐  7
  4⭐  5
  3⭐  3
```

## 反模式

1. **别绕过 curated gate**。如果你想「先 promote 到 curated 等回头补 review」——这正是 gate 要防的场景。正确做法：挂一条手工 `--verdict approved` 的 review，并在 `strengths/issues` 写明**当时的判断**，未来重跑时能追溯。
2. **别把 `review run` 跑成 CI 常驻**。每个角色~$0.01，493 角色 ~$5，但连续跑会刷 API 额度。想持续监控内容质量，用外部批处理 + 抽样。
3. **别删除历史 review 字段来「重置」**。改评审 rubric 后应该 bump `prompt_version` 而不是擦掉旧 review——审计留痕是治理资产的一部分。

## 相关

- [concepts.md](concepts.md) — 两道 gate 的全文解释
- [cli.md](cli.md) — `review` 命令完整参数
- [architecture.md](architecture.md) — `Reviewer` 类结构和 gate 实现位置
