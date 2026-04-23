import json

from ..models.role import RoleAsset


class JsonExporter:
    def export(
        self,
        role: RoleAsset,
        task: str,
        goal: str,
        context: dict = None,
        include_fields: list = None,
    ) -> dict:
        role_dict = role.to_dict()

        if include_fields:
            role_dict = {k: v for k, v in role_dict.items() if k in include_fields}

        return {
            "role_id": role.role_id,
            "version": role.version,
            "role": role_dict,
            "task": task,
            "goal": goal,
            "context": context or {},
        }

    def export_minimal(self, role: RoleAsset) -> dict:
        return {
            "role_id": role.role_id,
            "version": role.version,
            "identity": role.identity.to_dict(),
            "mission": role.mission.to_dict(),
            "boundaries": role.boundaries.to_dict(),
        }

    def to_json_string(self, data: dict, indent: int = 2) -> str:
        return json.dumps(data, ensure_ascii=False, indent=indent)
