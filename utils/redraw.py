import bpy

def redraw(bl_idname: str):
    """
    Forces Blender to redraw the region that contains the panel
    with the given bl_idname.
    """
    # Ensure the panel class exists in bpy.types
    panel_cls = getattr(bpy.types, bl_idname, None)
    if panel_cls is None:
        print(f"[redraw_panel_by_id] No panel found with bl_idname '{bl_idname}'")
        return

    # Extract where the panel lives
    space_type = getattr(panel_cls, "bl_space_type", None)
    region_type = getattr(panel_cls, "bl_region_type", None)

    # Loop through all areas in all windows
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if space_type is None or area.type == space_type:
                for region in area.regions:
                    if region_type is None or region.type == region_type:
                        region.tag_redraw()
