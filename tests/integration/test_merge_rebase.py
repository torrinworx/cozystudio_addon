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


def _managed_stash_entries(git_inst):
    return git_inst._managed_carryover_entries()


def _conflict_item_for_uuid(conflicts, uuid):
    for item in conflicts or []:
        if item.get("uuid") == uuid:
            return item
    return None


def _matrix_x(git_inst, uuid):
    data = git_inst._read(uuid)
    matrix = data.get("transforms", {}).get("matrix_basis", [])
    assert matrix
    return matrix[0][3]


def _create_manual_merge_conflict(git_inst, base_branch, branch_name, object_name):
    obj = create_test_object(name=object_name)
    obj.location.x = 0.0
    ensure_tracking_assignments(git_inst)
    uuid = wait_for_uuid(obj)
    assert uuid
    git_inst._check()
    assert wait_for_block_file(git_inst, uuid)

    _stage_group(git_inst, uuid)
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message=f"{object_name} base")
    assert "FINISHED" in result

    git_inst.repo.git.checkout("-b", branch_name)
    obj.location.x = 1.0
    git_inst._check()
    _stage_group(git_inst, uuid)
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message=f"{object_name} theirs")
    assert "FINISHED" in result

    git_inst.repo.git.checkout(base_branch)
    git_inst.restore_ref(base_branch, park_changes=False)
    obj.location.x = 2.0
    git_inst._check()
    _stage_group(git_inst, uuid)
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message=f"{object_name} ours")
    assert "FINISHED" in result

    git_inst.refresh_all()
    merge_result = git_inst.merge(branch_name, strategy="manual")
    assert not merge_result.get("ok")
    conflict = _conflict_item_for_uuid(merge_result.get("conflicts"), uuid)
    assert conflict
    return obj, uuid, conflict


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
    git_inst.restore_ref(base_branch, park_changes=False)

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

    _obj, uuid, conflict = _create_manual_merge_conflict(
        git_inst,
        base_branch,
        "feature_conflict",
        "CozyConflictObject",
    )

    assert conflict.get("reason") == "Tier A merge conflict."
    assert conflict.get("operation") == "merge"
    assert conflict.get("ours_ref") == git_inst.repo.head.commit.hexsha
    assert conflict.get("theirs_ref")
    assert conflict.get("ours_entry")
    assert conflict.get("theirs_entry")

    manifest_conflicts = (git_inst.manifest or {}).get("conflicts", [])
    manifest_conflict = _conflict_item_for_uuid(manifest_conflicts, uuid)
    assert manifest_conflict
    assert manifest_conflict.get("label") == "CozyConflictObject"

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
    git_inst.restore_ref(base_branch, park_changes=False)
    git_inst.repo.git.checkout("feature_rebase")

    rebase_result = git_inst.rebase(base_branch, strategy="manual")
    assert rebase_result.get("ok")
    assert not rebase_result.get("conflicts")

    data = git_inst._read(uuid)
    matrix = data.get("transforms", {}).get("matrix_basis", [])
    assert matrix and abs(matrix[0][3] - 3.0) < 1e-4

    git_inst.repo.git.branch("-D", "feature_rebase")


@pytest.mark.order(23)
def test_conflict_operator_checkout_theirs():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)
    clear_manifest_conflicts(git_inst)

    base_branch = get_repo_branch_name(git_inst.repo)
    assert base_branch

    _obj, uuid, _conflict = _create_manual_merge_conflict(
        git_inst,
        base_branch,
        "feature_operator_theirs",
        "CozyOperatorTheirsObject",
    )

    result = bpy.ops.cozystudio.resolve_conflict_version(
        "EXEC_DEFAULT",
        conflict_uuid=uuid,
        resolution="theirs",
    )
    assert "FINISHED" in result
    assert abs(_matrix_x(git_inst, uuid) - 1.0) < 1e-4
    assert not _conflict_item_for_uuid((git_inst.manifest or {}).get("conflicts", []), uuid)

    git_inst.repo.git.branch("-D", "feature_operator_theirs")


