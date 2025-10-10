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
import logging
import re

from .dump_anything import Loader, Dumper
from .replication.protocol import ReplicatedDatablock

from .bl_datablock import get_datablock_from_uuid, resolve_datablock_from_uuid
from .bl_action import (
    dump_animation_data,
    load_animation_data,
    resolve_animation_dependencies,
)
from bpy.types import (
    NodeSocketGeometry,
    NodeSocketShader,
    NodeSocketVirtual,
    NodeSocketCollection,
    NodeSocketObject,
    NodeSocketMaterial,
)

NODE_SOCKET_INDEX = re.compile("\[(\d*)\]")
IGNORED_SOCKETS = [
    "NodeSocketGeometry",
    "NodeSocketShader",
    "CUSTOM",
    "NodeSocketVirtual",
]
IGNORED_SOCKETS_TYPES = (NodeSocketGeometry, NodeSocketShader, NodeSocketVirtual)
ID_NODE_SOCKETS = (NodeSocketObject, NodeSocketCollection, NodeSocketMaterial)


def load_node(node_data: dict, node_tree: bpy.types.ShaderNodeTree):
    """ Load a node into a node_tree from a dict

        :arg node_data: dumped node data
        :type node_data: dict
        :arg node_tree: target node_tree
        :type node_tree: bpy.types.NodeTree
    """
    loader = Loader()
    target_node = node_tree.nodes.new(type=node_data["bl_idname"])
    target_node.select = False
    loader.load(target_node, node_data)
    image_uuid = node_data.get('image_uuid', None)
    node_tree_uuid = node_data.get('node_tree_uuid', None)

    if image_uuid and not target_node.image:
        image = resolve_datablock_from_uuid(image_uuid, bpy.data.images)
        if image is None:
            logging.error(f"Fail to find material image from uuid {image_uuid}")
        else:
            target_node.image = image

    if node_tree_uuid:
        target_node.node_tree = get_datablock_from_uuid(node_tree_uuid, None)

    if target_node.bl_idname == 'GeometryNodeRepeatOutput':
        target_node.repeat_items.clear()
        for sock_name, sock_type in node_data['repeat_items'].items():
            target_node.repeat_items.new(sock_type, sock_name)

    inputs_data = node_data.get('inputs')
    if inputs_data:
        inputs = [i for i in target_node.inputs if not isinstance(i, IGNORED_SOCKETS_TYPES)]
        for idx, inpt in enumerate(inputs):
            if idx < len(inputs_data) and hasattr(inpt, "default_value"):
                loaded_input = inputs_data[idx]
                try:
                    if isinstance(inpt, ID_NODE_SOCKETS):
                        inpt.default_value = get_datablock_from_uuid(loaded_input, None)
                    else:
                        inpt.default_value = loaded_input
                        setattr(inpt, 'default_value', loaded_input)
                except Exception as e:
                    logging.warning(f"Node {target_node.name} input {inpt.name} parameter not supported, skipping ({e})")
            else:
                logging.warning(f"Node {target_node.name} input length mismatch.")

    outputs_data = node_data.get('outputs')
    if outputs_data:
        outputs = [o for o in target_node.outputs if not isinstance(o, IGNORED_SOCKETS_TYPES)]
        for idx, output in enumerate(outputs):
            if idx < len(outputs_data) and hasattr(output, "default_value"):
                loaded_output = outputs_data[idx]
                try:
                    if isinstance(output, ID_NODE_SOCKETS):
                        output.default_value = get_datablock_from_uuid(loaded_output, None)
                    else:
                        output.default_value = loaded_output
                except Exception as e:
                    logging.warning(
                        f"Node {target_node.name} output {output.name} parameter not supported, skipping ({e})")
            else:
                logging.warning(
                    f"Node {target_node.name} output length mismatch.")


