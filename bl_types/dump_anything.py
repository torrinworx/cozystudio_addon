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
import bpy.types as T
import mathutils
import numpy as np


BPY_TO_NUMPY_TYPES = {
    'FLOAT': np.float32,
    'INT': np.int32,
    'BOOL': bool,
    'BOOLEAN': bool}

PRIMITIVE_TYPES = ['FLOAT', 'INT', 'BOOLEAN']

NP_COMPATIBLE_TYPES = ['FLOAT', 'INT', 'BOOLEAN', 'ENUM']


ATTRIBUTES_NUMPY_TYPES = {
    'FLOAT_VECTOR': np.float32,
    'FLOAT': np.float32,
    'FLOAT2': np.float32,
    'INT': np.int32,
    'INT8': np.int8,
    'BOOLEAN': bool,
}
ATTRIBUTES_TYPES_GETTERS = {
    'FLOAT_VECTOR': 'vector',
    'FLOAT2': 'vector',
    'FLOAT': 'value',
    'INT': 'value',
    'INT8': 'value',
    'BOOLEAN': 'value',
}
ATTRIBUTE_DIMENSION = {
    'FLOAT_VECTOR': 3,
    'FLOAT2': 2,
    'BOOLEAN': 1,
    'FLOAT': 1,
    'INT': 1,
    'INT8': 1,
}


def np_dump_attributes(attributes_collection: bpy.types.bpy_prop_collection, attributes_names = None) -> dict:
    """ Dump a list of attributes to the target dikt

        :arg attributes_collection: source collection
        :type attributes_collection: bpy.types.bpy_prop_collection
        :arg attributes_names: list of attributes name
        :type attributes_names: list
        :retrun: dict
    """
    assert type(attributes_collection) is T.bpy_prop_collection

    dumped_attributes = {}

    attributes_names = attributes_names or attributes_collection.keys()

    for attr_name in attributes_names:
        if attr_name not in attributes_collection.keys():
            logging.warning(f"Attribute {attr_name} not in collection.")
            continue
        attribute = attributes_collection[attr_name]
        attribute_dimension = ATTRIBUTE_DIMENSION.get(attribute.data_type)
        array_size = attributes_collection.domain_size(attribute.domain) * attribute_dimension
        array_type = ATTRIBUTES_NUMPY_TYPES.get(attribute.data_type)
        numpy_array = np.zeros(
            array_size,
            dtype=array_type
        )
        attribute.data.foreach_get(
            ATTRIBUTES_TYPES_GETTERS.get(attribute.data_type),
            numpy_array
        )
        dumped_attributes[attr_name] = {
            'data_type': attribute.data_type,
            'domain': attribute.domain,
            'data': numpy_array.tobytes()
        }

    return dumped_attributes


def np_load_attributes(attributes_collection: bpy.types.bpy_prop_collection, attributes_data: dict):
    """ Load a list of attributes from a dict to the target collection

        :arg attributes_collection: target collection
        :type attributes_collection: bpy.types.bpy_prop_collection
        :arg attributes_data: source data
        :type attributes_data: dict
    """
    assert type(attributes_collection) is T.bpy_prop_collection

    for attr_name, data in attributes_data.items():
        if attr_name not in attributes_collection.keys():
            attributes_collection.new(attr_name, type=data['data_type'], domain=data['domain'])
        attribute = attributes_collection[attr_name]
        array_type = ATTRIBUTES_NUMPY_TYPES.get(attribute.data_type)
        numpy_array = np.frombuffer(
            data['data'],
            dtype=array_type
        )
        attribute.data.foreach_set(
            ATTRIBUTES_TYPES_GETTERS.get(data['data_type']),
            numpy_array
        )


