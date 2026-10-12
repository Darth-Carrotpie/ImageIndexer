#!/usr/bin/env python3
"""Build an unpublished schema-v2 search candidate from reviewed observations."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

from annotation_data import load_annotations, sha256
from validate_catalog import validate


PACKAGE = Path(__file__).resolve().parents[1]
SEARCH_SCHEMA_VERSION = 2
FTS_COLUMNS = ("icon_id", "subject", "action", "state", "effect", "symbol", "color",
               "material", "visible_text", "keywords", "description", "inferred_use",
               "composition", "title", "collection")
KEYWORD_FIELDS = {
    "keywords": "keyword",
    "subjects": "subject",
    "materials": "material",
    "colors": "color",
    "effects": "effect",
    "symbols": "symbol",
    "inferred_uses": "inferred_use",
    "uncertainties": "uncertainty",
}


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def stage_is_owned(stage: Path, output: Path) -> bool:
    return (not stage.is_symlink() and stage.resolve().parent == output.parent.resolve()
            and stage.name.startswith(f".{output.name}.building-")
            and output.parent.resolve() != Path(output.anchor))


def link_tree(source: Path, destination: Path) -> None:
    # shortcut: unpublished candidates hard-link immutable payloads; a release builder must copy them.
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        target = destination / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file() and not path.is_symlink():
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(path, target)
        else:
            raise ValueError(f"payload link is not a regular file: {path}")


def load_profile(path: Path) -> dict:
    profile = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(profile, dict) or profile.get("profile_schema_version") != 1
            or profile.get("schema_version") != SEARCH_SCHEMA_VERSION
            or tuple(profile.get("fts_columns", ())) != FTS_COLUMNS
            or set(profile.get("bm25_weights", {})) != set(FTS_COLUMNS)):
        raise ValueError("search profile does not match schema-v2 columns")
    implementation = {}
    for source in (PACKAGE / "iconctl.py", Path(__file__), Path(__file__).with_name("annotation_data.py")):
        implementation[source.relative_to(PACKAGE).as_posix()] = sha256(source)
    profile["implementation_sha256"] = implementation
    profile["alias_map_sha256"] = hashlib.sha256(canonical(profile["alias_map"])).hexdigest()
    return profile


def apply_corrections(connection: sqlite3.Connection, freeze: dict) -> dict[str, Path]:
    thumbnail_sources = {}
    corrections = freeze.get("corrections")
    if not isinstance(corrections, list) or len(corrections) != 4:
        raise ValueError("identity freeze must contain four pairing corrections")
    prepared = []
    for correction in corrections:
        icon_id = correction["icon_id"]
        binding = connection.execute(
            "SELECT source_key FROM icon WHERE icon_id = ?", (icon_id,)).fetchone()
        matching = connection.execute(
            "SELECT r.icon_id,r.blob_sha256,d.relative_path,d.sha256,d.width,d.height "
            "FROM rendition r JOIN derivative d ON d.icon_id=r.icon_id "
            "WHERE r.source_path=? AND r.stable_role='transparent'",
            (correction["matching_source_path"],)).fetchone()
        background = connection.execute(
            "SELECT blob_sha256 FROM rendition WHERE icon_id=? AND stable_role='background' "
            "AND source_path=?", (icon_id, correction["background_source_path"])).fetchone()
        if (binding is None or binding[0] != correction["source_key"] or matching is None
                or background is None or matching[1] != correction["matching_blob_sha256"]
                or background[0] != correction["matching_blob_sha256"]):
            raise ValueError(f"reviewed rendition correction is not proven: {icon_id}")
        prepared.append((correction, matching))
    for correction, matching in prepared:
        icon_id = correction["icon_id"]
        thumbnail_sources[icon_id] = Path(matching[2])
        connection.execute(
            "UPDATE rendition SET blob_sha256=?,source_path=? "
            "WHERE icon_id=? AND stable_role='transparent'",
            (matching[1], correction["matching_source_path"], icon_id))
        connection.execute(
            "INSERT OR IGNORE INTO rendition_history(icon_id,blob_sha256,stable_role) VALUES(?,?,'transparent')",
            (icon_id, matching[1]))
        connection.execute("UPDATE icon SET grouping_status='reviewed' WHERE icon_id=?", (icon_id,))
        connection.execute(
            "UPDATE derivative SET source_blob_sha256=?,sha256=?,width=?,height=? WHERE icon_id=?",
            (matching[1], matching[3], matching[4], matching[5], icon_id))
    duplicates = connection.execute(
        "SELECT source_path,count(*) FROM rendition GROUP BY source_path HAVING count(*) != 1"
    ).fetchall()
    if duplicates:
        raise ValueError("pairing corrections left duplicate source occurrences")
    return thumbnail_sources


def observation_projection(annotation: dict, reviewed_terms: list[str], icon: sqlite3.Row) -> tuple[str, ...]:
    values = {
        "icon_id": icon["icon_id"],
        "subject": "\n".join(annotation["subjects"]),
        "action": annotation["action"] or "",
        "state": annotation["state"] or "",
        "effect": "\n".join(annotation["effects"]),
        "symbol": "\n".join(annotation["symbols"]),
        "color": "\n".join(annotation["colors"]),
        "material": "\n".join(annotation["materials"]),
        "visible_text": annotation["visible_text"] or "",
        "keywords": "\n".join([*annotation["keywords"], *reviewed_terms]),
        "description": annotation["description"],
        "inferred_use": "\n".join(annotation["inferred_uses"]),
        "composition": annotation["composition"],
        "title": icon["title"],
        "collection": icon["collection"],
    }
    return tuple(values[column] for column in FTS_COLUMNS)


def populate_search(connection: sqlite3.Connection, loaded: dict, profile: dict) -> str:
    tokenizer = profile["tokenizer"].replace("'", "''")
    connection.executescript(f"""
