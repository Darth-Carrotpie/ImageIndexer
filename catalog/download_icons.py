"""Restore a pinned icon release from private Nextcloud image ZIPs (stdlib only)."""
import argparse
import base64
import getpass
import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile

sys.dont_write_bytecode = True
CHUNK = 1024 * 1024


def digest(path):
    with path.open("rb") as stream:
        return "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest()


def safe_path(root, name):
    if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_./-]+", name)
            or any(p in ("", ".", "..") or p.endswith(".") for p in name.split("/"))):
        raise ValueError("Unsafe package path")
    target = root
    for component in [None, *name.split("/")]:
        if component is not None:
            target = target / component
        try:
            info = target.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Links/junctions are not allowed in installation paths")
    return target


def valid_record(record):
    if (type(record.get("size")) is not int or record["size"] < 0
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", record.get("sha256", ""))):
        raise ValueError("Invalid size/hash in manifest")


def matches(path, record):
    return path.is_file() and path.stat().st_size == record["size"] and digest(path) == record["sha256"]


def is_image(name):
    return name.startswith(("assets/", "thumbnails/")) and name.endswith(".png")


def load_plan(root):
    plan = json.loads(safe_path(root, "distribution.json").read_text(encoding="utf-8"))
    if plan["schema_version"] != 1:
        raise ValueError("Unsupported distribution schema")
    release = safe_path(root, plan["release_path"])
    manifest = safe_path(release, "manifests/release.json")
    if digest(manifest) != plan["release_manifest_sha256"]:
        raise ValueError("Original release manifest hash mismatch")
    payload = json.loads(manifest.read_text(encoding="utf-8"))["payload"]
    records = {}
    for record in payload:
        valid_record(record)
        path = safe_path(release, record["path"])
        if record["path"] in records:
            raise ValueError("Duplicate payload path")
        records[record["path"]] = record
        if not is_image(record["path"]) and not matches(path, record):
            raise ValueError("Bootstrap payload changed: " + record["path"])
    names, covered = set(), []
    for part in plan["parts"]:
        valid_record(part)
        if not re.fullmatch(r"IndexedIconPack-iip-r[0-9]+-images-[0-9]{3}\.zip", part["filename"]):
            raise ValueError("Invalid image archive filename")
        if part["filename"] in names or not part["paths"]:
            raise ValueError("Duplicate or empty image archive")
        names.add(part["filename"])
        covered.extend(part["paths"])
    if len(covered) != len(set(covered)) or set(covered) != {p for p in records if is_image(p)}:
        raise ValueError("Image archive inventory does not exactly cover the release")
    return plan, release, records


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        fp.close()
        raise ValueError("HTTP redirect refused; configure the canonical HTTPS WebDAV endpoint")


def share_config(url, token=""):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or any(ord(c) <= 32 for c in url)):
        raise ValueError("Use an HTTPS share or WebDAV URL without credentials, query or fragment")
    path = parsed.path.rstrip("/")
    share = re.fullmatch(r"(.*?)/(?:index\.php/)?s/([A-Za-z0-9_-]+)", path)
    modern = re.fullmatch(r"(.*?)/public\.php/dav/files/([A-Za-z0-9_-]+)", path)
    if share:
        prefix, token = share.groups()
        base = f"{parsed.scheme}://{parsed.netloc}{prefix}/public.php/dav/files/{token}/"
    elif modern:
        token = modern[2]
        base = url.rstrip("/") + "/"
    elif path.endswith("/public.php/webdav") and re.fullmatch(r"[A-Za-z0-9_-]+", token):
        base = url.rstrip("/") + "/"
    else:
        raise ValueError("Use the folder share link, /public.php/dav/files/TOKEN/, or legacy /public.php/webdav/")
    return {"webdav_base_url": base, "share_token": token, "password_env": "IIP_NEXTCLOUD_PASSWORD"}


