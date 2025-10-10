import bpy
# from deepdiff import DeepDiff, Delta
from .replication.protocol import ReplicatedDatablock

from . import utils
from .bl_datablock import resolve_datablock_from_uuid
from .dump_anything import Dumper, Loader


def dump_collection_children(collection):
    collection_children = []
    for child in collection.children:
        if child not in collection_children:
            collection_children.append(child.uuid)
    return collection_children


def dump_collection_objects(collection):
    collection_objects = []
    for object in collection.objects:
        if object not in collection_objects:
            collection_objects.append(object.uuid)

    return collection_objects


def load_collection_objects(dumped_objects, collection):
    for object in dumped_objects:
        object_ref = utils.find_from_attr('uuid', object, bpy.data.objects)

        if object_ref is None:
            continue
        elif object_ref.name not in collection.objects.keys():
            collection.objects.link(object_ref)

    for object in collection.objects:
        if object.uuid not in dumped_objects:
            collection.objects.unlink(object)


def load_collection_childrens(dumped_childrens, collection):
    for child_collection in dumped_childrens:
        collection_ref = utils.find_from_attr(
            'uuid',
            child_collection,
            bpy.data.collections)

        if collection_ref is None:
            continue
        if collection_ref.name not in collection.children.keys():
            collection.children.link(collection_ref)

    for child_collection in collection.children:
        if child_collection.uuid not in dumped_childrens:
            collection.children.unlink(child_collection)


def resolve_collection_dependencies(collection):
    deps = []

    for child in collection.children:
        deps.append(child)
    for object in collection.objects:
        deps.append(object)

    return deps


class BlCollection(ReplicatedDatablock):
    bl_id = "collections"
    bl_icon = 'FILE_FOLDER'
    bl_class = bpy.types.Collection
    bl_check_common = True
    bl_reload_parent = False

    use_delta = True

    @staticmethod
    def construct(data: dict) -> object:
        instance = bpy.data.collections.new(data["name"])
        return instance

    @staticmethod
    def load(data: dict, datablock: object):
        loader = Loader()
        loader.load(datablock, data)

        # Objects
        load_collection_objects(data['objects'], datablock)

        # Link childrens
        load_collection_childrens(data['children'], datablock)

        # FIXME: Find a better way after the replication big refacotoring
        # Keep other user from deleting collection object by flushing their history
        utils.flush_history()

    @staticmethod
    def dump(datablock: object) -> dict:
        dumper = Dumper()
        dumper.depth = 1
        dumper.include_filter = [
            "name",
            "instance_offset"
        ]
        data = dumper.dump(datablock)

        # dump objects
        data['objects'] = dump_collection_objects(datablock)

        # dump children collections
        data['children'] = dump_collection_children(datablock)

        return data

    @staticmethod
    def resolve(data: dict) -> object:
        uuid = data.get('uuid')
        return resolve_datablock_from_uuid(uuid, bpy.data.collections)

    @staticmethod
    def resolve_deps(datablock: object) -> list[object]:
        return resolve_collection_dependencies(datablock)

    # @staticmethod
    # def compute_delta(last_data: dict, current_data: dict) -> Delta:
    #     diff_params = {
    #         'ignore_order': True,
    #         'report_repetition': True
    #     }
    #     delta_params = {
    #         # 'mutate': True
    #     }

    #     return Delta(
    #         DeepDiff(last_data,
    #                  current_data,
    #                  cache_size=5000,
    #                  **diff_params),
    #         **delta_params)


_type = bpy.types.Collection
_class = BlCollection
