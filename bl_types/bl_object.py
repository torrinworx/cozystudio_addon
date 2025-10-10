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

import logging

import bpy
import mathutils
from .replication.exception import ContextError
from .replication.protocol import ReplicatedDatablock

from .utils import get_preferences
from .bl_action import (dump_animation_data, load_animation_data,
                        resolve_animation_dependencies)
from .bl_datablock import get_datablock_from_uuid, resolve_datablock_from_uuid
from .bl_material import IGNORED_SOCKETS
from .dump_anything import (Dumper, Loader, np_dump_collection,
                            np_load_collection)

SKIN_DATA = [
    'radius',
    'use_loose',
    'use_root'
]

SHAPEKEY_BLOCK_ATTR = [
    'mute',
    'value',
    'slider_min',
    'slider_max',
]

SUPPORTED_GEOMETRY_NODE_PARAMETERS = (int, str, float)


def get_node_group_properties_identifiers(node_group):
    props_ids = []
    if not node_group:
        return props_ids
    for socket in node_group.interface.items_tree:
        if socket.socket_type in IGNORED_SOCKETS:
            continue

        props_ids.append((f"{socket.identifier}_attribute_name", 'NodeSocketString'))
        if socket.in_out == 'OUTPUT':
            continue
        props_ids.append((socket.identifier, socket.socket_type))
        props_ids.append((f"{socket.identifier}_use_attribute", 'NodeSocketBool'))

    return props_ids


def dump_physics(target: bpy.types.Object) -> dict:
    """
        Dump all physics settings from a given object excluding modifier
        related physics settings (such as softbody, cloth, dynapaint and fluid)
    """
    dumper = Dumper()
    dumper.depth = 1
    physics_data = {}

    # Collisions (collision)
    if target.collision and target.collision.use:
        physics_data['collision'] = dumper.dump(target.collision)

    # Field (field)
    if target.field and target.field.type != "NONE":
        physics_data['field'] = dumper.dump(target.field)

    # Rigid Body (rigid_body)
    if target.rigid_body:
        physics_data['rigid_body'] = dumper.dump(target.rigid_body)

    # Rigid Body constraint (rigid_body_constraint)
    if target.rigid_body_constraint:
        physics_data['rigid_body_constraint'] = dumper.dump(target.rigid_body_constraint)

    return physics_data


def load_physics(dumped_settings: dict, target: bpy.types.Object):
    """  Load all physics settings from a given object excluding modifier
        related physics settings (such as softbody, cloth, dynapaint and fluid)
    """
    loader = Loader()

    if 'collision' in dumped_settings:
        loader.load(target.collision, dumped_settings['collision'])

    if 'field' in dumped_settings:
        loader.load(target.field, dumped_settings['field'])

    if 'rigid_body' in dumped_settings:
        if not target.rigid_body:
            with bpy.context.temp_override(object=target):
                bpy.ops.rigidbody.object_add()
        loader.load(target.rigid_body, dumped_settings['rigid_body'])
    elif target.rigid_body:
        with bpy.context.temp_override(object=target):
            bpy.ops.rigidbody.object_remove()

    if 'rigid_body_constraint' in dumped_settings:
        if not target.rigid_body_constraint:
            with bpy.context.temp_override(object=target):
                bpy.ops.rigidbody.constraint_add()
        loader.load(target.rigid_body_constraint, dumped_settings['rigid_body_constraint'])
    elif target.rigid_body_constraint:
        with bpy.context.temp_override(object=target):
            bpy.ops.rigidbody.constraint_remove()


def dump_modifier_geometry_node_props(modifier: bpy.types.Modifier) -> list:
    """ Dump geometry node modifier input properties

        :arg modifier: geometry node modifier to dump
        :type modifier: bpy.type.Modifier
    """
    dumped_props = []

    if not modifier.node_group:
        logging.warning(f"No geometry node group property found for modifier ({modifier.name})")
        return dumped_props

    for prop_id, prop_type in get_node_group_properties_identifiers(modifier.node_group):
        try:
            prop_value = modifier[prop_id]
        except KeyError as e:
            logging.error(f"fail to dump geomety node modifier property : {prop_id} ({e})")
        else:
            dump = None
            if isinstance(prop_value, bpy.types.ID):
                dump = prop_value.uuid
            elif isinstance(prop_value, SUPPORTED_GEOMETRY_NODE_PARAMETERS):
                dump = prop_value
            elif hasattr(prop_value, 'to_list'):
                dump = prop_value.to_list()

            dumped_props.append((dump, prop_type))

    return dumped_props


