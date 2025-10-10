import bpy
from pathlib import Path

from .replication.protocol import ReplicatedDatablock
from .dump_anything import Dumper, Loader
from .bl_file import get_filepath
from .bl_datablock import resolve_datablock_from_uuid


format_to_ext = {
    'BMP': 'bmp',
    'IRIS': 'sgi',
    'PNG': 'png',
    'JPEG': 'jpg',
    'JPEG2000': 'jp2',
    'TARGA': 'tga',
    'TARGA_RAW': 'tga',
    'CINEON': 'cin',
    'DPX': 'dpx',
    'OPEN_EXR_MULTILAYER': 'exr',
    'OPEN_EXR': 'exr',
    'HDR': 'hdr',
    'TIFF': 'tiff',
    'AVI_JPEG': 'avi',
    'AVI_RAW': 'avi',
    'FFMPEG': 'mpeg',
}


class BlImage(ReplicatedDatablock):
    bl_id = "images"
    bl_class = bpy.types.Image
    bl_check_common = False
    bl_icon = 'IMAGE_DATA'
    bl_reload_parent = False

    @staticmethod
    def construct(data: dict) -> object:
        return bpy.data.images.new(
            name=data['name'],
            width=data['size'][0],
            height=data['size'][1]
        )

    @staticmethod
    def load(data: dict, datablock: object):
        loader = Loader()
        loader.load(datablock, data)

        # datablock.name = data.get('name')
        datablock.source = 'FILE'
        datablock.filepath_raw = get_filepath(data['filename'])
        color_space_name = data.get("colorspace")

        if color_space_name:
            datablock.colorspace_settings.name = color_space_name

    @staticmethod
    def dump(datablock: object) -> dict:
        filename = Path(datablock.filepath).name

        data = {
            "filename": filename
        }

        dumper = Dumper()
        dumper.depth = 2
        dumper.include_filter = [
            "name",
            # 'source',
            'size',
            'alpha_mode']
        data.update(dumper.dump(datablock))
        data['colorspace'] = datablock.colorspace_settings.name

        return data

    @staticmethod
    def resolve(data: dict) -> object:
        uuid = data.get('uuid')
        return resolve_datablock_from_uuid(uuid, bpy.data.images)

    @staticmethod
    def resolve_deps(datablock: object) -> list[object]:
        deps = []

        if datablock.packed_file:
            filename = Path(bpy.path.abspath(datablock.filepath)).name
            datablock.filepath_raw = get_filepath(filename)
            datablock.save()
            # An image can't be unpacked to the modified path
            # TODO: make a bug report
            datablock.unpack(method="REMOVE")

        elif datablock.source == "GENERATED":
            filename = f"{datablock.name}.png"
            datablock.filepath = get_filepath(filename)
            datablock.save()

        if datablock.filepath:
            deps.append(Path(bpy.path.abspath(datablock.filepath)))

        return deps

    @staticmethod
    def needs_update(datablock: object, data:dict)-> bool:
        if datablock.is_dirty:
            datablock.save()

        return True


_type = bpy.types.Image
_class = BlImage
