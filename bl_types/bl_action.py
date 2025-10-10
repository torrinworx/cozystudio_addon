import bpy
import copy

from .replication.protocol import ReplicatedDatablock
from . import utils
from .bl_datablock import resolve_datablock_from_uuid
from .dump_anything import (
    Dumper,
    Loader,
    np_dump_collection,
    np_load_collection,
    remove_items_from_dict,
)

KEYFRAME = [
    "amplitude",
    "co",
    "back",
    "handle_left",
    "handle_right",
    "easing",
    "handle_left_type",
    "handle_right_type",
    "type",
    "interpolation",
]


def has_action(datablock):
    """Check if the datablock datablock has actions"""
    return (
        hasattr(datablock, "animation_data")
        and datablock.animation_data
        and datablock.animation_data.action
    )


def has_driver(datablock):
    """Check if the datablock datablock is driven"""
    return (
        hasattr(datablock, "animation_data")
        and datablock.animation_data
        and datablock.animation_data.drivers
    )


def dump_driver(driver):
    dumper = Dumper()
    dumper.depth = 6
    data = dumper.dump(driver)

    return data


def load_driver(target_datablock, src_driver):
    loader = Loader()
    drivers = target_datablock.animation_data.drivers
    src_driver_data = src_driver["driver"]
    new_driver = drivers.new(src_driver["data_path"], index=src_driver["array_index"])

    # Settings
    new_driver.driver.type = src_driver_data["type"]
    new_driver.driver.expression = src_driver_data["expression"]
    loader.load(new_driver, src_driver)

    # Variables
    for src_variable in src_driver_data["variables"]:
        src_var_data = src_driver_data["variables"][src_variable]
        new_var = new_driver.driver.variables.new()
        new_var.name = src_var_data["name"]
        new_var.type = src_var_data["type"]

        for src_target in src_var_data["targets"]:
            src_target_data = src_var_data["targets"][src_target]
            src_id = src_target_data.get("id")
            if src_id:
                new_var.targets[src_target].id = utils.resolve_from_id(
                    src_target_data["id"], src_target_data["id_type"]
                )
            loader.load(new_var.targets[src_target], src_target_data)

    # Fcurve
    new_fcurve = new_driver.keyframe_points
    for p in reversed(new_fcurve):
        new_fcurve.remove(p, fast=True)

    new_fcurve.add(len(src_driver["keyframe_points"]))

    for index, src_point in enumerate(src_driver["keyframe_points"]):
        new_point = new_fcurve[index]
        loader.load(new_point, src_driver["keyframe_points"][src_point])


def dump_fcurve(fcurve: bpy.types.FCurve, use_numpy: bool = True) -> dict:
    """Dump a sigle curve to a dict

    :arg fcurve: fcurve to dump
    :type fcurve: bpy.types.FCurve
    :arg use_numpy: use numpy to eccelerate dump
    :type use_numpy: bool
    :return: dict
    """
    fcurve_data = {
        "data_path": fcurve.data_path,
        "dumped_array_index": fcurve.array_index,
        "use_numpy": use_numpy,
    }

    if use_numpy:
        points = fcurve.keyframe_points
        fcurve_data["keyframes_count"] = len(fcurve.keyframe_points)
        fcurve_data["keyframe_points"] = np_dump_collection(points, KEYFRAME)
    else:  # Legacy method
        dumper = Dumper()
        fcurve_data["keyframe_points"] = []

        for k in fcurve.keyframe_points:
            fcurve_data["keyframe_points"].append(dumper.dump(k))

    if fcurve.modifiers:
        dumper = Dumper()
        dumper.exclude_filter = ["is_valid", "active"]
        dumped_modifiers = []
        for modfifier in fcurve.modifiers:
            dumped_modifiers.append(dumper.dump(modfifier))

        fcurve_data["modifiers"] = dumped_modifiers

    return fcurve_data


