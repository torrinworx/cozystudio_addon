import bpy
import uuid

from ..core._bl_types import _bl_types


class Track:
    """
    Handles tracking of bl_types. Assignes uuids to specific blender data blocks so that depsgraph can
    be parsed more efficiently.
    """

    def __init__(self):
        self.uuids = set()
        self.uuids_index = {}
        self.owners = []

    @staticmethod
    def _assign(uuids, uuids_index, bl_type):
        """
        Assign uuids to all datablocks of the given Blender type.
        """
        coll = getattr(bpy.data, f"{bl_type['name']}", None)
        if not coll:
            return

        for idb in coll:
            uid = getattr(idb, "cozystudio_uuid", "")
            if not uid:
                uid = str(uuid.uuid4())
                idb.cozystudio_uuid = uid

            uuids.add(uid)
            uuids_index[uid] = idb

    def _property(self):  # Assign property to every bl type.
        if not hasattr(bpy.types.ID, "cozystudio_uuid"):
            bpy.types.ID.cozystudio_uuid = bpy.props.StringProperty(
                default="", options={"HIDDEN"}
            )

        if not hasattr(bpy.types.ID, "uuid"):
            bpy.types.ID.uuid = bpy.props.StringProperty(
                default="", options={"HIDDEN", "SKIP_SAVE"}
            )

    def subscribe(self, bl_type):
        """Subscribe to msgbus for specific data block creation."""
        owner = object()
        self.owners.append(owner)
        subscribe_to = (bpy.types.BlendData, bl_type["name"])

        bpy.msgbus.subscribe_rna(
            key=subscribe_to,
            owner=owner,
            args=(self.uuids, self.uuids_index, bl_type),
            notify=self._assign,
            options={"PERSISTENT"},
        )

        bpy.msgbus.publish_rna(key=(bpy.types.BlendData, bl_type["name"]))

    def unsubscribe(self, owner):
        bpy.msgbus.clear_by_owner(owner)

    def find_by_uuid(self, uid):
        """Return datablock reference for a given UUID, or None."""
        return self.uuids_index.get(uid, None)

    def start(self):
        """
        1. At registration, add property to all types
        2. assign a uuid to all `bl_types`
        3. initiate a monitor that checks for new datablocks in bpy.data collections so that we can
            assign new uuids for new data blocks
        """
        self._property()

        for t in _bl_types:
            self._assign(self.uuids, self.uuids_index, t)
            self.subscribe(t)

    def stop(self):

        for owner in self.owners:
            self.unsubscribe(owner)
        self.owners.clear()
        self.uuids.clear()
        self.uuids_index.clear()