@pytest.mark.order(24)
def test_conflict_operator_checkout_mine():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)
    clear_manifest_conflicts(git_inst)

    base_branch = get_repo_branch_name(git_inst.repo)
    assert base_branch

    _obj, uuid, _conflict = _create_manual_merge_conflict(
        git_inst,
        base_branch,
        "feature_operator_ours",
        "CozyOperatorOursObject",
    )

    result = bpy.ops.cozystudio.resolve_conflict_version(
        "EXEC_DEFAULT",
        conflict_uuid=uuid,
        resolution="ours",
    )
    assert "FINISHED" in result
    assert abs(_matrix_x(git_inst, uuid) - 2.0) < 1e-4
    assert not _conflict_item_for_uuid((git_inst.manifest or {}).get("conflicts", []), uuid)

    git_inst.repo.git.branch("-D", "feature_operator_ours")


@pytest.mark.order(25)
def test_conflict_operator_marks_manual_resolution():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)
    clear_manifest_conflicts(git_inst)

    base_branch = get_repo_branch_name(git_inst.repo)
    assert base_branch

    _obj, uuid, _conflict = _create_manual_merge_conflict(
        git_inst,
        base_branch,
        "feature_operator_manual",
        "CozyOperatorManualObject",
    )

    result = bpy.ops.cozystudio.resolve_conflict(
        "EXEC_DEFAULT",
        conflict_uuid=uuid,
    )
    assert "FINISHED" in result
    assert abs(_matrix_x(git_inst, uuid) - 2.0) < 1e-4
    assert not _conflict_item_for_uuid((git_inst.manifest or {}).get("conflicts", []), uuid)

    git_inst.repo.git.branch("-D", "feature_operator_manual")


@pytest.mark.order(26)
def test_merge_parks_cozy_changes_until_restored():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)
    clear_manifest_conflicts(git_inst)

    base_branch = get_repo_branch_name(git_inst.repo)
    assert base_branch

    obj = create_test_object(name="CozyCarryoverMergeObject")
    obj.location.x = 0.0
    ensure_tracking_assignments(git_inst)
    uuid = wait_for_uuid(obj)
    assert uuid
    git_inst._check()
    assert wait_for_block_file(git_inst, uuid)

    _stage_group(git_inst, uuid)
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Carryover merge base")
    assert "FINISHED" in result

    git_inst.repo.git.checkout("-b", "feature_carryover_merge")
    obj.location.x = 1.0
    git_inst._check()
    _stage_group(git_inst, uuid)
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Feature committed change")
    assert "FINISHED" in result

    git_inst.repo.git.checkout(base_branch)
    git_inst.restore_ref(base_branch, park_changes=False)
    obj.location.x = 2.0
    git_inst._check()
    _stage_group(git_inst, uuid)
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Base committed change")
    assert "FINISHED" in result

    obj.location.x = 3.0
    git_inst._check()

    merge_result = git_inst.merge("feature_carryover_merge", strategy="manual")
    assert not merge_result.get("ok")
    assert _conflict_item_for_uuid(merge_result.get("conflicts"), uuid)
    assert _managed_stash_entries(git_inst)

    git_inst.refresh_ui_state()
    ui_state = git_inst.ui_state
    assert ui_state["carryover"]["has_parked"]

    try:
        blocked = bpy.ops.cozystudio.checkout_branch("EXEC_DEFAULT", branch_name=base_branch)
        assert "CANCELLED" in blocked
    except RuntimeError as exc:
        assert "Parked Cozy changes" in str(exc)

    clear_manifest_conflicts(git_inst)
    git_inst.last_integrity_report = git_inst.validate_manifest_integrity()
    git_inst.refresh_ui_state()

    result = bpy.ops.cozystudio.reapply_parked_changes("EXEC_DEFAULT")
    assert "FINISHED" in result
    assert not _managed_stash_entries(git_inst)

    data = git_inst._read(uuid)
    matrix = data.get("transforms", {}).get("matrix_basis", [])
    assert matrix and abs(matrix[0][3] - 3.0) < 1e-4

    git_inst.repo.git.restore(
        "--source=HEAD",
        "--staged",
        "--worktree",
        "--",
        ".cozystudio/manifest.json",
        ".cozystudio/blocks",
    )
    git_inst.restore_ref()
    git_inst.repo.git.branch("-D", "feature_carryover_merge")
