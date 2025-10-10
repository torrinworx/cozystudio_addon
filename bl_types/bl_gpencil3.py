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

from .utils import is_annotating
from .utils import get_preferences
from .bl_datablock import resolve_datablock_from_uuid
from .bl_material import dump_materials_slots, load_materials_slots
from .dump_anything import (Dumper, Loader, np_dump_collection,
                            np_load_collection, np_dump_attributes, np_load_attributes)

STROKE_POINT = [
    'co',
    'pressure',
    'strength',
    'uv_factor',
    'uv_rotation'

]

STROKE = [
    "aspect",
    "display_mode",
    "end_cap_mode",
    "hardness",
    "line_width",
    "material_index",
    "start_cap_mode",
    "uv_rotation",
    "uv_scale",
    "uv_translation",
    "vertex_color_fill",
    "use_cyclic",
    "vertex_color"
]


def dump_drawing_attributes(drawing):
    """ Dump a grease pencil drawing to a dict

        :param drawing: target grease pencil drawing
        :type drawing: bpy.types.GPencilStroke
        :return: (p_count, p_data)
    """
    return (len(drawing.points), np_dump_collection(drawing.attributes, drawing.attributes.keys()))


def load_drawing_attributes(drawing_data, drawing):
    """ Load a grease pencil drawing from a dict

        :param stroke_data: dumped grease pencil drawing
        :type stroke_data: dict
        :param drawing: target grease pencil drawing
        :type drawing: bpy.types.GPencilStroke
    """
    assert drawing and drawing_data

    # drawing.points.add(drawing_data[0])
    np_load_collection(drawing_data[1], drawing.attributes, None)

    # HACK: Temporary fix to trigger a BKE_gpencil_stroke_geometry_update to
    # fix fill issues
    # drawing.uv_scale = 1.0


def dump_frame(frame):
    """ Dump a grease pencil frame to a dict

        :param frame: target grease pencil stroke
        :type frame: bpy.types.GPencilFrame
        :return: dict
    """

    assert frame

    dumped_frame = dict()
    dumped_frame['frame_number'] = frame.frame_number
    dumped_frame['drawing'] = {
        'attributes': np_dump_attributes(frame.drawing.attributes),
        'strokes': [len(stroke.points) for stroke in frame.drawing.strokes]
    }

    return dumped_frame


def load_frame(frame_data, frame):
    """ Load a grease pencil frame from a dict

        :param frame_data: source grease pencil frame
        :type frame_data: dict
        :param frame: target grease pencil stroke
        :type frame: bpy.types.GPencilFrame
    """

    assert frame and frame_data
    assert 'attributes' in frame_data['drawing']
    assert 'strokes' in frame_data['drawing']

    # Load stroke points
    frame.drawing.add_strokes(frame_data['drawing']['strokes'])
    # frame.drawing.attributes.update()
    # Load stroke metadata
    np_load_attributes(frame.drawing.attributes, frame_data['drawing']['attributes'])


def dump_layer(layer):
    """ Dump a grease pencil layer

        :param layer: target grease pencil stroke
        :type layer: bpy.types.GPencilFrame
    """

    assert layer

    dumper = Dumper()

    dumper.include_filter = [
        'name',
        'opacity',
        'channel_color',
        'tint_color',
        'tint_factor',
        'vertex_paint_opacity',
        'radius_offset',
        'use_onion_skinning',
        'pass_index',
        # 'viewlayer_render',
        'blend_mode',
        'hide',
        'annotation_hide',
        'lock',
        'lock_frame',
        # 'lock_material',
        'use_masks',
        'use_lights',
        'use_solo_mode',
        'select',
        'show_in_front',
        # 'parent',
        # 'parent_bone',
        # 'matrix_inverse',
    ]

    dumped_layer = dumper.dump(layer)

    dumped_layer['frames'] = []

    for frame in layer.frames:
        dumped_layer['frames'].append(dump_frame(frame))

    return dumped_layer


def load_layer(layer_data, layer):
    """ Load a grease pencil layer from a dict

        :param layer_data: source grease pencil layer data
        :type layer_data: dict
        :param layer: target grease pencil stroke
        :type layer: bpy.types.GPencilFrame
    """
    # TODO: take existing data in account
    loader = Loader()
    loader.load(layer, layer_data)

    for frame_data in layer_data["frames"]:
        target_frame = layer.frames.new(frame_data['frame_number'])
        load_frame(frame_data, target_frame)


def layer_changed(datablock: object, data: dict) -> bool:
    if datablock.layers.active and \
            datablock.layers.active.name != data["active_layers"]:
        return True
    else:
        return False


def frame_changed(data: dict) -> bool:
    return bpy.context.scene.frame_current != data["eval_frame"]


class BlGpencil3(ReplicatedDatablock):
    bl_id = "grease_pencils_v3"
    bl_class = bpy.types.GreasePencilv3
    bl_check_common = False
    bl_icon = 'GREASEPENCIL'
    bl_reload_parent = False

    @staticmethod
    def construct(data: dict) -> object:
        return bpy.data.grease_pencils_v3.new(data["name"])

    @staticmethod
    def load(data: dict, datablock: object):
        # MATERIAL SLOTS
        src_materials = data.get('materials', None)
        if src_materials:
            load_materials_slots(src_materials, datablock.materials)

        loader = Loader()
        loader.load(datablock, data)

        # TODO: reuse existing layer
        for layer in datablock.layers:
            datablock.layers.remove(layer)

        if "layers" in data.keys():
            for layer in data["layers"]:
                layer_data = data["layers"].get(layer)

                # if layer not in datablock.layers.keys():
                target_layer = datablock.layers.new(data["layers"][layer]["name"])
                # else:
                #     target_layer = target.layers[layer]
                #     target_layer.clear()

                load_layer(layer_data, target_layer)

            datablock.layers.update()

    @staticmethod
    def dump(datablock: object) -> dict:
        dumper = Dumper()
        dumper.depth = 2
        dumper.include_filter = [
            'name',
            'zdepth_offset',
            'stroke_depth_order'
        ]
        data = dumper.dump(datablock)
        data['materials'] = dump_materials_slots(datablock.materials)
        data['layers'] = {}

        for layer in datablock.layers:
            data['layers'][layer.name] = dump_layer(layer)

        data["active_layers"] = datablock.layers.active.name if datablock.layers.active else "None"
        data["eval_frame"] = bpy.context.scene.frame_current
        return data

    @staticmethod
    def resolve(data: dict) -> object:
        uuid = data.get('uuid')
        return resolve_datablock_from_uuid(uuid, bpy.data.grease_pencils)

    @staticmethod
    def resolve_deps(datablock: object) -> list[object]:
        deps = []

        for material in datablock.materials:
            deps.append(material)

        return deps

    @staticmethod
    def needs_update(datablock: object, data: dict) -> bool:
        return bpy.context.mode == 'OBJECT' \
            or layer_changed(datablock, data) \
            or frame_changed(data) \
            or get_preferences().sync_flags.sync_during_editmode \
            or is_annotating(bpy.context)


_type = bpy.types.GreasePencilv3
_class = BlGpencil3