DROP TABLE icon_fts;
CREATE VIRTUAL TABLE icon_fts USING fts5({','.join(FTS_COLUMNS)}, tokenize='{tokenizer}');
CREATE TABLE icon_observation(
  icon_id TEXT PRIMARY KEY REFERENCES icon(icon_id),
  observation_schema_version INTEGER NOT NULL,
  source_blob_sha256 TEXT NOT NULL,
  preview_sha256 TEXT NOT NULL,
  raw_annotations_sha256 TEXT NOT NULL,
  accepted_annotations_sha256 TEXT NOT NULL,
  review_chain_sha256 TEXT NOT NULL,
  observation_json TEXT NOT NULL
);
CREATE TABLE search_profile(
  profile_id TEXT PRIMARY KEY,
  profile_sha256 TEXT NOT NULL UNIQUE,
  profile_json TEXT NOT NULL
);
""")
    profile_json = canonical(profile).decode("utf-8")
    profile_sha256 = hashlib.sha256(profile_json.encode("utf-8")).hexdigest()
    connection.execute("INSERT INTO search_profile VALUES(?,?,?)",
                       (profile["profile_id"], profile_sha256, profile_json))
    connection.execute("DELETE FROM icon_keyword")
    icons = {row["icon_id"]: row for row in connection.execute(
        "SELECT icon_id,title,collection FROM icon")}
    if set(icons) != set(loaded["annotations"]):
        raise ValueError("candidate IDs differ from accepted annotation IDs")
    review_chain_sha256 = hashlib.sha256(canonical(loaded["review_chain"])).hexdigest()
    for icon_id in sorted(icons):
        annotation = loaded["annotations"][icon_id]
        terms = loaded["reviewed_terms"].get(icon_id, [])
        source = loaded["manifest"][icon_id]
        preferred = connection.execute(
            "SELECT r.blob_sha256 FROM rendition r JOIN icon i USING(icon_id) "
            "WHERE r.icon_id=? AND r.stable_role=i.preferred_role", (icon_id,)).fetchone()
        if preferred is None or preferred[0] != source["source_blob_sha256"]:
            raise ValueError(f"observation preview is not pinned to preferred rendition: {icon_id}")
        accepted_json = canonical({"annotation": annotation,
                                   "reviewed_search_terms": terms}).decode("utf-8")
        connection.execute("UPDATE icon SET description=? WHERE icon_id=?",
                           (annotation["description"], icon_id))
        connection.execute("INSERT INTO icon_observation VALUES(?,?,?,?,?,?,?,?)", (
            icon_id, 1, source["source_blob_sha256"], source["preview_sha256"],
            loaded["raw_annotations_sha256"], loaded["accepted_annotations_sha256"],
            review_chain_sha256, accepted_json))
        keywords = set()
        for field, namespace in KEYWORD_FIELDS.items():
            keywords.update((namespace, normalized(value)) for value in annotation[field])
        for field in ("action", "state", "visible_text"):
            if annotation[field]:
                keywords.add((field, normalized(annotation[field])))
        keywords.update(("reviewed_term", normalized(value)) for value in terms)
        connection.executemany("INSERT INTO icon_keyword VALUES(?,?,?)",
                               ((icon_id, namespace, value)
                                for namespace, value in sorted(keywords)))
        connection.execute(f"INSERT INTO icon_fts({','.join(FTS_COLUMNS)}) "
                           f"VALUES({','.join('?' for _ in FTS_COLUMNS)})",
                           observation_projection(annotation, terms, icons[icon_id]))
    connection.executescript("""
