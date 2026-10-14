"""Launch the active local catalog without changing the global PATH."""
import json
from pathlib import Path
import re
import stat
import subprocess
import sys


def main():
    manager = Path(__file__).resolve().parent
    pointer = manager / ".imageindexer-active.json"
    if pointer.is_symlink():
        raise ValueError("Active-version pointer must be an ordinary file")
    target = Path(json.loads(pointer.read_text(encoding="utf-8"))["active"]) if pointer.exists() else manager
    if not target.is_absolute():
        raise ValueError("Invalid active-version path")
    for path in (target, *target.parents):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Active installation must not contain links or junctions")
    receipt = json.loads((target / ".imageindexer-install.json").read_text(encoding="utf-8"))
    commit = receipt.get("commit", "")
    if (receipt.get("repository") != "Darth-Carrotpie/ImageIndexer"
            or not re.fullmatch(r"[0-9a-f]{40}", commit)
            or target != manager and (target.parent != manager.parent or target.name != manager.name + "-" + commit[:12])):
        raise ValueError("Active installation is outside the managed versions")
    manifest = json.loads((target / "catalog/distribution.json").read_text(encoding="utf-8"))
    if not re.fullmatch(r"release/iip-r[0-9]+", manifest["release_path"]):
        raise ValueError("Invalid active release path")
    release = target / "catalog" / manifest["release_path"]
    subprocess.run([sys.executable, "-B", str(release / "iconctl.py"), "--package", str(release),
                    *sys.argv[1:]], check=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        sys.exit("ImageIndexer launch stopped: " + str(exc))
