import importlib
import tempfile
from pathlib import Path

import bpy
import pytest

from ..helpers import (
    assert_manifest_integrity_ok,
    assert_no_parked_changes,
    create_fresh_test_blend,
    create_test_object,
    enable_addon,
    ensure_tracking_assignments,
    get_working_paths,
    get_dirty_block_paths,
    get_repo_branch_name,
    init_git_repo_for_test,
    wait_for_block_file,
    wait_for_uuid,
)


ADDON_MODULE = "cozystudio_addon"


def _setup_flow_repo(prefix: str):
    work_dir = Path(tempfile.mkdtemp(prefix=prefix))
    create_fresh_test_blend(work_dir)
    enable_addon(ADDON_MODULE)
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    state_mod = importlib.import_module(f"{ADDON_MODULE}.ui.state")
    state_mod.reset_state()
    return init_git_repo_for_test(ui_mod)


def _find_object_by_uuid(uuid):
    for obj in bpy.data.objects:
        if getattr(obj, "cozystudio_uuid", None) == uuid:
            return obj
    return None


def _group_id_for_uuid(git_inst, uuid):
    return git_inst.state.get("entries", {}).get(uuid, {}).get("group_id") or uuid


def _ensure_base_branch(git_inst):
    base_branch = get_repo_branch_name(git_inst.repo)
    if base_branch:
        return base_branch
    try:
        git_inst.repo.git.checkout("-b", "main")
    except Exception:
        git_inst.repo.git.checkout("main")
    return "main"


def _assert_only_cozy_dirty(git_inst):
    working_paths = get_working_paths(git_inst)
    non_cozy = {
        path
        for path in working_paths
        if not path.startswith(".cozystudio/") and not path.endswith(".blend")
    }
    assert not non_cozy, f"Unexpected non-Cozy dirty paths: {sorted(non_cozy)}"


def _reapply_parked_if_needed(git_inst):
    if git_inst._managed_carryover_entries():
        result = bpy.ops.cozystudio.reapply_parked_changes("EXEC_DEFAULT")
        assert "FINISHED" in result
        assert_no_parked_changes(git_inst)


@pytest.mark.order(100)
@pytest.mark.flow
def test_flow_happy_path_merge():
    git_inst = _setup_flow_repo("cozy_flow_happy_")
    base_branch = _ensure_base_branch(git_inst)

    obj = create_test_object(name="CozyFlowHappyObject")
    obj.location.x = 1.0
    ensure_tracking_assignments(git_inst)

    uuid = wait_for_uuid(obj)
    assert uuid
    git_inst._check()
    assert wait_for_block_file(git_inst, uuid)

    result = bpy.ops.cozystudio.add_group(
        "EXEC_DEFAULT", group_id=_group_id_for_uuid(git_inst, uuid)
    )
    assert "FINISHED" in result
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Flow Happy Base")
    assert "FINISHED" in result

    git_inst.repo.git.checkout("-b", "flow_happy_feature")
    obj.location.x = 4.0
    git_inst._check()
    result = bpy.ops.cozystudio.add_group(
        "EXEC_DEFAULT", group_id=_group_id_for_uuid(git_inst, uuid)
    )
    assert "FINISHED" in result
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Flow Happy Feature")
    assert "FINISHED" in result

    git_inst.repo.git.checkout(base_branch)
    git_inst.restore_ref(base_branch, park_changes=False)
    result = bpy.ops.cozystudio.merge(
        "EXEC_DEFAULT", ref_name="flow_happy_feature", strategy="manual"
    )
    assert "FINISHED" in result

    restored = _find_object_by_uuid(uuid)
    assert restored is not None
    assert abs(restored.location.x - 4.0) < 1e-4

    assert_manifest_integrity_ok(git_inst)
    _assert_only_cozy_dirty(git_inst)
    assert_no_parked_changes(git_inst)

    git_inst.repo.git.branch("-D", "flow_happy_feature")


