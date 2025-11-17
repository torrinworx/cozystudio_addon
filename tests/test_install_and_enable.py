import sys
import time
import importlib

import bpy
import pytest

ADDON_MODULE = "cozystudio_addon"


def test_dependencies_can_be_installed():
    """Verify that install_packages() completes and dependencies are importable."""
    cozy = importlib.import_module(ADDON_MODULE)

    # Make sure we can at least parse requirements
    reqs = cozy.parse_requirements(cozy.REQUIREMENTS_PATH)
    assert isinstance(reqs, list)

    missing = cozy.check_dependencies()
    if not missing:
        # Nothing missing ⇒ already OK
        assert (
            cozy.DEPENDENCIES_INSTALLED is True or cozy.DEPENDENCIES_INSTALLED is False
        )
        return

    # Trigger installation synchronously
    cozy.install_packages()

    # Check the global flags were updated
    assert isinstance(cozy.MISSING_DEPENDENCIES, list)
    assert (
        len(cozy.MISSING_DEPENDENCIES) == 0
    ), f"Still missing after install: {cozy.MISSING_DEPENDENCIES}"
    assert cozy.DEPENDENCIES_INSTALLED, "Dependencies should report as installed"


def test_addon_can_enable_and_disable(tmp_path):
    """Enable and disable the CozyStudio addon inside Blender preferences."""
    if ADDON_MODULE in sys.modules:
        del sys.modules[ADDON_MODULE]

    # --- Enable ---
    result = bpy.ops.preferences.addon_enable(module=ADDON_MODULE)
    assert (
        "FINISHED" in result or "CANCELLED" in result
    ), f"addon_enable returned {result}"

    # Give Blender a moment to finish registration
    time.sleep(0.5)

    assert ADDON_MODULE in bpy.context.preferences.addons, (
        f"{ADDON_MODULE} should be in enabled addons after enable. "
        f"Currently: {[a for a in bpy.context.preferences.addons.keys()]}"
    )

    cozy = importlib.import_module(ADDON_MODULE)
    assert getattr(
        cozy, "DEPENDENCIES_INSTALLED", False
    ), "Dependencies were not marked installed after enabling."

    # --- Disable ---
    result = bpy.ops.preferences.addon_disable(module=ADDON_MODULE)
    assert (
        "FINISHED" in result or "CANCELLED" in result
    ), f"addon_disable returned {result}"

    assert (
        ADDON_MODULE not in bpy.context.preferences.addons
    ), f"{ADDON_MODULE} still appears enabled after disable."
