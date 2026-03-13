"""
Git system for blender files based on blender's internal data blocks.
"""

import traceback
from pathlib import Path

import bpy
from git import InvalidGitRepositoryError, NoSuchPathError, Repo

from .. import bl_types
from ..utils.timers import timers
from ..utils.write import WriteDict
from .bootstrap import BootstrapMixin
from .blocks import BlocksMixin
from .checkout import CheckoutMixin
from .constants import (
    MANIFEST_BLOCKS_KEY,
    MANIFEST_BOOTSTRAP_KEY,
    MANIFEST_GROUP_KEY,
    MANIFEST_GROUPS_KEY,
    MANIFEST_VERSION,
    MANIFEST_VERSION_KEY,
)
from .diffs import DiffsMixin
from .json_io import (
    default_json_decoder,
    default_json_encoder,
    normalize_json_data,
    serialize_json_data,
)
from .manifest import ManifestMixin
from .merge import MergeMixin
from .ops import OpsMixin
from .state import StateMixin
from .tracking import Track


class BpyGit(
    OpsMixin,
    DiffsMixin,
    StateMixin,
    BlocksMixin,
    ManifestMixin,
    CheckoutMixin,
    MergeMixin,
    BootstrapMixin,
):
    def __init__(self, check_interval=1.0):
        self.bpy_protocol = bl_types.get_data_translation_protocol()
        Track(self.bpy_protocol).start()

        self.path = Path(bpy.path.abspath("//")).resolve()
        self.cozystudio_path = self.path / ".cozystudio"
        self.blockspath = self.cozystudio_path / "blocks"
        self.manifestpath = self.cozystudio_path / "manifest.json"

        self.repo = None
        self.manifest = None
        self.initiated = False
        self.diffs = None
        self.state = None
        self.last_branch = None
        self.suspend_checks = False
        self.last_integrity_report = None
        self.last_capture_issues = []
        self.ui_state = self._empty_ui_state()

        self.check_interval = check_interval

        if str(self.path) == "" or not self.path.exists():
            self.refresh_ui_state()
            return

        git_dir = self.path / ".git"
        if not git_dir.exists():
            self.repo = None
            self.initiated = False
            self.refresh_ui_state()
            return

        try:
            self.repo = Repo(self.path, search_parent_directories=False)
            if self.repo.bare:
                self.repo = None
            elif Path(self.repo.working_tree_dir).resolve() != self.path:
                self.repo = None
            else:
                self.initiated = False
        except (InvalidGitRepositoryError, NoSuchPathError):
            self.repo = None
            self.initiated = False
            self.refresh_ui_state()
            return
        except Exception as e:
            print(f"[BpyGit] Unexpected error while initializing git: {e}")
            print(traceback.format_exc())
            self.repo = None
            self.initiated = False
            self.refresh_ui_state()
            return

        try:
            if self.manifestpath.exists():
                self.initiated = True
                self.restore_ref()
                self._ensure_bootstrap_file()
                timers.register(self._check)
        except Exception as e:
            print(f"[BpyGit] Error loading manifest: {e}")
            print(traceback.format_exc())
            self.manifest = None

        self.refresh_ui_state()


__all__ = [
    "BpyGit",
    "default_json_decoder",
    "default_json_encoder",
    "normalize_json_data",
    "serialize_json_data",
    "MANIFEST_BLOCKS_KEY",
    "MANIFEST_BOOTSTRAP_KEY",
    "MANIFEST_GROUP_KEY",
    "MANIFEST_GROUPS_KEY",
    "MANIFEST_VERSION",
    "MANIFEST_VERSION_KEY",
]
