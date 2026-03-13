import importlib

import bpy
import pytest

from ..helpers import (
    ensure_tracking_assignments,
    init_git_repo_for_test,
    wait_for_block_file,
    wait_for_uuid,
)

ADDON_MODULE = "cozystudio_addon"


def create_cube_object(name="CozySculptCube"):
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(
        [
            (-1.0, -1.0, -1.0),
            (1.0, -1.0, -1.0),
            (1.0, 1.0, -1.0),
            (-1.0, 1.0, -1.0),
            (-1.0, -1.0, 1.0),
            (1.0, -1.0, 1.0),
            (1.0, 1.0, 1.0),
            (-1.0, 1.0, 1.0),
        ],
        [],
        [
            (0, 1, 2, 3),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
        ],
    )
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)

    if bpy.context.view_layer:
        for scene_obj in bpy.context.view_layer.objects:
            scene_obj.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

    return obj


@pytest.mark.order(9)
def test_passive_check_defers_mesh_capture_in_sculpt_mode():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)

    cube = create_cube_object(name="CozyPassiveSculptCube")
    ensure_tracking_assignments(git_inst)

    mesh_uuid = wait_for_uuid(cube.data)
    assert mesh_uuid, "Mesh UUID was not assigned"

    git_inst._check()
    block_path = wait_for_block_file(git_inst, mesh_uuid)
    assert block_path is not None, "Mesh block file was not created"
    initial_block = block_path.read_text(encoding="utf-8")

    cube.data.vertices[0].co.x += 0.5
    cube.data.update()
    bpy.ops.object.mode_set(mode="SCULPT")

    git_inst._check()

    assert bpy.context.mode == "SCULPT"
    assert block_path.read_text(encoding="utf-8") == initial_block
    assert git_inst.last_capture_issues, "Expected passive capture issue in Sculpt mode"
    assert git_inst.last_capture_issues[0]["status"] == "deferred"

    bpy.ops.object.mode_set(mode="OBJECT")


@pytest.mark.order(10)
def test_commit_captures_mesh_changes_while_in_sculpt_mode():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)

    cube = create_cube_object(name="CozyInteractiveSculptCube")
    ensure_tracking_assignments(git_inst)

    object_uuid = wait_for_uuid(cube)
    mesh_uuid = wait_for_uuid(cube.data)
    assert object_uuid, "Object UUID was not assigned"
    assert mesh_uuid, "Mesh UUID was not assigned"

    git_inst._check()
    mesh_path = wait_for_block_file(git_inst, mesh_uuid)
    assert mesh_path is not None, "Mesh block file was not created"

    group_id = (
        git_inst.state.get("entries", {}).get(object_uuid, {}).get("group_id") or object_uuid
    )

    result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=group_id)
    assert "FINISHED" in result, f"add_group returned {result}"
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Baseline Sculpt Commit")
    assert "FINISHED" in result, f"commit returned {result}"

    baseline_block = mesh_path.read_text(encoding="utf-8")

    cube.data.vertices[0].co.z += 0.75
    cube.data.update()
    bpy.ops.object.mode_set(mode="SCULPT")

    result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=group_id)
    assert "FINISHED" in result, f"add_group returned {result}"
    result = bpy.ops.cozystudio.commit("EXEC_DEFAULT", message="Commit Sculpt Mesh")
    assert "FINISHED" in result, f"commit returned {result}"

    assert bpy.context.mode == "SCULPT"
    assert not git_inst.last_capture_issues
    assert mesh_path.read_text(encoding="utf-8") != baseline_block

    bpy.ops.object.mode_set(mode="OBJECT")
