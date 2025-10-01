"""
Stream updates from depsgraph, viewport, and object selection in Blender.

This module provides a unified `Updates` class with a `.stream()` method
that yields updates from multiple sources, useful for live collaboration
or real-time monitoring of Blender projects.
"""

import bpy
import queue
import threading
from typing import Generator, List, Dict, Any, Optional

# Sentinel object for shutting down the generator
_SENTINEL = object()

# Define allowed datablock types for depsgraph
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


class UpdateProvider:
    """
    Interface for update providers.
    Each provider must implement `start` and `stop` methods.
    """

    def start(self, q: queue.Queue):
        """Start the provider and begin pushing updates to the queue."""
        raise NotImplementedError

    def stop(self):
        """Stop the provider from pushing updates."""
        raise NotImplementedError


class DepsgraphProvider(UpdateProvider):
    """
    Provides updates from Blender's dependency graph.
    """

    def __init__(self):
        self.queue: Optional[queue.Queue] = None

    def _on_update(self, _, depsgraph: bpy.types.Depsgraph):
        """Callback for depsgraph updates."""
        try:
            filtered_updates = [
                u.id for u in depsgraph.updates if isinstance(u.id, ALLOWED_TYPES)
            ]
            if filtered_updates:
                update_data = {
                    "type": "depsgraph",
                    "updates": [id_.name for id_ in filtered_updates],
                }
                self.queue.put(update_data)
        except Exception as e:
            print(f"DepsgraphProvider error: {e}")

    def start(self, q: queue.Queue):
        self.queue = q
        bpy.app.handlers.depsgraph_update_post.append(self._on_update)

    def stop(self):
        if self._on_update in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(self._on_update)


class ViewportProvider(UpdateProvider):
    """
    Provides updates when the viewport state changes.
    """

    def __init__(self, interval: float = 0.1):
        self._running = False
        self._last_state: Optional[Dict] = None
        self.interval = interval
        self.queue: Optional[queue.Queue] = None

    def _get_state(self) -> Optional[Dict[str, Any]]:
        """Grab current viewport info from the first 3D view."""
        area = next((a for a in bpy.context.screen.areas if a.type == "VIEW_3D"), None)
        if not area:
            return None

        region = next((r for r in area.regions if r.type == "WINDOW"), None)
        if not region:
            return None

        space = area.spaces.active
        if not hasattr(space, "region_3d"):
            return None

        r3d = space.region_3d
        camera = space.camera
        camera_data = None
        if camera:
            camera_data = {
                "lens": camera.data.lens,
                "sensor_width": camera.data.sensor_width,
                "sensor_height": camera.data.sensor_height,
                "type": camera.data.type,
            }

        return {
            "region_width": region.width,
            "region_height": region.height,
            "view_matrix": [list(row) for row in r3d.view_matrix],
            "is_perspective": r3d.is_perspective,
            "camera_data": camera_data,
        }

    def _check(self):
        """Timer callback: compare and enqueue when viewport changes."""
        if not self._running:
            return None  # Stop the timer

        try:
            state = self._get_state()
            if state and state != self._last_state:
                self._last_state = state
                update_data = {
                    "type": "viewport",
                    "state": state,
                }
                self.queue.put(update_data)
        except Exception as e:
            print(f"ViewportProvider error: {e}")

        return self.interval  # Reschedule the timer

    def start(self, q: queue.Queue):
        self.queue = q
        self._running = True
        bpy.app.timers.register(self._check, first_interval=self.interval)
        print("ViewportProvider started.")

    def stop(self):
        self._running = False
        print("ViewportProvider stopped.")


class SelectionProvider(UpdateProvider):
    """
    Provides updates when the active object selection changes.
    """

    def __init__(self, interval: float = 0.1):
        self._running = False
        self._last_selection: Optional[List[str]] = None
        self.interval = interval
        self.queue: Optional[queue.Queue] = None

    def _get_selection(self) -> List[str]:
        """Get the list of currently selected object names."""
        return [obj.name for obj in bpy.context.selected_objects]

    def _check(self):
        """Timer callback: compare and enqueue when selection changes."""
        if not self._running:
            return None  # Stop the timer

        try:
            selection = self._get_selection()
            if selection != self._last_selection:
                self._last_selection = selection
                update_data = {
                    "type": "selection",
                    "selected_objects": selection,
                }
                self.queue.put(update_data)
        except Exception as e:
            print(f"SelectionProvider error: {e}")

        return self.interval  # Reschedule the timer

    def start(self, q: queue.Queue):
        self.queue = q
        self._running = True
        bpy.app.timers.register(self._check, first_interval=self.interval)
        print("SelectionProvider started.")

    def stop(self):
        self._running = False
        print("SelectionProvider stopped.")


class Updates:
    """
    Aggregates updates from multiple providers and exposes a unified stream.
    """

    def __init__(self, providers: List[UpdateProvider]):
        self.queue: queue.Queue = queue.Queue()
        self.providers = providers
        self.active = True

        # Start all providers
        for provider in self.providers:
            provider.start(self.queue)
        print(
            "Updates aggregator started with providers:",
            [type(p).__name__ for p in self.providers],
        )

    def stream(self) -> Generator[Dict[str, Any], None, None]:
        """
        Generator that yields update dictionaries from all providers.

        Yields:
            Dict[str, Any]: A dictionary representing an update.
        """
        while self.active:
            try:
                item = self.queue.get()
                if item is _SENTINEL:
                    break
                yield item
            except Exception as e:
                print(f"Updates stream error: {e}")
            finally:
                self.queue.task_done()

    def close(self):
        """Stop all providers and clean up."""
        if not self.active:
            return
        self.active = False
        for provider in self.providers:
            provider.stop()
        self.queue.put(_SENTINEL)
        print("Updates aggregator stopped.")


# Example usage:
_updates_manager: Optional[Updates] = None
_stream_thread: Optional[threading.Thread] = None


def _update_consumer():
    if not _updates_manager:
        print("No Updates manager is registered.")
        return

    for update in _updates_manager.stream():
        print("Received update:", update)


def register():
    global _updates_manager, _stream_thread
    if _updates_manager is None:
        providers = [
            DepsgraphProvider(),
            ViewportProvider(interval=0.1),
            SelectionProvider(interval=0.1),
        ]
        _updates_manager = Updates(providers)
        print("Updates manager registered.")

        # Start the consumer thread
        _stream_thread = threading.Thread(target=_update_consumer, daemon=True)
        _stream_thread.start()
        print("Update consumer thread started.")


def unregister():
    global _updates_manager, _stream_thread
    if _updates_manager:
        _updates_manager.close()
        _updates_manager = None
        print("Updates manager unregistered.")

    if _stream_thread:
        _stream_thread.join(timeout=0.5)
        _stream_thread = None
        print("Update consumer thread stopped.")
