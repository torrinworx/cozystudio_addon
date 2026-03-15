import bpy


_BRANCH_ITEMS_CACHE = []
_INTEGRATION_ITEMS_CACHE = []


def _git_ui():
    try:
        from . import state

        return getattr(state.git_instance, "ui_state", None) or {}
    except Exception:
        return {}


def _ref_enum_items(section_names, include_current=True, include_remote=True):
    git_ui = _git_ui()
    branch_ui = git_ui.get("branch", {})
    items = []
    seen = set()

    for section_name in section_names:
        for ref in branch_ui.get(section_name, []):
            ref_type = ref.get("type") or "local"
            if ref_type == "remote" and not include_remote:
                continue
            if ref.get("is_current") and not include_current:
                continue

            token = f"{ref_type}:{ref.get('name', '')}"
            if not ref.get("name") or token in seen:
                continue
            seen.add(token)
            label = ref.get("label") or ref.get("name")
            description = ref.get("description") or label
            items.append((token, label, description))

    if not items:
        items.append(("NONE", "No refs available", "No branches or refs available"))

    return items


def branch_ref_items(_self, _context):
    global _BRANCH_ITEMS_CACHE
    _BRANCH_ITEMS_CACHE = _ref_enum_items(
        ["recent", "local", "remote"],
        include_current=True,
        include_remote=True,
    )
    return _BRANCH_ITEMS_CACHE


def integration_ref_items(_self, _context):
    global _INTEGRATION_ITEMS_CACHE
    _INTEGRATION_ITEMS_CACHE = _ref_enum_items(
        ["local", "remote"],
        include_current=False,
        include_remote=True,
    )
    return _INTEGRATION_ITEMS_CACHE


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
    bpy.types.WindowManager.cozystudio_branch_target = bpy.props.EnumProperty(
        name="Branch Target",
        description="Branch or remote ref to switch to",
        items=branch_ref_items,
    )
    bpy.types.WindowManager.cozystudio_integration_mode = bpy.props.EnumProperty(
        name="Integrate",
        description="Integrate another branch into the current branch",
        items=[
            ("MERGE", "Merge", "Merge another branch into the current branch"),
            ("REBASE", "Rebase", "Rebase the current branch onto another branch"),
        ],
        default="MERGE",
    )
    bpy.types.WindowManager.cozystudio_integration_target = bpy.props.EnumProperty(
        name="Integration Target",
        description="Branch or remote ref to merge or rebase with",
        items=integration_ref_items,
    )
    bpy.types.WindowManager.cozystudio_conflict_strategy = bpy.props.EnumProperty(
        name="Conflict Strategy",
        description="How Cozy should handle conflicting block changes",
        items=[
            ("manual", "Manual", "Stop and let you resolve conflicts"),
            ("ours", "Keep Current", "Prefer the current branch on conflict"),
            ("theirs", "Take Incoming", "Prefer the incoming branch on conflict"),
        ],
        default="manual",
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
    if hasattr(bpy.types.WindowManager, "cozystudio_branch_target"):
        del bpy.types.WindowManager.cozystudio_branch_target
    if hasattr(bpy.types.WindowManager, "cozystudio_integration_mode"):
        del bpy.types.WindowManager.cozystudio_integration_mode
    if hasattr(bpy.types.WindowManager, "cozystudio_integration_target"):
        del bpy.types.WindowManager.cozystudio_integration_target
    if hasattr(bpy.types.WindowManager, "cozystudio_conflict_strategy"):
        del bpy.types.WindowManager.cozystudio_conflict_strategy