def np_load_collection(dikt: dict, collection: bpy.types.CollectionProperty, attributes: list = None):
    """ Dump a list of attributes from the sane collection
        to the target dikt.

        Without attribute given, it try to load all entry from dikt.

        :arg dikt: target dict
        :type dikt: dict
        :arg collection: source collection
        :type collection: bpy.types.CollectionProperty
        :arg attributes: list of attributes name
        :type attributes: list
    """
    if not dikt or len(collection) == 0:
        logging.debug(f'Skipping collection {collection}')
        return

    if attributes is None:
        attributes = dikt.keys()

    for attr in attributes:
        attr_type = collection[0].bl_rna.properties.get(attr).type

        if attr_type in PRIMITIVE_TYPES:
            np_load_collection_primitives(collection, attr, dikt[attr])
        elif attr_type == 'ENUM':
            np_load_collection_enum(collection, attr, dikt[attr])
        else:
            logging.error(f"{attr} of type {attr_type} not supported.")


def np_dump_collection(collection: bpy.types.CollectionProperty, attributes: list = None) -> dict:
    """ Dump a list of attributes from the sane collection
        to the target dikt

        Without attributes given, it try to dump all properties
        that matches NP_COMPATIBLE_TYPES.

        :arg collection: source collection
        :type collection: bpy.types.CollectionProperty
        :arg attributes: list of attributes name
        :type attributes: list
        :retrun: dict
    """
    dumped_collection = {}

    if len(collection) == 0:
        return dumped_collection

    # TODO: find a way without getting the first item
    properties = collection[0].bl_rna.properties

    if attributes is None:
        attributes = [p.identifier for p in properties if p.type in NP_COMPATIBLE_TYPES and not p.is_readonly]

    for attr in attributes:
        attr_type = properties[attr].type

        if attr_type in PRIMITIVE_TYPES:
            dumped_collection[attr] = np_dump_collection_primitive(
                collection, attr)
        elif attr_type == 'ENUM':
            dumped_collection[attr] = np_dump_collection_enum(collection, attr)
        else:
            logging.error(f"{attr} of type {attr_type} not supported. Only {PRIMITIVE_TYPES} and ENUM supported. Skipping it.")

    return dumped_collection


def np_dump_collection_primitive(collection: bpy.types.CollectionProperty, attribute: str) -> str:
    """ Dump a collection attribute as a sequence

        !!! warning
            Only work with int, float and bool attributes

        :arg collection: target collection
        :type collection: bpy.types.CollectionProperty
        :arg attribute: target attribute
        :type attribute: str
        :return: numpy byte buffer
    """
    if len(collection) == 0:
        logging.debug(f'Skipping empty {attribute} attribute')
        return {}

    attr_infos = collection[0].bl_rna.properties.get(attribute)

    assert attr_infos.type in ["FLOAT", "INT", "BOOLEAN"]

    size = sum(attr_infos.array_dimensions) if attr_infos.is_array else 1

    dumped_sequence = np.zeros(
        len(collection)*size,
        dtype=BPY_TO_NUMPY_TYPES.get(attr_infos.type))

    collection.foreach_get(attribute, dumped_sequence)

    return dumped_sequence.tobytes()


def np_dump_collection_enum(collection: bpy.types.CollectionProperty, attribute: str) -> list:
    """ Dump a collection enum attribute to an index list

        :arg collection: target collection
        :type collection: bpy.types.CollectionProperty
        :arg attribute: target attribute
        :type attribute: bpy.types.EnumProperty
        :return: list of int
    """
    attr_infos = collection[0].bl_rna.properties.get(attribute)

    assert attr_infos.type == "ENUM"

    enum_items = attr_infos.enum_items
    return [enum_items[getattr(i, attribute)].value for i in collection]


def np_load_collection_enum(collection: bpy.types.CollectionProperty, attribute: str, sequence: list):
    """ Load a collection enum attribute from a list sequence

        !!! warning
            Only work with Enum

        :arg collection: target collection
        :type collection: bpy.types.CollectionProperty
        :arg attribute: target attribute
        :type attribute: str
        :arg sequence: enum data buffer
        :type sequence: list
        :return: numpy byte buffer
    """

    attr_infos = collection[0].bl_rna.properties.get(attribute)

    assert attr_infos.type == "ENUM"

    enum_items = attr_infos.enum_items
    enum_idx = [i.value for i in enum_items]

    for index, item in enumerate(sequence):
        setattr(collection[index], attribute,
                enum_items[enum_idx.index(item)].identifier)


