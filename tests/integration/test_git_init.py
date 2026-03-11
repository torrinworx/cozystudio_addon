import importlib

import pytest

from ..helpers import init_git_repo_for_test

ADDON_MODULE = "cozystudio_addon"


@pytest.mark.order(4)
def test_initialize_git_repository():
    ui_mod = importlib.import_module(f"{ADDON_MODULE}.ui")
    git_inst = init_git_repo_for_test(ui_mod)
    assert git_inst is not None