def dump_node(node: bpy.types.ShaderNode) -> dict:
    """ Dump a single node to a dict

        :arg node: target node
        :type node: bpy.types.Node
        :retrun: dict
    """

    node_dumper = Dumper()
    node_dumper.depth = 1
    node_dumper.exclude_filter = [
        "dimensions",
        "show_expanded",
        "name_full",
        "select",
        "bl_label",
        "bl_height_min",
        "bl_height_max",
        "bl_height_default",
        "bl_width_min",
        "bl_width_max",
        "type",
        "bl_icon",
        "bl_width_default",
        "bl_static_type",
        "show_tetxure",
        "is_active_output",
        "hide",
        "show_options",
        "show_preview",
        "show_texture",
        "outputs",
        "width_hidden"
    ]

    dumped_node = node_dumper.dump(node)

    if node.parent:
        dumped_node['parent'] = node.parent.name

    dump_io_needed = (node.type not in ['REROUTE', 'OUTPUT_MATERIAL'])

    if dump_io_needed:
        io_dumper = Dumper()
        io_dumper.depth = 2
        io_dumper.include_filter = ["default_value"]

        if hasattr(node, 'inputs'):
            dumped_node['inputs'] = []
            inputs = [i for i in node.inputs if not isinstance(i, IGNORED_SOCKETS_TYPES)]
            for idx, inpt in enumerate(inputs):
                if hasattr(inpt, 'default_value'):
                    if isinstance(inpt.default_value, bpy.types.ID):
                        dumped_input = inpt.default_value.uuid
                    else:
                        dumped_input = io_dumper.dump(inpt.default_value)

                    dumped_node['inputs'].append(dumped_input)

        if hasattr(node, 'outputs'):
            dumped_node['outputs'] = []
            for idx, output in enumerate(node.outputs):
                if not isinstance(output, IGNORED_SOCKETS_TYPES):
                    if hasattr(output, 'default_value'):
                        dumped_node['outputs'].append(
                            io_dumper.dump(output.default_value))

    if hasattr(node, 'color_ramp'):
        ramp_dumper = Dumper()
        ramp_dumper.depth = 4
        ramp_dumper.include_filter = [
            'elements',
            'alpha',
            'color',
            'position',
            'interpolation',
            'hue_interpolation',
            'color_mode'
        ]
        dumped_node['color_ramp'] = ramp_dumper.dump(node.color_ramp)
    if hasattr(node, 'mapping'):
        curve_dumper = Dumper()
        curve_dumper.depth = 5
        curve_dumper.include_filter = [
            'curves',
            'points',
            'location'
        ]
        dumped_node['mapping'] = curve_dumper.dump(node.mapping)
    if hasattr(node, 'image') and getattr(node, 'image'):
        dumped_node['image_uuid'] = node.image.uuid
    if hasattr(node, 'node_tree') and getattr(node, 'node_tree'):
        dumped_node['node_tree_uuid'] = node.node_tree.uuid

    if node.bl_idname == 'GeometryNodeRepeatInput':
        dumped_node['paired_output'] = node.paired_output.name

    if node.bl_idname == 'GeometryNodeRepeatOutput':
        dumped_node['repeat_items'] = {item.name: item.socket_type for item in node.repeat_items}
    return dumped_node


def load_links(links_data, node_tree):
    """ Load node_tree links from a list

        :arg links_data: dumped node links
        :type links_data: list
        :arg node_tree: node links collection
        :type node_tree: bpy.types.NodeTree
    """

    for link in links_data:
        input_socket = node_tree.nodes[link['to_node']].inputs[int(link['to_socket'])]
        output_socket = node_tree.nodes[link['from_node']].outputs[int(link['from_socket'])]
        node_tree.links.new(input_socket, output_socket)


def dump_links(links):
    """ Dump node_tree links collection to a list

        :arg links: node links collection
        :type links: bpy.types.NodeLinks
        :retrun: list
    """

    links_data = []

    for link in links:
        to_socket = NODE_SOCKET_INDEX.search(
            link.to_socket.path_from_id()).group(1)
        from_socket = NODE_SOCKET_INDEX.search(
            link.from_socket.path_from_id()).group(1)
        links_data.append({
            'to_node': link.to_node.name,
            'to_socket': to_socket,
            'from_node': link.from_node.name,
            'from_socket': from_socket,
        })

    return links_data


def dump_node_tree(node_tree: bpy.types.ShaderNodeTree) -> dict:
    """ Dump a shader node_tree to a dict including links and nodes

        :arg node_tree: dumped shader node tree
        :type node_tree: bpy.types.ShaderNodeTree`
        :return: dict
    """
    node_tree_data = {
        'nodes': {node.name: dump_node(node) for node in node_tree.nodes},
        'links': dump_links(node_tree.links),
        'name': node_tree.name,
        'type': type(node_tree).__name__
    }

    sockets = [item for item in node_tree.interface.items_tree if item.item_type == 'SOCKET']
    node_tree_data['interface'] = dump_node_tree_sockets(sockets)

    return node_tree_data


