import bpy
from pathlib import Path
from bpy.app.handlers import persistent

from .utils.redraw import redraw

git_instance = None
_bpy_git_import_error = None
_group_expanded = set()


class INIT_OT_PrintOperator(bpy.types.Operator):
    bl_idname = "cozystudio.init_repo"
    bl_label = "Init"

    def execute(self, context):
        global git_instance

        if not bpy.data.filepath:
            # bpy.ops.cozystudio.save_prompt("INVOKE_DEFAULT")
            return {"CANCELLED"}

        git_instance.init()
        return {"FINISHED"}


class COMMMIT_OT_PrintOperator(bpy.types.Operator):
    bl_idname = "cozystudio.commit"
    bl_label = "Commit"

    # Add a StringProperty so the user can type into it.
    message: bpy.props.StringProperty(
        name="Commit Message",
        description="Message for this commit",
        default="",
    )

    def invoke(self, context, event):
        # Show a simple pop-up dialog to edit the message
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        # Draw the message field inside the pop-up
        layout = self.layout
        layout.prop(self, "message")

    def execute(self, context):
        global git_instance

        if not self.message.strip():
            self.report({"WARNING"}, "Commit message cannot be empty")
            return {"CANCELLED"}

        git_instance.commit(message=self.message)
        self.report({"INFO"}, f"Committed: {self.message}")
        return {"FINISHED"}
    
class COZYSTUDIO_OT_AddFile(bpy.types.Operator):
    bl_idname = "cozystudio.add_file"
    bl_label = "Add file to stage"

    file_path: bpy.props.StringProperty()

    def execute(self, context):
        global git_instance
        git_instance.stage(changes=[self.file_path])
        git_instance._update_diffs()
        return {"FINISHED"}


class COZYSTUDIO_OT_UnstageFile(bpy.types.Operator):
    bl_idname = "cozystudio.unstage_file"
    bl_label = "Unstage file"

    file_path: bpy.props.StringProperty()

    def execute(self, context):
        global git_instance
        git_instance.unstage(changes=[self.file_path])
        git_instance._update_diffs()
        return {"FINISHED"}


class COZYSTUDIO_OT_AddGroup(bpy.types.Operator):
    bl_idname = "cozystudio.add_group"
    bl_label = "Add group to stage"

    group_id: bpy.props.StringProperty()

    def execute(self, context):
        global git_instance
        if not git_instance or not getattr(git_instance, "state", None):
            return {"CANCELLED"}

        group = (git_instance.state.get("groups") or {}).get(self.group_id)
        if not group:
            return {"CANCELLED"}

        members = group.get("members", [])
        paths = [f".cozystudio/blocks/{uuid}.json" for uuid in members]
        git_instance.stage(changes=paths)
        git_instance._update_diffs()
        return {"FINISHED"}


class COZYSTUDIO_OT_UnstageGroup(bpy.types.Operator):
    bl_idname = "cozystudio.unstage_group"
    bl_label = "Unstage group"

    group_id: bpy.props.StringProperty()

    def execute(self, context):
        global git_instance
        if not git_instance or not getattr(git_instance, "state", None):
            return {"CANCELLED"}

        group = (git_instance.state.get("groups") or {}).get(self.group_id)
        if not group:
            return {"CANCELLED"}

        members = group.get("members", [])
        paths = [f".cozystudio/blocks/{uuid}.json" for uuid in members]
        git_instance.unstage(changes=paths)
        git_instance._update_diffs()
        return {"FINISHED"}


class COZYSTUDIO_OT_ToggleGroupExpanded(bpy.types.Operator):
    bl_idname = "cozystudio.toggle_group_expanded"
    bl_label = "Toggle group"

    group_id: bpy.props.StringProperty()

    def execute(self, context):
        if self.group_id in _group_expanded:
            _group_expanded.remove(self.group_id)
        else:
            _group_expanded.add(self.group_id)
        return {"FINISHED"}


