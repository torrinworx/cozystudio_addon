import os
import time
import shutil
from pathlib import Path

import bpy


def parse_requirements(path: Path):
    if not path.exists():
        return []
    pkgs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            pkgs.append(line.split("==")[0].strip())
    return pkgs


def wait_for_git_instance(ui_mod, timeout=3.0):
    start = time.time()
    while time.time() - start < timeout:
        git_inst = getattr(ui_mod, "git_instance", None)
        if git_inst is not None:
            return git_inst
        bpy.app.timers.is_registered
        time.sleep(0.1)
    return None


def wait_for_install_finished(cozy_mod, timeout=120.0):
    start = time.time()
    while time.time() - start < timeout:
        thread = getattr(cozy_mod, "_install_thread", None)
        if thread is None:
            return True
        if not thread.is_alive():
            return True
        bpy.app.timers.is_registered
        time.sleep(0.2)
    return False


def enable_addon(addon_name: str):
    result = bpy.ops.preferences.addon_enable(module=addon_name)
    if "FINISHED" not in result and "CANCELLED" not in result:
        raise RuntimeError(f"addon_enable returned {result}")


def disable_addon(addon_name: str):
    if addon_name in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_disable(module=addon_name)


def install_addon_to_extensions(addon_src: Path, addon_name: str):
    ext_root = Path(bpy.utils.user_resource("EXTENSIONS"))
    user_repo = ext_root / "user_default"
    user_repo.mkdir(parents=True, exist_ok=True)

    addon_dest = user_repo / addon_src.name
    if addon_dest.exists():
        shutil.rmtree(addon_dest, ignore_errors=True)
    shutil.copytree(addon_src, addon_dest)

    return addon_dest


def ensure_install_operator(cozy_mod):
    if hasattr(bpy.ops.cozystudio, "install_deps"):
        return
    try:
        cozy_mod.register()
    except Exception:
        pass

    if hasattr(bpy.ops.cozystudio, "install_deps"):
        return

    try:
        bpy.utils.register_class(cozy_mod.COZYSTUDIO_OT_install_deps)
    except Exception:
        pass
    try:
        bpy.utils.register_class(cozy_mod.CozyStudioPreferences)
    except Exception:
        pass


def init_git_repo_for_test(ui_mod, timeout=5.0):
    git_inst = wait_for_git_instance(ui_mod, timeout=timeout)
    if git_inst is None:
        ui_mod.check_and_init_git()
        git_inst = wait_for_git_instance(ui_mod, timeout=timeout)

    if git_inst is None:
        raise RuntimeError("git_instance was never created")

    result = bpy.ops.cozystudio.init_repo()
    if "FINISHED" not in result and "CANCELLED" not in result:
        raise RuntimeError(f"init_repo returned {result}")

    time.sleep(0.5)
    if not getattr(git_inst, "initiated", False):
        raise RuntimeError("git_instance was not marked initiated")

    project_dir = Path(os.path.dirname(bpy.data.filepath))
    git_dir = project_dir / ".git"
    blocks_dir = project_dir / ".blocks"
    if not git_dir.exists() or not git_dir.is_dir():
        raise RuntimeError(f".git directory not found at {git_dir}")
    if not blocks_dir.exists() or not blocks_dir.is_dir():
        raise RuntimeError(f".blocks directory not found at {blocks_dir}")

    return git_inst
