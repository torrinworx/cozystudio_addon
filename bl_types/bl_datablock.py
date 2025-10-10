import bpy

from collections.abc import Iterable


def get_datablock_from_uuid(uuid, default, ignore=[]):
    if not uuid:
        return default
    for category in dir(bpy.data):
        root = getattr(bpy.data, category)
        if isinstance(root, Iterable) and category not in ignore:
            for item in root:
                if getattr(item, "uuid", None) == uuid:
                    return item
    return default


def resolve_datablock_from_uuid(uuid, bpy_collection):
    for item in bpy_collection:
        if getattr(item, "uuid", None) == uuid:
            return item
    return None
