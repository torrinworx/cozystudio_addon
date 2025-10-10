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

from .utils import get_preferences
from .replication.protocol import ReplicatedDatablock
from .dump_anything import Dumper, Loader, np_load_collection, np_dump_collection
from .bl_material import dump_materials_slots, load_materials_slots
from .bl_datablock import resolve_datablock_from_uuid
from .bl_action import (
    dump_animation_data,
    load_animation_data,
    resolve_animation_dependencies,
)


SPLINE_BEZIER_POINT = [
    # "handle_left_type",
    # "handle_right_type",
    "handle_left",
    "co",
    "handle_right",
    "tilt",
    "weight_softbody",
    "radius",
]

SPLINE_POINT = [
    "co",
    "tilt",
    "weight_softbody",
    "radius",
]

CURVE_METADATA = [
    'align_x',
    'align_y',
    'bevel_depth',
    'bevel_factor_end',
    'bevel_factor_mapping_end',
    'bevel_factor_mapping_start',
    'bevel_factor_start',
    'bevel_object',
    'bevel_resolution',
    'body',
    'body_format',
    'dimensions',
    'eval_time',
    'extrude',
    'family',
    'fill_mode',
    'follow_curve',
    'font',
    'font_bold',
    'font_bold_italic',
    'font_italic',
    'name',
    'offset',
    'offset_x',
    'offset_y',
    'overflow',
    'original',
    'override_create',
    'override_library',
    'path_duration',
    'render_resolution_u',
    'render_resolution_v',
    'resolution_u',
    'resolution_v',
    'shape_keys',
    'shear',
    'size',
    'small_caps_scale',
    'space_character',
    'space_line',
    'space_word',
    'type',
    'taper_object',
    'texspace_location',
    'texspace_size',
    'transform',
    'twist_mode',
    'twist_smooth',
    'underline_height',
    'underline_position',
    'use_auto_texspace',
    'use_deform_bounds',
    'use_fake_user',
    'use_fill_caps',
    'use_fill_deform',
    'use_map_taper',
    'use_path',
    'use_path_follow',
    'use_radius',
    'use_stretch',
]


SPLINE_METADATA = [
    'hide',
    'material_index',
    # 'order_u',
    # 'order_v',
    # 'point_count_u',
    # 'point_count_v',
    'points',
    'radius_interpolation',
    'resolution_u',
    'resolution_v',
    'tilt_interpolation',
    'type',
    'use_bezier_u',
    'use_bezier_v',
    'use_cyclic_u',
    'use_cyclic_v',
    'use_endpoint_u',
    'use_endpoint_v',
    'use_smooth',
]


class BlCurve(ReplicatedDatablock):
    use_delta = True

    bl_id = "curves"
    bl_class = bpy.types.Curve
    bl_check_common = False
    bl_icon = 'CURVE_DATA'
    bl_reload_parent = False

    @staticmethod
    def construct(data: dict) -> object:
        return bpy.data.curves.new(data["name"], data["type"])

    @staticmethod
    def load(data: dict, datablock: object):
        load_animation_data(data.get('animation_data'), datablock)

        loader = Loader()
        loader.load(datablock, data)

        datablock.splines.clear()

        # load splines
        for spline in data['splines'].values():
            new_spline = datablock.splines.new(spline['type'])

            # Load curve geometry data
            if new_spline.type == 'BEZIER':
                bezier_points = new_spline.bezier_points
                bezier_points.add(spline['bezier_points_count'])
                np_load_collection(
                    spline['bezier_points'],
                    bezier_points,
                    SPLINE_BEZIER_POINT)

            if new_spline.type in ['POLY', 'NURBS']:
                points = new_spline.points
                points.add(spline['points_count'])
                np_load_collection(spline['points'], points, SPLINE_POINT)

            loader.load(new_spline, spline)

        # MATERIAL SLOTS
        src_materials = data.get('materials', None)
        if src_materials:
            load_materials_slots(src_materials, datablock.materials)

    @staticmethod
    def dump(datablock: object) -> dict:
        dumper = Dumper()
        # Conflicting attributes
        # TODO: remove them with the NURBS support
        dumper.include_filter = CURVE_METADATA
        dumper.exclude_filter = [
            'users',
            'order_u',
            'order_v',
            'point_count_v',
            'point_count_u',
            'active_textbox'
        ]
        if datablock.use_auto_texspace:
            dumper.exclude_filter.extend([
                'texspace_location',
                'texspace_size'])
        data = dumper.dump(datablock)

        data['animation_data'] = dump_animation_data(datablock)
        data['splines'] = {}

        for index, spline in enumerate(datablock.splines):
            dumper.depth = 2
            dumper.include_filter = SPLINE_METADATA
            spline_data = dumper.dump(spline)

            spline_data['points_count'] = len(spline.points)-1
            spline_data['points'] = np_dump_collection(
                spline.points, SPLINE_POINT)

            spline_data['bezier_points_count'] = len(spline.bezier_points)-1
            spline_data['bezier_points'] = np_dump_collection(
                spline.bezier_points, SPLINE_BEZIER_POINT)
            data['splines'][index] = spline_data

        if isinstance(datablock, T.SurfaceCurve):
            data['type'] = 'SURFACE'
        elif isinstance(datablock, T.TextCurve):
            data['type'] = 'FONT'
        elif isinstance(datablock, T.Curve):
            data['type'] = 'CURVE'

        data['materials'] = dump_materials_slots(datablock.materials)

        return data

    @staticmethod
    def resolve(data: dict) -> object:
        uuid = data.get('uuid')
        return resolve_datablock_from_uuid(uuid, bpy.data.curves)

    @staticmethod
    def resolve_deps(datablock: object) -> [object]:
        # TODO: resolve material
        deps = []
        curve = datablock

        if isinstance(curve, T.TextCurve):
            deps.extend([
                curve.font,
                curve.font_bold,
                curve.font_bold_italic,
                curve.font_italic])

        for material in datablock.materials:
            if material:
                deps.append(material)

        deps.extend(resolve_animation_dependencies(datablock))

        return deps

    @staticmethod
    def needs_update(datablock: object, data: dict) -> bool:
        return 'EDIT' not in bpy.context.mode \
            or get_preferences().sync_flags.sync_during_editmode


_type = [bpy.types.Curve, bpy.types.TextCurve]
_class = BlCurve
