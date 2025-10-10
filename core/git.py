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


"""
import os
import bpy
import json
import hashlib

from ..core.track import Track
# from ..core.bl_types import bl_types
# from ..multi_user.bl_types import bl_types
from .. import bl_types
from ._bl_types import _bl_types

# import importlib
# bl_types = importlib.import_module(".multi_user.bl_types")


class Git:
    def __init__(self):
        track = Track()
        track.start()

        self.filepath = bpy.data.filepath
        self.path = bpy.path.abspath("//")
        self.blockspath = os.path.join(self.path, ".blocks")
        
        self.bpy_protocol = bl_types.get_data_translation_protocol()
        print("THIS IS THING:", self.bpy_protocol)

    def init(self):
        """
        TODO: trigger modal popup: "Create blender git in /path/to/files/folder? This folder will become your
        project folder, all changes in this folder will be tracked."
        """
        # Maybe only do this step on commit:

        # Create .blend data blocks folder:
        if not os.path.isdir(self.blockspath):
            os.mkdir(self.blockspath)

    def commit(self):
        """Commit current state and run a quick serialization test."""
        current_state = self.current()

        manifest_path = os.path.join(self.path, "cozystudio.json")
        with open(manifest_path, "w") as json_file:
            json.dump(current_state, json_file, indent=4)

        # Write out .blend blobs as before
        for block in current_state:
            self.write(block)

        # --- Simple test of bpy_protocol serialization ---------------------
        if bpy.data.cameras:
            camera = bpy.data.cameras[0]
            print(f"[CozyStudio] Testing serialization of camera: {camera.name}")

            try:
                # Serialize this datablock using the Multi‑User protocol
                camera_dict = self.bpy_protocol.dump(camera)

                # For demonstration, print a small portion and optionally write to disk
                print(json.dumps(camera_dict, indent=2)[:500], "...")  # truncated for readability

                # Optionally, save full JSON as proof‑of‑concept
                test_path = os.path.join(self.path, f"{camera.name}_dump.json")
                with open(test_path, "w") as f:
                    json.dump(camera_dict, f, indent=2)
                print(f"[CozyStudio] Serialized camera data written to {test_path}")

                # --- Deserialization test ----------------------------------------
                print(f"[CozyStudio] Testing deserialization of camera from {test_path}")

                with open(test_path, "r") as f:
                    camera_data = json.load(f)

                # Use bpy_protocol to deserialize it back into Blender
                restored_camera = self.bpy_protocol.construct(camera_data)
                self.bpy_protocol.load(camera_data, restored_camera)

                print(f"[CozyStudio] Deserialized camera created: {restored_camera}")
                if hasattr(restored_camera, "name"):
                    print(f"[CozyStudio] Restored camera name: {restored_camera.name}")

            except Exception as ex:
                print(f"[CozyStudio] Error during camera (de)serialization test: {ex}")

        else:
            print("[CozyStudio] No cameras available for serialization test.")

    def write(self, block):
        """
        Writes a data-block to a .blend file, using it's uuid as it's name.
        
        TODO: Long term future: some kind of data-block serialization that converts data blocks to json and back to data-block types.
        
        
        """
        blend_path = os.path.join(self.blockspath, f"{block['cozystudio_uuid']}.blend")
        os.makedirs(self.blockspath, exist_ok=True)

        collection = getattr(bpy.data, block["type"], None)
        if not collection:
            print(f"No data collection {block['type']}")
            return

        target = next((db for db in collection if getattr(db, "cozystudio_uuid", None) == block["cozystudio_uuid"]), None)
        if target:
            bpy.data.libraries.write(blend_path, {target})
        else:
            print(f"Datablock with uuid {block['cozystudio_uuid']} not found.")

    def load(self):
        """
        Loads a data-block from a .blend file into the current blend file.

        TODO:
        with bpy.data.libraries.load("my_mesh.blend") as (data_from, data_to):
            data_to.meshes = data_from.meshes
        """

    @staticmethod
    def db_hash(db, tracked_props=None):
        """
        Return a hash over an explicit or generic set of properties for a data block.

        Used as a lightweight way to track if changes were made to data blocks.
        """
        h = hashlib.sha1()
        if tracked_props:
            for pname in tracked_props:
                if not hasattr(db, pname):
                    continue
                try:
                    value = getattr(db, pname)
                    if isinstance(value, bpy.types.bpy_struct):
                        h.update(f"{value.__class__.__name__}:{value.name}".encode())
                    elif hasattr(value, "__iter__") and not isinstance(
                        value, (str, bytes)
                    ):
                        joined = ",".join(
                            str(v.name if hasattr(v, "name") else v) for v in value
                        )
                        h.update(joined.encode())
                    else:
                        h.update(str(value).encode())
                except Exception:
                    continue
        else:
            for prop in db.bl_rna.properties:
                if prop.identifier in {"rna_type", "name", "users"}:
                    continue
                try:
                    value = getattr(db, prop.identifier)
                    if isinstance(
                        value, (bpy.types.bpy_struct, bpy.types.bpy_prop_collection)
                    ):
                        continue
                    h.update(str(value).encode("utf8"))
                except Exception:
                    continue
        return h.hexdigest()

    def current(self):
        """Return list of trackable datablock summaries for the current blend."""
        blocks = []

        for entry in _bl_types:
            data_type = entry["name"]
            props = entry.get("properties", [])

            if not hasattr(bpy.data, data_type):
                continue

            data_collection = getattr(bpy.data, data_type)
            if not isinstance(data_collection, bpy.types.bpy_prop_collection):
                continue

            for db in data_collection:
                if hasattr(db, "users") and db.users == 0:
                    continue

                blocks.append(
                    {
                        "type": data_type,
                        "name": db.name,
                        "name_full": getattr(db, "name_full", db.name),
                        "cozystudio_uuid": getattr(
                            db, "cozystudio_uuid", None
                        ),  # uuid for tracking in blender file block with lfs blocks
                        "hash": self.db_hash(
                            db, props
                        ),  # hash for checking if it's changed
                    }
                )

        return blocks
