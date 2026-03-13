import bpy

from . import state
from .helpers import _status_abbrev


def _git_ui():
    return getattr(state.git_instance, "ui_state", None) or {}


def _repo_ready(git_ui):
    return bool(state.git_instance) and bool(git_ui.get("repo", {}).get("initiated"))


def _draw_repo_missing(layout):
    if not bpy.data.filepath:
        layout.label(text="Save this .blend file to start a Cozy project.", icon="INFO")
        return
    layout.label(text="No CozyStudio repo found for this file.", icon="INFO")
    layout.operator("cozystudio.setup_project", text="Setup Project", icon="ADD")


def _draw_grouped_changes(layout, groups, staged):
    if not groups:
        layout.label(
            text="No staged changes." if staged else "No pending changes.",
            icon="CHECKMARK" if staged else "INFO",
        )
        return

    for group in groups:
        group_box = layout.box()
        header = group_box.row(align=True)
        group_id = group.get("group_id")
        is_ungrouped = group_id is None
        if not is_ungrouped:
            expanded = group_id in state._group_expanded
            icon = "TRIA_DOWN" if expanded else "TRIA_RIGHT"
            op = header.operator(
                "cozystudio.toggle_group_expanded",
                text="",
                icon=icon,
                emboss=False,
            )
            op.group_id = group_id
        else:
            expanded = True

        header.label(text=group.get("label", "Group"), icon="FILE_FOLDER")
        if group_id:
            op = header.operator(
                "cozystudio.unstage_group" if staged else "cozystudio.add_group",
                text="",
                icon="REMOVE" if staged else "ADD",
            )
            op.group_id = group_id

        if not expanded:
            continue

        for diff in group.get("diffs", []):
            row = group_box.row(align=True)
            uuid = diff.get("uuid")
            if uuid:
                op = row.operator(
                    "cozystudio.select_block",
                    text=diff.get("display_name") or diff.get("path", "Entry"),
                    icon="FILE",
                    emboss=False,
                )
                op.uuid = uuid
            else:
                row.label(text=diff.get("display_name") or diff.get("path", "Entry"), icon="FILE")

            if is_ungrouped:
                op = row.operator(
                    "cozystudio.unstage_file" if staged else "cozystudio.add_file",
                    text="",
                    icon="REMOVE" if staged else "ADD",
                )
                op.file_path = diff["path"]

            if diff.get("summary"):
                row.label(text=diff["summary"])
            row.label(text=_status_abbrev(diff["status"]))


class COZYSTUDIO_PT_ProjectPanel(bpy.types.Panel):
    bl_label = "Project"
    bl_idname = "COZYSTUDIO_PT_project"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cozy Studio"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        git_ui = _git_ui()
        repo_ui = git_ui.get("repo", {})
        branch_ui = git_ui.get("branch", {})
        changes_ui = git_ui.get("changes", {})

        header = layout.row(align=True)
        header.label(text="Datablock snapshots, not .blend history.", icon="ASSET_MANAGER")
        header.prop(context.window_manager, "cozystudio_advanced_mode", text="Advanced")

        if not _repo_ready(git_ui):
            _draw_repo_missing(layout)
            return

        status = layout.box()
        status.label(text="Project Status", icon="CHECKMARK")
        if branch_ui.get("detached"):
            status.label(text="Viewing a past snapshot", icon="TIME")
        else:
            status.label(text=f"On branch: {branch_ui.get('current') or 'unknown'}", icon="CURRENT_FILE")
        status.label(text=f"Tracked blocks: {repo_ui.get('tracked_blocks', 0)}")
        status.label(text=f"Groups: {repo_ui.get('tracked_groups', 0)}")
        status.label(
            text=(
                f"Changes: {changes_ui.get('unstaged', 0)} pending / {changes_ui.get('staged', 0)} staged"
            ),
            icon="GREASEPENCIL",
        )

        if context.window_manager.cozystudio_advanced_mode:
            advanced = layout.box()
            advanced.label(text="Advanced Details", icon="PREFERENCES")
            advanced.label(text=f"Repo path: {repo_ui.get('path') or '-'}")
            advanced.label(text=f"Manifest loaded: {'Yes' if repo_ui.get('has_manifest') else 'No'}")
            if branch_ui.get("head_hash"):
                advanced.label(text=f"HEAD: {branch_ui['head_hash']}")


