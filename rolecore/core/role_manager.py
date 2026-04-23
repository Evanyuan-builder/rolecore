from datetime import datetime, timezone
from typing import Optional

from ..models.role import RoleAsset, VALID_STATUSES, normalize_status
from ..models.registry_entry import RegistryEntry, VersionEntry, EntryMeta
from ..storage.role_store import RoleStore
from ..storage.registry_store import RegistryStore
from ..utils.path_utils import role_id_to_parts
from ..utils.version_utils import next_version, resolve_version, sort_versions
from ..utils.schema_validator import SchemaValidator, OfficialGateValidator

# Ordered status progression
_STATUS_ORDER = ["raw_imported", "normalized", "curated", "official", "archived"]


class RoleNotFoundError(Exception):
    pass


class RoleManager:
    def __init__(self, role_store: RoleStore, registry_store: RegistryStore):
        self.role_store = role_store
        self.registry_store = registry_store
        self._validator = SchemaValidator()

    def create_role(
        self,
        role_data: dict,
        version: str = "1",
        author: str = "system",
    ) -> RoleAsset:
        self._validator.validate_or_raise(role_data)

        role_id = role_data["meta"]["role_id"]
        group, role_name = role_id_to_parts(role_id)

        if self.registry_store.get_entry(role_id):
            raise ValueError(f"Role '{role_id}' already exists. Use update_role() to add versions.")

        now = self._now()
        role_data["meta"]["version"] = str(version)
        role_data["meta"].setdefault("created_at", now)
        role_data["meta"]["updated_at"] = now
        role_data["meta"]["author"] = author

        file_path = self.role_store.write_role(group, role_name, version, role_data)
        checksum = self.role_store.compute_checksum(file_path)

        entry = {
            "role_id": role_id,
            "name_cn": role_data["identity"]["name_cn"],
            "name_en": role_data["identity"]["name_en"],
            "group": group,
            "domain": role_data["identity"].get("domain", ""),
            "tags": role_data["meta"].get("tags", []),
            "latest_version": str(version),
            "versions": {
                str(version): {
                    "version": str(version),
                    "file_path": file_path,
                    "created_at": now,
                    "description": role_data["meta"].get("description", ""),
                    "checksum": checksum,
                }
            },
            "meta": {
                "author": author,
                "created_at": now,
                "updated_at": now,
                "status": normalize_status(role_data["meta"].get("status", "raw_imported")),
            },
        }
        self.registry_store.put_entry(role_id, entry)

        return RoleAsset.from_dict(role_data)

    def get_role(self, role_id: str, version: str = "latest") -> RoleAsset:
        entry_dict = self.registry_store.get_entry(role_id)
        if not entry_dict:
            raise RoleNotFoundError(f"Role '{role_id}' not found in registry")

        entry = RegistryEntry.from_dict(entry_dict)
        available = list(entry.versions.keys())
        resolved = resolve_version(version, available, entry.latest_version)

        ver_entry = entry.get_version_entry(resolved)
        if not ver_entry:
            raise RoleNotFoundError(f"Role '{role_id}' version '{resolved}' not in registry")

        group, role_name = role_id_to_parts(role_id)
        data = self.role_store.read_role(group, role_name, resolved)
        return RoleAsset.from_dict(data)

    def update_role(
        self,
        role_id: str,
        role_data: dict,
        new_version: Optional[str] = None,
        description: str = "",
    ) -> RoleAsset:
        self._validator.validate_or_raise(role_data)

        entry_dict = self.registry_store.get_entry(role_id)
        if not entry_dict:
            raise RoleNotFoundError(f"Role '{role_id}' not found")

        entry = RegistryEntry.from_dict(entry_dict)
        version = new_version or next_version(entry.latest_version)
        group, role_name = role_id_to_parts(role_id)

        now = self._now()
        role_data["meta"]["version"] = str(version)
        role_data["meta"]["updated_at"] = now

        file_path = self.role_store.write_role(group, role_name, version, role_data)
        checksum = self.role_store.compute_checksum(file_path)

        entry_dict["versions"][str(version)] = {
            "version": str(version),
            "file_path": file_path,
            "created_at": now,
            "description": description or role_data["meta"].get("description", ""),
            "checksum": checksum,
        }
        entry_dict["latest_version"] = str(version)
        entry_dict["meta"]["updated_at"] = now
        entry_dict["tags"] = role_data["meta"].get("tags", entry_dict.get("tags", []))
        entry_dict["meta"]["status"] = normalize_status(
            role_data["meta"].get("status", entry_dict["meta"].get("status", "raw_imported"))
        )

        self.registry_store.put_entry(role_id, entry_dict)
        return RoleAsset.from_dict(role_data)

    def deprecate_role(self, role_id: str) -> None:
        entry_dict = self.registry_store.get_entry(role_id)
        if not entry_dict:
            raise RoleNotFoundError(f"Role '{role_id}' not found")
        entry_dict["meta"]["status"] = "archived"
        entry_dict["meta"]["updated_at"] = self._now()
        self.registry_store.put_entry(role_id, entry_dict)

    def _refresh_version_checksum(self, entry_dict: dict, version: str) -> None:
        """Recompute checksum for a version after an on-disk write.
        Mutates entry_dict in place; caller is responsible for persisting."""
        ver = entry_dict.get("versions", {}).get(str(version))
        if not ver:
            return
        ver["checksum"] = self.role_store.compute_checksum(ver["file_path"])

    def resync_entry_from_yaml(self, role_id: str) -> dict:
        """Re-populate the registry entry's denormalized fields
        (name_cn, name_en, domain, tags, status, review) from the latest YAML on disk.
        Also refreshes the checksum. Returns a dict summarizing what changed.
        """
        entry_dict = self.registry_store.get_entry(role_id)
        if not entry_dict:
            raise RoleNotFoundError(f"Role '{role_id}' not found")
        group, role_name = role_id_to_parts(role_id)
        latest = entry_dict["latest_version"]
        data = self.role_store.read_role(group, role_name, latest)
        ident = data.get("identity", {}) or {}
        meta = data.get("meta", {}) or {}

        changes = {}
        new_name_cn = ident.get("name_cn", "")
        new_name_en = ident.get("name_en", "")
        new_domain = ident.get("domain", "")
        new_tags = meta.get("tags", []) or []
        new_status = normalize_status(meta.get("status", entry_dict["meta"].get("status", "raw_imported")))

        yaml_review = meta.get("review") or {}
        new_review = None
        if yaml_review:
            new_review = {
                "verdict": yaml_review.get("verdict", ""),
                "score": int(yaml_review.get("score") or 0),
                "reviewed_at": yaml_review.get("reviewed_at", ""),
            }

        if entry_dict.get("name_cn", "") != new_name_cn:
            changes["name_cn"] = (entry_dict.get("name_cn", ""), new_name_cn)
            entry_dict["name_cn"] = new_name_cn
        if entry_dict.get("name_en", "") != new_name_en:
            changes["name_en"] = (entry_dict.get("name_en", ""), new_name_en)
            entry_dict["name_en"] = new_name_en
        if entry_dict.get("domain", "") != new_domain:
            changes["domain"] = (entry_dict.get("domain", ""), new_domain)
            entry_dict["domain"] = new_domain
        if entry_dict.get("tags", []) != new_tags:
            changes["tags"] = (entry_dict.get("tags", []), new_tags)
            entry_dict["tags"] = new_tags
        if entry_dict["meta"].get("status", "") != new_status:
            changes["status"] = (entry_dict["meta"].get("status", ""), new_status)
            entry_dict["meta"]["status"] = new_status
        cur_review = entry_dict["meta"].get("review")
        if cur_review != new_review:
            changes["review"] = (cur_review, new_review)
            if new_review is None:
                entry_dict["meta"].pop("review", None)
            else:
                entry_dict["meta"]["review"] = new_review

        self._refresh_version_checksum(entry_dict, latest)
        if changes:
            entry_dict["meta"]["updated_at"] = self._now()
            self.registry_store.put_entry(role_id, entry_dict)
        return changes

    def delete_role(self, role_id: str, version: Optional[str] = None) -> None:
        entry_dict = self.registry_store.get_entry(role_id)
        if not entry_dict:
            raise RoleNotFoundError(f"Role '{role_id}' not found")

        group, role_name = role_id_to_parts(role_id)

        if version:
            self.role_store.delete_role_version(group, role_name, version)
            entry_dict["versions"].pop(str(version), None)
            if entry_dict["latest_version"] == str(version):
                remaining = sort_versions(list(entry_dict["versions"].keys()))
                entry_dict["latest_version"] = remaining[-1] if remaining else ""
            self.registry_store.put_entry(role_id, entry_dict)
        else:
            for ver in list(entry_dict["versions"].keys()):
                self.role_store.delete_role_version(group, role_name, ver)
            self.registry_store.delete_entry(role_id)

    def list_roles(self, group: Optional[str] = None, status: str = "live") -> list:
        """
        status values:
          specific status  → exact match (raw_imported / normalized / curated / official / archived)
          "live"           → all except archived  (default)
          "all"            → every role regardless of status
          "active"         → backward-compat alias for "live"
        """
        entries = self.registry_store.list_all_entries()
        result = []
        for e in entries:
            entry_status = normalize_status(e.get("meta", {}).get("status", "raw_imported"))
            if status in ("all",):
                pass
            elif status in ("live", "active"):
                if entry_status == "archived":
                    continue
            else:
                if entry_status != status:
                    continue
            if group and e.get("group") != group:
                continue
            result.append(RegistryEntry.from_dict(e))
        return result

    def promote_status(self, role_id: str, to_status: str) -> str:
        """
        Advance a role to the given status.
        Raises ValueError if to_status is not in VALID_STATUSES, or if the
        transition would skip a level (except archiving, which is always allowed).
        Returns the new status string.
        """
        if to_status not in VALID_STATUSES:
            raise ValueError(
                f"Unknown status '{to_status}'. Valid: {', '.join(sorted(VALID_STATUSES))}"
            )

        entry_dict = self.registry_store.get_entry(role_id)
        if not entry_dict:
            raise RoleNotFoundError(f"Role '{role_id}' not found")

        current = normalize_status(entry_dict.get("meta", {}).get("status", "raw_imported"))

        # Archiving is always permitted; otherwise enforce forward-only ordering
        if to_status != "archived":
            try:
                cur_idx = _STATUS_ORDER.index(current)
                tgt_idx = _STATUS_ORDER.index(to_status)
            except ValueError:
                cur_idx, tgt_idx = -1, 0
            if tgt_idx <= cur_idx:
                raise ValueError(
                    f"Cannot move '{role_id}' from '{current}' to '{to_status}' "
                    f"— status must advance forward (or archive)"
                )

        # Gate check before promoting to official
        if to_status == "official":
            group, role_name = role_id_to_parts(role_id)
            data = self.role_store.read_role(group, role_name, entry_dict["latest_version"])
            gaps = OfficialGateValidator().check(data)
            if gaps:
                raise ValueError(
                    f"Role '{role_id}' does not meet official gate requirements:\n"
                    + "\n".join(f"  • {g}" for g in gaps)
                )

        # Gate check before promoting to curated: must have an approved review.
        if to_status == "curated":
            from .reviewer import get_review_record
            group, role_name = role_id_to_parts(role_id)
            data = self.role_store.read_role(group, role_name, entry_dict["latest_version"])
            record = get_review_record(data)
            if not record:
                raise ValueError(
                    f"Role '{role_id}' has no review record. Attach one first via "
                    "`review run` or `review apply` before promoting to curated."
                )
            if record.verdict != "approved":
                raise ValueError(
                    f"Role '{role_id}' review verdict is '{record.verdict}' "
                    f"(score {record.score}); only 'approved' reviews may advance to curated."
                )

        # Update the status field inside the YAML file for the latest version
        group, role_name = role_id_to_parts(role_id)
        latest_ver = entry_dict["latest_version"]
        data = self.role_store.read_role(group, role_name, latest_ver)
        data["meta"]["status"] = to_status
        self.role_store.write_role(group, role_name, latest_ver, data)

        entry_dict["meta"]["status"] = to_status
        entry_dict["meta"]["updated_at"] = self._now()
        self._refresh_version_checksum(entry_dict, latest_ver)
        self.registry_store.put_entry(role_id, entry_dict)

        return to_status

    def check_official_gate(self, role_id: str) -> list:
        """Return list of gap strings for the role's latest version. Empty = passes."""
        entry_dict = self.registry_store.get_entry(role_id)
        if not entry_dict:
            raise RoleNotFoundError(f"Role '{role_id}' not found")
        group, role_name = role_id_to_parts(role_id)
        data = self.role_store.read_role(group, role_name, entry_dict["latest_version"])
        return OfficialGateValidator().check(data)

    def mark_enhanced_fields(self, role_id: str, field_paths: list) -> None:
        """
        Mark dot-path fields (e.g. 'identity.name_cn') as manually enhanced.
        These fields will be protected from upstream reimport overwrites.
        """
        from ..upstream.reimporter import mark_enhanced
        entry_dict = self.registry_store.get_entry(role_id)
        if not entry_dict:
            raise RoleNotFoundError(f"Role '{role_id}' not found")
        group, role_name = role_id_to_parts(role_id)
        latest_ver = entry_dict["latest_version"]
        data = self.role_store.read_role(group, role_name, latest_ver)
        updated = mark_enhanced(data, field_paths)
        self.role_store.write_role(group, role_name, latest_ver, updated)
        self._refresh_version_checksum(entry_dict, latest_ver)
        entry_dict["meta"]["updated_at"] = self._now()
        self.registry_store.put_entry(role_id, entry_dict)

    def unmark_enhanced_fields(self, role_id: str, field_paths: list) -> None:
        """Remove dot-path fields from the enhanced protection list."""
        from ..upstream.reimporter import unmark_enhanced
        entry_dict = self.registry_store.get_entry(role_id)
        if not entry_dict:
            raise RoleNotFoundError(f"Role '{role_id}' not found")
        group, role_name = role_id_to_parts(role_id)
        latest_ver = entry_dict["latest_version"]
        data = self.role_store.read_role(group, role_name, latest_ver)
        updated = unmark_enhanced(data, field_paths)
        self.role_store.write_role(group, role_name, latest_ver, updated)
        self._refresh_version_checksum(entry_dict, latest_ver)
        entry_dict["meta"]["updated_at"] = self._now()
        self.registry_store.put_entry(role_id, entry_dict)

    def get_versions(self, role_id: str) -> list:
        entry_dict = self.registry_store.get_entry(role_id)
        if not entry_dict:
            raise RoleNotFoundError(f"Role '{role_id}' not found")
        return sort_versions(list(entry_dict["versions"].keys()))

    def set_latest(self, role_id: str, version: str) -> None:
        entry_dict = self.registry_store.get_entry(role_id)
        if not entry_dict:
            raise RoleNotFoundError(f"Role '{role_id}' not found")
        if str(version) not in entry_dict["versions"]:
            raise ValueError(f"Version '{version}' does not exist for '{role_id}'")
        entry_dict["latest_version"] = str(version)
        entry_dict["meta"]["updated_at"] = self._now()
        self.registry_store.put_entry(role_id, entry_dict)

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
