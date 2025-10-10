import sys
import bpy
import logging
from pathlib import Path, WindowsPath, PosixPath

from .replication.protocol import ReplicatedDatablock

from . import utils
from .utils import get_preferences


def get_filepath(filename):
    """
    Construct the local filepath
    """
    return str(Path(
        utils.get_preferences().cache_directory,
        filename
    ))


def ensure_unpacked(datablock):
    if datablock.packed_file:
        logging.info(f"Unpacking {datablock.name}")

        filename = Path(bpy.path.abspath(datablock.filepath)).name
        datablock.filepath = get_filepath(filename)

        datablock.unpack(method="WRITE_ORIGINAL")


class BlFile(ReplicatedDatablock):
    bl_id = 'file'
    bl_name = "file"
    bl_class = Path
    bl_check_common = False
    bl_icon = 'FILE'
    bl_reload_parent = True

    @staticmethod
    def construct(data: dict) -> object:
        return Path(get_filepath(data['name']))

    @staticmethod
    def resolve(data: dict) -> object:
        return Path(get_filepath(data['name']))

    @staticmethod
    def dump(datablock: object) -> dict:
        """
        Read the file and return a dict as:
        {
            name : filename
            extension :
            file: file content
        }
        """
        logging.info("Extracting file metadata")

        data = {
            'name': datablock.name,
        }

        logging.info(f"Reading {datablock.name} content: {datablock.stat().st_size} bytes")

        try:
            file = open(datablock, "rb")
            data['file'] = file.read()

            file.close()
        except IOError:
            logging.warning(f"{datablock} doesn't exist, skipping")
        else:
            file.close()

        return data

    @staticmethod
    def load(data: dict, datablock: object):
        """
        Writing the file
        """

        try:
            file = open(datablock, "wb")
            file.write(data['file'])

            if get_preferences().clear_memory_filecache:
                del data["file"]
        except IOError:
            logging.warning(f"{datablock} doesn't exist, skipping")
        else:
            file.close()

    @staticmethod
    def resolve_deps(datablock: object) -> list[object]:
        return []

    @staticmethod
    def needs_update(datablock: object, data: dict) -> bool:
        if get_preferences().clear_memory_filecache:
            return False
        else:
            if not datablock:
                return None

            if not data:
                return True

            memory_size = sys.getsizeof(data['file'])-33
            disk_size = datablock.stat().st_size

            if memory_size != disk_size:
                return True
            else:
                return False


_type = [WindowsPath, PosixPath]
_class = BlFile
