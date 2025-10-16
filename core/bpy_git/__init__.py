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


def default_json_encoder(obj):
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode("ascii")
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def default_json_decoder(obj):
    """Recursively convert Base64-encoded strings back to bytes if possible."""
    if isinstance(obj, dict):
        return {k: default_json_decoder(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [default_json_decoder(x) for x in obj]
    elif isinstance(obj, str):
        # Try to detect Base64 strings that originated from bytes
        try:
            decoded = base64.b64decode(obj.encode("ascii"))
            # Optional heuristic: make sure we only replace if roundtrip encoding matches
            if base64.b64encode(decoded).decode("ascii") == obj:
                return decoded
        except Exception:
            pass  # Not a valid Base64 string, leave as-is
        return obj
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
        self.manifest_lock = False
        self.initiated = False
        self.diffs = None
        
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

        This function checks that __init___ hasn't already loaded
        a git repo.

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
    def _filter_changes(self, changes):
        """
        Simple re-useable filter to filer out .blend file and .blend1, and cozystudio.json from
        git changes. We handle these files manually elsewhere, the user should never see them in the ui.
        """
        IGNORE_PATTERNS = [
            "*.blend", "*.blend1",
            "cozystudio.json",
        ]

        if not changes:
            return []
        filtered = []
        for path in changes:
            if any(fnmatch(path, pattern) for pattern in IGNORE_PATTERNS):
                continue
            filtered.append(path)
        return filtered

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

        self._update_diffs()

    def discard(self, changes=list[str]):
        """
        Reverts all changes in a given file to the current head commit on the branch.
        
        similarly to checkout, we would have to experiement with loading data blocks into the scene,
        and then that brings dependency management complexity into this whole thing.
        
        Basically: `git restore <file>`
        """
        changes = self._filter_changes(changes)

        pass
    
    def commit(self, message="CozyStudio Commit"):
        """
        Commit staged changes, and only include updated manifest entries
        that correspond to staged .blocks files.
        """
        self.manifest_lock = True

        try:
            repo = self.repo
            manifest_path = self.manifestpath
            manifest_data = {}

            # Load current manifest or create fresh one if not exists
            if manifest_path.exists():
                try:
                    with open(manifest_path, "r") as f:
                        manifest_data = json.load(f)
                except json.JSONDecodeError:
                    manifest_data = {}
            else:
                manifest_data = {}

            # Identify staged .blocks files
            staged_blocks = [
                d for d in (self.diffs or [])
                if d["status"].startswith("staged") and d["path"].startswith(".blocks/")
            ]

            if not staged_blocks:
                print("[BpyGit] No staged .blocks files to commit.")
                return

            # Determine the UUID part from '.blocks/<uuid>.json'
            updated_manifest = dict(manifest_data)  # Start from current manifest

            for d in staged_blocks:
                rel_path = d["path"]
                uuid = Path(rel_path).stem
                block_file = self.blockspath / f"{uuid}.json"

                if d["status"].endswith("_deleted") or not block_file.exists():
                    # Handle deleted block
                    if uuid in updated_manifest:
                        del updated_manifest[uuid]
                        print(f"[BpyGit] Removed {uuid} from manifest (deleted).")
                else:
                    # Handle new or updated block
                    # We’ll read its definition from disk
                    with open(block_file, "r") as f:
                        # Find its deps, type, and hash we have from self._current_state
                        # but in this context we might already have it in self.manifest
                        block_entry = None
                        if self.manifest and uuid in self.manifest:
                            block_entry = self.manifest[uuid]
                        else:
                            # fallback: reconstruct from existing entries
                            entries, _ = self._current_state()
                            block_entry = entries.get(uuid)
                        if block_entry:
                            updated_manifest[uuid] = block_entry
                            print(f"[BpyGit] Updated {uuid} in manifest.")

            # Write updated manifest to disk
            with open(manifest_path, "w") as mf:
                json.dump(updated_manifest, mf, indent=2)

            # Stage changed files (manifest + all staged .blocks)
            files_to_add = [manifest_path] + [self.path / d["path"] for d in staged_blocks]
            repo.index.add([str(f.relative_to(self.path)) for f in files_to_add])

            # If HEAD doesn't exist (unborn repo), just commit directly
            if not repo.head.is_valid():
                repo.index.commit(message)
            else:
                # Regular commit
                repo.index.commit(message)

            print(f"[BpyGit] Committed {len(staged_blocks)} data blocks.")
            self._update_diffs()

        except Exception as e:
            print(f"[BpyGit] Commit failed: {e}")
            print(traceback.format_exc())

        finally:
            self.manifest_lock = False
            self._update_diffs()

    # --------

    def _check(self):
        """
        Checks every 0.5 seconds if the current data blocks are different than the ones on the disk,
        if a diff is detected, replace the data block.

        We should also somehow update the blender ui from here with git diff stuff so that the user can
        see what has chnaged.

        Unfortunately polling is the best way to get updates from a blender file about if a specific data
        block has any updates. blenders msgbus and despgraph_update_post methods are both inadequite for
        what we want to achieve here.
        
        This function is responsible for serializing the current state of blender data blocks, and writing
        them to the git repo. It does not handle commiting changes to the repo. This structure was chosen
        so we can display diffs in the blender ui similar to vscode git extension and stay close to the
        intended functionality of git.
        """
        if not self.manifestpath.exists(): return self.check_interval

        entries, blocks = self._current_state()
        if not entries: return self.check_interval

        for uuid, entry in self.manifest.items():
            cur = entries.get(uuid)
            if cur is None:
                # Delete .blocks/<uuid>.json file
                print(f"block deleted: {uuid}")
                self._delete_block_file(uuid)
            elif cur["hash"] != entry.get("hash"):
                # re-write .blocks/<uuid>.json file
                print(f"block hash changed: {uuid}")
                self._write_block_file(uuid, blocks[uuid])

        for uuid in entries.keys():
            if uuid not in self.manifest:
                # write .blocks/<uuid>.json file
                print(f"block added: {uuid}")
                self._write_block_file(uuid, blocks[uuid])

        # blanket update to manifest:
        entries, blocks = self._current_state()
        self.manifest.clear()
        self.manifest.update(entries)
        if not self.manifest_lock:
            self.manifest.write()

        self._update_diffs()

        return self.check_interval

    def _update_diffs(self):
        """
        Report unstaged (working tree) vs. index, plus staged (index) vs. HEAD.
        Also collects untracked files. Filters out .blend, .blend1, cozystudio.json.
        """
        repo = self.repo
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
                diffs_list.append({
                    "path": diff.b_path or diff.a_path,
                    "status": status,
                })

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
                diffs_list.append({
                    "path": diff.b_path or diff.a_path,
                    "status": "staged_added",   # hardcode as added
                })

        # Post-process: avoid double-listing files as both “unstaged” + “staged”
        # if they appear in both sets.  Also filter out .blend, cozystudio.json, etc.
        staged_paths = {d["path"] for d in diffs_list if d["status"].startswith("staged")}
        unique_diffs = []
        for d in diffs_list:
            # If a file is listed as staged_{added|modified|deleted},
            # we skip the “unstaged” A/M/D version so we only show it once.
            if d["path"] in staged_paths and d["status"] in ("added", "modified", "deleted"):
                continue
            unique_diffs.append(d)

        # Filter out *.blend, *.blend1, cozystudio.json, etc.
        filtered_paths = set(self._filter_changes(d["path"] for d in unique_diffs))
        final_diffs = [d for d in unique_diffs if d["path"] in filtered_paths]

        # Update self.diffs only if changed
        if self.diffs != final_diffs:
            self.diffs = final_diffs
            print(self.diffs)
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
       
    def _write_block_file(self, cozystudio_uuid, data):
        """
        Writes a given data block to the .blocks directory. Assumes data is already
        serialized and 64 bit encoded where needed.
        """
        block_path = os.path.join(self.blockspath, f"{cozystudio_uuid}.json")
        try:
            with open(block_path,"w") as f:
                # NOTE: Does not use default encoder. assumes data has already gone through self._serialize().
                json.dump(data, f, indent=2)
        except Exception as e:
            print(traceback.format_exc())
            print(data)

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
                    "hash": hash[target]
                }
                blocks[cozystudio_uuid] = target

        return entries, blocks


























    # Experimental functions, only the above is solidified.

    def checkout(self, commit):
        """
        checks out a given commit in the git repo and reconstructs the blender file data blocks using the
        manifest at that commit.
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
            if self.needs_update(
                datablock, data
            ):  # TODO: build a custom differ for data block quick comparison.
                impl.load(data, datablock)
            # No update necessary for datablock

        else:
            # Build fresh
            datablock = impl.construct(data)
            impl.load(data, datablock)

    def _read(self, cozystudio_uuid):
        """
        Reads and returns the data of a serialized data block given a blocks cozystudio_uuid.

        NOTES:

        IMPORTANT: Read assumes that the data block no longer exists in the .blend file
        it doesn't try to resolve to an existing data block, it constructs a new one and
        it's dependencies from scratch.

        block_entry looks like this:
        {
            "type": "scenes",
            "name": "Scene",
            "name_full": "Scene",
            "cozystudio_uuid": "bc6b3df8-0e87-40fd-be4a-040c9927a299",
            "deps": [
                "b264c244-6853-4017-aac0-a86981fac218",
                "189b95bf-f14e-40ca-b344-64c5a2a6cd8c"
            ]
        },

        need to make sure that a datablock is constructed only after all the blocks it references (“dependencies”) exist in Blender
        """
        block_path = self.blockspath / f"{cozystudio_uuid}.json"

        if not block_path.exists():
            raise FileNotFoundError(f"Data file not found: {block_path}")

        with open(block_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            data = default_json_decoder(data)

        return data

    def topological_sort(manifest):
        """
        Sketch: Code for sorting manifest entries to build a dependency based order to load
        data blocks of a given manifest.
        """
        deps = {e["cozystudio_uuid"]: set(e.get("deps", [])) for e in manifest}
        reverse = defaultdict(set)
        for k, vs in deps.items():
            for v in vs:
                reverse[v].add(k)

        # Find roots (no dependencies)
        roots = deque([k for k, ds in deps.items() if not ds])
        order = []
        while roots:
            n = roots.popleft()
            order.append(n)
            for m in list(reverse[n]):
                deps[m].remove(n)
                if not deps[m]:
                    roots.append(m)
        if any(deps[k] for k in deps):
            raise ValueError("Cycle detected in dependency graph")
        return order
