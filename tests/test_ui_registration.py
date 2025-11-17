import bpy
import pytest
import importlib

ADDON_MODULE = "cozystudio_addon"

expected_ops = [
    "cozystudio.init_repo",
    "cozystudio.commit",
    "cozystudio.checkout_commit",
    "cozystudio.add_file",
    "cozystudio.unstage_file",
]
expected_panels = ["COZYSTUDIO_PT_panel"]


@pytest.mark.order(3)
def test_all_cozystudio_ui_classes_registered():
    """Ensure all CozyStudio operators and panels are registered once addon is enabled."""
    assert (
        ADDON_MODULE in bpy.context.preferences.addons
    ), f"{ADDON_MODULE} must be enabled before running UI registration tests."

    importlib.import_module(f"{ADDON_MODULE}.ui")

    # Operator registration
    missing_ops = [
        op for op in expected_ops if not hasattr(bpy.ops.cozystudio, op.split(".")[-1])
    ]
    assert not missing_ops, f"Missing operators: {missing_ops}"

    # Panel registration
    missing_panels = [pid for pid in expected_panels if not hasattr(bpy.types, pid)]
    assert not missing_panels, f"Missing panels: {missing_panels}"

    # Just confirm the draw method exists, don't call it
    for pid in expected_panels:
        panel_cls = getattr(bpy.types, pid)
        assert hasattr(panel_cls, "draw"), f"Panel {pid} has no draw() method"
