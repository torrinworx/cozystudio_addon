from fnmatch import fnmatch

from deepdiff import DeepHash

from ..utils.redraw import redraw
from ..utils.write import WriteDict
from .constants import (
    MANIFEST_BLOCKS_KEY,
    MANIFEST_BOOTSTRAP_KEY,
    MANIFEST_GROUP_KEY,
    MANIFEST_GROUPS_KEY,
    MANIFEST_VERSION,
    MANIFEST_VERSION_KEY,
)
from .json_io import serialize_json_data


class MergeMixin:
    def merge(self, ref, strategy="manual"):
        if not self.repo or not self.initiated:
            return {"ok": False, "errors": ["Repository not initialized."], "conflicts": {}}
        dirty_paths = self._dirty_paths()
        if dirty_paths and not self._is_merge_safe_dirty(dirty_paths):
            return {"ok": False, "errors": ["Working tree is dirty."], "conflicts": {}}

        ours_ref = self.repo.head.commit.hexsha
        try:
            base_ref = self.repo.git.merge_base(ours_ref, ref).strip()
        except Exception:
            base_ref = None

        result = self._merge_refs(base_ref, ours_ref, ref, strategy=strategy)
        return result

    def rebase(self, onto_ref, strategy="manual"):
        if not self.repo or not self.initiated:
            return {"ok": False, "errors": ["Repository not initialized."], "conflicts": {}}
        dirty_paths = self._dirty_paths()
        if dirty_paths and not self._is_merge_safe_dirty(dirty_paths):
            return {"ok": False, "errors": ["Working tree is dirty."], "conflicts": {}}

        head_ref = self.repo.head.commit.hexsha
        commits = list(self.repo.iter_commits(f"{onto_ref}..{head_ref}", reverse=True))
        if not commits:
            return {"ok": True, "errors": [], "conflicts": {}}

        try:
            self.repo.git.checkout(onto_ref)
        except Exception as e:
            return {"ok": False, "errors": [f"Failed to checkout {onto_ref}: {e}"], "conflicts": {}}

        for commit in commits:
            parent = commit.parents[0].hexsha if commit.parents else None
            result = self._merge_refs(parent, "WORKING_TREE", commit.hexsha, strategy=strategy)
            if not result.get("ok"):
                result["failed_commit"] = commit.hexsha
                return result

        return {"ok": True, "errors": [], "conflicts": {}}

    def _merge_refs(self, base_ref, ours_ref, theirs_ref, strategy="manual"):
        conflicts = {}
        errors = []

        base_manifest = self._load_manifest_at(base_ref) if base_ref else self._empty_manifest()
        if ours_ref == "WORKING_TREE":
            ours_manifest = self._load_manifest_working()
        else:
            ours_manifest = self._load_manifest_at(ours_ref)
        theirs_manifest = self._load_manifest_at(theirs_ref)

        base_blocks = base_manifest.get(MANIFEST_BLOCKS_KEY, {})
        ours_blocks = ours_manifest.get(MANIFEST_BLOCKS_KEY, {})
        theirs_blocks = theirs_manifest.get(MANIFEST_BLOCKS_KEY, {})

        uuids = sorted(set(base_blocks.keys()) | set(ours_blocks.keys()) | set(theirs_blocks.keys()))
        merged_blocks = {}

        self.suspend_checks = True
        try:
            for uuid in uuids:
                base_data = self._load_block_data(base_ref, uuid) if base_ref else None
                ours_data = self._load_block_data(ours_ref, uuid)
                theirs_data = self._load_block_data(theirs_ref, uuid)

                tier = self._merge_tier_for_uuid(uuid, ours_blocks, theirs_blocks)
                result = self._merge_block_data(base_data, ours_data, theirs_data, tier, strategy)

                if result["conflict"]:
                    conflicts[uuid] = result["reason"]
                    if strategy == "ours":
                        merged = ours_data
                    elif strategy == "theirs":
                        merged = theirs_data
                    else:
                        merged = ours_data
                else:
                    merged = result["data"]

                if merged is not None:
                    merged_blocks[uuid] = merged

            self._write_merged_blocks(merged_blocks)
            merged_manifest = self._merge_manifest_metadata(ours_manifest, theirs_manifest, merged_blocks)

            if conflicts:
                merged_manifest["conflicts"] = conflicts
            elif "conflicts" in merged_manifest:
                del merged_manifest["conflicts"]

            self.manifest = WriteDict(self.manifestpath)
            self.manifest.clear()
            self.manifest.update(merged_manifest)
            self.manifest.write()

            self._restore_from_manifest()
            self._update_diffs()
            redraw("COZYSTUDIO_PT_panel")
            redraw("COZYSTUDIO_PT_log")
        except Exception as e:
            errors.append(str(e))
        finally:
            self.suspend_checks = False

        ok = not errors and (not conflicts or strategy in ("ours", "theirs"))
        return {"ok": ok, "errors": errors, "conflicts": conflicts}

    def _merge_tier_for_uuid(self, uuid, ours_blocks, theirs_blocks):
        ours_entry = ours_blocks.get(uuid, {})
        theirs_entry = theirs_blocks.get(uuid, {})
        block_type = ours_entry.get("type") or theirs_entry.get("type")

        tier_a = {"objects", "meshes", "collections"}
        tier_b = {"materials", "images", "lights", "cameras", "scenes"}

        if block_type in tier_a:
            return "A"
        if block_type in tier_b:
            return "B"
        return "C"

    def _merge_block_data(self, base_data, ours_data, theirs_data, tier, strategy):
        if ours_data == theirs_data:
            return {"data": ours_data, "conflict": False}

        if base_data is None:
            if ours_data is None:
                return {"data": theirs_data, "conflict": False}
            if theirs_data is None:
                return {"data": ours_data, "conflict": False}
            return {"data": None, "conflict": True, "reason": "Both added different data."}

        if ours_data == base_data:
            return {"data": theirs_data, "conflict": False}
        if theirs_data == base_data:
            return {"data": ours_data, "conflict": False}

        if tier == "A":
            merged, conflict = self._three_way_merge_json(base_data, ours_data, theirs_data)
            if conflict:
                return {"data": None, "conflict": True, "reason": "Tier A merge conflict."}
            return {"data": merged, "conflict": False}

        if tier == "B":
            return {"data": None, "conflict": True, "reason": "Tier B overlap conflict."}

        return {"data": None, "conflict": True, "reason": "Tier C conflict."}

    def _three_way_merge_json(self, base, ours, theirs):
        if not isinstance(base, dict) or not isinstance(ours, dict) or not isinstance(theirs, dict):
            if ours == theirs:
                return ours, False
            return None, True

        merged = {}
        conflict = False
        keys = set(base.keys()) | set(ours.keys()) | set(theirs.keys())
        for key in sorted(keys):
            base_val = base.get(key)
            ours_val = ours.get(key)
            theirs_val = theirs.get(key)

            if ours_val == theirs_val:
                merged[key] = ours_val
                continue
            if ours_val == base_val:
                merged[key] = theirs_val
                continue
            if theirs_val == base_val:
                merged[key] = ours_val
                continue

            if isinstance(base_val, dict) and isinstance(ours_val, dict) and isinstance(theirs_val, dict):
                child, child_conflict = self._three_way_merge_json(base_val, ours_val, theirs_val)
                if child_conflict:
                    conflict = True
                    continue
                merged[key] = child
                continue

            conflict = True

        if conflict:
            return None, True
        return merged, False

    def _merge_manifest_metadata(self, ours_manifest, theirs_manifest, merged_blocks):
        ours_blocks = ours_manifest.get(MANIFEST_BLOCKS_KEY, {})
        theirs_blocks = theirs_manifest.get(MANIFEST_BLOCKS_KEY, {})

        merged_manifest = {
            MANIFEST_VERSION_KEY: MANIFEST_VERSION,
            MANIFEST_BLOCKS_KEY: {},
            MANIFEST_GROUPS_KEY: ours_manifest.get(MANIFEST_GROUPS_KEY, {}),
            MANIFEST_BOOTSTRAP_KEY: ours_manifest.get(MANIFEST_BOOTSTRAP_KEY, self._bootstrap_name()),
        }

        for uuid, data in merged_blocks.items():
            entry = ours_blocks.get(uuid) or theirs_blocks.get(uuid)
            if not entry:
                continue

            serialized = serialize_json_data(data)
            hash_value = DeepHash(serialized)[serialized]
            merged_manifest[MANIFEST_BLOCKS_KEY][uuid] = {
                "type": entry.get("type"),
                "deps": entry.get("deps", []),
                "hash": hash_value,
                MANIFEST_GROUP_KEY: entry.get(MANIFEST_GROUP_KEY),
            }

        return merged_manifest

    def _dirty_paths(self):
        if not self.repo:
            return set()

        dirty = set()
        for diff in self.repo.index.diff(None):
            dirty.add(diff.b_path or diff.a_path)
        for path in self.repo.untracked_files:
            dirty.add(path)
        return {p for p in dirty if p}

    def _is_merge_safe_dirty(self, dirty_paths):
        allowed_patterns = [
            ".cozystudio/blocks/*",
            ".cozystudio/manifest.json",
            ".cozystudio/manifest",
            "*.blend",
            "*.blend1",
        ]

        for path in dirty_paths:
            if any(fnmatch(path, pattern) for pattern in allowed_patterns):
                continue
            if path.startswith(".cozystudio/blocks/"):
                continue
            return False

        return True
