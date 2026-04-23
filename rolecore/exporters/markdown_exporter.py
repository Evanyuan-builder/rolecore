from ..models.role import RoleAsset


class MarkdownExporter:
    def export(self, role: RoleAsset) -> str:
        i = role.identity
        m = role.meta
        sections = [
            f"# {i.name_cn} / {i.name_en}",
            f"> **岗位 ID**: `{role.role_id}` | **版本**: v{role.version} | **状态**: {m.status}",
            "",
            self._render_identity(role),
            self._render_mission(role),
            self._render_boundaries(role),
            self._render_io(role),
            self._render_behavior(role),
            self._render_workflows(role),
            self._render_capabilities(role),
            self._render_evaluation(role),
        ]
        return "\n\n".join(s for s in sections if s)

    def export_summary(self, role: RoleAsset) -> str:
        i = role.identity
        m = role.mission
        ev = role.evaluation
        metrics = "\n".join(f"- {x}" for x in ev.metrics[:3])
        return (
            f"## {i.name_cn} / {i.name_en}\n\n"
            f"**定位**: {i.positioning.strip()}\n\n"
            f"**使命**: {m.summary.strip()}\n\n"
            f"**核心指标**:\n{metrics}"
        )

    def _render_identity(self, role: RoleAsset) -> str:
        i = role.identity
        return (
            f"## 岗位身份\n\n"
            f"| 字段 | 内容 |\n"
            f"|------|------|\n"
            f"| 中文名 | {i.name_cn} |\n"
            f"| 英文名 | {i.name_en} |\n"
            f"| 责任域 | {i.domain} |\n\n"
            f"**定位**\n\n{i.positioning.strip()}"
        )

    def _render_mission(self, role: RoleAsset) -> str:
        m = role.mission
        items = "\n".join(f"- {a}" for a in m.core_accountability)
        return f"## 岗位使命\n\n{m.summary.strip()}\n\n**核心负责事项**\n\n{items}"

    def _render_boundaries(self, role: RoleAsset) -> str:
        b = role.boundaries
        can = "\n".join(f"- {x}" for x in b.can_do)
        cannot = "\n".join(f"- {x}" for x in b.cannot_do)
        escalate = "\n".join(f"- {x}" for x in b.escalate_when)
        return (
            f"## 职责边界\n\n"
            f"### 可以做\n\n{can}\n\n"
            f"### 不可做\n\n{cannot}\n\n"
            f"### 需要升级或移交的情况\n\n{escalate}"
        )

    def _render_io(self, role: RoleAsset) -> str:
        io = role.io
        inputs = "\n".join(f"- {x}" for x in io.inputs)
        outputs = "\n".join(f"- {x}" for x in io.outputs)
        return f"## 输入与输出\n\n**输入**\n\n{inputs}\n\n**输出**\n\n{outputs}"

    def _render_behavior(self, role: RoleAsset) -> str:
        bh = role.behavior
        return (
            f"## 行为风格\n\n"
            f"| 维度 | 描述 |\n"
            f"|------|------|\n"
            f"| 沟通风格 | {bh.communication_style} |\n"
            f"| 风险偏好 | {bh.risk_preference} |\n"
            f"| 决策方式 | {bh.decision_approach} |\n"
            f"| 协作方式 | {bh.collaboration_mode} |"
        )

    def _render_workflows(self, role: RoleAsset) -> str:
        if not role.workflows:
            return ""
        parts = ["## 工作流模板"]
        for wf in role.workflows:
            steps = "\n".join(f"{i+1}. {s}" for i, s in enumerate(wf.steps))
            parts.append(f"### {wf.name}\n\n{steps}")
        return "\n\n".join(parts)

    def _render_capabilities(self, role: RoleAsset) -> str:
        cap = role.capabilities
        tools = "\n".join(f"- {x}" for x in cap.tools)
        knowledge = "\n".join(f"- {x}" for x in cap.knowledge)
        ctx = "\n".join(f"- {x}" for x in cap.context_requirements)
        runtime = "\n".join(f"- {x}" for x in cap.runtime_conditions)
        return (
            f"## 能力需求\n\n"
            f"**工具**\n\n{tools}\n\n"
            f"**知识**\n\n{knowledge}\n\n"
            f"**上下文需求**\n\n{ctx}\n\n"
            f"**运行条件**\n\n{runtime}"
        )

    def _render_evaluation(self, role: RoleAsset) -> str:
        ev = role.evaluation
        metrics = "\n".join(f"- {x}" for x in ev.metrics)
        criteria = "\n".join(f"- {x}" for x in ev.success_criteria)
        return f"## 评价标准\n\n**度量指标**\n\n{metrics}\n\n**成功标准**\n\n{criteria}"