def configure(config_path):
    if not sys.stdin.isatty():
        raise ValueError("Nextcloud setup needs an interactive terminal")
    # Check before prompting or replacing: never follow a link to another file.
    safe_path(config_path.parent, config_path.name)
    if config_path.exists() and input("Replace saved Nextcloud configuration? [y/N]: ").strip().lower() != "y":
        return
    while True:
        url = input("Nextcloud folder share link (or full public WebDAV URL): ").strip()
        token = input("Legacy share token: ").strip() if url.rstrip("/").endswith("/public.php/webdav") else ""
        try:
            config = share_config(url, token)
            break
        except ValueError as exc:
            print(str(exc))
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         prefix=".nextcloud-", dir=config_path.parent, delete=False) as output:
            temporary = Path(output.name)
            json.dump(config, output, indent=2)
            output.write("\n")
        os.replace(temporary, config_path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print("Saved private configuration; the password is never written to disk.")


def credentials(config_path):
    if not config_path.exists():
        configure(config_path)
    safe_path(config_path.parent, config_path.name)
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    base = config.get("webdav_base_url", "")
    parsed = urlsplit(base)
    token = config.get("share_token", "")
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or any(ord(c) <= 32 for c in base) or not re.fullmatch(r"[A-Za-z0-9_-]+", token)):
        raise ValueError("Fill nextcloud.json with the HTTPS folder WebDAV URL and share token")
    password = os.environ.get(config.get("password_env", "IIP_NEXTCLOUD_PASSWORD"))
    if password is None:
        if not sys.stdin.isatty():
            raise ValueError("No password environment variable set; use an interactive terminal for the hidden prompt")
        password = getpass.getpass("Nextcloud share password: ")
    if not password:
        raise ValueError("A share password is required")
    username = "anonymous" if "/public.php/dav/files/" in parsed.path else token
    authorization = "Basic " + base64.b64encode((username + ":" + password).encode("utf-8")).decode("ascii")
    return base.rstrip("/") + "/", authorization


def publish(source, target):
    # ponytail: atomic no-overwrite needs hard links; use NTFS/ext4/APFS, not FAT.
    os.link(source, target)
    source.unlink()


def download(part, cache, url, authorization):
    target = safe_path(cache, part["filename"])
    partial = safe_path(cache, part["filename"] + ".part")
    if target.exists():
        if not matches(target, part):
            raise ValueError("Corrupt cached archive; remove only " + str(target))
        return target
    start = partial.stat().st_size if partial.exists() else 0
    if start > part["size"]:
        raise ValueError("Oversized partial download; remove only " + str(partial))
    if start < part["size"]:
        headers = {"Authorization": authorization, "Accept-Encoding": "identity",
                   "X-Requested-With": "XMLHttpRequest", "User-Agent": "IndexedIconPack/1"}
        if start:
            headers["Range"] = f"bytes={start}-"
        request = Request(url, headers=headers)
        try:
            with build_opener(NoRedirect()).open(request, timeout=60) as response:
                if response.status == 200:
                    start = 0  # A server without Range support safely restarts our partial file.
                elif response.status != 206 or response.headers.get("Content-Range") != (
                        f"bytes {start}-{part['size'] - 1}/{part['size']}"):
                    raise ValueError("Unexpected HTTP status/range; partial download preserved")
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise ValueError("Unexpected HTTP content encoding")
                length = response.headers.get("Content-Length")
                if length is not None and int(length) != part["size"] - start:
                    raise ValueError("Unexpected download size (check share access and URL)")
                with partial.open("ab" if start else "wb") as output:
                    received = start
                    while chunk := response.read(min(CHUNK, part["size"] - received + 1)):
                        received += len(chunk)
                        if received > part["size"]:
                            raise ValueError("Download exceeds pinned archive size")
                        output.write(chunk)
        except HTTPError as exc:
            code = exc.code
            exc.close()
            raise ValueError(f"HTTP {code}; check share password, expiry and WebDAV endpoint") from None
        except (URLError, OSError, HTTPException):
            raise ValueError("Download interrupted; retry to resume " + partial.name) from None
    if not matches(partial, part):
        if partial.stat().st_size < part["size"]:
            raise ValueError("Incomplete download; retry to resume " + partial.name)
        raise ValueError("Archive SHA-256 mismatch; remove only " + str(partial))
    publish(partial, target)
    return target


