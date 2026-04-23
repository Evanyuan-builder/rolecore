from dataclasses import dataclass, field
from typing import Optional

from .role import normalize_status


@dataclass
class VersionEntry:
    version: str
    file_path: str
    created_at: str
    description: str
    checksum: str

    @classmethod
    def from_dict(cls, d: dict) -> "VersionEntry":
        return cls(
            version=str(d["version"]),
            file_path=d["file_path"],
            created_at=d.get("created_at", ""),
            description=d.get("description", ""),
            checksum=d.get("checksum", ""),
        )

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "file_path": self.file_path,
            "created_at": self.created_at,
            "description": self.description,
            "checksum": self.checksum,
        }


@dataclass
class EntryMeta:
    author: str
    created_at: str
    updated_at: str
    status: str

    @classmethod
    def from_dict(cls, d: dict) -> "EntryMeta":
        return cls(
            author=d.get("author", "system"),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            status=normalize_status(d.get("status", "raw_imported")),
        )

    def to_dict(self) -> dict:
        return {
            "author": self.author,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
        }


@dataclass
class RegistryEntry:
    role_id: str
    name_cn: str
    name_en: str
    group: str
    domain: str
    tags: list
    latest_version: str
    versions: dict  # version_str -> VersionEntry
    meta: EntryMeta

    @classmethod
    def from_dict(cls, d: dict) -> "RegistryEntry":
        versions = {
            k: VersionEntry.from_dict(v)
            for k, v in d.get("versions", {}).items()
        }
        return cls(
            role_id=d["role_id"],
            name_cn=d.get("name_cn", ""),
            name_en=d.get("name_en", ""),
            group=d["group"],
            domain=d.get("domain", ""),
            tags=d.get("tags", []),
            latest_version=str(d["latest_version"]),
            versions=versions,
            meta=EntryMeta.from_dict(d.get("meta", {})),
        )

    def to_dict(self) -> dict:
        return {
            "role_id": self.role_id,
            "name_cn": self.name_cn,
            "name_en": self.name_en,
            "group": self.group,
            "domain": self.domain,
            "tags": self.tags,
            "latest_version": self.latest_version,
            "versions": {k: v.to_dict() for k, v in self.versions.items()},
            "meta": self.meta.to_dict(),
        }

    def get_version_entry(self, version: str) -> Optional[VersionEntry]:
        return self.versions.get(str(version))

    def get_latest_entry(self) -> Optional[VersionEntry]:
        return self.versions.get(self.latest_version)
