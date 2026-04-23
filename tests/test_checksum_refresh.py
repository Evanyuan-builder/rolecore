"""Checksum refresh path — ensure direct-YAML writes that bypass update_role
can resync cleanly via _refresh_version_checksum and resync_entry_from_yaml.

Phase 2.5 invariant: any path that writes YAML directly must re-compute the
registry checksum, or the Registry drifts.
"""

import os
from copy import deepcopy

import pytest
import yaml

from rolecore.storage.role_store import RoleStore
from rolecore.storage.registry_store import RegistryStore
from rolecore.core.role_manager import RoleManager


@pytest.fixture
def temp_engine(tmp_path, valid_role_data):
    roles_dir = tmp_path / "roles"
    registry_path = tmp_path / "registry" / "registry.json"
    role_store = RoleStore(str(roles_dir))
    registry_store = RegistryStore(str(registry_path))
    rm = RoleManager(role_store, registry_store)

    data = deepcopy(valid_role_data)
    data["meta"]["status"] = "raw_imported"
    rm.create_role(data)
    return rm, registry_store, roles_dir, "engineering.test_role"


def test_direct_yaml_write_then_resync_updates_checksum(temp_engine):
    rm, rs, roles_dir, role_id = temp_engine
    entry_before = rs.get_entry(role_id)
    checksum_before = entry_before["versions"]["1"]["checksum"]

    yaml_path = entry_before["versions"]["1"]["file_path"]
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Simulate a direct YAML rewrite (Phase 2.5 bypass scenario).
    data["identity"]["name_cn"] = "改过的名字"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    # Registry is now drifted: YAML changed but registry's checksum is stale.
    entry_midway = rs.get_entry(role_id)
    assert entry_midway["versions"]["1"]["checksum"] == checksum_before
    assert entry_midway["name_cn"] != "改过的名字"

    # Resync should restore parity.
    changes = rm.resync_entry_from_yaml(role_id)
    assert "name_cn" in changes

    entry_after = rs.get_entry(role_id)
    assert entry_after["name_cn"] == "改过的名字"
    assert entry_after["versions"]["1"]["checksum"] != checksum_before


def test_resync_is_noop_when_in_sync(temp_engine):
    rm, rs, _, role_id = temp_engine
    # First resync applies any trivial normalizations...
    rm.resync_entry_from_yaml(role_id)
    # ...and a second call must report no field changes.
    changes = rm.resync_entry_from_yaml(role_id)
    assert changes == {}


def test_promote_refreshes_checksum(temp_engine):
    """promote_status writes status back into the YAML and must refresh checksum."""
    rm, rs, _, role_id = temp_engine
    before = rs.get_entry(role_id)["versions"]["1"]["checksum"]

    rm.promote_status(role_id, "normalized")

    after = rs.get_entry(role_id)["versions"]["1"]["checksum"]
    assert after != before
    assert rs.get_entry(role_id)["meta"]["status"] == "normalized"
