import importlib
import json
import subprocess
import tempfile
import time
from pathlib import Path

import pytest
import bpy

from ..helpers import init_git_repo_for_test

ADDON_MODULE = "cozystudio_addon"


@pytest.mark.order(4)
def test_initialize_git_repository():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)
    assert git_inst is not None


@pytest.mark.order(99)
def test_new_file_save_init_commit_flow():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_dir = Path(tmp_dir)
        blend_path = project_dir / "TestProject.blend"

        bpy.ops.wm.read_factory_settings(use_empty=False)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
        bpy.ops.wm.open_mainfile(filepath=str(blend_path))

        start = time.time()
        while time.time() - start < 3.0:
            ui_mod.check_and_init_git()
            git_inst = getattr(ui_mod, "git_instance", None)
            if git_inst is not None and getattr(git_inst, "path", None) == project_dir:
                break
            time.sleep(0.1)

        git_inst = getattr(ui_mod, "git_instance", None)
        assert git_inst is not None
        assert git_inst.path == project_dir

        result = bpy.ops.cozystudio.setup_project()
        assert "FINISHED" in result, f"setup_project returned {result}"

        git_inst._check()
        manifest_path = project_dir / ".cozystudio" / "manifest.json"
        assert manifest_path.exists()
        blocks_path = project_dir / ".cozystudio" / "blocks"
        assert blocks_path.exists()
        assert any(blocks_path.iterdir())

        with open(manifest_path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        assert manifest.get("blocks")

        entry_ids = list((git_inst.state or {}).get("entries", {}).keys())
        assert entry_ids
        group_id = (
            git_inst.state.get("entries", {}).get(entry_ids[0], {}).get("group_id")
            or entry_ids[0]
        )
        result = bpy.ops.cozystudio.add_group("EXEC_DEFAULT", group_id=group_id)
        assert "FINISHED" in result, f"add_group returned {result}"

        result = git_inst.commit(message="Initial Commit")
        assert result.get("ok"), f"commit returned {result}"
        assert git_inst.repo.head.is_valid()


@pytest.mark.order(100)
def test_setup_project_prefers_local_repo_over_parent_repo():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")

    with tempfile.TemporaryDirectory() as tmp_dir:
        parent_dir = Path(tmp_dir)
        subprocess.run(["git", "init"], cwd=parent_dir, check=True, capture_output=True)

        project_dir = parent_dir / "nested_project"
        project_dir.mkdir()
        blend_path = project_dir / "NestedProject.blend"

        bpy.ops.wm.read_factory_settings(use_empty=False)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
        bpy.ops.wm.open_mainfile(filepath=str(blend_path))

        start = time.time()
        while time.time() - start < 3.0:
            ui_mod.check_and_init_git()
            git_inst = getattr(ui_mod, "git_instance", None)
            if git_inst is not None and getattr(git_inst, "path", None) == project_dir:
                break
            time.sleep(0.1)

        git_inst = getattr(ui_mod, "git_instance", None)
        assert git_inst is not None
        assert git_inst.path == project_dir
        assert git_inst.repo is None

        result = bpy.ops.cozystudio.setup_project()
        assert "FINISHED" in result, f"setup_project returned {result}"

        assert (project_dir / ".git").exists()
        assert git_inst.repo is not None
        assert Path(git_inst.repo.working_tree_dir).resolve() == project_dir
        assert Path(parent_dir / ".git").resolve() != Path(git_inst.repo.working_tree_dir).resolve()