def extract(archive, part, release, records, scratch):
    if not matches(archive, part):
        raise ValueError("Archive hash/size mismatch: " + archive.name)
    with zipfile.ZipFile(archive) as zipped:
        entries = zipped.infolist()
        if len(entries) != len(part["paths"]) or {i.filename for i in entries} != set(part["paths"]):
            raise ValueError("ZIP inventory differs from pinned part")
        # Check every member before writing any; never use extractall on network content.
        for entry in entries:
            safe_path(release, entry.filename)
            mode = entry.external_attr >> 16
            if (entry.is_dir() or stat.S_IFMT(mode) not in (0, stat.S_IFREG)
                    or entry.file_size != records[entry.filename]["size"]
                    or entry.compress_type != zipfile.ZIP_STORED or entry.flag_bits & 1):
                raise ValueError("Unsafe or unexpected ZIP member")
        for entry in entries:
            target = safe_path(release, entry.filename)
            record = records[entry.filename]
            if target.exists():
                if not matches(target, record):
                    raise ValueError("Refusing to overwrite conflicting file: " + entry.filename)
                continue
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(prefix=".icon-extract-", dir=scratch, delete=False) as output:
                    temporary = Path(output.name)
                    with zipped.open(entry) as source:
                        shutil.copyfileobj(source, output, CHUNK)
                if not matches(temporary, record):
                    raise ValueError("Extracted file hash mismatch: " + entry.filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                safe_path(release, entry.filename)
                publish(temporary, target)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)


def install(root, config_path, cache, offline=False):
    plan, release, records = load_plan(root)
    if cache.resolve().is_relative_to(release.resolve()):
        raise ValueError("Archive cache must be outside the immutable release")
    missing = set()
    for name, record in records.items():
        if not is_image(name):
            continue
        target = safe_path(release, name)
        if target.exists() and not matches(target, record):
            raise ValueError("Refusing to overwrite conflicting file: " + name)
        if not target.exists():
            missing.add(name)
    auth = None
    for part in plan["parts"]:
        if missing.isdisjoint(part["paths"]):
            continue
        archive = safe_path(cache, part["filename"])
        if not archive.exists():
            if offline:
                raise ValueError("Offline archive missing: " + str(archive))
            if auth is None:
                auth = credentials(config_path)
            cache.mkdir(parents=True, exist_ok=True)
            print("Downloading " + part["filename"], flush=True)
            archive = download(part, cache, auth[0] + quote(part["filename"]), auth[1])
        print("Verifying/extracting " + part["filename"], flush=True)
        extract(archive, part, release, records, root)
    print("Deep-verifying restored release...", flush=True)
    subprocess.run([sys.executable, "-B", str(release / "tools/validate_catalog.py"),
                    "--package", str(release), "--json"], check=True)
    print("Installation verified: " + plan["release_path"], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="default: nextcloud.json beside this script")
    parser.add_argument("--archives-dir", type=Path, help="default: download-cache beside this script")
    parser.add_argument("--offline", action="store_true", help="use existing ZIPs only; no password/network")
    parser.add_argument("--configure", action="store_true", help="interactively create or replace private share configuration")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    lock = safe_path(root, ".download.lock")
    try:
        with lock.open("x", encoding="utf-8") as stream:
            stream.write(str(os.getpid()))
    except FileExistsError:
        parser.exit(1, "Another install is running, or .download.lock is stale; see README.md.\n")
    try:
        if args.configure:
            configure(args.config or root / "nextcloud.json")
        install(root, args.config or root / "nextcloud.json",
                args.archives_dir.absolute() if args.archives_dir else root / "download-cache", args.offline)
    except (ValueError, OSError, KeyError, TypeError, EOFError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        parser.exit(1, "Installation stopped: " + str(exc) + "\n")
    except KeyboardInterrupt:
        parser.exit(130, "Installation interrupted; rerun to resume.\n")
    finally:
        lock.unlink()


if __name__ == "__main__":
    main()