class COZYSTUDIO_OT_CheckoutCommit(bpy.types.Operator):
    """Checkout a specific commit hash"""
    bl_idname = "cozystudio.checkout_commit"
    bl_label = "Checkout Commit"

    commit_hash: bpy.props.StringProperty(
        name="Commit Hash",
        description="Enter git commit hash to checkout",
        default="",
    )

    def execute(self, context):
        global git_instance

        if not git_instance or not getattr(git_instance, "initiated", False):
            self.report({"ERROR"}, "No CozyStudio Git repo initialized.")
            return {"CANCELLED"}

        if not self.commit_hash.strip():
            self.report({"WARNING"}, "Please enter a commit hash.")
            return {"CANCELLED"}

        try:
            print(f"[CozyStudio] Checking out commit {self.commit_hash}")
            git_instance.checkout(self.commit_hash)
            self.report({"INFO"}, f"Checked out commit {self.commit_hash[:8]}...")
        except Exception as e:
            self.report({"ERROR"}, f"Checkout failed: {e}")
            import traceback
            traceback.print_exc()
            return {"CANCELLED"}

        return {"FINISHED"}


class COZYSTUDIO_OT_CheckoutBranch(bpy.types.Operator):
    """Checkout a branch"""
    bl_idname = "cozystudio.checkout_branch"
    bl_label = "Checkout Branch"

    branch_name: bpy.props.StringProperty(
        name="Branch",
        description="Branch name to checkout",
        default="",
    )

    def execute(self, context):
        global git_instance

        if not git_instance or not getattr(git_instance, "initiated", False):
            self.report({"ERROR"}, "No CozyStudio Git repo initialized.")
            return {"CANCELLED"}

        if not self.branch_name.strip():
            self.report({"WARNING"}, "Please enter a branch name.")
            return {"CANCELLED"}

        try:
            git_instance.repo.git.checkout(self.branch_name)
            self.report({"INFO"}, f"Checked out {self.branch_name}")
        except Exception as e:
            self.report({"ERROR"}, f"Checkout failed: {e}")
            import traceback
            traceback.print_exc()
            return {"CANCELLED"}

        return {"FINISHED"}


class COZYSTUDIO_OT_SelectBlock(bpy.types.Operator):
    bl_idname = "cozystudio.select_block"
    bl_label = "Select datablock"

    uuid: bpy.props.StringProperty()

    def execute(self, context):
        global git_instance

        if not git_instance or not getattr(git_instance, "initiated", False):
            return {"CANCELLED"}

        if not self.uuid:
            return {"CANCELLED"}

        datablock = None
        for _type_name, impl_class in git_instance.bpy_protocol.implementations.items():
            data_collection = getattr(bpy.data, impl_class.bl_id, None)
            if not data_collection:
                continue
            for block in data_collection:
                if getattr(block, "cozystudio_uuid", None) == self.uuid:
                    datablock = block
                    break
            if datablock is not None:
                break

        if datablock is None:
            return {"CANCELLED"}

        if context.view_layer:
            for obj in context.view_layer.objects:
                obj.select_set(False)

        selected = []
        if isinstance(datablock, bpy.types.Object):
            datablock.select_set(True)
            selected = [datablock]
        else:
            for obj in bpy.data.objects:
                if getattr(obj, "data", None) == datablock:
                    obj.select_set(True)
                    selected.append(obj)
                    continue
                materials = getattr(getattr(obj, "data", None), "materials", None)
                if materials and datablock in materials:
                    obj.select_set(True)
                    selected.append(obj)

        if selected and context.view_layer:
            context.view_layer.objects.active = selected[0]

        return {"FINISHED"}


class COZYSTUDIO_UL_CommitList(bpy.types.UIList):
    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        filter_text = (self.filter_name or "").strip().lower()

        flt_flags = [self.bitflag_filter_item] * len(items)
        if filter_text:
            for idx, item in enumerate(items):
                haystack = f"{item.commit_hash} {item.summary}".lower()
                if filter_text not in haystack:
                    flt_flags[idx] = 0

        if self.use_filter_invert:
            flt_flags = [
                0 if flag == self.bitflag_filter_item else self.bitflag_filter_item
                for flag in flt_flags
            ]

        flt_neworder = []
        if self.use_filter_sort_alpha:
            flt_neworder = sorted(
                range(len(items)),
                key=lambda i: (items[i].summary or "").lower(),
            )

        return flt_flags, flt_neworder

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        split = layout.split(factor=0.86, align=True)
        split.label(text=f"{item.short_hash}  {item.summary}")
        op = split.operator(
            "cozystudio.checkout_commit", text="", icon="FILE_REFRESH", emboss=True
        )
        op.commit_hash = item.commit_hash


