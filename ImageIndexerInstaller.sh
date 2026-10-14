#!/usr/bin/env bash
# Run in Bash (Linux, macOS, WSL or Git Bash); no Git checkout is required.
set -euo pipefail

if [[ $# != 1 || $1 == --help || $1 == -h ]]; then
    printf 'Usage: bash ImageIndexerInstaller.sh INSTALL_DIRECTORY\nRequires Bash, Python 3.11+ (or uv), HTTPS access and an interactive terminal.\n'
    [[ $# == 1 && ( $1 == --help || $1 == -h ) ]] && exit 0
    exit 2
fi

probe='import sys, sqlite3; assert sys.version_info >= (3,11); sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE probe USING fts5(text)")'
runtime=()
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "$probe" >/dev/null 2>&1; then
        runtime=("$candidate")
        break
    fi
done
if [[ ${#runtime[@]} == 0 ]] && command -v py >/dev/null 2>&1 && py -3 -c "$probe" >/dev/null 2>&1; then
    runtime=(py -3)
fi
if [[ ${#runtime[@]} == 0 ]] && command -v uv >/dev/null 2>&1; then
    printf 'Using uv to select Python 3.11+ (it may download a managed runtime).\n'
    runtime=(uv run --no-project --python '>=3.11' python)
    "${runtime[@]}" -c "$probe"
fi
if [[ ${#runtime[@]} == 0 ]]; then
    printf 'Install Python 3.11+ with SQLite FTS5, or uv, then rerun. No system packages were changed.\n' >&2
    exit 1
fi
destination=$1
if command -v cygpath >/dev/null 2>&1; then
    destination=$(cygpath -w "$destination")
fi

# Keep bootstrap logic here so curl needs to fetch only this entry point.
"${runtime[@]}" -B - "$destination" <<'IMAGEINDEXER_PY'
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile

REPOSITORY = "Darth-Carrotpie/ImageIndexer"
RECEIPT = ".imageindexer-install.json"
LIMIT = 300 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        fp.close()
        raise ValueError("Unexpected GitHub redirect; no download was executed")


def fetch(url, output, limit):
    request = Request(url, headers={"User-Agent": "ImageIndexerInstaller/1", "Accept-Encoding": "identity"})
    with build_opener(NoRedirect()).open(request, timeout=60) as response:
        size = 0
        while chunk := response.read(min(1024 * 1024, limit - size + 1)):
            size += len(chunk)
            if size > limit:
                raise ValueError("GitHub response exceeds installer size limit")
            output.write(chunk)


def no_links(path):
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Install paths must not contain symlinks or junctions")


def unpack(archive, destination, commit):
    prefix = "ImageIndexer-" + commit + "/"
    with zipfile.ZipFile(archive) as zipped:
        entries = zipped.infolist()
        if len(entries) > 5000 or sum(e.file_size for e in entries) > LIMIT:
            raise ValueError("Source archive exceeds installer size limit")
        names = set()
        # Validate the whole inventory before writing any archive member.
        for entry in entries:
            if entry.orig_filename != entry.filename:
                raise ValueError("Source archive path was normalized; refusing ambiguous names")
            if not entry.filename.startswith(prefix):
                raise ValueError("Unexpected source archive root")
            name = entry.filename[len(prefix):].rstrip("/")
            if not name and entry.is_dir():
                continue
            parts = name.split("/")
            if (not re.fullmatch(r"[A-Za-z0-9_./-]+", name)
                    or any(p.lower() in ("", ".", "..", ".git") or p.endswith(".")
                           or re.fullmatch(r"(?i)(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\..*)?", p) for p in parts)
                    or name.casefold() in names or entry.flag_bits & 1
                    or stat.S_IFMT(entry.external_attr >> 16) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                raise ValueError("Unsafe or duplicate source archive path")
            names.add(name.casefold())
        for entry in entries:
            name = entry.filename[len(prefix):].rstrip("/")
            if not name or entry.is_dir():
                continue
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(entry) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output, 1024 * 1024)


def run(root, *arguments):
    subprocess.run([sys.executable, "-B", *map(str, arguments)], cwd=root, stdin=sys.stdin, check=True)


def bootstrap(root):
    receipt = root / RECEIPT
    if receipt.exists():
        no_links(receipt)
        saved = json.loads(receipt.read_text(encoding="utf-8"))
        if saved.get("repository") != REPOSITORY or not re.fullmatch(r"[0-9a-f]{40}", saved.get("commit", "")):
            raise ValueError("Unrecognized install receipt; use a new directory")
        print("Resuming existing snapshot " + saved["commit"], flush=True)
    else:
        if any(p.name != ".installer.lock" for p in root.iterdir()):
            raise ValueError("Destination is not empty and is not an installer-owned snapshot; use a new directory")
        print("Downloading the public source and catalog (no Git required)...", flush=True)
        with tempfile.TemporaryDirectory(prefix=".installer-", dir=root) as scratch:
            scratch = Path(scratch)
            metadata = scratch / "commit.json"
            with metadata.open("xb") as stream:
                fetch(f"https://api.github.com/repos/{REPOSITORY}/git/ref/heads/main", stream, 1024 * 1024)
            commit = json.loads(metadata.read_text(encoding="utf-8"))["object"]["sha"]
            if not re.fullmatch(r"[0-9a-f]{40}", commit):
                raise ValueError("Invalid GitHub commit identity")
            archive = scratch / "source.zip"
            with archive.open("xb") as stream:
                fetch(f"https://codeload.github.com/{REPOSITORY}/zip/{commit}", stream, LIMIT)
            source = scratch / "source"
            source.mkdir()
            unpack(archive, source, commit)
            run(source, source / "tools/prepare_public_catalog.py", "check")
            # A crash while publishing leaves an unowned partial directory; never overwrite it.
            for child in source.iterdir():
                target = root / child.name
                if target.exists():
                    raise ValueError("Destination changed during installation")
                child.rename(target)
            with archive.open("rb") as stream:
                archive_hash = hashlib.file_digest(stream, "sha256").hexdigest()
            with receipt.open("x", encoding="utf-8") as stream:
                json.dump({"repository": REPOSITORY, "commit": commit, "source_archive_sha256": archive_hash}, stream)
    # Also recheck an existing installation; this never requires private pixels.
    for path in root.rglob("*"):
        no_links(path)
    run(root, root / "tools/prepare_public_catalog.py", "check")


def install(root):
    root = Path(os.path.abspath(root.expanduser()))
    no_links(root)
    if root == Path(root.anchor):
        raise ValueError("Choose a dedicated install directory, not a filesystem root")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = root / ".installer.lock"
    try:
        lock.touch(exist_ok=False)
    except FileExistsError:
        raise ValueError("Installer lock exists; confirm no installer is running before removing .installer.lock") from None
    try:
        bootstrap(root)
        print("Public catalog ready. Image access requires your own asset license.", flush=True)
        print("Allow at least 8 GB for images and cached ZIPs; use a hard-link-capable filesystem.", flush=True)
        if input("Download/verify private images now? [Y/n]: ").strip().lower() not in ("n", "no"):
            print("The downloader will ask for the share link and hidden password only when needed.", flush=True)
            run(root, root / "catalog/download_icons.py")
        else:
            print("Metadata-only installation; images have NOT been verified.", flush=True)
        plan = json.loads((root / "catalog/distribution.json").read_text(encoding="utf-8"))
        release = root / "catalog" / plan["release_path"]
        print("\nInstalled at: " + str(root))
        print("Open the local browser with:\n" + shlex.join([
            sys.executable.replace("\\", "/"), "-B", str(release / "iconctl.py").replace("\\", "/"),
            "--package", str(release).replace("\\", "/"), "serve"]))
        print("Rerun the installer with the same path to resume; use a new path for a newer snapshot.")
    finally:
        lock.unlink()


if __name__ == "__main__":
    try:
        # Script bytes arrive on stdin, including for curl | bash; prompts need the terminal.
        sys.stdin = open("CONIN$" if os.name == "nt" else "/dev/tty", encoding="utf-8")
        install(Path(sys.argv[1]))
    except (OSError, ValueError, KeyError, TypeError, EOFError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        sys.exit("Installation stopped: " + str(exc))
    except KeyboardInterrupt:
        sys.exit("Installation interrupted; rerun with the same destination to resume.")
IMAGEINDEXER_PY
