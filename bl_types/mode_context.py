from contextlib import contextmanager

import bpy


def resolve_owner_object(datablock):
    if isinstance(datablock, bpy.types.Object):
        return datablock

    for obj in bpy.data.objects:
        if getattr(obj, "data", None) == datablock:
            return obj

    return None


def _mode_operator_name(mode):
    if not mode:
        return "OBJECT"
    if mode.startswith("EDIT"):
        return "EDIT"
    if mode == "PAINT_VERTEX":
        return "VERTEX_PAINT"
    if mode == "PAINT_WEIGHT":
        return "WEIGHT_PAINT"
    if mode == "PAINT_TEXTURE":
        return "TEXTURE_PAINT"
    return mode


@contextmanager
def mode_session(datablock, policy, interactive):
    if not interactive or not policy or policy.get("state") != "requires_mode_switch":
        yield
        return

    view_layer = bpy.context.view_layer
    owner = resolve_owner_object(datablock)
    if view_layer is None or owner is None or owner.name not in view_layer.objects:
        yield
        return

    previous_active = view_layer.objects.active
    previous_mode = bpy.context.mode
    previous_selection = {
        obj.name: obj.select_get()
        for obj in view_layer.objects
    }

    try:
        if bpy.context.mode != "OBJECT" and previous_active and previous_active != owner:
            bpy.ops.object.mode_set(mode="OBJECT")

        owner.select_set(True)
        view_layer.objects.active = owner

        target_mode = _mode_operator_name(policy.get("mode"))
        if target_mode and _mode_operator_name(bpy.context.mode) != target_mode:
            bpy.ops.object.mode_set(mode=target_mode)

        yield
    finally:
        for obj in view_layer.objects:
            obj.select_set(previous_selection.get(obj.name, False))

        if previous_active and previous_active.name in view_layer.objects:
            previous_active.select_set(True)
            view_layer.objects.active = previous_active

        restore_mode = _mode_operator_name(previous_mode)
        if restore_mode and previous_active and _mode_operator_name(bpy.context.mode) != restore_mode:
            bpy.ops.object.mode_set(mode=restore_mode)
