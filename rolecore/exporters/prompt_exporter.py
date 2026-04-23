from ..models.role import RoleAsset


class PromptExporter:
    def export(self, role: RoleAsset, task: str, goal: str, context: dict = None) -> str:
        sections = [
            self._render_identity_section(role),
            self._render_mission_section(role),
            self._render_boundaries_section(role),
            self._render_behavior_section(role),
            self._render_workflows_section(role),
            self._render_task_section(task, goal),
        ]
        if context:
            sections.append(self._render_context_section(context))
        sections.append(
            "请严格按照该岗位的身份、边界、工作流、交付物和成功标准执行任务。\n"
            "如果当前任务超出该岗位职责，请明确指出边界，不要越权发挥。"
        )
        return "\n\n".join(s for s in sections if s)

    def _render_identity_section(self, role: RoleAsset) -> str:
        i = role.identity
        return (
            f"【岗位身份】\n"
            f"中文名：{i.name_cn}\n"
            f"英文名：{i.name_en}\n"
            f"责任域：{i.domain}\n"
            f"岗位定位：{i.positioning.strip()}"
        )

    def _render_mission_section(self, role: RoleAsset) -> str:
        m = role.mission
        accountability = "\n".join(f"  - {a}" for a in m.core_accountability)
        return (
            f"【岗位使命】\n"
            f"{m.summary.strip()}\n\n"
            f"核心负责事项：\n{accountability}"
        )

    def _render_boundaries_section(self, role: RoleAsset) -> str:
        b = role.boundaries
        can = "\n".join(f"  ✓ {x}" for x in b.can_do)
        cannot = "\n".join(f"  ✗ {x}" for x in b.cannot_do)
        escalate = "\n".join(f"  ↑ {x}" for x in b.escalate_when)
        return (
            f"【职责边界】\n"
            f"可以做：\n{can}\n\n"
            f"不可做：\n{cannot}\n\n"
            f"需要升级或移交的情况：\n{escalate}"
        )

    def _render_behavior_section(self, role: RoleAsset) -> str:
        bh = role.behavior
        return (
            f"【行为风格】\n"
            f"沟通风格：{bh.communication_style}\n"
            f"风险偏好：{bh.risk_preference}\n"
            f"决策方式：{bh.decision_approach}\n"
            f"协作方式：{bh.collaboration_mode}"
        )

    def _render_workflows_section(self, role: RoleAsset) -> str:
        if not role.workflows:
            return ""
        parts = ["【标准工作流】"]
        for wf in role.workflows:
            steps = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(wf.steps))
            parts.append(f"{wf.name}：\n{steps}")
        return "\n\n".join(parts)

    def _render_task_section(self, task: str, goal: str) -> str:
        return f"【当前任务】\n{task}\n\n【目标】\n{goal}"

    def _render_context_section(self, context: dict) -> str:
        if not context:
            return ""
        lines = "\n".join(f"  {k}: {v}" for k, v in context.items())
        return f"【补充上下文】\n{lines}"
