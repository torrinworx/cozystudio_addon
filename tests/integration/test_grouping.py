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


@pytest.mark.order(13)
def test_ui_semantic_diffs_keep_backend_grouping_and_metadata():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)

    obj_a = create_test_object(name="CozySemanticA")
    obj_b = create_test_object(name="CozySemanticB")
    shared_mat = bpy.data.materials.new("CozySemanticSharedMat")
    shared_mat.use_nodes = True

    obj_a.data.materials.append(shared_mat)
    obj_b.data.materials.append(shared_mat)

    ensure_tracking_assignments(git_inst)

    obj_a_uuid = wait_for_uuid(obj_a)
    obj_b_uuid = wait_for_uuid(obj_b)
    mat_uuid = wait_for_uuid(shared_mat)

    assert obj_a_uuid
    assert obj_b_uuid
    assert mat_uuid

    git_inst._check()
    result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=mat_uuid)
    assert "FINISHED" in result, f"add_group returned {result}"
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Base semantic grouping")
    assert "FINISHED" in result, f"commit returned {result}"

    shared_mat.diffuse_color = (0.2, 0.3, 0.4, 1.0)
    git_inst._check()
    git_inst.refresh_ui_state()

    unstaged_groups = git_inst.ui_state["changes"]["unstaged_groups"]
    material_group = next(
        group
        for group in unstaged_groups
        if group["group_id"] == mat_uuid
    )
    material_diff = next(
        diff for diff in material_group["diffs"] if diff.get("uuid") == mat_uuid
    )

    assert material_group["label"].startswith("Shared: ")
    assert material_diff["group_id"] == mat_uuid
    assert material_diff["datablock_type"] == "materials"
    assert material_diff["display_name"].startswith("CozySemanticSharedMat")
    assert material_diff["summary"] in {"Updated diffuse color", "Updated 1 sections"}
