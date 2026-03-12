import importlib
import json

import bpy
import pytest

from ..helpers import (
    create_test_object,
    ensure_tracking_assignments,
    init_git_repo_for_test,
    wait_for_uuid,
)

ADDON_MODULE = "cozystudio_addon"


def _staged_paths(git_inst):
    return {
        path
        for (path, stage) in git_inst.repo.index.entries.keys()
        if stage == 0
    }


@pytest.mark.order(9)
def test_group_stage_stages_all_members():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)

    test_obj = create_test_object(name="CozyStageGroupObject")
    ensure_tracking_assignments(git_inst)

    obj_uuid = wait_for_uuid(test_obj)
    mesh_uuid = wait_for_uuid(test_obj.data)
    assert obj_uuid, "Object UUID was not assigned"
    assert mesh_uuid, "Mesh UUID was not assigned"

    git_inst._check()
    entries = git_inst.state.get("entries", {})
    groups = git_inst.state.get("groups", {})
    group_id = entries.get(obj_uuid, {}).get("group_id") or obj_uuid
    group_members = groups.get(group_id, {}).get("members", [])

    result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=group_id)
    assert "FINISHED" in result, f"add_group returned {result}"

    staged = _staged_paths(git_inst)
    expected = {f".cozystudio/blocks/{uuid}.json" for uuid in group_members}
    assert expected.issubset(staged)


@pytest.mark.order(10)
def test_commit_autostages_missing_group_members_and_manifest():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)

    test_obj = create_test_object(name="CozyCommitGroupObject")
    ensure_tracking_assignments(git_inst)

    obj_uuid = wait_for_uuid(test_obj)
    assert obj_uuid, "Object UUID was not assigned"

    git_inst._check()
    entries = git_inst.state.get("entries", {})
    groups = git_inst.state.get("groups", {})
    group_id = entries.get(obj_uuid, {}).get("group_id") or obj_uuid
    group_members = groups.get(group_id, {}).get("members", [])
    assert group_members, "Group members were not resolved"

    first_member = group_members[0]
    git_inst.stage(changes=[f".cozystudio/blocks/{first_member}.json"])

    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Group Commit")
    assert "FINISHED" in result, f"commit returned {result}"

    commit = git_inst.repo.head.commit
    for member_uuid in group_members:
        path = f".cozystudio/blocks/{member_uuid}.json"
        assert commit.tree / ".cozystudio" / "blocks" / f"{member_uuid}.json"

    manifest_raw = git_inst.repo.git.show(
        f"{commit.hexsha}:.cozystudio/manifest.json"
    )
    manifest = json.loads(manifest_raw)
    manifest_groups = manifest.get("groups", {})
    manifest_blocks = manifest.get("blocks", {})

    manifest_group = manifest_groups.get(group_id)
    assert manifest_group, "Manifest missing group metadata"
    assert set(manifest_group.get("members", [])) == set(group_members)

    for member_uuid in group_members:
        entry = manifest_blocks.get(member_uuid)
        assert entry, f"Manifest missing block entry for {member_uuid}"
        assert entry.get("group_id") == group_id
