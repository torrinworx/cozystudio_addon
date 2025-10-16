# provides a class that simplifies git interaction between blender and git

"""
1. Somehow: init blender project? => inits git in the folder of the project
2. see current blender changes in list of changes "What changes are we tracking to display and counting as commits?"
3. Need function, "diff" that get's the current state of the blender file, what new data blocks blender considers "savable" in the current
    pool of stored data. Then the differ checks with the previous commit, and shows the updates blocks.

Note: shouldn't rely on if blender has saved them to count them as new commit, need to track commits ourselves because user might save blender
file outside of commits. Blender save != commit

What this system handles:
- Writing serialized blender file changes, data blocks, to a manifest.json file of some kind.
- Updating lfs data-blocks if changes are made in the blender file and linking them to the correct entries in the manifest
- Constructing the blender file out of the manifest.json file from any commit, via git lfs data block raw storage by looking up data block ids in the manifest at that commit.

What we are offloading to git:
- diffing manifest.json to find what was updated/removed/added
- git lfs will store the raw data-blocks, linked to data blocks in the manifest.json file.


I'm still debating if we should allow traditional merge requests or rebases? Like I can't comprehend how that would work with
data blocks. What is the industry standard for a version control system? Is it overwrite or nothing? how should we handle that?

For storing data blocks in git lfs, look into blender data writing, storing data blocks directly to a .blend file, keeping track of which
blend file is the current version of the data blocks listed in manifest, then pull from that blend file to build the blender file at a
given git commit hash for the manifest.

We hook into git, we update .blend file blobs of data blocks in git lfs with new commits from blender.

When the user clicks the commit button, we take the new data blocks, save them to .blend files, and commit it to the git repo/lfs for storage while also recording the new data block associations in the cozystudio.json manifest file.

This way we use git for version control and .blend file commit tracking so we dont have to do that manually. The only thing the cozy studio addon has to do is pipe blender data blocks to new .blend files, record them in the manifest,
and when we change to a previous commit, rebuild the .blend file using the data blocks of the manifest in that commit hash.


To test:
1. Create a git repo, with a blend file. We init it with the cozystudio.json manifest
2. Add and comit everything to the repo, cube example file.
3. remove/change the cube out for a cone. Commit "Adding Cone" commit".
4. change the current checkedout branch in git to the initial commit. CozyStudio automatically swaps out the data blocks to replicate the ones we stored in the initial commit within the current blender file.


Obviously we would have to replicate some kind of stashing feature, similar to what git has, but I'm assuming it would just use the
functionality we would build out in the above anyway. Just with some wiring to hook up.



Future:
Need still: Some lightweight diffing system, looks at tracked blender type properties to simply tell the user "Object was moved from xyz to xyz"



Notes:
.blocks/uuids.json files store the raw data blocks in individualized json files. not sure how we resolve these
data blocks to their dependents or their dependencies yet, need to research how multi-user does it.

cozystudio.json file, this is simply used to detect diffs between currently commited data blocks in the local repo,
with the current state of data blocks in blender.

I'm unsure if using the cozystudio.json file to diff is a good idea, or how we should run the diffing so that
new changes appear in the ui or how often, should we watch depsgraph for updates and run it then? how should
we handle this?


Need to create a system so that the user can add assets to git lfs in adition to the .blocks folder.

Also how do we handle .blend files? How do we store or build them? Should we commit a light weight empty .blend
file? so on a fresh clone  you pull a blank .blend file stored in lfs, that way we aren't multiplying .blend files
that one stays the same, then the current data blocks in .blocks are loaded to recreate the file? something like that?

flow:
init repo, git, lfs, then commit current data blocks and blank .blend file to git lfs, while committing cozystudio.json
manifest of current data blocks being stored,

We never use WriteDict helper on data blocks themselves, just on the manifest. If we did it for each data block, we would
use too much memory, blender already uses alot of memory so we don't want to duplicate this.

WriteDict shouldn't be used for live updating data-blocks since that will be handled by a dedicated commit() function,
we should only periodically be diffing the data blocks and the stored json committed data blocks occasionally.

Design note: Maybe for simplicity sake we should bound togther data blocks and their dependencies? that might simplify some
things? Idk what the trade offs are though.


TASKS:
- checkout function, reconstruct a given manifest file in the current blender file.
- build and test topological dependency loading
- import git python and use git functionality, hookup git init, commit, checkout features.
- using git python, re-build and simplify __init__ function to check if the current directory has already been initialized.
    ensure that the initialized repo also automatically loads the manifest WriteDict if it's there.



periodically, or when things in the blender file change, we need to "write" data blocks to the
files. This is separate from committing them to the repo, or even git adding them. By writing
them, we can then just use git to show the difference between their current state freshly
written from the blend file data blocks and the state already committed in the git repo.


committing and adding to staging special cases we need to handle manually:
- hide cozystudio.json from appearing in changes, this should always be committed when any staged changes are committed.
    Caveat: non staged changes will still appear in this manifest, so we need to not commit the changed data block entries
    in the manifest that havent been staged
- Handle .blend and .blend1 files. We don't want to directly commit these, so my theory: we handle this manually, hide changes
    to the .blend file in git from the user. Never commit them. on init we commit a blank shell .blend file that on launch with
    our addon auto mounts the currently checked out commit in blender. Auto loading the datat blocks in .blocks at that commit.
    So we never actually commit the .blend1 file, and never commit any new changes to the .blend file.

"""

