import bpy

from . import state
from .helpers import _status_abbrev


class MAIN_PT_Panel(bpy.types.Panel):
    bl_label = "Changes"
    bl_idname = "COZYSTUDIO_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cozy Studio"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        git_ui = getattr(state.git_instance, "ui_state", None) or {}
        repo_ui = git_ui.get("repo", {})

        if not state.git_instance or not repo_ui.get("initiated"):
            layout.label(text="No CozyStudio repo found.")
            layout.operator("cozystudio.init_repo", text="Init Repository")
            return

        layout.prop(context.window_manager, "cozystudio_commit_message", text="Message")
        row = layout.row(align=True)
        row.label(text="Auto refresh: 1s")
        row.operator("cozystudio.manual_refresh", text="Refresh", icon="FILE_REFRESH")
        layout.separator()

        integrity_ui = git_ui.get("integrity", {})
        if integrity_ui.get("errors"):
            box = layout.box()
            box.label(text=integrity_ui["errors"][0], icon="ERROR")

        conflicts_ui = git_ui.get("conflicts", {})
        if conflicts_ui.get("has_conflicts"):
            box = layout.box()
            box.label(text="Unresolved conflicts block snapshots.", icon="ERROR")

        grouped_staged = git_ui.get("changes", {}).get("staged_groups", [])
        grouped_unstaged = git_ui.get("changes", {}).get("unstaged_groups", [])

        if grouped_staged:
            box = layout.box()
            box.label(
                text=f"STAGED CHANGES ({git_ui.get('changes', {}).get('staged', 0)})",
                icon="CHECKMARK",
            )
            for group in grouped_staged:
                group_box = box.box()
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
                header.label(text=group["label"], icon="FILE_FOLDER")
                if group_id:
                    op = header.operator("cozystudio.unstage_group", text="", icon="REMOVE")
                    op.group_id = group_id

                if expanded:
                    for diff in group["diffs"]:
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
                            row.label(
                                text=diff.get("display_name") or diff.get("path", "Entry"),
                                icon="FILE",
                            )
                        if is_ungrouped:
                            op = row.operator(
                                "cozystudio.unstage_file", text="", icon="REMOVE"
                            )
                            op.file_path = diff["path"]
                        if diff.get("summary"):
                            row.label(text=diff["summary"])
                        row.label(text=_status_abbrev(diff["status"]))

        if grouped_unstaged:
            box = layout.box()
            box.label(
                text=f"CHANGES ({git_ui.get('changes', {}).get('unstaged', 0)})",
                icon="GREASEPENCIL",
            )
            for group in grouped_unstaged:
                group_box = box.box()
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
                header.label(text=group["label"], icon="FILE_FOLDER")
                if group_id:
                    op = header.operator("cozystudio.add_group", text="", icon="ADD")
                    op.group_id = group_id

                if expanded:
                    for diff in group["diffs"]:
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
                            row.label(
                                text=diff.get("display_name") or diff.get("path", "Entry"),
                                icon="FILE",
                            )
                        if is_ungrouped:
                            op = row.operator(
                                "cozystudio.add_file", text="", icon="ADD"
                            )
                            op.file_path = diff["path"]
                        if diff.get("summary"):
                            row.label(text=diff["summary"])
                        row.label(text=_status_abbrev(diff["status"]))

        layout.separator()
        layout.operator("cozystudio.commit", text="Commit")


class COZYSTUDIO_PT_LogPanel(bpy.types.Panel):
    bl_label = "Log"
    bl_idname = "COZYSTUDIO_PT_log"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cozy Studio"
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        git_ui = getattr(state.git_instance, "ui_state", None) or {}
        repo_ui = git_ui.get("repo", {})

        if not state.git_instance or not repo_ui.get("initiated"):
            layout.label(text="No CozyStudio repo found.")
            return

        if not repo_ui.get("available"):
            layout.label(text="No repository available.")
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

        snapshot_ui = git_ui.get("snapshot", {})
        branch_ui = git_ui.get("branch", {})
        if snapshot_ui.get("viewing_past") and branch_ui.get("head_short_hash"):
            row = layout.row(align=True)
            row.label(text=f"Detached at {branch_ui['head_short_hash']}")

            branch_name = snapshot_ui.get("return_branch")
            if branch_name:
                op = row.operator(
                    "cozystudio.checkout_branch",
                    text="Return",
                    icon="LOOP_BACK",
                )
                op.branch_name = branch_name

        if not history_items:
            layout.label(text="No commits found.")
            return

        layout.template_list(
            "COZYSTUDIO_UL_CommitList",
            "",
            wm,
            "cozystudio_commit_items",
            wm,
            "cozystudio_commit_index",
            rows=5,
        )
