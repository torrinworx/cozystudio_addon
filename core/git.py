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
import base64
import hashlib
import traceback

from ..core.track import Track
from .. import bl_types


def default_json_encoder(obj):
    if isinstance(obj, bytes):
        # Base64 encode bytes → safe text representation
        return base64.b64encode(obj).decode("ascii")
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class Git:
    def __init__(self):
        track = Track()
        track.start()

        self.filepath = bpy.data.filepath
        self.path = bpy.path.abspath("//")
        self.blockspath = os.path.join(self.path, ".blocks")

        self.bpy_protocol = bl_types.get_data_translation_protocol()
        print("THIS IS THING:", self.bpy_protocol)

        for type_name, impl_class in self.bpy_protocol.implementations.items():
            print(type_name, "→", impl_class)

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

    def write(self, block):
        """
        Writes a data-block to a .blend file, using it's uuid as it's name.
        """

        collection = getattr(bpy.data, block["type"], None)
        if not collection:
            print(f"No data collection {block['type']}")
            return

        target = next(
            (
                db
                for db in collection
                if getattr(db, "cozystudio_uuid", None) == block["cozystudio_uuid"]
            ),
            None,
        )
        data = self.bpy_protocol.dump(target)
        try:
            with open(
                os.path.join(self.blockspath, f"{block['cozystudio_uuid']}.json"), "w"
            ) as f:
                json.dump(data, f, indent=2, default=default_json_encoder)
        except Exception as e:
            print(traceback.format_exc())
            print(data)

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
        """
        Return list of trackable datablock summaries for the current blend.

        Uses a simple hashing to detect later on in the pipe if blocks have changed.
        """
        blocks = []

        for type_name, impl_class in self.bpy_protocol.implementations.items():
            if not hasattr(bpy.data, impl_class.bl_id):
                continue

            data_collection = getattr(bpy.data, impl_class.bl_id)
            if not isinstance(data_collection, bpy.types.bpy_prop_collection):
                continue

            for db in data_collection:
                if hasattr(db, "users") and db.users == 0:
                    continue

                # serilalize to json, hash, don't store json (maybe in the future cache somewhere so we are not duplicating this step)
                #
                data = self.bpy_protocol.dump(db)
                json_string = json.dumps(data, default=default_json_encoder)
                encoded_string = json_string.encode("utf-8")
                hash_object = hashlib.sha256(encoded_string)
                hex_digest = hash_object.hexdigest()

                blocks.append(
                    {
                        "type": impl_class.bl_id,
                        "name": getattr(db, "name", None),
                        "name_full": getattr(db, "name_full", None),
                        # ^ for debugging, probably want to remove once implementation is finished.
                        "cozystudio_uuid": getattr(
                            db, "cozystudio_uuid", None
                        ),  # uuid for tracking in blender file block with lfs blocks
                        "hash": hex_digest,
                    }
                )

        return blocks
