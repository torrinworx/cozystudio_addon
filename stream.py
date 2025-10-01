"""
Stream raw depsgraph data blocks.

This class allows you to get a stream of despgraph data blocks from blender live as the blender file is being updated.

The allowed data blocks are only those that are reuqired to replicate a blender file over the wire. Data blocks not
essential to this task are ignored.

The class should return a .stream() function, a python generator that returns the stream of data blocks.

For each update we get from blender, there is a list of things in the blender file that have changed. We need to filter out
unrelated changes from that list, and return it from the generator.
"""

import bpy
import threading
import queue
from typing import Generator, Optional, List


# Define allowed datablock types
ALLOWED_TYPES = (
    bpy.types.Object,
    bpy.types.Mesh,
    bpy.types.Camera,
    bpy.types.Light,
    bpy.types.Curve,
    bpy.types.Armature,
    bpy.types.GreasePencil,
    bpy.types.Material,
    bpy.types.Image,
    bpy.types.World,
    bpy.types.Action,
    bpy.types.ShapeKey,
    bpy.types.Collection,
    bpy.types.Scene,
)

# Sentinel object for shutting down the generator
_SENTINEL = object()


class Updates:
    """
    Stream raw depsgraph datablocks for live collaboration.
    Hooks into `bpy.app.handlers.depsgraph_update_post`
    and captures allowed datablock updates as they occur.
    """

    def __init__(self):
        self.queue: queue.Queue = queue.Queue()
        self.active: bool = True
        bpy.app.handlers.depsgraph_update_post.append(self.on_update)

    def on_update(self, _, depsgraph: bpy.types.Depsgraph):
        """Collect updates from Blender's dependency graph."""
        try:
            # Filter updates
            filtered_updates: List[bpy.types.ID] = [
                update.id
                for update in depsgraph.updates
                if isinstance(update.id, ALLOWED_TYPES)
            ]

            if filtered_updates:
                self.queue.put(filtered_updates)
        except Exception as e:
            print(f"Error in on_update: {e}")

    def stream(self) -> Generator[List[bpy.types.ID], None, None]:
        """
        Generator that yields lists of datablocks from the queue.
        Each list corresponds to a depsgraph update event.
        """
        while self.active:
            try:
                filtered_updates = self.queue.get()
                if filtered_updates is _SENTINEL:
                    break
                yield filtered_updates
            except Exception as e:
                print(f"Error in stream generator: {e}")
            finally:
                self.queue.task_done()

    def close(self):
        """Unregister handler and cleanup."""
        if self.on_update in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(self.on_update)
        self.active = False
        self.queue.put(_SENTINEL)


# Singleton reference to the updates manager
_updates_manager: Optional[Updates] = None


def register():
    global _updates_manager
    if _updates_manager is None:
        _updates_manager = Updates()

        def print_updates():
            for update_list in _updates_manager.stream():
                for update in update_list:
                    print(update)

        thread = threading.Thread(target=print_updates, daemon=True)
        thread.start()


def unregister():
    global _updates_manager
    if _updates_manager:
        _updates_manager.close()
        _updates_manager = None
