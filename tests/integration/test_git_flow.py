import importlib
import json

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


def _find_object_by_uuid(uuid):
    for obj in bpy.data.objects:
        if getattr(obj, "cozystudio_uuid", None) == uuid:
            return obj
    return None


def _managed_stash_entries(git_inst):
    return git_inst._managed_carryover_entries()


@pytest.mark.order(5)
def test_git_flow_stage_commit_checkout():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)

    test_obj = create_test_object(name="CozyFlowObject")
    test_obj.location.x = 1.0

    ensure_tracking_assignments(git_inst)

    uuid = wait_for_uuid(test_obj)
    assert uuid, "Object UUID was not assigned"
    git_inst._check()
    block_path = wait_for_block_file(git_inst, uuid)
    assert block_path is not None, "Block file was not created"

    rel_path = f".cozystudio/blocks/{uuid}.json"

    group_id = (
        git_inst.state.get("entries", {}).get(uuid, {}).get("group_id") or uuid
    )
    result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=group_id)
    assert "FINISHED" in result, f"add_group returned {result}"

    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Commit 1")
    assert "FINISHED" in result, f"commit returned {result}"
    commit1 = git_inst.repo.head.commit.hexsha

    test_obj.location.x = 2.0
    git_inst._check()
    result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=group_id)
    assert "FINISHED" in result, f"add_group returned {result}"
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Commit 2")
    assert "FINISHED" in result, f"commit returned {result}"

    git_inst.checkout(commit1)

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


@pytest.mark.order(7)
def test_checkout_does_not_dirty_blocks():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)

    test_obj = create_test_object(name="CozyNoDiffObject")
    test_obj.location.x = 1.0

    ensure_tracking_assignments(git_inst)

    uuid = wait_for_uuid(test_obj)
    assert uuid, "Object UUID was not assigned"
    mesh_uuid = wait_for_uuid(test_obj.data)
    assert mesh_uuid, "Mesh UUID was not assigned"

    git_inst._check()
    block_path = wait_for_block_file(git_inst, uuid)
    assert block_path is not None, "Block file was not created"

    rel_path = f".cozystudio/blocks/{uuid}.json"
    mesh_path = f".cozystudio/blocks/{mesh_uuid}.json"

    group_id = (
        git_inst.state.get("entries", {}).get(uuid, {}).get("group_id") or uuid
    )
    result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=group_id)
    assert "FINISHED" in result, f"add_group returned {result}"
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Commit A")
    assert "FINISHED" in result, f"commit returned {result}"
    commit_a = git_inst.repo.head.commit.hexsha

    test_obj.location.x = 2.0
    git_inst._check()
    result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=group_id)
    assert "FINISHED" in result, f"add_group returned {result}"
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Commit B")
    assert "FINISHED" in result, f"commit returned {result}"
    commit_b = git_inst.repo.head.commit.hexsha

    git_inst.checkout(commit_a)

    working_paths = {
        diff.b_path or diff.a_path
        for diff in git_inst.repo.index.diff(None)
    }
    working_paths.update(git_inst.repo.untracked_files)
    dirty_blocks = {
        path for path in working_paths if path.startswith(".cozystudio/blocks/")
    }
    assert rel_path not in dirty_blocks, (
        f"Unexpected object block diff after checkout: {rel_path}"
    )
    assert mesh_path not in dirty_blocks, (
        f"Unexpected mesh block diff after checkout: {mesh_path}"
    )

    git_inst.checkout(commit_b)

    working_paths = {
        diff.b_path or diff.a_path
        for diff in git_inst.repo.index.diff(None)
    }
    working_paths.update(git_inst.repo.untracked_files)
    dirty_blocks = {
        path for path in working_paths if path.startswith(".cozystudio/blocks/")
    }
    assert rel_path not in dirty_blocks, (
        f"Unexpected object block diff after checkout: {rel_path}"
    )
    assert mesh_path not in dirty_blocks, (
        f"Unexpected mesh block diff after checkout: {mesh_path}"
    )