def np_load_collection_primitives(collection: bpy.types.CollectionProperty, attribute: str, sequence: str):
    """ Load a collection attribute from a str bytes sequence

        !!! warning
            Only work with int, float and bool attributes

        :arg collection: target collection
        :type collection: bpy.types.CollectionProperty
        :arg attribute: target attribute
        :type attribute: str
        :arg sequence: data buffer
        :type sequence: strr
    """
    if len(collection) == 0 or not sequence:
        logging.debug(f"Skipping loading {attribute}")
        return

    attr_infos = collection[0].bl_rna.properties.get(attribute)

    assert attr_infos.type in ["FLOAT", "INT", "BOOLEAN"]

    collection.foreach_set(
        attribute,
        np.frombuffer(sequence, dtype=BPY_TO_NUMPY_TYPES.get(attr_infos.type)))


def remove_items_from_dict(d, keys, recursive=False):
    copy = dict(d)
    for k in keys:
        copy.pop(k, None)
    if recursive:
        for k in [k for k in copy.keys() if isinstance(copy[k], dict)]:
            copy[k] = remove_items_from_dict(copy[k], keys, recursive)
    return copy


def _is_dictionnary(v):
    return hasattr(v, "items") and callable(v.items)


def _dump_filter_type(t):
    return lambda x: isinstance(x, t)


def _dump_filter_type_by_name(t_name):
    return lambda x: t_name == x.__class__.__name__


def _dump_filter_array(array):
    # only primitive type array
    if not isinstance(array, T.bpy_prop_array):
        return False
    if len(array) > 0 and type(array[0]) not in [bool, float, int]:
        return False
    return True


def _dump_filter_default(default):
    if default is None:
        return False
    if type(default) is list:
        return False
    return True


def _load_filter_type(t, use_bl_rna=True):
    def filter_function(x):
        if use_bl_rna and x.bl_rna_property:
            return isinstance(x.bl_rna_property, t)
        else:
            return isinstance(x.read(), t)
    return filter_function


def _load_filter_array(array):
    # only primitive type array
    if not isinstance(array.read(), T.bpy_prop_array):
        return False
    if len(array.read()) > 0 and type(array.read()[0]) not in [bool, float, int]:
        return False
    return True


def _load_filter_color(color):
    return color.__class__.__name__ == 'Color'


def _load_filter_default(default):
    if default.read() is None:
        return False
    if type(default.read()) is list:
        return False
    return True


