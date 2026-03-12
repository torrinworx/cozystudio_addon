import json
import os
import traceback

from .json_io import default_json_decoder, serialize_json_data


class BlocksMixin:
    def _delete_block_file(self, cozystudio_uuid):
        try:
            block_file = self.blockspath / f"{cozystudio_uuid}.json"
            if not block_file.exists():
                print(f"[BpyGit] Block file not found: {block_file}")
                return False
            block_file.unlink()
            print(f"[BpyGit] Deleted block file: {block_file}")
            return True
        except Exception as e:
            print(f"[BpyGit] Error deleting block file '{cozystudio_uuid}': {e}")
            print(traceback.format_exc())
            return False

    def _write_block_file(self, cozystudio_uuid, block_str):
        block_path = os.path.join(self.blockspath, f"{cozystudio_uuid}.json")
        try:
            with open(block_path, "w") as f:
                f.write(block_str)
        except Exception:
            print(traceback.format_exc())
            print(block_str)

    def _read(self, cozystudio_uuid):
        block_path = self.blockspath / f"{cozystudio_uuid}.json"
        if not block_path.exists():
            raise FileNotFoundError(f"Data file not found: {block_path}")

        with open(block_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            data = default_json_decoder(data)
        return data

    def _load_block_data(self, ref, uuid):
        if ref == "WORKING_TREE":
            block_path = self.blockspath / f"{uuid}.json"
            if not block_path.exists():
                return None
            with open(block_path, "r", encoding="utf-8") as handle:
                return default_json_decoder(json.load(handle))

        if not ref:
            return None

        block_rel = os.path.join(".cozystudio", "blocks", f"{uuid}.json")
        try:
            raw = self.repo.git.show(f"{ref}:{block_rel}")
            return default_json_decoder(json.loads(raw))
        except Exception:
            return None

    def _write_merged_blocks(self, merged_blocks):
        existing = {
            path.stem
            for path in self.blockspath.iterdir()
            if path.is_file() and path.name.endswith(".json")
        }

        for uuid in existing:
            if uuid not in merged_blocks:
                self._delete_block_file(uuid)

        for uuid, data in merged_blocks.items():
            serialized = serialize_json_data(data)
            self._write_block_file(uuid, serialized)