@pytest.mark.order(8)
def test_commit_ignores_blend_file():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)

    test_obj = create_test_object(name="CozyNoBlendCommitObject")
    ensure_tracking_assignments(git_inst)

    uuid = wait_for_uuid(test_obj)
    assert uuid, "Object UUID was not assigned"

    git_inst._check()
    group_id = (
        git_inst.state.get("entries", {}).get(uuid, {}).get("group_id") or uuid
    )

    blend_name = bpy.path.basename(bpy.data.filepath)
    git_inst.stage(changes=[blend_name])
    staged_paths = {
        path
        for (path, stage) in git_inst.repo.index.entries.keys()
        if stage == 0
    }
    assert blend_name not in staged_paths, ".blend file should not stage through Cozy"

    result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=group_id)
    assert "FINISHED" in result, f"add_group returned {result}"

    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Commit Without Blend")
    assert "FINISHED" in result, f"commit returned {result}"

    commit = git_inst.repo.head.commit
    committed_paths = {item.path for item in commit.tree.traverse() if item.type == "blob"}
    assert ".cozystudio/manifest.json" in committed_paths
    assert f".cozystudio/blocks/{uuid}.json" in committed_paths
    assert not any(path.endswith(".blend") for path in committed_paths), (
        f"Snapshot commit should not include bootstrap blend files: {sorted(committed_paths)}"
    )


@pytest.mark.order(11)
def test_branch_switch_restores_manifest_state():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)
    base_branch = get_repo_branch_name(git_inst.repo)
    assert base_branch
    git_inst.switch_branch(base_branch)

    test_obj = create_test_object(name="CozyBranchSwitchObject")
    test_obj.location.x = 0.0
    ensure_tracking_assignments(git_inst)

    uuid = wait_for_uuid(test_obj)
    assert uuid, "Object UUID was not assigned"

    git_inst._check()
    group_id = (
        git_inst.state.get("entries", {}).get(uuid, {}).get("group_id") or uuid
    )
    result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=group_id)
    assert "FINISHED" in result, f"add_group returned {result}"
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Base Branch State")
    assert "FINISHED" in result, f"commit returned {result}"

    git_inst.repo.git.checkout("-b", "feature_switch")
    rel_path = f".cozystudio/blocks/{uuid}.json"

    test_obj.location.x = 4.0
    git_inst._check()
    result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=group_id)
    assert "FINISHED" in result, f"add_group returned {result}"
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Feature Branch State")
    assert "FINISHED" in result, f"commit returned {result}"

    result = bpy.ops.cozystudio.checkout_branch(
        "EXEC_DEFAULT", branch_name=base_branch
    )
    assert "FINISHED" in result, f"checkout_branch returned {result}"
    assert not git_inst.repo.head.is_detached
    assert git_inst.repo.active_branch.name == base_branch

    restored_obj = _find_object_by_uuid(uuid)
    assert restored_obj is not None
    assert abs(restored_obj.location.x - 0.0) < 1e-4

    working_paths = {
        diff.b_path or diff.a_path
        for diff in git_inst.repo.index.diff(None)
    }
    working_paths.update(git_inst.repo.untracked_files)
    dirty_blocks = {
        path for path in working_paths if path.startswith(".cozystudio/blocks/")
    }
    assert rel_path not in dirty_blocks, (
        f"Unexpected target block diff after branch switch: {dirty_blocks}"
    )

    result = bpy.ops.cozystudio.checkout_branch(
        "EXEC_DEFAULT", branch_name="feature_switch"
    )
    assert "FINISHED" in result, f"checkout_branch returned {result}"
    assert not git_inst.repo.head.is_detached
    assert git_inst.repo.active_branch.name == "feature_switch"

    restored_obj = _find_object_by_uuid(uuid)
    assert restored_obj is not None
    assert abs(restored_obj.location.x - 4.0) < 1e-4

    working_paths = {
        diff.b_path or diff.a_path
        for diff in git_inst.repo.index.diff(None)
    }
    working_paths.update(git_inst.repo.untracked_files)
    dirty_blocks = {
        path for path in working_paths if path.startswith(".cozystudio/blocks/")
    }
    assert rel_path not in dirty_blocks, (
        f"Unexpected target block diff after branch switch: {dirty_blocks}"
    )

    result = bpy.ops.cozystudio.checkout_branch(
        "EXEC_DEFAULT", branch_name=base_branch
    )
    assert "FINISHED" in result, f"checkout_branch returned {result}"
    git_inst.repo.git.branch("-D", "feature_switch")


