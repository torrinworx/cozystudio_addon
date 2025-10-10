import bpy

from .replication.protocol import ReplicatedDatablock
from .bl_material import (dump_node_tree,
                          load_node_tree,
                          get_node_tree_dependencies)
from .bl_datablock import resolve_datablock_from_uuid
from .bl_action import resolve_animation_dependencies


class BlNodeGroup(ReplicatedDatablock):
    use_delta = True

    bl_id = "node_groups"
    bl_class = bpy.types.NodeTree
    bl_check_common = False
    bl_icon = 'NODETREE'
    bl_reload_parent = False

    @staticmethod
    def construct(data: dict) -> object:
        return bpy.data.node_groups.new(data["name"], data["type"])

    @staticmethod
    def load(data: dict, datablock: object):
        load_node_tree(data, datablock)

    @staticmethod
    def dump(datablock: object) -> dict:
        return dump_node_tree(datablock)

    @staticmethod
    def resolve(data: dict) -> object:
        uuid = data.get('uuid')
        return resolve_datablock_from_uuid(uuid, bpy.data.node_groups)

    @staticmethod
    def resolve_deps(datablock: object) -> list[object]:
        deps = []
        deps.extend(get_node_tree_dependencies(datablock))
        deps.extend(resolve_animation_dependencies(datablock))
        return deps


_type = [bpy.types.ShaderNodeTree, bpy.types.GeometryNodeTree]
_class = BlNodeGroup
