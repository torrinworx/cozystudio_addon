import importlib
import json

import bpy
import pytest

from ..helpers import (
    create_test_object,
    ensure_tracking_assignments,
    init_git_repo_for_test,
    wait_for_block_file,
    wait_for_uuid,
)

ADDON_MODULE = "cozystudio_addon"


def _find_object_by_uuid(uuid):
    for obj in bpy.data.objects:
        if getattr(obj, "cozystudio_uuid", None) == uuid:
            return obj
    return None


@pytest.mark.order(5)
def test_git_flow_stage_commit_checkout():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)

    test_obj = create_test_object(name="CozyFlowObject")
    test_obj.location.x = 1.0

    ensure_tracking_assignments(git_inst)

    uuid = wait_for_uuid(test_obj)
    assert uuid, "Object UUID was not assigned"
    mesh_uuid = wait_for_uuid(test_obj.data)
    assert mesh_uuid, "Mesh UUID was not assigned"

    git_inst._check()
    block_path = wait_for_block_file(git_inst, uuid)
    assert block_path is not None, "Block file was not created"

    rel_path = f".blocks/{uuid}.json"
    mesh_path = f".blocks/{mesh_uuid}.json"
    result = bpy.ops.cozystudio.add_file(file_path=rel_path)
    assert "FINISHED" in result, f"add_file returned {result}"
    result = bpy.ops.cozystudio.add_file(file_path=mesh_path)
    assert "FINISHED" in result, f"add_file returned {result}"

    git_inst._update_diffs()
    staged_paths = [d["path"] for d in (git_inst.diffs or []) if d["status"].startswith("staged")]
    assert rel_path in staged_paths

    result = bpy.ops.cozystudio.unstage_file(file_path=rel_path)
    assert "FINISHED" in result, f"unstage_file returned {result}"

    git_inst._update_diffs()
    staged_paths = [d["path"] for d in (git_inst.diffs or []) if d["status"].startswith("staged")]
    assert rel_path not in staged_paths

    result = bpy.ops.cozystudio.add_file(file_path=rel_path)
    assert "FINISHED" in result, f"add_file returned {result}"
    result = bpy.ops.cozystudio.add_file(file_path=mesh_path)
    assert "FINISHED" in result, f"add_file returned {result}"

    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Commit 1")
    assert "FINISHED" in result, f"commit returned {result}"
    commit1 = git_inst.repo.head.commit.hexsha

    test_obj.location.x = 2.0
    git_inst._check()
    result = bpy.ops.cozystudio.add_file(file_path=rel_path)
    assert "FINISHED" in result, f"add_file returned {result}"

    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Commit 2")
    assert "FINISHED" in result, f"commit returned {result}"

    result = bpy.ops.cozystudio.checkout_commit("EXEC_DEFAULT", commit_hash=commit1)
    assert "FINISHED" in result, f"checkout_commit returned {result}"

    block_data_raw = git_inst.repo.git.show(f"{commit1}:{rel_path}")
    restored_data = json.loads(block_data_raw)
    assert restored_data.get("type_id") == "Object"
    assert restored_data.get("name", "").startswith("CozyFlowObject")

    matrix = restored_data.get("transforms", {}).get("matrix_basis", [])
    assert matrix and abs(matrix[0][3] - 1.0) < 1e-4


@pytest.mark.order(6)
def test_deserialize_reuses_existing_object():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)

    test_obj = create_test_object(name="CozyCheckoutObject")
    test_obj.location.x = 1.0

    ensure_tracking_assignments(git_inst)

    uuid = wait_for_uuid(test_obj)
    assert uuid, "Object UUID was not assigned"

    git_inst._check()
    block_path = wait_for_block_file(git_inst, uuid)
    assert block_path is not None, "Block file was not created"

    data = git_inst._read(uuid)
    if data.get("uuid") is None:
        data["uuid"] = uuid

    matches = [
        obj
        for obj in bpy.data.objects
        if getattr(obj, "cozystudio_uuid", None) == uuid
        or getattr(obj, "uuid", None) == uuid
    ]
    assert matches, "No object found before deserialize"
    assert len(matches) == 1

    git_inst.deserialize(data)
    matches = [
        obj
        for obj in bpy.data.objects
        if getattr(obj, "cozystudio_uuid", None) == uuid
        or getattr(obj, "uuid", None) == uuid
    ]
    assert len(matches) == 1, "Duplicate objects were created during deserialize"
