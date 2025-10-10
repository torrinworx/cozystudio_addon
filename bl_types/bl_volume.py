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
from pathlib import Path

from .dump_anything import Loader, Dumper
from .replication.protocol import ReplicatedDatablock
from .bl_datablock import resolve_datablock_from_uuid
from .bl_material import dump_materials_slots, load_materials_slots
from .bl_action import (
    dump_animation_data,
    load_animation_data,
    resolve_animation_dependencies,
)


class BlVolume(ReplicatedDatablock):
    use_delta = True

    bl_id = "volumes"
    bl_class = bpy.types.Volume
    bl_check_common = False
    bl_icon = 'VOLUME_DATA'
    bl_reload_parent = False

    @staticmethod
    def construct(data: dict) -> object:
        return bpy.data.volumes.new(data["name"])

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
            'use_fake_user',
            'session_uid',
            'velocity_grid'  # Not correctly initialized by Blender(TODO: check if it's a bug)
        ]

        data = dumper.dump(datablock)

        data['display'] = dumper.dump(datablock.display)

        # Fix material index
        data['materials'] = dump_materials_slots(datablock.materials)
        data['animation_data'] = dump_animation_data(datablock)
        return data

    @staticmethod
    def load(data: dict, datablock: object):
        load_animation_data(data.get('animation_data'), datablock)
        loader = Loader()
        loader.load(datablock, data)
        loader.load(datablock.display, data['display'])

        # MATERIAL SLOTS
        src_materials = data.get('materials', None)
        if src_materials:
            load_materials_slots(src_materials, datablock.materials)

    @staticmethod
    def resolve(data: dict) -> object:
        uuid = data.get('uuid')
        return resolve_datablock_from_uuid(uuid, bpy.data.volumes)

    @staticmethod
    def resolve_deps(datablock: object) -> list[object]:
        # TODO: resolve material
        deps = []

        external_vdb = Path(bpy.path.abspath(datablock.filepath))
        if external_vdb.exists() and not external_vdb.is_dir():
            deps.append(external_vdb)

        for material in datablock.materials:
            if material:
                deps.append(material)

        deps.extend(resolve_animation_dependencies(datablock))

        return deps


_type = bpy.types.Volume
_class = BlVolume
