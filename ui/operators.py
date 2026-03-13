import traceback

import bpy

from . import state


class _CozyOperatorMixin:
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


class COZYSTUDIO_OT_SetupProject(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.setup_project"
    bl_label = "Setup Project"
    bl_description = "Initialize CozyStudio tracking for this Blender project"

    def execute(self, context):
        if not bpy.data.filepath:
            self.report({"ERROR"}, "Save this .blend file before setting up CozyStudio")
            return {"CANCELLED"}
        if not state.git_instance:
            state.check_and_init_git()
        if not state.git_instance:
            self.report({"ERROR"}, "CozyStudio could not initialize for this file")
            return {"CANCELLED"}
        state.git_instance.init()
        state.git_instance.refresh_ui_state()
        self.report({"INFO"}, "CozyStudio project is ready")
        return {"FINISHED"}


class INIT_OT_PrintOperator(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.init_repo"
    bl_label = "Init"
    bl_description = "Initialize CozyStudio Git repository for this project"

    def execute(self, context):
        result = bpy.ops.cozystudio.setup_project("EXEC_DEFAULT")
        if "FINISHED" in result:
            return {"FINISHED"}
        return {"CANCELLED"}


class COZYSTUDIO_OT_CreateSnapshot(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.create_snapshot"
    bl_label = "Create Snapshot"
    bl_description = "Create a CozyStudio snapshot from staged datablock changes"

    message: bpy.props.StringProperty(
        name="Snapshot Message",
        description="Message for this snapshot",
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
            self.report({"WARNING"}, "Snapshot message cannot be empty")
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
                self.report({"ERROR"}, "Snapshot failed")
            return {"CANCELLED"}

        if hasattr(context.window_manager, "cozystudio_commit_message"):
            context.window_manager.cozystudio_commit_message = ""
        self.report({"INFO"}, f"Snapshot created: {message}")
        return {"FINISHED"}


class COMMMIT_OT_PrintOperator(_CozyOperatorMixin, bpy.types.Operator):
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
        result = bpy.ops.cozystudio.create_snapshot(
            "EXEC_DEFAULT",
            message=self.message,
        )
        if "FINISHED" in result:
            return {"FINISHED"}
        return {"CANCELLED"}


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


class COZYSTUDIO_OT_RestoreSnapshot(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.restore_snapshot"
    bl_label = "Restore Snapshot"
    bl_description = "Restore the scene from a previous CozyStudio snapshot"

    commit_hash: bpy.props.StringProperty(
        name="Snapshot",
        description="Commit hash to restore",
        default="",
    )

    def execute(self, context):
        error = self._require_git()
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        if not self.commit_hash.strip():
            self.report({"WARNING"}, "Please enter a snapshot hash")
            return {"CANCELLED"}
        try:
            state.git_instance.checkout(self.commit_hash)
            self.report({"INFO"}, f"Restored snapshot {self.commit_hash[:8]}")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Restore failed: {e}")
            traceback.print_exc()
            return {"CANCELLED"}


class COZYSTUDIO_OT_CheckoutCommit(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.checkout_commit"
    bl_label = "Checkout Commit"
    bl_description = "Checkout a specific commit hash"

    commit_hash: bpy.props.StringProperty(
        name="Commit Hash",
        description="Enter git commit hash to checkout",
        default="",
    )

    def execute(self, context):
        result = bpy.ops.cozystudio.restore_snapshot(
            "EXEC_DEFAULT",
            commit_hash=self.commit_hash,
        )
        if "FINISHED" in result:
            return {"FINISHED"}
        return {"CANCELLED"}


class COZYSTUDIO_OT_SwitchBranch(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.switch_branch"
    bl_label = "Switch Branch"
    bl_description = "Switch to another branch using CozyStudio restore safeguards"

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
        if not self.branch_name.strip():
            self.report({"WARNING"}, "Please enter a branch name")
            return {"CANCELLED"}
        try:
            state.git_instance.switch_branch(self.branch_name)
            self.report({"INFO"}, f"Switched to {self.branch_name}")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Branch switch failed: {e}")
            traceback.print_exc()
            return {"CANCELLED"}


class COZYSTUDIO_OT_CheckoutBranch(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.checkout_branch"
    bl_label = "Checkout Branch"
    bl_description = "Checkout a branch"

    branch_name: bpy.props.StringProperty(
        name="Branch",
        description="Branch name to checkout",
        default="",
    )

    def execute(self, context):
        result = bpy.ops.cozystudio.switch_branch(
            "EXEC_DEFAULT",
            branch_name=self.branch_name,
        )
        if "FINISHED" in result:
            return {"FINISHED"}
        return {"CANCELLED"}


class COZYSTUDIO_OT_BringInChanges(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.bring_in_changes"
    bl_label = "Bring In Changes"
    bl_description = "Merge another branch or ref into the current CozyStudio state"

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

    def invoke(self, context, event):
        if self.ref_name:
            return self.execute(context)
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "ref_name")
        self.layout.prop(self, "strategy")

    def execute(self, context):
        error = self._require_git()
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        if not self.ref_name.strip():
            self.report({"WARNING"}, "Choose a branch or ref to bring in")
            return {"CANCELLED"}

        result = state.git_instance.merge(self.ref_name, strategy=self.strategy)
        if result.get("errors"):
            self.report({"ERROR"}, result["errors"][0])
            if not result.get("conflicts"):
                return {"CANCELLED"}
        if result.get("conflicts"):
            state.git_instance.refresh_ui_state()
            self.report({"WARNING"}, "Incoming changes need conflict resolution")
            return {"FINISHED"}
        self.report({"INFO"}, f"Brought in changes from {self.ref_name}")
        return {"FINISHED"}


class COZYSTUDIO_OT_ReplayMyWork(_CozyOperatorMixin, bpy.types.Operator):
    bl_idname = "cozystudio.replay_my_work"
    bl_label = "Replay My Work"
    bl_description = "Rebase the current branch onto another ref using CozyStudio restore safeguards"

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

    def invoke(self, context, event):
        if self.ref_name:
            return self.execute(context)
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "ref_name")
        self.layout.prop(self, "strategy")

    def execute(self, context):
        error = self._require_git()
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        if not self.ref_name.strip():
            self.report({"WARNING"}, "Choose a branch or ref to replay onto")
            return {"CANCELLED"}

        result = state.git_instance.rebase(self.ref_name, strategy=self.strategy)
        if result.get("errors"):
            self.report({"ERROR"}, result["errors"][0])
            if not result.get("conflicts"):
                return {"CANCELLED"}
        if result.get("conflicts"):
            state.git_instance.refresh_ui_state()
            self.report({"WARNING"}, "Replay stopped for conflict resolution")
            return {"FINISHED"}
        self.report({"INFO"}, f"Replayed work onto {self.ref_name}")
        return {"FINISHED"}


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
        conflicts = manifest.get("conflicts")
        if not conflicts:
            self.report({"WARNING"}, "No conflicts to resolve")
            return {"CANCELLED"}

        if self.conflict_uuid:
            if isinstance(conflicts, dict) and self.conflict_uuid in conflicts:
                del conflicts[self.conflict_uuid]
                if not conflicts:
                    del manifest["conflicts"]
                else:
                    manifest["conflicts"] = conflicts
            else:
                self.report({"WARNING"}, "Conflict entry was not found")
                return {"CANCELLED"}
        else:
            del manifest["conflicts"]

        manifest.write()
        self._refresh_and_validate()
        self.report({"INFO"}, "Conflict marker cleared")
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
