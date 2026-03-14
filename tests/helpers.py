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

    result = bpy.ops.cozystudio.setup_project()
    if "FINISHED" not in result and "CANCELLED" not in result:
        raise RuntimeError(f"setup_project returned {result}")

    time.sleep(0.5)
    if not getattr(git_inst, "initiated", False):
        raise RuntimeError("git_instance was not marked initiated")

    project_dir = Path(os.path.dirname(bpy.data.filepath))
    git_dir = project_dir / ".git"
    blocks_dir = project_dir / ".cozystudio" / "blocks"
    if not git_dir.exists() or not git_dir.is_dir():
        raise RuntimeError(f".git directory not found at {git_dir}")
    if not blocks_dir.exists() or not blocks_dir.is_dir():
        raise RuntimeError(f".cozystudio/blocks directory not found at {blocks_dir}")

    try:
        if git_inst.repo is not None and git_inst.repo.head.is_detached:
            branch_name = get_repo_branch_name(git_inst.repo)
            if branch_name:
                git_inst.repo.git.checkout(branch_name)
                git_inst.restore_ref(branch_name, park_changes=False)
        if getattr(git_inst, "repo", None) is not None:
            parked = git_inst._managed_carryover_entries()
            if parked:
                git_inst.reapply_parked_changes()
                parked = git_inst._managed_carryover_entries()
                for entry in parked:
                    git_inst.repo.git.stash("drop", entry["stash_ref"])
    except Exception as exc:
        raise RuntimeError(f"Failed to normalize test repo state: {exc}") from exc

    return git_inst


def create_test_object(name="CozyTestObject"):
    mesh = bpy.data.meshes.new(name + "Mesh")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def ensure_tracking_assignments(git_inst):
    from cozystudio_addon.bl_git.tracking import Track

    Track(git_inst.bpy_protocol)._run_assign_loop()


def wait_for_uuid(obj, timeout=3.0):
    start = time.time()
    while time.time() - start < timeout:
        uuid = getattr(obj, "cozystudio_uuid", None)
        if uuid:
            return uuid
        bpy.app.timers.is_registered
        time.sleep(0.1)
    return None


def wait_for_block_file(git_inst, uuid, timeout=3.0):
    start = time.time()
    while time.time() - start < timeout:
        block_path = git_inst.blockspath / f"{uuid}.json"
        if block_path.exists():
            return block_path
        time.sleep(0.1)
    return None


def wait_for_object_prefix(prefix, timeout=3.0):
    start = time.time()
    while time.time() - start < timeout:
        if bpy.context.view_layer:
            bpy.context.view_layer.update()
        matches = [obj for obj in bpy.data.objects if obj.name.startswith(prefix)]
        if not matches and bpy.context.scene:
            matches = [
                obj
                for obj in bpy.context.scene.objects
                if obj.name.startswith(prefix)
            ]
        if matches:
            return matches
        time.sleep(0.1)
    return []


def get_repo_branch_name(repo):
    if repo is None:
        return None
    try:
        if not repo.head.is_detached:
            return repo.active_branch.name
    except Exception:
        pass

    if "main" in repo.heads:
        return "main"
    if "master" in repo.heads:
        return "master"
    if repo.heads:
        return repo.heads[0].name
    return None


def clear_manifest_conflicts(git_inst):
    manifest = getattr(git_inst, "manifest", None)
    if not manifest or not isinstance(manifest, dict):
        return
    if "conflicts" not in manifest:
        return
    del manifest["conflicts"]
    manifest.write()
