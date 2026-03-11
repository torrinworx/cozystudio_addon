import importlib

import bpy
import pytest

from ..helpers import ensure_install_operator, wait_for_install_finished

ADDON_MODULE = "cozystudio_addon"


@pytest.mark.order(2)
@pytest.mark.install
def test_install_deps_operator():
    if ADDON_MODULE not in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_enable(module=ADDON_MODULE)

    cozy = importlib.import_module(ADDON_MODULE)
    ensure_install_operator(cozy)

    cozy.MISSING_DEPENDENCIES[:] = cozy.check_dependencies()

    assert hasattr(bpy.ops.cozystudio, "install_deps")
    result = bpy.ops.cozystudio.install_deps("EXEC_DEFAULT")
    assert "RUNNING_MODAL" in result or "FINISHED" in result, \
        f"install_deps returned {result}"

    completed = wait_for_install_finished(cozy, timeout=300.0)
    assert completed, "Dependency install did not complete in time"

    assert cozy.DEPENDENCIES_INSTALLED, "Dependencies should report as installed"
    assert not cozy.MISSING_DEPENDENCIES, \
        f"Still missing after install: {cozy.MISSING_DEPENDENCIES}"
    assert cozy.auto_load_was_registered
