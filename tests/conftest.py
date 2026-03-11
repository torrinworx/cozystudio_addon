import importlib
from pathlib import Path

import pytest
import bpy

from .helpers import enable_addon, init_git_repo_for_test


ADDON_MODULE = "cozystudio_addon"


@pytest.fixture(scope="session")
def addon_enabled():
    enable_addon(ADDON_MODULE)
    return importlib.import_module(ADDON_MODULE)


@pytest.fixture(scope="session")
def ui_module():
    return importlib.import_module(f"{ADDON_MODULE}.ui")


@pytest.fixture(scope="session")
def git_repo(addon_enabled, ui_module):
    return init_git_repo_for_test(ui_module)
