import bpy
from .replication.protocol import ReplicatedDatablock

from . import dump_anything
from .bl_action import (dump_animation_data, load_animation_data,
                        resolve_animation_dependencies)
from .bl_datablock import get_datablock_from_uuid, resolve_datablock_from_uuid

IGNORED_ATTR = [
    "is_embedded_data",
    "is_evaluated",
    "is_fluid",
    "is_library_indirect",
    "users"
]


def dump_textures_slots(texture_slots: bpy.types.bpy_prop_collection) -> list:
    """ Dump every texture slot collection as the form:
        [(index, slot_texture_uuid, slot_texture_name), (), ...]
    """
    dumped_slots = []
    for index, slot in enumerate(texture_slots):
        if slot and slot.texture:
            dumped_slots.append((index, slot.texture.uuid, slot.texture.name))

    return dumped_slots


def load_texture_slots(dumped_slots: list, target_slots: bpy.types.bpy_prop_collection):
    """
    """
    for index, slot in enumerate(target_slots):
        if slot:
            target_slots.clear(index)

    for index, slot_uuid, slot_name in dumped_slots:
        target_slots.create(index).texture = get_datablock_from_uuid(
            slot_uuid, slot_name
        )


class BlParticle(ReplicatedDatablock):
    use_delta = True

    bl_id = "particles"
    bl_class = bpy.types.ParticleSettings
    bl_icon = "PARTICLES"
    bl_check_common = False
    bl_reload_parent = False

    @staticmethod
    def construct(data: dict) -> object:
        return bpy.data.particles.new(data["name"])

    @staticmethod
    def load(data: dict, datablock: object):
        load_animation_data(data.get('animation_data'), datablock)
        dump_anything.load(datablock, data)

        dump_anything.load(datablock.effector_weights, data["effector_weights"])

        # Force field
        force_field_1 = data.get("force_field_1", None)
        if force_field_1:
            dump_anything.load(datablock.force_field_1, force_field_1)

        force_field_2 = data.get("force_field_2", None)
        if force_field_2:
            dump_anything.load(datablock.force_field_2, force_field_2)

        # Texture slots
        load_texture_slots(data["texture_slots"], datablock.texture_slots)

    @staticmethod
    def dump(datablock: object) -> dict:
        dumper = dump_anything.Dumper()
        dumper.depth = 1
        dumper.exclude_filter = IGNORED_ATTR
        data = dumper.dump(datablock)

        # Particle effectors
        data["effector_weights"] = dumper.dump(datablock.effector_weights)
        if datablock.force_field_1:
            data["force_field_1"] = dumper.dump(datablock.force_field_1)
        if datablock.force_field_2:
            data["force_field_2"] = dumper.dump(datablock.force_field_2)

        # Texture slots
        data["texture_slots"] = dump_textures_slots(datablock.texture_slots)
        data['animation_data'] = dump_animation_data(datablock)
        return data

    @staticmethod
    def resolve(data: dict) -> object:
        uuid = data.get('uuid')
        return resolve_datablock_from_uuid(uuid, bpy.data.particles)

    @staticmethod
    def resolve_deps(datablock: object) -> list[object]:
        deps = [t.texture for t in datablock.texture_slots if t and t.texture]
        deps.extend(resolve_animation_dependencies(datablock))
        return deps


_type = bpy.types.ParticleSettings
_class = BlParticle
