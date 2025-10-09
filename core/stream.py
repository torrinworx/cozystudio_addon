# """
# Stream updates from depsgraph, viewport, and object selection in Blender.

# This module provides a unified `Updates` class with a `.stream()` method
# that yields updates from multiple sources, useful for live collaboration.


# This file is designed to provide updates from a blender file, that can be
# used to re-assmble the entire blender file if needed.

# TODO:

# Fix massive performance issues with things like changing the materials using the color picker,
# or the metallic roughness sliders of a material on an object, these changes slow down and freeze
# blender. An issue with despgraph_update_post, maybe there is a built in way to throttle the updates
# get from blender?

# Need uuid tracking system.

# need to modify selected list of bpy.types and append a uuid to them.


# """

# import bpy
# import queue
# import threading
# from typing import Generator, List, Dict, Any, Optional

# _SENTINEL = object()

# ALLOWED_TYPES = (
#     bpy.types.Object,
#     bpy.types.Mesh,
#     bpy.types.Camera,
#     bpy.types.Light,
#     bpy.types.Curve,
#     bpy.types.Armature,
#     bpy.types.GreasePencil,
#     bpy.types.Material,
#     bpy.types.Image,
#     bpy.types.World,
#     bpy.types.Action,
#     bpy.types.ShapeKey,
#     bpy.types.Collection,
#     bpy.types.Scene,
# )


# class UpdateProvider:
#     """Base class for update providers with auto-registration of subclasses."""

#     registry: List[type] = []

#     def __init_subclass__(cls, **kwargs):
#         super().__init_subclass__(**kwargs)
#         UpdateProvider.registry.append(cls)

#     def start(self, q: queue.Queue):
#         raise NotImplementedError

#     def stop(self):
#         raise NotImplementedError


# class DepsgraphProvider(UpdateProvider):
#     def __init__(self, interval: float = 0.1):
#         self.queue: Optional[queue.Queue] = None
#         self.buffer_map = {}  # deduplication dict
#         self._running = False
#         self.interval = interval

#         self.last_material_values = {}

#     def _should_emit_material(self, mat: bpy.types.Material):
#         key = mat.as_pointer()
#         curr = (mat.metallic, mat.roughness)
#         prev = self.last_material_values.get(key)
#         if (
#             prev is None
#             or abs(curr[0] - prev[0]) > 0.001
#             or abs(curr[1] - prev[1]) > 0.001
#         ):
#             self.last_material_values[key] = curr
#             return True
#         return False

#     def _on_update(self, _, depsgraph: bpy.types.Depsgraph):
#         try:
#             for u in depsgraph.updates:
#                 if isinstance(u.id, ALLOWED_TYPES):
#                     # Deduplicate by datablock pointer
#                     self.buffer_map[u.id.as_pointer()] = u
#         except Exception as e:
#             print(f"DepsgraphProvider error: {e}")

#     def _flush(self):
#         if not self._running:
#             return None
#         if self.buffer_map:
#             # Emit only unique, latest updates
#             for u in self.buffer_map.values():
#                 # Optional: Skip noisy material updates if nearly identical
#                 if isinstance(
#                     u.id, bpy.types.Material
#                 ) and not self._should_emit_material(u.id):
#                     continue
#                 self.queue.put(u)
#             self.buffer_map.clear()
#         return self.interval

#     def test(self, scene, depsgraph):
#         print("test")

#     def start(self, q: queue.Queue):
#         self.queue = q
#         self._running = True

#         bpy.app.handlers.depsgraph_update_post.append(self._on_update)
#         bpy.app.timers.register(self._flush, first_interval=self.interval)

#     def stop(self):
#         self._running = False
#         if self._on_update in bpy.app.handlers.depsgraph_update_post:
#             bpy.app.handlers.depsgraph_update_post.remove(self._on_update)


# class ViewportProvider(UpdateProvider):
#     def __init__(self, interval: float = 0.1):
#         self._running = False
#         self._last_state: Optional[Dict] = None
#         self.interval = interval
#         self.queue: Optional[queue.Queue] = None

#     def _get_state(self) -> Optional[Dict[str, Any]]:
#         area = next((a for a in bpy.context.screen.areas if a.type == "VIEW_3D"), None)
#         if not area:
#             return None

#         region = next((r for r in area.regions if r.type == "WINDOW"), None)
#         if not region:
#             return None

