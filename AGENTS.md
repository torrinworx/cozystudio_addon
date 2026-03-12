# AGENTS

This file is the persistent context for LLM agents working in `cozystudio_addon`.
It is prescriptive. Use it as the ground rules and architecture memory.

## PURPOSE & NON-GOALS
- Purpose: stable operational memory for agents so they can act correctly without re-discovering core architecture.
- Non-goals: this is not a full documentation set or per-module reference. Read code for specifics.
- If working inside a git submodule, always check for a nested `AGENTS.md` and follow it.

## PROJECT PHILOSOPHY
- Datablocks are source of truth; `.blend` binaries are bootstraps only.
- Prefer explicit, deterministic serialization over implicit magic.
- Keep Git-facing behavior predictable and UI-driven.
- READMEs are condensed, accurate summaries, not substitutes for code.

## DECISION HIERARCHY
1) System invariants
2) Architecture coherence
3) Module clarity
4) Style rules
5) Local convenience
6) Micro-optimizations

If a change violates a higher tier, it is wrong even if it "works."

## ARCHITECTURE MAP (COZYSTUDIO_ADDON)
- Blender entry: `cozystudio_addon/__init__.py` registers core classes, dependency install operator, and auto-load.
- Auto registration: `cozystudio_addon/auto_load.py` discovers modules, orders class registration, and calls module hooks.
- UI + operators: `cozystudio_addon/ui.py` provides the Git panel, staging, commit, and checkout actions.
- Git core: `cozystudio_addon/core/bpy_git/__init__.py` manages repo init, diffs, stage/unstage, manifest updates, and checkout restore.
- UUID tracking: `cozystudio_addon/core/bpy_git/tracking.py` assigns `cozystudio_uuid` to supported datablocks.
- Serialization protocol: `cozystudio_addon/bl_types/` implements datablock dump/construct/load and dep resolution.
- Utilities: `cozystudio_addon/utils/` provides timers, redraw, and JSON persistence helpers.

## ADD-ON LIFECYCLE CONTRACT
- Add-on registration must not assume dependencies are installed.
- Dependency install happens via `cozystudio.install_deps` and only then auto-loads full module registration.
- `BpyGit` only initializes once a `.blend` is saved and a repo exists or is created by the user.
- `.blend` is a committed bootstrap named after the project folder; `.blend1` is ignored.
- `.cozystudio/manifest.json` + `.cozystudio/blocks/` are the tracked artifacts.

## CODING POLICY (STRICT)
- No one-off helper functions. Inline unless reused in multiple places.
- No aliasing variables if they are used directly and not transformed.
- Shared utilities live in `common/` only if they are cross-module and justified.
- Keep code tight and direct; avoid helper sprawl.

## ANTI-PATTERNS
- Local helpers used once (e.g., `toArray`, `normalizeX`) instead of inline logic.
- Defensive guards for guaranteed injections.
- Re-declaring config aliases without transformation.

## DOCS POLICY
- Update AGENTS.md after any core architecture or invariant change.
- Update READMEs only after user confirms changes are working and satisfactory.
- Update CHANGES.md only after user confirms changes are working and satisfactory.
- Always tell the user when docs were updated.

## ECOSYSTEM CONTEXT
- Blender data is tracked via `bl_types` serialization (extracted from multi-user).
- Git operations are performed via GitPython within the Blender project folder.
- Manifest (`.cozystudio/manifest.json`) is the authoritative index of tracked datablocks.