def load_modifier_geometry_node_props(dumped_modifier: dict, target_modifier: bpy.types.Modifier):
    """ Load geometry node modifier inputs

        :arg dumped_modifier: source dumped modifier to load
        :type dumped_modifier: dict
        :arg target_modifier: target geometry node modifier
        :type target_modifier: bpy.type.Modifier
    """

    for input_index, inpt in enumerate(get_node_group_properties_identifiers(target_modifier.node_group)):
        dumped_value, dumped_type = dumped_modifier['props'][input_index]
        if dumped_type in ['NodeSocketInt', 'NodeSocketFloat', 'NodeSocketString', 'NodeSocketBool']:
            target_modifier[inpt[0]] = dumped_value
        elif dumped_type in ['NodeSocketColor', 'NodeSocketVector']:
            input_value = target_modifier[inpt[0]]
            for index in range(len(input_value)):
                input_value[index] = dumped_value[index]
        elif dumped_type in ['NodeSocketCollection', 'NodeSocketObject', 'NodeSocketImage', 'NodeSocketTexture', 'NodeSocketMaterial']:
            target_modifier[inpt[0]] = get_datablock_from_uuid(dumped_value, None)


def load_pose(target_bone, data):
    target_bone.rotation_mode = data['rotation_mode']
    loader = Loader()
    loader.load(target_bone, data)


def find_data_from_name(name=None):
    instance = None
    if not name:
        pass
    elif name in bpy.data.meshes.keys():
        instance = bpy.data.meshes[name]
    elif name in bpy.data.lights.keys():
        instance = bpy.data.lights[name]
    elif name in bpy.data.cameras.keys():
        instance = bpy.data.cameras[name]
    elif name in bpy.data.curves.keys():
        instance = bpy.data.curves[name]
    elif name in bpy.data.metaballs.keys():
        instance = bpy.data.metaballs[name]
    elif name in bpy.data.armatures.keys():
        instance = bpy.data.armatures[name]
    elif name in bpy.data.grease_pencils.keys():
        instance = bpy.data.grease_pencils[name]
    elif name in bpy.data.grease_pencils_v3.keys():
        instance = bpy.data.grease_pencils_v3[name]
    elif name in bpy.data.curves.keys():
        instance = bpy.data.curves[name]
    elif name in bpy.data.lattices.keys():
        instance = bpy.data.lattices[name]
    elif name in bpy.data.speakers.keys():
        instance = bpy.data.speakers[name]
    elif name in bpy.data.lightprobes.keys():
        instance = bpy.data.lightprobes[name]
    elif name in bpy.data.volumes.keys():
        instance = bpy.data.volumes[name]
    return instance


def load_data(object, name):
    logging.info("loading data")
    pass


def _is_editmode(object: bpy.types.Object) -> bool:
    child_data = getattr(object, 'data', None)
    return (child_data and
            hasattr(child_data, 'is_editmode') and
            child_data.is_editmode)


def find_textures_dependencies(modifiers: bpy.types.bpy_prop_collection) -> list[bpy.types.Texture]:
    """ Find textures lying in a modifier stack

        :arg modifiers: modifiers collection
        :type modifiers: bpy.types.bpy_prop_collection
        :return: list of bpy.types.Texture pointers
    """
    textures = []
    for mod in modifiers:
        modifier_attributes = [getattr(mod, attr_name)
                               for attr_name in mod.bl_rna.properties.keys()]
        for attr in modifier_attributes:
            if issubclass(type(attr), bpy.types.Texture) and attr is not None:
                textures.append(attr)

    return textures


def find_geometry_nodes_dependencies(modifiers: bpy.types.bpy_prop_collection) -> list[bpy.types.NodeTree]:
    """ Find geometry nodes dependencies from a modifier stack

        :arg modifiers: modifiers collection
        :type modifiers: bpy.types.bpy_prop_collection
        :return: list of bpy.types.NodeTree pointers
    """
    dependencies = []
    for mod in modifiers:
        if mod.type == 'NODES' and mod.node_group:
            dependencies.append(mod.node_group)
            for inpt, inpt_type in get_node_group_properties_identifiers(mod.node_group):
                inpt_value = mod.get(inpt)
                # Avoid to handle 'COLLECTION', 'OBJECT' to avoid circular dependencies
                if inpt_type in ['IMAGE', 'TEXTURE', 'MATERIAL'] and inpt_value:
                    dependencies.append(inpt_value)

    return dependencies


