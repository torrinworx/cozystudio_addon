import bpy

__all__ = [
    'bl_object',
    'bl_mesh',
    'bl_camera',
    'bl_collection',
    'bl_curve',
    'bl_gpencil',
    'bl_gpencil3',
    'bl_image',
    'bl_light',
    'bl_scene',
    'bl_material',
    'bl_armature',
    'bl_action',
    'bl_world',
    'bl_metaball',
    'bl_lattice',
    'bl_lightprobe',
    'bl_speaker',
    'bl_font',
    'bl_sound',
    'bl_file',
    'bl_node_group',
    'bl_texture',
    "bl_particle",
    "bl_volume",
]  # Order here defines execution order


import importlib
def types_to_register():
    return __all__

from .replication.protocol import DataTranslationProtocol

def get_data_translation_protocol()-> DataTranslationProtocol:
    """ Return a data translation protocol from implemented bpy types
    """
    bpy_protocol = DataTranslationProtocol()
    for module_name in __all__:
        if module_name not in globals():
            impl = importlib.import_module(f".{module_name}", __package__)
        else:
            impl = globals()[module_name]
        if impl and hasattr(impl, "_type") and hasattr(impl, "_type"):
            bpy_protocol.register_implementation(impl._type, impl._class)
    return bpy_protocol
