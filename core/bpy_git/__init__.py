"""
Git system for blender files based on blender's internal data blocks.
"""

import os
import bpy
import json
import base64
import traceback
from pathlib import Path
from fnmatch import fnmatch
from deepdiff import DeepHash
from collections import defaultdict, deque
from git import Repo, InvalidGitRepositoryError, NoSuchPathError
from ... import bl_types
from .tracking import Track
from ...utils.timers import timers
from ...utils.write import WriteDict
from ...utils.redraw import redraw

import base64


def default_json_encoder(obj):
    if isinstance(obj, (bytes, bytearray)):
        # Tag so we can unambiguously reverse it later
        return {"__bytes__": True, "data": base64.b64encode(obj).decode("ascii")}
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def default_json_decoder(obj):
    # Only decode if it was tagged during encoding
    if isinstance(obj, dict):
        if obj.get("__bytes__") is True and "data" in obj:
            return base64.b64decode(obj["data"])
        # Recurse
        return {k: default_json_decoder(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [default_json_decoder(x) for x in obj]
    else:
        return obj


class BpyGit:
    def __init__(self, check_interval=5):
        """
        Checks the current path, tries to load an exisitng bpy_git repo.

        This doesn't try to rectify or start a bpy_git repo as this code
        is loaded on blender startup. This only attempts to load a
        bpy_git repo if one can be found. The user must manually initate
        one with BpyGit.init(). That handles file creation and folder
        creation and git initialization.
        """
        self.bpy_protocol = bl_types.get_data_translation_protocol()
        Track(self.bpy_protocol).start()

        self.path = Path(bpy.path.abspath("//")).resolve()
        self.blockspath = Path(os.path.join(self.path, ".blocks"))
        self.manifestpath = Path(os.path.join(self.path, "cozystudio.json"))

        self.repo = None
        self.manifest = None
        self.initiated = False
        self.diffs = None
        self.state = None  # unified current state, entries and blocks.

        self.check_interval = check_interval

        if str(self.path) == "" or not self.path.exists():
            # Blender file is not saved yet. Save before using Git features. - TODO Add warning in blender
            return

        try:
            self.repo = Repo(self.path)
            if self.repo.bare:
                self.repo = None  # No repo found at current blender file
            else:
                self.initiated = True  # Repo found at current blender file
        except (InvalidGitRepositoryError, NoSuchPathError):
            # TODO: Warning in blender: No valid Git repository detected in {self.path}
            self.repo = None
            self.initiated = False
            return
        except Exception as e:
            print(f"[BpyGit] Unexpected error while initializing git: {e}")
            print(traceback.format_exc())
            self.repo = None
            self.initiated = False
            return

        try:
            if self.manifestpath.exists():
                # Load existing manifest
                self.manifest = WriteDict(self.manifestpath)
                timers.register(self._check)
                # only loading an existing one here, initiating one is handled in self.init()
        except Exception as e:
            print(f"[BpyGit] Error loading manifest: {e}")
            print(traceback.format_exc())
            self.manifest = None

    def init(self):
        """
        Initiates a bpy_git repo in the current blender file path.

        TODO: trigger modal popup: "Create blender git in /path/to/files/folder? This folder will become your
        project folder, all changes in this folder will be tracked."
        """

        if not self.initiated:
            os.mkdir(self.blockspath)
            self.manifest = WriteDict(self.manifestpath)
            self.repo = Repo.init(self.path)
            self.initiated = True
            timers.register(self._check)

    # ---- Staged changes ----

    def stage(self, changes: list[str]):
        """
        Stage one or more files in the git repo.
        """
        changes = self._filter_changes(changes)
        if not changes:
            return

        for path in changes:
            file_path = Path(self.path, path)
            try:
                if file_path.exists():
                    # normal file, add it
                    self.repo.index.add([str(path)])
                else:
                    # file deleted on disk, so remove it from index
                    self.repo.index.remove([str(path)], working_tree=False)
            except Exception as e:
                print(f"[BpyGit] stage() error on {path}: {e}")

        self._manifest(changes)
        self._update_diffs()

    def unstage(self, changes: list[str]):
        """
        Removes changes from the staging area.
        """
        changes = self._filter_changes(changes)
        if not changes:
            return

        try:
            if self.repo.head.is_valid():
                # Equivalent to: git restore --staged <files>
                self.repo.git.restore("--staged", *changes)
            else:
                # no commits yet -> just remove directly from index
                self.repo.index.remove(changes, working_tree=False, r=True)
        except Exception as e:
            print(f"[BpyGit] unstage() error: {e}")

        self._manifest(changes)
        self._update_diffs()

    def discard(self, changes=list[str]):
        """
        Reverts all changes in a given file to the current head commit on the branch.
        similarly to checkout, we would have to experiement with loading data blocks into the scene,
        and then that brings dependency management complexity into this whole thing.
        Basically: `git restore <file>`
        """
        changes = self._filter_changes(changes)

        # ...

        self._manifest(changes)
        self._update_diffs()
        pass

    def commit(self, message="CozyStudio Commit"):
        """
        Commit staged changes, and only include updated manifest entries
        that correspond to staged .blocks files.
        """
        try:
            self._update_diffs()
            self.repo.index.commit(message)
            self._update_diffs()
        except Exception as e:
            print(f"[BpyGit] Commit failed: {e}")
            print(traceback.format_exc())
        finally:
            self._update_diffs()

    def _filter_changes(self, changes):
        """
        Simple re-useable filter to filer out .blend file and .blend1, and cozystudio.json from
        git changes. We handle these files manually elsewhere, the user should never see them in the ui.
        """
        IGNORE_PATTERNS = ["*.blend", "*.blend1", "cozystudio.json"]

        if not changes:
            return []

        filtered = []
        for path in changes:
            if any(fnmatch(path, pattern) for pattern in IGNORE_PATTERNS):
                continue
            filtered.append(path)
        return filtered

    def _manifest(self, changes: list[str]):
        """
        Update cozystudio.json to reflect the .blocks/*.json changes being staged,
        unstaged, or discarded.

        Rules:
        - If a .blocks/<uuid>.json file was added or modified: update its manifest entry
            using current data from `self.state['entries']`.
        - If a .blocks/<uuid>.json file was deleted: remove that block UUID from manifest.
        - Then write cozystudio.json, and stage it in the repo for commit.
        """

        # Filter out non-block changes
        changes = [c for c in self._filter_changes(changes) if c.startswith(".blocks/")]
        if not changes:
            return

        entries = self.state.get("entries", {})
        manifest = self.manifest

        try:
            for rel_path in changes:
                block_path = Path(self.path, rel_path)
                block_uuid = block_path.stem

                # Deleted or missing .blocks file → remove from manifest
                if not block_path.exists():
                    if block_uuid in manifest:
                        del manifest[block_uuid]
                        print(
                            f"[BpyGit] Removed manifest entry for deleted block {block_uuid}"
                        )
                    continue

                # If present in current state → update manifest entry
                current_entry = entries.get(block_uuid)
                if current_entry:
                    manifest[block_uuid] = {
                        "type": current_entry["type"],
                        "deps": current_entry.get("deps", []),
                        "hash": current_entry["hash"],
                    }
                    print(f"[BpyGit] Updated manifest entry: {block_uuid}")
                else:
                    # File exists but not found in current state
                    # (shouldn't happen normally; keep manifest as-is)
                    print(f"[BpyGit] Warning: {block_uuid} not in current state")

            # Write manifest to disk
            manifest.write()

            # Stage manifest in Git
            try:
                manifest_rel = os.path.relpath(self.manifestpath, self.path)
                self.repo.index.add([manifest_rel])
            except Exception as e:
                print(f"[BpyGit] Error staging updated manifest: {e}")

        except Exception:
            print("[BpyGit] Error updating manifest:")
            print(traceback.format_exc())

    # --------
    def _check(self):
        """
        Checks every 0.5 seconds if the current data blocks are different than the ones on the disk,
        if a diff is detected, replace the data block.
        Unfortunately polling is the best way to get updates from a blender file about if a specific data
        block has any updates. blenders msgbus and despgraph_update_post methods are both inadequite for
        what we want to achieve here.
        This function is responsible for serializing the current state of blender data blocks, and writing
        them to the git repo. It does not handle commiting changes to the repo. This structure was chosen
        so we can display diffs in the blender ui similar to vscode git extension and stay close to the
        intended functionality of git.
        """
        prev_entries = self.state.get("entries") if self.state else None
        if prev_entries is None:
            prev_entries = {}

        entries, blocks = self._current_state()
        if not entries:
            return self.check_interval

        # resolve deleted or modified entry in prev_entries
        for uuid, entry in prev_entries.items():
            cur = entries.get(uuid)
            if cur is None:
                # Delete .blocks/<uuid>.json file
                print(f"block deleted: {uuid}")
                self._delete_block_file(uuid)
            elif cur["hash"] != entry.get("hash"):
                # re-write .blocks/<uuid>.json file
                print(f"block hash changed: {uuid}")
                self._write_block_file(uuid, blocks[uuid])

        # resolve added entry in prev_entries
        for uuid in entries.keys():
            if uuid not in prev_entries:
                # write .blocks/<uuid>.json file
                print(f"block added: {uuid}")
                self._write_block_file(uuid, blocks[uuid])

        self.state = {"entries": entries, "blocks": blocks}
        self._update_diffs()
        return self.check_interval

    def _update_diffs(self):
        """
        Build list of git differences and triggers panel redraw so ui can display
        diffs. This function is only meant for converting git stuff into displayable
        ui.
        """
        repo = self.repo
        if not repo:
            return

        diffs_list = []
        empty_tree_sha = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        change_type_map = {
            "A": "added",
            "M": "modified",
            "D": "deleted",
            "R": "renamed",
            "C": "copied",
            "T": "typechange",
        }

        def append_diffs(git_diff, prefix=""):
            """
            Helper to parse a set of GitPython diffs.
            Each diff.change_type is one of {A,M,D,R,C,T}, which we map to a readable status.
            We optionally prefix the status for “staged_” vs. “unstaged.”
            """
            for diff in git_diff:
                change = diff.change_type
                status = change_type_map.get(change, "modified")
                if prefix:
                    status = f"{prefix}_{status}"
                diffs_list.append(
                    {
                        "path": diff.b_path or diff.a_path,
                        "status": status,
                    }
                )

        # "Unstaged" changes = what differs between index and working tree
        # i.e. what you would see if you did "git diff" (no arguments).
        working_diffs = repo.index.diff(None)  # index vs. working tree
        append_diffs(working_diffs)

        # Untracked files
        for path in repo.untracked_files:
            diffs_list.append({"path": path, "status": "untracked"})

        # "Staged" changes = what's in the index vs. HEAD. If HEAD is invalid,
        # compare index to the empty-tree SHA to produce "added" entries.
        if repo.head.is_valid():
            staged_diffs = repo.index.diff(repo.head.commit)
            append_diffs(staged_diffs, prefix="staged")
        else:
            # --- unborn HEAD (first commit) ---
            # Compare index with empty tree, but force anything we find to be "added"
            staged_diffs = repo.index.diff(empty_tree_sha)
            for diff in staged_diffs:
                diffs_list.append(
                    {
                        "path": diff.b_path or diff.a_path,
                        "status": "staged_added",  # hardcode as added
                    }
                )

        # Post-process: avoid double-listing files as both “unstaged” + “staged”
        # if they appear in both sets.  Also filter out .blend, cozystudio.json, etc.
        staged_paths = {
            d["path"] for d in diffs_list if d["status"].startswith("staged")
        }
        unique_diffs = []
        for d in diffs_list:
            # If a file is listed as staged_{added|modified|deleted},
            # we skip the “unstaged” A/M/D version so we only show it once.
            if d["path"] in staged_paths and d["status"] in (
                "added",
                "modified",
                "deleted",
            ):
                continue
            unique_diffs.append(d)

        # Filter out _.blend,_ .blend1, cozystudio.json, etc.
        filtered_paths = set(self._filter_changes(d["path"] for d in unique_diffs))
        final_diffs = [d for d in unique_diffs if d["path"] in filtered_paths]

        # Update self.diffs only if changed
        if self.diffs != final_diffs:
            self.diffs = final_diffs
            redraw("COZYSTUDIO_PT_panel")

    def _delete_block_file(self, cozystudio_uuid):
        """
        Delete a given block written to the .blocks directory.
        """
        try:
            block_file = self.blockspath / f"{cozystudio_uuid}.json"
            if not block_file.exists():
                print(f"[BpyGit] Block file not found: {block_file}")
                return False
            block_file.unlink()
            print(f"[BpyGit] Deleted block file: {block_file}")
            return True
        except Exception as e:
            print(f"[BpyGit] Error deleting block file '{cozystudio_uuid}': {e}")
            print(traceback.format_exc())
            return False

    def _write_block_file(self, cozystudio_uuid, block_str):
        """
        Writes a given data block to the .blocks directory. Assumes data is already
        serialized and 64 bit encoded where needed.
        """
        block_path = os.path.join(self.blockspath, f"{cozystudio_uuid}.json")
        try:
            with open(block_path, "w") as f:
                # NOTE: Does not use default encoder. assumes data has already gone through self._serialize().
                f.write(block_str)
        except Exception as e:
            print(traceback.format_exc())
            print(block_str)

    def _serialize(self, block) -> str:
        """
        Returns the serialized dictionary of a single data block.
        input: data block class
        returns: json string representing the data block
        Also calls default_json_encoder for handling raw 64 bit data used in some data blocks.
        """
        data = self.bpy_protocol.dump(block)
        return json.dumps(data, indent=2, default=default_json_encoder)

    def _current_state(self):
        """
        Gets the current state of tracked data blocks in the blender file.
        Return two items:
        entries: a dictionary where keys are cozystudio_uuids of blocks and
            values contain block type, dependencies, and hash information.
            Intended to be stored in the manifest
        blocks: a dictionary of the serialized data blocks in the current scene.
            keys are cozystudio_uuids, and values are the serialized data blocks.
        """
        entries = {}
        blocks = {}

        for type_name, impl_class in self.bpy_protocol.implementations.items():
            if not hasattr(bpy.data, impl_class.bl_id):
                continue
            data_collection = getattr(bpy.data, impl_class.bl_id)
            if not isinstance(data_collection, bpy.types.bpy_prop_collection):
                continue

            for db in data_collection:
                if hasattr(db, "users") and db.users == 0:
                    continue
                cozystudio_uuid = getattr(db, "cozystudio_uuid", None)
                deps = [d.cozystudio_uuid for d in self.bpy_protocol.resolve_deps(db)]
                target = self._serialize(db)
                hash = DeepHash(target)
                entries[cozystudio_uuid] = {
                    "type": impl_class.bl_id,
                    "deps": deps,
                    "hash": hash[target],
                }
                blocks[cozystudio_uuid] = target

        return entries, blocks

    def checkout(self, commit):
        """
        checks out a given commit in the git repo and reconstructs the blender file data blocks using the
        manifest at that commit.

        1. Switch Git to that commit state (files, manifest, etc.).
        → e.g. do self.repo.git.checkout(commit_hash).

        2. Load the manifest (cozystudio.json) from that commit.
        → This gives you the authoritative list of all datablocks and their dependency graph at that point in time.

        3. Determine load order using topological_sort().
            Even though you said each commit includes all blocks, you still need deterministic order to ensure that blocks with dependencies are created after their dependencies exist in Blender.

        4. For each block in sorted order:
            Read .blocks/<uuid>.json file via _read().
            Deserialize it into a Python dict (already handled by _read() + default_json_decoder()).
            Pass it to deserialize() to either:
                Find an existing Blender datablock and update it via impl.load().
                Or create a new one via impl.construct() and then load data.

        5. Clean up extra data blocks that exist in bpy.data but are not in that manifest (optional, but usually necessary to “revert” deletions).

        6. Refresh UI and state tracking so that your Git panel updates (_update_diffs(), etc.).
        """
        self.repo.git.checkout(
            commit
        )  # restore cozystudio.json + .blocks/ to that commit

        self.manifest = WriteDict(
            self.manifestpath
        )  # re-read manifest from current commit

        # Get topological dependency load order for blocks:
        load_order = self._topological_sort(self.manifest)

        # Load blocks into scene:
        for uuid in load_order:
            data = self._read(uuid)
            try:
                self.deserialize(data)
            except Exception as e:
                print(f"[BpyGit] Failed to restore block {uuid}: {e}")

        # Cleanup orphaned data blocks that don't have references in the current commits manifest.
        all_valid = set(self.manifest.keys())
        for type_name, impl_class in self.bpy_protocol.implementations.items():
            data_collection = getattr(bpy.data, impl_class.bl_id, None)
            if not data_collection:
                continue
            for block in list(data_collection):
                pass
                # uuid = getattr(block, "cozystudio_uuid", None)
                # if uuid and uuid not in all_valid:
                #     bpy.data.remove(block)

        # Update state
        self._check()

        # Update diffs
        self._update_diffs()

        # Redraw panel
        redraw("COZYSTUDIO_PT_panel")

    def _read(self, cozystudio_uuid):
        """
        Reads and returns the data of a serialized data block given a blocks cozystudio_uuid.
        """
        block_path = self.blockspath / f"{cozystudio_uuid}.json"
        if not block_path.exists():
            raise FileNotFoundError(f"Data file not found: {block_path}")

        with open(block_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            data = default_json_decoder(data)
        return data

    def deserialize(self, data: dict):
        print("DATA: ", data)

        # Defensive: normalize type_id if corrupted
        type_id = data.get("type_id")
        if isinstance(type_id, (bytes, bytearray)):
            data["type_id"] = type_id.decode("utf-8", errors="ignore")

        restored_data = self.bpy_protocol.construct(data)
        self.bpy_protocol.load(data, restored_data)

        # Optional: link orphan Objects into the active scene as a fallback
        if isinstance(restored_data, bpy.types.Object) and restored_data.users == 0:
            try:
                bpy.context.scene.collection.objects.link(restored_data)
            except RuntimeError:
                pass

        print(f"[BpyGit] Deserialized created: {restored_data}")

    def _topological_sort(self, manifest):
        """
        Return list of UUIDs sorted so that all dependencies appear before their dependents.

        Works with either:
        - dict form: {uuid: {"deps": [...]}, ...}
        - list form: [{"cozystudio_uuid": ..., "deps": [...]}, ...]
        """
        # Normalize into a {uuid: set(deps)} mapping
        if isinstance(manifest, dict):
            deps = {uuid: set(v.get("deps", [])) for uuid, v in manifest.items()}
        else:
            deps = {e["cozystudio_uuid"]: set(e.get("deps", [])) for e in manifest}

        # Build reverse lookup: dep -> dependents
        dependents = defaultdict(set)
        for uuid, ds in deps.items():
            for dep in ds:
                dependents[dep].add(uuid)

        # Nodes with no incoming edges (roots)
        queue = deque([u for u, ds in deps.items() if not ds])
        order = []

        # Standard Kahn's algorithm
        while queue:
            u = queue.popleft()
            order.append(u)
            for v in list(dependents[u]):
                deps[v].discard(u)
                if not deps[v]:
                    queue.append(v)

        # Detect remaining edges (cycles)
        cycles = [k for k, ds in deps.items() if ds]
        if cycles:
            raise ValueError(f"Dependency cycle detected: {cycles}")

        return order

    # Experimental functions, only the above is solidified.
    """
    def deserialize(self, data):
        """ """
        type_id = data.get("type_id")
        if not type_id:
            raise ValueError("Invalid datablock: missing 'type_id' field")
        impl = self.bpy_protocol.get_implementation(type_id)
        # Try to resolve existing datablock
        datablock = impl.resolve(data)
        if datablock:
            # Compare current vs stored version
            if self.needs_update(datablock, data):
                # TODO: build a custom differ for data block quick comparison.
                impl.load(data, datablock)
            # No update necessary for datablock
        else:
            # Build fresh
            datablock = impl.construct(data)
            impl.load(data, datablock)
    """