def load_fcurve(fcurve_data, fcurve):
    """Load a dumped fcurve

    :arg fcurve_data: a dumped fcurve
    :type fcurve_data: dict
    :arg fcurve: fcurve to dump
    :type fcurve: bpy.types.FCurve
    """
    use_numpy = fcurve_data.get("use_numpy")
    loader = Loader()
    keyframe_points = fcurve.keyframe_points

    # Remove all keyframe points
    for i in range(len(keyframe_points)):
        keyframe_points.remove(keyframe_points[0], fast=True)

    if use_numpy:
        keyframe_points.add(fcurve_data["keyframes_count"])
        np_load_collection(fcurve_data["keyframe_points"], keyframe_points, KEYFRAME)

    else:
        # paste dumped keyframes
        for dumped_keyframe_point in fcurve_data["keyframe_points"]:
            if dumped_keyframe_point["type"] == "":
                dumped_keyframe_point["type"] = "KEYFRAME"

            new_kf = keyframe_points.insert(
                dumped_keyframe_point["co"][0],
                dumped_keyframe_point["co"][1],
                options={"FAST", "REPLACE"},
            )

            keycache = copy.copy(dumped_keyframe_point)
            keycache = remove_items_from_dict(
                keycache, ["co", "handle_left", "handle_right", "type"]
            )

            loader = Loader()
            loader.load(new_kf, keycache)

            new_kf.type = dumped_keyframe_point["type"]
            new_kf.handle_left = [
                dumped_keyframe_point["handle_left"][0],
                dumped_keyframe_point["handle_left"][1],
            ]
            new_kf.handle_right = [
                dumped_keyframe_point["handle_right"][0],
                dumped_keyframe_point["handle_right"][1],
            ]

            fcurve.update()

    dumped_fcurve_modifiers = fcurve_data.get("modifiers", None)

    if dumped_fcurve_modifiers:
        # clear modifiers
        for fmod in fcurve.modifiers:
            fcurve.modifiers.remove(fmod)

        # Load each modifiers in order
        for modifier_data in dumped_fcurve_modifiers:
            modifier = fcurve.modifiers.new(modifier_data["type"])

            loader.load(modifier, modifier_data)
    elif fcurve.modifiers:
        for fmod in fcurve.modifiers:
            fcurve.modifiers.remove(fmod)


def dump_animation_data(datablock):
    animation_data = {}
    if has_action(datablock):
        animation_data["action"] = datablock.animation_data.action.uuid
    if has_driver(datablock):
        animation_data["drivers"] = []
        for driver in datablock.animation_data.drivers:
            animation_data["drivers"].append(dump_driver(driver))

    return animation_data


def load_animation_data(animation_data, datablock):
    # Load animation data
    if animation_data:
        if datablock.animation_data is None:
            datablock.animation_data_create()

        for d in datablock.animation_data.drivers:
            datablock.animation_data.drivers.remove(d)

        if "drivers" in animation_data:
            for driver in animation_data["drivers"]:
                load_driver(datablock, driver)

        action = animation_data.get("action")
        if action:
            action = resolve_datablock_from_uuid(action, bpy.data.actions)
            datablock.animation_data.action = action
        elif datablock.animation_data.action:
            datablock.animation_data.action = None

    # Remove existing animation data if there is not more to load
    elif hasattr(datablock, "animation_data") and datablock.animation_data:
        datablock.animation_data_clear()


def resolve_animation_dependencies(datablock):
    if has_action(datablock):
        return [datablock.animation_data.action]
    else:
        return []


class BlAction(ReplicatedDatablock):
    use_delta = True

    bl_id = "actions"
    bl_class = bpy.types.Action
    bl_check_common = False
    bl_icon = "ACTION_TWEAK"
    bl_reload_parent = False

    @staticmethod
    def construct(data: dict) -> object:
        return bpy.data.actions.new(data["name"])

    @staticmethod
    def load(data: dict, datablock: object):
        for dumped_fcurve in data["fcurves"]:
            dumped_data_path = dumped_fcurve["data_path"]
            dumped_array_index = dumped_fcurve["dumped_array_index"]

            # create fcurve if needed
            fcurve = datablock.fcurves.find(dumped_data_path, index=dumped_array_index)
            if fcurve is None:
                fcurve = datablock.fcurves.new(
                    dumped_data_path, index=dumped_array_index
                )

            load_fcurve(dumped_fcurve, fcurve)

        id_root = data.get("id_root")

        if id_root:
            datablock.id_root = id_root

    @staticmethod
    def dump(datablock: object) -> dict:
        dumper = Dumper()
        dumper.exclude_filter = [
            "name_full",
            "original",
            "use_fake_user",
            "user",
            "is_library_indirect",
            "select_control_point",
            "select_right_handle",
            "select_left_handle",
            "uuid",
            "users",
            "session_uid",
        ]
        dumper.depth = 1
        data = dumper.dump(datablock)

        data["fcurves"] = []

        for fcurve in datablock.fcurves:
            data["fcurves"].append(dump_fcurve(fcurve, use_numpy=True))

        return data

    @staticmethod
    def resolve(data: dict) -> object:
        uuid = data.get("uuid")
        return resolve_datablock_from_uuid(uuid, bpy.data.actions)

    @staticmethod
    def resolve_deps(datablock: object) -> [object]:
        return []


_type = bpy.types.Action
_class = BlAction
