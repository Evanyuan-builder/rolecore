import os
import re


def build_role_path(base_dir: str, group: str, role_name: str, version: str) -> str:
    return os.path.join(base_dir, group, role_name, f"v{version}.yaml")


def role_id_to_parts(role_id: str) -> tuple:
    """'engineering.backend_engineer' → ('engineering', 'backend_engineer')"""
    parts = role_id.split(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid role_id format '{role_id}'. Expected 'group.role_name'")
    return parts[0], parts[1]


def parts_to_role_id(group: str, role_name: str) -> str:
    return f"{group}.{role_name}"


def normalize_name(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[\s\-]+", "_", name)
    name = re.sub(r"[^\w]", "", name)
    return name


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)
