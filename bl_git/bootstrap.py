import os
from pathlib import Path

import bpy

from .constants import MANIFEST_BOOTSTRAP_KEY


class BootstrapMixin:
    def _bootstrap_name(self):
        if self.manifest is not None:
            bootstrap_name = self.manifest.get(MANIFEST_BOOTSTRAP_KEY)
            if isinstance(bootstrap_name, str) and bootstrap_name.endswith(".blend"):
                return bootstrap_name

        blend_path = bpy.data.filepath
        if blend_path:
            try:
                blend_path = Path(blend_path)
                if blend_path.parent.resolve() == self.path:
                    return blend_path.name
            except Exception:
                pass

        return f"{self.path.name}.blend"

    def _bootstrap_path(self):
        return self.path / self._bootstrap_name()

    def _ensure_bootstrap_file(self):
        bootstrap_path = self._bootstrap_path()
        if bootstrap_path.exists():
            return
        try:
            bpy.ops.wm.save_as_mainfile(filepath=str(bootstrap_path), copy=True)
        except Exception as e:
            print(f"[BpyGit] Failed to write bootstrap .blend: {e}")

    def _stage_manifest_file(self):
        if not self.repo:
            return

        try:
            if self.manifestpath.exists():
                manifest_rel = os.path.relpath(self.manifestpath, self.path)
                self.repo.index.add([manifest_rel])
        except Exception as e:
            print(f"[BpyGit] Failed to stage manifest.json: {e}")
