# Cozy Studio Blender Add-on

Cozy Studio is a Blender add-on that tracks Blender datablocks as plain JSON so project changes can be staged, committed, and restored in Git without versioning the binary `.blend` file directly or continusously recording user input.

## What It Does
- Tracks supported Blender datablocks and serializes them into `.blocks/<uuid>.json` files.
- Maintains a manifest (`cozystudio.json`) with block metadata, dependencies, and grouping info.
- Exposes a Git-style workflow inside Blender (stage, commit, checkout).
- Uses GitPython to manage an on-disk repository in the Blender project folder.

## Install & Enable
1. Install the add-on in Blender (zip or folder install).
2. Enable it in Preferences.
3. Click the “Install Dependencies” button in the add-on preferences.

Dependencies are listed in `cozystudio_addon/requirements.txt` and are installed into Blender's Python environment.

[Screencast from 2026-03-11 22-57-20.webm](https://github.com/user-attachments/assets/dd081a9b-d05a-454a-84f5-aeebf6a0389a)



## Usage (In Blender)
1. Save your `.blend` file to a folder that will become the project root.
2. Open the **Cozy Studio** panel in the 3D View sidebar.
3. Click **Init Repository** to create `.blocks/` and initialize a Git repo.
4. Make Blender changes; the add-on writes/updates `.blocks/<uuid>.json` files.
5. Stage individual files or groups from the panel.
6. Commit with a message.
7. Use **Checkout** to restore previous commits (manifest-driven load order).

## Tests
The test harness runs pytest inside Blender.

From `cozystudio_addon/`:
```bash
python test.py
```

Environment overrides (copy `.env.example` to `.env`):
- `COZYSTUDIO_BLENDER_BIN`: path to Blender binary
- `COZYSTUDIO_TEST_DIR`: scratch directory for tests

## Project Layout
- `cozystudio_addon/__init__.py`: Blender entry point; dependency install + addon prefs.
- `cozystudio_addon/auto_load.py`: module discovery and class registration order.
- `cozystudio_addon/ui.py`: UI panel + Git operators (stage, commit, checkout).
- `cozystudio_addon/core/bpy_git/`: Git-backed datablock serialization and checkout.
- `cozystudio_addon/core/bpy_git/tracking.py`: assigns UUIDs to supported datablocks.
- `cozystudio_addon/bl_types/`: datablock serialization protocol and implementations.
- `cozystudio_addon/utils/`: timers, redraw, and JSON persistence helpers.

## Notes
- `.blend` and `.blend1` are intentionally ignored; only `.blocks` and the manifest are tracked.
- The add-on expects Git to be available and uses GitPython for repository actions.
