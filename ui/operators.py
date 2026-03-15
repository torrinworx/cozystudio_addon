import re
import traceback
from pathlib import Path

import bpy

from . import state


class _CozyOperatorMixin:
    @staticmethod
    def _sanitize_branch_name(name):
        sanitized = re.sub(r"\s+", "-", (name or "").strip())
        sanitized = re.sub(r"[~^:?*\\\[]+", "-", sanitized)
        sanitized = sanitized.replace("@{", "-")
        sanitized = re.sub(r"\.\.+", ".", sanitized)
        sanitized = re.sub(r"/\.+", "/", sanitized)
        sanitized = re.sub(r"/+", "/", sanitized)
        sanitized = sanitized.strip("/.")
        sanitized = re.sub(r"-+", "-", sanitized)
        sanitized = re.sub(r"/+$", "", sanitized)
        if sanitized.endswith(".lock"):
            sanitized = sanitized[:-5].rstrip(".-/")
        return sanitized

    @staticmethod
    def _is_valid_branch_name(repo, branch_name):
        if not repo or not branch_name:
            return False
        try:
            repo.git.check_ref_format("--branch", branch_name)
            return True
        except Exception:
            return False

    def _resolve_branch_name(self, repo, raw_name):
        branch_name = (raw_name or "").strip()
        if not branch_name:
            return None, None
        if self._is_valid_branch_name(repo, branch_name):
            return branch_name, None

        sanitized = self._sanitize_branch_name(branch_name)
        if sanitized and self._is_valid_branch_name(repo, sanitized):
            return sanitized, branch_name
        return None, branch_name

    def _require_git(self, require_repo=True):
        if not state.git_instance:
            return "No CozyStudio state is available."
        if require_repo and not getattr(state.git_instance, "initiated", False):
            return "No CozyStudio project is initialized."
        return None

    def _stage_group_paths(self, group_id):
        group = ((state.git_instance.state or {}).get("groups") or {}).get(group_id)
        if not group:
            return None
        return [f".cozystudio/blocks/{uuid}.json" for uuid in group.get("members", [])]

    def _refresh_and_validate(self):
        state.git_instance.refresh_all()
        report = state.git_instance.validate_manifest_integrity()
        state.git_instance.last_integrity_report = report
        state.git_instance.refresh_ui_state()
        return report

    def _sync_preflight(self):
        if state.git_instance._managed_carryover():
            return "Parked Cozy changes already exist. Restore them before continuing."
        dirty_paths = state.git_instance._dirty_paths()
        if state.git_instance._blocking_dirty_paths(dirty_paths):
            return "Working tree has non-Cozy changes. Commit or stash them first."
        return None

    def _integration_preflight(self):
        error = self._sync_preflight()
        if error:
            return error
        if state.git_instance.repo and state.git_instance.repo.head.is_detached:
            return "Checkout a branch before merging or rebasing."
        if getattr(state.git_instance, "manifest", None) and state.git_instance.manifest.get("conflicts"):
            return "Resolve conflicts before merging or rebasing."
        dirty_paths = state.git_instance._dirty_paths()
        cozy_dirty = state.git_instance._cozy_dirty_paths(dirty_paths)
        if cozy_dirty:
            return "Working tree has Cozy changes. Commit or discard them before merging or rebasing."
        return None

    @staticmethod
    def _parse_ref_token(token):
        token = (token or "").strip()
        if not token or token == "NONE" or ":" not in token:
            return None, None
        ref_type, name = token.split(":", 1)
        return ref_type, name


