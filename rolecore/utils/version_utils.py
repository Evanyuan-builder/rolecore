def parse_version(version_str: str) -> int:
    try:
        return int(str(version_str))
    except (ValueError, TypeError):
        return -1


def sort_versions(versions: list) -> list:
    return sorted(versions, key=lambda v: parse_version(v))


def next_version(current_latest: str) -> str:
    n = parse_version(current_latest)
    if n < 0:
        return "1"
    return str(n + 1)


def is_valid_version(version_str: str) -> bool:
    try:
        return int(str(version_str)) > 0
    except (ValueError, TypeError):
        return False


def resolve_version(version_str: str, available: list, latest: str) -> str:
    if version_str == "latest":
        if not latest:
            raise ValueError("No latest version defined for this role")
        return latest
    if str(version_str) not in [str(v) for v in available]:
        raise ValueError(
            f"Version '{version_str}' not found. Available: {available}"
        )
    return str(version_str)
