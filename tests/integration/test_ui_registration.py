import importlib

import bpy
import pytest

ADDON_MODULE = "cozystudio_addon"

expected_ops = [
    "cozystudio.setup_project",
    "cozystudio.commit",
    "cozystudio.checkout_commit",
    "cozystudio.checkout_branch",
    "cozystudio.reapply_parked_changes",
    "cozystudio.merge",
    "cozystudio.rebase",
    "cozystudio.resolve_conflict",
    "cozystudio.resolve_conflict_version",
    "cozystudio.run_diagnostics",
    "cozystudio.select_block",
    "cozystudio.add_file",
    "cozystudio.unstage_file",
    "cozystudio.add_group",
    "cozystudio.unstage_group",
    "cozystudio.revert_change",
    "cozystudio.install_deps",
]
expected_panels = [
    "COZYSTUDIO_PT_main",
    "COZYSTUDIO_PT_changes",
    "COZYSTUDIO_PT_history",
    "COZYSTUDIO_PT_branches",
    "COZYSTUDIO_PT_conflicts",
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
    assert hasattr(bpy.types.WindowManager, "cozystudio_commit_message")

    for pid in expected_panels:
        panel_cls = getattr(bpy.types, pid)
        assert hasattr(panel_cls, "draw"), f"Panel {pid} has no draw() method"