@pytest.mark.order(12)
def test_ui_state_payload_tracks_repo_branch_conflicts_and_counts():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)

    test_obj = create_test_object(name="CozyUiStateObject")
    test_obj.location.x = 1.0
    ensure_tracking_assignments(git_inst)

    uuid = wait_for_uuid(test_obj)
    assert uuid, "Object UUID was not assigned"

    git_inst._check()
    group_id = (
        git_inst.state.get("entries", {}).get(uuid, {}).get("group_id") or uuid
    )

    result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=group_id)
    assert "FINISHED" in result, f"add_group returned {result}"

    git_inst.refresh_ui_state()
    ui_state = git_inst.ui_state
    assert ui_state["repo"]["available"]
    assert ui_state["repo"]["initiated"]
    assert ui_state["changes"]["staged"] >= 1
    assert ui_state["changes"]["staged_groups"]

    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="UI State Base")
    assert "FINISHED" in result, f"commit returned {result}"
    commit1 = git_inst.repo.head.commit.hexsha
    base_branch = get_repo_branch_name(git_inst.repo)
    assert base_branch

    test_obj.location.x = 3.0
    git_inst._check()
    result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=group_id)
    assert "FINISHED" in result, f"add_group returned {result}"
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="UI State Updated")
    assert "FINISHED" in result, f"commit returned {result}"

    git_inst.checkout(commit1)

    ui_state = git_inst.ui_state
    assert ui_state["branch"]["detached"]
    assert ui_state["commit"]["viewing_past"]
    assert ui_state["commit"]["return_branch"] == base_branch
    assert ui_state["integrity"]["ok"]
    assert ui_state["history"]["items"]
    assert ui_state["history"]["items"][0]["commit_hash"]

    git_inst.manifest["conflicts"] = [
        {
            "uuid": uuid,
            "reason": "Synthetic test conflict",
            "label": "CozyUiStateObject",
            "datablock_type": "objects",
            "operation": "merge",
            "ours_ref": commit1,
            "theirs_ref": commit1,
            "ours_entry": git_inst.manifest.get("blocks", {}).get(uuid),
            "theirs_entry": git_inst.manifest.get("blocks", {}).get(uuid),
        }
    ]
    git_inst.manifest.write()
    git_inst.last_integrity_report = git_inst.validate_manifest_integrity()
    git_inst.refresh_ui_state()

    ui_state = git_inst.ui_state
    assert ui_state["conflicts"]["has_conflicts"]
    assert ui_state["conflicts"]["items"][0]["uuid"] == uuid
    assert ui_state["conflicts"]["items"][0]["label"] == "CozyUiStateObject"
    assert ui_state["conflicts"]["operation"] == "merge"
    assert not ui_state["integrity"]["ok"]
    assert "Unresolved conflicts present in manifest." in ui_state["integrity"]["errors"]

    clear_manifest_conflicts(git_inst)
    git_inst.last_integrity_report = git_inst.validate_manifest_integrity()
    git_inst.switch_branch(base_branch)


@pytest.mark.order(13)
def test_checkout_branch_auto_stashes_and_reapplies_cozy_changes():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)
    base_branch = get_repo_branch_name(git_inst.repo)
    assert base_branch

    test_obj = create_test_object(name="CozyCarryoverBranchObject")
    test_obj.location.x = 0.0
    ensure_tracking_assignments(git_inst)

    uuid = wait_for_uuid(test_obj)
    assert uuid

    git_inst._check()
    group_id = (
        git_inst.state.get("entries", {}).get(uuid, {}).get("group_id") or uuid
    )
    result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=group_id)
    assert "FINISHED" in result
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Carryover base")
    assert "FINISHED" in result

    git_inst.repo.git.checkout("-b", "feature_carryover_branch")
    git_inst.repo.git.checkout(base_branch)
    git_inst.restore_ref(base_branch, park_changes=False)

    test_obj.location.x = 7.0
    git_inst._check()

    result = bpy.ops.cozystudio.checkout_branch(
        "EXEC_DEFAULT", branch_name="feature_carryover_branch"
    )
    assert "FINISHED" in result, f"checkout_branch returned {result}"
    assert git_inst.repo.active_branch.name == "feature_carryover_branch"
    assert not _managed_stash_entries(git_inst)

    restored_obj = _find_object_by_uuid(uuid)
    assert restored_obj is not None
    assert abs(restored_obj.location.x - 7.0) < 1e-4

    working_paths = {
        diff.b_path or diff.a_path
        for diff in git_inst.repo.index.diff(None)
    }
    working_paths.update(git_inst.repo.untracked_files)
    assert f".cozystudio/blocks/{uuid}.json" in working_paths

    git_inst.repo.git.restore(
        "--source=HEAD",
        "--staged",
        "--worktree",
        "--",
        ".cozystudio/manifest.json",
        ".cozystudio/blocks",
    )
    git_inst.restore_ref()
    git_inst.repo.git.checkout(base_branch)
    git_inst.restore_ref(base_branch, park_changes=False)
    git_inst.repo.git.branch("-D", "feature_carryover_branch")


