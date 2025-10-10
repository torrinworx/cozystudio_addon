import bpy

_bl_types = [
    {"name": "scenes", "bl_class": bpy.types.Scene, "properties": ["frame_start", "frame_end", "render"]},
    {"name": "collections", "bl_class": bpy.types.Collection, "properties": ["hide_render", "hide_select", "hide_viewport"]},
    {"name": "objects", "bl_class": bpy.types.Object, "properties": ["location", "rotation_euler", "scale", "data", "material_slots"]},
    {"name": "meshes", "bl_class": bpy.types.Mesh, "properties": ["vertices", "edges", "polygons"]},
    {"name": "materials", "bl_class": bpy.types.Material, "properties": ["diffuse_color", "use_nodes", "node_tree"]},
    {"name": "images", "bl_class": bpy.types.Image, "properties": []},
    {"name": "worlds", "bl_class": bpy.types.World, "properties": []},
    {"name": "cameras", "bl_class": bpy.types.Camera, "properties": ["lens", "sensor_width", "sensor_height"]},
    {"name": "lights", "bl_class": bpy.types.Light, "properties": ["color", "energy", "type"]},
    {"name": "curves", "bl_class": bpy.types.Curve, "properties": []},
    {"name": "armatures", "bl_class": bpy.types.Armature, "properties": []},
    {"name": "actions", "bl_class": bpy.types.Action, "properties": []},
    {"name": "node_groups", "bl_class": bpy.types.NodeTree, "properties": []},
]
