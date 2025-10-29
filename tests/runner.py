import os
import sys
import shutil
from pathlib import Path

import bpy

if __name__ == "__main__":
    help('modules')
    
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    target_path = Path(argv[0]).absolute()  # directory to init git repo and create blender file.

    if not target_path.exists():
        os.makedirs(target_path)
    else:
        # If path exists, wipe it for sanatization.
        pass

    blend_path = os.path.join(target_path, "test.blend")

    bpy.ops.wm.read_factory_settings(use_empty=False)
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print(f"Saved new default cube file: {blend_path}")
    bpy.ops.wm.open_mainfile(filepath=blend_path)

    # manually install addon, move cozystudio_addon into the blender addon directory

    user_repo = Path(bpy.utils.user_resource("EXTENSIONS")) / "user_default"
    user_repo.mkdir(parents=True, exist_ok=True)

    addon_src = Path(__file__).parent.absolute() / "cozystudio_addon"
    addon_dest = user_repo / addon_src.name

    print(f"Installing addon from {addon_src} → {addon_dest}")

    if addon_dest.exists():
        print(f"Removing previous addon from {addon_dest}")
        if addon_dest.is_symlink() or addon_dest.is_file():
            addon_dest.unlink()
        else:
            shutil.rmtree(addon_dest)

    # Copy entire addon directory tree
    shutil.copytree(addon_src, addon_dest)
    print(f"Copied addon to: {addon_dest}")

    # TODO: Check if vscode version of cozystudio_addon is enabled, if it is, disable it.
    # TODO: Sanatize python environment to fresh blender python modules. Revert any python modules that might have been installed by an addon.