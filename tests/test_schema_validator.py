"""Schema validator happy-path and failure-mode tests."""

from copy import deepcopy

import pytest

from rolecore.utils.schema_validator import SchemaValidator, SchemaValidationError


def test_valid_role_passes(valid_role_data):
    assert SchemaValidator().validate(valid_role_data) == []


def test_missing_top_level_key_flagged(valid_role_data):
    data = deepcopy(valid_role_data)
    del data["mission"]
    errors = SchemaValidator().validate(data)
    assert any("mission" in e for e in errors), errors


def test_missing_section_field_flagged(valid_role_data):
    data = deepcopy(valid_role_data)
    del data["identity"]["positioning"]
    errors = SchemaValidator().validate(data)
    assert any("identity.positioning" in e for e in errors), errors


def test_invalid_status_flagged(valid_role_data):
    data = deepcopy(valid_role_data)
    data["meta"]["status"] = "not_a_real_status"
    errors = SchemaValidator().validate(data)
    assert any("meta.status" in e for e in errors), errors


def test_list_field_not_list_flagged(valid_role_data):
    data = deepcopy(valid_role_data)
    data["mission"]["core_accountability"] = "not a list"
    errors = SchemaValidator().validate(data)
    assert any("core_accountability" in e and "list" in e for e in errors), errors


def test_validate_or_raise_on_bad_data(valid_role_data):
    data = deepcopy(valid_role_data)
    del data["evaluation"]
    with pytest.raises(SchemaValidationError):
        SchemaValidator().validate_or_raise(data)


def test_validate_or_raise_on_good_data(valid_role_data):
    SchemaValidator().validate_or_raise(valid_role_data)
