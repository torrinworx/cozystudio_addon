import json
import os
import traceback
from pathlib import Path

from .constants import (
    MANIFEST_BLOCKS_KEY,
    MANIFEST_BOOTSTRAP_KEY,
    MANIFEST_GROUP_KEY,
    MANIFEST_GROUPS_KEY,
    MANIFEST_VERSION,
    MANIFEST_VERSION_KEY,
)


class ManifestMixin:
    def _manifest(self, changes: list[str]):
        changes = [c for c in changes if c.startswith(".cozystudio/blocks/")]
        if not changes:
            return

        if self.manifest is None:
            return

        self._ensure_state()
        self._ensure_manifest_schema()

        entries = self.state.get("entries", {})
        groups = self.state.get("groups", {})
        manifest = self.manifest
        blocks = manifest.get(MANIFEST_BLOCKS_KEY, {})

        try:
            for rel_path in changes:
                block_path = Path(self.path, rel_path)
                block_uuid = block_path.stem

                if not block_path.exists():
                    if block_uuid in blocks:
                        del blocks[block_uuid]
                        print(
                            f"[BpyGit] Removed manifest entry for deleted block {block_uuid}"
                        )
                    continue

                current_entry = entries.get(block_uuid)
                if current_entry:
                    blocks[block_uuid] = {
                        "type": current_entry["type"],
                        "deps": current_entry.get("deps", []),
                        "hash": current_entry["hash"],
                        MANIFEST_GROUP_KEY: current_entry.get(MANIFEST_GROUP_KEY),
                    }
                    print(f"[BpyGit] Updated manifest entry: {block_uuid}")
                else:
                    print(f"[BpyGit] Warning: {block_uuid} not in current state")

            manifest[MANIFEST_GROUPS_KEY] = groups
            manifest.write()

            try:
                manifest_rel = os.path.relpath(self.manifestpath, self.path)
                self.repo.index.add([manifest_rel])
            except Exception as e:
                print(f"[BpyGit] Error staging updated manifest: {e}")

        except Exception:
            print("[BpyGit] Error updating manifest:")
            print(traceback.format_exc())

    def _ensure_manifest_schema(self):
        if self.manifest is None:
            return

        if (
            MANIFEST_VERSION_KEY in self.manifest
            and MANIFEST_BLOCKS_KEY in self.manifest
            and isinstance(self.manifest.get(MANIFEST_BLOCKS_KEY), dict)
            and MANIFEST_GROUPS_KEY in self.manifest
            and isinstance(self.manifest.get(MANIFEST_GROUPS_KEY), dict)
        ):
            if self.manifest.get(MANIFEST_VERSION_KEY) != MANIFEST_VERSION:
                self.manifest[MANIFEST_VERSION_KEY] = MANIFEST_VERSION
                self.manifest.write()
            if MANIFEST_BOOTSTRAP_KEY not in self.manifest:
                self.manifest[MANIFEST_BOOTSTRAP_KEY] = self._bootstrap_name()
                self.manifest.write()
            return

        self._ensure_state()
        rebuilt_blocks = {}
        for uuid, entry in (self.state or {}).get("entries", {}).items():
            rebuilt_blocks[uuid] = {
                "type": entry.get("type"),
                "deps": entry.get("deps", []),
                "hash": entry.get("hash"),
                MANIFEST_GROUP_KEY: entry.get(MANIFEST_GROUP_KEY),
            }

        self.manifest.clear()
        self.manifest[MANIFEST_VERSION_KEY] = MANIFEST_VERSION
        self.manifest[MANIFEST_BLOCKS_KEY] = rebuilt_blocks
        self.manifest[MANIFEST_GROUPS_KEY] = (self.state or {}).get("groups", {})
        self.manifest[MANIFEST_BOOTSTRAP_KEY] = self._bootstrap_name()
        self.manifest.write()

    def validate_manifest_integrity(self):
        report = {"ok": True, "errors": [], "warnings": []}
        if self.manifest is None:
            report["ok"] = False
            report["errors"].append("Manifest is not loaded.")
            return report

        if not isinstance(self.manifest, dict):
            report["ok"] = False
            report["errors"].append("Manifest is not a dictionary.")
            return report

        required_keys = [
            MANIFEST_VERSION_KEY,
            MANIFEST_BLOCKS_KEY,
            MANIFEST_GROUPS_KEY,
            MANIFEST_BOOTSTRAP_KEY,
        ]
        for key in required_keys:
            if key not in self.manifest:
                report["ok"] = False
                report["errors"].append(f"Manifest missing key: {key}")

        blocks = self.manifest.get(MANIFEST_BLOCKS_KEY)
        if not isinstance(blocks, dict):
            report["ok"] = False
            report["errors"].append("Manifest blocks field is not a dict.")
            blocks = {}

        if not self.blockspath.exists():
            report["ok"] = False
            report["errors"].append("Blocks directory does not exist.")
            return report

        block_files = {
            path.stem
            for path in self.blockspath.iterdir()
            if path.is_file() and path.name.endswith(".json")
        }

        for uuid in blocks.keys():
            if uuid not in block_files:
                report["ok"] = False
                report["errors"].append(f"Missing block file for {uuid}.")

        for uuid in block_files:
            if uuid not in blocks:
                report["warnings"].append(f"Block file not in manifest: {uuid}.")

        conflicts = self.manifest.get("conflicts")
        if conflicts:
            report["ok"] = False
            report["errors"].append("Unresolved conflicts present in manifest.")

        return report

    def _load_manifest_at(self, ref):
        if not ref:
            return self._empty_manifest()

        manifest_rel = os.path.relpath(self.manifestpath, self.path)
        try:
            raw = self.repo.git.show(f"{ref}:{manifest_rel}")
            data = json.loads(raw)
            if not isinstance(data, dict):
                return self._empty_manifest()
            return data
        except Exception:
            return self._empty_manifest()

    def _load_manifest_working(self):
        if not self.manifestpath.exists():
            return self._empty_manifest()
        try:
            with open(self.manifestpath, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                return self._empty_manifest()
            return data
        except Exception:
            return self._empty_manifest()

    def _empty_manifest(self):
        return {
            MANIFEST_VERSION_KEY: MANIFEST_VERSION,
            MANIFEST_BLOCKS_KEY: {},
            MANIFEST_GROUPS_KEY: {},
            MANIFEST_BOOTSTRAP_KEY: self._bootstrap_name(),
        }
