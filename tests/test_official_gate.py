"""Official gate tests — ensure human-confirmation hard gate (name_cn) holds."""

from copy import deepcopy

from rolecore.utils.schema_validator import OfficialGateValidator


def test_valid_role_passes_gate(valid_role_data):
    assert OfficialGateValidator().check(valid_role_data) == []


def test_empty_name_cn_blocks_gate(valid_role_data):
    """The hard human-confirmation gate: name_cn must be non-empty."""
    data = deepcopy(valid_role_data)
    data["identity"]["name_cn"] = ""
    gaps = OfficialGateValidator().check(data)
    assert any("name_cn" in g for g in gaps), gaps


def test_whitespace_only_name_cn_blocks_gate(valid_role_data):
    data = deepcopy(valid_role_data)
    data["identity"]["name_cn"] = "   "
    gaps = OfficialGateValidator().check(data)
    assert any("name_cn" in g for g in gaps), gaps


def test_short_positioning_blocks_gate(valid_role_data):
    data = deepcopy(valid_role_data)
    data["identity"]["positioning"] = "Too short."
    gaps = OfficialGateValidator().check(data)
    assert any("positioning" in g for g in gaps), gaps


def test_short_mission_summary_blocks_gate(valid_role_data):
    data = deepcopy(valid_role_data)
    data["mission"]["summary"] = "Short."
    gaps = OfficialGateValidator().check(data)
    assert any("mission.summary" in g for g in gaps), gaps


def test_insufficient_core_accountability_blocks_gate(valid_role_data):
    data = deepcopy(valid_role_data)
    data["mission"]["core_accountability"] = data["mission"]["core_accountability"][:2]
    gaps = OfficialGateValidator().check(data)
    assert any("core_accountability" in g for g in gaps), gaps


def test_missing_workflow_blocks_gate(valid_role_data):
    data = deepcopy(valid_role_data)
    data["workflows"] = []
    gaps = OfficialGateValidator().check(data)
    assert any("workflow" in g for g in gaps), gaps


def test_placeholder_communication_style_blocks_gate(valid_role_data):
    data = deepcopy(valid_role_data)
    data["behavior"]["communication_style"] = "Execute tasks within defined role scope"
    gaps = OfficialGateValidator().check(data)
    assert any("communication_style" in g for g in gaps), gaps
