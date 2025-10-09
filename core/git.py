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








"""

import bpy
import hashlib

TRACKABLE_TYPES = {  # just some basic examples.
    "objects": ["location", "rotation_euler", "scale", "data", "material_slots"],
    "meshes": ["vertices", "edges", "polygons"],
    "materials": ["diffuse_color", "use_nodes", "node_tree"],
    "lights": ["color", "energy", "type"],
    "cameras": ["lens", "sensor_width", "sensor_height"],
    "collections": ["hide_render", "hide_select", "hide_viewport"],
    "scenes": ["frame_start", "frame_end", "render"],
}


class Git:
    def __init__(self):
        self.previous_state = self.current()
        self.current_state = []
        self.filepath = bpy.data.filepath

    @staticmethod
    def db_hash(db, tracked_props=None):
        """Return a hash over an explicit or generic set of properties."""
        h = hashlib.sha1()
        if tracked_props:
            for pname in tracked_props:
                if not hasattr(db, pname):
                    continue
                try:
                    value = getattr(db, pname)
                    if isinstance(value, bpy.types.bpy_struct):
                        h.update(f"{value.__class__.__name__}:{value.name}".encode())
                    elif hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
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
        for data_type, props in TRACKABLE_TYPES.items():
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
                        "hash": self.db_hash(db, props),
                        "values": {p: getattr(db, p) for p in props if hasattr(db, p)}
                    }
                )

        return blocks

    def compare(self):
        """Compare with the previous snapshot, then update baseline."""
        self.current_state = self.current()

        prev = {(b["type"], b["name"]): b for b in self.previous_state}
        cur = {(b["type"], b["name"]): b for b in self.current_state}

        added = set(cur) - set(prev)
        removed = set(prev) - set(cur)
        changed = [k for k in set(cur) & set(prev) if cur[k]["hash"] != prev[k]["hash"]]

        print("==== DIFF RESULT ====")
        if added:
            print("Added:")
            [print(f"  + {t}:{n}") for t, n in added]
        if removed:
            print("Removed:")
            [print(f"  - {t}:{n}") for t, n in removed]
        if changed:
            print("Modified:")
            [print(f"  * {t}:{n}") for t, n in changed]
        if not (added or removed or changed):
            print("No differences.")

        self.previous_state = self.current_state.copy()
        return {"added": added, "removed": removed, "changed": changed}
