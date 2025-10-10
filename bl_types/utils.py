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
import math
import time
from collections.abc import Iterable
from pathlib import Path

import bpy
from .replication.constants import (CONNECTING, STATE_ACTIVE, STATE_AUTH,
                                   STATE_CONFIG, STATE_INITIAL, STATE_LOBBY,
                                   STATE_QUITTING, STATE_SRV_SYNC,
                                   STATE_SYNCING, STATE_WAITING)


CLEARED_DATABLOCKS = [
    "actions",
    "armatures",
    "cache_files",
    "cameras",
    "collections",
    "curves",
    "filepath",
    "fonts",
    "grease_pencils",
    "grease_pencils_v3",
    "images",
    "lattices",
    "libraries",
    "lightprobes",
    "lights",
    "linestyles",
    "masks",
    "materials",
    "meshes",
    "metaballs",
    "movieclips",
    "node_groups",
    "objects",
    "paint_curves",
    "particles",
    "scenes",
    "shape_keys",
    "sounds",
    "speakers",
    "texts",
    "textures",
    "volumes",
    "worlds",
]


def find_from_attr(attr_name, attr_value, list):
    for item in list:
        if getattr(item, attr_name, None) == attr_value:
            return item
    return None


def flush_history():
    try:
        logging.debug("Flushing history")
        for i in range(bpy.context.preferences.edit.undo_steps+1):
            bpy.ops.ed.undo_push(message="Multiuser history flush")
    except RuntimeError:
        logging.error("Fail to overwrite history")


def get_state_str(state):
    state_str = 'UNKOWN'
    if state == STATE_WAITING:
        state_str = 'WARMING UP DATA'
    elif state == STATE_SYNCING:
        state_str = 'FETCHING'
    elif state == STATE_AUTH:
        state_str = 'AUTHENTICATION'
    elif state == STATE_CONFIG:
        state_str = 'CONFIGURATION'
    elif state == STATE_ACTIVE:
        state_str = 'ONLINE'
    elif state == STATE_SRV_SYNC:
        state_str = 'PUSHING'
    elif state == STATE_INITIAL:
        state_str = 'OFFLINE'
    elif state == STATE_QUITTING:
        state_str = 'QUITTING'
    elif state == CONNECTING:
        state_str = 'LAUNCHING SERVICES'
    elif state == STATE_LOBBY:
        state_str = 'LOBBY'

    return state_str


def clean_scene():
    for type_name in CLEARED_DATABLOCKS:
        sub_collection_to_avoid = [
            bpy.data.linestyles.get('LineStyle'),
            bpy.data.materials.get('Dots Stroke')
        ]
        try:
            type_collection = getattr(bpy.data, type_name)
        except AttributeError:
            continue
        else:
            items_to_remove = [i for i in type_collection if i not in sub_collection_to_avoid]
            for item in items_to_remove:
                try:
                    type_collection.remove(item)
                    logging.info(item.name)
                except Exception:
                    continue

    # Clear sequencer
    bpy.context.scene.sequence_editor_clear()


def get_selected_objects(scene, active_view_layer):
    return [obj.uuid for obj in scene.objects if obj.select_get(view_layer=active_view_layer)]


def resolve_from_id(id, optionnal_type=None):
    for category in dir(bpy.data):
        root = getattr(bpy.data, category)
        if isinstance(root, Iterable):
            if id in root and ((optionnal_type is None) or (optionnal_type.lower() in root[id].__class__.__name__.lower())):
                return root[id]
    return None


def get_preferences():
    if __package__ not in bpy.context.preferences.addons:
        return None
    else:
        return bpy.context.preferences.addons[__package__].preferences


def current_milli_time():
    return int(round(time.time() * 1000))


def get_expanded_icon(prop: bpy.types.BoolProperty) -> str:
    if prop:
        return 'DISCLOSURE_TRI_DOWN'
    else:
        return 'DISCLOSURE_TRI_RIGHT'


# Taken from here: https://stackoverflow.com/a/55659577
def get_folder_size(folder):
    return ByteSize(sum(file.stat().st_size for file in Path(folder).rglob('*')))


class ByteSize(int):

    _kB = 1024
    _suffixes = 'B', 'kB', 'MB', 'GB', 'PB'

    def __new__(cls, *args, **kwargs):
        return super().__new__(cls, *args, **kwargs)

    def __init__(self, *args, **kwargs):
        self.bytes = self.B = int(self)
        self.kilobytes = self.kB = self / self._kB**1
        self.megabytes = self.MB = self / self._kB**2
        self.gigabytes = self.GB = self / self._kB**3
        self.petabytes = self.PB = self / self._kB**4
        *suffixes, last = self._suffixes
        suffix = next((
            suffix
            for suffix in suffixes
            if 1 < getattr(self, suffix) < self._kB
        ), last)
        self.readable = suffix, getattr(self, suffix)

        super().__init__()

    def __str__(self):
        return self.__format__('.2f')

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, super().__repr__())

    def __format__(self, format_spec):
        suffix, val = self.readable
        return '{val:{fmt}} {suf}'.format(val=math.ceil(val), fmt=format_spec, suf=suffix)

    def __sub__(self, other):
        return self.__class__(super().__sub__(other))

    def __add__(self, other):
        return self.__class__(super().__add__(other))

    def __mul__(self, other):
        return self.__class__(super().__mul__(other))

    def __rsub__(self, other):
        return self.__class__(super().__sub__(other))

    def __radd__(self, other):
        return self.__class__(super().__add__(other))

    def __rmul__(self, other):
        return self.__class__(super().__rmul__(other))

def is_annotating(context: bpy.types.Context):
    """ Check if the annotate mode is enabled
    """
    active_tool = bpy.context.workspace.tools.from_space_view3d_mode('OBJECT', create=False)
    return (active_tool and active_tool.idname == 'builtin.annotate')
