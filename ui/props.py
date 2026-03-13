import bpy


class COZYSTUDIO_CommitItem(bpy.types.PropertyGroup):
    commit_hash: bpy.props.StringProperty()
    short_hash: bpy.props.StringProperty()
    summary: bpy.props.StringProperty()
    is_head: bpy.props.BoolProperty(default=False)


def register_props():
    bpy.types.WindowManager.cozystudio_commit_items = bpy.props.CollectionProperty(
        type=COZYSTUDIO_CommitItem
    )
    bpy.types.WindowManager.cozystudio_commit_index = bpy.props.IntProperty(default=0)
    bpy.types.WindowManager.cozystudio_commit_message = bpy.props.StringProperty(
        name="Commit Message",
        description="Message for this commit",
        default="",
    )
    bpy.types.WindowManager.cozystudio_advanced_mode = bpy.props.BoolProperty(
        name="Advanced Mode",
        description="Show raw Git-oriented details in the Cozy Studio UI",
        default=False,
    )


def unregister_props():
    if hasattr(bpy.types.WindowManager, "cozystudio_commit_items"):
        del bpy.types.WindowManager.cozystudio_commit_items
    if hasattr(bpy.types.WindowManager, "cozystudio_commit_index"):
        del bpy.types.WindowManager.cozystudio_commit_index
    if hasattr(bpy.types.WindowManager, "cozystudio_commit_message"):
        del bpy.types.WindowManager.cozystudio_commit_message
    if hasattr(bpy.types.WindowManager, "cozystudio_advanced_mode"):
        del bpy.types.WindowManager.cozystudio_advanced_mode
