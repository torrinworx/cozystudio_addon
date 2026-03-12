from pathlib import Path

import bpy
from bpy.app.handlers import persistent

from ..utils.redraw import redraw

git_instance = None
_bpy_git_import_error = None
_group_expanded = set()


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
        return 0.5

    if not bpy.data.filepath:
        return 0.5

    current_path = Path(bpy.path.abspath("//")).resolve()
    if git_instance is not None and current_path.exists():
        try:
            if getattr(git_instance, "path", None) != current_path:
                git_instance = None
        except Exception:
            git_instance = None

    if git_instance is None:
        try:
            from ..bl_git import BpyGit
        except Exception as e:
            _bpy_git_import_error = e
            return 0.5

        git_instance = BpyGit()

    try:
        if git_instance:
            redraw("COZYSTUDIO_PT_log")
    except Exception:
        pass
    return None


@persistent
def init_git_on_load(_dummy=None):
    bpy.app.timers.register(check_and_init_git, first_interval=0.5)


def reset_state():
    global git_instance
    global _bpy_git_import_error

    git_instance = None
    _bpy_git_import_error = None
    _group_expanded.clear()
