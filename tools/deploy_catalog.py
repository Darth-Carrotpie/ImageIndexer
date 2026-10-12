"""Select a verified immutable local release without changing its files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path, PurePosixPath
from urllib.request import urlopen

sys.dont_write_bytecode = True
import validate_catalog


HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
RELEASE = re.compile(r"iip-r[0-9]{6,}\Z")


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return "sha256:" + value.hexdigest()


def valid_relative(value: str) -> bool:
    path = PurePosixPath(value)
    return (bool(value) and "\\" not in value and ":" not in value
            and not path.is_absolute() and all(part not in ("", ".", "..") for part in value.split("/")))


def verify_release(root: Path, release_id: str, expected_hash: str) -> dict:
    if not RELEASE.fullmatch(release_id) or not HASH.fullmatch(expected_hash):
        raise ValueError("invalid release ID or expected manifest hash")
    release = root / "releases" / release_id
    resolved = release.resolve(strict=True)
    if resolved != release or not resolved.is_relative_to(root):
        raise ValueError("release must be an ordinary directory inside deployment root")
    manifest_file = release / "manifests" / "release.json"
    if not manifest_file.resolve(strict=True).is_relative_to(release) or manifest_file.is_symlink():
        raise ValueError("release manifest escapes release root")
    manifest_bytes = manifest_file.read_bytes()
    if digest(manifest_bytes) != expected_hash:
        raise ValueError("release manifest differs from approved handoff hash")
    manifest = json.loads(manifest_bytes)
    if (not isinstance(manifest, dict)
            or manifest.get("manifest_schema_version") != 1
            or manifest.get("catalog_id") != "indexed-icon-pack"
            or manifest.get("release_id") != release_id
            or type(manifest.get("schema_version")) is not int
            or manifest.get("schema_version") not in (1, 2)
            or not HASH.fullmatch(str(manifest.get("catalog_revision", "")))
            or not HASH.fullmatch(str(manifest.get("identity_registry_sha256", "")))):
        raise ValueError("incompatible release manifest")
    predecessor_id = manifest.get("predecessor_release_id")
    predecessor_hash = manifest.get("predecessor_release_manifest_sha256")
    if (predecessor_id is None) != (predecessor_hash is None):
        raise ValueError("incomplete predecessor identity")
    if predecessor_id is not None and (not isinstance(predecessor_id, str)
                                    or not isinstance(predecessor_hash, str)
                                    or not RELEASE.fullmatch(predecessor_id)
                                    or not HASH.fullmatch(predecessor_hash)):
        raise ValueError("invalid predecessor identity")
    event_range = manifest.get("identity_event_range")
    if event_range is not None and (not isinstance(event_range, dict)
                                    or type(event_range.get("first")) is not int
                                    or type(event_range.get("last")) is not int
                                    or event_range["first"] < 1
                                    or event_range["last"] < event_range["first"]):
        raise ValueError("invalid identity event range")
    payload = manifest.get("payload")
    if not isinstance(payload, list):
        raise ValueError("missing payload inventory")
    listed: list[str] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("invalid payload entry")
        name, size, sha = item.get("path"), item.get("size"), item.get("sha256")
        if (not isinstance(name, str) or not valid_relative(name)
                or name == "manifests/release.json" or name.lower().endswith(".meta")
                or not isinstance(size, int) or isinstance(size, bool) or size < 0
                or not isinstance(sha, str) or not HASH.fullmatch(sha)):
            raise ValueError("invalid payload entry")
        path = release.joinpath(*PurePosixPath(name).parts)
        if not path.resolve(strict=True).is_relative_to(release) or not path.is_file():
            raise ValueError(f"payload escapes release: {name}")
        if path.stat().st_size != size or file_digest(path) != sha:
            raise ValueError(f"payload hash mismatch: {name}")
        listed.append(name)
    if listed != sorted(set(listed)):
        raise ValueError("payload inventory must be sorted and unique")
    files = []
    for path in release.rglob("*"):
        if path.is_symlink():
            raise ValueError("symlinks are not allowed in an immutable release")
        if path.is_file():
            files.append(path.relative_to(release).as_posix())
    if sorted(files) != sorted(listed + ["manifests/release.json"]):
        raise ValueError("release has missing or unlisted files")
    return manifest


def read_active(root: Path) -> dict | None:
    path = root / "active.json"
    if path.is_symlink():
        raise ValueError("active pointer cannot be a symlink")
    if not path.exists():
        return None
    if not path.resolve(strict=True).is_relative_to(root):
        raise ValueError("active pointer must be an ordinary file in deployment root")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("catalog_id") != "indexed-icon-pack"
            or not RELEASE.fullmatch(str(data.get("release_id", "")))
            or not HASH.fullmatch(str(data.get("release_manifest_sha256", "")))
            or data.get("relative_release_path") != f"releases/{data.get('release_id')}"):
        raise ValueError("invalid active pointer")
    return data


def activate(args: argparse.Namespace) -> None:
    supplied_root = Path(args.deployment_root)
    if supplied_root.is_symlink():
        raise ValueError("deployment root cannot be a symlink")
    root = supplied_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("deployment root must be an ordinary directory")
    # ponytail: Single-host lock file; shared/multi-host activation needs a coordinator.
    lock = root / "active.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError("active pointer is locked; inspect the stale lock before retrying") from exc
    try:
        os.close(fd)
        prior = read_active(root)
        prior_id = prior["release_id"] if prior else "none"
        if prior_id != args.expected_active:
            raise ValueError(f"active pointer changed: expected {args.expected_active}, found {prior_id}")
        manifest = verify_release(root, args.release_id, args.expected_manifest_sha256)
        problems = validate_catalog.validate(root / "releases" / args.release_id)
        if problems:
            raise ValueError("deep catalog validation failed: " + "; ".join(problems[:3]))
        pointer = {
            "catalog_id": manifest["catalog_id"],
            "release_id": args.release_id,
            "release_manifest_sha256": args.expected_manifest_sha256,
            "relative_release_path": f"releases/{args.release_id}",
        }
        fd, temporary = tempfile.mkstemp(prefix="active-", suffix=".tmp", dir=root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(pointer, stream, sort_keys=True, separators=(",", ":"))
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, root / "active.json")
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        print(json.dumps({"selected": pointer, "previous_release_id": prior_id,
                          "needs_reader_reload_and_version_check": True}, sort_keys=True))
    finally:
        lock.unlink(missing_ok=True)


def check_loaded(args: argparse.Namespace) -> None:
    root = Path(args.deployment_root).resolve(strict=True)
    active = read_active(root)
    if active is None:
        raise ValueError("no active release selected")
    manifest = verify_release(root, active["release_id"], active["release_manifest_sha256"])
    with urlopen(args.version_url, timeout=10) as response:
        loaded = json.load(response)
    if not isinstance(loaded, dict):
        raise ValueError("reader version response must be an object")
    expected = {**active, "catalog_revision": manifest["catalog_revision"],
                "schema_version": manifest["schema_version"]}
    for key in ("catalog_id", "release_id", "release_manifest_sha256",
                "catalog_revision", "schema_version"):
        if loaded.get(key) != expected.get(key):
            raise ValueError(f"reader has not loaded selected {key}")
    print(json.dumps({"loaded": loaded, "matches_active": True}, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    select = sub.add_parser("activate", help="atomically select an installed release")
    select.add_argument("--deployment-root", required=True)
    select.add_argument("--release-id", required=True)
    select.add_argument("--expected-manifest-sha256", required=True)
    select.add_argument("--expected-active", required=True, help="current release ID, or none")
    select.set_defaults(run=activate)
    check = sub.add_parser("check-loaded", help="compare a reader's version endpoint with active.json")
    check.add_argument("--deployment-root", required=True)
    check.add_argument("--version-url", required=True)
    check.set_defaults(run=check_loaded)
    args = parser.parse_args()
    try:
        args.run(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
