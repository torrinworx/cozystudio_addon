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
    bpy.types.WindowManager.cozystudio_branch_name = bpy.props.StringProperty(
        name="Branch Name",
        description="Name for the new branch",
        default="",
    )
    bpy.types.WindowManager.cozystudio_branch_source = bpy.props.EnumProperty(
        name="Branch Source",
        description="Source for the new branch",
        items=[
            ("HEAD", "HEAD", "Create from current HEAD"),
            ("SELECTED", "Selected Commit", "Create from selected commit in History"),
        ],
        default="HEAD",
    )


def unregister_props():
    if hasattr(bpy.types.WindowManager, "cozystudio_commit_items"):
        del bpy.types.WindowManager.cozystudio_commit_items
    if hasattr(bpy.types.WindowManager, "cozystudio_commit_index"):
        del bpy.types.WindowManager.cozystudio_commit_index
    if hasattr(bpy.types.WindowManager, "cozystudio_commit_message"):
        del bpy.types.WindowManager.cozystudio_commit_message
    if hasattr(bpy.types.WindowManager, "cozystudio_branch_name"):
        del bpy.types.WindowManager.cozystudio_branch_name
    if hasattr(bpy.types.WindowManager, "cozystudio_branch_source"):
        del bpy.types.WindowManager.cozystudio_branch_source