import os
import bpy
import json
import base64
import traceback
from pathlib import Path
from deepdiff import DeepHash
from collections import defaultdict, deque
from git import Repo, InvalidGitRepositoryError, NoSuchPathError

from ... import bl_types
from .tracking import Track
from ...utils.timers import timers
from ...utils.write_dict import WriteDict
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
    """
    These three need some kind of a middleware that removes .blend, .blend1, and cozystudio.json from what is sent
    to the user, and removes them from commits so that we aren't committing .blend files on each commit, only the
    .blocks in lfs.
    
    We also need to define a startup protocall on repo init that commits a blank blender file that we can use to
    construct the scene from, I'm curious if we could cache the build somewhere so we don't have to build the file
    from the data blocks on blender file open every time as that will introduce overhead. Let's first worry about
    reconsturcting a blender file from committed serialized data blocks in the .blocks folder before we get to that.
    
    As for handling cozystudio.json manifest, we need to manually commit the individual inline updates to the
    individual data blocks that the user has added to the staged commit via self.stage(). so in the ui, the ui is
    given a list of changes from the .blocks folder, but also other stuff in the whole repo, because in the future
    we want to support asset folders with images/asset models, etc. But with these "Staged changes" functions we 
    need to handle: Everytime a data block json is added to staged, we need to also update cozystudio.json with that
    data block (I think this is already automatically handled, but because _check() runs on a timer we should do this
    check for consistancy), then add that line to the staged version of cozystudio.json file. The user is never supposed
    to handle commits or staging the cozystudio.json file, it's done behind the scenes completely. When the user commits
    data block changes, we also commit the cozystudio.json file that is updated, only with the data block entries that 
    are currently staged.
    
    TODO: Filter files we never want to stage or change like *.blend files and custom handle cozystudio.json.
    """

    def stage(self, changes=list[str]):
        """
        Stage one or more files in the git repo.
        """
        self.repo.index.add(changes)
        self._update_diffs()


    def unstage(self, changes: list[str]):
        """
        Removes changes from the staging area. Uses restore if possible,
        handles unborn HEAD (no commits yet) gracefully.
        """

        # HEAD exists, unstage like `git restore --staged <file>`
        if self.repo.head.is_valid():
            self.repo.git.restore('--staged', *changes)
        # No commits yet (unborn HEAD), remove directly from index
        else:
            self.repo.index.remove(changes, working_tree=False)

    def discard(self, changes=list[str]):
        """
        Reverts all changes in a given file to the current head commit on the branch.
        
        Basically: `git restore <file>`
        """
        pass
    
    def commit(self):
        """
        Commits the currently staged changes to the current branch.
        """
        pass
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

        self._update_diffs()

        return self.check_interval

    def _update_diffs(self):
        repo = self.repo
        diffs_list = []
        empty_tree_sha = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        empty_tree = repo.tree(empty_tree_sha)

        # Base mapping for change types
        change_type_map = {
            "A": "added",
            "M": "modified",
            "D": "deleted",
            "R": "renamed",
            "C": "copied",
            "T": "typechange",
        }

        def append_diffs(diffs, prefix=""):
            """Helper to normalize and add diff entries to diffs_list"""
            for diff in diffs:
                change = diff.change_type
                status = change_type_map.get(change, "modified")
                if prefix:
                    status = f"{prefix}_{status}"
                diffs_list.append({
                    "path": diff.b_path or diff.a_path,
                    "status": status,
                })

        # Unstaged (working tree vs index or HEAD)
        if repo.head.is_valid():
            working_diffs = repo.head.commit.diff(None)
        else:
            working_diffs = repo.index.diff(empty_tree)
        append_diffs(working_diffs)

        # Untracked
        for path in repo.untracked_files:
            diffs_list.append({"path": path, "status": "untracked"})

        # Staged (index vs HEAD or empty tree)
        if repo.head.is_valid():
            staged_diffs = repo.index.diff(repo.head.commit)
        else:
            staged_diffs = repo.index.diff(empty_tree)
        append_diffs(staged_diffs, prefix="staged")

        staged_paths = {d["path"] for d in diffs_list if d["status"].startswith("staged")}
        unique_diffs = []
        for d in diffs_list:
            if not (d["status"] in ("deleted", "modified", "added") and d["path"] in staged_paths):
                unique_diffs.append(d)

        # Update only if changed
        if self.diffs != unique_diffs:
            self.diffs = unique_diffs
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
