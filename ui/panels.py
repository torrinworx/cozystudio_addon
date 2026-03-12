import bpy

from . import state
from .helpers import _display_block_label, _group_diffs, _status_abbrev


class MAIN_PT_Panel(bpy.types.Panel):
    bl_label = "Changes"
    bl_idname = "COZYSTUDIO_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cozy Studio"
    bl_order = 0

    def draw(self, context):
        layout = self.layout

        if not state.git_instance or not getattr(state.git_instance, "initiated", False):
            layout.label(text="No CozyStudio repo found.")
            layout.operator("cozystudio.init_repo", text="Init Repository")
            return

        layout.prop(context.window_manager, "cozystudio_commit_message", text="Message")
        row = layout.row(align=True)
        row.label(text="Auto refresh: 1s")
        row.operator("cozystudio.manual_refresh", text="Refresh", icon="FILE_REFRESH")
        layout.separator()

        diffs = getattr(state.git_instance, "diffs", None) or []
        staged = [d for d in diffs if d["status"].startswith("staged")]
        unstaged = [d for d in diffs if not d["status"].startswith("staged")]

        grouped_staged = _group_diffs(state.git_instance, staged)
        grouped_unstaged = _group_diffs(state.git_instance, unstaged)

        if grouped_staged:
            box = layout.box()
            box.label(text="STAGED CHANGES", icon="CHECKMARK")
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
                                text=_display_block_label(diff, group["name_cache"]),
                                icon="FILE",
                                emboss=False,
                            )
                            op.uuid = uuid
                        else:
                            row.label(
                                text=_display_block_label(diff, group["name_cache"]),
                                icon="FILE",
                            )
                        if is_ungrouped:
                            op = row.operator(
                                "cozystudio.unstage_file", text="", icon="REMOVE"
                            )
                            op.file_path = diff["path"]
                        row.label(text=_status_abbrev(diff["status"]))

        if grouped_unstaged:
            box = layout.box()
            box.label(text="CHANGES", icon="GREASEPENCIL")
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
                                text=_display_block_label(diff, group["name_cache"]),
                                icon="FILE",
                                emboss=False,
                            )
                            op.uuid = uuid
                        else:
                            row.label(
                                text=_display_block_label(diff, group["name_cache"]),
                                icon="FILE",
                            )
                        if is_ungrouped:
                            op = row.operator(
                                "cozystudio.add_file", text="", icon="ADD"
                            )
                            op.file_path = diff["path"]
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

        if not state.git_instance or not getattr(state.git_instance, "initiated", False):
            layout.label(text="No CozyStudio repo found.")
            return

        repo = getattr(state.git_instance, "repo", None)
        if repo is None:
            layout.label(text="No repository available.")
            return

        wm = context.window_manager

        commits = []
        try:
            commits = list(repo.iter_commits(all=True, max_count=10))
        except Exception:
            commits = []

        items = wm.cozystudio_commit_items
        items.clear()
        for commit in commits:
            item = items.add()
            item.commit_hash = commit.hexsha
            item.short_hash = commit.hexsha[:8]
            item.summary = commit.message.splitlines()[0] if commit.message else "(no message)"

        if repo.head.is_detached:
            head_hash = None
            try:
                head_hash = repo.head.commit.hexsha
            except Exception:
                head_hash = None

            if head_hash:
                row = layout.row(align=True)
                row.label(text=f"Detached at {head_hash[:8]}")

                preferred = getattr(state.git_instance, "last_branch", None)
                branch_name = None
                if preferred and preferred in repo.heads:
                    branch_name = preferred
                elif "main" in repo.heads:
                    branch_name = "main"
                elif "master" in repo.heads:
                    branch_name = "master"
                elif repo.heads:
                    branch_name = repo.heads[0].name

                if branch_name:
                    op = row.operator(
                        "cozystudio.checkout_branch",
                        text="Return",
                        icon="LOOP_BACK",
                    )
                    op.branch_name = branch_name

        if not commits:
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
