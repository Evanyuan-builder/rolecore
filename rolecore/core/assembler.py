from datetime import datetime, timezone

from ..core.role_manager import RoleManager
from ..models.assembly_context import AssemblyContext
from ..exporters.prompt_exporter import PromptExporter
from ..exporters.json_exporter import JsonExporter
from ..exporters.markdown_exporter import MarkdownExporter


class Assembler:
    def __init__(self, role_manager: RoleManager):
        self.role_manager = role_manager
        self._prompt_exporter = PromptExporter()
        self._json_exporter = JsonExporter()
        self._markdown_exporter = MarkdownExporter()

    def assemble(
        self,
        role_id: str,
        task: str,
        goal: str,
        context: dict = None,
        version: str = "latest",
        export_format: str = "prompt",
    ) -> AssemblyContext:
        errors = self.validate_assembly_inputs(role_id, task, goal)
        if errors:
            raise ValueError("Invalid assembly inputs:\n" + "\n".join(f"  - {e}" for e in errors))

        role = self.role_manager.get_role(role_id, version)
        ctx = context or {}

        if export_format == "json":
            output = self._json_exporter.to_json_string(
                self._json_exporter.export(role, task, goal, ctx)
            )
        elif export_format == "markdown":
            output = self._markdown_exporter.export(role)
        else:
            output = self._prompt_exporter.export(role, task, goal, ctx)

        return AssemblyContext(
            role_id=role_id,
            version=role.version,
            task=task,
            goal=goal,
            context=ctx,
            role=role,
            assembled_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            prompt=output,
            export_format=export_format,
        )

    def assemble_batch(self, requests: list) -> list:
        results = []
        for req in requests:
            try:
                ac = self.assemble(
                    role_id=req["role_id"],
                    task=req["task"],
                    goal=req["goal"],
                    context=req.get("context"),
                    version=req.get("version", "latest"),
                    export_format=req.get("export_format", "prompt"),
                )
                results.append({"ok": True, "result": ac})
            except Exception as e:
                results.append({"ok": False, "role_id": req.get("role_id"), "error": str(e)})
        return results

    def validate_assembly_inputs(self, role_id: str, task: str, goal: str) -> list:
        errors = []
        if not role_id or not role_id.strip():
            errors.append("role_id is required")
        elif "." not in role_id:
            errors.append("role_id must be in 'group.role_name' format")
        if not task or not task.strip():
            errors.append("task is required")
        if not goal or not goal.strip():
            errors.append("goal is required")
        return errors
