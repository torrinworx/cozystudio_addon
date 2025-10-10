import bpy
from .replication.protocol import ReplicatedDatablock

from .bl_action import (dump_animation_data, load_animation_data,
                        resolve_animation_dependencies)
from .bl_datablock import resolve_datablock_from_uuid
from .dump_anything import Dumper, Loader


class BlSpeaker(ReplicatedDatablock):
    use_delta = True

    bl_id = "speakers"
    bl_class = bpy.types.Speaker
    bl_check_common = False
    bl_icon = 'SPEAKER'
    bl_reload_parent = False

    @staticmethod
    def load(data: dict, datablock: object):
        loader = Loader()
        loader.load(datablock, data)
        load_animation_data(data.get('animation_data'), datablock)

    @staticmethod
    def construct(data: dict) -> object:
        return bpy.data.speakers.new(data["name"])

    @staticmethod
    def dump(datablock: object) -> dict:
        dumper = Dumper()
        dumper.depth = 1
        dumper.include_filter = [
            "muted",
            'volume',
            'name',
            'pitch',
            'sound',
            'volume_min',
            'volume_max',
            'attenuation',
            'distance_max',
            'distance_reference',
            'cone_angle_outer',
            'cone_angle_inner',
            'cone_volume_outer'
        ]

        data = dumper.dump(datablock)
        data['animation_data'] = dump_animation_data(datablock)
        return data

    @staticmethod
    def resolve(data: dict) -> object:
        uuid = data.get('uuid')
        return resolve_datablock_from_uuid(uuid, bpy.data.speakers)

    @staticmethod
    def resolve_deps(datablock: object) -> list[object]:
        # TODO: resolve material
        deps = []

        sound = datablock.sound

        if sound:
            deps.append(sound)

        deps.extend(resolve_animation_dependencies(datablock))
        return deps


_type = bpy.types.Speaker
_class = BlSpeaker
