from pathlib import Path

import bpy

from .bl_file import get_filepath, ensure_unpacked
from .replication.protocol import ReplicatedDatablock
from .dump_anything import Loader
from .bl_datablock import resolve_datablock_from_uuid


class BlSound(ReplicatedDatablock):
    bl_id = "sounds"
    bl_class = bpy.types.Sound
    bl_check_common = False
    bl_icon = 'SOUND'
    bl_reload_parent = False

    @staticmethod
    def construct(data: dict) -> object:
        filename = data.get('filename')

        return bpy.data.sounds.load(get_filepath(filename))

    @staticmethod
    def load(data: dict, datablock: object):
        loader = Loader()
        loader.load(datablock, data)

    @staticmethod
    def dump(datablock: object) -> dict:
        filename = Path(datablock.filepath).name

        if not filename:
            raise FileExistsError(datablock.filepath)

        return {
            'filename': filename,
            'name': datablock.name
        }

    @staticmethod
    def resolve_deps(datablock: object) -> list[object]:
        deps = []
        if datablock.filepath and datablock.filepath != '<builtin>':
            ensure_unpacked(datablock)

            deps.append(Path(bpy.path.abspath(datablock.filepath)))

        return deps

    @staticmethod
    def resolve(data: dict) -> object:
        uuid = data.get('uuid')
        return resolve_datablock_from_uuid(uuid, bpy.data.sounds)

    @staticmethod
    def needs_update(datablock: object, data: dict) -> bool:
        return False


_type = bpy.types.Sound
_class = BlSound
