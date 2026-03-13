# Cozy Studio Add-on Overhaul Plan

This file tracks the implementation plan for the Cozy Studio Blender add-on overhaul.

Core product rules:

- Native Blender save remains untouched.
- Normal `.blend` saves are ignored by Cozy snapshot history.
- Cozy history is driven by `.cozystudio/manifest.json` and `.cozystudio/blocks/*.json`.
- `.blend` skeleton/bootstrap handling is only for project init/open/clone/recovery, not for every snapshot.
- Restore, branch switching, merge results, and history navigation rebuild from tracked datablocks.

## Tracking

- [x] Record the approved overhaul plan in `cozystudio_addon/PLAN.md`

## Phase 1 - History Model Cleanup

- [ ] Remove bootstrap `.blend` writes from normal snapshot commits
- [ ] Stop staging bootstrap `.blend` files during snapshot commits
- [ ] Keep `.blend` files excluded from regular change detection and staging
- [ ] Make manifest and block files the only committed history artifacts by default
- [ ] Verify snapshot commits work without committed `.blend` binaries

## Phase 2 - Open / Restore / Switch Pipeline

- [ ] Introduce one backend restore entrypoint for ref restore and working-tree reconstruction
- [ ] Route branch switching through the same safe restore path as snapshot restore
- [ ] Limit bootstrap shell creation to init/open/clone/recovery flows
- [ ] Preserve orphan cleanup and dependency-ordered restore in every reconstruction path
- [ ] Verify restore and ref switching work from manifest and block files alone

## Phase 3 - Consolidated UI State API

- [ ] Add a single UI-facing state payload on `BpyGit`
- [ ] Include repo state, branch state, past-snapshot state, conflicts, integrity, and change counts
- [ ] Stop having panels read scattered backend internals directly
- [ ] Make panel rendering depend on the consolidated state payload

## Phase 4 - Semantic Diff Layer

- [ ] Enrich diff rows with UUID, datablock type, group ID, display name, and summary
- [ ] Add human-readable summaries for transforms, creation/deletion, collection changes, materials, and animation edits
- [ ] Add safe generic fallback summaries for unsupported fine-grained diff cases
- [ ] Keep grouping aligned with backend object/shared/orphan group logic

## Phase 5 - UI Shell Rewrite

- [ ] Replace the current experimental panels with a state-driven shell
- [ ] Create `Project` panel for setup and project status
- [ ] Create `Changes` panel for grouped asset/datablock changes
- [ ] Create `Snapshot` panel as the main commit surface
- [ ] Create `History` panel for timeline and restore flows
- [ ] Create `Sync` panel for branch/merge/rebase workflows
- [ ] Create `Conflicts` panel for resolution workflows
- [ ] Create `Diagnostics` panel for integrity and system status
- [ ] Add an `Advanced` mode for raw Git-oriented details

## Phase 6 - Operator Redesign

- [ ] Replace or wrap placeholder operators with product-language operators
- [ ] Add project setup, snapshot, restore, branch switch, merge, rebase, conflict resolve, and diagnostics operators
- [ ] Remove direct unsafe branch checkout behavior from the UI layer
- [ ] Keep temporary compatibility shims for legacy operator names while migrating tests

## Phase 7 - Snapshot Flow Hardening

- [ ] Add structured preflight checks for snapshot actions
- [ ] Keep snapshot blocking on integrity errors and unresolved conflicts
- [ ] Return structured backend results for UI feedback instead of bool-only outcomes
- [ ] Preserve grouped staging behavior for related datablocks

## Phase 8 - History Timeline

- [ ] Replace the minimal commit list with richer snapshot timeline items
- [ ] Add snapshot detail inspection with changed asset summaries
- [ ] Add restore actions from history items
- [ ] Add explicit `Viewing Past Snapshot` state and `Return to Branch` flow

## Phase 9 - Sync / Branch / Merge / Rebase

- [ ] Build a user-facing sync workflow over the existing merge/rebase backend
- [ ] Rename merge to `Bring In Changes` in the main UX
- [ ] Rename rebase to `Replay My Work` in the main UX
- [ ] Add preflight and safety checks for branch/sync operations
- [ ] Keep advanced branch operations hidden until the main workflow is stable

## Phase 10 - Conflict Model Upgrade

- [ ] Upgrade manifest conflict entries to structured records for UI use
- [ ] Store asset name, type, group, reason, tier, and allowed actions in conflict entries
- [ ] Add backend methods for per-conflict resolution
- [ ] Add a finalize-merge path once conflicts are resolved
- [ ] Surface a blocking conflicts banner and dedicated conflict resolution UI

## Phase 11 - Diagnostics

- [ ] Add a diagnostics view for manifest integrity, missing blocks, orphan cleanup issues, unsupported data, and last operation log
- [ ] Persist warnings until they are resolved
- [ ] Make trust-critical backend problems visible without using raw console output as the only signal

## Phase 12 - UI State / Props Refactor

- [ ] Expand UI props for active section, filters, selected history item, selected branch/ref, selected conflict, snapshot message, and advanced mode
- [ ] Move heavy panel state preparation out of panel draw methods
- [ ] Build reusable UI helpers for state-driven rendering

## Phase 13 - Testing and Regression Coverage

- [ ] Add tests proving snapshots do not commit or depend on `.blend` binaries
- [ ] Add tests for restore and branch switch reconstruction from manifest/block data
- [ ] Add tests for semantic diff payload generation
- [ ] Add tests for snapshot preflight behavior
- [ ] Add tests for merge/rebase UI-facing flows
- [ ] Add tests for structured conflict generation and resolution
- [ ] Update UI registration and operator coverage tests for the new shell

## Definition Of Done

- [ ] Users can save `.blend` files normally without Cozy interfering
- [ ] Snapshot history commits only Cozy tracked artifacts
- [ ] Restore and branch switching rebuild from manifest and block files
- [ ] The main workflow avoids raw Git jargon for typical Blender users
- [ ] Conflicts are visible, blocking, and resolvable in UI
- [ ] Diagnostics explain integrity problems clearly
