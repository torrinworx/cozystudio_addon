from cozystudio_addon.bl_git import BpyGit, MANIFEST_GROUP_KEY


def test_group_stage_paths_returns_missing_members():
    staged_paths = {".cozystudio/blocks/a.json"}
    entries = {
        "a": {MANIFEST_GROUP_KEY: "group-1"},
        "b": {MANIFEST_GROUP_KEY: "group-1"},
    }
    groups = {"group-1": {"members": ["a", "b"]}}

    missing = BpyGit._group_stage_paths(staged_paths, entries, groups)

    assert missing == [".cozystudio/blocks/a.json", ".cozystudio/blocks/b.json"]


def test_group_stage_paths_handles_unknown_group():
    staged_paths = {".cozystudio/blocks/orphan.json"}
    entries = {"orphan": {MANIFEST_GROUP_KEY: None}}
    groups = {}

    missing = BpyGit._group_stage_paths(staged_paths, entries, groups)

    assert missing == [".cozystudio/blocks/orphan.json"]