class MAIN_PT_Panel(bpy.types.Panel):
    bl_label = "Changes"
    bl_idname = "COZYSTUDIO_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cozy Studio"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        global git_instance

        # Handle uninitialized repo case
        if not git_instance or not getattr(git_instance, "initiated", False):
            layout.label(text="No CozyStudio repo found.")
            layout.operator("cozystudio.init_repo", text="Init Repository")
            return

        # Already initialized: show diffs if any
        diffs = getattr(git_instance, "diffs", None) or []
        staged = [d for d in diffs if d["status"].startswith("staged")]
        unstaged = [d for d in diffs if not d["status"].startswith("staged")]

        grouped_staged = _group_diffs(git_instance, staged)
        grouped_unstaged = _group_diffs(git_instance, unstaged)

        # --- Staged section ---
        if grouped_staged:
            box = layout.box()
            box.label(text="STAGED CHANGES", icon="CHECKMARK")
            for group in grouped_staged:
                group_box = box.box()
                header = group_box.row(align=True)
                group_id = group.get("group_id")
                is_ungrouped = group_id is None
                if not is_ungrouped:
                    expanded = group_id in _group_expanded
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
                                text=_display_block_label(
                                    diff, group["name_cache"]
                                ),
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

        # --- Unstaged section ---
        if grouped_unstaged:
            box = layout.box()
            box.label(text="CHANGES", icon="GREASEPENCIL")
            for group in grouped_unstaged:
                group_box = box.box()
                header = group_box.row(align=True)
                group_id = group.get("group_id")
                is_ungrouped = group_id is None
                if not is_ungrouped:
                    expanded = group_id in _group_expanded
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
                                text=_display_block_label(
                                    diff, group["name_cache"]
                                ),
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
        global git_instance

        if not git_instance or not getattr(git_instance, "initiated", False):
            layout.label(text="No CozyStudio repo found.")
            return

        repo = getattr(git_instance, "repo", None)
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

                preferred = getattr(git_instance, "last_branch", None)
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

# Helper to display short status labels
def _status_abbrev(status: str) -> str:
    base = status.removeprefix("staged_")
    abbrevs = {
        "added": "A",
        "modified": "M",
        "deleted": "D",
        "renamed": "R",
        "copied": "C",
        "untracked": "U",
        "typechange": "T",
    }
    letter = abbrevs.get(base, "?")
    return f"S:{letter}" if status.startswith("staged_") else letter


def _extract_block_uuid(path: str) -> str | None:
    if not path:
        return None
    if not path.startswith(".cozystudio/blocks/") or not path.endswith(".json"):
        return None
    try:
        return Path(path).stem
    except Exception:
        return None


def _build_name_cache(git_instance, entries):
    name_cache = {}
    if not git_instance or not entries:
        return name_cache

    for _type_name, impl_class in git_instance.bpy_protocol.implementations.items():
        data_collection = getattr(bpy.data, impl_class.bl_id, None)
        if not data_collection:
            continue
        for datablock in data_collection:
            uuid = getattr(datablock, "cozystudio_uuid", None)
            if not uuid or uuid not in entries:
                continue
            if uuid not in name_cache:
                name_cache[uuid] = getattr(datablock, "name", None) or uuid

    return name_cache


def _group_label(group_id, group_meta, name_cache):
    group_type = (group_meta or {}).get("type", "group")
    root_uuid = (group_meta or {}).get("root", group_id)
    name = name_cache.get(root_uuid) or root_uuid or "Group"

    if group_type == "object":
        prefix = "Object"
    elif group_type == "shared":
        prefix = "Shared"
    elif group_type == "orphan":
        prefix = "Orphan"
    else:
        prefix = "Group"

    return f"{prefix}: {name}"


def _display_block_label(diff, name_cache):
    uuid = diff.get("uuid")
    entry_type = diff.get("entry_type")
    name = name_cache.get(uuid) or uuid or diff.get("path")
    if entry_type:
        return f"{name} ({entry_type})"
    return name


