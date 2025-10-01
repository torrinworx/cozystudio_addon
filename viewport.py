import bpy

_last_state = None
_running = False


def get_viewport_state():
    """Grab current viewport info from the first 3D view."""
    area = next((a for a in bpy.context.screen.areas if a.type == "VIEW_3D"), None)
    if not area:
        return None

    region = next((r for r in area.regions if r.type == "WINDOW"), None)
    if not region:
        return None

    space = area.spaces.active
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
        "view_matrix": tuple(map(tuple, r3d.view_matrix)),
        "is_perspective": r3d.is_perspective,
        "camera_data": camera_data,
    }


def _check(interval):
    """Timer callback: compare and print when viewport changes."""
    global _last_state, _running
    if not _running:
        return None  # stop timer

    state = get_viewport_state()
    if state and state != _last_state:
        _last_state = state
        print("Viewport changed:", state)

    return interval  # reschedule this timer


def start_viewport_watcher(interval=0.2):
    """Begin monitoring viewport changes with a repeating timer."""
    global _running
    if not _running:
        _running = True
        bpy.app.timers.register(lambda: _check(interval), first_interval=interval)


def stop_viewport_watcher():
    """Stop monitoring."""
    global _running
    _running = False


# Blender add‑on entry points
def register():
    start_viewport_watcher(0.05)


def unregister():
    stop_viewport_watcher()
