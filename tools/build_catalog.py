#!/usr/bin/env python3
"""Build an unpublished, deterministic icon catalog before visual annotation.

This tool never calls an image model, publishes a release, or writes to the
source tree. A candidate is deliberately not a deployable package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import struct
import sys
import tempfile
import unicodedata
import uuid
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None


CATALOG_ID = "indexed-icon-pack"
SCHEMA_VERSION = 1
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ROLE_BY_FOLDER = {"Background": "background", "No Background": "transparent", "PNG": "default"}
ROLE_PRIORITY = ("transparent", "default", "background")
ORDINAL_RE = re.compile(r"_(\d+)\.png$", re.IGNORECASE)
UUID4_RE = re.compile(r"^(?:icon|pack|event)_[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def relative_file(path: Path, root: Path) -> str:
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError(f"source file escapes source root: {path}")
    return path.relative_to(root).as_posix()


def png_facts(path: Path) -> dict:
    digest = hashlib.sha256()
    byte_size = 0
    with path.open("rb") as stream:
        header = stream.read(33)
        if len(header) != 33 or header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
            raise ValueError(f"invalid PNG header: {path}")
        if struct.unpack(">I", header[8:12])[0] != 13:
            raise ValueError(f"invalid PNG IHDR length: {path}")
        width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(">IIBBBBB", header[16:29])
        if not width or not height or compression != 0 or filtering != 0 or interlace not in (0, 1):
            raise ValueError(f"unsupported PNG IHDR: {path}")
        valid_depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
        if bit_depth not in valid_depths.get(color_type, ()):
            raise ValueError(f"invalid PNG color type/depth: {path}")
        digest.update(header)
        byte_size += len(header)
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            byte_size += len(chunk)
    if Image is None:
        raise RuntimeError("Pillow is required; install requirements-build.txt")
    with Image.open(path) as image:
        image.load()
    return {"sha256": digest.hexdigest(), "byte_size": byte_size, "width": width,
            "height": height, "color_type": color_type}


def scan(source: Path) -> tuple[list[dict], dict]:
    root = source.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("--source must be a directory")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"symlinks are not accepted in source tree: {path}")
    files = sorted((p for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".png"),
                   key=lambda p: p.relative_to(root).as_posix().casefold())
    if not files:
        raise ValueError("source tree contains no PNG files")

    seen_paths: dict[str, str] = {}
    seen_keys: dict[str, str] = {}
    groups: dict[str, dict[str, dict]] = defaultdict(dict)
    hashes: dict[str, list[str]] = defaultdict(list)
    for index, path in enumerate(files, 1):
        relative = relative_file(path, root)
        normalized = unicodedata.normalize("NFC", relative).casefold()
        if normalized in seen_paths and seen_paths[normalized] != relative:
            raise ValueError(f"case/Unicode path collision: {relative} vs {seen_paths[normalized]}")
        seen_paths[normalized] = relative
        parts = Path(relative).parts
        if len(parts) != 3 or parts[1] not in ROLE_BY_FOLDER:
            raise ValueError(f"unsupported PNG layout (expected collection/role/file): {relative}")
        match = ORDINAL_RE.search(parts[2])
        if not match:
            raise ValueError(f"unnumbered PNG needs explicit identity review: {relative}")
        collection = unicodedata.normalize("NFC", parts[0])
        ordinal = f"{int(match.group(1)):04d}"
        source_key = f"{collection}/{ordinal}"
        folded_key = source_key.casefold()
        if folded_key in seen_keys and seen_keys[folded_key] != source_key:
            raise ValueError(f"case/Unicode identity collision: {source_key} vs {seen_keys[folded_key]}")
        seen_keys[folded_key] = source_key
        role = ROLE_BY_FOLDER[parts[1]]
        if role in groups[source_key]:
            raise ValueError(f"duplicate rendition role for {source_key}: {relative}")
        facts = png_facts(path)
        entry = {"source_key": source_key, "collection": collection, "ordinal": ordinal,
                 "role": role, "source_path": relative, "source_file": path, **facts}
        groups[source_key][role] = entry
        hashes[facts["sha256"]].append(relative)
        if index % 1000 == 0:
            print(f"scanned {index}/{len(files)} PNGs", file=sys.stderr)

    conflicts = []
    ambiguous = set()
    by_collection: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for roles in groups.values():
        for entry in roles.values():
            by_collection[entry["collection"]][entry["role"]].append(entry)
    for collection, role_entries in by_collection.items():
        transparent_by_hash = defaultdict(list)
        for entry in role_entries["transparent"]:
            transparent_by_hash[entry["sha256"]].append(entry)
        for background in role_entries["background"]:
            for transparent in transparent_by_hash[background["sha256"]]:
                if background["ordinal"] != transparent["ordinal"]:
                    ambiguous.update((background["source_key"], transparent["source_key"]))
                    conflicts.append({"background": background["source_path"],
                                      "transparent": transparent["source_path"],
                                      "sha256": background["sha256"]})
    duplicate_aliases = [{"sha256": digest, "source_paths": paths}
                         for digest, paths in sorted(hashes.items()) if len(paths) > 1]
    icons = []
    for source_key, roles in sorted(groups.items()):
        first = next(iter(roles.values()))
        paired = "background" in roles and "transparent" in roles
        icons.append({"source_key": source_key, "collection": first["collection"],
                      "ordinal": first["ordinal"], "renditions": roles,
                      "preferred_role": next(role for role in ROLE_PRIORITY if role in roles),
                      "grouping_status": "ambiguous" if source_key in ambiguous else
                      ("candidate" if paired else "single")})
    anomalies = {"schema_version": SCHEMA_VERSION,
                 "pairing_policy": "numbered pairs are candidates, not visually verified identities",
                 "candidate_pair_count": sum(icon["grouping_status"] == "candidate" for icon in icons),
                 "ambiguous_pair_count": sum(icon["grouping_status"] == "ambiguous" for icon in icons),
                 "cross_ordinal_exact_matches": conflicts,
                 "duplicate_blob_aliases": duplicate_aliases}
    return icons, anomalies


def read_registry(path: Path) -> tuple[list[dict], dict[str, str], str]:
    if not path.is_file():
        raise ValueError(f"identity registry missing: {path}")
    raw = path.read_bytes()
    if not raw or not raw.endswith(b"\n"):
        raise ValueError("identity registry must be nonempty LF-terminated JSONL")
    events = []
    mappings = {}
    previous_hash = None
    pack_id = None
    for number, line in enumerate(raw.splitlines(), 1):
        event = json.loads(line)
        expected = {"sequence", "event_id", "previous_event_sha256", "event_kind", "catalog_id",
                    "pack_id", "icon_id", "source_key", "evidence_sha256"}
        if set(event) != expected or canonical(event) != line:
            raise ValueError(f"noncanonical/invalid identity event {number}")
        if event["sequence"] != number or event["previous_event_sha256"] != previous_hash:
            raise ValueError(f"broken identity chain at event {number}")
        if event["event_kind"] != "assign" or event["catalog_id"] != CATALOG_ID:
            raise ValueError(f"unsupported identity event at {number}")
        for key, prefix in (("event_id", "event"), ("icon_id", "icon"), ("pack_id", "pack")):
            value = event[key]
            if not isinstance(value, str) or not UUID4_RE.fullmatch(value) or not value.startswith(prefix + "_"):
                raise ValueError(f"invalid {key} at event {number}")
        pack_id = pack_id or event["pack_id"]
        if pack_id != event["pack_id"] or event["source_key"] in mappings or event["icon_id"] in mappings.values():
            raise ValueError(f"identity collision at event {number}")
        mappings[event["source_key"]] = event["icon_id"]
        previous_hash = sha256(line)
        events.append(event)
    return events, mappings, pack_id


def write_registry(path: Path, icons: list[dict], base: Path | None) -> tuple[dict[str, str], str]:
    if base:
        old_path = base / "manifests/icon-identities.jsonl"
        events, mappings, pack_id = read_registry(old_path)
        previous_lines = old_path.read_bytes()
        previous_hash = sha256(previous_lines.splitlines()[-1])
    else:
        events, mappings, pack_id = [], {}, f"pack_{uuid.uuid4()}"
        previous_lines = b""
        previous_hash = None
    with path.open("wb") as stream:
        stream.write(previous_lines)
        for icon in icons:
            key = icon["source_key"]
            if key in mappings:
                continue
            icon_id = f"icon_{uuid.uuid4()}"
            mappings[key] = icon_id
            evidence = [{"role": role, "sha256": entry["sha256"], "source_path": entry["source_path"]}
                        for role, entry in sorted(icon["renditions"].items())]
            event = {"sequence": len(events) + 1, "event_id": f"event_{uuid.uuid4()}",
                     "previous_event_sha256": previous_hash, "event_kind": "assign",
                     "catalog_id": CATALOG_ID, "pack_id": pack_id, "icon_id": icon_id,
                     "source_key": key, "evidence_sha256": sha256(canonical(evidence))}
            line = canonical(event)
            stream.write(line + b"\n")
            previous_hash = sha256(line)
            events.append(event)
    return mappings, pack_id


def check_base(base: Path, icons: list[dict]) -> None:
    # ponytail: This first builder only accepts an unchanged/additive unpublished pack;
    # add a reviewed continuity planner before changed bytes, retirements, or published bases.
    db_path = base / "catalog.sqlite"
    if not db_path.is_file() or (base / "manifests/release.json").exists():
        raise ValueError("--base must be an unpublished pre-annotation candidate")
    with closing(sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)) as connection:
        state = connection.execute("SELECT catalog_id,schema_version,annotation_status FROM catalog_state").fetchone()
        if state != (CATALOG_ID, SCHEMA_VERSION, "pending_model_choice"):
            raise ValueError("base catalog lineage/schema/annotation state is unsupported")
        old = {(key, role): (digest, path) for key, role, digest, path in connection.execute(
            "SELECT icon.source_key,rendition.stable_role,rendition.blob_sha256,rendition.source_path "
            "FROM rendition JOIN icon USING(icon_id)")}
    new = {(icon["source_key"], role): (entry["sha256"], entry["source_path"])
           for icon in icons for role, entry in icon["renditions"].items()}
    changed = [(key, role) for (key, role), facts in old.items() if new.get((key, role)) != facts]
    if changed:
        raise ValueError(f"existing source changed/removed; explicit continuity review is required: {changed[:8]}")
    events, mappings, _ = read_registry(base / "manifests/icon-identities.jsonl")
    if len(events) != len({icon["source_key"] for icon in icons if icon["source_key"] in mappings}):
        raise ValueError("base identities missing from source; explicit retirement review is required")


DDL = """
PRAGMA foreign_keys=ON;
PRAGMA user_version=1;
CREATE TABLE catalog_state(catalog_id TEXT PRIMARY KEY,pack_id TEXT NOT NULL,schema_version INTEGER NOT NULL,annotation_status TEXT NOT NULL);
CREATE TABLE icon(icon_id TEXT PRIMARY KEY,pack_id TEXT NOT NULL,source_key TEXT NOT NULL UNIQUE,collection TEXT NOT NULL,ordinal TEXT NOT NULL,title TEXT NOT NULL,preferred_role TEXT NOT NULL,lifecycle_status TEXT NOT NULL,grouping_status TEXT NOT NULL,description TEXT NOT NULL DEFAULT '');
CREATE INDEX icon_collection_ordinal ON icon(collection,ordinal);
CREATE TABLE blob(sha256 TEXT PRIMARY KEY,byte_size INTEGER NOT NULL,width INTEGER NOT NULL,height INTEGER NOT NULL,color_type INTEGER NOT NULL,relative_path TEXT NOT NULL UNIQUE);
CREATE TABLE rendition(icon_id TEXT NOT NULL REFERENCES icon(icon_id),stable_role TEXT NOT NULL,blob_sha256 TEXT NOT NULL REFERENCES blob(sha256),source_path TEXT NOT NULL,PRIMARY KEY(icon_id,stable_role));
CREATE INDEX rendition_blob ON rendition(blob_sha256);
CREATE TABLE rendition_history(icon_id TEXT NOT NULL REFERENCES icon(icon_id),blob_sha256 TEXT NOT NULL REFERENCES blob(sha256),stable_role TEXT NOT NULL,PRIMARY KEY(icon_id,blob_sha256,stable_role));
CREATE INDEX rendition_history_blob ON rendition_history(blob_sha256);
CREATE TABLE derivative(icon_id TEXT PRIMARY KEY REFERENCES icon(icon_id),source_blob_sha256 TEXT NOT NULL REFERENCES blob(sha256),relative_path TEXT NOT NULL,sha256 TEXT NOT NULL,width INTEGER NOT NULL,height INTEGER NOT NULL);
CREATE TABLE icon_keyword(icon_id TEXT NOT NULL REFERENCES icon(icon_id),namespace TEXT NOT NULL,value TEXT NOT NULL,PRIMARY KEY(icon_id,namespace,value));
CREATE INDEX icon_keyword_value ON icon_keyword(namespace,value,icon_id);
CREATE VIRTUAL TABLE icon_fts USING fts5(icon_id UNINDEXED,title,collection,description,keywords);
"""


def thumbnail(source: Path, output: Path) -> tuple[str, int, int]:
    if Image is None:
        raise RuntimeError("Pillow is required; install requirements-build.txt")
    with Image.open(source) as image:
        image.load()
        image = image.convert("RGBA")
        image.thumbnail((256, 256), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        canvas.paste(image, ((256 - image.width) // 2, (256 - image.height) // 2))
        canvas.save(output, format="PNG", optimize=False, compress_level=9)
    return sha256(output.read_bytes()), 256, 256


def stage_is_owned(stage: Path, output: Path) -> bool:
    """The only tree this command may replace or remove is its own temp sibling."""
    return (not stage.is_symlink() and stage.resolve().parent == output.parent.resolve()
            and stage.name.startswith(f".{output.name}.building-")
            and output.parent.resolve() != Path(output.anchor))


def build(source: Path, output: Path, base: Path | None) -> None:
    if Image is None:
        raise RuntimeError("Pillow is required; install requirements-build.txt")
    source = source.resolve(strict=True)
    output = output.resolve()
    if output.exists():
        raise ValueError("--output must be a new directory; existing candidates are never overwritten")
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("output must be outside source tree")
    if base:
        base = base.resolve(strict=True)
        if output.is_relative_to(base) or base.is_relative_to(output):
            raise ValueError("output must be outside base tree")
    output.parent.mkdir(parents=True, exist_ok=True)
    icons, anomalies = scan(source)
    if base:
        check_base(base, icons)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.building-", dir=output.parent))
    try:
        for folder in ("assets/sha256", "thumbnails", "manifests"):
            (stage / folder).mkdir(parents=True, exist_ok=True)
        mappings, pack_id = write_registry(stage / "manifests/icon-identities.jsonl", icons, base)
        (stage / "manifests/anomalies.json").write_bytes(canonical(anomalies) + b"\n")
        catalog_lines = []
        with closing(sqlite3.connect(stage / "catalog.sqlite")) as db:
            db.executescript(DDL)
            db.execute("INSERT INTO catalog_state VALUES (?,?,?,?)",
                       (CATALOG_ID, pack_id, SCHEMA_VERSION, "pending_model_choice"))
            copied = set()
            for index, icon in enumerate(icons, 1):
                icon_id = mappings[icon["source_key"]]
                title = f"{icon['collection'].removesuffix(' Icons')} {int(icon['ordinal']):02d}"
                db.execute("INSERT INTO icon VALUES (?,?,?,?,?,?,?,?,?,?)",
                           (icon_id, pack_id, icon["source_key"], icon["collection"], icon["ordinal"],
                            title, icon["preferred_role"], "active", icon["grouping_status"], ""))
                db.execute("INSERT INTO icon_fts VALUES (?,?,?,?,?)", (icon_id, title, icon["collection"], "", ""))
                for role, entry in sorted(icon["renditions"].items()):
                    digest = entry["sha256"]
                    relative = f"assets/sha256/{digest[:2]}/{digest}.png"
                    if digest not in copied:
                        destination = stage / relative
                        destination.parent.mkdir(exist_ok=True)
                        shutil.copyfile(entry["source_file"], destination)
                        if sha256(destination.read_bytes()) != digest:
                            raise ValueError(f"source changed during copy: {entry['source_path']}")
                        copied.add(digest)
                        db.execute("INSERT INTO blob VALUES (?,?,?,?,?,?)",
                                   (digest, entry["byte_size"], entry["width"], entry["height"],
                                    entry["color_type"], relative))
                    db.execute("INSERT INTO rendition VALUES (?,?,?,?)",
                               (icon_id, role, digest, entry["source_path"]))
                    db.execute("INSERT INTO rendition_history VALUES (?,?,?)", (icon_id, digest, role))
                    catalog_lines.append({"icon_id": icon_id, "source_key": icon["source_key"],
                                          "stable_role": role, "source_path": entry["source_path"],
                                          "blob_sha256": digest, "byte_size": entry["byte_size"],
                                          "width": entry["width"], "height": entry["height"],
                                          "color_type": entry["color_type"]})
                preferred = icon["renditions"][icon["preferred_role"]]
                thumb_path = f"thumbnails/{icon_id}.png"
                preferred_hash = preferred["sha256"]
                preferred_blob = stage / f"assets/sha256/{preferred_hash[:2]}/{preferred_hash}.png"
                thumb_hash, thumb_width, thumb_height = thumbnail(preferred_blob, stage / thumb_path)
                db.execute("INSERT INTO derivative VALUES (?,?,?,?,?,?)",
                           (icon_id, preferred["sha256"], thumb_path, thumb_hash, thumb_width, thumb_height))
                if index % 500 == 0:
                    print(f"built {index}/{len(icons)} logical icons", file=sys.stderr)
            if db.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("foreign key check failed")
            db.commit()
        with (stage / "manifests/catalog.jsonl").open("wb") as stream:
            for row in sorted(catalog_lines, key=lambda row: (row["source_key"], row["stable_role"])):
                stream.write(canonical(row) + b"\n")
        if not stage_is_owned(stage, output) or output.exists() or output.is_symlink():
            raise ValueError("candidate target changed or temporary stage is outside intended parent")
        os.replace(stage, output)
    except Exception:
        if stage_is_owned(stage, output):
            shutil.rmtree(stage)
        raise
    print(json.dumps({"status": "pending_model_choice", "catalog_id": CATALOG_ID,
                      "pack_id": pack_id, "logical_icons": len(icons),
                      "renditions": sum(len(icon["renditions"]) for icon in icons),
                      "unique_blobs": len(copied), "ambiguous_pairs": anomalies["ambiguous_pair_count"],
                      "candidate": output.as_posix()}, sort_keys=True))


def annotation_plan(workspace: Path, output: Path) -> None:
    workspace = workspace.resolve(strict=True)
    if (workspace / "manifests/release.json").exists():
        raise ValueError("annotation-plan expects an unpublished candidate")
    with closing(sqlite3.connect(f"file:{(workspace / 'catalog.sqlite').as_posix()}?mode=ro", uri=True)) as db:
        state = db.execute("SELECT annotation_status FROM catalog_state").fetchone()
        if state != ("pending_model_choice",):
            raise ValueError("candidate is not at model-choice gate")
        rows = db.execute("SELECT icon.icon_id,icon.source_key,icon.collection,icon.grouping_status,"
                          "rendition.stable_role,rendition.source_path,blob.width,blob.height,blob.color_type "
                          "FROM icon JOIN rendition USING(icon_id) JOIN blob ON blob.sha256=rendition.blob_sha256 "
                          "ORDER BY icon.source_key,rendition.stable_role").fetchall()
    dimensions = Counter(f"{row[6]}x{row[7]}" for row in rows)
    by_icon = defaultdict(list)
    for icon_id, key, collection, grouping, role, source_path, width, height, color_type in rows:
        by_icon[icon_id].append({"source_key": key, "collection": collection, "grouping_status": grouping,
                                 "role": role, "source_path": source_path, "width": width,
                                 "height": height, "color_type": color_type})
    candidates = []
    for icon_id, entries in by_icon.items():
        categories = [entries[0]["grouping_status"]]
        if any(entry["width"] > 512 or entry["height"] > 512 for entry in entries):
            categories.append("over_512")
        if any(entry["color_type"] == 3 for entry in entries):
            categories.append("indexed_color")
        candidates.append({"icon_id": icon_id, "source_key": entries[0]["source_key"],
                           "categories": categories, "renditions": entries})
    samples = []
    chosen = set()
    for category in ("ambiguous", "candidate", "single", "over_512", "indexed_color"):
        for candidate in sorted(candidates, key=lambda item: item["source_key"]):
            if category in candidate["categories"] and candidate["icon_id"] not in chosen:
                samples.append(candidate)
                chosen.add(candidate["icon_id"])
                if sum(category in item["categories"] for item in samples) >= 10:
                    break
    for candidate in sorted(candidates, key=lambda item: item["source_key"]):
        if len(samples) >= 100:
            break
        if candidate["icon_id"] not in chosen:
            samples.append(candidate)
            chosen.add(candidate["icon_id"])
    plan = {"schema_version": SCHEMA_VERSION, "catalog_id": CATALOG_ID,
            "status": "stop_before_any_image_model_call", "pending_logical_icons": len(by_icon),
            "source_renditions": len(rows), "dimension_counts": dict(sorted(dimensions.items())),
            "grouping_counts": dict(Counter(entry[0]["grouping_status"] for entry in by_icon.values())),
            "suggested_request_count": len(by_icon), "sample": samples,
            "cost_inputs": {"model": "owner_selection_required", "image_detail": "owner_selection_required",
                            "images_per_icon": "1 preferred; second rendition when needed for ambiguity",
                            "browser_thumbnail_px": 256, "annotation_preview_max_edge_px": 512,
                            "annotation_preview_policy": "resize a working copy with aspect ratio preserved; retain exact originals; inspect second rendition when grouping is ambiguous",
                            "prices": "check current provider prices at gate",
                            "estimate_note": "actual image token usage requires chosen model and pilot"},
            "proposed_annotation": {
                "prompt": "Inspect the supplied icon image(s). Describe only visibly supported content, not the filename or collection. Keep literal observations separate from possible UI uses. If two renditions are supplied, say whether they depict the same motif and flag uncertainty. Return structured data with no invented text or symbols.",
                "fields": {"description": "one literal sentence", "subjects": ["visible subject"],
                           "action": "visible action or null", "state": "visible state or null",
                           "colors": ["dominant color"], "materials": ["visible material"],
                           "effects": ["visible effect"], "composition": "count and orientation",
                           "symbols": ["visible symbol"], "visible_text": "literal text or null",
                           "keywords": ["literal search term"], "inferred_uses": ["possible UI use"],
                           "same_motif_across_renditions": "yes, no, or uncertain"}}}
    output = output.resolve()
    if output.exists():
        raise ValueError("annotation-plan output must be a new file")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical(plan) + b"\n")
    print(json.dumps({"status": plan["status"], "logical_icons": len(by_icon),
                      "renditions": len(rows), "plan": output.as_posix()}, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    bootstrap = sub.add_parser("bootstrap", help="build a new unpublished pre-annotation candidate")
    bootstrap.add_argument("--source", type=Path, required=True)
    bootstrap.add_argument("--output", type=Path, required=True)
    bootstrap.add_argument("--base", type=Path, help="prior unpublished candidate; only unchanged/additive inputs supported")
    plan = sub.add_parser("annotation-plan", help="prepare model-choice facts without model calls")
    plan.add_argument("--workspace", type=Path, required=True)
    plan.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "bootstrap":
            build(args.source, args.output, args.base)
        else:
            annotation_plan(args.workspace, args.output)
    except (ValueError, OSError, sqlite3.Error, RuntimeError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
