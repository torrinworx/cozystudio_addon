import os
import sys
import subprocess
from pathlib import Path


def load_env(env_path: Path):
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main():
    addon_root = Path(__file__).parent.resolve()
    load_env(addon_root / ".env")

    blender_bin = os.environ.get(
        "COZYSTUDIO_BLENDER_BIN",
        "/home/torrin/blender-4.5.3-linux-x64/blender",
    )
    test_dir = os.environ.get(
        "COZYSTUDIO_TEST_DIR",
        "/tmp/cozystudio_addon_tests",
    )

    blender_path = Path(blender_bin)
    if not blender_path.exists():
        print(f"Blender binary not found at {blender_path}")
        print("Set COZYSTUDIO_BLENDER_BIN in cozystudio_addon/.env")
        sys.exit(1)

    runner = addon_root / "tests" / "runner.py"
    if not runner.exists():
        print(f"Test runner not found at {runner}")
        sys.exit(1)

    cmd = [
        str(blender_path),
        "--background",
        "--python",
        str(runner),
        "--",
        str(test_dir),
    ]

    print("Running Blender tests:")
    print(" ".join(cmd))
    result = subprocess.call(cmd, cwd=str(addon_root))
    sys.exit(result)


if __name__ == "__main__":
    main()
