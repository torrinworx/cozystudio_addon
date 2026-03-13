import bpy


class COZYSTUDIO_UL_CommitList(bpy.types.UIList):
    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        filter_text = (self.filter_name or "").strip().lower()

        flt_flags = [self.bitflag_filter_item] * len(items)
        if filter_text:
            for idx, item in enumerate(items):
                haystack = f"{item.commit_hash} {item.summary}".lower()
                if filter_text not in haystack:
                    flt_flags[idx] = 0

        if self.use_filter_invert:
            flt_flags = [
                0 if flag == self.bitflag_filter_item else self.bitflag_filter_item
                for flag in flt_flags
            ]

        flt_neworder = []
        if self.use_filter_sort_alpha:
            flt_neworder = sorted(
                range(len(items)),
                key=lambda i: (items[i].summary or "").lower(),
            )

        return flt_flags, flt_neworder

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        split = layout.split(factor=0.86, align=True)
        split.label(
            text=f"{item.short_hash}  {item.summary}",
            icon="RADIOBUT_ON" if item.is_head else "BLANK1",
        )
        op = split.operator(
            "cozystudio.checkout_commit", text="", icon="FILE_REFRESH", emboss=True
        )
        op.commit_hash = item.commit_hash
