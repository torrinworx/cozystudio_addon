import bpy

from . import state
from .helpers import _status_abbrev


def _git_ui():
    return getattr(state.git_instance, "ui_state", None) or {}


def _repo_ready(git_ui):
    return bool(state.git_instance) and bool(git_ui.get("repo", {}).get("initiated"))


def _ref_name_from_token(token):
    token = (token or "").strip()
    if not token or token == "NONE" or ":" not in token:
        return None, None
    return token.split(":", 1)


def _find_ref_row(branch_ui, token):
    ref_type, ref_name = _ref_name_from_token(token)
    if not ref_name:
        return None
    for section in ("recent", "local", "remote"):
        for item in branch_ui.get(section, []):
            if item.get("type") == ref_type and item.get("name") == ref_name:
                return item
    return None


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
                text=f"Detached at {branch_ui.get('head_short_hash') or 'commit'} (not on a branch)",
                icon="TIME",
            )
            if commit_ui.get("return_branch"):
                op = row.operator("cozystudio.checkout_branch", text="Return to Branch", icon="LOOP_BACK")
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
        branch_ui = git_ui.get("branch", {})
        commit_ui = git_ui.get("commit", {})
        if not repo_ui.get("available"):
            layout.label(text="No repository available.", icon="ERROR")
            return

        if branch_ui.get("detached"):
            layout.label(
                text=f"HEAD: detached at {branch_ui.get('head_short_hash') or 'commit'}",
                icon="TIME",
            )
        else:
            layout.label(
                text=f"HEAD: {branch_ui.get('current') or 'unknown'}",
                icon="CURRENT_FILE",
            )

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
            row.label(
                text=f"Detached at {branch_ui['head_short_hash']} (not on a branch)",
                icon="TIME",
            )
            if commit_ui.get("return_branch"):
                op = row.operator("cozystudio.checkout_branch", text="Return to Branch", icon="LOOP_BACK")
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
        workflow_ui = git_ui.get("workflow", {})
        conflicts_ui = git_ui.get("conflicts", {})
        wm = context.window_manager

        status_box = layout.box()
        status_box.label(text="Branch Status", icon="CURRENT_FILE")
        if branch_ui.get("detached"):
            status_box.label(
                text=f"Detached at {branch_ui.get('head_short_hash') or 'commit'}",
                icon="TIME",
            )
            if branch_ui.get("head_summary"):
                status_box.label(text=branch_ui["head_summary"], icon="FILE_TEXT")
        else:
            status_box.label(
                text=f"On branch: {branch_ui.get('current') or 'unknown'}",
                icon="CURRENT_FILE",
            )
            if branch_ui.get("upstream"):
                status_box.label(
                    text=(
                        f"Tracks {branch_ui['upstream']}  "
                        f"ahead {branch_ui.get('ahead', 0)}  behind {branch_ui.get('behind', 0)}"
                    ),
                    icon="LINKED",
                )
            if branch_ui.get("head_summary"):
                status_box.label(
                    text=f"HEAD {branch_ui.get('head_short_hash') or ''}  {branch_ui['head_summary']}",
                    icon="FILE_TEXT",
                )

        workflow_box = layout.box()
        workflow_box.label(text=workflow_ui.get("summary") or "Workflow", icon="INFO")
        if workflow_ui.get("detail"):
            workflow_box.label(text=workflow_ui["detail"])
        if workflow_ui.get("dirty_cozy"):
            workflow_box.label(
                text=f"Local Cozy changes: {workflow_ui['dirty_cozy']}",
                icon="GREASEPENCIL",
            )
        if workflow_ui.get("dirty_non_cozy"):
            workflow_box.label(
                text=f"Non-Cozy changes blocking branch actions: {workflow_ui['dirty_non_cozy']}",
                icon="ERROR",
            )
        for blocker in workflow_ui.get("blockers", [])[:3]:
            workflow_box.label(text=blocker, icon="ERROR")

        if carryover_ui.get("has_parked"):
            box = layout.box()
            box.label(text="Parked Cozy changes", icon="INFO")
            if carryover_ui.get("operation"):
                box.label(text=f"Created during {carryover_ui['operation']}")
            if carryover_ui.get("source") or carryover_ui.get("target"):
                box.label(
                    text=(
                        f"From {carryover_ui.get('source') or 'unknown'} "
                        f"to {carryover_ui.get('target') or 'unknown'}"
                    )
                )
            box.operator(
                "cozystudio.reapply_parked_changes",
                text="Restore Parked Changes",
                icon="IMPORT",
            )

        history_items = git_ui.get("history", {}).get("items", [])
        selected_commit = None
        if history_items:
            try:
                selected_commit = history_items[wm.cozystudio_commit_index]
            except Exception:
                selected_commit = None

        switch_box = layout.box()
        switch_box.label(text="Switch Branch", icon="FILE_PARENT")
        switch_box.prop(wm, "cozystudio_branch_target", text="Target")
        selected_ref = _find_ref_row(branch_ui, getattr(wm, "cozystudio_branch_target", ""))
        if selected_ref:
            switch_box.label(
                text=selected_ref.get("description") or selected_ref.get("label") or selected_ref.get("name"),
                icon="INFO",
            )
        elif branch_ui.get("local") or branch_ui.get("remote"):
            switch_box.label(text="Choose a branch or remote ref to switch to.", icon="INFO")

        switch_row = switch_box.row(align=True)
        switch_row.enabled = workflow_ui.get("can_switch", True) and bool(selected_ref)
        switch_op = switch_row.operator(
            "cozystudio.checkout_selected_ref",
            text=(
                "Checkout Tracking Branch"
                if selected_ref and selected_ref.get("type") == "remote"
                else "Switch Branch"
            ),
            icon="LOOP_BACK",
        )
        switch_op.ref_token = getattr(wm, "cozystudio_branch_target", "")
        fetch_row = switch_box.row(align=True)
        fetch_row.enabled = workflow_ui.get("can_fetch", True)
        fetch_row.operator("cozystudio.fetch_branches", text="Fetch / Refresh", icon="FILE_REFRESH")

        if branch_ui.get("detached") and commit_ui.get("return_branch"):
            return_row = switch_box.row(align=True)
            return_row.enabled = workflow_ui.get("can_switch", True)
            op = return_row.operator("cozystudio.checkout_branch", text="Return to Branch", icon="LOOP_BACK")
            op.branch_name = commit_ui["return_branch"]

        create_box = layout.box()
        create_box.label(text="Create Branch", icon="ADD")
        create_box.prop(wm, "cozystudio_branch_name", text="Name")
        create_box.prop(wm, "cozystudio_branch_source", text="From")

        source = getattr(wm, "cozystudio_branch_source", "HEAD")
        if source == "SELECTED":
            if selected_commit:
                create_box.label(
                    text=(
                        f"From commit: {selected_commit.get('short_hash', '')}  "
                        f"{selected_commit.get('summary', '')}"
                    ),
                    icon="FILE_TEXT",
                )
                create_box.label(
                    text="New branch will be checked out at this commit.",
                    icon="INFO",
                )
            else:
                create_box.label(
                    text="Select a commit in History to use as source.",
                    icon="INFO",
                )
        else:
            if branch_ui.get("detached"):
                create_box.label(
                    text=(
                        f"From HEAD (detached at {branch_ui.get('head_short_hash') or 'commit'})"
                    ),
                    icon="TIME",
                )
            else:
                create_box.label(
                    text=f"From HEAD on {branch_ui.get('current') or 'unknown'}",
                    icon="CURRENT_FILE",
                )
            create_box.label(
                text="New branch will be checked out at HEAD.",
                icon="INFO",
            )

        create_row = create_box.row()
        branch_name = (getattr(wm, "cozystudio_branch_name", "") or "").strip()
        can_create = (
            workflow_ui.get("can_create", True)
            and bool(branch_name)
            and (source != "SELECTED" or selected_commit)
        )
        create_row.enabled = can_create
        op = create_row.operator("cozystudio.create_branch", text="Create Branch", icon="ADD")
        op.branch_name = branch_name
        op.ref = selected_commit.get("commit_hash", "") if selected_commit and source == "SELECTED" else ""

        integrate_box = layout.box()
        integrate_box.label(text="Integrate Into Current Branch", icon="SORTTIME")
        integrate_box.prop(wm, "cozystudio_integration_mode", text="Mode")
        integrate_box.prop(wm, "cozystudio_integration_target", text="Target")
        integrate_box.prop(wm, "cozystudio_conflict_strategy", text="Conflicts")

        selected_target = _find_ref_row(branch_ui, getattr(wm, "cozystudio_integration_target", ""))
        if selected_target:
            mode_label = "Merge" if wm.cozystudio_integration_mode == "MERGE" else "Rebase"
            current_name = branch_ui.get("current") or "current branch"
            if wm.cozystudio_integration_mode == "MERGE":
                summary = f"{mode_label} {selected_target.get('name')} into {current_name}"
            else:
                summary = f"{mode_label} {current_name} onto {selected_target.get('name')}"
            integrate_box.label(text=summary, icon="INFO")
        else:
            integrate_box.label(text="Choose a branch or remote ref to integrate.", icon="INFO")

        if branch_ui.get("detached"):
            integrate_box.label(text="Checkout a branch before merging or rebasing.", icon="ERROR")
        if conflicts_ui.get("has_conflicts"):
            integrate_box.label(text="Finish current conflicts before another integration.", icon="ERROR")

        integrate_row = integrate_box.row()
        can_integrate = bool(selected_target)
        if wm.cozystudio_integration_mode == "MERGE":
            can_integrate = can_integrate and workflow_ui.get("can_merge", True)
        else:
            can_integrate = can_integrate and workflow_ui.get("can_rebase", True)
        integrate_row.enabled = can_integrate
        op = integrate_row.operator(
            "cozystudio.integrate_selected_ref",
            text="Start Integration",
            icon="IMPORT" if wm.cozystudio_integration_mode == "MERGE" else "TRIA_RIGHT_BAR",
        )
        op.ref_token = getattr(wm, "cozystudio_integration_target", "")
        op.mode = wm.cozystudio_integration_mode
        op.strategy = wm.cozystudio_conflict_strategy

        if branch_ui.get("recent"):
            recent_box = layout.box()
            recent_box.label(text="Recent Branches", icon="RECOVER_LAST")
            for branch in branch_ui.get("recent", []):
                recent_box.label(text=branch.get("name", "branch"), icon="FILE_PARENT")


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