def dump_node_tree_sockets(sockets: bpy.types.Collection) -> dict:
    """ dump sockets of a shader_node_tree

        :arg target_node_tree: target node_tree
        :type target_node_tree: bpy.types.NodeTree
        :arg socket_id: socket identifer
        :type socket_id: str
        :return: dict
    """
    sockets_data = []
    for socket in sockets:
        if not socket.socket_type:
            logging.error(f"Socket {socket.name} has no type, skipping")
            raise ValueError(f"Socket {socket.name} has no type, skipping")
        sockets_data.append(
            (
                socket.name,
                socket.socket_type,
                socket.in_out
            )
        )

    return sockets_data


def load_node_tree_sockets(interface: bpy.types.NodeTreeInterface,
                           sockets_data: dict):
    """ load sockets of a shader_node_tree

        :arg target_node_tree: target node_tree
        :type target_node_tree: bpy.types.NodeTree
        :arg socket_id: socket identifer
        :type socket_id: str
        :arg socket_data: dumped socket data
        :type socket_data: dict
    """
    # Remove old sockets
    interface.clear()

    # Check for new sockets
    for name, socket_type, in_out in sockets_data:
        if not socket_type:
            logging.error(f"Socket {name} has no type, skipping")
            continue
        socket = interface.new_socket(
            name,
            in_out=in_out,
            socket_type=socket_type
        )


def load_node_tree(node_tree_data: dict, target_node_tree: bpy.types.ShaderNodeTree) -> dict:
    """Load a shader node_tree from dumped data

        :arg node_tree_data: dumped node data
        :type node_tree_data: dict
        :arg target_node_tree: target node_tree
        :type target_node_tree: bpy.types.NodeTree
    """
    # TODO: load only required nodes
    target_node_tree.nodes.clear()

    if not target_node_tree.is_property_readonly('name'):
        target_node_tree.name = node_tree_data['name']

    if 'interface' in node_tree_data:
        load_node_tree_sockets(target_node_tree.interface, node_tree_data['interface'])

    # Load nodes
    for node in node_tree_data["nodes"]:
        load_node(node_tree_data["nodes"][node], target_node_tree)

    for node_id, node_data in node_tree_data["nodes"].items():
        target_node = target_node_tree.nodes.get(node_id, None)
        if target_node is None:
            continue
        elif 'parent' in node_data:
            target_node.parent =  target_node_tree.nodes[node_data['parent']]
        else:
            target_node.parent = None

    # Load geo node repeat zones
    zone_input_to_pair = [node_data for node_data in node_tree_data["nodes"].values() if node_data['bl_idname'] == 'GeometryNodeRepeatInput']
    for node_input_data in zone_input_to_pair:
        zone_input = target_node_tree.nodes.get(node_input_data['name'])
        zone_output = target_node_tree.nodes.get(node_input_data['paired_output'])

        zone_input.pair_with_output(zone_output)

    # TODO: load only required nodes links
    # Load nodes links
    target_node_tree.links.clear()

    load_links(node_tree_data["links"], target_node_tree)


def get_node_tree_dependencies(node_tree: bpy.types.NodeTree) -> list:
    def has_image(node): return (
        node.type in ['TEX_IMAGE', 'TEX_ENVIRONMENT'] and node.image)

    def has_node_group(node): return (
        hasattr(node, 'node_tree') and node.node_tree)

    def has_texture(node):
        return node.type in ["ATTRIBUTE_SAMPLE_TEXTURE", "TEXTURE"] and node.texture

    deps = []

    for node in node_tree.nodes:
        if has_image(node):
            deps.append(node.image)
        elif has_node_group(node):
            deps.append(node.node_tree)
        elif has_texture(node):
            deps.append(node.texture)

    return deps


def dump_materials_slots(materials: bpy.types.bpy_prop_collection) -> list:
    """ Dump material slots collection

        :arg materials: material slots collection to dump
        :type materials: bpy.types.bpy_prop_collection
        :return: list of tuples (mat_uuid, mat_name)
    """
    return [(m.uuid, m.name) for m in materials if m]