#         space = area.spaces.active
#         if not hasattr(space, "region_3d"):
#             return None

#         r3d = space.region_3d
#         camera = space.camera
#         camera_data = None
#         if camera:
#             camera_data = {
#                 "lens": camera.data.lens,
#                 "sensor_width": camera.data.sensor_width,
#                 "sensor_height": camera.data.sensor_height,
#                 "type": camera.data.type,
#             }

#         return {
#             "region_width": region.width,
#             "region_height": region.height,
#             "view_matrix": [list(row) for row in r3d.view_matrix],
#             "is_perspective": r3d.is_perspective,
#             "camera_data": camera_data,
#         }

#     def _check(self):
#         if not self._running:
#             return None
#         try:
#             state = self._get_state()
#             if state and state != self._last_state:
#                 self._last_state = state
#                 self.queue.put(
#                     {
#                         "type": "viewport",
#                         "state": state,
#                     }
#                 )
#         except Exception as e:
#             print(f"ViewportProvider error: {e}")
#         return self.interval

#     def start(self, q: queue.Queue):
#         self.queue = q
#         self._running = True
#         bpy.app.timers.register(self._check, first_interval=self.interval)
#         print("ViewportProvider started.")

#     def stop(self):
#         self._running = False
#         print("ViewportProvider stopped.")


# class SelectionProvider(UpdateProvider):
#     def __init__(self, interval: float = 0.1):
#         self._running = False
#         self._last_selection: Optional[List[str]] = None
#         self.interval = interval
#         self.queue: Optional[queue.Queue] = None

#     def _get_selection(self) -> List[str]:
#         return [obj.name for obj in bpy.context.selected_objects]

#     def _check(self):
#         if not self._running:
#             return None
#         try:
#             selection = self._get_selection()
#             if selection != self._last_selection:
#                 self._last_selection = selection
#                 self.queue.put(
#                     {
#                         "type": "selection",
#                         "selected_objects": selection,
#                     }
#                 )
#         except Exception as e:
#             print(f"SelectionProvider error: {e}")
#         return self.interval

#     def start(self, q: queue.Queue):
#         self.queue = q
#         self._running = True
#         bpy.app.timers.register(self._check, first_interval=self.interval)
#         print("SelectionProvider started.")

#     def stop(self):
#         self._running = False
#         print("SelectionProvider stopped.")


# class Updates:
#     """Aggregates updates from all auto-registered providers."""

#     def __init__(self):
#         self.queue: queue.Queue = queue.Queue()
#         # Instantiate every registered provider
#         self.providers = [cls() for cls in UpdateProvider.registry]
#         self.active = True

#         for provider in self.providers:
#             provider.start(self.queue)

#         print(
#             "Updates aggregator started with providers:",
#             [type(p).__name__ for p in self.providers],
#         )

#     def stream(self) -> Generator[Dict[str, Any], None, None]:
#         while self.active:
#             try:
#                 item = self.queue.get()
#                 if item is _SENTINEL:
#                     break
#                 yield item
#             except Exception as e:
#                 print(f"Updates stream error: {e}")
#             finally:
#                 self.queue.task_done()

#     def close(self):
#         if not self.active:
#             return
#         self.active = False
#         for provider in self.providers:
#             provider.stop()
#         self.queue.put(_SENTINEL)
#         print("Updates aggregator stopped.")


# # Example usage
# _updates_manager: Optional[Updates] = None
# _stream_thread: Optional[threading.Thread] = None


# def _update_consumer():
#     if not _updates_manager:
#         print("No Updates manager is registered.")
#         return
#     for update in _updates_manager.stream():
#         print("Received update:", update)


# def register():
#     global _updates_manager, _stream_thread
#     if _updates_manager is None:
#         _updates_manager = Updates()
#         print("Updates manager registered.")

#         _stream_thread = threading.Thread(target=_update_consumer, daemon=True)
#         _stream_thread.start()
#         print("Update consumer thread started.")


# def unregister():
#     global _updates_manager, _stream_thread
#     if _updates_manager:
#         _updates_manager.close()
#         _updates_manager = None
#         print("Updates manager unregistered.")

#     if _stream_thread:
#         _stream_thread.join(timeout=0.5)
#         _stream_thread = None
#         print("Update consumer thread stopped.")
