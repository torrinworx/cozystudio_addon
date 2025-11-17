import sys
import time
import importlib
import bpy
import pytest

ADDON_MODULE = "cozystudio_addon"


# dependency installation
@pytest.mark.order(1)
def test_dependencies_can_be_installed():
    """Verify that install_packages() completes and dependencies are importable."""
    cozy = importlib.import_module(ADDON_MODULE)

    # Parse requirements
    reqs = cozy.parse_requirements(cozy.REQUIREMENTS_PATH)
    assert isinstance(reqs, list)

    missing = cozy.check_dependencies()
    if not missing:
        # Already satisfied
        assert isinstance(cozy.DEPENDENCIES_INSTALLED, bool)
        return

    # Trigger installation synchronously
    cozy.install_packages()

    # Verify flags
    assert isinstance(cozy.MISSING_DEPENDENCIES, list)
    assert (
        len(cozy.MISSING_DEPENDENCIES) == 0
    ), f"Still missing after install: {cozy.MISSING_DEPENDENCIES}"
    assert cozy.DEPENDENCIES_INSTALLED, "Dependencies should report as installed"


# Enable add‑on  (leaves it enabled for subsequent tests)
@pytest.mark.order(2)
def test_addon_enable():
    """Enable the CozyStudio addon inside Blender preferences."""
    if ADDON_MODULE in sys.modules:
        del sys.modules[ADDON_MODULE]

    result = bpy.ops.preferences.addon_enable(module=ADDON_MODULE)
    assert (
        "FINISHED" in result or "CANCELLED" in result
    ), f"addon_enable returned {result}"

    # Give Blender time to register everything
    time.sleep(0.5)

    assert ADDON_MODULE in bpy.context.preferences.addons, (
        f"{ADDON_MODULE} should appear in enabled addons after enable. "
        f"Currently: {[a for a in bpy.context.preferences.addons.keys()]}"
    )

    cozy = importlib.import_module(ADDON_MODULE)
    assert getattr(
        cozy, "DEPENDENCIES_INSTALLED", False
    ), "Dependencies were not marked installed after enabling."


# Disable add‑on
@pytest.mark.order(-1)  # run at very end of whole session
def test_addon_disable():
    """Disable the CozyStudio addon after all other tests."""
    # only disable if currently enabled
    if ADDON_MODULE not in bpy.context.preferences.addons:
        pytest.skip("Addon is not currently enabled")

    result = bpy.ops.preferences.addon_disable(module=ADDON_MODULE)
    assert (
        "FINISHED" in result or "CANCELLED" in result
    ), f"addon_disable returned {result}"

    time.sleep(0.2)
    assert (
        ADDON_MODULE not in bpy.context.preferences.addons
    ), f"{ADDON_MODULE} still appears enabled after disable."
