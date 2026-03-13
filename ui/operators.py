import bpy

from . import state


class INIT_OT_PrintOperator(bpy.types.Operator):
    bl_idname = "cozystudio.init_repo"
    bl_label = "Init"
    bl_description = "Initialize CozyStudio Git repository for this project"

    def execute(self, context):
        if not bpy.data.filepath:
            return {"CANCELLED"}

        state.git_instance.init()
        return {"FINISHED"}


class COMMMIT_OT_PrintOperator(bpy.types.Operator):
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
        layout = self.layout
        layout.prop(self, "message")

    def execute(self, context):
        message = (self.message or "").strip()
        if not message:
            message = (context.window_manager.cozystudio_commit_message or "").strip()

        if not message:
            self.report({"WARNING"}, "Commit message cannot be empty")
            return {"CANCELLED"}

        ok = state.git_instance.commit(message=message)
        if not ok:
            capture_issues = getattr(state.git_instance, "last_capture_issues", None) or []
            if capture_issues and capture_issues[0].get("reason"):
                self.report({"ERROR"}, capture_issues[0]["reason"])
                return {"CANCELLED"}
            report = getattr(state.git_instance, "last_integrity_report", None)
            if report and report.get("errors"):
                self.report({"ERROR"}, report["errors"][0])
            else:
                self.report({"ERROR"}, "Commit failed")
            return {"CANCELLED"}
        if hasattr(context.window_manager, "cozystudio_commit_message"):
            context.window_manager.cozystudio_commit_message = ""
        self.report({"INFO"}, f"Committed: {message}")
        return {"FINISHED"}


class COZYSTUDIO_OT_ManualRefresh(bpy.types.Operator):
    bl_idname = "cozystudio.manual_refresh"
    bl_label = "Refresh"
    bl_description = "Refresh CozyStudio Git state and UI"

    def execute(self, context):
        if not state.git_instance or not getattr(state.git_instance, "initiated", False):
            return {"CANCELLED"}

        state.git_instance.refresh_all()
        capture_issues = getattr(state.git_instance, "last_capture_issues", None) or []
        if capture_issues and capture_issues[0].get("reason"):
            self.report({"WARNING"}, capture_issues[0]["reason"])
        report = state.git_instance.validate_manifest_integrity()
        state.git_instance.last_integrity_report = report
        if not report.get("ok") and report.get("errors"):
            self.report({"ERROR"}, report["errors"][0])
        return {"FINISHED"}


class COZYSTUDIO_OT_AddFile(bpy.types.Operator):
    bl_idname = "cozystudio.add_file"
    bl_label = "Add file to stage"
    bl_description = "Stage a file for commit"

    file_path: bpy.props.StringProperty()

    def execute(self, context):
        state.git_instance.stage(changes=[self.file_path])
        state.git_instance._update_diffs()
        return {"FINISHED"}


class COZYSTUDIO_OT_UnstageFile(bpy.types.Operator):
    bl_idname = "cozystudio.unstage_file"
    bl_label = "Unstage file"
    bl_description = "Remove a file from the staging area"

    file_path: bpy.props.StringProperty()

    def execute(self, context):
        state.git_instance.unstage(changes=[self.file_path])
        state.git_instance._update_diffs()
        return {"FINISHED"}


class COZYSTUDIO_OT_AddGroup(bpy.types.Operator):
    bl_idname = "cozystudio.add_group"
    bl_label = "Add group to stage"
    bl_description = "Stage all files in this group"

    group_id: bpy.props.StringProperty()

    def execute(self, context):
        if not state.git_instance or not getattr(state.git_instance, "state", None):
            return {"CANCELLED"}

        group = (state.git_instance.state.get("groups") or {}).get(self.group_id)
        if not group:
            return {"CANCELLED"}

        members = group.get("members", [])
        paths = [f".cozystudio/blocks/{uuid}.json" for uuid in members]
        state.git_instance.stage(changes=paths)
        state.git_instance._update_diffs()
        return {"FINISHED"}


class COZYSTUDIO_OT_UnstageGroup(bpy.types.Operator):
    bl_idname = "cozystudio.unstage_group"
    bl_label = "Unstage group"
    bl_description = "Unstage all files in this group"

    group_id: bpy.props.StringProperty()

    def execute(self, context):
        if not state.git_instance or not getattr(state.git_instance, "state", None):
            return {"CANCELLED"}

        group = (state.git_instance.state.get("groups") or {}).get(self.group_id)
        if not group:
            return {"CANCELLED"}

        members = group.get("members", [])
        paths = [f".cozystudio/blocks/{uuid}.json" for uuid in members]
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


class COZYSTUDIO_OT_CheckoutCommit(bpy.types.Operator):
    bl_idname = "cozystudio.checkout_commit"
    bl_label = "Checkout Commit"
    bl_description = "Checkout a specific commit hash"

    commit_hash: bpy.props.StringProperty(
        name="Commit Hash",
        description="Enter git commit hash to checkout",
        default="",
    )

    def execute(self, context):
        if not state.git_instance or not getattr(state.git_instance, "initiated", False):
            self.report({"ERROR"}, "No CozyStudio Git repo initialized.")
            return {"CANCELLED"}

        if not self.commit_hash.strip():
            self.report({"WARNING"}, "Please enter a commit hash.")
            return {"CANCELLED"}

        try:
            print(f"[CozyStudio] Checking out commit {self.commit_hash}")
            state.git_instance.checkout(self.commit_hash)
            self.report({"INFO"}, f"Checked out commit {self.commit_hash[:8]}...")
        except Exception as e:
            self.report({"ERROR"}, f"Checkout failed: {e}")
            import traceback

            traceback.print_exc()
            return {"CANCELLED"}

        return {"FINISHED"}


class COZYSTUDIO_OT_CheckoutBranch(bpy.types.Operator):
    bl_idname = "cozystudio.checkout_branch"
    bl_label = "Checkout Branch"
    bl_description = "Checkout a branch"

    branch_name: bpy.props.StringProperty(
        name="Branch",
        description="Branch name to checkout",
        default="",
    )

    def execute(self, context):
        if not state.git_instance or not getattr(state.git_instance, "initiated", False):
            self.report({"ERROR"}, "No CozyStudio Git repo initialized.")
            return {"CANCELLED"}

        if not self.branch_name.strip():
            self.report({"WARNING"}, "Please enter a branch name.")
            return {"CANCELLED"}

        try:
            state.git_instance.repo.git.checkout(self.branch_name)
            self.report({"INFO"}, f"Checked out {self.branch_name}")
        except Exception as e:
            self.report({"ERROR"}, f"Checkout failed: {e}")
            import traceback

            traceback.print_exc()
            return {"CANCELLED"}

        return {"FINISHED"}


class COZYSTUDIO_OT_SelectBlock(bpy.types.Operator):
    bl_idname = "cozystudio.select_block"
    bl_label = "Select datablock"
    bl_description = "Select the Blender datablock tied to this entry"

    uuid: bpy.props.StringProperty()

    def execute(self, context):
        if not state.git_instance or not getattr(state.git_instance, "initiated", False):
            return {"CANCELLED"}

        if not self.uuid:
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
