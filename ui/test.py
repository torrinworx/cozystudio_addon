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


class MAIN_PT_Panel(bpy.types.Panel):
    bl_label = "Git"
    bl_idname = "COZYSTUDIO_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cozy Studio"

    def draw(self, context):
        layout = self.layout

        global git_instance
        if git_instance and getattr(git_instance, "diffs", None):
            layout.label(text="Changes")
            for diff in git_instance.diffs:
                layout.label(text=diff)
        else:
            layout.label(text="(no diffs)")

        layout.operator("cozystudio.init_repo", text="Init")
        layout.operator("cozystudio.commit", text="Commit")

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
