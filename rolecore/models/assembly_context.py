from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AssemblyContext:
    role_id: str
    version: str
    task: str
    goal: str
    context: dict
    role: object  # RoleAsset — avoid circular import with string annotation
    assembled_at: str
    prompt: str = ""
    export_format: str = "prompt"

    def to_dict(self) -> dict:
        return {
            "role_id": self.role_id,
            "version": self.version,
            "task": self.task,
            "goal": self.goal,
            "context": self.context,
            "assembled_at": self.assembled_at,
            "export_format": self.export_format,
            "prompt": self.prompt,
        }
