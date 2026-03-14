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
from .json_io import normalize_json_data, serialize_json_data


class MergeMixin:
    def merge(self, ref, strategy="manual"):
        if not self.repo or not self.initiated:
            return {"ok": False, "errors": ["Repository not initialized."], "conflicts": []}
        if self._managed_carryover():
            return {
                "ok": False,
                "errors": ["Parked Cozy changes already exist. Restore them before continuing."],
                "conflicts": [],
            }
        parked = self._park_cozy_changes("merge", ref)
        if not parked.get("ok"):
            return {"ok": False, "errors": [parked["error"]], "conflicts": []}

        ours_ref = self.repo.head.commit.hexsha
        try:
            base_ref = self.repo.git.merge_base(ours_ref, ref).strip()
        except Exception:
            base_ref = None

        result = self._merge_refs(base_ref, ours_ref, ref, strategy=strategy)
        if parked.get("stashed"):
            if result.get("ok") and not result.get("conflicts"):
                carryover_result = self.reapply_parked_changes()
                result["carryover"] = carryover_result
                if not carryover_result.get("ok"):
                    result["warnings"] = [carryover_result["error"]]
            else:
                result["carryover"] = {"ok": False, "parked": True}
        return result

    def rebase(self, onto_ref, strategy="manual"):
        if not self.repo or not self.initiated:
            return {"ok": False, "errors": ["Repository not initialized."], "conflicts": []}
        if self._managed_carryover():
            return {
                "ok": False,
                "errors": ["Parked Cozy changes already exist. Restore them before continuing."],
                "conflicts": [],
            }
        parked = self._park_cozy_changes("rebase", onto_ref)
        if not parked.get("ok"):
            return {"ok": False, "errors": [parked["error"]], "conflicts": []}

        head_ref = self.repo.head.commit.hexsha
        commits = list(self.repo.iter_commits(f"{onto_ref}..{head_ref}", reverse=True))
        if not commits:
            result = {"ok": True, "errors": [], "conflicts": []}
            if parked.get("stashed"):
                carryover_result = self.reapply_parked_changes()
                result["carryover"] = carryover_result
                if not carryover_result.get("ok"):
                    result["warnings"] = [carryover_result["error"]]
            return result

        try:
            self.restore_ref(onto_ref, park_changes=False)
        except Exception as e:
            return {"ok": False, "errors": [f"Failed to checkout {onto_ref}: {e}"], "conflicts": []}

        for commit in commits:
            parent = commit.parents[0].hexsha if commit.parents else None
            result = self._merge_refs(parent, "WORKING_TREE", commit.hexsha, strategy=strategy)
            if not result.get("ok"):
                result["failed_commit"] = commit.hexsha
                if parked.get("stashed"):
                    result["carryover"] = {"ok": False, "parked": True}
                return result

        result = {"ok": True, "errors": [], "conflicts": []}
        if parked.get("stashed"):
            carryover_result = self.reapply_parked_changes()
            result["carryover"] = carryover_result
            if not carryover_result.get("ok"):
                result["warnings"] = [carryover_result["error"]]
        return result

    def _merge_refs(self, base_ref, ours_ref, theirs_ref, strategy="manual"):
        conflicts = []
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
                    conflicts.append(
                        {
                            "uuid": uuid,
                            "reason": result["reason"],
                            "label": (
                                (ours_data or {}).get("name")
                                or (theirs_data or {}).get("name")
                                or uuid
                            ),
                            "datablock_type": (
                                (ours_blocks.get(uuid) or {}).get("type")
                                or (theirs_blocks.get(uuid) or {}).get("type")
                            ),
                            "operation": "rebase" if ours_ref == "WORKING_TREE" else "merge",
                            "base_ref": self._conflict_ref_value(base_ref),
                            "ours_ref": self._conflict_ref_value(ours_ref),
                            "theirs_ref": self._conflict_ref_value(theirs_ref),
                            "ours_entry": normalize_json_data(ours_blocks.get(uuid)),
                            "theirs_entry": normalize_json_data(theirs_blocks.get(uuid)),
                            "ours_data": (
                                normalize_json_data(ours_data) if ours_ref == "WORKING_TREE" else None
                            ),
                            "theirs_data": None,
                        }
                    )
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

            recorded_conflicts = conflicts if strategy == "manual" else []
            if recorded_conflicts:
                merged_manifest["conflicts"] = recorded_conflicts
            elif "conflicts" in merged_manifest:
                del merged_manifest["conflicts"]

            self.manifest = WriteDict(self.manifestpath)
            self.manifest.clear()
            self.manifest.update(merged_manifest)
            self.manifest.write()

            self.restore_ref()
            self._update_diffs()
            redraw("COZYSTUDIO_PT_changes")
            redraw("COZYSTUDIO_PT_history")
        except Exception as e:
            errors.append(str(e))
        finally:
            self.suspend_checks = False

        returned_conflicts = conflicts if strategy == "manual" else []
        ok = not errors and (not returned_conflicts or strategy in ("ours", "theirs"))
        return {"ok": ok, "errors": errors, "conflicts": returned_conflicts}

    def _conflict_ref_value(self, ref):
        if ref in {None, "WORKING_TREE"}:
            return ref
        try:
            return self.repo.commit(ref).hexsha
        except Exception:
            return ref

    def _conflict_side_data(self, conflict, side):
        data_key = f"{side}_data"
        if conflict.get(data_key) is not None:
            return conflict.get(data_key)
        return self._load_block_data(conflict.get(f"{side}_ref"), conflict.get("uuid"))

    def resolve_conflict(self, conflict_uuid, resolution="manual"):
        if not isinstance(self.manifest, dict):
            return {"ok": False, "error": "No manifest is loaded."}

        conflicts = self._manifest_conflict_items()
        if not conflicts:
            return {"ok": False, "error": "No conflicts to resolve."}

        if not conflict_uuid:
            return {"ok": False, "error": "A conflict UUID is required."}

        conflict = None
        remaining = []
        for item in conflicts:
            if item.get("uuid") == conflict_uuid and conflict is None:
                conflict = item
                continue
            remaining.append(item)

        if conflict is None:
            return {"ok": False, "error": "Conflict entry was not found."}

        if resolution in {"ours", "theirs"}:
            entry = conflict.get(f"{resolution}_entry")
            data = self._conflict_side_data(conflict, resolution)
            manifest_blocks = self.manifest.get(MANIFEST_BLOCKS_KEY, {})
            if entry:
                manifest_blocks[conflict_uuid] = dict(entry)
            elif conflict_uuid in manifest_blocks:
                del manifest_blocks[conflict_uuid]

            if data is None:
                self._delete_block_file(conflict_uuid)
            else:
                self._write_block_file(conflict_uuid, serialize_json_data(data))

            self.manifest[MANIFEST_BLOCKS_KEY] = manifest_blocks

        self._set_manifest_conflicts(remaining)
        self.manifest.write()
        self.restore_ref(park_changes=False)
        self.refresh_ui_state()
        return {
            "ok": True,
            "resolution": resolution,
            "remaining": len(remaining),
            "conflict": conflict,
        }

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

    def _cozy_dirty_paths(self, dirty_paths):
        cozy_paths = set()
        for path in dirty_paths or set():
            if path in {".cozystudio/manifest", ".cozystudio/manifest.json"}:
                cozy_paths.add(path)
                continue
            if path.startswith(".cozystudio/blocks/"):
                cozy_paths.add(path)
        return cozy_paths

    def _blocking_dirty_paths(self, dirty_paths):
        allowed_patterns = ["*.blend", "*.blend1"]
        cozy_paths = self._cozy_dirty_paths(dirty_paths)
        blocking = set()
        for path in dirty_paths or set():
            if path in cozy_paths:
                continue
            if any(fnmatch(path, pattern) for pattern in allowed_patterns):
                continue
            blocking.add(path)
        return blocking

    def _is_merge_safe_dirty(self, dirty_paths):
        return not self._blocking_dirty_paths(dirty_paths)