class Dumper:
    # TODO: support occlude readonly
    # TODO: use foreach_set/get on collection compatible properties
    def __init__(self):
        self.verbose = True
        self.depth = 1
        self.keep_compounds_as_leaves = False
        self.accept_read_only = True
        self._build_inline_dump_functions()
        self._build_match_elements()
        self.type_subset = self.match_subset_all
        self.include_filter = []
        self.exclude_filter = ['session_uid']

    def dump(self, any):
        return self._dump_any(any, 0)

    def _dump_any(self, any, depth):
        for filter_function, dump_function in self.type_subset:
            if filter_function(any):
                return dump_function[not (depth >= self.depth)](any, depth + 1)

    def _build_inline_dump_functions(self):
        self._dump_identity = (lambda x, depth: x, lambda x, depth: x)
        self._dump_ref = (lambda x, depth: x.name, self._dump_object_as_branch)
        self._dump_ID = (lambda x, depth: x.name, self._dump_default_as_branch)
        self._dump_collection = (
            self._dump_default_as_leaf, self._dump_collection_as_branch)
        self._dump_array = (self._dump_array_as_branch,
                            self._dump_array_as_branch)
        self._dump_matrix = (self._dump_matrix_as_leaf,
                             self._dump_matrix_as_leaf)
        self._dump_vector = (self._dump_vector_as_leaf,
                             self._dump_vector_as_leaf)
        self._dump_quaternion = (
            self._dump_quaternion_as_leaf, self._dump_quaternion_as_leaf)
        self._dump_default = (self._dump_default_as_leaf,
                              self._dump_default_as_branch)
        self._dump_color = (self._dump_color_as_leaf, self._dump_color_as_leaf)

    def _build_match_elements(self):
        self._match_type_bool = (_dump_filter_type(bool), self._dump_identity)
        self._match_type_int = (_dump_filter_type(int), self._dump_identity)
        self._match_type_float = (
            _dump_filter_type(float), self._dump_identity)
        self._match_type_string = (_dump_filter_type(str), self._dump_identity)
        self._match_type_ref = (_dump_filter_type(T.Object), self._dump_ref)
        self._match_type_ID = (_dump_filter_type(T.ID), self._dump_ID)
        self._match_type_bpy_prop_collection = (
            _dump_filter_type(T.bpy_prop_collection), self._dump_collection)
        self._match_type_array = (_dump_filter_array, self._dump_array)
        self._match_type_matrix = (_dump_filter_type(
            mathutils.Matrix), self._dump_matrix)
        self._match_type_vector = (_dump_filter_type(
            mathutils.Vector), self._dump_vector)
        self._match_type_quaternion = (_dump_filter_type(
            mathutils.Quaternion), self._dump_quaternion)
        self._match_type_euler = (_dump_filter_type(
            mathutils.Euler), self._dump_quaternion)
        self._match_type_color = (
            _dump_filter_type_by_name("Color"), self._dump_color)
        self._match_default = (_dump_filter_default, self._dump_default)

    def _dump_collection_as_branch(self, collection, depth):
        dump = {}
        for i in collection.items():
            dv = self._dump_any(i[1], depth)
            if not (dv is None):
                dump[i[0]] = dv
        return dump

    def _dump_default_as_leaf(self, default, depth):
        if self.keep_compounds_as_leaves:
            return str(type(default))
        else:
            return None

    def _dump_array_as_branch(self, array, depth):
        return [i for i in array]

    def _dump_matrix_as_leaf(self, matrix, depth):
        return [list(v) for v in matrix]

    def _dump_vector_as_leaf(self, vector, depth):
        return list(vector)

    def _dump_quaternion_as_leaf(self, quaternion, depth):
        return list(quaternion)

    def _dump_color_as_leaf(self, color, depth):
        return list(color)

    def _dump_object_as_branch(self, default, depth):
        if depth == 1:
            return self._dump_default_as_branch(default, depth)
        else:
            return default.name

    def _dump_default_as_branch(self, default, depth):
        def is_valid_property(p):
            try:
                if (self.include_filter and p not in self.include_filter):
                    return False
                getattr(default, p)
            except AttributeError as err:
                logging.debug(err)
                return False
            if p.startswith("__"):
                return False
            if callable(getattr(default, p)):
                return False
            if p in ["bl_rna", "rna_type"]:
                return False
            return True

        all_property_names = [p for p in dir(default) if is_valid_property(
            p) and p != '' and p not in self.exclude_filter]
        dump = {}
        for p in all_property_names:
            if (self.exclude_filter and p in self.exclude_filter) or\
                    (self.include_filter and p not in self.include_filter):
                return False
            dp = self._dump_any(getattr(default, p), depth)
            if not (dp is None):
                dump[p] = dp
        return dump

    @property
    def match_subset_all(self):
        return [
            self._match_type_bool,
            self._match_type_int,
            self._match_type_float,
            self._match_type_string,
            self._match_type_ref,
            self._match_type_ID,
            self._match_type_bpy_prop_collection,
            self._match_type_array,
            self._match_type_matrix,
            self._match_type_vector,
            self._match_type_quaternion,
            self._match_type_euler,
            self._match_type_color,
            self._match_default
        ]

    @property
    def match_subset_primitives(self):
        return [
            self._match_type_bool,
            self._match_type_int,
            self._match_type_float,
            self._match_type_string,
            self._match_default
        ]


