import bpy

from .props import register_props, unregister_props
from .state import check_and_init_git, init_git_on_load, reset_state


def register():
    bpy.app.timers.register(check_and_init_git)

    if init_git_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(init_git_on_load)

    register_props()


def unregister():
    if init_git_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(init_git_on_load)

    unregister_props()
    reset_state()