def dump_vertex_groups(src_object: bpy.types.Object) -> dict:
    """ Dump object's vertex groups

        :param target_object: dump vertex groups of this object
        :type  target_object: bpy.types.Object
    """
    if isinstance(src_object.data, bpy.types.GreasePencil):
        logging.warning(
            "Grease pencil vertex groups are not supported yet. More info: https://gitlab.com/slumber/multi-user/-/issues/161")
    else:
        points_attr = 'vertices' if isinstance(
            src_object.data, bpy.types.Mesh) else 'points'
        dumped_vertex_groups = {}

        # Vertex group metadata
        for vg in src_object.vertex_groups:
            dumped_vertex_groups[vg.index] = {
                'name': vg.name,
                'vertices': []
            }

        # Vertex group assignation
        for vert in getattr(src_object.data, points_attr):
            for vg in vert.groups:
                vertices = dumped_vertex_groups.get(vg.group)['vertices']
                vertices.append((vert.index, vg.weight))

    return dumped_vertex_groups


def load_vertex_groups(dumped_vertex_groups: dict, target_object: bpy.types.Object):
    """ Load object vertex groups

        :param dumped_vertex_groups: vertex_groups to load
        :type dumped_vertex_groups: dict
        :param target_object: object to load the vertex groups into
        :type  target_object: bpy.types.Object
    """
    target_object.vertex_groups.clear()
    for vg in dumped_vertex_groups.values():
        vertex_group = target_object.vertex_groups.new(name=vg['name'])
        for index, weight in vg['vertices']:
            vertex_group.add([index], weight, 'REPLACE')


def dump_shape_keys(target_key: bpy.types.Key) -> dict:
    """ Dump the target shape_keys datablock to a dict using numpy

        :param dumped_key: target key datablock
        :type dumped_key: bpy.types.Key
        :return: dict
    """

    dumped_key_blocks = []
    dumper = Dumper()
    dumper.include_filter = [
        'name',
        'mute',
        'value',
        'slider_min',
        'slider_max',
    ]
    for key in target_key.key_blocks:
        dumped_key_block = dumper.dump(key)
        dumped_key_block['data'] = np_dump_collection(key.data, ['co'])
        dumped_key_block['relative_key'] = key.relative_key.name
        dumped_key_blocks.append(dumped_key_block)

    return {
        'reference_key': target_key.reference_key.name,
        'use_relative': target_key.use_relative,
        'key_blocks': dumped_key_blocks,
        'animation_data': dump_animation_data(target_key)
    }


def load_shape_keys(dumped_shape_keys: dict, target_object: bpy.types.Object):
    """ Load the target shape_keys datablock to a dict using numpy

        :param dumped_key: src key data
        :type dumped_key: bpy.types.Key
        :param target_object: object used to load the shapekeys data onto
        :type target_object: bpy.types.Object
    """
    loader = Loader()
    # Remove existing ones
    target_object.shape_key_clear()

    # Create keys and load vertices coords
    dumped_key_blocks = dumped_shape_keys.get('key_blocks')
    for dumped_key_block in dumped_key_blocks:
        key_block = target_object.shape_key_add(name=dumped_key_block['name'])

        loader.load(key_block, dumped_key_block)
        np_load_collection(dumped_key_block['data'], key_block.data, ['co'])

    # Load relative key after all
    for dumped_key_block in dumped_key_blocks:
        relative_key_name = dumped_key_block.get('relative_key')
        key_name = dumped_key_block.get('name')

        target_keyblock = target_object.data.shape_keys.key_blocks[key_name]
        relative_key = target_object.data.shape_keys.key_blocks[relative_key_name]

        target_keyblock.relative_key = relative_key

    # Shape keys animation data
    anim_data = dumped_shape_keys.get('animation_data')

    if anim_data:
        load_animation_data(anim_data, target_object.data.shape_keys)


