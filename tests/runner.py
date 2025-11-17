import os
import sys
import shutil
import subprocess
from pathlib import Path

import bpy

'''
Example command:
/home/torrin/blender-4.5.3-linux-x64/blender --background --python ./tests/runner.py -- /home/torrin/Data/Repos/Personal/Cone/
'''


def parse_requirements(filepath: Path):
    """Read package names (ignoring versions and comments) from requirements.txt."""
    if not filepath.exists():
        print(f"[cleanup] No requirements.txt found at {filepath}")
        return []
    pkgs = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                # Strip versions (pkg==1.2.3 → pkg)
                pkgs.append(line.split("==")[0].strip())
    return pkgs


def uninstall_requirements(req_path: Path):
    pkgs = parse_requirements(req_path)
    if not pkgs:
        print("[cleanup] Nothing to uninstall.")
        return
    print(f"[cleanup] Uninstalling: {', '.join(pkgs)}")
    pybin = sys.executable
    try:
        # use --yes to auto-confirm removal
        subprocess.check_call([pybin, "-m", "pip", "uninstall", "--yes", *pkgs])
    except Exception as e:
        print(f"[cleanup] Error uninstalling packages: {e}")


if __name__ == "__main__":
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    target_path = Path(
        argv[0]
    ).absolute()  # directory to init git repo and create blender file.

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

    addon_src = Path(__file__).parent.parent.absolute()

    # removing previous addon_requirenments
    req_path = addon_src / "requirements.txt"
    uninstall_requirements(req_path)
    # TODO: Check if vscode version of cozystudio_addon is enabled, if it is, disable it.

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
