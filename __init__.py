bl_info = {
    "name": "Cozy Studio",
    "author": "Torrin Leonard",
    "description": "",
    "blender": (4, 5, 3),
    "version": (0, 0, 1),
    "location": "",
    "warning": "",
    "category": "Generic",
}
from . import auto_load

auto_load.init()


def register():
    auto_load.register()


def unregister():
    auto_load.unregister()