def dump_modifiers(modifiers: bpy.types.bpy_prop_collection) -> dict:
    """ Dump all modifiers of a modifier collection into a dict

        :param modifiers: modifiers
        :type modifiers: bpy.types.bpy_prop_collection
        :return: dict
    """
    dumped_modifiers = []
    dumper = Dumper()
    dumper.depth = 1
    dumper.exclude_filter = ['is_active']

    for modifier in modifiers:
        dumped_modifier = dumper.dump(modifier)
        # hack to dump geometry nodes inputs
        if modifier.type == 'NODES':
            dumped_modifier['props'] = dump_modifier_geometry_node_props(modifier)
        elif modifier.type == 'PARTICLE_SYSTEM':
            dumper.exclude_filter = [
                "is_edited",
                "is_editable",
                "is_global_hair"
            ]
            dumped_modifier['particle_system'] = dumper.dump(modifier.particle_system)
            dumped_modifier['particle_system']['settings_uuid'] = modifier.particle_system.settings.uuid

        elif modifier.type in ['SOFT_BODY', 'CLOTH']:
            dumped_modifier['settings'] = dumper.dump(modifier.settings)
        elif modifier.type == 'UV_PROJECT':
            dumped_modifier['projectors'] = [p.object.name for p in modifier.projectors if p and p.object]

        dumped_modifiers.append(dumped_modifier)
    return dumped_modifiers


def dump_constraints(constraints: bpy.types.bpy_prop_collection) -> list:
    """Dump all constraints to a list

        :param constraints: constraints
        :type constraints: bpy.types.bpy_prop_collection
        :return: dict
    """
    dumper = Dumper()
    dumper.depth = 2
    dumper.include_filter = None
    dumped_constraints = []
    for constraint in constraints:
        dumped_constraints.append(dumper.dump(constraint))
    return dumped_constraints

def load_constraints(dumped_constraints: list, constraints: bpy.types.bpy_prop_collection):
    """ Load dumped constraints

        :param dumped_constraints: list of constraints to load
        :type dumped_constraints: list
        :param constraints: constraints
        :type constraints: bpy.types.bpy_prop_collection
    """
    loader = Loader()
    constraints.clear()
    for dumped_constraint in dumped_constraints:
        constraint_type = dumped_constraint.get('type')
        new_constraint = constraints.new(constraint_type)
        loader.load(new_constraint, dumped_constraint)

def load_modifiers(dumped_modifiers: list, modifiers: bpy.types.bpy_prop_collection):
    """ Dump all modifiers of a modifier collection into a dict

        :param dumped_modifiers: list of modifiers to load
        :type dumped_modifiers: list
        :param modifiers: modifiers
        :type modifiers: bpy.types.bpy_prop_collection
    """
    loader = Loader()
    modifiers.clear()
    for dumped_modifier in dumped_modifiers:
        name = dumped_modifier.get('name')
        mtype = dumped_modifier.get('type')
        loaded_modifier = modifiers.new(name, mtype)
        loader.load(loaded_modifier, dumped_modifier)

        if loaded_modifier.type == 'NODES':
            load_modifier_geometry_node_props(dumped_modifier, loaded_modifier)
        elif loaded_modifier.type == 'PARTICLE_SYSTEM':
            default = loaded_modifier.particle_system.settings
            dumped_particles = dumped_modifier['particle_system']
            loader.load(loaded_modifier.particle_system, dumped_particles)

            settings = get_datablock_from_uuid(dumped_particles['settings_uuid'], None)
            if settings:
                loaded_modifier.particle_system.settings = settings
                # Hack to remove the default generated particle settings
                if not default.uuid:
                    bpy.data.particles.remove(default)
        elif loaded_modifier.type in ['SOFT_BODY', 'CLOTH']:
            loader.load(loaded_modifier.settings, dumped_modifier['settings'])
        elif loaded_modifier.type == 'UV_PROJECT':
            for projector_index, projector_object in enumerate(dumped_modifier['projectors']):
                target_object = bpy.data.objects.get(projector_object)
                if target_object:
                    loaded_modifier.projectors[projector_index].object = target_object
                else:
                    logging.error("Could't load projector target object {projector_object}")