@pytest.mark.order(110)
@pytest.mark.flow
def test_flow_checkout_with_dirty_changes_reapplies():
    git_inst = _setup_flow_repo("cozy_flow_dirty_")
    base_branch = _ensure_base_branch(git_inst)

    obj = create_test_object(name="CozyFlowDirtyObject")
    obj.location.x = 0.0
    ensure_tracking_assignments(git_inst)
    uuid = wait_for_uuid(obj)
    assert uuid
    git_inst._check()
    assert wait_for_block_file(git_inst, uuid)

    result = bpy.ops.cozystudio.add_group(
        "EXEC_DEFAULT", group_id=_group_id_for_uuid(git_inst, uuid)
    )
    assert "FINISHED" in result
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Flow Dirty Base")
    assert "FINISHED" in result

    git_inst.repo.git.checkout("-b", "flow_dirty_feature")
    git_inst.repo.git.checkout(base_branch)
    git_inst.restore_ref(base_branch, park_changes=False)

    obj.location.x = 3.0
    git_inst._check()
    dirty_blocks = get_dirty_block_paths(git_inst)
    assert dirty_blocks

    result = bpy.ops.cozystudio.checkout_branch(
        "EXEC_DEFAULT", branch_name="flow_dirty_feature"
    )
    assert "FINISHED" in result

    if git_inst._managed_carryover_entries():
        result = bpy.ops.cozystudio.reapply_parked_changes("EXEC_DEFAULT")
        assert "FINISHED" in result
        assert_no_parked_changes(git_inst)

    restored = _find_object_by_uuid(uuid)
    assert restored is not None
    assert abs(restored.location.x - 3.0) < 1e-4

    assert_manifest_integrity_ok(git_inst)

    git_inst.repo.git.checkout(base_branch)
    git_inst.restore_ref(base_branch, park_changes=False)
    git_inst.repo.git.branch("-D", "flow_dirty_feature")


@pytest.mark.order(120)
@pytest.mark.flow
def test_flow_conflict_resolution_paths():
    git_inst = _setup_flow_repo("cozy_flow_conflict_")
    base_branch = _ensure_base_branch(git_inst)

    def make_conflict(branch_name: str, object_name: str):
        obj = create_test_object(name=object_name)
        obj.location.x = 0.0
        ensure_tracking_assignments(git_inst)
        uuid = wait_for_uuid(obj)
        assert uuid
        git_inst._check()
        assert wait_for_block_file(git_inst, uuid)

        result = bpy.ops.cozystudio.add_group(
            "EXEC_DEFAULT", group_id=_group_id_for_uuid(git_inst, uuid)
        )
        assert "FINISHED" in result
        result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message=f"{object_name} base")
        assert "FINISHED" in result

        git_inst.repo.git.checkout("-b", branch_name)
        obj.location.x = 1.0
        git_inst._check()
        result = bpy.ops.cozystudio.add_group(
            "EXEC_DEFAULT", group_id=_group_id_for_uuid(git_inst, uuid)
        )
        assert "FINISHED" in result
        result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message=f"{object_name} theirs")
        assert "FINISHED" in result

        git_inst.repo.git.checkout(base_branch)
        git_inst.restore_ref(base_branch, park_changes=False)
        obj.location.x = 2.0
        git_inst._check()
        result = bpy.ops.cozystudio.add_group(
            "EXEC_DEFAULT", group_id=_group_id_for_uuid(git_inst, uuid)
        )
        assert "FINISHED" in result
        result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message=f"{object_name} ours")
        assert "FINISHED" in result

        merge_result = bpy.ops.cozystudio.merge(
            "EXEC_DEFAULT", ref_name=branch_name, strategy="manual"
        )
        assert "FINISHED" in merge_result
        return uuid

    theirs_uuid = make_conflict("flow_conflict_theirs", "CozyFlowTheirsObject")
    result = bpy.ops.cozystudio.resolve_conflict_version(
        "EXEC_DEFAULT", conflict_uuid=theirs_uuid, resolution="theirs"
    )
    assert "FINISHED" in result
    _reapply_parked_if_needed(git_inst)
    restored = _find_object_by_uuid(theirs_uuid)
    assert restored is not None
    assert abs(restored.location.x - 1.0) < 1e-4
    git_inst.repo.git.branch("-D", "flow_conflict_theirs")

    ours_uuid = make_conflict("flow_conflict_ours", "CozyFlowOursObject")
    result = bpy.ops.cozystudio.resolve_conflict_version(
        "EXEC_DEFAULT", conflict_uuid=ours_uuid, resolution="ours"
    )
    assert "FINISHED" in result
    _reapply_parked_if_needed(git_inst)
    restored = _find_object_by_uuid(ours_uuid)
    assert restored is not None
    assert abs(restored.location.x - 2.0) < 1e-4
    git_inst.repo.git.branch("-D", "flow_conflict_ours")

    manual_uuid = make_conflict("flow_conflict_manual", "CozyFlowManualObject")
    result = bpy.ops.cozystudio.resolve_conflict(
        "EXEC_DEFAULT", conflict_uuid=manual_uuid
    )
    assert "FINISHED" in result
    _reapply_parked_if_needed(git_inst)
    restored = _find_object_by_uuid(manual_uuid)
    assert restored is not None
    assert abs(restored.location.x - 2.0) < 1e-4
    git_inst.repo.git.branch("-D", "flow_conflict_manual")

    assert_manifest_integrity_ok(git_inst)
    assert_no_parked_changes(git_inst)


