"""Reviewer + curated-gate tests."""

from copy import deepcopy

import pytest

from rolecore.core.reviewer import (
    REVIEW_SYSTEM_PROMPT,
    Reviewer,
    ReviewRecord,
    ReviewParseError,
    parse_review_response,
    build_user_prompt,
    get_review_record,
)
from rolecore.storage.role_store import RoleStore
from rolecore.storage.registry_store import RegistryStore
from rolecore.core.role_manager import RoleManager


@pytest.fixture
def temp_rm(tmp_path, valid_role_data):
    """Fresh role_manager with a role at 'normalized' status, ready for curated review."""
    role_store = RoleStore(str(tmp_path / "roles"))
    registry_store = RegistryStore(str(tmp_path / "registry" / "registry.json"))
    rm = RoleManager(role_store, registry_store)

    data = deepcopy(valid_role_data)
    data["meta"]["status"] = "raw_imported"
    rm.create_role(data)
    # Advance to normalized so curated is the next step.
    rm.promote_status(data["meta"]["role_id"], "normalized")
    return rm, data["meta"]["role_id"]


def test_parse_review_response_happy_path():
    text = """Thinking...
    {
      "verdict": "approved",
      "score": 4,
      "strengths": ["Clear positioning"],
      "issues": [],
      "fix_hints": []
    }"""
    r = parse_review_response(text)
    assert r.verdict == "approved"
    assert r.score == 4
    assert r.strengths == ["Clear positioning"]


def test_parse_review_response_invalid_verdict():
    with pytest.raises(ReviewParseError):
        parse_review_response('{"verdict": "meh", "score": 3}')


def test_parse_review_response_out_of_range_score():
    with pytest.raises(ReviewParseError):
        parse_review_response('{"verdict": "approved", "score": 99}')


def test_parse_review_response_no_json():
    with pytest.raises(ReviewParseError):
        parse_review_response("just some prose without any JSON")


def test_build_user_prompt_includes_role_id(valid_role_data):
    prompt = build_user_prompt(valid_role_data)
    assert "engineering.test_role" in prompt
    assert "identity:" in prompt


def test_build_user_prompt_strips_source_noise(valid_role_data):
    data = deepcopy(valid_role_data)
    data["meta"]["source"] = {"secret_upstream_hash": "xyz"}
    prompt = build_user_prompt(data)
    assert "secret_upstream_hash" not in prompt


def test_attach_manual_review_writes_meta_review(temp_rm):
    rm, role_id = temp_rm
    r = Reviewer(rm)
    record = r.attach_manual(role_id, verdict="approved", score=5,
                             strengths=["great"], reviewer_model="human")
    # Reload and check meta.review is persisted.
    role = rm.get_role(role_id, version="latest")
    recovered = get_review_record(role.to_dict())
    assert recovered is not None
    assert recovered.verdict == "approved"
    assert recovered.score == 5
    assert recovered.strengths == ["great"]


def test_promote_to_curated_requires_review(temp_rm):
    rm, role_id = temp_rm
    with pytest.raises(ValueError, match="no review record"):
        rm.promote_status(role_id, "curated")


def test_promote_to_curated_requires_approved_verdict(temp_rm):
    rm, role_id = temp_rm
    Reviewer(rm).attach_manual(role_id, verdict="needs_work", score=3,
                               issues=["vague workflow"])
    with pytest.raises(ValueError, match="needs_work"):
        rm.promote_status(role_id, "curated")


def test_promote_to_curated_passes_with_approval(temp_rm):
    rm, role_id = temp_rm
    Reviewer(rm).attach_manual(role_id, verdict="approved", score=4)
    new_status = rm.promote_status(role_id, "curated")
    assert new_status == "curated"


def test_attach_record_refreshes_checksum(temp_rm):
    rm, role_id = temp_rm
    before = rm.registry_store.get_entry(role_id)["versions"]["1"]["checksum"]
    Reviewer(rm).attach_manual(role_id, verdict="approved", score=5)
    after = rm.registry_store.get_entry(role_id)["versions"]["1"]["checksum"]
    assert before != after


def test_review_system_prompt_is_well_formed():
    assert "STRICT JSON" in REVIEW_SYSTEM_PROMPT
    for verdict in ("approved", "needs_work", "rejected"):
        assert verdict in REVIEW_SYSTEM_PROMPT
