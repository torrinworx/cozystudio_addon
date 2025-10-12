import json
from pathlib import Path


class WriteList(list):
    """
    A persistent list that automatically syncs changes to a JSON file.
    Loads existing JSON data if the file exists, or initializes new data otherwise.
    """

    def __init__(self, path, data=None):
        self.path = Path(path)

        if self.path.exists():
            if data is not None:
                raise FileExistsError(
                    f"JSON file '{self.path}' already exists. "
                    "Initial data should not be provided."
                )
            with open(self.path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            if not isinstance(existing_data, list):
                raise ValueError(f"JSON file '{self.path}' does not contain a list.")
            super().__init__(existing_data)
        else:
            super().__init__(data or [])
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._write_to_file()

    def _write_to_file(self):
        """Write current list state to JSON file."""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self, f, ensure_ascii=False, indent=2)

    # --- list modification overrides ---
    def append(self, item):
        super().append(item)
        self._write_to_file()

    def extend(self, iterable):
        super().extend(iterable)
        self._write_to_file()

    def insert(self, index, item):
        super().insert(index, item)
        self._write_to_file()

    def remove(self, item):
        super().remove(item)
        self._write_to_file()

    def pop(self, index=-1):
        result = super().pop(index)
        self._write_to_file()
        return result

    def clear(self):
        super().clear()
        self._write_to_file()

    def sort(self, *args, **kwargs):
        super().sort(*args, **kwargs)
        self._write_to_file()

    def reverse(self):
        super().reverse()
        self._write_to_file()

    def __setitem__(self, index, value):
        super().__setitem__(index, value)
        self._write_to_file()

    def __delitem__(self, index):
        super().__delitem__(index)
        self._write_to_file()

    def __iadd__(self, other):
        result = super().__iadd__(other)
        self._write_to_file()
        return result
