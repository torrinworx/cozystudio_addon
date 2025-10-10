# ##### BEGIN GPL LICENSE BLOCK #####
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####


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
