import bpy
from pathlib import Path

from .replication.protocol import ReplicatedDatablock
from .bl_datablock import resolve_datablock_from_uuid
from .bl_file import ensure_unpacked, get_filepath


class BlFont(ReplicatedDatablock):
    bl_id = "fonts"
    bl_class = bpy.types.VectorFont
    bl_check_common = False
    bl_icon = 'FILE_FONT'
    bl_reload_parent = False

    @staticmethod
    def construct(data: dict) -> object:
        filename = data.get('filename')

        if filename == '<builtin>':
            return bpy.data.fonts.load(filename)
        else:
            return bpy.data.fonts.load(get_filepath(filename))

    @staticmethod
    def load(data: dict, datablock: object):
        pass

    @staticmethod
    def dump(datablock: object) -> dict:
        if datablock.filepath == '<builtin>':
            filename = '<builtin>'
        else:
            filename = Path(datablock.filepath).name

        if not filename:
            raise FileExistsError(datablock.filepath)

        return {
            'filename': filename,
            'name': datablock.name
        }

    @staticmethod
    def resolve(data: dict) -> object:
        uuid = data.get('uuid')
        return resolve_datablock_from_uuid(uuid, bpy.data.fonts)

    @staticmethod
    def resolve_deps(datablock: object) -> list[object]:
        deps = []
        if datablock.filepath and datablock.filepath != '<builtin>':
            ensure_unpacked(datablock)

            deps.append(Path(bpy.path.abspath(datablock.filepath)))

        return deps

    @staticmethod
    def needs_update(datablock: object, data: dict) -> bool:
        return False


_type = bpy.types.VectorFont
_class = BlFont
