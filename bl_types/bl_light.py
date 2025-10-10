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

from .bl_action import (dump_animation_data, load_animation_data,
                        resolve_animation_dependencies)
from .bl_datablock import resolve_datablock_from_uuid
from .dump_anything import Dumper, Loader


class BlLight(ReplicatedDatablock):
    use_delta = True

    bl_id = "lights"
    bl_class = bpy.types.Light
    bl_check_common = False
    bl_icon = 'LIGHT_DATA'
    bl_reload_parent = False

    @staticmethod
    def construct(data: dict) -> object:
        instance = bpy.data.lights.new(data["name"], data["type"])
        instance.uuid = data.get("uuid")
        return instance

    @staticmethod
    def load(data: dict, datablock: object):
        loader = Loader()
        loader.load(datablock, data)
        load_animation_data(data.get('animation_data'), datablock)

    @staticmethod
    def dump(datablock: object) -> dict:
        dumper = Dumper()
        dumper.depth = 3
        dumper.include_filter = [
            "name",
            "type",
            "color",
            "energy",
            "specular_factor",
            "uuid",
            "shadow_soft_size",
            "use_custom_distance",
            "cutoff_distance",
            "use_shadow",
            "shadow_buffer_clip_start",
            "shadow_buffer_soft",
            "shadow_buffer_bias",
            "shadow_buffer_bleed_bias",
            "contact_shadow_distance",
            "contact_shadow_soft_size",
            "contact_shadow_bias",
            "contact_shadow_thickness",
            "shape",
            "size_y",
            "size",
            "angle",
            'spot_size',
            'spot_blend'
        ]
        data = dumper.dump(datablock)
        data['animation_data'] = dump_animation_data(datablock)
        return data

    @staticmethod
    def resolve(data: dict) -> object:
        uuid = data.get('uuid')
        return  resolve_datablock_from_uuid(uuid, bpy.data.lights)

    @staticmethod
    def resolve_deps(datablock: object) -> list[object]:
        deps = []

        deps.extend(resolve_animation_dependencies(datablock))

        return deps


_type = [bpy.types.SpotLight, bpy.types.PointLight, bpy.types.AreaLight, bpy.types.SunLight]
_class = BlLight
