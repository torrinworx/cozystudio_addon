# Blender add-on for Cozy Studio

The codebase (to be open sourced) for the python blender addon for Cozy Studio.

The goal with creating this plugin is to allow users to use Blender on their own hardware, while being able to use all Cozy Studio features within their Blender ui. That means they can commit changes, pull files, live collaborate, and use gpu services all within their local version of Blender through a websocket connection to the main js server.

The plugin has the following features:
- startup checks - check if the current version of the plugin is the latest available production build on Github, if not, force download the newest version. Check server connectivity with Cozy Studio home server. Show connectivity error.
- Still able to use local blender git features if connection down.
- Don't hard lock if version is out of date. But restrict and refuse online requests due to compatibility concerns. (Should be handled server side and client side)
- Modular design, code should be loaded in modules, buttons are routed to module calls via a module router of some kind.
- Blender ui and core functionality should be handled in completely separate files.
- Desireable to build everything with as minimal dependencies as possible, preferable to build everything ourselves due to Blenders limited Python dependencies. Possibly solvable with a custom build script that compiles all deps into a single python file? Not sure.
-
