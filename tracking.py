import bpy
from abc import ABC, abstractmethod

"""
"updates" are just generic commits. Not commits to a git repo, just a stream of updates from blender.

"updates" should give our system enough information to reconstruct the blender file if we monitor from blender open
to save .blend file.

"updates" should be able to be streamed to another client and reconstructed to view a "live collaboration"

in a git system that uses this updatees tracking system, assume that we commit the current state of a blender file:
1. initial commit.
2. bunch of depsgraph updates happen, user adds meshes and modifies the file, etc.
3. ui updates to diff between current blender file state of datablocks and step 1. initial commit.

so for the git system we don't really need live updates. But I wnat to design Updates so that we can use the same code for "updates"
in both the streaming and git commit systems. This way we have one source of truth for tracking updates.

The trick is just desigining this updates system so that it can return data blocks, only data blocks, that you would save to a
blender file, or that blender would consider savable. We need to exclude inbetween things, between when user onMouseDowns and onMouseUps
and only save the state onMouseUp. So we need to somehow also indicate if the despgraphs are "commitable" state.

Maybe Updates should be able to be called in two states for these purposes:
Updates().stream() # live streaming dedicated.
Updates().commits() # commits dedicated.

no matter the implementation, we need to ensure that we are commiting/returning the raw data blocks for each of the
permitted data blocks that we want, data blocks that:
- Blender would save, objects moving, assets added, textures changed, etc

and filter them for committs so that only:
- blender "savable" AND (aditional logic) commits that aren't "user messing around", (eg inbetween steps), these might need to be defined manually to be seaemless, but that's fine.


For streaming:
- commits are sent over the wire as they come in

for committing to blender git:
- some custom system that reads the last committed version, and the latest state of the data blocks. We don't need a constant
stream of data blocks, just the latest state. (remember that's how git works, it doesn't read constantly and commit every character
as you are typing, just the final changes you choose to commit, but it does diff between the current state and previous commits)


So after all that, each update should return their data blocks. But then what is the point of the Updates class? Do we even need it? 
couldn't we just create a list of strings of the updates to watch for and a simple for loop?
"""


class Update(ABC):
    """
    Base handler for a specific Blender data type.
    """

    registry = {}  # auto-registration

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if getattr(cls, "bpy_type", None) is not None:
            Update.registry[cls.bpy_type] = cls()

    @abstractmethod
    def commit(self, datablock, update):
        """Default commit = dump savable properties into a dict."""
        return {
            "type": datablock.__class__.__name__,
            "name": getattr(datablock, "name", None),
            "data": self._serialize_savable_props(datablock),
        }

    def _serialize_savable_props(self, datablock):
        data = {}
        for prop in datablock.bl_rna.properties:
            if prop.is_readonly or prop.is_runtime:
                continue
            try:
                value = getattr(datablock, prop.identifier)
                data[prop.identifier] = self._coerce(value)
            except Exception:
                # some props raise when accessed
                pass
        return data

    def _coerce(self, value):
        # Normalize values into JSON-safe structures
        if isinstance(value, (int, float, str, bool, type(None))):
            return value
        elif hasattr(value, "to_tuple"):  # e.g. Vector, Color
            return tuple(value)
        elif isinstance(value, (list, tuple)):
            return [self._coerce(v) for v in value]
        return str(value)  # fallback: store repr


# --------------------------------------------------------
# Example Handlers
# --------------------------------------------------------


class ObjectUpdate(Update):
    bpy_type = bpy.types.Object

    def commit(self, datablock, update):
        # custom: only transform + link to mesh ID
        return {
            "type": "Object",
            "name": datablock.name,
            "location": tuple(datablock.location),
            "rotation": tuple(datablock.rotation_euler),
            "scale": tuple(datablock.scale),
            "data": datablock.data.name if datablock.data else None,
        }


class MeshUpdate(Update):
    bpy_type = bpy.types.Mesh

    def commit(self, datablock, update):
        # custom: hash vertices instead of full dump
        verts = [tuple(v.co) for v in datablock.vertices]
        return {
            "type": "Mesh",
            "name": datablock.name,
            "vertex_count": len(verts),
            "vertices": verts,  # replace with hash in production
        }


class Updates:
    def __init__(self):
        self.handlers = Update.registry
        self.cache = {}

    def on_update(self, scene, depsgraph):
        commits = []
        for update in depsgraph.updates:
            datablock = update.id
            handler = self.handlers.get(type(datablock))
            if handler:
                commit_data = handler.commit(datablock, update)
                key = f"{commit_data['type']}:{commit_data['name']}"
                if self.cache.get(key) != commit_data:
                    self.cache[key] = commit_data
                    commits.append(commit_data)
        if commits:
            print("COMMITS:", commits)


updates_manager = None


def register():
    global updates_manager
    updates_manager = Updates()
    bpy.app.handlers.depsgraph_update_post.append(updates_manager.on_update)


def unregister():
    global updates_manager
    if (
        updates_manager
        and updates_manager.on_update in bpy.app.handlers.depsgraph_update_post
    ):
        bpy.app.handlers.depsgraph_update_post.remove(updates_manager.on_update)
    updates_manager = None
