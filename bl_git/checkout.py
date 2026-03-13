from collections import defaultdict, deque

import bpy

from ..utils.redraw import redraw
from ..utils.write import WriteDict
from .constants import MANIFEST_BLOCKS_KEY


class CheckoutMixin:
    def checkout(self, commit):
        self.restore_ref(commit, detach=True)

    def switch_branch(self, branch_name):
        self.restore_ref(branch_name)

    def restore_ref(self, ref=None, detach=False):
        self.suspend_checks = True
        try:
            if ref:
                if detach:
                    try:
                        if not self.repo.head.is_detached:
                            try:
                                self.last_branch = self.repo.active_branch.name
                            except Exception:
                                self.last_branch = None
                        self.repo.git.checkout("--detach", ref)
                    except Exception:
                        self.repo.git.checkout(ref)
                else:
                    self.repo.git.checkout(ref)

            self._load_working_manifest()
            self._restore_from_manifest()

            integrity = self.validate_manifest_integrity()
            self.last_integrity_report = integrity
            if not integrity.get("ok"):
                print("[BpyGit] Manifest integrity issues after checkout:")
                for err in integrity.get("errors", []):
                    print(" -", err)

            self._update_diffs()

            redraw("COZYSTUDIO_PT_panel")
            redraw("COZYSTUDIO_PT_log")
        finally:
            self.suspend_checks = False

    def _load_working_manifest(self):
        if not self.manifestpath.exists():
            self.manifest = None
            return
        self.manifest = WriteDict(self.manifestpath)
        self._ensure_manifest_schema()

    def _restore_from_manifest(self):
        if self.manifest is None or not isinstance(self.manifest, dict):
            return

        manifest_blocks = self.manifest.get(MANIFEST_BLOCKS_KEY, {})

        valid_manifest_blocks = {}
        for uuid, entry in manifest_blocks.items():
            block_path = self.blockspath / f"{uuid}.json"
            if block_path.exists():
                valid_manifest_blocks[uuid] = entry
            else:
                print(f"[BpyGit] Missing block file for {uuid}: {block_path}")

        load_order = self._topological_sort({MANIFEST_BLOCKS_KEY: valid_manifest_blocks})

        for uuid in load_order:
            data = self._read(uuid)
            if data.get("uuid") is None:
                data["uuid"] = uuid
            try:
                self.deserialize(data)
            except Exception as e:
                print(f"[BpyGit] Failed to restore block {uuid}: {e}")

        self._cleanup_orphans(valid=set(valid_manifest_blocks.keys()))

        entries, blocks, groups, issues = self._current_state(interactive=False)
        self.state = {
            "entries": entries or {},
            "blocks": blocks or {},
            "groups": groups or {},
        }
        self.last_capture_issues = issues

    def deserialize(self, data: dict):
        print("DATA: ", data)

        type_id = data.get("type_id")
        if isinstance(type_id, (bytes, bytearray)):
            data["type_id"] = type_id.decode("utf-8", errors="ignore")

        restored_data = self.bpy_protocol.resolve(data)
        if restored_data is None:
            restored_data = self.bpy_protocol.construct(data)
        self.bpy_protocol.apply(data, restored_data, interactive=True)

        restored_uuid = data.get("uuid")
        if restored_uuid:
            if getattr(restored_data, "cozystudio_uuid", None) != restored_uuid:
                restored_data.cozystudio_uuid = restored_uuid
            if getattr(restored_data, "uuid", None) != restored_uuid:
                restored_data.uuid = restored_uuid

        if isinstance(restored_data, bpy.types.Object):
            for scene in bpy.data.scenes:
                if restored_data.name not in scene.objects:
                    try:
                        scene.collection.objects.link(restored_data)
                    except RuntimeError:
                        pass

        print(f"[BpyGit] Deserialized created: {restored_data}")

    def _topological_sort(self, manifest):
        if isinstance(manifest, dict):
            manifest = manifest.get(MANIFEST_BLOCKS_KEY, {})
            deps = {
                uuid: set(self._extract_dep_uuids(v.get("deps", [])))
                for uuid, v in manifest.items()
            }
        else:
            deps = {}

        for uuid, ds in deps.items():
            if uuid in ds:
                ds.discard(uuid)
            deps[uuid] = {dep for dep in ds if dep in deps}

        dependents = defaultdict(set)
        for uuid, ds in deps.items():
            for dep in ds:
                dependents[dep].add(uuid)

        queue = deque([u for u, ds in deps.items() if not ds])
        order = []

        while queue:
            u = queue.popleft()
            order.append(u)
            for v in list(dependents[u]):
                deps[v].discard(u)
                if not deps[v]:
                    queue.append(v)

        cycles = [k for k, ds in deps.items() if ds]
        if cycles:
            raise ValueError(f"Dependency cycle detected: {cycles}")

        return order