class COZYSTUDIO_OT_SetupProject(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.setup_project"
    bl_label = "Setup Project"
    bl_description = "Initialize CozyStudio tracking for this Blender project"

    def execute(self, context):
        if not bpy.data.filepath:
            self.report({"ERROR"}, "Save this .blend file before setting up CozyStudio")
            return {"CANCELLED"}
        current_path = Path(bpy.path.abspath("//")).resolve()
        local_git_dir = current_path / ".git"
        if state.git_instance is not None:
            try:
                working_tree_dir = getattr(getattr(state.git_instance, "repo", None), "working_tree_dir", None)
                if getattr(state.git_instance, "path", None) != current_path:
                    state.git_instance = None
                elif working_tree_dir and Path(working_tree_dir).resolve() != current_path:
                    state.git_instance = None
                elif not local_git_dir.exists() and getattr(state.git_instance, "repo", None) is not None:
                    state.git_instance = None
            except Exception:
                state.git_instance = None
        if not state.git_instance:
            state.check_and_init_git()
        if not state.git_instance:
            self.report({"ERROR"}, "CozyStudio could not initialize for this file")
            return {"CANCELLED"}
        state.git_instance.init()
        state.git_instance.refresh_ui_state()
        self.report({"INFO"}, "CozyStudio project is ready")
        return {"FINISHED"}


class COZYSTUDIO_OT_Commit(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.commit"
    bl_label = "Commit"
    bl_description = "Commit staged CozyStudio changes"

    message: bpy.props.StringProperty(
        name="Commit Message",
        description="Message for this commit",
        default="",
    )

    def invoke(self, context, event):
        return self.execute(context)

    def draw(self, context):
        self.layout.prop(self, "message")

    def execute(self, context):
        error = self._require_git()
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}

        message = (self.message or "").strip()
        if not message:
            message = (context.window_manager.cozystudio_commit_message or "").strip()
        if not message:
            self.report({"WARNING"}, "Commit message cannot be empty")
            return {"CANCELLED"}

        result = state.git_instance.commit(message=message)
        if not result.get("ok"):
            blockers = result.get("blockers") or []
            errors = result.get("errors") or []
            if blockers:
                self.report({"ERROR"}, blockers[0])
            elif errors:
                self.report({"ERROR"}, errors[0])
            else:
                self.report({"ERROR"}, "Commit failed")
            return {"CANCELLED"}

        if hasattr(context.window_manager, "cozystudio_commit_message"):
            context.window_manager.cozystudio_commit_message = ""
        self.report({"INFO"}, f"Committed: {message}")
        return {"FINISHED"}


class COZYSTUDIO_OT_RunDiagnostics(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.run_diagnostics"
    bl_label = "Run Diagnostics"
    bl_description = "Refresh CozyStudio state and validate manifest integrity"

    def execute(self, context):
        error = self._require_git()
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}

        report = self._refresh_and_validate()
        capture_issues = getattr(state.git_instance, "last_capture_issues", None) or []
        if capture_issues and capture_issues[0].get("reason"):
            self.report({"WARNING"}, capture_issues[0]["reason"])
        if not report.get("ok") and report.get("errors"):
            self.report({"ERROR"}, report["errors"][0])
            return {"CANCELLED"}
        self.report({"INFO"}, "Diagnostics refreshed")
        return {"FINISHED"}


class COZYSTUDIO_OT_ManualRefresh(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.manual_refresh"
    bl_label = "Refresh"
    bl_description = "Refresh CozyStudio Git state and UI"

    def execute(self, context):
        result = bpy.ops.cozystudio.run_diagnostics("EXEC_DEFAULT")
        if "FINISHED" in result:
            return {"FINISHED"}
        return {"CANCELLED"}


class COZYSTUDIO_OT_AddFile(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.add_file"
    bl_label = "Add file to stage"
    bl_description = "Stage a file for commit"

    file_path: bpy.props.StringProperty()

    def execute(self, context):
        error = self._require_git()
        if error:
            return {"CANCELLED"}
        state.git_instance.stage(changes=[self.file_path])
        state.git_instance._update_diffs()
        return {"FINISHED"}


class COZYSTUDIO_OT_UnstageFile(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.unstage_file"
    bl_label = "Unstage file"
    bl_description = "Remove a file from the staging area"

    file_path: bpy.props.StringProperty()

    def execute(self, context):
        error = self._require_git()
        if error:
            return {"CANCELLED"}
        state.git_instance.unstage(changes=[self.file_path])
        state.git_instance._update_diffs()
        return {"FINISHED"}


class COZYSTUDIO_OT_AddGroup(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.add_group"
    bl_label = "Add group to stage"
    bl_description = "Stage all files in this group"

    group_id: bpy.props.StringProperty()

    def execute(self, context):
        error = self._require_git()
        if error or not getattr(state.git_instance, "state", None):
            return {"CANCELLED"}
        paths = self._stage_group_paths(self.group_id)
        if not paths:
            return {"CANCELLED"}
        state.git_instance.stage(changes=paths)
        state.git_instance._update_diffs()
        return {"FINISHED"}


class COZYSTUDIO_OT_UnstageGroup(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.unstage_group"
    bl_label = "Unstage group"
    bl_description = "Unstage all files in this group"

    group_id: bpy.props.StringProperty()

    def execute(self, context):
        error = self._require_git()
        if error or not getattr(state.git_instance, "state", None):
            return {"CANCELLED"}
        paths = self._stage_group_paths(self.group_id)
        if not paths:
            return {"CANCELLED"}
        state.git_instance.unstage(changes=paths)
        state.git_instance._update_diffs()
        return {"FINISHED"}


class COZYSTUDIO_OT_RevertChange(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.revert_change"
    bl_label = "Revert Change"
    bl_description = "Revert a staged or unstaged change"

    file_path: bpy.props.StringProperty()
    status: bpy.props.StringProperty()

    def execute(self, context):
        error = self._require_git()
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        if not self.file_path:
            return {"CANCELLED"}

        repo = state.git_instance.repo
        if repo is None:
            return {"CANCELLED"}

        status = self.status or ""
        is_staged = status.startswith("staged_")
        is_added = status.endswith("added") or status.endswith("untracked")
        file_abs = Path(state.git_instance.path, self.file_path)

        try:
            if is_staged:
                repo.git.restore("--staged", self.file_path)
            if is_added and file_abs.exists():
                file_abs.unlink()
            else:
                repo.git.restore(self.file_path)
        except Exception as e:
            self.report({"ERROR"}, f"Revert failed: {e}")
            traceback.print_exc()
            return {"CANCELLED"}

        if self.file_path.startswith(".cozystudio/blocks/") and self.file_path.endswith(
            ".json"
        ):
            uuid = Path(self.file_path).stem
            if file_abs.exists():
                try:
                    data = state.git_instance._read(uuid)
                    if data.get("uuid") is None:
                        data["uuid"] = uuid
                    state.git_instance.deserialize(data)
                except Exception as e:
                    self.report({"ERROR"}, f"Failed to restore datablock: {e}")
                    traceback.print_exc()
                    return {"CANCELLED"}

        state.git_instance._update_diffs()
        state.git_instance.refresh_ui_state()
        return {"FINISHED"}


class COZYSTUDIO_OT_ToggleGroupExpanded(bpy.types.Operator):
    bl_idname = "cozystudio.toggle_group_expanded"
    bl_label = "Toggle group"
    bl_description = "Expand or collapse a group"

    group_id: bpy.props.StringProperty()

    def execute(self, context):
        if self.group_id in state._group_expanded:
            state._group_expanded.remove(self.group_id)
        else:
            state._group_expanded.add(self.group_id)
        return {"FINISHED"}


class COZYSTUDIO_OT_CheckoutCommit(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.checkout_commit"
    bl_label = "Checkout Commit"
    bl_description = "Checkout a commit using CozyStudio reconstruction"

    commit_hash: bpy.props.StringProperty(
        name="Commit Hash",
        description="Commit hash to checkout",
        default="",
    )

    def execute(self, context):
        error = self._require_git()
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        preflight = self._sync_preflight()
        if preflight:
            self.report({"ERROR"}, preflight)
            return {"CANCELLED"}
        if not self.commit_hash.strip():
            self.report({"WARNING"}, "Please enter a commit hash")
            return {"CANCELLED"}
        try:
            state.git_instance.checkout(self.commit_hash)
            if state.git_instance._managed_carryover():
                self.report(
                    {"WARNING"},
                    f"Checked out commit {self.commit_hash[:8]}; local Cozy changes are parked safely.",
                )
            else:
                self.report({"INFO"}, f"Checked out commit {self.commit_hash[:8]}")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Checkout failed: {e}")
            traceback.print_exc()
            return {"CANCELLED"}


class COZYSTUDIO_OT_FetchBranches(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.fetch_branches"
    bl_label = "Fetch Branches"
    bl_description = "Fetch remote branches and refresh branch data"

    def execute(self, context):
        error = self._require_git()
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        if getattr(state.git_instance, "manifest", None) and state.git_instance.manifest.get("conflicts"):
            self.report({"ERROR"}, "Resolve conflicts before fetching branch data")
            return {"CANCELLED"}
        try:
            fetched = state.git_instance.fetch_remotes()
            if not fetched:
                self.report({"INFO"}, "No remotes configured")
            else:
                self.report({"INFO"}, f"Fetched {', '.join(fetched)}")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Fetch failed: {e}")
            traceback.print_exc()
            return {"CANCELLED"}


class COZYSTUDIO_OT_CheckoutSelectedRef(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.checkout_selected_ref"
    bl_label = "Switch Ref"
    bl_description = "Switch to the selected branch or remote tracking branch"

    ref_token: bpy.props.StringProperty(
        name="Selected Ref",
        description="Branch or remote ref token",
        default="",
    )

    def execute(self, context):
        error = self._require_git()
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}

        preflight = self._sync_preflight()
        if preflight:
            self.report({"ERROR"}, preflight)
            return {"CANCELLED"}
        if getattr(state.git_instance, "manifest", None) and state.git_instance.manifest.get("conflicts"):
            self.report({"ERROR"}, "Resolve conflicts before switching branches")
            return {"CANCELLED"}

        token = self.ref_token or context.window_manager.cozystudio_branch_target
        ref_type, ref_name = self._parse_ref_token(token)
        if not ref_name:
            self.report({"WARNING"}, "Choose a branch or remote ref")
            return {"CANCELLED"}

        try:
            if ref_type == "remote":
                state.git_instance.checkout_remote_branch(ref_name)
                local_name = ref_name.split("/", 1)[-1]
                self.report({"INFO"}, f"Checked out tracking branch {local_name}")
            else:
                state.git_instance.switch_branch(ref_name)
                self.report({"INFO"}, f"Checked out branch {ref_name}")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Branch switch failed: {e}")
            traceback.print_exc()
            return {"CANCELLED"}


class COZYSTUDIO_OT_ReapplyParkedChanges(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.reapply_parked_changes"
    bl_label = "Restore Parked Changes"
    bl_description = "Restore Cozy changes that were parked during checkout, merge, or rebase"

    def execute(self, context):
        error = self._require_git()
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}

        result = state.git_instance.reapply_parked_changes()
        if not result.get("ok"):
            self.report({"ERROR"}, result.get("error", "Failed to restore parked Cozy changes"))
            return {"CANCELLED"}

        self.report({"INFO"}, "Restored parked Cozy changes")
        return {"FINISHED"}


class COZYSTUDIO_OT_CheckoutBranch(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.checkout_branch"
    bl_label = "Checkout Branch"
    bl_description = "Checkout a branch using CozyStudio reconstruction"

    branch_name: bpy.props.StringProperty(
        name="Branch",
        description="Branch name to switch to",
        default="",
    )

    def execute(self, context):
        error = self._require_git()
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        preflight = self._sync_preflight()
        if preflight:
            self.report({"ERROR"}, preflight)
            return {"CANCELLED"}
        if getattr(state.git_instance, "manifest", None) and state.git_instance.manifest.get("conflicts"):
            self.report({"ERROR"}, "Resolve conflicts before switching branches")
            return {"CANCELLED"}
        if not self.branch_name.strip():
            self.report({"WARNING"}, "Please enter a branch name")
            return {"CANCELLED"}
        try:
            state.git_instance.switch_branch(self.branch_name)
            if state.git_instance._managed_carryover():
                self.report(
                    {"WARNING"},
                    f"Checked out branch {self.branch_name}; local Cozy changes are parked safely.",
                )
            else:
                self.report({"INFO"}, f"Checked out branch {self.branch_name}")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Branch checkout failed: {e}")
            traceback.print_exc()
            return {"CANCELLED"}


class COZYSTUDIO_OT_CreateBranch(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.create_branch"
    bl_label = "Create Branch"
    bl_description = "Create and checkout a new branch"

    branch_name: bpy.props.StringProperty(
        name="Branch",
        description="Branch name to create",
        default="",
    )
    ref: bpy.props.StringProperty(
        name="Ref",
        description="Optional commit hash to branch from",
        default="",
    )

    def execute(self, context):
        error = self._require_git()
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        preflight = self._sync_preflight()
        if preflight:
            self.report({"ERROR"}, preflight)
            return {"CANCELLED"}
        if getattr(state.git_instance, "manifest", None) and state.git_instance.manifest.get("conflicts"):
            self.report({"ERROR"}, "Resolve conflicts before creating a branch")
            return {"CANCELLED"}

        repo = state.git_instance.repo
        requested_name = self.branch_name or context.window_manager.cozystudio_branch_name or ""
        branch_name, adjusted_from = self._resolve_branch_name(repo, requested_name)
        if not branch_name:
            self.report({"WARNING"}, "Enter a valid branch name")
            return {"CANCELLED"}

        if repo and branch_name in {head.name for head in repo.heads}:
            self.report({"ERROR"}, f"Branch '{branch_name}' already exists")
            return {"CANCELLED"}

        ref = (self.ref or "").strip() or None
        if ref and repo:
            try:
                repo.commit(ref)
            except Exception:
                self.report({"ERROR"}, "Selected commit was not found")
                return {"CANCELLED"}

        try:
            state.git_instance.create_branch(branch_name, ref=ref)
            if hasattr(context.window_manager, "cozystudio_branch_name"):
                context.window_manager.cozystudio_branch_name = ""
            if adjusted_from and adjusted_from != branch_name:
                self.report({"INFO"}, f"Created branch {branch_name} from '{adjusted_from}'")
                return {"FINISHED"}
            self.report({"INFO"}, f"Created branch {branch_name}")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Branch creation failed: {e}")
            traceback.print_exc()
            return {"CANCELLED"}


class COZYSTUDIO_OT_Merge(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.merge"
    bl_label = "Merge"
    bl_description = "Merge another branch or ref into the current branch"

    ref_name: bpy.props.StringProperty(
        name="Source Branch or Ref",
        description="Branch or ref to merge into the current branch",
        default="",
    )
    strategy: bpy.props.EnumProperty(
        name="Conflict Strategy",
        description="Conflict strategy to use during the merge",
        items=[
            ("manual", "Manual", "Record conflicts for manual resolution"),
            ("ours", "Keep Current", "Prefer the current branch on conflict"),
            ("theirs", "Take Incoming", "Prefer incoming changes on conflict"),
        ],
        default="manual",
    )

    def execute(self, context):
        error = self._require_git()
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        preflight = self._integration_preflight()
        if preflight:
            self.report({"ERROR"}, preflight)
            return {"CANCELLED"}
        if not self.ref_name.strip():
            self.report({"WARNING"}, "Choose a branch or ref to merge")
            return {"CANCELLED"}

        result = state.git_instance.merge(self.ref_name, strategy=self.strategy)
        if result.get("errors"):
            self.report({"ERROR"}, result["errors"][0])
            if not result.get("conflicts"):
                return {"CANCELLED"}
        if result.get("conflicts"):
            state.git_instance.refresh_ui_state()
            if result.get("carryover", {}).get("parked"):
                self.report(
                    {"WARNING"},
                    "Merge stopped for conflict resolution; local Cozy changes are parked safely.",
                )
            else:
                self.report({"WARNING"}, "Merge stopped for conflict resolution")
            return {"FINISHED"}
        if result.get("warnings"):
            self.report({"WARNING"}, result["warnings"][0])
            return {"FINISHED"}
        self.report({"INFO"}, f"Merged {self.ref_name}")
        return {"FINISHED"}


class COZYSTUDIO_OT_Rebase(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.rebase"
    bl_label = "Rebase"
    bl_description = "Rebase the current branch onto another branch or ref"

    ref_name: bpy.props.StringProperty(
        name="Onto Branch or Ref",
        description="Branch or ref to replay current work onto",
        default="",
    )
    strategy: bpy.props.EnumProperty(
        name="Conflict Strategy",
        description="Conflict strategy to use during the rebase",
        items=[
            ("manual", "Manual", "Record conflicts for manual resolution"),
            ("ours", "Keep Current", "Prefer current changes on conflict"),
            ("theirs", "Take Target", "Prefer target changes on conflict"),
        ],
        default="manual",
    )

    def execute(self, context):
        error = self._require_git()
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        preflight = self._integration_preflight()
        if preflight:
            self.report({"ERROR"}, preflight)
            return {"CANCELLED"}
        if not self.ref_name.strip():
            self.report({"WARNING"}, "Choose a branch or ref to rebase onto")
            return {"CANCELLED"}

        result = state.git_instance.rebase(self.ref_name, strategy=self.strategy)
        if result.get("errors"):
            self.report({"ERROR"}, result["errors"][0])
            if not result.get("conflicts"):
                return {"CANCELLED"}
        if result.get("conflicts"):
            state.git_instance.refresh_ui_state()
            if result.get("carryover", {}).get("parked"):
                self.report(
                    {"WARNING"},
                    "Rebase stopped for conflict resolution; local Cozy changes are parked safely.",
                )
            else:
                self.report({"WARNING"}, "Rebase stopped for conflict resolution")
            return {"FINISHED"}
        if result.get("warnings"):
            self.report({"WARNING"}, result["warnings"][0])
            return {"FINISHED"}
        self.report({"INFO"}, f"Rebased onto {self.ref_name}")
        return {"FINISHED"}


class COZYSTUDIO_OT_IntegrateSelectedRef(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.integrate_selected_ref"
    bl_label = "Integrate Selected Ref"
    bl_description = "Merge or rebase the current branch with the selected target"

    ref_token: bpy.props.StringProperty(
        name="Target Ref",
        description="Target branch or remote ref token",
        default="",
    )
    mode: bpy.props.EnumProperty(
        name="Mode",
        description="Integration mode",
        items=[
            ("MERGE", "Merge", "Merge the target into the current branch"),
            ("REBASE", "Rebase", "Rebase the current branch onto the target"),
        ],
        default="MERGE",
    )
    strategy: bpy.props.EnumProperty(
        name="Conflict Strategy",
        description="How Cozy should handle conflicting blocks",
        items=[
            ("manual", "Manual", "Stop and let you resolve conflicts"),
            ("ours", "Keep Current", "Prefer the current branch on conflict"),
            ("theirs", "Take Incoming", "Prefer the target branch on conflict"),
        ],
        default="manual",
    )

    def execute(self, context):
        error = self._require_git()
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}

        preflight = self._integration_preflight()
        if preflight:
            self.report({"ERROR"}, preflight)
            return {"CANCELLED"}

        token = self.ref_token or context.window_manager.cozystudio_integration_target
        mode = self.mode or context.window_manager.cozystudio_integration_mode
        strategy = self.strategy or context.window_manager.cozystudio_conflict_strategy
        _ref_type, ref_name = self._parse_ref_token(token)
        if not ref_name:
            self.report({"WARNING"}, "Choose a branch or remote ref to integrate")
            return {"CANCELLED"}

        current = state.git_instance.ui_state.get("branch", {}).get("current")
        if current and ref_name == current:
            self.report({"WARNING"}, "Choose a different branch than the current branch")
            return {"CANCELLED"}

        op = bpy.ops.cozystudio.merge if mode == "MERGE" else bpy.ops.cozystudio.rebase
        result = op("EXEC_DEFAULT", ref_name=ref_name, strategy=strategy)
        if "FINISHED" in result:
            return {"FINISHED"}
        return {"CANCELLED"}


class COZYSTUDIO_OT_ResolveConflict(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.resolve_conflict"
    bl_label = "Resolve Conflict"
    bl_description = "Mark a CozyStudio conflict as resolved after you have fixed the scene"

    conflict_uuid: bpy.props.StringProperty(
        name="Conflict UUID",
        description="Specific conflict entry to clear; leave empty to clear all",
        default="",
    )

    def execute(self, context):
        error = self._require_git()
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        manifest = getattr(state.git_instance, "manifest", None)
        if not isinstance(manifest, dict):
            self.report({"ERROR"}, "No manifest is loaded")
            return {"CANCELLED"}

        if self.conflict_uuid:
            result = state.git_instance.resolve_conflict(self.conflict_uuid, resolution="manual")
            if not result.get("ok"):
                self.report({"ERROR"}, result.get("error", "Conflict entry was not found"))
                return {"CANCELLED"}
            self._refresh_and_validate()
            self.report({"INFO"}, "Conflict marked manually resolved")
            return {"FINISHED"}

        conflicts = state.git_instance._manifest_conflict_items()
        if not conflicts:
            self.report({"WARNING"}, "No conflicts to resolve")
            return {"CANCELLED"}

        state.git_instance._set_manifest_conflicts([])
        manifest.write()
        self._refresh_and_validate()
        self.report({"INFO"}, "All conflict markers cleared")
        return {"FINISHED"}


class COZYSTUDIO_OT_ResolveConflictVersion(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.resolve_conflict_version"
    bl_label = "Apply Conflict Version"
    bl_description = "Resolve a CozyStudio conflict by checking out your side or the incoming side"

    conflict_uuid: bpy.props.StringProperty(
        name="Conflict UUID",
        description="Conflict entry to resolve",
        default="",
    )
    resolution: bpy.props.EnumProperty(
        name="Resolution",
        description="Conflict version to apply",
        items=[
            ("ours", "Checkout Mine", "Keep the current branch or replayed version"),
            ("theirs", "Checkout Theirs", "Take the incoming version for this conflict"),
        ],
        default="ours",
    )

    def execute(self, context):
        error = self._require_git()
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        if not self.conflict_uuid:
            self.report({"ERROR"}, "Conflict UUID is required")
            return {"CANCELLED"}

        result = state.git_instance.resolve_conflict(self.conflict_uuid, resolution=self.resolution)
        if not result.get("ok"):
            self.report({"ERROR"}, result.get("error", "Failed to resolve conflict"))
            return {"CANCELLED"}

        self._refresh_and_validate()
        label = "mine" if self.resolution == "ours" else "theirs"
        self.report({"INFO"}, f"Checked out {label} for {self.conflict_uuid}")
        return {"FINISHED"}


class COZYSTUDIO_OT_SelectBlock(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.select_block"
    bl_label = "Select datablock"
    bl_description = "Select the Blender datablock tied to this entry"

    uuid: bpy.props.StringProperty()

    def execute(self, context):
        error = self._require_git()
        if error or not self.uuid:
            return {"CANCELLED"}

        datablock = None
        for _type_name, impl_class in state.git_instance.bpy_protocol.implementations.items():
            data_collection = getattr(bpy.data, impl_class.bl_id, None)
            if not data_collection:
                continue
            for block in data_collection:
                if getattr(block, "cozystudio_uuid", None) == self.uuid:
                    datablock = block
                    break
            if datablock is not None:
                break

        if datablock is None:
            return {"CANCELLED"}

        if context.view_layer:
            for obj in context.view_layer.objects:
                obj.select_set(False)

        selected = []
        if isinstance(datablock, bpy.types.Object):
            datablock.select_set(True)
            selected = [datablock]
        else:
            for obj in bpy.data.objects:
                if getattr(obj, "data", None) == datablock:
                    obj.select_set(True)
                    selected.append(obj)
                    continue
                materials = getattr(getattr(obj, "data", None), "materials", None)
                if materials and datablock in materials:
                    obj.select_set(True)
                    selected.append(obj)

        if selected and context.view_layer:
            context.view_layer.objects.active = selected[0]
        return {"FINISHED"}