class BlenderAPIElement:
    def __init__(self, api_element, sub_element_name="", occlude_read_only=True):
        self.api_element = api_element
        self.sub_element_name = sub_element_name
        self.occlude_read_only = occlude_read_only

    def read(self):
        return getattr(self.api_element, self.sub_element_name) if self.sub_element_name else self.api_element

    def write(self, value):
        # take precaution if property is read-only
        if self.sub_element_name and \
                not self.api_element.is_property_readonly(self.sub_element_name):

            setattr(self.api_element, self.sub_element_name, value)
        else:
            self.api_element = value

    def extend(self, element_name):
        return BlenderAPIElement(self.read(), element_name)

    @property
    def bl_rna_property(self):
        if not hasattr(self.api_element, "bl_rna"):
            return False
        if not self.sub_element_name:
            return False
        return self.api_element.bl_rna.properties[self.sub_element_name]


class Loader:
    def __init__(self):
        self.type_subset = self.match_subset_all
        self.occlude_read_only = False
        self.order = ['*']
        self.exclure_filter = []

    def load(self, dst_data, src_dumped_data):
        self._load_any(
            BlenderAPIElement(
                dst_data, occlude_read_only=self.occlude_read_only),
            src_dumped_data
        )

    def _load_any(self, any, dump):
        for filter_function, load_function in self.type_subset:
            if filter_function(any) and any.sub_element_name not in self.exclure_filter:
                load_function(any, dump)
                return

    def _load_identity(self, element, dump):
        element.write(dump)

    def _load_array(self, element, dump):
        # supports only primitive types currently
        try:
            for i in range(len(dump)):
                element.read()[i] = dump[i]
        except AttributeError as err:
            logging.debug(err)
            if not self.occlude_read_only:
                raise err

    def _load_collection(self, element, dump):
        if not element.bl_rna_property:
            return
        # local enum
        CONSTRUCTOR_NEW = "new"
        CONSTRUCTOR_ADD = "add"

        DESTRUCTOR_REMOVE = "remove"
        DESTRUCTOR_CLEAR = "clear"

        _constructors = {
            T.ColorRampElement: (CONSTRUCTOR_NEW, ["position"]),
            T.ParticleSettingsTextureSlot: (CONSTRUCTOR_ADD, []),
            T.GpencilModifier: (CONSTRUCTOR_NEW, ["name", "type"]),
        }

        destructors = {
            T.ColorRampElement: DESTRUCTOR_REMOVE,
            T.GpencilModifier: DESTRUCTOR_CLEAR,
        }
        element_type = element.bl_rna_property.fixed_type

        _constructor = _constructors.get(type(element_type))

        if _constructor is None:  # collection type not supported
            return

        destructor = destructors.get(type(element_type))

        # Try to clear existing
        if destructor:
            if destructor == DESTRUCTOR_REMOVE:
                collection = element.read()
                elems_to_remove = len(collection)

                # Color ramp doesn't allow to remove all elements
                if type(element_type) is T.ColorRampElement:
                    elems_to_remove -= 1

                for i in range(elems_to_remove):
                    collection.remove(collection[0])
            else:
                getattr(element.read(), DESTRUCTOR_CLEAR)()

        for dump_idx, dumped_element in enumerate(dump.values()):
            if dump_idx == 0 and len(element.read()) > 0:
                new_element = element.read()[0]
            else:
                try:
                    _constructor_parameters = [
                        dumped_element[name] for name in _constructor[1]
                    ]
                except KeyError:
                    logging.debug("Collection load error, missing parameters.")
                    continue  # TODO handle error

                new_element = getattr(element.read(), _constructor[0])(
                    *_constructor_parameters)
            self._load_any(
                BlenderAPIElement(
                    new_element, occlude_read_only=self.occlude_read_only),
                dumped_element
            )

    def _load_curve_mapping(self, element, dump):
        mapping = element.read()
        curves = mapping.curves

        for curve_index, curve in dump['curves'].items():
            dst_curve = curves[curve_index]

            # cleanup existing curve
            for idx in range(len(dst_curve.points), 0, -1):
                try:
                    dst_curve.points.remove(dst_curve.points[0])
                except Exception:
                    break

            default_point_count = len(dst_curve.points)

            for point_idx, point in curve['points'].items():
                pos = point['location']

                if point_idx < default_point_count:
                    dst_curve.points[int(point_idx)].location = pos
                else:
                    dst_curve.points.new(pos[0], pos[1])
        curves.update()

    def _load_pointer(self, instance, dump):
        rna_property_type = instance.bl_rna_property.fixed_type
        if not rna_property_type:
            return
        if isinstance(rna_property_type, T.Image):
            instance.write(bpy.data.images.get(dump))
        elif isinstance(rna_property_type, T.Texture):
            instance.write(bpy.data.textures.get(dump))
        elif isinstance(rna_property_type, T.ColorRamp):
            self._load_default(instance, dump)
        elif isinstance(rna_property_type, T.NodeTree):
            instance.write(bpy.data.node_groups.get(dump))
        elif isinstance(rna_property_type, T.Object):
            instance.write(bpy.data.objects.get(dump))
        elif isinstance(rna_property_type, T.Mesh):
            instance.write(bpy.data.meshes.get(dump))
        elif isinstance(rna_property_type, T.Material):
            instance.write(bpy.data.materials.get(dump))
        elif isinstance(rna_property_type, T.Collection):
            instance.write(bpy.data.collections.get(dump))
        elif isinstance(rna_property_type, T.VectorFont):
            instance.write(bpy.data.fonts.get(dump))
        elif isinstance(rna_property_type, T.Sound):
            instance.write(bpy.data.sounds.get(dump))
        # elif isinstance(rna_property_type, T.ParticleSettings):
        #     instance.write(bpy.data.particles.get(dump))

    def _load_matrix(self, matrix, dump):
        matrix.write(mathutils.Matrix(dump))

    def _load_vector(self, vector, dump):
        vector.write(mathutils.Vector(dump))

    def _load_quaternion(self, quaternion, dump):
        quaternion.write(mathutils.Quaternion(dump))

    def _load_euler(self, euler, dump):
        euler.write(mathutils.Euler(dump))

    def _ordered_keys(self, keys):
        ordered_keys = []
        for order_element in self.order:
            if order_element == '*':
                ordered_keys += [k for k in keys if not k in self.order]
            else:
                if order_element in keys:
                    ordered_keys.append(order_element)
        return ordered_keys

    def _load_default(self, default, dump):
        if not _is_dictionnary(dump):
            return  # TODO error handling
        for k in self._ordered_keys(dump.keys()):
            v = dump[k]
            if not hasattr(default.read(), k):
                continue
            try:
                self._load_any(default.extend(k), v)
            except Exception:
                logging.debug(f"Skipping {k}")

    @property
    def match_subset_all(self):
        return [
            (_load_filter_type(T.BoolProperty), self._load_identity),
            (_load_filter_type(T.IntProperty), self._load_identity),
            # before float because bl_rna type of matrix if FloatProperty
            (_load_filter_type(mathutils.Matrix, use_bl_rna=False), self._load_matrix),
            # before float because bl_rna type of vector if FloatProperty
            (_load_filter_type(mathutils.Vector, use_bl_rna=False), self._load_vector),
            (_load_filter_type(mathutils.Quaternion,
                               use_bl_rna=False), self._load_quaternion),
            (_load_filter_type(mathutils.Euler, use_bl_rna=False), self._load_euler),
            (_load_filter_type(T.CurveMapping,  use_bl_rna=False),
             self._load_curve_mapping),
            (_load_filter_type(T.FloatProperty), self._load_identity),
            (_load_filter_type(T.StringProperty), self._load_identity),
            (_load_filter_type(T.EnumProperty), self._load_identity),
            (_load_filter_type(T.PointerProperty), self._load_pointer),
            (_load_filter_array, self._load_array),
            (_load_filter_type(T.CollectionProperty), self._load_collection),
            (_load_filter_default, self._load_default),
            (_load_filter_color, self._load_identity),
        ]


# Utility functions
def dump(any, depth=1):
    dumper = Dumper()
    dumper.depth = depth
    return dumper.dump(any)


def load(dst, src):
    loader = Loader()
    loader.load(dst, src)
