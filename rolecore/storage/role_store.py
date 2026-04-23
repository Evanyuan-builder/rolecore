import hashlib
import os

import yaml

from ..utils.path_utils import build_role_path, ensure_dir
from ..utils.version_utils import parse_version


class RoleStore:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    def read_role(self, group: str, role_name: str, version: str) -> dict:
        path = self.resolve_path(group, role_name, version)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Role file not found: {path}")
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def write_role(self, group: str, role_name: str, version: str, data: dict) -> str:
        path = self.resolve_path(group, role_name, version)
        ensure_dir(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        return path

    def delete_role_version(self, group: str, role_name: str, version: str) -> None:
        path = self.resolve_path(group, role_name, version)
        if os.path.exists(path):
            os.remove(path)
        role_dir = os.path.dirname(path)
        if os.path.isdir(role_dir) and not os.listdir(role_dir):
            os.rmdir(role_dir)

    def list_versions(self, group: str, role_name: str) -> list:
        role_dir = os.path.join(self.base_dir, group, role_name)
        if not os.path.isdir(role_dir):
            return []
        versions = []
        for fname in os.listdir(role_dir):
            if fname.startswith("v") and fname.endswith(".yaml"):
                ver = fname[1:-5]
                versions.append(ver)
        return sorted(versions, key=lambda v: parse_version(v))

    def resolve_path(self, group: str, role_name: str, version: str) -> str:
        return build_role_path(self.base_dir, group, role_name, version)

    def compute_checksum(self, file_path: str) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return f"sha256:{h.hexdigest()}"
