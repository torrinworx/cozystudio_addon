"""
Script to initialize test environment.

We want to run the addon within blender and test the operators used in the ui as if the user was clicking on buttons.

We also want to test every aspect of the addon, from dependency installation to commits and merges. So sanatization is needed.

Example command:

First install pytest in blenders pip:
/home/torrin/blender-4.5.3-linux-x64/4.5/python/bin/python3.11 -m pip install pytest

Then run headless test:
/home/torrin/blender-4.5.3-linux-x64/blender --background --python ./tests/runner.py -- /home/torrin/Data/Repos/Personal/Cone/
"""

import sys
import shutil
import subprocess
from pathlib import Path

import bpy
import pytest


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


def disable_addon(addon_name: str):
    """Disable the addon if it's enabled."""
    if addon_name in bpy.context.preferences.addons:
        print(f"[cleanup] Disabling enabled addon: {addon_name}")
        try:
            bpy.ops.preferences.addon_disable(module=addon_name)
        except Exception as e:
            print(f"[cleanup] Failed to disable {addon_name}: {e}")
    else:
        print(f"[cleanup] Addon {addon_name} not enabled, nothing to disable.")


def remove_existing_addons(addon_name: str):
    """
    Remove all existing installations of the addon from every known extension folder.
    """
    ext_root = Path(bpy.utils.user_resource("EXTENSIONS")).parent
    print(f"[cleanup] Checking extensions under {ext_root}")

    for repo_dir in ext_root.iterdir():
        if not repo_dir.is_dir():
            continue
        addon_dir = repo_dir / addon_name
        if addon_dir.exists():
            print(f"[cleanup] Found previous version at {addon_dir}, removing…")
            try:
                if addon_dir.is_symlink() or addon_dir.is_file():
                    addon_dir.unlink()
                else:
                    shutil.rmtree(addon_dir)
            except Exception as e:
                print(f"[cleanup] Failed to remove {addon_dir}: {e}")


def sanitize_target_directory(target_path: Path):
    """Wipe any existing files and folders inside the target path."""
    if target_path.exists():
        print(f"[cleanup] Sanitizing existing target directory: {target_path}")
        for item in target_path.iterdir():
            try:
                if item.is_file() or item.is_symlink():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            except Exception as e:
                print(f"[cleanup] Failed to remove {item}: {e}")
    else:
        target_path.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    target_path = Path(argv[0]).absolute() if argv else Path.cwd()

    # Ensure target directory exists
    target_path.mkdir(parents=True, exist_ok=True)
    sanitize_target_directory(target_path)

    # Create clean blend file
    blend_path = target_path / "test.blend"
    bpy.ops.wm.read_factory_settings(use_empty=False)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    print(f"[setup] Saved new default cube file: {blend_path}")
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))

    # Addon setup
    addon_name = "cozystudio_addon"
    addon_src = Path(__file__).parent.parent.absolute()

    # Uninstall pip dependencies used by addon
    req_path = addon_src / "requirements.txt"
    uninstall_requirements(req_path)

    # Ensure addon is disabled and previous copies removed
    disable_addon(addon_name)
    remove_existing_addons(addon_name)

    # Copy new addon into user_default
    user_repo = Path(bpy.utils.user_resource("EXTENSIONS")) / "user_default"
    user_repo.mkdir(parents=True, exist_ok=True)

    addon_dest = user_repo / addon_src.name

    print(f"[install] Installing addon from {addon_src} → {addon_dest}")
    if addon_dest.exists():
        print(f"[install] Removing previous addon at {addon_dest}")
        if addon_dest.is_symlink() or addon_dest.is_file():
            addon_dest.unlink()
        else:
            shutil.rmtree(addon_dest)

    try:
        shutil.copytree(addon_src, addon_dest)
        print(f"[install] Copied addon to: {addon_dest}")
    except Exception as e:
        print(f"[install] Failed to copy addon: {e}")

    # Run pytest on all files in the same directory (tests/)
    tests_dir = Path(__file__).parent
    print(f"[tests] Starting pytest in {tests_dir}")
    result = pytest.main([str(tests_dir), "-vv", "--maxfail=1", "--disable-warnings"])

    # Optional: control Blender exit code
    sys.exit(result)
