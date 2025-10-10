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
import bpy.types as T
from .replication.protocol import ReplicatedDatablock

from .bl_action import (dump_animation_data, load_animation_data,
                        resolve_animation_dependencies)
from .bl_datablock import resolve_datablock_from_uuid
from .dump_anything import Dumper, Loader


class BlTexture(ReplicatedDatablock):
    use_delta = True

    bl_id = "textures"
    bl_class = bpy.types.Texture
    bl_check_common = False
    bl_icon = 'TEXTURE'
    bl_reload_parent = False

    @staticmethod
    def load(data: dict, datablock: object):
        loader = Loader()
        loader.load(datablock, data)
        load_animation_data(data.get('animation_data'), datablock)

    @staticmethod
    def construct(data: dict) -> object:
        return bpy.data.textures.new(data["name"], data["type"])

    @staticmethod
    def dump(datablock: object) -> dict:

        dumper = Dumper()
        dumper.depth = 1
        dumper.exclude_filter = [
            'tag',
            'original',
            'users',
            'uuid',
            'is_embedded_data',
            'is_evaluated',
            'name_full',
            'session_uid',
        ]

        data = dumper.dump(datablock)

        color_ramp = getattr(datablock, 'color_ramp', None)

        if color_ramp:
            dumper.depth = 4
            data['color_ramp'] = dumper.dump(color_ramp)

        data['animation_data'] = dump_animation_data(datablock)
        return data

    @staticmethod
    def resolve(data: dict) -> object:
        uuid = data.get('uuid')
        return resolve_datablock_from_uuid(uuid, bpy.data.textures)

    @staticmethod
    def resolve_deps(datablock: object) -> list[object]:
        deps = []

        image = getattr(datablock, "image", None)

        if image:
            deps.append(image)

        deps.extend(resolve_animation_dependencies(datablock))

        return deps


_type = [T.WoodTexture, T.VoronoiTexture,
         T.StucciTexture, T.NoiseTexture,
         T.MusgraveTexture, T.MarbleTexture,
         T.MagicTexture, T.ImageTexture,
         T.DistortedNoiseTexture, T.CloudsTexture,
         T.BlendTexture]
_class = BlTexture
