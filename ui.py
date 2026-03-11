import bpy
from pathlib import Path
from bpy.app.handlers import persistent

git_instance = None
_bpy_git_import_error = None


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
    
class COZYSTUDIO_OT_CheckoutCommit(bpy.types.Operator):
    """Checkout a specific commit hash (testing)"""
    bl_idname = "cozystudio.checkout_commit"
    bl_label = "Checkout Commit"

    commit_hash: bpy.props.StringProperty(
        name="Commit Hash",
        description="Enter git commit hash to checkout",
        default="",
    )

    def invoke(self, context, event):
        if self.commit_hash:
            return self.execute(context)
        # Show a popup dialog with a text field for commit hash
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "commit_hash")

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
        paths = [f".blocks/{uuid}.json" for uuid in members]
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
        paths = [f".blocks/{uuid}.json" for uuid in members]
        git_instance.unstage(changes=paths)
        git_instance._update_diffs()
        return {"FINISHED"}


class MAIN_PT_Panel(bpy.types.Panel):
    bl_label = "Git"
    bl_idname = "COZYSTUDIO_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cozy Studio"

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
                header.label(text=group["label"], icon="FILE_FOLDER")
                if group.get("group_id"):
                    op = header.operator("cozystudio.unstage_group", text="", icon="REMOVE")
                    op.group_id = group["group_id"]

                for diff in group["diffs"]:
                    row = group_box.row(align=True)
                    row.label(text=_display_block_label(diff, group["name_cache"]), icon="FILE")
                    op = row.operator("cozystudio.unstage_file", text="", icon="REMOVE")
                    op.file_path = diff["path"]
                    row.label(text=_status_abbrev(diff["status"]))

        # --- Unstaged section ---
        if grouped_unstaged:
            box = layout.box()
            box.label(text="CHANGES", icon="GREASEPENCIL")
            for group in grouped_unstaged:
                group_box = box.box()
                header = group_box.row(align=True)
                header.label(text=group["label"], icon="FILE_FOLDER")
                if group.get("group_id"):
                    op = header.operator("cozystudio.add_group", text="", icon="ADD")
                    op.group_id = group["group_id"]

                for diff in group["diffs"]:
                    row = group_box.row(align=True)
                    row.label(text=_display_block_label(diff, group["name_cache"]), icon="FILE")
                    op = row.operator("cozystudio.add_file", text="", icon="ADD")
                    op.file_path = diff["path"]
                    row.label(text=_status_abbrev(diff["status"]))

        layout.separator()
        layout.operator("cozystudio.commit", text="Commit")

        layout.label(text="Checkout")
        repo = getattr(git_instance, "repo", None)
        if repo is None:
            layout.label(text="No repository available.")
        else:
            head_hash = None
            try:
                if repo.head.is_valid():
                    head_hash = repo.head.commit.hexsha
            except Exception:
                head_hash = None

            if head_hash:
                label = f"HEAD: {head_hash[:8]}"
                if repo.head.is_detached:
                    label = f"HEAD (detached): {head_hash[:8]}"
                layout.label(text=label)

            has_changes = False
            try:
                git_instance._update_diffs()
                has_changes = bool(getattr(git_instance, "diffs", None))
            except Exception:
                has_changes = False

            if has_changes:
                layout.label(text="Uncommitted changes present", icon="ERROR")

            commits = []
            try:
                if repo.head.is_detached:
                    preferred = getattr(git_instance, "last_branch", None)
                    branch = None
                    if preferred and preferred in repo.heads:
                        branch = repo.heads[preferred]
                    elif "main" in repo.heads:
                        branch = repo.heads["main"]
                    elif "master" in repo.heads:
                        branch = repo.heads["master"]
                    elif repo.heads:
                        branch = repo.heads[0]
                    if branch:
                        commits = list(repo.iter_commits(branch.name, max_count=10))
                if not commits:
                    commits = list(repo.iter_commits(max_count=10))
            except Exception:
                commits = []

            if commits:
                for commit in commits:
                    row = layout.row(align=True)
                    summary = commit.message.splitlines()[0] if commit.message else "(no message)"
                    row.label(text=f"{commit.hexsha[:8]}  {summary}")
                    op = row.operator("cozystudio.checkout_commit", text="Checkout", icon="FILE_REFRESH")
                    op.commit_hash = commit.hexsha
            else:
                layout.label(text="No commits found.")

            checkout_row = layout.row(align=True)
            checkout_row.operator("cozystudio.checkout_commit", text="Checkout by Hash", icon="FILE_REFRESH")

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
    if not path.startswith(".blocks/") or not path.endswith(".json"):
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
        grouped_list.append(
            {
                "group_id": None,
                "label": f"Ungrouped ({len(ungrouped)})",
                "diffs": sorted(ungrouped, key=lambda d: d.get("path", "")),
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

    if git_instance is None:
        try:
            from .core.bpy_git import BpyGit
        except Exception as e:
            _bpy_git_import_error = e
            return 0.5

        git_instance = BpyGit()
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


def unregister():
    if init_git_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(init_git_on_load)

    global git_instance
    git_instance = None
