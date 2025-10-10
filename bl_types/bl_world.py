import bpy
from .replication.protocol import ReplicatedDatablock

from .bl_action import (dump_animation_data, load_animation_data,
                        resolve_animation_dependencies)
from .bl_datablock import resolve_datablock_from_uuid
from .bl_material import (dump_node_tree, get_node_tree_dependencies,
                          load_node_tree)
from .dump_anything import Dumper, Loader


class BlWorld(ReplicatedDatablock):
    use_delta = True

    bl_id = "worlds"
    bl_class = bpy.types.World
    bl_check_common = True
    bl_icon = 'WORLD_DATA'
    bl_reload_parent = False

    @staticmethod
    def construct(data: dict) -> object:
        return bpy.data.worlds.new(data["name"])

    @staticmethod
    def load(data: dict, datablock: object):
        load_animation_data(data.get('animation_data'), datablock)
        loader = Loader()
        loader.load(datablock, data)

        if data["use_nodes"]:
            if datablock.node_tree is None:
                datablock.use_nodes = True

            load_node_tree(data['node_tree'], datablock.node_tree)

    @staticmethod
    def dump(datablock: object) -> dict:
        world_dumper = Dumper()
        world_dumper.depth = 1
        world_dumper.include_filter = [
            "use_nodes",
            "name",
            "color"
        ]
        data = world_dumper.dump(datablock)
        if datablock.use_nodes:
            data['node_tree'] = dump_node_tree(datablock.node_tree)

        data['animation_data'] = dump_animation_data(datablock)
        return data

    @staticmethod
    def resolve(data: dict) -> object:
        uuid = data.get('uuid')
        return resolve_datablock_from_uuid(uuid, bpy.data.worlds)

    @staticmethod
    def resolve_deps(datablock: object) -> list[object]:
        deps = []

        if datablock.use_nodes:
            deps.extend(get_node_tree_dependencies(datablock.node_tree))

        deps.extend(resolve_animation_dependencies(datablock))
        return deps


_type = bpy.types.World
_class = BlWorld
