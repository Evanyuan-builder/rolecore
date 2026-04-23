from ..models.registry_entry import RegistryEntry
from ..storage.registry_store import RegistryStore


class SearchEngine:
    def __init__(self, registry_store: RegistryStore):
        self.registry_store = registry_store

    def search_by_group(self, group: str) -> list:
        return [
            RegistryEntry.from_dict(e)
            for e in self.registry_store.list_all_entries()
            if e.get("group") == group
        ]

    def search_by_tags(self, tags: list, match_mode: str = "any") -> list:
        data = self.registry_store.load()
        tag_index = data.get("tag_index", {})

        if match_mode == "all":
            candidate_sets = [set(tag_index.get(t, [])) for t in tags]
            if not candidate_sets:
                return []
            role_ids = candidate_sets[0].intersection(*candidate_sets[1:])
        else:
            role_ids = set()
            for tag in tags:
                role_ids.update(tag_index.get(tag, []))

        result = []
        for role_id in role_ids:
            entry = data["roles"].get(role_id)
            if entry:
                result.append(RegistryEntry.from_dict(entry))
        return result

    def search_by_keyword(self, keyword: str, fields: list = None) -> list:
        if fields is None:
            fields = ["name_cn", "name_en", "domain", "tags"]
        kw = keyword.lower()
        result = []
        for entry_dict in self.registry_store.list_all_entries():
            if self._entry_matches_keyword(entry_dict, kw, fields):
                result.append(RegistryEntry.from_dict(entry_dict))
        return result

    def search(
        self,
        group: str = None,
        tags: list = None,
        keyword: str = None,
        tag_match_mode: str = "any",
        status: str = "active",
    ) -> list:
        entries = self.registry_store.list_all_entries()
        result = []
        kw = keyword.lower() if keyword else None

        for entry_dict in entries:
            if status and entry_dict.get("meta", {}).get("status") != status:
                continue
            if group and entry_dict.get("group") != group:
                continue
            if tags:
                entry_tags = set(entry_dict.get("tags", []))
                if tag_match_mode == "all":
                    if not set(tags).issubset(entry_tags):
                        continue
                else:
                    if not set(tags).intersection(entry_tags):
                        continue
            if kw and not self._entry_matches_keyword(
                entry_dict, kw, ["name_cn", "name_en", "domain", "tags"]
            ):
                continue
            result.append(RegistryEntry.from_dict(entry_dict))
        return result

    def get_all_groups(self) -> list:
        data = self.registry_store.load()
        return sorted(data.get("groups", {}).keys())

    def get_all_tags(self) -> list:
        data = self.registry_store.load()
        return sorted(data.get("tag_index", {}).keys())

    def _entry_matches_keyword(self, entry_dict: dict, kw: str, fields: list) -> bool:
        for field in fields:
            val = entry_dict.get(field, "")
            if isinstance(val, list):
                if any(kw in str(item).lower() for item in val):
                    return True
            elif isinstance(val, str):
                if kw in val.lower():
                    return True
        return False
