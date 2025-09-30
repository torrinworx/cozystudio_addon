# ui/panel.py
import bpy
from ..core.logic import say_hello

class MYADDON_OT_hello(bpy.types.Operator):
    """Simple operator that calls core logic"""
    bl_idname = "myaddon.hello"
    bl_label = "Say Hello"

    def execute(self, context):
        say_hello()  # <-- calls core function!
        self.report({'INFO'}, "Hello printed in system console")
        return {'FINISHED'}

class MYADDON_PT_main(bpy.types.Panel):
    """UI panel with a hello button"""
    bl_label = "My Addon"
    bl_idname = "MYADDON_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "My Addon"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Hello World Example")
        layout.operator("myaddon.hello", text="Say Hello")
