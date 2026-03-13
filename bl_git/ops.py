from pathlib import Path
import traceback

from git import Repo

from ..utils.redraw import redraw
from ..utils.timers import timers
from ..utils.write import WriteDict
from .constants import (
    MANIFEST_BLOCKS_KEY,
    MANIFEST_BOOTSTRAP_KEY,
    MANIFEST_GROUP_KEY,
    MANIFEST_GROUPS_KEY,
    MANIFEST_VERSION,
    MANIFEST_VERSION_KEY,
)


class OpsMixin:
    def init(self):
        if not self.initiated:
            self.cozystudio_path.mkdir(exist_ok=True)
            self.blockspath.mkdir(exist_ok=True)
            bootstrap_name = self._bootstrap_name()
            self.manifest = WriteDict(
                self.manifestpath,
                data={
                    MANIFEST_VERSION_KEY: MANIFEST_VERSION,
                    MANIFEST_BLOCKS_KEY: {},
                    MANIFEST_GROUPS_KEY: {},
                    MANIFEST_BOOTSTRAP_KEY: bootstrap_name,
                },
            )
            if self.repo is None:
                self.repo = Repo.init(self.path)
            self.initiated = True
            timers.register(self._check)
            self._check()
            if self.manifest is not None:
                rebuilt_blocks = {}
                for uuid, entry in (self.state or {}).get("entries", {}).items():
                    rebuilt_blocks[uuid] = {
                        "type": entry.get("type"),
                        "deps": entry.get("deps", []),
                        "hash": entry.get("hash"),
                        MANIFEST_GROUP_KEY: entry.get(MANIFEST_GROUP_KEY),
                    }
                self.manifest[MANIFEST_BLOCKS_KEY] = rebuilt_blocks
                self.manifest[MANIFEST_GROUPS_KEY] = (self.state or {}).get("groups", {})
                self.manifest[MANIFEST_BOOTSTRAP_KEY] = self._bootstrap_name()
                self.manifest.write()

    def stage(self, changes: list[str]):
        changes = self._filter_changes(changes)
        if not changes:
            return

        self._ensure_state()

        for path in changes:
            file_path = Path(self.path, path)
            try:
                if file_path.exists():
                    self.repo.index.add([str(path)])
                else:
                    self.repo.index.remove([str(path)], working_tree=False)
            except Exception as e:
                print(f"[BpyGit] stage() error on {path}: {e}")

        self._manifest(changes)
        self._update_diffs()

    def unstage(self, changes: list[str]):
        changes = self._filter_changes(changes)
        if not changes:
            return

        self._ensure_state()

        try:
            if self.repo.head.is_valid():
                self.repo.git.restore("--staged", *changes)
            else:
                self.repo.index.remove(changes, working_tree=False, r=True)
        except Exception as e:
            print(f"[BpyGit] unstage() error: {e}")

        self._manifest(changes)
        self._update_diffs()

    def discard(self, changes=list[str]):
        changes = self._filter_changes(changes)

        self._ensure_state()

        self._manifest(changes)
        self._update_diffs()
        pass

    def commit(self, message="CozyStudio Commit"):
        if self.manifest is None or not self.repo:
            return False
        try:
            self._check(interactive=True)
            if self.last_capture_issues:
                print("[BpyGit] Commit blocked by capture issues:")
                for issue in self.last_capture_issues:
                    print(" -", issue.get("reason"))
                return False
            self._ensure_state()

            integrity = self.validate_manifest_integrity()
            self.last_integrity_report = integrity
            if not integrity.get("ok"):
                print("[BpyGit] Commit blocked by manifest integrity errors:")
                for err in integrity.get("errors", []):
                    print(" -", err)
                return False

            conflicts = self.manifest.get("conflicts") if isinstance(self.manifest, dict) else None
            if conflicts:
                print("[BpyGit] Commit blocked: unresolved conflicts present.")
                return False

            entries = (self.state or {}).get("entries", {})
            groups = (self.state or {}).get("groups", {})

            staged_paths = {
                path
                for (path, stage) in self.repo.index.entries.keys()
                if stage == 0
            }
            group_stage_paths = self._group_stage_paths(staged_paths, entries, groups)
            if group_stage_paths:
                self.stage(changes=group_stage_paths)

            if self.manifest is not None:
                rebuilt_blocks = {}
                for uuid, entry in (self.state or {}).get("entries", {}).items():
                    rebuilt_blocks[uuid] = {
                        "type": entry.get("type"),
                        "deps": entry.get("deps", []),
                        "hash": entry.get("hash"),
                        MANIFEST_GROUP_KEY: entry.get(MANIFEST_GROUP_KEY),
                    }
                self.manifest[MANIFEST_BLOCKS_KEY] = rebuilt_blocks
                self.manifest[MANIFEST_GROUPS_KEY] = (self.state or {}).get("groups", {})
                self.manifest[MANIFEST_BOOTSTRAP_KEY] = self._bootstrap_name()
                self.manifest.write()

            self._stage_manifest_file()
            self._update_diffs()
            self.repo.index.commit(message)
            self._update_diffs()
            redraw("COZYSTUDIO_PT_log")
            return True
        except Exception as e:
            print(f"[BpyGit] Commit failed: {e}")
            print(traceback.format_exc())
            return False
        finally:
            self._update_diffs()

    def _check(self, interactive=False):
        if self.suspend_checks:
            return self.check_interval
        prev_entries = self.state.get("entries") if self.state else None
        if prev_entries is None:
            prev_entries = {}

        entries, blocks, groups, issues = self._current_state(interactive=interactive)
        self.last_capture_issues = issues
        if not entries:
            return self.check_interval

        for uuid, entry in prev_entries.items():
            cur = entries.get(uuid)
            if cur is None:
                print(f"block deleted: {uuid}")
                self._delete_block_file(uuid)
            elif cur["hash"] != entry.get("hash"):
                print(f"block hash changed: {uuid}")
                self._write_block_file(uuid, blocks[uuid])

        for uuid in entries.keys():
            if uuid not in prev_entries:
                print(f"block added: {uuid}")
                self._write_block_file(uuid, blocks[uuid])

        self.state = {"entries": entries, "blocks": blocks, "groups": groups}
        self._update_diffs()
        return self.check_interval

    def refresh_all(self):
        if not self.initiated:
            return
        self._check(interactive=True)
        self._update_diffs()
        redraw("COZYSTUDIO_PT_panel")
        redraw("COZYSTUDIO_PT_log")

    @staticmethod
    def _group_stage_paths(staged_paths, entries, groups):
        staged_block_paths = {
            path
            for path in staged_paths
            if path.startswith(".cozystudio/blocks/") and path.endswith(".json")
        }
        staged_uuids = {Path(path).stem for path in staged_block_paths}
        staged_group_ids = set()
        for uuid in staged_uuids:
            entry = entries.get(uuid, {})
            group_id = entry.get(MANIFEST_GROUP_KEY) or uuid
            staged_group_ids.add(group_id)

        group_stage_paths = set()
        for group_id in staged_group_ids:
            group_meta = groups.get(group_id)
            members = (group_meta or {}).get("members", [])
            if not members:
                members = [group_id]
            for member_uuid in members:
                path = f".cozystudio/blocks/{member_uuid}.json"
                group_stage_paths.add(path)

        return sorted(group_stage_paths)
