from pathlib import Path

import bpy


def _status_abbrev(status: str) -> str:
    base = status.removeprefix("staged_")
    abbrevs = {
        "added": "A",
        "modified": "M",
        "deleted": "D",
        "renamed": "R",
        "copied": "C",
        "untracked": "U",
        "typechange": "T",
    }
    letter = abbrevs.get(base, "?")
    return f"S:{letter}" if status.startswith("staged_") else letter


def _extract_block_uuid(path: str) -> str | None:
    if not path:
        return None
    if not path.startswith(".cozystudio/blocks/") or not path.endswith(".json"):
        return None
    try:
        return Path(path).stem
    except Exception:
        return None


def _build_name_cache(git_instance, entries):
    name_cache = {}
    if not git_instance or not entries:
        return name_cache

    for _type_name, impl_class in git_instance.bpy_protocol.implementations.items():
        data_collection = getattr(bpy.data, impl_class.bl_id, None)
        if not data_collection:
            continue
        for datablock in data_collection:
            uuid = getattr(datablock, "cozystudio_uuid", None)
            if not uuid or uuid not in entries:
                continue
            if uuid not in name_cache:
                name_cache[uuid] = getattr(datablock, "name", None) or uuid

    return name_cache


def _group_label(group_id, group_meta, name_cache):
    group_type = (group_meta or {}).get("type", "group")
    root_uuid = (group_meta or {}).get("root", group_id)
    name = name_cache.get(root_uuid) or root_uuid or "Group"

    if group_type == "object":
        prefix = "Object"
    elif group_type == "shared":
        prefix = "Shared"
    elif group_type == "orphan":
        prefix = "Orphan"
    else:
        prefix = "Group"

    return f"{prefix}: {name}"


def _display_block_label(diff, name_cache):
    uuid = diff.get("uuid")
    entry_type = diff.get("entry_type")
    name = name_cache.get(uuid) or uuid or diff.get("path")
    if entry_type:
        return f"{name} ({entry_type})"
    return name


def _group_diffs(git_instance, diffs):
    entries = (git_instance.state or {}).get("entries", {}) if git_instance else {}
    groups = (git_instance.state or {}).get("groups", {}) if git_instance else {}
    name_cache = _build_name_cache(git_instance, entries)

    grouped = {}
    ungrouped = []

    for diff in diffs:
        path = diff.get("path", "")
        uuid = _extract_block_uuid(path)
        if not uuid or uuid not in entries:
            ungrouped.append(diff)
            continue

        group_id = entries[uuid].get("group_id") or uuid
        entry_type = entries[uuid].get("type")
        group = grouped.setdefault(
            group_id,
            {"group": groups.get(group_id), "diffs": []},
        )
        group["diffs"].append({**diff, "uuid": uuid, "entry_type": entry_type})

    grouped_list = []
    for group_id, data in grouped.items():
        group_meta = data.get("group")
        group_members = (group_meta or {}).get("members", [])
        member_total = len(group_members) if group_members else len(data["diffs"])
        label = _group_label(group_id, group_meta, name_cache)
        if member_total >= len(data["diffs"]):
            label = f"{label} ({len(data['diffs'])}/{member_total})"
        else:
            label = f"{label} ({len(data['diffs'])})"

        grouped_list.append(
            {
                "group_id": group_id,
                "label": label,
                "diffs": sorted(data["diffs"], key=lambda d: d.get("path", "")),
                "name_cache": name_cache,
            }
        )

    if ungrouped:
        enriched = []
        for diff in ungrouped:
            path = diff.get("path", "")
            uuid = _extract_block_uuid(path)
            entry_type = entries.get(uuid, {}).get("type") if uuid else None
            enriched.append({**diff, "uuid": uuid, "entry_type": entry_type})
        grouped_list.append(
            {
                "group_id": None,
                "label": f"Ungrouped ({len(enriched)})",
                "diffs": sorted(enriched, key=lambda d: d.get("path", "")),
                "name_cache": name_cache,
            }
        )

    grouped_list.sort(key=lambda g: g.get("label", ""))
    return grouped_list