@pytest.mark.order(130)
@pytest.mark.flow
def test_flow_rebase_chain():
    git_inst = _setup_flow_repo("cozy_flow_rebase_")
    base_branch = _ensure_base_branch(git_inst)

    obj = create_test_object(name="CozyFlowRebaseObject")
    obj.location.x = 0.0
    ensure_tracking_assignments(git_inst)
    uuid = wait_for_uuid(obj)
    assert uuid
    git_inst._check()
    assert wait_for_block_file(git_inst, uuid)

    result = bpy.ops.cozystudio.add_group(
        "EXEC_DEFAULT", group_id=_group_id_for_uuid(git_inst, uuid)
    )
    assert "FINISHED" in result
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Flow Rebase Base")
    assert "FINISHED" in result

    git_inst.repo.git.checkout("-b", "flow_rebase_feature")
    obj.location.x = 2.0
    git_inst._check()
    result = bpy.ops.cozystudio.add_group(
        "EXEC_DEFAULT", group_id=_group_id_for_uuid(git_inst, uuid)
    )
    assert "FINISHED" in result
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Flow Rebase Step 1")
    assert "FINISHED" in result

    obj.location.x = 5.0
    git_inst._check()
    result = bpy.ops.cozystudio.add_group(
        "EXEC_DEFAULT", group_id=_group_id_for_uuid(git_inst, uuid)
    )
    assert "FINISHED" in result
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Flow Rebase Step 2")
    assert "FINISHED" in result

    git_inst.repo.git.checkout(base_branch)
    git_inst.restore_ref(base_branch, park_changes=False)
    git_inst.repo.git.checkout("flow_rebase_feature")

    result = bpy.ops.cozystudio.rebase(
        "EXEC_DEFAULT", ref_name=base_branch, strategy="manual"
    )
    assert "FINISHED" in result

    restored = _find_object_by_uuid(uuid)
    assert restored is not None
    assert abs(restored.location.x - 5.0) < 1e-4

    assert_manifest_integrity_ok(git_inst)
    _assert_only_cozy_dirty(git_inst)
    assert_no_parked_changes(git_inst)

    git_inst.repo.git.checkout(base_branch)
    git_inst.restore_ref(base_branch, park_changes=False)
    git_inst.repo.git.branch("-D", "flow_rebase_feature")


@pytest.mark.order(140)
@pytest.mark.flow
def test_flow_order_stress_sequence():
    git_inst = _setup_flow_repo("cozy_flow_order_")
    base_branch = _ensure_base_branch(git_inst)

    obj = create_test_object(name="CozyFlowOrderObject")
    obj.location.x = 1.0
    ensure_tracking_assignments(git_inst)
    uuid = wait_for_uuid(obj)
    assert uuid
    git_inst._check()
    assert wait_for_block_file(git_inst, uuid)

    result = bpy.ops.cozystudio.add_group(
        "EXEC_DEFAULT", group_id=_group_id_for_uuid(git_inst, uuid)
    )
    assert "FINISHED" in result
    result = bpy.ops.cozystudio.unstage_group(
        "EXEC_DEFAULT", group_id=_group_id_for_uuid(git_inst, uuid)
    )
    assert "FINISHED" in result
    result = bpy.ops.cozystudio.add_group(
        "EXEC_DEFAULT", group_id=_group_id_for_uuid(git_inst, uuid)
    )
    assert "FINISHED" in result
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Flow Order Base")
    assert "FINISHED" in result
    base_commit = git_inst.repo.head.commit.hexsha

    git_inst.repo.git.checkout("-b", "flow_order_feature")
    obj.location.x = 6.0
    git_inst._check()
    result = bpy.ops.cozystudio.add_group(
        "EXEC_DEFAULT", group_id=_group_id_for_uuid(git_inst, uuid)
    )
    assert "FINISHED" in result
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Flow Order Feature")
    assert "FINISHED" in result

    result = bpy.ops.cozystudio.checkout_commit(
        "EXEC_DEFAULT", commit_hash=base_commit
    )
    assert "FINISHED" in result
    assert git_inst.repo.head.is_detached

    result = bpy.ops.cozystudio.checkout_branch(
        "EXEC_DEFAULT", branch_name=base_branch
    )
    assert "FINISHED" in result
    assert not git_inst.repo.head.is_detached

    result = bpy.ops.cozystudio.merge(
        "EXEC_DEFAULT", ref_name="flow_order_feature", strategy="manual"
    )
    assert "FINISHED" in result

    assert_no_parked_changes(git_inst)
    _assert_only_cozy_dirty(git_inst)
    assert not get_dirty_block_paths(git_inst)

    restored = _find_object_by_uuid(uuid)
    assert restored is not None
    assert abs(restored.location.x - 6.0) < 1e-4

    assert_manifest_integrity_ok(git_inst)
    assert_no_parked_changes(git_inst)

    git_inst.repo.git.checkout(base_branch)
    git_inst.restore_ref(base_branch, park_changes=False)
    git_inst.repo.git.branch("-D", "flow_order_feature")
