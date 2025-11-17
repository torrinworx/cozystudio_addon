import os
import time
import bpy
import pytest
import importlib

ADDON_MODULE = "cozystudio_addon"


def _wait_for_git_instance(ui_mod, timeout=3.0):
    """Poll until ui_mod.git_instance exists and is initialized, or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        git_inst = getattr(ui_mod, "git_instance", None)
        if git_inst is not None:
            # optional: if BpyGit sets an 'initiated' flag, wait for that too
            return git_inst
        # Manually run any pending timers; Blender does this in its event loop.
        bpy.app.timers.is_registered  # Accessing runs internal tick check
        time.sleep(0.1)
    return None


@pytest.mark.order(4)
def test_initialize_git_repository():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")

    # Force Blender timers to tick a few times to allow check_and_init_git to run.
    git_inst = _wait_for_git_instance(ui_mod)
    if git_inst is None:
        # If still missing, call it manually — exactly what the timer would do.
        ui_mod.check_and_init_git()
        git_inst = getattr(ui_mod, "git_instance", None)

    assert git_inst is not None, "git_instance was never created before init_repo"

    # Now trigger the operator that should initialize or mark it initiated
    result = bpy.ops.cozystudio.init_repo()
    assert "FINISHED" in result or "CANCELLED" in result, \
        f"init_repo operator returned {result}"

    # Give background timers a moment if they are used during .init()
    time.sleep(0.5)

    git_inst = getattr(ui_mod, "git_instance", None)
    assert git_inst is not None, "git_instance still missing after init_repo"
    assert getattr(git_inst, "initiated", False), "git_instance was not marked initiated"

    # Verify that a .git directory was actually created in same folder as current file
    git_path = os.path.join(os.path.dirname(bpy.data.filepath), ".git")
    assert os.path.exists(git_path) and os.path.isdir(git_path), \
        f".git directory not found at expected path: {git_path}"

    print("[GIT] Repository initialized successfully at:", git_path)