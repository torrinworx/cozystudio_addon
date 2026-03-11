import bpy
import pytest

ADDON_MODULE = "cozystudio_addon"


@pytest.mark.order(1)
def test_addon_enable():
    result = bpy.ops.preferences.addon_enable(module=ADDON_MODULE)
    assert "FINISHED" in result or "CANCELLED" in result, \
        f"addon_enable returned {result}"

    assert ADDON_MODULE in bpy.context.preferences.addons, (
        f"{ADDON_MODULE} should appear in enabled addons after enable. "
        f"Currently: {[a for a in bpy.context.preferences.addons.keys()]}"
    )
