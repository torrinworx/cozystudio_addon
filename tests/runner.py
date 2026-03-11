"""
Create a clean test environment and run pytest inside Blender.

Usage (from cozystudio_addon/):

  python test.py
"""

import sys
import shutil
import subprocess
from pathlib import Path

import bpy
import pytest


# Helpers
def ensure_pytest_installed():
    try:
        import pytest  # noqa: F401
        import pytest_order  # noqa: F401
        return
    except Exception:
        pass

    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip",
            "pytest",
            "pytest-order",
        ]
    )


def parse_requirements(path: Path):
    if not path.exists():
        return []
    pkgs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            pkgs.append(line.split("==")[0].strip())
    return pkgs


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

    ensure_pytest_installed()

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
    try:
        reqs = parse_requirements(addon_src / "requirements.txt")
        if reqs:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "uninstall", "--yes", *reqs],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass
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
    install_code = pytest.main(
        [
            str(tests_dir),
            "-vv",
            "-q",
            "--color=yes",
            "--maxfail=1",
            "--disable-warnings",
            "-m",
            "install",
            "--ignore=tests/unit",
        ]
    )
    if install_code != 0:
        sys.exit(install_code)

    exit_code = pytest.main(
        [
            str(tests_dir),
            "-vv",
            "-q",
            "--color=yes",
            "--maxfail=1",
            "--disable-warnings",
            "-m",
            "not install",
        ]
    )

    sys.exit(exit_code)