def _group_diffs(git_instance, diffs):
    entries = (git_instance.state or {}).get("entries", {}) if git_instance else {}
    groups = (git_instance.state or {}).get("groups", {}) if git_instance else {}
    name_cache = _build_name_cache(git_instance, entries)

    grouped = {}
    ungrouped = []

    for diff in diffs:
        path = diff.get("path", "")
        uuid = _extract_block_uuid(path)
        if not uuid or uuid not in entries:
            ungrouped.append(diff)
            continue

        group_id = entries[uuid].get("group_id") or uuid
        entry_type = entries[uuid].get("type")
        group = grouped.setdefault(
            group_id,
            {"group": groups.get(group_id), "diffs": []},
        )
        group["diffs"].append({**diff, "uuid": uuid, "entry_type": entry_type})

    grouped_list = []
    for group_id, data in grouped.items():
        group_meta = data.get("group")
        group_members = (group_meta or {}).get("members", [])
        member_total = len(group_members) if group_members else len(data["diffs"])
        label = _group_label(group_id, group_meta, name_cache)
        if member_total >= len(data["diffs"]):
            label = f"{label} ({len(data['diffs'])}/{member_total})"
        else:
            label = f"{label} ({len(data['diffs'])})"

        grouped_list.append(
            {
                "group_id": group_id,
                "label": label,
                "diffs": sorted(data["diffs"], key=lambda d: d.get("path", "")),
                "name_cache": name_cache,
            }
        )

    if ungrouped:
        enriched = []
        for diff in ungrouped:
            path = diff.get("path", "")
            uuid = _extract_block_uuid(path)
            entry_type = entries.get(uuid, {}).get("type") if uuid else None
            enriched.append({**diff, "uuid": uuid, "entry_type": entry_type})
        grouped_list.append(
            {
                "group_id": None,
                "label": f"Ungrouped ({len(enriched)})",
                "diffs": sorted(enriched, key=lambda d: d.get("path", "")),
                "name_cache": name_cache,
            }
        )

    grouped_list.sort(key=lambda g: g.get("label", ""))
    return grouped_list


def is_data_restricted():
    try:
        _ = bpy.data.filepath
        return False
    except AttributeError:
        return True


def check_and_init_git():
    global git_instance
    global _bpy_git_import_error

    if is_data_restricted():
        # Still restricted, reschedule to try again in 0.5 seconds
        return 0.5

    if not bpy.data.filepath:
        return 0.5

    current_path = Path(bpy.path.abspath("//")).resolve()
    if git_instance is not None and current_path.exists():
        try:
            if getattr(git_instance, "path", None) != current_path:
                git_instance = None
        except Exception:
            git_instance = None

    if git_instance is None:
        try:
            from .core.bpy_git import BpyGit
        except Exception as e:
            _bpy_git_import_error = e
            return 0.5

        git_instance = BpyGit()

    try:
        if git_instance:
            redraw("COZYSTUDIO_PT_log")
    except Exception:
        pass
    return None


@persistent
def init_git_on_load(_dummy=None):
    bpy.app.timers.register(check_and_init_git, first_interval=0.5)


def register():
    # Ensure Git will be (re)initialized if a .blend file is already open
    bpy.app.timers.register(check_and_init_git)

    # Also ensure future file loads re-init Git by adding a load_post handler
    if init_git_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(init_git_on_load)

    bpy.types.WindowManager.cozystudio_commit_items = bpy.props.CollectionProperty(
        type=COZYSTUDIO_CommitItem
    )
    bpy.types.WindowManager.cozystudio_commit_index = bpy.props.IntProperty(
        default=0
    )


def unregister():
    if init_git_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(init_git_on_load)

    if hasattr(bpy.types.WindowManager, "cozystudio_commit_items"):
        del bpy.types.WindowManager.cozystudio_commit_items
    if hasattr(bpy.types.WindowManager, "cozystudio_commit_index"):
        del bpy.types.WindowManager.cozystudio_commit_index

    global git_instance
    git_instance = None


class COZYSTUDIO_CommitItem(bpy.types.PropertyGroup):
    commit_hash: bpy.props.StringProperty()
    short_hash: bpy.props.StringProperty()
    summary: bpy.props.StringProperty()
