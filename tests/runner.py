"""
Create a clean test environment and run pytest inside Blender.

Usage:

  1.  Install pytest and pytest-order into Blender's bundled Python:
      /home/torrin/blender-4.5.3-linux-x64/4.5/python/bin/python3.11 -m pip install pytest pytest-order

  2.  Run headless tests:
      /home/torrin/blender-4.5.3-linux-x64/blender \
          --background --python ./tests/runner.py -- /home/torrin/Data/Repos/Personal/Cone/
"""

import sys
import shutil
import subprocess
from pathlib import Path

import bpy
import pytest


# Helpers
def parse_requirements(path: Path):
    """Return package names from a requirements.txt (ignore versions/comments)."""
    if not path.exists():
        return []
    pkgs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            pkgs.append(line.split("==")[0].strip())
    return pkgs


def uninstall_requirements(req_path: Path):
    pkgs = parse_requirements(req_path)
    if not pkgs:
        return
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "uninstall", "--yes", *pkgs],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass  # keep quiet; pytest will show failures if this matters


def disable_addon(name: str):
    if name in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_disable(module=name)


def remove_existing_addons(name: str):
    ext_root = Path(bpy.utils.user_resource("EXTENSIONS")).parent
    for repo in ext_root.iterdir():
        addon_dir = repo / name
        if addon_dir.exists():
            if addon_dir.is_symlink() or addon_dir.is_file():
                addon_dir.unlink(missing_ok=True)
            else:
                shutil.rmtree(addon_dir, ignore_errors=True)


def sanitize_target_directory(target: Path):
    """Delete contents of target folder but keep the folder itself."""
    if not target.exists():
        target.mkdir(parents=True, exist_ok=True)
        return
    for item in target.iterdir():
        if item.is_file() or item.is_symlink():
            item.unlink(missing_ok=True)
        else:
            shutil.rmtree(item, ignore_errors=True)


if __name__ == "__main__":
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    target_path = Path(argv[0]).absolute() if argv else Path.cwd()

    # Silence Blender's banner in pytest output
    print("\n\033[36m[ runner ] Preparing clean Blender test environment\033[0m")

    sanitize_target_directory(target_path)

    blend_path = target_path / "test.blend"
    bpy.ops.wm.read_factory_settings(use_empty=False)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))

    addon_name = "cozystudio_addon"
    addon_src = Path(__file__).parent.parent.resolve()

    # reset environment for the addon
    uninstall_requirements(addon_src / "requirements.txt")
    disable_addon(addon_name)
    remove_existing_addons(addon_name)

    user_repo = Path(bpy.utils.user_resource("EXTENSIONS")) / "user_default"
    user_repo.mkdir(parents=True, exist_ok=True)

    addon_dest = user_repo / addon_src.name
    if addon_dest.exists():
        shutil.rmtree(addon_dest, ignore_errors=True)
    shutil.copytree(addon_src, addon_dest)

    # Run pytest with its own coloured output
    tests_dir = Path(__file__).parent
    print(f"\033[36m[ runner ] Launching pytest in {tests_dir}\033[0m\n")

    #  -q  : quiet start banner
    #  -rA : show test summary
    #  --color=yes : force colours when under Blender
    exit_code = pytest.main(
        [
            str(tests_dir),
            "-vv",
            "-q",
            "--color=yes",
            "--maxfail=1",
            "--disable-warnings",
        ]
    )

    sys.exit(exit_code)
