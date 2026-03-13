from collections import defaultdict, deque
from pathlib import Path

import bpy
from deepdiff import DeepHash

from .constants import MANIFEST_BLOCKS_KEY, MANIFEST_GROUP_KEY
from .json_io import serialize_json_data


class StateMixin:
    def _current_state(self, interactive=False):
        entries = {}
        blocks = {}
        db_by_uuid = {}
        issues = []
        previous_entries = (self.state or {}).get("entries", {})
        previous_blocks = (self.state or {}).get("blocks", {})

        for type_name, impl_class in self.bpy_protocol.implementations.items():
            if not hasattr(bpy.data, impl_class.bl_id):
                continue
            data_collection = getattr(bpy.data, impl_class.bl_id)
            if not isinstance(data_collection, bpy.types.bpy_prop_collection):
                continue

            for db in data_collection:
                if hasattr(db, "users") and db.users == 0:
                    continue
                cozystudio_uuid = getattr(db, "cozystudio_uuid", None)
                if not cozystudio_uuid:
                    continue

                captured = self.bpy_protocol.capture(
                    db,
                    stamp_uuid=cozystudio_uuid,
                    interactive=interactive,
                )
                if captured["status"] != "ok":
                    issue = dict(captured)
                    issue["uuid"] = cozystudio_uuid
                    issue["name"] = getattr(db, "name", cozystudio_uuid)
                    issue["type"] = impl_class.bl_id
                    issues.append(issue)

                    if not interactive and cozystudio_uuid in previous_entries and cozystudio_uuid in previous_blocks:
                        entries[cozystudio_uuid] = previous_entries[cozystudio_uuid]
                        blocks[cozystudio_uuid] = previous_blocks[cozystudio_uuid]
                        db_by_uuid[cozystudio_uuid] = db
                    continue

                deps = []
                for dep in captured["deps"] or []:
                    normalized = self._normalize_dep(dep)
                    if normalized is None or normalized == cozystudio_uuid or normalized in deps:
                        continue
                    deps.append(normalized)

                target = serialize_json_data(captured["data"])
                hash_value = DeepHash(target)
                entries[cozystudio_uuid] = {
                    "type": impl_class.bl_id,
                    "deps": deps,
                    "hash": hash_value[target],
                    MANIFEST_GROUP_KEY: None,
                }
                blocks[cozystudio_uuid] = target
                db_by_uuid[cozystudio_uuid] = db

        groups, group_ids = self._resolve_groups(entries, db_by_uuid)
        for uuid, group_id in group_ids.items():
            if uuid in entries:
                entries[uuid][MANIFEST_GROUP_KEY] = group_id

        return entries, blocks, groups, issues

    def _ensure_state(self):
        if self.state is None:
            entries, blocks, groups, issues = self._current_state()
            self.state = {
                "entries": entries or {},
                "blocks": blocks or {},
                "groups": groups or {},
            }
            self.last_capture_issues = issues

    def _is_shared_block(self, uuid, entries, db_by_uuid) -> bool:
        entry = entries.get(uuid)
        if not entry:
            return False
        if entry.get("type") == "objects":
            return False
        datablock = db_by_uuid.get(uuid)
        if datablock is None:
            return False
        if not hasattr(datablock, "users"):
            return False
        try:
            return datablock.users > 1
        except Exception:
            return False

    def _resolve_groups(self, entries, db_by_uuid):
        deps_map = {}
        for uuid, entry in entries.items():
            deps_map[uuid] = set(self._extract_dep_uuids(entry.get("deps", [])))

        shared = {
            uuid
            for uuid in entries
            if self._is_shared_block(uuid, entries, db_by_uuid)
        }

        groups = {}
        group_ids = {}

        def traverse_group(root_uuid, group_type):
            if root_uuid not in groups:
                groups[root_uuid] = {
                    "type": group_type,
                    "root": root_uuid,
                    "members": [],
                }
            queue = deque([root_uuid])
            while queue:
                current = queue.popleft()
                if current in group_ids:
                    continue
                group_ids[current] = root_uuid
                groups[root_uuid]["members"].append(current)
                for dep in sorted(deps_map.get(current, [])):
                    if dep not in entries:
                        continue
                    if dep in group_ids:
                        continue
                    if dep in shared and dep != root_uuid:
                        continue
                    queue.append(dep)

        object_roots = sorted(
            [uuid for uuid, entry in entries.items() if entry.get("type") == "objects"]
        )
        for root_uuid in object_roots:
            traverse_group(root_uuid, "object")

        shared_roots = sorted([uuid for uuid in shared if uuid not in group_ids])
        for root_uuid in shared_roots:
            traverse_group(root_uuid, "shared")

        for uuid in sorted(entries.keys()):
            if uuid in group_ids:
                continue
            traverse_group(uuid, "orphan")

        for group in groups.values():
            group["members"].sort()

        return groups, group_ids

    def _normalize_path_dep(self, path_value: Path) -> str:
        try:
            if path_value.is_absolute():
                try:
                    return path_value.relative_to(self.path).as_posix()
                except ValueError:
                    return path_value.as_posix()
            return path_value.as_posix()
        except Exception:
            return str(path_value)

    def _normalize_dep(self, dep):
        if isinstance(dep, Path):
            return {"file": self._normalize_path_dep(dep)}
        if hasattr(dep, "cozystudio_uuid"):
            dep_uuid = getattr(dep, "cozystudio_uuid", None)
            if dep_uuid:
                return dep_uuid
        if isinstance(dep, str) and dep:
            return dep
        return None

    def _extract_dep_uuids(self, deps) -> list[str]:
        uuids = []
        for dep in deps or []:
            if isinstance(dep, str):
                uuids.append(dep)
            elif isinstance(dep, dict):
                dep_uuid = dep.get("uuid")
                if dep_uuid:
                    uuids.append(dep_uuid)
        return uuids

    def _cleanup_orphans(self, valid=None):
        if valid is None:
            manifest_blocks = {}
            if self.manifest is not None and isinstance(self.manifest, dict):
                manifest_blocks = self.manifest.get(MANIFEST_BLOCKS_KEY, {})
            valid = set(manifest_blocks.keys())

        for type_name, impl_class in self.bpy_protocol.implementations.items():
            data_collection = getattr(bpy.data, impl_class.bl_id, None)
            if not data_collection:
                continue
            to_remove = []
            for block in list(data_collection):
                block_uuid = getattr(block, "cozystudio_uuid", None)
                if block_uuid and block_uuid not in valid:
                    to_remove.append(block)

            to_remove.sort(
                key=lambda block: (
                    getattr(block, "cozystudio_uuid", ""),
                    getattr(block, "name", ""),
                )
            )

            for block in to_remove:
                try:
                    data_collection.remove(block, do_unlink=True)
                except TypeError:
                    try:
                        data_collection.remove(block)
                    except Exception as e:
                        print(
                            f"[BpyGit] Failed to remove orphan {block}: {e}"
                        )
                except Exception as e:
                    print(f"[BpyGit] Failed to remove orphan {block}: {e}")
