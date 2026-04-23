import json
import os
from datetime import datetime, timezone
from typing import Optional


def _empty_registry() -> dict:
    return {
        "version": "1.0",
        "updated_at": "",
        "roles": {},
        "groups": {},
        "tag_index": {},
    }


class RegistryStore:
    def __init__(self, registry_path: str):
        self.registry_path = registry_path

    def load(self) -> dict:
        if not os.path.exists(self.registry_path):
            return _empty_registry()
        with open(self.registry_path, encoding="utf-8") as f:
            data = json.load(f)
        for key, default in _empty_registry().items():
            data.setdefault(key, default)
        return data

    def save(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
        data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        tmp_path = self.registry_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.registry_path)

    def get_entry(self, role_id: str) -> Optional[dict]:
        data = self.load()
        return data["roles"].get(role_id)

    def put_entry(self, role_id: str, entry: dict) -> None:
        data = self.load()
        data["roles"][role_id] = entry
        self._sync_group(data, role_id, entry)
        self.update_tag_index_in(data, role_id, entry.get("tags", []))
        self.save(data)

    def delete_entry(self, role_id: str) -> None:
        data = self.load()
        entry = data["roles"].pop(role_id, None)
        if entry:
            group = entry.get("group", "")
            if group in data["groups"]:
                ids = data["groups"][group].get("role_ids", [])
                if role_id in ids:
                    ids.remove(role_id)
            for tag, ids in data["tag_index"].items():
                if role_id in ids:
                    ids.remove(role_id)
        self.save(data)

    def list_all_entries(self) -> list:
        return list(self.load()["roles"].values())

    def update_tag_index(self, role_id: str, tags: list) -> None:
        data = self.load()
        self.update_tag_index_in(data, role_id, tags)
        self.save(data)

    def rebuild_tag_index(self) -> None:
        data = self.load()
        data["tag_index"] = {}
        for role_id, entry in data["roles"].items():
            self.update_tag_index_in(data, role_id, entry.get("tags", []))
        self.save(data)

    # --- internal helpers ---

    def _sync_group(self, data: dict, role_id: str, entry: dict) -> None:
        group = entry.get("group", "")
        if not group:
            return
        if group not in data["groups"]:
            data["groups"][group] = {"label": group, "description": "", "role_ids": []}
        ids = data["groups"][group].setdefault("role_ids", [])
        if role_id not in ids:
            ids.append(role_id)

    def update_tag_index_in(self, data: dict, role_id: str, tags: list) -> None:
        # Remove old entries for this role
        for tag_ids in data["tag_index"].values():
            if role_id in tag_ids:
                tag_ids.remove(role_id)
        # Add new
        for tag in tags:
            data["tag_index"].setdefault(tag, [])
            if role_id not in data["tag_index"][tag]:
                data["tag_index"][tag].append(role_id)
