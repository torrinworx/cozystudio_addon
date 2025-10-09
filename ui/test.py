import bpy
from ..core.git import Git
from bpy.app.handlers import persistent

git_instance = None

class COZYSTUDIO_OT_SavePrompt(bpy.types.Operator):
    """Ask user to save the file before continuing"""
    bl_idname = "cozystudio.save_prompt"
    bl_label = "Save Blend File Required"

    def execute(self, context):
        bpy.ops.wm.save_mainfile('INVOKE_DEFAULT')
        self.report({'INFO'}, "Please save your .blend file before continuing.")
        return {'CANCELLED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_confirm(self, event)


class COZYSTUDIO_OT_PrintOperator(bpy.types.Operator):
    bl_idname = "cozystudio.compare"
    bl_label = "Compare"

    def execute(self, context):
        global git_instance

        if not bpy.data.filepath:
            bpy.ops.cozystudio.save_prompt('INVOKE_DEFAULT')
            return {'CANCELLED'}

        git_instance.init()
        return {'FINISHED'}


class COZYSTUDIO_PT_Panel(bpy.types.Panel):
    bl_label = "Cozy Studio"
    bl_idname = "COZYSTUDIO_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Cozy Studio"

    def draw(self, context):
        layout = self.layout
        layout.operator("cozystudio.compare", text="Git Compare Test")

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
    
    elif bpy.data.filepath == "":
        git_instance = None
        return None

    git_instance = Git()
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
