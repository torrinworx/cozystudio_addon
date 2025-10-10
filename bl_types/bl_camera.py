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


class BlCamera(ReplicatedDatablock):
    use_delta = True

    bl_id = "cameras"
    bl_class = bpy.types.Camera
    bl_check_common = False
    bl_icon = 'CAMERA_DATA'
    bl_reload_parent = False

    @staticmethod
    def construct(data: dict) -> object:
        return bpy.data.cameras.new(data["name"])

    @staticmethod
    def load(data: dict, datablock: object):
        loader = Loader()       
        loader.load(datablock, data)

        dof_settings = data.get('dof')

        load_animation_data(data.get('animation_data'), datablock)

        # DOF settings
        if dof_settings:
            loader.load(datablock.dof, dof_settings)

        background_images = data.get('background_images')

        datablock.background_images.clear()
        # TODO: Use image uuid
        if background_images:
            for img_name, img_data in background_images.items():
                img_id = img_data.get('image')
                if img_id:
                    target_img = datablock.background_images.new()
                    target_img.image = bpy.data.images[img_id]
                    loader.load(target_img, img_data)

                    img_user = img_data.get('image_user')
                    if img_user:
                        loader.load(target_img.image_user, img_user)

    @staticmethod
    def dump(datablock: object) -> dict:
        dumper = Dumper()
        dumper.depth = 3
        dumper.include_filter = [
            "name",
            'type',
            'lens',
            'lens_unit',
            'shift_x',
            'shift_y',
            'clip_start',
            'clip_end',
            'dof',
            'use_dof',
            'sensor_fit',
            'sensor_width',
            'focus_object',
            'focus_distance',
            'aperture_fstop',
            'aperture_blades',
            'aperture_rotation',
            'ortho_scale',
            'aperture_ratio',
            'display_size',
            'show_limits',
            'show_mist',
            'show_sensor',
            'show_name',
            'sensor_fit',
            'sensor_height',
            'sensor_width',
            'show_background_images',
            'background_images',
            'alpha',
            'display_depth',
            'frame_method',
            'offset',
            'rotation',
            'scale',
            'use_flip_x',
            'use_flip_y',
            'image_user',
            'image',
            'frame_duration',
            'frame_start',
            'frame_offset',
            'use_cyclic',
            'use_auto_refresh'
        ]
        data = dumper.dump(datablock)
        data['animation_data'] = dump_animation_data(datablock)

        for index, image in enumerate(datablock.background_images):
            if image.image_user:
                data['background_images'][index]['image_user'] = dumper.dump(image.image_user)
        return data

    @staticmethod
    def resolve(data: dict) -> object:
        uuid = data.get('uuid')
        return resolve_datablock_from_uuid(uuid, bpy.data.cameras)

    @staticmethod
    def resolve_deps(datablock: object) -> list[object]:
        deps = []
        for background in datablock.background_images:
            if background.image:
                deps.append(background.image)

        deps.extend(resolve_animation_dependencies(datablock))

        return deps


_type = bpy.types.Camera
_class = BlCamera
