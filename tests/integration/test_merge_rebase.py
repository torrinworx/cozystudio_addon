import importlib

import bpy
import pytest

from ..helpers import (
    clear_manifest_conflicts,
    create_test_object,
    ensure_tracking_assignments,
    get_repo_branch_name,
    init_git_repo_for_test,
    wait_for_block_file,
    wait_for_uuid,
)

ADDON_MODULE = "cozystudio_addon"


def _stage_group(git_inst, uuid):
    group_id = (
        git_inst.state.get("entries", {}).get(uuid, {}).get("group_id") or uuid
    )
    result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=group_id)
    assert "FINISHED" in result, f"add_group returned {result}"


@pytest.mark.order(20)
def test_merge_no_conflict_applies_theirs():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)
    clear_manifest_conflicts(git_inst)

    base_branch = get_repo_branch_name(git_inst.repo)
    assert base_branch

    obj = create_test_object(name="CozyMergeObject")
    obj.location.x = 0.0
    ensure_tracking_assignments(git_inst)
    uuid = wait_for_uuid(obj)
    assert uuid
    git_inst._check()
    assert wait_for_block_file(git_inst, uuid)

    _stage_group(git_inst, uuid)
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Base")
    assert "FINISHED" in result
    base_commit = git_inst.repo.head.commit.hexsha

    git_inst.repo.git.checkout("-b", "feature")
    obj.location.x = 1.0
    git_inst._check()
    _stage_group(git_inst, uuid)
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Feature change")
    assert "FINISHED" in result

    git_inst.repo.git.checkout(base_branch)
    git_inst.checkout(base_commit)
    git_inst.refresh_all()

    merge_result = git_inst.merge("feature", strategy="manual")
    assert merge_result.get("ok")
    assert not merge_result.get("conflicts")

    data = git_inst._read(uuid)
    matrix = data.get("transforms", {}).get("matrix_basis", [])
    assert matrix and abs(matrix[0][3] - 1.0) < 1e-4

    git_inst.repo.git.branch("-D", "feature")


@pytest.mark.order(21)
def test_merge_conflict_marks_manifest():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)
    clear_manifest_conflicts(git_inst)

    base_branch = get_repo_branch_name(git_inst.repo)
    assert base_branch

    obj = create_test_object(name="CozyConflictObject")
    obj.location.x = 0.0
    ensure_tracking_assignments(git_inst)
    uuid = wait_for_uuid(obj)
    assert uuid
    git_inst._check()
    assert wait_for_block_file(git_inst, uuid)

    _stage_group(git_inst, uuid)
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Base conflict")
    assert "FINISHED" in result
    base_commit = git_inst.repo.head.commit.hexsha

    git_inst.repo.git.checkout("-b", "feature_conflict")
    obj.location.x = 1.0
    git_inst._check()
    _stage_group(git_inst, uuid)
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Feature change")
    assert "FINISHED" in result

    git_inst.repo.git.checkout(base_branch)
    git_inst.checkout(base_commit)
    git_inst.refresh_all()
    obj.location.x = 2.0
    git_inst._check()
    _stage_group(git_inst, uuid)
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Base change")
    assert "FINISHED" in result

    git_inst.refresh_all()
    merge_result = git_inst.merge("feature_conflict", strategy="manual")
    assert not merge_result.get("ok")
    assert uuid in merge_result.get("conflicts", {})

    manifest_conflicts = (git_inst.manifest or {}).get("conflicts", {})
    assert uuid in manifest_conflicts

    git_inst.repo.git.branch("-D", "feature_conflict")


@pytest.mark.order(22)
def test_rebase_replays_commits():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)
    clear_manifest_conflicts(git_inst)

    base_branch = get_repo_branch_name(git_inst.repo)
    assert base_branch

    obj = create_test_object(name="CozyRebaseObject")
    obj.location.x = 0.0
    ensure_tracking_assignments(git_inst)
    uuid = wait_for_uuid(obj)
    assert uuid
    git_inst._check()
    assert wait_for_block_file(git_inst, uuid)

    _stage_group(git_inst, uuid)
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Base rebase")
    assert "FINISHED" in result
    base_commit = git_inst.repo.head.commit.hexsha

    git_inst.repo.git.checkout("-b", "feature_rebase")
    obj.location.x = 1.0
    git_inst._check()
    _stage_group(git_inst, uuid)
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Step 1")
    assert "FINISHED" in result

    obj.location.x = 3.0
    git_inst._check()
    _stage_group(git_inst, uuid)
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Step 2")
    assert "FINISHED" in result

    git_inst.repo.git.checkout(base_branch)
    git_inst.checkout(base_commit)
    git_inst.refresh_all()
    git_inst.repo.git.checkout("feature_rebase")

    rebase_result = git_inst.rebase(base_branch, strategy="manual")
    assert rebase_result.get("ok")
    assert not rebase_result.get("conflicts")

    data = git_inst._read(uuid)
    matrix = data.get("transforms", {}).get("matrix_basis", [])
    assert matrix and abs(matrix[0][3] - 3.0) < 1e-4

    git_inst.repo.git.branch("-D", "feature_rebase")


@pytest.mark.order(23)
def test_product_language_sync_and_conflict_operators():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)
    clear_manifest_conflicts(git_inst)

    base_branch = get_repo_branch_name(git_inst.repo)
    assert base_branch

    obj = create_test_object(name="CozyOperatorMergeObject")
    obj.location.x = 0.0
    ensure_tracking_assignments(git_inst)
    uuid = wait_for_uuid(obj)
    assert uuid
    git_inst._check()
    assert wait_for_block_file(git_inst, uuid)

    _stage_group(git_inst, uuid)
    result = bpy.ops.cozystudio.create_snapshot("EXEC_DEFAULT", message="Base state")
    assert "FINISHED" in result
    base_commit = git_inst.repo.head.commit.hexsha

    git_inst.repo.git.checkout("-b", "feature_operator_merge")
    obj.location.x = 2.0
    git_inst._check()
    _stage_group(git_inst, uuid)
    result = bpy.ops.cozystudio.create_snapshot("EXEC_DEFAULT", message="Feature state")
    assert "FINISHED" in result

    git_inst.repo.git.checkout(base_branch)
    git_inst.checkout(base_commit)
    git_inst.refresh_all()

    result = bpy.ops.cozystudio.bring_in_changes(
        "EXEC_DEFAULT", ref_name="feature_operator_merge", strategy="manual"
    )
    assert "FINISHED" in result
    data = git_inst._read(uuid)
    matrix = data.get("transforms", {}).get("matrix_basis", [])
    assert matrix and abs(matrix[0][3] - 2.0) < 1e-4

    git_inst.manifest["conflicts"] = {uuid: "Synthetic operator conflict"}
    git_inst.manifest.write()
    result = bpy.ops.cozystudio.resolve_conflict(
        "EXEC_DEFAULT", conflict_uuid=uuid
    )
    assert "FINISHED" in result
    assert not (git_inst.manifest or {}).get("conflicts")

    git_inst.repo.git.branch("-D", "feature_operator_merge")
