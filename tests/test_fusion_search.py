"""Fusion search tests — axis classification, scoring, triad selection."""

import json
import os

import pytest

from rolecore.core.fusion_search import (
    FusionSearchEngine,
    JOB_GROUPS,
    TECH_GROUPS,
    SPECIALTY_GROUPS,
    axis_of,
    tokenize_query,
)


class _InMemoryRegistryStore:
    """Test double — satisfies FusionSearchEngine's dependency with a static dict."""

    def __init__(self, entries):
        self._entries = list(entries)

    def list_all_entries(self):
        return list(self._entries)


def _entry(role_id, group, name_cn, name_en, tags, status="official", domain=""):
    return {
        "role_id": role_id,
        "name_cn": name_cn,
        "name_en": name_en,
        "group": group,
        "domain": domain,
        "tags": tags,
        "latest_version": "1",
        "versions": {"1": {
            "version": "1",
            "file_path": f"/fake/{role_id}.yaml",
            "created_at": "2026-01-01T00:00:00Z",
            "description": "",
            "checksum": "sha256:deadbeef",
        }},
        "meta": {
            "author": "test",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "status": status,
        },
    }


def test_axis_classification_complete():
    """Every registered group must classify into exactly one axis."""
    assert JOB_GROUPS.isdisjoint(TECH_GROUPS)
    assert JOB_GROUPS.isdisjoint(SPECIALTY_GROUPS)
    assert TECH_GROUPS.isdisjoint(SPECIALTY_GROUPS)


def test_axis_of_known_groups():
    assert axis_of("engineering") == "job"
    assert axis_of("language") == "tech"
    assert axis_of("language_specialist") == "specialty"


def test_axis_of_unknown_group_is_none():
    assert axis_of("totally_fictional_group") is None


def test_tokenize_lowercase_and_split():
    assert tokenize_query("  Python  后端  ") == ["python", "后端"]
    assert tokenize_query("") == []


def test_fusion_triad_for_python_backend_senior():
    store = _InMemoryRegistryStore([
        _entry("engineering.backend_architect", "engineering",
               "后端架构师", "Backend Architect",
               ["engineering", "backend", "architect"]),
        _entry("language.python", "language",
               "Python 专家", "Python Expert",
               ["language", "python"]),
        _entry("language_specialist.python_pro", "language_specialist",
               "Python 高级开发", "Python Pro",
               ["language_specialist", "python_pro"]),
        _entry("specialized.unrelated", "specialized",
               "无关角色", "Unrelated",
               ["specialized"]),
    ])
    fse = FusionSearchEngine(store)
    result = fse.find("Python 后端 高级开发")

    assert result["triad"]["job"].entry.role_id == "engineering.backend_architect"
    assert result["triad"]["tech"].entry.role_id == "language.python"
    assert result["triad"]["specialty"].entry.role_id == "language_specialist.python_pro"


def test_fusion_prefers_shorter_canonical_on_tie():
    """When scores tie, the shorter role_id tail wins (more canonical)."""
    store = _InMemoryRegistryStore([
        _entry("language_specialist.python_pro", "language_specialist",
               "Python 高级开发", "Python Pro",
               ["language_specialist", "python_pro"]),
        _entry("core_dev.temporal_python_pro", "core_dev",
               "Temporal (Python) 高级开发", "Temporal Python Pro",
               ["core_dev", "temporal_python_pro"]),
    ])
    fse = FusionSearchEngine(store)
    result = fse.find("Python 高级开发")
    # Both hit on name_cn+name_en+tags+role_id_tail, but python_pro is shorter.
    top_specialty = result["specialty"][0]
    assert top_specialty.entry.role_id == "language_specialist.python_pro"


def test_fusion_status_filter_respected():
    store = _InMemoryRegistryStore([
        _entry("language.python", "language",
               "Python 专家", "Python Expert",
               ["language", "python"], status="raw_imported"),
    ])
    fse = FusionSearchEngine(store)
    # Default filter = official, so a raw_imported entry is hidden.
    result = fse.find("Python")
    assert result["tech"] == []
    # Filter disabled => shows up.
    result = fse.find("Python", status_filter="")
    assert len(result["tech"]) == 1


def test_fusion_empty_query_returns_empty():
    store = _InMemoryRegistryStore([])
    fse = FusionSearchEngine(store)
    result = fse.find("   ")
    assert result["tokens"] == []
    assert result["job"] == result["tech"] == result["specialty"] == []


def test_fusion_verdict_filter_respected():
    store = _InMemoryRegistryStore([
        dict(_entry("language.python_a", "language", "Python A", "Python A",
                    ["language", "python"]),
             **{}) | {"meta": {
                 **_entry("language.python_a", "language", "Python A", "Python A",
                          ["language", "python"])["meta"],
                 "review": {"verdict": "approved", "score": 5, "reviewed_at": ""},
             }},
        dict(_entry("language.python_b", "language", "Python B", "Python B",
                    ["language", "python"]),
             **{}) | {"meta": {
                 **_entry("language.python_b", "language", "Python B", "Python B",
                          ["language", "python"])["meta"],
                 "review": {"verdict": "needs_work", "score": 2, "reviewed_at": ""},
             }},
    ])
    fse = FusionSearchEngine(store)
    result = fse.find("Python", verdict_filter="approved")
    ids = [h.entry.role_id for h in result["tech"]]
    assert ids == ["language.python_a"]
    # No filter => both show up.
    result = fse.find("Python")
    assert len(result["tech"]) == 2


def test_fusion_hit_to_dict_serializable():
    store = _InMemoryRegistryStore([
        _entry("language.python", "language",
               "Python 专家", "Python Expert",
               ["language", "python"]),
    ])
    result = FusionSearchEngine(store).find("Python")
    hit = result["tech"][0]
    payload = hit.to_dict()
    # to_dict() must be JSON-serializable.
    json.dumps(payload, ensure_ascii=False)
    assert payload["axis"] == "tech"
    assert payload["role_id"] == "language.python"
