# Cozy Studio for Blender

Cozy Studio is a Blender add-on that brings a Git-style workflow to your Blender projects. It tracks Blender datablocks as readable files so you can see meaningful changes without relying on raw `.blend` diffs, and commit from inside Blender.

If you have ever wished Blender changes behaved more like code changes, Cozy Studio is built for that. You get a clean history of what changed, the ability to stage only the parts you want, and a workflow that stays inside Blender.

Get meaningful diffs based on Blender datablocks instead of binary files

## How it stores changes
Cozy Studio watches supported datablocks and writes them out as readable files. Those files are what you stage and commit. This keeps your history clear and reviewable while still working normally in Blender. This means you can do fancy things like this:

[Screencast from 2026-03-11 22-57-20.webm](https://github.com/user-attachments/assets/dd081a9b-d05a-454a-84f5-aeebf6a0389a)

## Usage (In Blender)
1. Save your `.blend` file to a folder that will become the project root.
2. Open the **Cozy Studio** panel in the 3D View sidebar.
3. Click **Init Repository** to initialize a Git/CozyStudio repo.
4. Make Blender changes; the add-on will automatically serialize and write the datablocks.
5. Stage individual changes or groups from the panel.
6. Commit with a message.
7. Use **Checkout** to restore previous commits (manifest-driven load order).

## Install
1. Download the Cozy Studio add-on (zip or folder).
2. In Blender: **Edit > Preferences > Add-ons > Install…**
3. Enable **Cozy Studio**.
4. In the add-on preferences, click **Install Dependencies**.

## Issues
If something doesn’t work, please open an issue with steps to reproduce.
