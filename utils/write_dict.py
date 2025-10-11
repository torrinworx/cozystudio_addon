import json
from pathlib import Path

class WriteDict(dict):
    """
    A dictionary wrapper that mirrors changes (writes) to a JSON file automatically on each update.
    - Loads existing JSON file data if available.
    - Writes only when updates occur (not when reading).
    - Raises an error if both initial data is provided and data already exists at given path.
    
    Example:
    ```python
    # Creating a new synced dict
    somedict = WriteDict('./cozystudio.json', {'name': 'Tom', 'age': '32'})
    somedict.update({'email': 'tom@yahoo.com'}) # written to file

    print(somedict['email'])  # prints: tom@yahoo.com

    # Re-opening the same dict later
    somedict2 = WriteDict('./cozystudio.json')
    print(somedict2['email'])  # prints: tom@yahoo.com
    ```
    
    a mini db.
    """

    def __init__(self, path, data=None):
        self.path = Path(path)
        
        # JSON file already exists
        if self.path.exists():
            # Load existing data from file
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # if file exists and data is also provided, raise exception
            if data:
                raise FileExistsError(
                    f"JSON file '{self.path}' already exists. "
                    "Initial data should not be provided."
                )

            super().__init__(data)
        
        # File doesn’t exist, initialize with provided data or empty dict
        else:
            super().__init__(data or {})
            # Ensure directory exists before writing
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._write_to_file()

    def _write_to_file(self):
        """Write current dictionary state to JSON file"""
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self, f, ensure_ascii=False, indent=2)

    # Override modifying dict operations to automatically write changes

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
