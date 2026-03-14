# Cozy Studio Add-on Plan

Current direction:

- Use standard Git terminology in the UI.
- Keep the main workflow simple: `Changes`, `History`, `Branches`.
- Treat `.cozystudio/manifest.json` and `.cozystudio/blocks/*.json` as the only tracked history artifacts.
- Rebuild scene state from tracked datablocks for commit checkout and branch checkout.
- Handle stash/carryover behavior automatically with managed Git stash flows hidden behind the UI.

## Foundation

- [x] Commit only Cozy tracked artifacts by default
- [x] Ignore normal `.blend` saves in Cozy history
- [x] Route restore and branch switching through datablock reconstruction
- [x] Expose a consolidated UI state payload from the backend
- [x] Build grouped semantic diffs for tracked datablocks

## 1. Git-Native UI Shell

- [x] Make `Changes` the main work surface
- [x] Put commit message, commit action, staged changes, and unstaged changes in `Changes`
- [x] Keep `History` focused on commit inspection and `Checkout Commit`
- [x] Add a `Branches` panel for branch checkout, merge, and rebase
- [x] Remove redundant top-level panels and abstract product-language copy
- [x] Show `Conflicts` only when conflicts exist
- [x] Keep `Diagnostics` separate and minimal

## 2. Operator and Copy Cleanup

- [x] Rename UI operators and labels to Git terms (`commit`, `checkout commit`, `checkout branch`, `merge`, `rebase`)
- [x] Remove compatibility aliases and unused experimental operators
- [x] Keep safe preflight checks for commit, checkout, merge, and rebase
- [x] Keep detached-head handling explicit and understandable in the UI

## 3. Branch and History Workflows

- [x] Make commit checkout clearly detached-head aware
- [x] Provide a clear return path from detached HEAD back to a branch checkout
- [x] Keep merge and rebase available from `Branches` without extra panel sprawl
- [x] Avoid exposing unnecessary Git detail until the workflow needs it

## 4. Conflict Handling

- [ ] Upgrade manifest conflict entries into structured UI-friendly records
- [ ] Show blocking conflict state in the main workflow when present
- [ ] Keep a dedicated `Conflicts` panel only for active resolution work
- [ ] Add backend helpers for per-conflict resolution and merge finalization

## 5. Diagnostics and Trust Signals

- [ ] Show integrity problems, capture issues, missing blocks, and last-operation failures clearly
- [ ] Persist important warnings until they are resolved
- [ ] Avoid relying on console output as the only user-visible error signal

## 6. Automatic Carryover / Stash Behavior

- [x] Define expected behavior for uncommitted Cozy changes during branch checkout and commit checkout
- [x] Auto-stash Cozy changes before checkout, merge, and rebase flows and reapply them when appropriate
- [x] Surface recovery UI when stash apply fails or conflicts are introduced
- [x] Preserve commit history integrity while carryover logic is active

## 7. Testing

- [x] Update registration and integration tests for the Git-native shell
- [x] Add coverage for commit checkout and branch checkout reconstruction
- [x] Add coverage for commit preflight blockers
- [x] Add coverage for merge/rebase UI flows
- [ ] Add coverage for structured conflict generation and resolution
- [x] Add coverage for stash/carryover behavior

## Done When

- [ ] Users can save `.blend` files normally without Cozy interfering
- [ ] Commit history contains only Cozy tracked artifacts
- [ ] Commit checkout and branch checkout rebuild from manifest and block files
- [ ] The UI uses clear Git terminology and stays easy to navigate
- [ ] Conflicts appear only when needed and can be resolved in the UI
- [ ] Diagnostics make trust-critical problems visible
