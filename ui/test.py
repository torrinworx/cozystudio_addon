import bpy
from ..core.bpy_git import BpyGit
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
    bl_label = "Compare"

    def execute(self, context):
        global git_instance

        git_instance.commit()
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

        if not git_instance or not getattr(git_instance, "diffs", None):
            layout.label(text="(no diffs)")
            layout.operator("cozystudio.init_repo", text="Init")
            layout.operator("cozystudio.commit", text="Commit")
            return

        staged = [d for d in git_instance.diffs if d["status"].startswith("staged")]
        unstaged = [d for d in git_instance.diffs if not d["status"].startswith("staged")]
        
        print("STAGED: ", staged)
        print("UNSTAGED: ", unstaged)

        # --- Staged section ---
        if staged:
            box = layout.box()
            box.label(text="STAGED CHANGES", icon="CHECKMARK")
            for diff in staged:
                # Each row: filename | Unstage | Status flag
                row = box.row(align=True)
                row.label(text=diff["path"], icon="FILE")
                op = row.operator("cozystudio.unstage_file", text="", icon="REMOVE")
                op.file_path = diff["path"]
                # status marker at the end (S)
                row.label(text=_status_abbrev(diff["status"]))

        # --- Unstaged section (modified/untracked/deleted) ---
        if unstaged:
            box = layout.box()
            box.label(text="CHANGES", icon="GREASEPENCIL")
            for diff in unstaged:
                row = box.row(align=True)
                row.label(text=diff["path"], icon="FILE")
                op = row.operator("cozystudio.add_file", text="", icon="ADD")
                op.file_path = diff["path"]
                # status marker (M/U/D)
                row.label(text=_status_abbrev(diff["status"]))

        layout.separator()
        layout.operator("cozystudio.commit", text="Commit")
        if not getattr(git_instance, 'initiated', False):
            layout.operator("cozystudio.init_repo", text="Init")

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
