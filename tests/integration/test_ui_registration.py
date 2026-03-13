import importlib

import bpy
import pytest

ADDON_MODULE = "cozystudio_addon"

expected_ops = [
    "cozystudio.setup_project",
    "cozystudio.create_snapshot",
    "cozystudio.restore_snapshot",
    "cozystudio.switch_branch",
    "cozystudio.bring_in_changes",
    "cozystudio.replay_my_work",
    "cozystudio.resolve_conflict",
    "cozystudio.run_diagnostics",
    "cozystudio.init_repo",
    "cozystudio.commit",
    "cozystudio.checkout_commit",
    "cozystudio.checkout_branch",
    "cozystudio.select_block",
    "cozystudio.add_file",
    "cozystudio.unstage_file",
    "cozystudio.install_deps",
]
expected_panels = [
    "COZYSTUDIO_PT_project",
    "COZYSTUDIO_PT_panel",
    "COZYSTUDIO_PT_snapshot",
    "COZYSTUDIO_PT_log",
    "COZYSTUDIO_PT_sync",
    "COZYSTUDIO_PT_conflicts",
    "COZYSTUDIO_PT_diagnostics",
]


@pytest.mark.order(3)
def test_all_cozystudio_ui_classes_registered():
    assert (
        ADDON_MODULE in bpy.context.preferences.addons
    ), f"{ADDON_MODULE} must be enabled before running UI registration tests."

    importlib.import_module(f"{ADDON_MODULE}.ui")

    missing_ops = [
        op for op in expected_ops if not hasattr(bpy.ops.cozystudio, op.split(".")[-1])
    ]
    assert not missing_ops, f"Missing operators: {missing_ops}"

    missing_panels = [pid for pid in expected_panels if not hasattr(bpy.types, pid)]
    assert not missing_panels, f"Missing panels: {missing_panels}"
    assert hasattr(bpy.types.WindowManager, "cozystudio_advanced_mode")

    for pid in expected_panels:
        panel_cls = getattr(bpy.types, pid)
        assert hasattr(panel_cls, "draw"), f"Panel {pid} has no draw() method"
