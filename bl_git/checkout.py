from collections import defaultdict, deque

import bpy

from ..utils.redraw import redraw
from ..utils.write import WriteDict
from .constants import MANIFEST_BLOCKS_KEY


class CheckoutMixin:
    def checkout(self, commit):
        self.restore_ref(commit, detach=True, operation="checkout_commit")

    def switch_branch(self, branch_name):
        self.restore_ref(branch_name, operation="checkout_branch")

    def create_branch(self, branch_name, ref=None):
        if not self.repo or not self.initiated:
            raise RuntimeError("Repository not initialized.")
        target_ref = ref or "HEAD"
        parked = self._park_cozy_changes("create_branch", target_ref)
        if not parked.get("ok"):
            raise RuntimeError(parked["error"])

        self.suspend_checks = True
        try:
            if ref:
                self.repo.git.checkout("-b", branch_name, ref)
            else:
                self.repo.git.checkout("-b", branch_name)

            self._load_working_manifest()
            self._restore_from_manifest()

            integrity = self.validate_manifest_integrity()
            self.last_integrity_report = integrity
            if not integrity.get("ok"):
                print("[BpyGit] Manifest integrity issues after branch creation:")
                for err in integrity.get("errors", []):
                    print(" -", err)

            self._update_diffs()

            redraw("COZYSTUDIO_PT_changes")
            redraw("COZYSTUDIO_PT_history")
        finally:
            self.suspend_checks = False

        if parked and parked.get("stashed"):
            self.reapply_parked_changes()

    def _current_ref_label(self):
        if not self.repo:
            return None
        try:
            if not self.repo.head.is_detached:
                return self.repo.active_branch.name
        except Exception:
            pass
        try:
            return self.repo.head.commit.hexsha[:8]
        except Exception:
            return None

    def _managed_carryover_entries(self):
        if not self.repo:
            return []
        try:
            lines = self.repo.git.stash("list").splitlines()
        except Exception:
            return []

        entries = []
        prefix = f"{self.carryover_message_prefix}|"
        for line in lines:
            if prefix not in line:
                continue
            stash_ref, _, remainder = line.partition(":")
            payload = remainder[remainder.index(prefix) :].strip()
            entry = {"stash_ref": stash_ref.strip(), "message": payload}
            for chunk in payload.split("|"):
                if "=" not in chunk:
                    continue
                key, value = chunk.split("=", 1)
                entry[key] = value
            entries.append(entry)
        return entries

    def _managed_carryover(self):
        entries = self._managed_carryover_entries()
        if not entries:
            return None
        return entries[0]

    def _park_cozy_changes(self, operation, target_ref):
        if not self.repo or not self.initiated:
            return {"ok": True, "stashed": False}

        parked = self._managed_carryover()
        if parked:
            return {
                "ok": False,
                "error": "Parked Cozy changes already exist. Restore them before continuing.",
            }

        dirty_paths = self._dirty_paths()
        blocking_paths = self._blocking_dirty_paths(dirty_paths)
        if blocking_paths:
            return {
                "ok": False,
                "error": "Working tree has non-Cozy changes. Commit or stash them first.",
            }

        cozy_paths = self._cozy_dirty_paths(dirty_paths)
        if not cozy_paths:
            return {"ok": True, "stashed": False}

        source_ref = self._current_ref_label() or "unknown"
        message = (
            f"{self.carryover_message_prefix}|operation={operation}|"
            f"source={source_ref}|target={target_ref or 'HEAD'}"
        )
        self.last_carryover_error = None
        before_refs = [entry["stash_ref"] for entry in self._managed_carryover_entries()]
        self.repo.git.stash(
            "push",
            "--include-untracked",
            "-m",
            message,
            "--",
            ".cozystudio/manifest.json",
            ".cozystudio/blocks",
        )
        after_entries = self._managed_carryover_entries()
        for entry in after_entries:
            if entry["stash_ref"] not in before_refs:
                self._update_diffs()
                self.refresh_ui_state()
                return {"ok": True, "stashed": True, "entry": entry}
        return {"ok": True, "stashed": False}

    def reapply_parked_changes(self):
        parked = self._managed_carryover()
        if not parked:
            return {"ok": False, "error": "No parked Cozy changes were found."}
        if self._blocking_dirty_paths(self._dirty_paths()):
            return {
                "ok": False,
                "error": "Working tree has non-Cozy changes. Commit or stash them first.",
            }
        if isinstance(self.manifest, dict) and self.manifest.get("conflicts"):
            return {
                "ok": False,
                "error": "Resolve conflicts before restoring parked Cozy changes.",
            }

        try:
            self.repo.git.stash("apply", "--index", parked["stash_ref"])
            self.repo.git.stash("drop", parked["stash_ref"])
            self.last_carryover_error = None
            self.restore_ref()
            return {"ok": True, "restored": True}
        except Exception as e:
            self.last_carryover_error = str(e)
            try:
                self.repo.git.restore(
                    "--source=HEAD",
                    "--staged",
                    "--worktree",
                    "--",
                    ".cozystudio/manifest.json",
                    ".cozystudio/blocks",
                )
            except Exception:
                pass
            self.restore_ref()
            return {
                "ok": False,
                "error": f"Parked Cozy changes are still safe in {parked['stash_ref']}: {e}",
            }

    def restore_ref(self, ref=None, detach=False, operation=None, park_changes=True):
        parked = None
        if ref and park_changes:
            parked = self._park_cozy_changes(
                operation or ("checkout_commit" if detach else "checkout_branch"),
                ref,
            )
            if not parked.get("ok"):
                raise RuntimeError(parked["error"])

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

            redraw("COZYSTUDIO_PT_changes")
            redraw("COZYSTUDIO_PT_history")
        finally:
            self.suspend_checks = False

        if parked and parked.get("stashed"):
            self.reapply_parked_changes()

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