class MAIN_PT_Panel(bpy.types.Panel):
    bl_label = "Changes"
    bl_idname = "COZYSTUDIO_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cozy Studio"
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        git_ui = _git_ui()

        if not _repo_ready(git_ui):
            _draw_repo_missing(layout)
            return

        integrity_ui = git_ui.get("integrity", {})
        conflicts_ui = git_ui.get("conflicts", {})
        changes_ui = git_ui.get("changes", {})

        if integrity_ui.get("errors"):
            box = layout.box()
            box.label(text=integrity_ui["errors"][0], icon="ERROR")

        if conflicts_ui.get("has_conflicts"):
            box = layout.box()
            box.label(text="Unresolved conflicts block snapshots.", icon="ERROR")

        staged_box = layout.box()
        staged_box.label(text=f"Staged ({changes_ui.get('staged', 0)})", icon="CHECKMARK")
        _draw_grouped_changes(staged_box, changes_ui.get("staged_groups", []), staged=True)

        unstaged_box = layout.box()
        unstaged_box.label(text=f"Pending ({changes_ui.get('unstaged', 0)})", icon="GREASEPENCIL")
        _draw_grouped_changes(unstaged_box, changes_ui.get("unstaged_groups", []), staged=False)


class COZYSTUDIO_PT_SnapshotPanel(bpy.types.Panel):
    bl_label = "Snapshot"
    bl_idname = "COZYSTUDIO_PT_snapshot"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cozy Studio"
    bl_order = 2

    def draw(self, context):
        layout = self.layout
        git_ui = _git_ui()
        if not _repo_ready(git_ui):
            _draw_repo_missing(layout)
            return

        snapshot_ui = git_ui.get("snapshot", {})
        changes_ui = git_ui.get("changes", {})
        layout.prop(context.window_manager, "cozystudio_commit_message", text="Message")
        layout.label(text=f"{changes_ui.get('staged', 0)} staged rows ready for snapshot.", icon="CHECKMARK")
        if snapshot_ui.get("blockers"):
            blockers = layout.box()
            blockers.label(text="Snapshot blocked", icon="ERROR")
            for blocker in snapshot_ui.get("blockers", []):
                blockers.label(text=blocker)
        elif not changes_ui.get("staged"):
            layout.label(text="Stage one or more groups to create a snapshot.", icon="INFO")

        row = layout.row()
        row.enabled = snapshot_ui.get("can_commit")
        row.operator("cozystudio.create_snapshot", text="Create Snapshot", icon="CHECKMARK")


class COZYSTUDIO_PT_LogPanel(bpy.types.Panel):
    bl_label = "History"
    bl_idname = "COZYSTUDIO_PT_log"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cozy Studio"
    bl_order = 3

    def draw(self, context):
        layout = self.layout
        git_ui = _git_ui()
        if not _repo_ready(git_ui):
            _draw_repo_missing(layout)
            return

        repo_ui = git_ui.get("repo", {})
        if not repo_ui.get("available"):
            layout.label(text="No repository available.", icon="ERROR")
            return

        wm = context.window_manager
        history_items = git_ui.get("history", {}).get("items", [])
        items = wm.cozystudio_commit_items
        items.clear()
        for commit in history_items:
            item = items.add()
            item.commit_hash = commit.get("commit_hash", "")
            item.short_hash = commit.get("short_hash", "")
            item.summary = commit.get("summary", "(no message)")
            item.is_head = bool(commit.get("is_head"))

        snapshot_ui = git_ui.get("snapshot", {})
        branch_ui = git_ui.get("branch", {})
        if snapshot_ui.get("viewing_past") and branch_ui.get("head_short_hash"):
            row = layout.row(align=True)
            row.label(text=f"Detached at {branch_ui['head_short_hash']}", icon="TIME")
            branch_name = snapshot_ui.get("return_branch")
            if branch_name:
                op = row.operator("cozystudio.switch_branch", text="Return", icon="LOOP_BACK")
                op.branch_name = branch_name

        if not history_items:
            layout.label(text="No snapshots found.", icon="INFO")
            return

        layout.template_list(
            "COZYSTUDIO_UL_CommitList",
            "",
            wm,
            "cozystudio_commit_items",
            wm,
            "cozystudio_commit_index",
            rows=6,
        )


