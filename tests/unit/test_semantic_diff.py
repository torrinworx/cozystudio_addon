from cozystudio_addon.bl_git import BpyGit


def test_summarize_block_diff_reports_transform_changes():
    summary = BpyGit._summarize_block_diff(
        "modified",
        "objects",
        {"transforms": {"matrix_basis": [[1, 0, 0, 0]]}},
        {"transforms": {"matrix_basis": [[1, 0, 0, 2]]}},
    )

    assert summary == "Transform changed"


def test_summarize_block_diff_reports_collection_material_and_animation_changes():
    collection_summary = BpyGit._summarize_block_diff(
        "modified",
        "collections",
        {"objects": ["a"], "children": []},
        {"objects": ["a", "b"], "children": []},
    )
    material_summary = BpyGit._summarize_block_diff(
        "modified",
        "meshes",
        {"materials": ["mat-a"]},
        {"materials": ["mat-b"]},
    )
    animation_summary = BpyGit._summarize_block_diff(
        "modified",
        "actions",
        {"animation_data": {"action": "a"}},
        {"animation_data": {"action": "b"}},
    )

    assert collection_summary == "Collection membership changed"
    assert material_summary == "Material slots changed"
    assert animation_summary == "Animation changed"


def test_summarize_block_diff_uses_safe_generic_fallbacks():
    added_summary = BpyGit._summarize_block_diff("staged_added", "meshes", None, {"name": "Cube"})
    deleted_summary = BpyGit._summarize_block_diff("deleted", "materials", {"name": "Mat"}, None)
    fallback_summary = BpyGit._summarize_block_diff(
        "modified",
        "worlds",
        {"name": "World", "strength": 1.0, "color": [1, 1, 1]},
        {"name": "World", "strength": 2.0, "color": [0.5, 0.5, 0.5]},
    )

    assert added_summary == "Created mesh"
    assert deleted_summary == "Deleted material"
    assert fallback_summary == "Updated 2 sections"
