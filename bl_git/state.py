from collections import defaultdict, deque
from pathlib import Path

import bpy
from deepdiff import DeepHash

from .constants import MANIFEST_BLOCKS_KEY, MANIFEST_GROUP_KEY
from .json_io import serialize_json_data


class StateMixin:
    def _empty_ui_state(self):
        return {
            "repo": {
                "available": bool(getattr(self, "repo", None)),
                "initiated": bool(getattr(self, "initiated", False)),
                "path": str(getattr(self, "path", "") or ""),
                "has_manifest": isinstance(getattr(self, "manifest", None), dict),
            },
            "branch": {
                "current": None,
                "detached": False,
                "head_hash": None,
                "head_short_hash": None,
                "head_summary": None,
                "last_branch": getattr(self, "last_branch", None),
            },
            "snapshot": {
                "viewing_past": False,
                "return_branch": None,
            },
            "conflicts": {
                "has_conflicts": False,
                "items": [],
            },
            "integrity": {
                "ok": True,
                "errors": [],
                "warnings": [],
            },
            "changes": {
                "total": 0,
                "staged": 0,
                "unstaged": 0,
                "staged_groups": [],
                "unstaged_groups": [],
            },
            "history": {
                "items": [],
            },
            "capture": {
                "has_issues": False,
                "issues": [],
            },
        }

    def refresh_ui_state(self):
        ui_state = self._empty_ui_state()
        ui_state["repo"]["available"] = bool(self.repo)
        ui_state["repo"]["initiated"] = bool(self.initiated)
        ui_state["repo"]["path"] = str(self.path)
        ui_state["repo"]["has_manifest"] = isinstance(self.manifest, dict)
        ui_state["branch"]["last_branch"] = self.last_branch

        capture_issues = [dict(issue) for issue in (self.last_capture_issues or [])]
        ui_state["capture"]["issues"] = capture_issues
        ui_state["capture"]["has_issues"] = bool(capture_issues)

        integrity = self.last_integrity_report
        if integrity is None and self.manifest is not None and self.initiated:
            integrity = self.validate_manifest_integrity()
        if isinstance(integrity, dict):
            ui_state["integrity"] = {
                "ok": bool(integrity.get("ok", False)),
                "errors": list(integrity.get("errors", [])),
                "warnings": list(integrity.get("warnings", [])),
            }

        manifest_conflicts = None
        if isinstance(self.manifest, dict):
            manifest_conflicts = self.manifest.get("conflicts")
        if isinstance(manifest_conflicts, dict):
            ui_state["conflicts"]["items"] = [
                {"uuid": uuid, "reason": reason}
                for uuid, reason in sorted(manifest_conflicts.items())
            ]
        elif isinstance(manifest_conflicts, list):
            items = []
            for item in manifest_conflicts:
                if isinstance(item, dict):
                    items.append(dict(item))
                else:
                    items.append({"uuid": None, "reason": str(item)})
            ui_state["conflicts"]["items"] = items
        elif manifest_conflicts:
            ui_state["conflicts"]["items"] = [
                {"uuid": None, "reason": str(manifest_conflicts)}
            ]
        ui_state["conflicts"]["has_conflicts"] = bool(ui_state["conflicts"]["items"])

        if self.repo is not None:
            head_hash = None
            if self.repo.head.is_valid():
                try:
                    head_commit = self.repo.head.commit
                    head_hash = head_commit.hexsha
                    ui_state["branch"]["head_hash"] = head_hash
                    ui_state["branch"]["head_short_hash"] = head_hash[:8]
                    ui_state["branch"]["head_summary"] = (
                        head_commit.message.splitlines()[0]
                        if head_commit.message
                        else "(no message)"
                    )
                except Exception:
                    head_hash = None

            detached = False
            try:
                detached = self.repo.head.is_detached
            except Exception:
                detached = False
            ui_state["branch"]["detached"] = detached

            if detached:
                ui_state["snapshot"]["viewing_past"] = True
                return_branch = None
                if self.last_branch and self.last_branch in self.repo.heads:
                    return_branch = self.last_branch
                elif "main" in self.repo.heads:
                    return_branch = "main"
                elif "master" in self.repo.heads:
                    return_branch = "master"
                elif self.repo.heads:
                    return_branch = self.repo.heads[0].name
                ui_state["snapshot"]["return_branch"] = return_branch
            else:
                try:
                    ui_state["branch"]["current"] = self.repo.active_branch.name
                except Exception:
                    ui_state["branch"]["current"] = None

            try:
                commits = list(self.repo.iter_commits(all=True, max_count=10))
            except Exception:
                commits = []
            ui_state["history"]["items"] = [
                {
                    "commit_hash": commit.hexsha,
                    "short_hash": commit.hexsha[:8],
                    "summary": commit.message.splitlines()[0]
                    if commit.message
                    else "(no message)",
                    "is_head": commit.hexsha == head_hash,
                }
                for commit in commits
            ]

        diffs = list(self.diffs or [])
        staged = [diff for diff in diffs if diff.get("status", "").startswith("staged")]
        unstaged = [diff for diff in diffs if not diff.get("status", "").startswith("staged")]
        ui_state["changes"]["total"] = len(diffs)
        ui_state["changes"]["staged"] = len(staged)
        ui_state["changes"]["unstaged"] = len(unstaged)

        entries = (self.state or {}).get("entries", {})
        groups = (self.state or {}).get("groups", {})
        name_cache = {}
        if entries:
            for _type_name, impl_class in self.bpy_protocol.implementations.items():
                data_collection = getattr(bpy.data, impl_class.bl_id, None)
                if not data_collection:
                    continue
                for datablock in data_collection:
                    uuid = getattr(datablock, "cozystudio_uuid", None)
                    if not uuid or uuid not in entries or uuid in name_cache:
                        continue
                    name_cache[uuid] = getattr(datablock, "name", None) or uuid

        for section_name, section_diffs in (
            ("staged_groups", staged),
            ("unstaged_groups", unstaged),
        ):
            grouped = {}
            ungrouped = []

            for diff in section_diffs:
                path = diff.get("path", "")
                uuid = None
                if path.startswith(".cozystudio/blocks/") and path.endswith(".json"):
                    try:
                        uuid = Path(path).stem
                    except Exception:
                        uuid = None
                if not uuid or uuid not in entries:
                    entry_type = entries.get(uuid, {}).get("type") if uuid else None
                    ungrouped.append(
                        {
                            **diff,
                            "uuid": uuid,
                            "entry_type": entry_type,
                            "display_name": name_cache.get(uuid) or uuid or path,
                        }
                    )
                    continue

                group_id = entries[uuid].get(MANIFEST_GROUP_KEY) or uuid
                entry_type = entries[uuid].get("type")
                if group_id not in grouped:
                    group_meta = groups.get(group_id) or {}
                    group_type = group_meta.get("type", "group")
                    root_uuid = group_meta.get("root", group_id)
                    root_name = name_cache.get(root_uuid) or root_uuid or "Group"
                    if group_type == "object":
                        label = f"Object: {root_name}"
                    elif group_type == "shared":
                        label = f"Shared: {root_name}"
                    elif group_type == "orphan":
                        label = f"Orphan: {root_name}"
                    else:
                        label = f"Group: {root_name}"
                    grouped[group_id] = {
                        "group_id": group_id,
                        "label": label,
                        "group": group_meta,
                        "diffs": [],
                    }

                grouped[group_id]["diffs"].append(
                    {
                        **diff,
                        "uuid": uuid,
                        "entry_type": entry_type,
                        "display_name": (
                            f"{name_cache.get(uuid) or uuid or path} ({entry_type})"
                            if entry_type
                            else name_cache.get(uuid) or uuid or path
                        ),
                    }
                )

            section_groups = []
            for group_id, group_data in grouped.items():
                group_meta = group_data.get("group") or {}
                group_members = group_meta.get("members", [])
                member_total = len(group_members) if group_members else len(group_data["diffs"])
                label = group_data["label"]
                if member_total >= len(group_data["diffs"]):
                    label = f"{label} ({len(group_data['diffs'])}/{member_total})"
                else:
                    label = f"{label} ({len(group_data['diffs'])})"
                section_groups.append(
                    {
                        "group_id": group_id,
                        "label": label,
                        "diffs": sorted(
                            group_data["diffs"], key=lambda diff: diff.get("path", "")
                        ),
                    }
                )

            if ungrouped:
                section_groups.append(
                    {
                        "group_id": None,
                        "label": f"Ungrouped ({len(ungrouped)})",
                        "diffs": sorted(
                            ungrouped, key=lambda diff: diff.get("path", "")
                        ),
                    }
                )

            section_groups.sort(key=lambda group: group.get("label", ""))
            ui_state["changes"][section_name] = section_groups

        self.ui_state = ui_state
        return ui_state

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
