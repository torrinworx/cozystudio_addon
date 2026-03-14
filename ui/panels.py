import bpy

from . import state
from .helpers import _status_abbrev


def _git_ui():
    return getattr(state.git_instance, "ui_state", None) or {}


def _repo_ready(git_ui):
    return bool(state.git_instance) and bool(git_ui.get("repo", {}).get("initiated"))


def _draw_repo_missing(layout):
    box = layout.box()
    box.label(text="Welcome to Cozy Studio", icon="INFO")
    if not bpy.data.filepath:
        box.label(text="Save this .blend file to start a Cozy project.", icon="FILE_TICK")
        return
    box.label(text="No project repo found for this file.", icon="INFO")
    box.operator("cozystudio.setup_project", text="Init Project", icon="ADD")


class COZYSTUDIO_PT_MainPanel(bpy.types.Panel):
    bl_label = "Cozy Studio"
    bl_idname = "COZYSTUDIO_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cozy Studio"
    bl_order = 0

    @classmethod
    def poll(cls, context):
        return not _repo_ready(_git_ui())

    def draw(self, context):
        _draw_repo_missing(self.layout)


def _draw_grouped_changes(layout, groups, staged):
    if not groups:
        layout.label(
            text="No staged changes." if staged else "No unstaged changes.",
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

            op = row.operator(
                "cozystudio.revert_change",
                text="",
                icon="TRASH",
            )
            op.file_path = diff["path"]
            op.status = diff.get("status", "")

            if diff.get("summary"):
                row.label(text=diff["summary"])
            row.label(text=_status_abbrev(diff["status"]))


class COZYSTUDIO_PT_ChangesPanel(bpy.types.Panel):
    bl_label = "Changes"
    bl_idname = "COZYSTUDIO_PT_changes"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cozy Studio"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        return _repo_ready(_git_ui())

    def draw(self, context):
        layout = self.layout
        git_ui = _git_ui()

        commit_ui = git_ui.get("commit", {})
        branch_ui = git_ui.get("branch", {})
        changes_ui = git_ui.get("changes", {})
        integrity_ui = git_ui.get("integrity", {})
        conflicts_ui = git_ui.get("conflicts", {})
        carryover_ui = git_ui.get("carryover", {})

        if commit_ui.get("viewing_past"):
            row = layout.row(align=True)
            row.label(
                text=f"Detached at {branch_ui.get('head_short_hash') or 'commit'}",
                icon="TIME",
            )
            if commit_ui.get("return_branch"):
                op = row.operator("cozystudio.checkout_branch", text="Checkout Branch", icon="LOOP_BACK")
                op.branch_name = commit_ui["return_branch"]

        if carryover_ui.get("has_parked"):
            box = layout.box()
            box.label(text="Parked Cozy changes", icon="INFO")
            if carryover_ui.get("source") or carryover_ui.get("target"):
                box.label(
                    text=(
                        f"From {carryover_ui.get('source') or 'unknown'} "
                        f"to {carryover_ui.get('target') or 'unknown'}"
                    )
                )
            if carryover_ui.get("operation"):
                box.label(text=f"Operation: {carryover_ui['operation']}")
            if carryover_ui.get("stash_ref"):
                box.label(text=f"Stored in {carryover_ui['stash_ref']}")
            if carryover_ui.get("error"):
                box.label(text=carryover_ui["error"], icon="ERROR")
            box.operator(
                "cozystudio.reapply_parked_changes",
                text="Restore Parked Changes",
                icon="IMPORT",
            )

        layout.prop(context.window_manager, "cozystudio_commit_message", text="Message")

        row = layout.row()
        row.enabled = commit_ui.get("can_commit")
        row.operator("cozystudio.commit", text="Commit", icon="CHECKMARK")

        if integrity_ui.get("errors"):
            box = layout.box()
            box.label(text=integrity_ui["errors"][0], icon="ERROR")

        if conflicts_ui.get("has_conflicts"):
            box = layout.box()
            count = conflicts_ui.get("count", 0)
            operation = conflicts_ui.get("operation") or "merge"
            box.label(text=f"{count} unresolved conflicts block commits.", icon="ERROR")
            box.label(text=f"Finish the {operation} by choosing mine, theirs, or manual resolve.")

        if commit_ui.get("blockers"):
            blockers = layout.box()
            blockers.label(text="Commit blocked", icon="ERROR")
            for blocker in commit_ui.get("blockers", []):
                blockers.label(text=blocker)

        staged_box = layout.box()
        staged_box.label(text=f"Staged ({changes_ui.get('staged', 0)})", icon="CHECKMARK")
        _draw_grouped_changes(staged_box, changes_ui.get("staged_groups", []), staged=True)

        unstaged_box = layout.box()
        unstaged_box.label(text=f"Unstaged ({changes_ui.get('unstaged', 0)})", icon="GREASEPENCIL")
        _draw_grouped_changes(unstaged_box, changes_ui.get("unstaged_groups", []), staged=False)


class COZYSTUDIO_PT_HistoryPanel(bpy.types.Panel):
    bl_label = "History"
    bl_idname = "COZYSTUDIO_PT_history"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cozy Studio"
    bl_order = 2

    @classmethod
    def poll(cls, context):
        return _repo_ready(_git_ui())

    def draw(self, context):
        layout = self.layout
        git_ui = _git_ui()

        repo_ui = git_ui.get("repo", {})
        carryover_ui = git_ui.get("carryover", {})
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

        commit_ui = git_ui.get("commit", {})
        branch_ui = git_ui.get("branch", {})
        if carryover_ui.get("has_parked"):
            box = layout.box()
            box.label(text="Parked Cozy changes block further checkout operations.", icon="INFO")
            box.operator(
                "cozystudio.reapply_parked_changes",
                text="Restore Parked Changes",
                icon="IMPORT",
            )
        if commit_ui.get("viewing_past") and branch_ui.get("head_short_hash"):
            row = layout.row(align=True)
            row.label(text=f"Detached at {branch_ui['head_short_hash']}", icon="TIME")
            if commit_ui.get("return_branch"):
                op = row.operator("cozystudio.checkout_branch", text="Checkout Branch", icon="LOOP_BACK")
                op.branch_name = commit_ui["return_branch"]

        if not history_items:
            layout.label(text="No commits found.", icon="INFO")
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




class COZYSTUDIO_PT_BranchesPanel(bpy.types.Panel):
    bl_label = "Branches"
    bl_idname = "COZYSTUDIO_PT_branches"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cozy Studio"
    bl_order = 3

    @classmethod
    def poll(cls, context):
        return _repo_ready(_git_ui())

    def draw(self, context):
        layout = self.layout
        git_ui = _git_ui()

        branch_ui = git_ui.get("branch", {})
        commit_ui = git_ui.get("commit", {})
        carryover_ui = git_ui.get("carryover", {})

        if carryover_ui.get("has_parked"):
            box = layout.box()
            box.label(text="Parked Cozy changes must be restored first.", icon="INFO")
            box.operator(
                "cozystudio.reapply_parked_changes",
                text="Restore Parked Changes",
                icon="IMPORT",
            )

        if branch_ui.get("detached"):
            row = layout.row(align=True)
            row.label(
                text=f"Detached at {branch_ui.get('head_short_hash') or 'commit'}",
                icon="TIME",
            )
            if commit_ui.get("return_branch"):
                op = row.operator("cozystudio.checkout_branch", text="Checkout Branch", icon="LOOP_BACK")
                op.branch_name = commit_ui["return_branch"]
        else:
            layout.label(
                text=f"Current branch: {branch_ui.get('current') or 'unknown'}",
                icon="CURRENT_FILE",
            )

        branches = branch_ui.get("available", [])
        if not branches:
            layout.label(text="No local branches found.", icon="INFO")
            return

        for branch in branches:
            row = layout.row(align=True)
            row.label(
                text=branch.get("name", "branch"),
                icon="RADIOBUT_ON" if branch.get("is_current") else "BLANK1",
            )
            if branch.get("is_current"):
                continue

            op = row.operator("cozystudio.checkout_branch", text="Checkout", icon="LOOP_BACK")
            op.branch_name = branch.get("name", "")
            op = row.operator("cozystudio.merge", text="Merge", icon="IMPORT")
            op.ref_name = branch.get("name", "")
            op = row.operator("cozystudio.rebase", text="Rebase", icon="TRIA_RIGHT_BAR")
            op.ref_name = branch.get("name", "")


class COZYSTUDIO_PT_ConflictsPanel(bpy.types.Panel):
    bl_label = "Conflicts"
    bl_idname = "COZYSTUDIO_PT_conflicts"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cozy Studio"
    bl_order = 4

    @classmethod
    def poll(cls, context):
        git_ui = _git_ui()
        return _repo_ready(git_ui) and git_ui.get("conflicts", {}).get("has_conflicts")

    def draw(self, context):
        layout = self.layout
        conflicts_ui = _git_ui().get("conflicts", {})

        layout.label(text=f"{conflicts_ui.get('count', 0)} unresolved conflicts", icon="ERROR")
        for item in conflicts_ui.get("items", []):
            box = layout.box()
            title = item.get("label") or item.get("uuid") or "Conflict"
            if item.get("datablock_type"):
                title = f"{title} ({item['datablock_type']})"
            box.label(text=title, icon="ERROR")
            box.label(text=item.get("reason") or "Conflict")
            if item.get("operation"):
                box.label(text=f"Operation: {item['operation']}")
            if item.get("uuid"):
                row = box.row(align=True)
                op = row.operator(
                    "cozystudio.resolve_conflict_version",
                    text="Checkout Mine",
                    icon="LOOP_BACK",
                )
                op.conflict_uuid = item["uuid"]
                op.resolution = "ours"
                op = row.operator(
                    "cozystudio.resolve_conflict_version",
                    text="Checkout Theirs",
                    icon="IMPORT",
                )
                op.conflict_uuid = item["uuid"]
                op.resolution = "theirs"
                row = box.row(align=True)
                op = row.operator("cozystudio.select_block", text="Select Block", icon="RESTRICT_SELECT_OFF")
                op.uuid = item["uuid"]
                op = row.operator(
                    "cozystudio.resolve_conflict",
                    text="Mark Manually Resolved",
                    icon="CHECKMARK",
                )
                op.conflict_uuid = item["uuid"]