CREATE VIRTUAL TABLE icon_fts_vocab USING fts5vocab(icon_fts, 'row');
CREATE VIRTUAL TABLE icon_fts_instance USING fts5vocab(icon_fts, 'instance');
PRAGMA user_version=2;
UPDATE catalog_state SET schema_version=2,annotation_status='annotated_search_candidate';
""")
    return profile_sha256


def write_catalog_manifest(connection: sqlite3.Connection, path: Path) -> None:
    rows = connection.execute(
        "SELECT i.icon_id,i.source_key,r.stable_role,r.source_path,b.sha256,b.byte_size,"
        "b.width,b.height,b.color_type FROM rendition r JOIN icon i USING(icon_id) "
        "JOIN blob b ON b.sha256=r.blob_sha256 ORDER BY i.source_key,r.stable_role"
    ).fetchall()
    with path.open("wb") as stream:
        for row in rows:
            stream.write(canonical({
                "icon_id": row[0], "source_key": row[1], "stable_role": row[2],
                "source_path": row[3], "blob_sha256": row[4], "byte_size": row[5],
                "width": row[6], "height": row[7], "color_type": row[8],
            }) + b"\n")


def build(base: Path, run: Path, freeze_path: Path, reviews: list[Path],
          profile_path: Path, output: Path) -> dict:
    base = base.resolve(strict=True)
    run = run.resolve(strict=True)
    freeze_path = freeze_path.resolve(strict=True)
    reviews = [path.resolve(strict=True) for path in reviews]
    profile_path = profile_path.resolve(strict=True)
    output = output.resolve()
    if output.exists() or output.is_symlink():
        raise ValueError("--output must be a new directory")
    problems = validate(base, freeze=freeze_path)
    if problems:
        raise ValueError(f"base/freeze validation failed: {problems[:3]}")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if (sha256(base / "manifests" / "icon-identities.jsonl")
            != freeze.get("identity_registry_sha256")
            or sha256(base / "manifests" / "catalog.jsonl")
            != freeze.get("source_catalog_manifest_sha256")):
        raise ValueError("base does not match the frozen identity inputs")
    loaded = load_annotations(run, reviews)
    if (loaded["plan"].get("identity_registry_sha256") != freeze["identity_registry_sha256"]
            or loaded["plan"].get("candidate_catalog_manifest_sha256")
            != freeze["source_catalog_manifest_sha256"]):
        raise ValueError("annotation run is not pinned to the frozen candidate")
    profile = load_profile(profile_path)

    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.building-", dir=output.parent))
    try:
        (stage / "manifests").mkdir()
        shutil.copyfile(base / "catalog.sqlite", stage / "catalog.sqlite")
        for source in (base / "manifests").iterdir():
            if source.is_file() and source.name != "catalog.jsonl":
                shutil.copyfile(source, stage / "manifests" / source.name)
        link_tree(base / "assets", stage / "assets")
        connection = sqlite3.connect(stage / "catalog.sqlite")
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            thumbnail_sources = apply_corrections(connection, freeze)
            profile_sha256 = populate_search(connection, loaded, profile)
            if connection.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("candidate foreign key check failed")
            write_catalog_manifest(connection, stage / "manifests" / "catalog.jsonl")
            derivatives = connection.execute(
                "SELECT icon_id,relative_path FROM derivative ORDER BY icon_id").fetchall()
            connection.commit()
        finally:
            connection.close()
        for icon_id, relative in derivatives:
            source_relative = thumbnail_sources.get(icon_id, Path(relative))
            source = base / source_relative
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(source, target)

        correction_record = {
            "correction_schema_version": 1,
            "identity_freeze_sha256": sha256(freeze_path),
            "source_catalog_manifest_sha256": freeze["source_catalog_manifest_sha256"],
            "corrections": freeze["corrections"],
        }
        provenance = {
            "annotation_provenance_schema_version": 1,
            "raw_annotations_sha256": loaded["raw_annotations_sha256"],
            "accepted_annotations_sha256": loaded["accepted_annotations_sha256"],
            "review_chain_sha256": hashlib.sha256(canonical(loaded["review_chain"])).hexdigest(),
            "annotation_manifest_sha256": sha256(run / "icons.jsonl"),
            "annotation_plan_sha256": sha256(run / "plan.json"),
            "reviews": [{"sha256": sha256(path), "name": path.name} for path in reviews],
        }
        profile_record = {"search_profile_sha256": profile_sha256, "profile": profile}
        for name, value in (("rendition-corrections.json", correction_record),
                            ("annotation-provenance.json", provenance),
                            ("search-profile.json", profile_record)):
            (stage / "manifests" / name).write_bytes(canonical(value) + b"\n")
        problems = validate(stage, freeze=freeze_path)
        if problems:
            raise ValueError(f"built candidate failed validation: {problems[:5]}")
        if not stage_is_owned(stage, output) or output.exists() or output.is_symlink():
            raise ValueError("candidate target changed or stage is outside intended parent")
        os.replace(stage, output)
    except Exception:
        if stage_is_owned(stage, output):
            shutil.rmtree(stage)
        raise
    result = {
        "status": "annotated_search_candidate",
        "schema_version": SEARCH_SCHEMA_VERSION,
        "logical_icons": len(loaded["annotations"]),
        "search_profile_sha256": profile_sha256,
        "candidate": output.as_posix(),
    }
    print(json.dumps(result, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--review", type=Path, nargs="*", default=[])
    parser.add_argument("--profile", type=Path,
                        default=Path(__file__).with_name("search_profile_v1.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        build(args.base, args.run, args.freeze, args.review, args.profile, args.output)
    except (ValueError, OSError, sqlite3.Error, json.JSONDecodeError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
