import bpy
from .core.bpy_git import BpyGit
from bpy.app.handlers import persistent

git_instance = None


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
        diffs = getattr(git_instance, "diffs", None)
        staged = [d for d in diffs if d["status"].startswith("staged")]
        unstaged = [d for d in diffs if not d["status"].startswith("staged")]

        # --- Staged section ---
        if staged:
            box = layout.box()
            box.label(text="STAGED CHANGES", icon="CHECKMARK")
            for diff in staged:
                row = box.row(align=True)
                row.label(text=diff["path"], icon="FILE")
                op = row.operator("cozystudio.unstage_file", text="", icon="REMOVE")
                op.file_path = diff["path"]
                row.label(text=_status_abbrev(diff["status"]))

        # --- Unstaged section ---
        if unstaged:
            box = layout.box()
            box.label(text="CHANGES", icon="GREASEPENCIL")
            for diff in unstaged:
                row = box.row(align=True)
                row.label(text=diff["path"], icon="FILE")
                op = row.operator("cozystudio.add_file", text="", icon="ADD")
                op.file_path = diff["path"]
                row.label(text=_status_abbrev(diff["status"]))

        layout.separator()
        layout.operator("cozystudio.commit", text="Commit")

        layout.label(text="Test Checkout")
        checkout_row = layout.row(align=True)
        checkout_row.operator("cozystudio.checkout_commit", text="Checkout Commit", icon="FILE_REFRESH")

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


def is_data_restricted():
    try:
        _ = bpy.data.filepath
        return False
    except AttributeError:
        return True


def check_and_init_git():
    global git_instance

    if is_data_restricted():
        # Still restricted, reschedule to try again in 0.5 seconds
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
