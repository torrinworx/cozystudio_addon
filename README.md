# Cozy Studio

Version control lets you track changes, keep history, and collaborate safely. Cozy Studio brings the ease of Git version control to Blender in a way that fits how Blender projects actually work.

Control the history and versioning of your `.blend` projects, see who changed what and when, revert changes, check out older versions, and merge or rebase updates, all from the Blender UI.

# How does it work?
Other Blender version control systems rely on storing full `.blend` copies or recording user inputs. Those methods are bulky, fragile, and make it hard to understand what actually changed.

Cozy Studio uses Blender's datablock system. It serializes individual datablocks into JSON files, stores them in a Git repo, and deserializes them back into Blender when you check out a previous commit or reopen a project.

This runs alongside Blender's autosave without interfering with it, so you can keep autosave on and still get clean, reviewable history.

[Screencast from 2026-03-11 22-57-20.webm](https://github.com/user-attachments/assets/dd081a9b-d05a-454a-84f5-aeebf6a0389a)

# Features
- Datablock-based diffs written as readable files.
- Stage or unstage individual changes or grouped updates.
- Commit from inside Blender with clear blockers when something is wrong.
- Check out older commits or switch branches from the UI.
- Merge and rebase with conflict resolution tools.

# Quick Start (In Blender)
1. Save your `.blend` file to a folder that will become the project root.
2. Open the **Cozy Studio** panel in the 3D View sidebar.
3. Click **Init Repository** to initialize a Git/Cozy Studio repo.
4. Make Blender changes; Cozy Studio will write datablocks automatically.
5. Stage individual changes or groups from the panel.
6. Commit with a message.
7. Use **Checkout** to restore previous commits.

# Install
1. Download the Cozy Studio add-on (zip or folder).
2. In Blender: **Edit > Preferences > Add-ons > Install...**
3. Enable **Cozy Studio**.
4. In the add-on preferences, click **Install Dependencies**.