@pytest.mark.order(14)
def test_git_named_commit_checkout_and_branch_checkout_operators():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)
    base_branch = get_repo_branch_name(git_inst.repo)
    assert base_branch

    test_obj = create_test_object(name="CozyProductOpsObject")
    test_obj.location.x = 1.0
    ensure_tracking_assignments(git_inst)

    uuid = wait_for_uuid(test_obj)
    assert uuid

    git_inst._check()
    group_id = (
        git_inst.state.get("entries", {}).get(uuid, {}).get("group_id") or uuid
    )
    result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=group_id)
    assert "FINISHED" in result
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Git Language Base")
    assert "FINISHED" in result
    commit1 = git_inst.repo.head.commit.hexsha

    test_obj.location.x = 5.0
    git_inst._check()
    result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=group_id)
    assert "FINISHED" in result
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Git Language Updated")
    assert "FINISHED" in result

    result = bpy.ops.cozystudio.checkout_commit("EXEC_DEFAULT", commit_hash=commit1)
    assert "FINISHED" in result
    assert git_inst.repo.head.is_detached

    restored_obj = _find_object_by_uuid(uuid)
    assert restored_obj is not None
    assert abs(restored_obj.location.x - 1.0) < 1e-4

    result = bpy.ops.cozystudio.checkout_branch("EXEC_DEFAULT", branch_name=base_branch)
    assert "FINISHED" in result
    assert not git_inst.repo.head.is_detached
    assert git_inst.repo.active_branch.name == base_branch

    restored_obj = _find_object_by_uuid(uuid)
    assert restored_obj is not None
    assert abs(restored_obj.location.x - 5.0) < 1e-4

    result = bpy.ops.cozystudio.run_diagnostics("EXEC_DEFAULT")
    assert "FINISHED" in result


@pytest.mark.order(15)
def test_commit_preflight_returns_structured_blockers():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)

    result = git_inst.commit_preflight()

    assert "ok" in result
    assert "can_commit" in result
    if result["can_commit"]:
        assert result["staged_count"] > 0
    else:
        assert any(
            "No staged changes" in blocker for blocker in result.get("blockers", [])
        )


@pytest.mark.order(16)
def test_create_branch_normalizes_human_friendly_name():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)

    test_obj = create_test_object(name="CozyBranchNameObject")
    ensure_tracking_assignments(git_inst)

    uuid = wait_for_uuid(test_obj)
    assert uuid

    git_inst._check()
    group_id = (
        git_inst.state.get("entries", {}).get(uuid, {}).get("group_id") or uuid
    )
    result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=group_id)
    assert "FINISHED" in result
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Branch Name Base")
    assert "FINISHED" in result

    result = bpy.ops.cozystudio.create_branch(
        "EXEC_DEFAULT",
        branch_name="adding purple cone",
    )
    assert "FINISHED" in result
    assert git_inst.repo.active_branch.name == "adding-purple-cone"


@pytest.mark.order(17)
def test_history_scoped_to_current_branch():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)
    base_branch = get_repo_branch_name(git_inst.repo)
    assert base_branch

    test_obj = create_test_object(name="CozyHistoryScopeObject")
    test_obj.location.x = 1.0
    ensure_tracking_assignments(git_inst)

    uuid = wait_for_uuid(test_obj)
    assert uuid

    git_inst._check()
    group_id = (
        git_inst.state.get("entries", {}).get(uuid, {}).get("group_id") or uuid
    )
    result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=group_id)
    assert "FINISHED" in result
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="History Base")
    assert "FINISHED" in result

    branch_name = "feature_history_scope"
    git_inst.create_branch(branch_name)

    test_obj.location.x = 2.0
    git_inst._check()
    result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=group_id)
    assert "FINISHED" in result
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="History Feature")
    assert "FINISHED" in result
    feature_commit = git_inst.repo.head.commit.hexsha

    git_inst.refresh_ui_state()
    feature_history_hashes = {
        item.get("commit_hash") for item in git_inst.ui_state["history"]["items"]
    }
    assert feature_commit in feature_history_hashes

    git_inst.switch_branch(base_branch)
    git_inst.refresh_ui_state()
    base_history_hashes = {
        item.get("commit_hash") for item in git_inst.ui_state["history"]["items"]
    }
    assert feature_commit not in base_history_hashes

    git_inst.repo.git.branch("-D", branch_name)
