import bpy

from collections.abc import Iterable


def get_datablock_from_uuid(uuid, default, ignore=[]):
    if not uuid:
        return default
    for category in dir(bpy.data):
        root = getattr(bpy.data, category)
        if isinstance(root, Iterable) and category not in ignore:
            for item in root:
                item_uuid = getattr(item, "uuid", None)
                if item_uuid == uuid:
                    return item
                if getattr(item, "cozystudio_uuid", None) == uuid:
                    return item
    return default


def resolve_datablock_from_uuid(uuid, bpy_collection):
    for item in bpy_collection:
        item_uuid = getattr(item, "uuid", None)
        if item_uuid == uuid:
            return item
        if getattr(item, "cozystudio_uuid", None) == uuid:
            return item
    return None
