import bpy
import uuid

class Track:
    """
    Handles tracking of data blocks using bl types defined by bl_types by assigning uuids
    to them and subscribing to them if new ones appear so that new ones are assigned.
    """

    def __init__(self, bpy_protocol):
        # We keep track of these two internally but don't use them internally, might be useful later? idk
        self.uuids_index = {}
        self.owners = []
        
        self.bpy_types = bpy_protocol.implementations.items() # Only used to know which types to track.

    @staticmethod
    def _assign(uuids_index, bl_type):
        """
        Assign uuids to all datablocks of the given Blender type.
        """
        coll = getattr(bpy.data, bl_type.bl_id, None)
        if not coll:
            return

        for idb in coll:
            uid = getattr(idb, "cozystudio_uuid", "")
            if not uid:
                uid = str(uuid.uuid4())
                idb.cozystudio_uuid = uid
                idb.uuid = uid

            uuids_index[uid] = idb

    def _property(self):  # Assign property to every bl type.
        if not hasattr(bpy.types.ID, "cozystudio_uuid"):
            bpy.types.ID.cozystudio_uuid = bpy.props.StringProperty(
                default="", options={"HIDDEN"}
            )
        if not hasattr(bpy.types.ID, "uuid"):
            bpy.types.ID.uuid = bpy.props.StringProperty(
                default="", options={"HIDDEN"}
            )

    def subscribe(self, bl_type):
        """Subscribe to msgbus for specific data block creation."""
        owner = object()
        self.owners.append(owner)
        if not hasattr(bpy.types.BlendData, bl_type.bl_id):
            return
        subscribe_to = (bpy.types.BlendData, bl_type.bl_id)

        bpy.msgbus.subscribe_rna(
            key=subscribe_to,
            owner=owner,
            args=(self.uuids, self.uuids_index, bl_type),
            notify=self._assign,
            options={"PERSISTENT"},
        )

        bpy.msgbus.publish_rna(key=subscribe_to)

    def unsubscribe(self, owner):
        bpy.msgbus.clear_by_owner(owner)

    def start(self):
        """
        1. At registration, add property to all types
        2. assign a uuid to all `bl_types`
        3. initiate a monitor that checks for new datablocks in bpy.data collections so that we can
            assign new uuids for new data blocks
        """
        self._property()

        for type_name, impl_class in self.bpy_types:
            self._assign(self.uuids_index, impl_class)
            self.subscribe(impl_class)

    def stop(self):

        for owner in self.owners:
            self.unsubscribe(owner)
        self.owners.clear()
        self.uuids.clear()
        self.uuids_index.clear()
