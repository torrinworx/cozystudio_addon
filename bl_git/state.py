import json
from collections import defaultdict, deque
from pathlib import Path

import bpy
from deepdiff import DeepHash

from .constants import MANIFEST_BLOCKS_KEY, MANIFEST_GROUP_KEY, MANIFEST_GROUPS_KEY
from .json_io import serialize_json_data


class StateMixin:
    TYPE_LABELS = {
        "objects": "object",
        "meshes": "mesh",
        "collections": "collection",
        "materials": "material",
        "actions": "animation",
        "images": "image",
        "cameras": "camera",
        "lights": "light",
        "worlds": "world",
        "scenes": "scene",
        "node_groups": "node group",
        "textures": "texture",
        "curves": "curve",
        "fonts": "font",
        "armatures": "armature",
        "metaballs": "metaball",
        "lightprobes": "light probe",
        "volumes": "volume",
        "speakers": "speaker",
        "sounds": "sound",
        "particles": "particle settings",
        "grease_pencils": "grease pencil",
        "grease_pencil": "grease pencil",
    }

    def _empty_ui_state(self):
        return {
            "repo": {
                "available": bool(getattr(self, "repo", None)),
                "initiated": bool(getattr(self, "initiated", False)),
                "path": str(getattr(self, "path", "") or ""),
                "has_manifest": isinstance(getattr(self, "manifest", None), dict),
                "tracked_blocks": 0,
                "tracked_groups": 0,
            },
            "branch": {
                "current": None,
                "current_ref": None,
                "current_ref_type": None,
                "detached": False,
                "head_hash": None,
                "head_short_hash": None,
                "head_summary": None,
                "last_branch": getattr(self, "last_branch", None),
                "available": [],
                "local": [],
                "remote": [],
                "recent": [],
                "upstream": None,
                "ahead": 0,
                "behind": 0,
            },
            "commit": {
                "viewing_past": False,
                "return_branch": None,
                "can_commit": False,
                "blockers": [],
            },
            "conflicts": {
                "has_conflicts": False,
                "items": [],
                "count": 0,
                "operation": None,
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
                "count": 0,
            },
            "capture": {
                "has_issues": False,
                "issues": [],
                "count": 0,
            },
            "carryover": {
                "has_parked": False,
                "stash_ref": None,
                "operation": None,
                "source": None,
                "target": None,
                "error": None,
            },
            "workflow": {
                "state": "idle",
                "summary": None,
                "detail": None,
                "dirty_cozy": 0,
                "dirty_non_cozy": 0,
                "has_conflicts": False,
                "can_switch": True,
                "can_create": True,
                "can_merge": True,
                "can_rebase": True,
                "can_fetch": True,
                "blockers": [],
            },
        }

    @staticmethod
    def _ref_ui_row(name, ref_type="local", is_current=False, upstream=None):
        label = name
        if ref_type == "remote":
            label = f"{name} [remote]"
        elif is_current:
            label = f"{name} [current]"
        description = name if ref_type == "local" else f"Remote branch {name}"
        if upstream:
            description = f"{description} tracking {upstream}"
        return {
            "name": name,
            "type": ref_type,
            "label": label,
            "description": description,
            "is_current": is_current,
            "upstream": upstream,
        }

    def _recent_branch_names(self):
        if not self.repo:
            return []
        recent = []
        seen = set()
        current = None
        try:
            if not self.repo.head.is_detached:
                current = self.repo.active_branch.name
        except Exception:
            current = None

        candidates = [getattr(self, "last_branch", None)]
        try:
            reflog_lines = self.repo.git.reflog("--format=%gs").splitlines()
        except Exception:
            reflog_lines = []

        for line in reflog_lines:
            if not line.startswith("checkout: moving from "):
                continue
            target = line.split(" to ")[-1].strip()
            if target:
                candidates.append(target)

        local_names = {head.name for head in self.repo.heads}
        for name in candidates:
            if not name or name == current or name not in local_names or name in seen:
                continue
            seen.add(name)
            recent.append(name)
            if len(recent) >= 5:
                break
        return recent

    def _ahead_behind_counts(self, current_branch_name, upstream_name):
        if not self.repo or not current_branch_name or not upstream_name:
            return 0, 0
        try:
            counts = self.repo.git.rev_list(
                "--left-right",
                "--count",
                f"{current_branch_name}...{upstream_name}",
            ).strip()
            ahead, behind = counts.split()
            return int(ahead), int(behind)
        except Exception:
            return 0, 0

    def _workflow_blockers(self, ui_state, dirty_paths, cozy_paths, blocking_paths):
        blockers = []
        workflow = ui_state["workflow"]
        branch_ui = ui_state["branch"]
        carryover_ui = ui_state["carryover"]
        conflicts_ui = ui_state["conflicts"]

        workflow["dirty_cozy"] = len(cozy_paths)
        workflow["dirty_non_cozy"] = len(blocking_paths)
        workflow["has_conflicts"] = conflicts_ui.get("has_conflicts", False)

        if carryover_ui.get("has_parked"):
            blockers.append("Restore parked Cozy changes before switching, merging, or rebasing.")
            workflow["state"] = "parked"
            workflow["summary"] = "Parked changes pending"
            workflow["detail"] = "Restore or clear parked Cozy changes before other branch actions."
        elif conflicts_ui.get("has_conflicts"):
            operation = conflicts_ui.get("operation") or "merge"
            blockers.append(f"Resolve {operation} conflicts before more branch actions.")
            workflow["state"] = f"{operation}_conflicts"
            workflow["summary"] = f"{operation.title()} conflicts need resolution"
            workflow["detail"] = "Use the Conflicts panel to choose mine, theirs, or resolve manually."
        elif branch_ui.get("detached"):
            workflow["state"] = "detached"
            workflow["summary"] = "Detached HEAD"
            workflow["detail"] = "You can create a branch here or return to a branch before integrating changes."
        else:
            workflow["state"] = "idle"
            workflow["summary"] = f"On branch {branch_ui.get('current') or 'unknown'}"
            workflow["detail"] = branch_ui.get("head_summary") or ""

        if cozy_paths and not carryover_ui.get("has_parked") and not conflicts_ui.get("has_conflicts"):
            workflow["detail"] = "Local Cozy changes will be parked and restored during branch switches or integrations."

        if blocking_paths:
            blockers.append("Working tree has non-Cozy changes. Commit or stash them first.")

        workflow["can_fetch"] = not conflicts_ui.get("has_conflicts", False)
        workflow["can_switch"] = not carryover_ui.get("has_parked") and not conflicts_ui.get(
            "has_conflicts", False
        ) and not blocking_paths
        workflow["can_create"] = workflow["can_switch"]
        workflow["can_merge"] = workflow["can_switch"] and not branch_ui.get("detached")
        workflow["can_rebase"] = workflow["can_merge"]

        workflow["blockers"] = blockers
        return blockers

    @classmethod
    def _type_label(cls, datablock_type):
        if not datablock_type:
            return "datablock"
        return cls.TYPE_LABELS.get(datablock_type, datablock_type.replace("_", " ").rstrip("s"))

    @staticmethod
    def _group_label(group_id, group_meta, name_cache):
        group_type = (group_meta or {}).get("type", "group")
        root_uuid = (group_meta or {}).get("root", group_id)
        name = name_cache.get(root_uuid) or root_uuid or "Group"
        if group_type == "object":
            return f"Object: {name}"
        if group_type == "shared":
            return f"Shared: {name}"
        if group_type == "orphan":
            return f"Orphan: {name}"
        return f"Group: {name}"

    @staticmethod
    def _load_json_file(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return None

    def _load_json_for_source(self, rel_path, source):
        if not rel_path:
            return None
        try:
            if source == "WORKTREE":
                return self._load_json_file(self.path / rel_path)
            if source == "INDEX":
                raw = self.repo.git.show(f":{rel_path}")
            else:
                raw = self.repo.git.show(f"{source}:{rel_path}")
            return json.loads(raw)
        except Exception:
            return None

    def _manifest_for_source(self, source):
        if source == "WORKTREE":
            return self._load_manifest_working()
        if source == "INDEX":
            manifest = self._load_json_for_source(
                self.manifestpath.relative_to(self.path).as_posix(),
                "INDEX",
            )
            return manifest if isinstance(manifest, dict) else self._empty_manifest()
        if source == "HEAD":
            if self.repo is None or not self.repo.head.is_valid():
                return self._empty_manifest()
            return self._load_manifest_at("HEAD")
        return self._empty_manifest()

    def _build_name_cache(self, entries):
        name_cache = {}
        if not entries:
            return name_cache
        for _type_name, impl_class in self.bpy_protocol.implementations.items():
            data_collection = getattr(bpy.data, impl_class.bl_id, None)
            if not data_collection:
                continue
            for datablock in data_collection:
                uuid = getattr(datablock, "cozystudio_uuid", None)
                if not uuid or uuid not in entries or uuid in name_cache:
                    continue
                name_cache[uuid] = getattr(datablock, "name", None) or uuid
        return name_cache

    @classmethod
    def _summarize_block_diff(cls, status, datablock_type, before_block, after_block):
        base_status = status.removeprefix("staged_")
        type_label = cls._type_label(datablock_type)
        if base_status in {"added", "untracked"}:
            return f"Created {type_label}"
        if base_status == "deleted":
            return f"Deleted {type_label}"
        if base_status == "renamed":
            return f"Renamed {type_label}"
        if base_status == "copied":
            return f"Copied {type_label}"
        if base_status == "typechange":
            return f"Changed {type_label} type"
        if not isinstance(before_block, dict) or not isinstance(after_block, dict):
            return f"Updated {type_label}"

        changed_keys = sorted(
            {
                key
                for key in set(before_block.keys()) | set(after_block.keys())
                if before_block.get(key) != after_block.get(key)
            }
        )
        if not changed_keys:
            return f"Updated {type_label}"

        summaries = []
        if "transforms" in changed_keys:
            summaries.append("Transform changed")
        if "parent_uid" in changed_keys:
            summaries.append("Parenting changed")
        if "objects" in changed_keys or "children" in changed_keys:
            summaries.append("Collection membership changed")
        if "materials" in changed_keys:
            summaries.append("Material slots changed")
        if "node_tree" in changed_keys and datablock_type == "materials":
            summaries.append("Material nodes changed")
        if "animation_data" in changed_keys or "nodes_animation_data" in changed_keys:
            summaries.append("Animation changed")

        if summaries:
            return ", ".join(summaries[:2])
        if len(changed_keys) == 1:
            key = changed_keys[0].replace("_", " ")
            return f"Updated {key}"
        return f"Updated {len(changed_keys)} sections"

    def _diff_sources_for_status(self, status):
        base_status = status.removeprefix("staged_")
        if status.startswith("staged_"):
            return ("HEAD", None) if base_status == "deleted" else ("HEAD", "INDEX")
        return ("INDEX", None) if base_status == "deleted" else ("INDEX", "WORKTREE")

    def _entry_context_for_diff(self, uuid, before_source, after_source, manifests, entries, groups):
        if not uuid:
            return None, None, None
        current_entry = entries.get(uuid)
        current_group = None
        if current_entry:
            current_group = groups.get(current_entry.get(MANIFEST_GROUP_KEY) or uuid)

        before_manifest = manifests.get(before_source, self._empty_manifest())
        after_manifest = manifests.get(after_source, self._empty_manifest())
        before_entry = (before_manifest.get(MANIFEST_BLOCKS_KEY) or {}).get(uuid)
        after_entry = (after_manifest.get(MANIFEST_BLOCKS_KEY) or {}).get(uuid)
        entry = after_entry or current_entry or before_entry
        group_id = None
        group_meta = None
        if entry:
            group_id = entry.get(MANIFEST_GROUP_KEY) or uuid
            group_meta = groups.get(group_id)
            if group_meta is None and isinstance(after_manifest.get(MANIFEST_GROUPS_KEY), dict):
                group_meta = after_manifest.get(MANIFEST_GROUPS_KEY, {}).get(group_id)
            if group_meta is None and isinstance(before_manifest.get(MANIFEST_GROUPS_KEY), dict):
                group_meta = before_manifest.get(MANIFEST_GROUPS_KEY, {}).get(group_id)
        return entry, group_id, group_meta or current_group

    def _build_ui_diff_row(self, diff, manifests, entries, groups, name_cache):
        path = diff.get("path", "")
        uuid = None
        if path.startswith(".cozystudio/blocks/") and path.endswith(".json"):
            try:
                uuid = Path(path).stem
            except Exception:
                uuid = None

        before_source, after_source = self._diff_sources_for_status(diff.get("status", ""))
        before_block = self._load_json_for_source(path, before_source) if uuid else None
        after_block = self._load_json_for_source(path, after_source) if uuid and after_source else None
        entry, group_id, group_meta = self._entry_context_for_diff(
            uuid,
            before_source,
            after_source,
            manifests,
            entries,
            groups,
        )
        datablock_type = (entry or {}).get("type")
        display_name = (
            name_cache.get(uuid)
            or (after_block or {}).get("name")
            or (before_block or {}).get("name")
            or uuid
            or path
        )

        return {
            **diff,
            "uuid": uuid,
            "datablock_type": datablock_type,
            "entry_type": datablock_type,
            "group_id": group_id,
            "group": group_meta,
            "display_name": (
                f"{display_name} ({datablock_type})" if datablock_type else display_name
            ),
            "summary": self._summarize_block_diff(
                diff.get("status", ""),
                datablock_type,
                before_block,
                after_block,
            ),
        }

    def _build_ui_diff_groups(self, section_diffs, manifests, entries, groups, name_cache):
        grouped = {}
        ungrouped = []
        for diff in section_diffs:
            row = self._build_ui_diff_row(diff, manifests, entries, groups, name_cache)
            group_id = row.get("group_id")
            if row.get("uuid") and group_id:
                group_meta = row.get("group") or {}
                group = grouped.setdefault(
                    group_id,
                    {
                        "group_id": group_id,
                        "label": self._group_label(group_id, group_meta, name_cache),
                        "group": group_meta,
                        "diffs": [],
                    },
                )
                group["diffs"].append(row)
                continue
            ungrouped.append(row)

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
                        group_data["diffs"], key=lambda item: item.get("path", "")
                    ),
                }
            )

        if ungrouped:
            section_groups.append(
                {
                    "group_id": None,
                    "label": f"Ungrouped ({len(ungrouped)})",
                    "diffs": sorted(ungrouped, key=lambda item: item.get("path", "")),
                }
            )

        section_groups.sort(key=lambda item: item.get("label", ""))
        return section_groups

    def refresh_ui_state(self):
        ui_state = self._empty_ui_state()
        ui_state["repo"]["available"] = bool(self.repo)
        ui_state["repo"]["initiated"] = bool(self.initiated)
        ui_state["repo"]["path"] = str(self.path)
        ui_state["repo"]["has_manifest"] = isinstance(self.manifest, dict)
        ui_state["branch"]["last_branch"] = self.last_branch
        ui_state["carryover"]["error"] = self.last_carryover_error

        parked = self._managed_carryover()
        if parked:
            ui_state["carryover"]["has_parked"] = True
            ui_state["carryover"]["stash_ref"] = parked.get("stash_ref")
            ui_state["carryover"]["operation"] = parked.get("operation")
            ui_state["carryover"]["source"] = parked.get("source")
            ui_state["carryover"]["target"] = parked.get("target")

        capture_issues = [dict(issue) for issue in (self.last_capture_issues or [])]
        ui_state["capture"]["issues"] = capture_issues
        ui_state["capture"]["has_issues"] = bool(capture_issues)
        ui_state["capture"]["count"] = len(capture_issues)

        integrity = self.last_integrity_report
        if integrity is None and self.manifest is not None and self.initiated:
            integrity = self.validate_manifest_integrity()
        if isinstance(integrity, dict):
            ui_state["integrity"] = {
                "ok": bool(integrity.get("ok", False)),
                "errors": list(integrity.get("errors", [])),
                "warnings": list(integrity.get("warnings", [])),
            }

        ui_state["conflicts"]["items"] = self._manifest_conflict_items()
        ui_state["conflicts"]["has_conflicts"] = bool(ui_state["conflicts"]["items"])
        ui_state["conflicts"]["count"] = len(ui_state["conflicts"]["items"])
        if ui_state["conflicts"]["items"]:
            ui_state["conflicts"]["operation"] = ui_state["conflicts"]["items"][0].get(
                "operation"
            )

        if self.repo is not None:
            dirty_paths = self._dirty_paths()
            cozy_paths = self._cozy_dirty_paths(dirty_paths)
            blocking_paths = self._blocking_dirty_paths(dirty_paths)
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
                ui_state["branch"]["current_ref"] = ui_state["branch"]["head_short_hash"]
                ui_state["branch"]["current_ref_type"] = "detached"
                ui_state["commit"]["viewing_past"] = True
                return_branch = None
                if self.last_branch and self.last_branch in self.repo.heads:
                    return_branch = self.last_branch
                elif "main" in self.repo.heads:
                    return_branch = "main"
                elif "master" in self.repo.heads:
                    return_branch = "master"
                elif self.repo.heads:
                    return_branch = self.repo.heads[0].name
                ui_state["commit"]["return_branch"] = return_branch
                ui_state["commit"]["blockers"].append(
                    "Checkout a branch before committing."
                )
            else:
                try:
                    ui_state["branch"]["current"] = self.repo.active_branch.name
                    ui_state["branch"]["current_ref"] = self.repo.active_branch.name
                    ui_state["branch"]["current_ref_type"] = "branch"
                except Exception:
                    ui_state["branch"]["current"] = None

                try:
                    tracking = self.repo.active_branch.tracking_branch()
                except Exception:
                    tracking = None
                if tracking is not None:
                    ui_state["branch"]["upstream"] = tracking.name
                    ahead, behind = self._ahead_behind_counts(
                        ui_state["branch"]["current"],
                        tracking.name,
                    )
                    ui_state["branch"]["ahead"] = ahead
                    ui_state["branch"]["behind"] = behind

            local_rows = []
            for head in sorted(self.repo.heads, key=lambda item: item.name):
                upstream = None
                try:
                    tracking = head.tracking_branch()
                    upstream = tracking.name if tracking is not None else None
                except Exception:
                    upstream = None
                local_rows.append(
                    self._ref_ui_row(
                        head.name,
                        ref_type="local",
                        is_current=head.name == ui_state["branch"].get("current"),
                        upstream=upstream,
                    )
                )
            ui_state["branch"]["local"] = local_rows
            ui_state["branch"]["available"] = list(local_rows)

            remote_rows = []
            seen_remote = set()
            for remote in getattr(self.repo, "remotes", []):
                for ref in getattr(remote, "refs", []):
                    ref_name = getattr(ref, "name", None)
                    if not ref_name or ref_name.endswith("/HEAD") or ref_name in seen_remote:
                        continue
                    seen_remote.add(ref_name)
                    remote_rows.append(self._ref_ui_row(ref_name, ref_type="remote"))
            ui_state["branch"]["remote"] = sorted(
                remote_rows,
                key=lambda item: item.get("name", ""),
            )

            ui_state["branch"]["recent"] = [
                self._ref_ui_row(name, ref_type="local")
                for name in self._recent_branch_names()
            ]

            history_ref = "HEAD"
            if not detached:
                try:
                    history_ref = self.repo.active_branch.name or "HEAD"
                except Exception:
                    history_ref = "HEAD"
            try:
                commits = list(self.repo.iter_commits(history_ref, max_count=10))
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
            ui_state["history"]["count"] = len(ui_state["history"]["items"])

            self._workflow_blockers(ui_state, dirty_paths, cozy_paths, blocking_paths)

        diffs = list(self.diffs or [])
        staged = [diff for diff in diffs if diff.get("status", "").startswith("staged")]
        unstaged = [diff for diff in diffs if not diff.get("status", "").startswith("staged")]
        ui_state["changes"]["total"] = len(diffs)
        ui_state["changes"]["staged"] = len(staged)
        ui_state["changes"]["unstaged"] = len(unstaged)

        entries = (self.state or {}).get("entries", {})
        groups = (self.state or {}).get("groups", {})
        ui_state["repo"]["tracked_blocks"] = len(entries)
        ui_state["repo"]["tracked_groups"] = len(groups)
        name_cache = self._build_name_cache(entries)
        manifests = {
            "WORKTREE": self._manifest_for_source("WORKTREE"),
            "INDEX": self._manifest_for_source("INDEX"),
            "HEAD": self._manifest_for_source("HEAD"),
            None: self._empty_manifest(),
        }
        ui_state["changes"]["staged_groups"] = self._build_ui_diff_groups(
            staged,
            manifests,
            entries,
            groups,
            name_cache,
        )
        ui_state["changes"]["unstaged_groups"] = self._build_ui_diff_groups(
            unstaged,
            manifests,
            entries,
            groups,
            name_cache,
        )
        if ui_state["capture"]["has_issues"]:
            ui_state["commit"]["blockers"].append("Resolve capture issues before committing.")
        if not ui_state["integrity"].get("ok", True):
            ui_state["commit"]["blockers"].append("Fix manifest integrity errors before committing.")
        if ui_state["conflicts"]["has_conflicts"]:
            ui_state["commit"]["blockers"].append("Resolve conflicts before committing.")
        ui_state["commit"]["can_commit"] = (
            ui_state["changes"]["staged"] > 0 and not ui_state["commit"]["blockers"]
        )

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
