import bpy

from .replication.exception import ContextError
from .replication.protocol import ReplicatedDatablock
from .bl_action import (dump_animation_data, load_animation_data,
                        resolve_animation_dependencies)
from .bl_datablock import resolve_datablock_from_uuid
from .dump_anything import (Dumper, Loader, np_dump_collection,
                            np_load_collection)

POINT = ['co', 'weight_softbody', 'co_deform']


class BlLattice(ReplicatedDatablock):
    use_delta = True

    bl_id = "lattices"
    bl_class = bpy.types.Lattice
    bl_check_common = False
    bl_icon = 'LATTICE_DATA'
    bl_reload_parent = False

    @staticmethod
    def construct(data: dict) -> object:
        return bpy.data.lattices.new(data["name"])

    @staticmethod
    def load(data: dict, datablock: object):
        load_animation_data(data.get('animation_data'), datablock)
        if datablock.is_editmode:
            raise ContextError("lattice is in edit mode")

        loader = Loader()
        loader.load(datablock, data)

        np_load_collection(data['points'], datablock.points, POINT)

    @staticmethod
    def dump(datablock: object) -> dict:
        if datablock.is_editmode:
            raise ContextError("lattice is in edit mode")

        dumper = Dumper()
        dumper.depth = 1
        dumper.include_filter = [
            "name",
            'type',
            'points_u',
            'points_v',
            'points_w',
            'interpolation_type_u',
            'interpolation_type_v',
            'interpolation_type_w',
            'use_outside'
        ]
        data = dumper.dump(datablock)

        data['points'] = np_dump_collection(datablock.points, POINT)
        data['animation_data'] = dump_animation_data(datablock)
        return data

    @staticmethod
    def resolve(data: dict) -> object:
        uuid = data.get('uuid')
        return resolve_datablock_from_uuid(uuid, bpy.data.lattices)

    @staticmethod
    def resolve_deps(datablock: object) -> list[object]:
        return resolve_animation_dependencies(datablock)


_type = bpy.types.Lattice
_class = BlLattice
