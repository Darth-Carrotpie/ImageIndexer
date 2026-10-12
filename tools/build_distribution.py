"""Split an immutable release into bounded image ZIPs and a no-image bootstrap."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.dont_write_bytecode = True
from download_icons import digest, is_image
from validate_catalog import validate

SOURCE = Path(__file__).resolve().parents[1]
LIMIT = 1_000_000_000  # Decimal 1 GB, including all ZIP headers.


def partition(records, limit=LIMIT):
    parts, current, size = [], [], 22  # End-of-central-directory record.
    for record in records:
        cost = record["size"] + 76 + 2 * len(record["path"].encode("ascii"))
        if cost + 22 > limit:
            raise ValueError("An individual image exceeds the archive limit")
        if current and size + cost > limit:
            parts.append(current)
            current, size = [], 22
        current.append(record)
        size += cost
    if current:
        parts.append(current)
    return parts


def add_file(zipped, source, name, compression=zipfile.ZIP_STORED):
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.compress_type = compression
    info.file_size = source.stat().st_size
    with source.open("rb") as incoming, zipped.open(info, "w") as outgoing:
        shutil.copyfileobj(incoming, outgoing, 1024 * 1024)


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def restore_proof(thin, output, release_id, manifest_hash):
    print("Restoring from deliverable ZIPs in a clean temporary directory...", flush=True)
    with tempfile.TemporaryDirectory(prefix=".distribution-proof-", dir=output.parent) as directory:
        root = Path(directory)
        with zipfile.ZipFile(thin) as zipped:
            if any(name.lower().endswith(".png") for name in zipped.namelist()):
                raise ValueError("No-image ZIP contains PNGs")
            # This archive was just generated above from the explicit local allowlist.
            zipped.extractall(root)
        command = [sys.executable, "-B", str(root / "download_icons.py"),
                   "--offline", "--archives-dir", str(output)]
        subprocess.run(command, check=True)
        subprocess.run(command, check=True)  # Already complete: no configuration/network needed.
        release = root / "release" / release_id
        if digest(release / "manifests/release.json") != manifest_hash:
            raise ValueError("Restored release manifest changed")
        result = subprocess.run([sys.executable, "-B", str(release / "iconctl.py"),
            "--package", str(release), "search", "gold key", "--limit", "5", "--json"],
            check=True, capture_output=True, text=True)
        response = json.loads(result.stdout)
        if response["returned_count"] != 5:
            raise ValueError("Restored catalog search smoke failed")
    return {"clean_restore": True, "deep_validation": True, "repeat_install": True,
            "no_images_in_bootstrap": True, "cli_search_returned": 5,
            "temporary_copy_removed": True, "live_nextcloud_tested": False}


def build(release, output, expected):
    release, output = release.resolve(strict=True), output.resolve()
    if output.exists() or output.is_relative_to(release):
        raise ValueError("Output must be a new directory outside the immutable release")
    manifest_path = release / "manifests/release.json"
    manifest_hash = digest(manifest_path)
    if manifest_hash != "sha256:" + expected.removeprefix("sha256:"):
        raise ValueError("Input release manifest does not match the trusted pin")
    print("Deep-verifying immutable input...", flush=True)
    errors = validate(release)
    if errors:
        raise ValueError("Input release failed validation: " + "; ".join(errors[:5]))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    release_id = manifest["release_id"]
    if not re.fullmatch(r"iip-r[0-9]{6,}", release_id):
        raise ValueError("Unsupported release ID")
    images = [r for r in manifest["payload"] if is_image(r["path"])]
    metadata = [r for r in manifest["payload"] if not is_image(r["path"])]
    if not images or any(r["path"].lower().endswith(".png") for r in metadata):
        raise ValueError("Unexpected image layout")
    output.mkdir(parents=True)
    bootstrap = output / "bootstrap"
    packaged = bootstrap / "release" / release_id
    for name in [r["path"] for r in metadata] + ["manifests/release.json"]:
        target = packaged / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(release / name, target)
    shutil.copyfile(SOURCE / "tools/download_icons.py", bootstrap / "download_icons.py")
    shutil.copyfile(SOURCE / "NEXTCLOUD_RELEASE.md", bootstrap / "README.md")
    shutil.copyfile(SOURCE / "LICENSE", bootstrap / "LICENSE")
    write_json(bootstrap / "nextcloud.json", {
        "webdav_base_url": "", "share_token": "", "password_env": "IIP_NEXTCLOUD_PASSWORD"})
    parts = []
    for index, group in enumerate(partition(images), 1):
        path = output / f"IndexedIconPack-{release_id}-images-{index:03}.zip"
        print("Writing " + path.name, flush=True)
        with zipfile.ZipFile(path, "x", allowZip64=False) as zipped:
            for record in group:
                add_file(zipped, release / record["path"], record["path"])
        if path.stat().st_size > LIMIT:
            raise ValueError("ZIP exceeded the size cap")
        parts.append({"filename": path.name, "size": path.stat().st_size,
                      "sha256": digest(path), "paths": [r["path"] for r in group]})
    plan = {"schema_version": 1, "release_path": "release/" + release_id,
            "release_manifest_sha256": manifest_hash, "parts": parts}
    write_json(bootstrap / "distribution.json", plan)
    thin = output / f"IndexedIconPack-{release_id}-no-icons.zip"
    print("Writing " + thin.name, flush=True)
    with zipfile.ZipFile(thin, "x", compression=zipfile.ZIP_DEFLATED, allowZip64=False) as zipped:
        for path in sorted(bootstrap.rglob("*")):
            if path.is_file():
                add_file(zipped, path, path.relative_to(bootstrap).as_posix(), zipfile.ZIP_DEFLATED)
    artifacts = [{k: part[k] for k in ("filename", "size", "sha256")} for part in parts]
    artifacts.append({"filename": thin.name, "size": thin.stat().st_size, "sha256": digest(thin)})
    with (output / "SHA256SUMS.txt").open("x", encoding="ascii", newline="\n") as stream:
        for artifact in artifacts:
            stream.write(artifact["sha256"].removeprefix("sha256:") + "  " + artifact["filename"] + "\n")
    result = {"status": "built_pending_restore_proof", "release_manifest_sha256": manifest_hash,
              "image_files": len(images), "image_bytes": sum(r["size"] for r in images),
              "metadata_files_including_manifest": len(metadata) + 1, "artifacts": artifacts}
    write_json(output / "BUILD.json", result)
    proof = restore_proof(thin, output, release_id, manifest_hash)
    write_json(output / "VERIFICATION.json", {"status": "ready_for_nextcloud_configuration",
               "release_manifest_sha256": manifest_hash, "checks": proof, "artifacts": artifacts})
    print(json.dumps(result, indent=2), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.release, args.output, args.expected_manifest_sha256)
