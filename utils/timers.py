import bpy

class Timers:
    """
    Utility for managing Blender timer registration/unregistration globally.
    """

    def __init__(self):
        self.registered = set()

    def register(self, func, *, first_interval=0.1, persistent=False):
        """
        Register a timer and track it for later cleanup on addon unregister.

        func: the function to call.
        first_interval: how soon to first run (seconds).
        persistent: keep timer through file reloads.
        """
        bpy.app.timers.register(func, first_interval=first_interval, persistent=persistent)
        self.registered.add(func)
        return func

    def unregister_all(self):
        """
        Unregisters all tracked timers.
        """
        for func in list(self.registered):
            try:
                bpy.app.timers.unregister(func)
            except ValueError:
                # Already stopped or unregistered, ignore safely.
                pass
            self.registered.discard(func)

timers = Timers()
