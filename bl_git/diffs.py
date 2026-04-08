from fnmatch import fnmatch

from ..branding import UI_REFRESH_PANEL_IDS
from ..utils.redraw import redraw, redraw_many
from .paths import CANONICAL_MANIFEST_REL


class DiffsMixin:
    def _filter_changes(self, changes):
        IGNORE_PATTERNS = [
            "*.blend",
            # Blender(by default) allows up to 32 incremental versions
            "*.blend[0-9]",
            "*.blend[0-9][0-9]", 
            CANONICAL_MANIFEST_REL,
        ]

        if not changes:
            return []

        filtered = []
        for path in changes:
            if any(fnmatch(path, pattern) for pattern in IGNORE_PATTERNS):
                continue
            filtered.append(path)
        return filtered

    def _update_diffs(self):
        repo = self.repo
        if not repo:
            self.refresh_ui_state()
            return

        diffs_list = []
        empty_tree_sha = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        change_type_map = {
            "A": "added",
            "M": "modified",
            "D": "deleted",
            "R": "renamed",
            "C": "copied",
            "T": "typechange",
        }

        working_diffs = repo.index.diff(None)
        for diff in working_diffs:
            change = diff.change_type
            status = change_type_map.get(change, "modified")
            diffs_list.append(
                {
                    "path": diff.b_path or diff.a_path,
                    "status": status,
                }
            )

        for path in repo.untracked_files:
            diffs_list.append({"path": path, "status": "untracked"})

        if repo.head.is_valid():
            staged_diffs = repo.index.diff(repo.head.commit)
            for diff in staged_diffs:
                change = diff.change_type
                status = change_type_map.get(change, "modified")
                status = f"staged_{status}"
                diffs_list.append(
                    {
                        "path": diff.b_path or diff.a_path,
                        "status": status,
                    }
                )
        else:
            staged_diffs = repo.index.diff(empty_tree_sha)
            for diff in staged_diffs:
                diffs_list.append(
                    {
                        "path": diff.b_path or diff.a_path,
                        "status": "staged_added",
                    }
                )

        staged_paths = {
            d["path"] for d in diffs_list if d["status"].startswith("staged")
        }
        unique_diffs = []
        for d in diffs_list:
            if d["path"] in staged_paths and d["status"] in (
                "added",
                "modified",
                "deleted",
            ):
                continue
            unique_diffs.append(d)

        filtered_paths = set(self._filter_changes(d["path"] for d in unique_diffs))
        final_diffs = [d for d in unique_diffs if d["path"] in filtered_paths]

        if self.diffs != final_diffs:
            self.diffs = final_diffs
            redraw_many(*UI_REFRESH_PANEL_IDS[:1], UI_REFRESH_PANEL_IDS[2])

        self.refresh_ui_state()