class COZYSTUDIO_PT_SyncPanel(bpy.types.Panel):
    bl_label = "Sync"
    bl_idname = "COZYSTUDIO_PT_sync"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cozy Studio"
    bl_order = 4

    def draw(self, context):
        layout = self.layout
        git_ui = _git_ui()
        if not _repo_ready(git_ui):
            _draw_repo_missing(layout)
            return

        branch_ui = git_ui.get("branch", {})
        snapshot_ui = git_ui.get("snapshot", {})
        layout.label(
            text=(
                f"Current branch: {branch_ui.get('current')}"
                if not branch_ui.get("detached")
                else "Current state: viewing a past snapshot"
            ),
            icon="CURRENT_FILE",
        )
        if snapshot_ui.get("return_branch"):
            row = layout.row(align=True)
            row.label(text=f"Return branch: {snapshot_ui['return_branch']}")
            op = row.operator("cozystudio.switch_branch", text="Return", icon="LOOP_BACK")
            op.branch_name = snapshot_ui["return_branch"]

        row = layout.row(align=True)
        row.operator("cozystudio.bring_in_changes", text="Bring In Changes", icon="IMPORT")
        row.operator("cozystudio.replay_my_work", text="Replay My Work", icon="TRIA_RIGHT_BAR")
        if context.window_manager.cozystudio_advanced_mode:
            advanced = layout.box()
            advanced.label(text="Advanced Branch State", icon="PREFERENCES")
            advanced.label(text=f"Detached: {'Yes' if branch_ui.get('detached') else 'No'}")
            advanced.label(text=f"Last branch: {branch_ui.get('last_branch') or '-'}")
            advanced.label(text=f"HEAD: {branch_ui.get('head_short_hash') or '-'}")


class COZYSTUDIO_PT_ConflictsPanel(bpy.types.Panel):
    bl_label = "Conflicts"
    bl_idname = "COZYSTUDIO_PT_conflicts"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cozy Studio"
    bl_order = 5

    def draw(self, context):
        layout = self.layout
        git_ui = _git_ui()
        if not _repo_ready(git_ui):
            _draw_repo_missing(layout)
            return

        conflicts_ui = git_ui.get("conflicts", {})
        if not conflicts_ui.get("has_conflicts"):
            layout.label(text="No unresolved conflicts.", icon="CHECKMARK")
            return

        layout.label(text=f"{conflicts_ui.get('count', 0)} unresolved conflicts", icon="ERROR")
        clear_all = layout.row()
        clear_all.operator("cozystudio.resolve_conflict", text="Mark All Resolved", icon="CHECKMARK")
        for item in conflicts_ui.get("items", []):
            box = layout.box()
            if context.window_manager.cozystudio_advanced_mode and item.get("uuid"):
                box.label(text=item["uuid"], icon="FILE")
            box.label(text=item.get("reason") or "Conflict", icon="ERROR")
            if item.get("uuid"):
                op = box.operator("cozystudio.resolve_conflict", text="Mark Resolved", icon="CHECKMARK")
                op.conflict_uuid = item["uuid"]


class COZYSTUDIO_PT_DiagnosticsPanel(bpy.types.Panel):
    bl_label = "Diagnostics"
    bl_idname = "COZYSTUDIO_PT_diagnostics"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cozy Studio"
    bl_order = 6

    def draw(self, context):
        layout = self.layout
        git_ui = _git_ui()
        if not _repo_ready(git_ui):
            _draw_repo_missing(layout)
            return

        integrity_ui = git_ui.get("integrity", {})
        capture_ui = git_ui.get("capture", {})

        row = layout.row(align=True)
        row.label(text="System status", icon="INFO")
        row.operator("cozystudio.run_diagnostics", text="Refresh", icon="FILE_REFRESH")

        integrity_box = layout.box()
        integrity_box.label(
            text="Manifest integrity OK" if integrity_ui.get("ok") else "Manifest integrity issues",
            icon="CHECKMARK" if integrity_ui.get("ok") else "ERROR",
        )
        for error in integrity_ui.get("errors", []):
            integrity_box.label(text=error)
        for warning in integrity_ui.get("warnings", []):
            integrity_box.label(text=warning, icon="INFO")

        capture_box = layout.box()
        capture_box.label(
            text=(
                f"Capture issues: {capture_ui.get('count', 0)}"
                if capture_ui.get("has_issues")
                else "Capture path is healthy"
            ),
            icon="ERROR" if capture_ui.get("has_issues") else "CHECKMARK",
        )
        for issue in capture_ui.get("issues", []):
            capture_box.label(text=issue.get("reason") or issue.get("status") or "Issue")

        if context.window_manager.cozystudio_advanced_mode:
            repo_ui = git_ui.get("repo", {})
            changes_ui = git_ui.get("changes", {})
            advanced = layout.box()
            advanced.label(text="Advanced Diagnostics", icon="PREFERENCES")
            advanced.label(text=f"Repo path: {repo_ui.get('path') or '-'}")
            advanced.label(text=f"History items cached: {git_ui.get('history', {}).get('count', 0)}")
            advanced.label(text=f"Pending groups: {len(changes_ui.get('unstaged_groups', []))}")
            advanced.label(text=f"Staged groups: {len(changes_ui.get('staged_groups', []))}")
