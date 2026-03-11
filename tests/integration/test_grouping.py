import importlib

import bpy
import pytest

from ..helpers import (
    create_test_object,
    ensure_tracking_assignments,
    init_git_repo_for_test,
    wait_for_uuid,
)

ADDON_MODULE = "cozystudio_addon"


@pytest.mark.order(6)
def test_object_rooted_grouping_shared_material():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)

    obj_a = create_test_object(name="CozyGroupA")
    obj_b = create_test_object(name="CozyGroupB")
    shared_mat = bpy.data.materials.new("CozySharedMat")
    shared_mat.use_nodes = True

    obj_a.data.materials.append(shared_mat)
    obj_b.data.materials.append(shared_mat)

    ensure_tracking_assignments(git_inst)

    uuid_a = wait_for_uuid(obj_a)
    uuid_b = wait_for_uuid(obj_b)
    mesh_a_uuid = wait_for_uuid(obj_a.data)
    mesh_b_uuid = wait_for_uuid(obj_b.data)
    mat_uuid = wait_for_uuid(shared_mat)

    assert uuid_a, "Object A UUID was not assigned"
    assert uuid_b, "Object B UUID was not assigned"
    assert mesh_a_uuid, "Mesh A UUID was not assigned"
    assert mesh_b_uuid, "Mesh B UUID was not assigned"
    assert mat_uuid, "Material UUID was not assigned"

    git_inst._check()
    entries = git_inst.state.get("entries", {})
    groups = git_inst.state.get("groups", {})

    assert entries[uuid_a]["group_id"] == uuid_a
    assert entries[mesh_a_uuid]["group_id"] == uuid_a
    assert entries[uuid_b]["group_id"] == uuid_b
    assert entries[mesh_b_uuid]["group_id"] == uuid_b
    assert entries[mat_uuid]["group_id"] == mat_uuid

    assert groups[uuid_a]["type"] == "object"
    assert uuid_a in groups[uuid_a]["members"]
    assert mesh_a_uuid in groups[uuid_a]["members"]
    assert groups[mat_uuid]["type"] == "shared"
