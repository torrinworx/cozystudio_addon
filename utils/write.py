import json
from pathlib import Path


class WriteBase:
    """
    Base class for JSON/LJSON persistent containers.
    Handles file I/O, path management, and autowrite behavior.
    Subclasses may override _write_to_file and _load_file for custom formats.
    """

    def __init__(self, path, autowrite=False):
        self.path = Path(path)
        self.autowrite = autowrite
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # --- Default I/O methods ---
    def _write_to_file(self):
        """Write the current container state to a JSON file (regular JSON array or dict)."""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self, f, ensure_ascii=False, indent=2)

    def _load_file(self):
        """Load and return JSON data from file; returns None if not found."""
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    # --- Public and helpers ---
    def write(self):
        """For manual persistence."""
        self._write_to_file()

    def _maybe_write(self):
        """Write only if autowrite is enabled."""
        if self.autowrite:
            self._write_to_file()


class WriteDict(WriteBase, dict):
    """A persistent dictionary synced to a standard JSON file."""

    def __init__(self, path, data=None, autowrite=False):
        WriteBase.__init__(self, path, autowrite)
        existing_data = self._load_file()

        if existing_data is not None:
            if data is not None:
                raise FileExistsError(
                    f"File '{self.path}' already exists. Initial data should not be provided."
                )
            if not isinstance(existing_data, dict):
                raise ValueError(
                    f"JSON file '{self.path}' does not contain a dictionary."
                )
            dict.__init__(self, existing_data)
        else:
            dict.__init__(self, data or {})
            self._write_to_file()

    # --- dict modification overrides ---
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._maybe_write()

    def __delitem__(self, key):
        super().__delitem__(key)
        self._maybe_write()

    def clear(self):
        super().clear()
        self._maybe_write()

    def pop(self, key, default=None):
        result = super().pop(key, default)
        self._maybe_write()
        return result

    def popitem(self):
        result = super().popitem()
        self._maybe_write()
        return result

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._maybe_write()

    def setdefault(self, key, default=None):
        result = super().setdefault(key, default)
        self._maybe_write()
        return result


class WriteList(WriteBase, list):
    """
    A persistent list stored as a line-delimited JSON (LJSON) file.
    Each list element is serialized on its own line.
    """

    def __init__(self, path, data=None, autowrite=False):
        # Force .ljson extension if not present
        self.path = Path(path)
        if self.path.suffix.lower() != ".ljson":
            self.path = self.path.with_suffix(".ljson")

        WriteBase.__init__(self, self.path, autowrite)

        existing_data = self._load_file()
        if existing_data is not None:
            if data is not None:
                raise FileExistsError(
                    f"LJSON file '{self.path}' already exists. Initial data should not be provided."
                )
            if not isinstance(existing_data, list):
                raise ValueError(f"LJSON file '{self.path}' does not contain a list.")
            list.__init__(self, existing_data)
        else:
            list.__init__(self, data or [])
            self._write_to_file()

    # --- LJSON-specific I/O overrides ---
    def _write_to_file(self):
        with open(self.path, "w", encoding="utf-8") as f:
            for entry in self:
                json_line = json.dumps(entry, ensure_ascii=False)
                f.write(json_line + "\n")

    def _load_file(self):
        if not self.path.exists():
            return None
        with open(self.path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    # --- list modification overrides ---
    def append(self, item):
        super().append(item)
        self._maybe_write()

    def extend(self, iterable):
        super().extend(iterable)
        self._maybe_write()

    def insert(self, index, item):
        super().insert(index, item)
        self._maybe_write()

    def remove(self, item):
        super().remove(item)
        self._maybe_write()

    def pop(self, index=-1):
        result = super().pop(index)
        self._maybe_write()
        return result

    def clear(self):
        super().clear()
        self._maybe_write()

    def sort(self, *args, **kwargs):
        super().sort(*args, **kwargs)
        self._maybe_write()

    def reverse(self):
        super().reverse()
        self._maybe_write()