def load_materials_slots(src_materials: list, dst_materials: bpy.types.bpy_prop_collection):
    """ Load material slots

        :arg src_materials: dumped material collection (ex: object.materials)
        :type src_materials: list of tuples (uuid, name)
        :arg dst_materials: target material collection pointer
        :type dst_materials: bpy.types.bpy_prop_collection
    """
    # MATERIAL SLOTS
    dst_materials.clear()

    for mat_uuid, mat_name in src_materials:
        mat_ref = None
        if mat_uuid:
            mat_ref = get_datablock_from_uuid(mat_uuid, None)
        else:
            mat_ref = bpy.data.materials[mat_name]
        dst_materials.append(mat_ref)


class BlMaterial(ReplicatedDatablock):
    use_delta = True

    bl_id = "materials"
    bl_class = bpy.types.Material
    bl_check_common = False
    bl_icon = 'MATERIAL_DATA'
    bl_reload_parent = False
    bl_reload_child = True

    @staticmethod
    def construct(data: dict) -> object:
        return bpy.data.materials.new(data["name"])

    @staticmethod
    def load(data: dict, datablock: object):
        loader = Loader()

        is_grease_pencil = data.get('is_grease_pencil')
        use_nodes = data.get('use_nodes')

        loader.load(datablock, data)

        if is_grease_pencil:
            if not datablock.is_grease_pencil:
                bpy.data.materials.create_gpencil_data(datablock)
            loader.load(datablock.grease_pencil, data['grease_pencil'])
        elif use_nodes:
            if datablock.node_tree is None:
                datablock.use_nodes = True

            load_node_tree(data['node_tree'], datablock.node_tree)
            load_animation_data(data.get('nodes_animation_data'), datablock.node_tree)
        load_animation_data(data.get('animation_data'), datablock)

    @staticmethod
    def dump(datablock: object) -> dict:
        mat_dumper = Dumper()
        mat_dumper.depth = 2
        mat_dumper.include_filter = [
            'name',
            'blend_method',
            'shadow_method',
            'alpha_threshold',
            'show_transparent_back',
            'use_backface_culling',
            'use_screen_refraction',
            'use_sss_translucency',
            'refraction_depth',
            'preview_render_type',
            'use_preview_world',
            'pass_index',
            'use_nodes',
            'diffuse_color',
            'specular_color',
            'roughness',
            'specular_intensity',
            'metallic',
            'line_color',
            'line_priority',
            'is_grease_pencil'
        ]
        data = mat_dumper.dump(datablock)

        if datablock.is_grease_pencil:
            gp_mat_dumper = Dumper()
            gp_mat_dumper.depth = 3

            gp_mat_dumper.include_filter = [
                'color',
                'fill_color',
                'mix_color',
                'mix_factor',
                'mix_stroke_factor',
                # 'texture_angle',
                # 'texture_scale',
                # 'texture_offset',
                'pixel_size',
                'hide',
                'lock',
                'ghost',
                # 'texture_clamp',
                'flip',
                'use_overlap_strokes',
                'show_stroke',
                'show_fill',
                'alignment_mode',
                'pass_index',
                'mode',
                'stroke_style',
                # 'stroke_image',
                'fill_style',
                'gradient_type',
                # 'fill_image',
                'use_stroke_holdout',
                'use_overlap_strokes',
                'use_fill_holdout',
            ]
            data['grease_pencil'] = gp_mat_dumper.dump(datablock.grease_pencil)
        elif datablock.use_nodes:
            data['node_tree'] = dump_node_tree(datablock.node_tree)
            data['nodes_animation_data'] = dump_animation_data(datablock.node_tree)

        data['animation_data'] = dump_animation_data(datablock)

        return data

    @staticmethod
    def resolve(data: dict) -> object:
        uuid = data.get('uuid')
        return resolve_datablock_from_uuid(uuid, bpy.data.materials)

    @staticmethod
    def resolve_deps(datablock: object) -> list[object]:
        deps = []

        if datablock.use_nodes:
            deps.extend(get_node_tree_dependencies(datablock.node_tree))
            deps.extend(resolve_animation_dependencies(datablock.node_tree))
        deps.extend(resolve_animation_dependencies(datablock))

        return deps


_type = bpy.types.Material
_class = BlMaterial
