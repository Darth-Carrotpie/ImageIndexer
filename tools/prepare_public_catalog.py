"""Publish a byte-preserved, image-free catalog; never reannotate or rebuild SQLite."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import zipfile

from build_distribution import add_file, write_json
from download_icons import digest, is_image, load_plan, safe_path

SOURCE = Path(__file__).resolve().parents[1]
MAX_FILE_BYTES = 100 * 1024 * 1024
WRAPPER = ("README.md", "LICENSE", "download_icons.py", "distribution.json",
           "nextcloud.example.json", "observations.jsonl")
PRIVATE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp", ".ico",
                    ".zip", ".7z", ".unitypackage", ".db", ".pem", ".key", ".pfx", ".p12"}
# Bounded publication guard, not a complete secret or rights audit.
SENSITIVE = re.compile(r"sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|"
                       r"github_pat_[A-Za-z0-9_]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
                       r"data:image/[^,\s]+;base64,[A-Za-z0-9+/]{80,}")


def observation_lines(database):
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only = ON")
        if db.execute("SELECT COUNT(*) FROM icon_observation").fetchone()[0] != db.execute(
                "SELECT COUNT(*) FROM icon").fetchone()[0]:
            raise ValueError("Observation export must cover every icon")
        for row in db.execute("SELECT * FROM icon_observation ORDER BY icon_id"):
            item = dict(row)
            item["observation"] = json.loads(item.pop("observation_json"))
            yield json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def publication_files(root):
    plan, release, records = load_plan(root)
    names = list(WRAPPER) + [plan["release_path"] + "/manifests/release.json"]
    names += [plan["release_path"] + "/" + name for name in records if not is_image(name)]
    for name in names:
        path = safe_path(root, name)
        if not path.is_file() or path.suffix.lower() in PRIVATE_SUFFIXES:
            raise ValueError("Missing or private publication file: " + name)
        if path.stat().st_size >= MAX_FILE_BYTES:
            raise ValueError("Ordinary Git file-size ceiling reached: " + name)
    return sorted(names), plan, release


def check_catalog(root):
    root = root.resolve(strict=True)
    names, plan, release = publication_files(root)
    example = json.loads((root / "nextcloud.example.json").read_text(encoding="utf-8"))
    if example != {"webdav_base_url": "", "share_token": "", "password_env": "IIP_NEXTCLOUD_PASSWORD"}:
        raise ValueError("Public Nextcloud example must contain no endpoint or credentials")
    count = 0
    with closing(observation_lines(release / "catalog.sqlite")) as expected_rows, \
            (root / "observations.jsonl").open(encoding="utf-8", newline="") as exported:
        for expected in expected_rows:
            if exported.readline() != expected:
                raise ValueError("Observation export differs from the pinned database")
            count += 1
        if exported.read(1):
            raise ValueError("Observation export has extra records")
    return {"status": "metadata_verified_images_not_checked", "release_path": plan["release_path"],
            "release_manifest_sha256": plan["release_manifest_sha256"], "observations": count,
            "database_bytes": (release / "catalog.sqlite").stat().st_size,
            "public_files": len(names), "public_bytes": sum((root / p).stat().st_size for p in names)}


def inspect_public_file(path, relative, database_relative):
    if (relative.startswith("work/") or path.suffix.lower() in PRIVATE_SUFFIXES
            or path.name in ("nextcloud.json", ".download.lock", ".installer.lock", ".imageindexer-install.json")
            or path.name.startswith(".nextcloud-")
            or path.name.startswith(".env") and path.name != ".env.example"
            or ".sqlite" in path.name and relative != database_relative):
        raise ValueError("Private/generated file would enter Git: " + relative)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Publication expects ordinary files: " + relative)
    if path.stat().st_size >= MAX_FILE_BYTES:
        raise ValueError("Ordinary Git file-size ceiling reached: " + relative)
    if relative != database_relative:
        text = path.read_text(encoding="utf-8-sig")
        if SENSITIVE.search(text):
            raise ValueError("Potential secret or embedded image in: " + relative)


def check_repository(repository, catalog):
    repository = repository.resolve(strict=True)
    catalog = catalog.resolve(strict=True)
    names, plan, _ = publication_files(catalog)
    prefix = catalog.relative_to(repository).as_posix() + "/"
    candidates = subprocess.run(["git", "-C", str(repository), "ls-files", "--cached", "--others",
        "--exclude-standard", "-z"], check=True, capture_output=True).stdout.decode("utf-8").split("\0")
    candidates = sorted(set(filter(None, candidates)))
    if not {prefix + name for name in names}.issubset(candidates):
        raise ValueError("Git ignore rules hide required catalog publication files")
    database = prefix + plan["release_path"] + "/catalog.sqlite"
    for name in candidates:
        path = repository / name
        if not path.resolve().is_relative_to(repository):
            raise ValueError("Publication path escapes repository")
        inspect_public_file(path, name, database)
    # Catch inherited/global LFS filters or newline conversion on hash-pinned payloads.
    pinned = [prefix + n for n in names if n.startswith("release/") or n == "distribution.json"]
    attrs = subprocess.run(["git", "-C", str(repository), "check-attr", "text", "filter", "--", *pinned],
                           check=True, capture_output=True, text=True).stdout.splitlines()
    if any(not line.endswith(": unset") for line in attrs):
        raise ValueError("Pinned payloads need -text -filter attributes; ordinary Git only")
    return {"git_candidate_files": len(candidates),
            "git_candidate_bytes": sum((repository / name).stat().st_size for name in candidates)}


def prepare(bootstrap, output, expected):
    bootstrap = bootstrap.resolve(strict=True)
    output = output.resolve()
    plan, release, records = load_plan(bootstrap)
    if plan["release_manifest_sha256"] != "sha256:" + expected.removeprefix("sha256:"):
        raise ValueError("Input release differs from the trusted manifest pin")
    if output.exists() or output.is_relative_to(bootstrap):
        raise ValueError("Output must be a new directory outside the source bootstrap")
    output.mkdir(parents=True)
    # Failed output is retained for diagnosis; no existing catalog is replaced.
    for name in [p for p in records if not is_image(p)] + ["manifests/release.json"]:
        target = safe_path(output, plan["release_path"] + "/" + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(safe_path(release, name), target)
    shutil.copyfile(bootstrap / "distribution.json", output / "distribution.json")
    for source, target in (("tools/download_icons.py", "download_icons.py"),
                           ("NEXTCLOUD_RELEASE.md", "README.md"), ("LICENSE", "LICENSE")):
        shutil.copyfile(SOURCE / source, output / target)
    write_json(output / "nextcloud.example.json", {
        "webdav_base_url": "", "share_token": "", "password_env": "IIP_NEXTCLOUD_PASSWORD"})
    with (output / "observations.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        stream.writelines(observation_lines(release / "catalog.sqlite"))
    return check_catalog(output)


def make_zip(catalog, output):
    proof = check_catalog(catalog)
    names, plan, _ = publication_files(catalog)
    if output.exists():
        raise ValueError("ZIP output must be new")
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, allowZip64=False) as archive:
        for name in names:
            add_file(archive, catalog / name, name, zipfile.ZIP_DEFLATED)
    return {**proof, "filename": output.name, "size": output.stat().st_size, "sha256": digest(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("prepare")
    create.add_argument("--bootstrap", type=Path, required=True)
    create.add_argument("--output", type=Path, default=SOURCE / "catalog")
    create.add_argument("--expected-manifest-sha256", required=True)
    check = commands.add_parser("check")
    check.add_argument("--catalog", type=Path, default=SOURCE / "catalog")
    check.add_argument("--repository", type=Path, help="also audit Git's public candidate inventory")
    archive = commands.add_parser("zip")
    archive.add_argument("--catalog", type=Path, default=SOURCE / "catalog")
    archive.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.bootstrap, args.output, args.expected_manifest_sha256)
    elif args.command == "zip":
        result = make_zip(args.catalog, args.output)
    else:
        result = check_catalog(args.catalog)
        if args.repository:
            result.update(check_repository(args.repository, args.catalog))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
