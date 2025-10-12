import json
from pathlib import Path


class WriteDict(dict):
    """
    A persistent dictionary that automatically syncs changes to a JSON file.
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
            if not isinstance(existing_data, dict):
                raise ValueError(f"JSON file '{self.path}' does not contain a dictionary.")
            super().__init__(existing_data)
        else:
            super().__init__(data or {})
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._write_to_file()

    def _write_to_file(self):
        """Write current dictionary state to JSON file."""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self, f, ensure_ascii=False, indent=2)

    # --- dict modification overrides ---
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._write_to_file()

    def __delitem__(self, key):
        super().__delitem__(key)
        self._write_to_file()

    def clear(self):
        super().clear()
        self._write_to_file()

    def pop(self, key, default=None):
        result = super().pop(key, default)
        self._write_to_file()
        return result

    def popitem(self):
        result = super().popitem()
        self._write_to_file()
        return result

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._write_to_file()

    def setdefault(self, key, default=None):
        result = super().setdefault(key, default)
        self._write_to_file()
        return result
