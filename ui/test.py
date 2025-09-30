# ui/panel.py
import bpy
from ..core.logic import say_hello


class COZYSTUDIO_OT_test(bpy.types.Operator):
    """Simple operator that calls core logic"""

    bl_idname = "cozystudio_addon.recording"
    bl_label = "Say Hello"

    def execute(self, context):
        say_hello()
        self.report({"INFO"}, "Replaying recording")
        return {"FINISHED"}


class COZYSTUDIO_PT_main(bpy.types.Panel):
    """UI panel with a hello button"""

    bl_label = "Cozy Studio"
    bl_idname = "COZYSTUDIO_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cozy Studio"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Replay test")
        layout.operator("cozystudio_addon.recording", text="Replay recording")