class BlObject(ReplicatedDatablock):
    use_delta = True

    bl_id = "objects"
    bl_class = bpy.types.Object
    bl_check_common = False
    bl_icon = 'OBJECT_DATA'
    bl_reload_parent = False

    @staticmethod
    def construct(data: dict) -> object:
        # TODO: refactoring
        object_name = data.get("name")
        data_uuid = data.get("data_uuid")
        data_id = data.get("data")
        data_type = data.get("type")

        object_data = get_datablock_from_uuid(
            data_uuid,
            find_data_from_name(data_id),
            ignore=['images'])  # TODO: use resolve_from_id

        if data_type != 'EMPTY' and object_data is None:
            raise Exception(f"Fail to load object {data['name']})")

        return bpy.data.objects.new(object_name, object_data)

    @staticmethod
    def load(data: dict, datablock: object):
        loader = Loader()
        load_animation_data(data.get('animation_data'), datablock)
        data_uuid = data.get("data_uuid")
        data_id = data.get("data")

        if datablock.data and (datablock.data.name != data_id):
            datablock.data = get_datablock_from_uuid(
                data_uuid, find_data_from_name(data_id), ignore=['images'])

        # vertex groups
        vertex_groups = data.get('vertex_groups', None)
        if vertex_groups:
            load_vertex_groups(vertex_groups, datablock)

        object_data = datablock.data

        # SHAPE KEYS
        shape_keys = data.get('shape_keys')
        if shape_keys:
            load_shape_keys(shape_keys, datablock)

        # Load transformation data
        loader.load(datablock, data)

        #  Object display fields
        if 'display' in data:
            loader.load(datablock.display, data['display'])

        #  Parenting
        parent_id = data.get('parent_uid')
        if parent_id:
            parent = get_datablock_from_uuid(parent_id[0], bpy.data.objects[parent_id[1]])
            # Avoid reloading
            if datablock.parent != parent and parent is not None:
                datablock.parent = parent
        elif datablock.parent:
            datablock.parent = None

        # Pose
        if 'pose' in data:
            if not datablock.pose:
                raise Exception('No pose data yet (Fixed in a near futur)')

            # Bones
            for bone in data['pose']['bones']:
                target_bone = datablock.pose.bones.get(bone)
                bone_data = data['pose']['bones'].get(bone)

                if 'constraints' in bone_data.keys():
                    loader.load(target_bone, bone_data['constraints'])

                load_pose(target_bone, bone_data)

        # TODO: find another way...
        if datablock.empty_display_type == "IMAGE":
            img_uuid = data.get('data_uuid')
            if datablock.data is None and img_uuid:
                datablock.data = get_datablock_from_uuid(img_uuid, None)

        if hasattr(datablock, 'cycles_visibility') \
                and 'cycles_visibility' in data:
            loader.load(datablock.cycles_visibility, data['cycles_visibility'])

        if hasattr(datablock, 'modifiers'):
            load_modifiers(data['modifiers'], datablock.modifiers)

        if hasattr(object_data, 'skin_vertices') \
                and object_data.skin_vertices\
                and 'skin_vertices' in data:
            for index, skin_data in enumerate(object_data.skin_vertices):
                np_load_collection(
                    data['skin_vertices'][index],
                    skin_data.data,
                    SKIN_DATA)

        constraints = data.get('constraints')
        if constraints:
            load_constraints(constraints, datablock.constraints)

        # PHYSICS
        load_physics(data, datablock)

        transform = data.get('transforms', None)
        if transform:
            datablock.matrix_parent_inverse = mathutils.Matrix(transform['matrix_parent_inverse'])
            datablock.matrix_basis = mathutils.Matrix(transform['matrix_basis'])


    @staticmethod
    def dump(datablock: object) -> dict:
        if _is_editmode(datablock):
            if get_preferences().sync_flags.sync_during_editmode:
                datablock.update_from_editmode()
            else:
                raise ContextError("Object is in edit-mode.")

        dumper = Dumper()
        dumper.depth = 1
        dumper.include_filter = [
            "name",
            "rotation_mode",
            "data",
            "library",
            "empty_display_type",
            "empty_display_size",
            "empty_image_offset",
            "empty_image_depth",
            "empty_image_side",
            "show_empty_image_orthographic",
            "show_empty_image_perspective",
            "show_empty_image_only_axis_aligned",
            "use_empty_image_alpha",
            "color",
            "instance_collection",
            "instance_type",
            'lock_location',
            'lock_rotation',
            'lock_scale',
            'hide_render',
            'display_type',
            'display_bounds_type',
            'show_bounds',
            'show_name',
            'show_axis',
            'show_wire',
            'show_all_edges',
            'show_texture_space',
            'show_in_front',
            'type',
            'parent_type',
            'parent_bone',
            'track_axis',
            'up_axis',
        ]

        data = dumper.dump(datablock)
        data['animation_data'] = dump_animation_data(datablock)
        dumper.include_filter = [
            'matrix_parent_inverse',
            'matrix_local',
            'matrix_basis']
        data['transforms'] = dumper.dump(datablock)
        dumper.include_filter = [
            'show_shadows',
        ]
        data['display'] = dumper.dump(datablock.display)

        data['data_uuid'] = getattr(datablock.data, 'uuid', None)

        # PARENTING
        if datablock.parent:
            data['parent_uid'] = (datablock.parent.uuid, datablock.parent.name)

        # MODIFIERS
        modifiers = getattr(datablock, 'modifiers', None)
        if hasattr(datablock, 'modifiers'):
            data['modifiers'] = dump_modifiers(modifiers)

        gp_modifiers = getattr(datablock, 'grease_pencil_modifiers', None)

        if gp_modifiers:
            dumper.include_filter = None
            dumper.depth = 1
            gp_modifiers_data = data["grease_pencil_modifiers"] = {}

            for index, modifier in enumerate(gp_modifiers):
                gp_mod_data = gp_modifiers_data[modifier.name] = dict()
                gp_mod_data.update(dumper.dump(modifier))

                if hasattr(modifier, 'use_custom_curve') \
                        and modifier.use_custom_curve:
                    curve_dumper = Dumper()
                    curve_dumper.depth = 5
                    curve_dumper.include_filter = [
                        'curves',
                        'points',
                        'location']
                    gp_mod_data['curve'] = curve_dumper.dump(modifier.curve)


        # CONSTRAINTS
        if hasattr(datablock, 'constraints'):
            data["constraints"] = dump_constraints(datablock.constraints)

        # POSE
        if hasattr(datablock, 'pose') and datablock.pose:
            # BONES
            bones = {}
            for bone in datablock.pose.bones:
                bones[bone.name] = {}
                dumper.depth = 1
                rotation = 'rotation_quaternion' if bone.rotation_mode == 'QUATERNION' else 'rotation_euler'
                dumper.include_filter = [
                    'rotation_mode',
                    'location',
                    'scale',
                    'custom_shape',
                    'use_custom_shape_bone_size',
                    'custom_shape_scale',
                    rotation
                ]
                bones[bone.name] = dumper.dump(bone)

                dumper.include_filter = []
                dumper.depth = 3
                bones[bone.name]["constraints"] = dumper.dump(bone.constraints)

            data['pose'] = {'bones': bones}

        # VERTEx GROUP
        if len(datablock.vertex_groups) > 0:
            data['vertex_groups'] = dump_vertex_groups(datablock)

        #  SHAPE KEYS
        object_data = datablock.data
        if hasattr(object_data, 'shape_keys') and object_data.shape_keys:
            data['shape_keys'] = dump_shape_keys(object_data.shape_keys)

        #  SKIN VERTICES
        if hasattr(object_data, 'skin_vertices') and object_data.skin_vertices:
            skin_vertices = list()
            for skin_data in object_data.skin_vertices:
                skin_vertices.append(
                    np_dump_collection(skin_data.data, SKIN_DATA))
            data['skin_vertices'] = skin_vertices

        # CYCLE SETTINGS
        if hasattr(datablock, 'cycles_visibility'):
            dumper.include_filter = [
                'camera',
                'diffuse',
                'glossy',
                'transmission',
                'scatter',
                'shadow',
            ]
            data['cycles_visibility'] = dumper.dump(datablock.cycles_visibility)

        # PHYSICS
        data.update(dump_physics(datablock))

        return data

    @staticmethod
    def resolve_deps(datablock: object) -> list[object]:
        deps = []

        # Avoid Empty case
        if datablock.data:
            deps.append(datablock.data)

        # Particle systems
        for particle_slot in datablock.particle_systems:
            deps.append(particle_slot.settings)

        if datablock.parent:
            deps.append(datablock.parent)

        if datablock.instance_type == 'COLLECTION':
            # TODO: uuid based
            deps.append(datablock.instance_collection)

        if datablock.modifiers:
            deps.extend(find_textures_dependencies(datablock.modifiers))
            deps.extend(find_geometry_nodes_dependencies(datablock.modifiers))

        if hasattr(datablock.data, 'shape_keys') and datablock.data.shape_keys:
            deps.extend(resolve_animation_dependencies(datablock.data.shape_keys))

        deps.extend(resolve_animation_dependencies(datablock))

        return deps

    @staticmethod
    def resolve(data: dict) -> object:
        uuid = data.get('uuid')
        return resolve_datablock_from_uuid(uuid, bpy.data.objects)


_type = bpy.types.Object
_class = BlObject
