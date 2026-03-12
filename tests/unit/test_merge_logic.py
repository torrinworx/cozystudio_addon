import json

from cozystudio_addon.bl_git import BpyGit


def _merge(base, ours, theirs):
    inst = BpyGit.__new__(BpyGit)
    return inst._three_way_merge_json(base, ours, theirs)


def test_three_way_merge_non_overlapping():
    base = {"a": 1, "b": {"x": 1}, "c": 3}
    ours = {"a": 1, "b": {"x": 2}, "c": 3}
    theirs = {"a": 1, "b": {"x": 1}, "c": 4}

    merged, conflict = _merge(base, ours, theirs)
    assert not conflict
    assert merged["b"]["x"] == 2
    assert merged["c"] == 4


def test_three_way_merge_conflict():
    base = {"a": 1}
    ours = {"a": 2}
    theirs = {"a": 3}

    merged, conflict = _merge(base, ours, theirs)
    assert conflict
    assert merged is None


def test_three_way_merge_nested_conflict():
    base = {"a": {"x": 1, "y": 2}}
    ours = {"a": {"x": 2, "y": 2}}
    theirs = {"a": {"x": 3, "y": 2}}

    merged, conflict = _merge(base, ours, theirs)
    assert conflict
    assert merged is None
