"""Read-only integrity check for an Indexed Icon Pack candidate or release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import struct
import sys
import unicodedata
import uuid
from collections import defaultdict
from contextlib import closing
from pathlib import Path
from urllib.parse import quote

sys.dont_write_bytecode = True

HEX = re.compile(r"[0-9a-f]{64}\Z")
RELEASE_ID = re.compile(r"iip-r[0-9]{6,}\Z")
WINDOWS_ABSOLUTE = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\)")
FORBIDDEN_EDITOR = re.compile(r"(?i)(?:\bunity\b|(?:^|[_.\\/])guid(?:$|[_.\\/])|\.meta(?:$|[\\/]))")
EDITOR_GUID = re.compile(r"(?i)\b[0-9a-f]{32}\b")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
V2_FTS_COLUMNS = ("icon_id", "subject", "action", "state", "effect", "symbol", "color",
                  "material", "visible_text", "keywords", "description", "inferred_use",
                  "composition", "title", "collection")
V2_KEYWORD_FIELDS = {
    "keywords": "keyword", "subjects": "subject", "materials": "material",
    "colors": "color", "effects": "effect", "symbols": "symbol",
    "inferred_uses": "inferred_use", "uncertainties": "uncertainty",
}


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _valid_id(value: object, prefix: str) -> bool:
    if not isinstance(value, str) or not value.startswith(prefix):
        return False
    try:
        parsed = uuid.UUID(value[len(prefix) :])
    except (ValueError, AttributeError):
        return False
    return parsed.version == 4 and str(parsed) == value[len(prefix) :]


def _relative(root: Path, value: object, errors: list[str], label: str) -> Path | None:
    if not isinstance(value, str) or not value or "\\" in value or WINDOWS_ABSOLUTE.match(value):
        errors.append(f"{label}: invalid relative path {value!r}")
        return None
    parts = value.split("/")
    if value.startswith("/") or any(part in ("", ".", "..") for part in parts) or ":" in parts[0]:
        errors.append(f"{label}: invalid relative path {value!r}")
        return None
    target = root.joinpath(*parts)
    if not target.resolve().is_relative_to(root):
        errors.append(f"{label}: path escapes package: {value!r}")
        return None
    return target


def _scan_text(value: object, errors: list[str], label: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if FORBIDDEN_EDITOR.search(str(key)):
                errors.append(f"{label}: editor-specific field {key!r}")
            _scan_text(item, errors, f"{label}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _scan_text(item, errors, f"{label}[{index}]")
    elif isinstance(value, str):
        if WINDOWS_ABSOLUTE.search(value) or value.startswith(("file://", "/")):
            errors.append(f"{label}: absolute workstation path")
        if FORBIDDEN_EDITOR.search(value) or EDITOR_GUID.search(value):
            errors.append(f"{label}: editor-specific value")


def _json_file(path: Path, errors: list[str]) -> object | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"{path.name}: cannot read JSON: {exc}")
        return None
    _scan_text(value, errors, path.name)
    return value


def _registry(path: Path, errors: list[str]) -> tuple[bytes, list[dict]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        errors.append(f"identity registry: {exc}")
        return b"", []
    if not raw or not raw.endswith(b"\n") or b"\r" in raw:
        errors.append("identity registry must be nonempty canonical LF JSONL")
    events: list[dict] = []
    previous_hash: str | None = None
    seen_events: set[str] = set()
    seen_source_keys: set[tuple[str, str]] = set()
    assignments: dict[str, tuple[str, str]] = {}
    for number, line in enumerate(raw.splitlines(), 1):
        try:
            event = json.loads(line.decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            errors.append(f"identity event {number}: invalid JSON: {exc}")
            continue
        if not isinstance(event, dict):
            errors.append(f"identity event {number}: expected object")
            continue
        if json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() != line:
            errors.append(f"identity event {number}: not canonically encoded")
        _scan_text(event, errors, f"identity event {number}")
        if event.get("sequence") != number:
            errors.append(f"identity event {number}: sequence gap")
        if event.get("previous_event_sha256") != previous_hash:
            errors.append(f"identity event {number}: broken hash chain")
        if not _valid_id(event.get("event_id"), "event_"):
            errors.append(f"identity event {number}: invalid event ID")
        elif event["event_id"] in seen_events:
            errors.append(f"identity event {number}: repeated event ID")
        seen_events.add(event.get("event_id"))
        if not _valid_id(event.get("icon_id"), "icon_"):
            errors.append(f"identity event {number}: invalid icon ID")
        if not _valid_id(event.get("pack_id"), "pack_"):
            errors.append(f"identity event {number}: invalid pack ID")
        if not isinstance(event.get("evidence_sha256"), str) or not HEX.fullmatch(event["evidence_sha256"]):
            errors.append(f"identity event {number}: invalid evidence hash")
        if event.get("event_kind") == "assign":
            icon_id = event.get("icon_id")
            binding = (event.get("pack_id"), event.get("source_key"))
            if binding in seen_source_keys:
                errors.append(f"identity event {number}: repeated source binding")
            seen_source_keys.add(binding)
            if icon_id in assignments and assignments[icon_id] != binding:
                errors.append(f"identity event {number}: icon ID rebound")
            assignments[icon_id] = binding
        else:
            # ponytail: v1 knows assignment events only; extend with reviewed continuity events.
            errors.append(f"identity event {number}: unsupported event kind")
        previous_hash = hashlib.sha256(line).hexdigest()
        events.append(event)
    if len({e.get("icon_id") for e in events if e.get("event_kind") == "assign"}) != sum(
        e.get("event_kind") == "assign" for e in events
    ):
        errors.append("identity registry repeats an assignment")
    return raw, events


def _db_rows(connection: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    return connection.execute(f"SELECT * FROM {table}").fetchall()


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _v2_projection(icon: sqlite3.Row, accepted: dict) -> tuple[dict[str, str], set[tuple[str, str]]]:
    annotation = accepted.get("annotation")
    reviewed = accepted.get("reviewed_search_terms")
    list_fields = set(V2_KEYWORD_FIELDS) | {"subjects", "effects", "symbols", "colors", "materials"}
    if (not isinstance(annotation, dict) or not isinstance(reviewed, list)
            or any(not isinstance(annotation.get(field), list) for field in list_fields)
            or any(not isinstance(term, str) or not term.strip() for term in reviewed)):
        raise ValueError("invalid accepted observation JSON")
    values = {
        "icon_id": icon["icon_id"], "subject": "\n".join(annotation["subjects"]),
        "action": annotation.get("action") or "", "state": annotation.get("state") or "",
        "effect": "\n".join(annotation["effects"]),
        "symbol": "\n".join(annotation["symbols"]),
        "color": "\n".join(annotation["colors"]),
        "material": "\n".join(annotation["materials"]),
        "visible_text": annotation.get("visible_text") or "",
        "keywords": "\n".join([*annotation["keywords"], *reviewed]),
        "description": annotation.get("description"),
        "inferred_use": "\n".join(annotation["inferred_uses"]),
        "composition": annotation.get("composition"), "title": icon["title"],
        "collection": icon["collection"],
    }
    if any(not isinstance(value, str) for value in values.values()):
        raise ValueError("invalid accepted observation text")
    keywords = set()
    for field, namespace in V2_KEYWORD_FIELDS.items():
        keywords.update((namespace, _normalized(value)) for value in annotation[field])
    for field in ("action", "state", "visible_text"):
        if annotation.get(field):
            keywords.add((field, _normalized(annotation[field])))
    keywords.update(("reviewed_term", _normalized(value)) for value in reviewed)
    return values, keywords


def validate_identity_freeze(root: Path, freeze_path: Path, events: list[dict],
                             catalog_lines: list[dict], corrections_applied: bool = False) -> list[str]:
    errors: list[str] = []
    freeze = _json_file(freeze_path, errors)
    if not isinstance(freeze, dict):
        return errors + ["identity freeze must be a JSON object"]
    if freeze.get("freeze_schema_version") != 1 or freeze.get("status") != "frozen_ids_unpublished":
        errors.append("unsupported identity freeze")
    registry = root / "manifests/icon-identities.jsonl"
    catalog = root / "manifests/catalog.jsonl"
    if freeze.get("identity_registry_sha256") != _digest(registry):
        errors.append("frozen identity registry hash mismatch")
    if not corrections_applied and freeze.get("source_catalog_manifest_sha256") != _digest(catalog):
        errors.append("frozen source catalog hash mismatch")
    if freeze.get("identity_event_count") != len(events):
        errors.append("frozen identity count mismatch")
    if any(event.get("pack_id") != freeze.get("pack_id") or
           event.get("catalog_id") != freeze.get("catalog_id") for event in events):
        errors.append("frozen catalog/pack binding mismatch")
    assignments = {event.get("source_key"): event.get("icon_id") for event in events
                   if event.get("event_kind") == "assign"}
    rows = {row.get("source_path"): row for row in catalog_lines}
    corrections = freeze.get("corrections")
    if not isinstance(corrections, list) or len(corrections) != 4:
        return errors + ["identity freeze must list four reviewed corrections"]
    if corrections_applied:
        record_path = root / "manifests" / "rendition-corrections.json"
        record = _json_file(record_path, errors) if record_path.is_file() else None
        if (not isinstance(record, dict) or record.get("correction_schema_version") != 1
                or record.get("identity_freeze_sha256") != _digest(freeze_path)
                or record.get("source_catalog_manifest_sha256")
                != freeze.get("source_catalog_manifest_sha256")
                or record.get("corrections") != corrections):
            errors.append("rendition correction record does not match the identity freeze")
    sources, targets = set(), set()
    for correction in corrections:
        if not isinstance(correction, dict):
            errors.append("invalid identity correction")
            continue
        key = correction.get("source_key")
        icon_id = correction.get("icon_id")
        background_path = correction.get("background_source_path")
        matching_path = correction.get("matching_source_path")
        digest = correction.get("matching_blob_sha256")
        background = rows.get(background_path)
        matching = rows.get(matching_path)
        if (not isinstance(digest, str) or not HEX.fullmatch(digest)
                or assignments.get(key) != icon_id or key in targets or matching_path in sources
                or not background or not matching
                or background.get("source_key") != key or background.get("icon_id") != icon_id
                or background.get("stable_role") != "background"
                or matching.get("stable_role") != "transparent"
                or (matching.get("source_key") == key) != corrections_applied
                or (matching.get("icon_id") == icon_id) != corrections_applied
                or background.get("blob_sha256") != digest
                or matching.get("blob_sha256") != digest):
            errors.append(f"unproven identity correction: {key}")
        targets.add(key)
        sources.add(matching_path)
    return errors


def validate(package: Path, *, fast: bool = False, previous: Path | None = None,
             freeze: Path | None = None) -> list[str]:
    """Return all detected integrity errors; never modify the package."""
    errors: list[str] = []
    root = package.resolve()
    if not root.is_dir():
        return [f"package directory does not exist: {package}"]
    db_path = root / "catalog.sqlite"
    registry_path = root / "manifests" / "icon-identities.jsonl"
    for required in (db_path, registry_path):
        if not required.is_file():
            errors.append(f"missing required file: {required.relative_to(root).as_posix()}")
    if errors:
        return errors

    for path in root.rglob("*"):
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            errors.append(f"link or junction is not allowed: {path.relative_to(root).as_posix()}")
        if path.is_file() and (
            path.name.lower().endswith((".meta", ".unity", ".prefab", ".asset"))
            or path.name in ("catalog.sqlite-wal", "catalog.sqlite-shm")
        ):
            errors.append(f"editor/SQLite sidecar file is not allowed: {path.relative_to(root).as_posix()}")

    registry_bytes, events = _registry(registry_path, errors)
    anomalies = root / "manifests" / "anomalies.json"
    if anomalies.exists():
        _json_file(anomalies, errors)
    catalog_lines: list[dict] = []
    catalog_path = root / "manifests" / "catalog.jsonl"
    if not catalog_path.is_file():
        errors.append("missing manifests/catalog.jsonl")
    else:
        for number, line in enumerate(catalog_path.read_bytes().splitlines(), 1):
            try:
                row = json.loads(line.decode("utf-8"))
                if not isinstance(row, dict):
                    raise ValueError("expected an object")
                if json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() != line:
                    errors.append(f"catalog manifest line {number} is not canonical")
                _scan_text(row, errors, f"catalog manifest line {number}")
                catalog_lines.append(row)
            except (UnicodeError, ValueError) as exc:
                errors.append(f"invalid catalog manifest line {number}: {exc}")

    if freeze is not None:
        corrections_applied = (root / "manifests" / "rendition-corrections.json").is_file()
        errors.extend(validate_identity_freeze(
            root, freeze, events, catalog_lines, corrections_applied=corrections_applied))

    manifest_path = root / "manifests" / "release.json"
    manifest = _json_file(manifest_path, errors) if manifest_path.exists() else None
    if manifest_path.exists() and not isinstance(manifest, dict):
        errors.append("release manifest must be a JSON object")

    uri = "file:" + quote(db_path.as_posix(), safe="/:") + "?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        return errors + [f"cannot open SQLite read-only: {exc}"]
    icon_by_id: dict[str, sqlite3.Row] = {}
    history: set[tuple[str, str, str]] = set()
    blob_by_hash: dict[str, sqlite3.Row] = {}
    try:
        schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
        if schema_version not in (1, 2):
            errors.append("unsupported SQLite user_version")
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            errors.append("SQLite integrity_check failed")
        if connection.execute("PRAGMA foreign_key_check").fetchone():
            errors.append("SQLite foreign_key_check failed")
        required_tables = {
            "catalog_state", "icon", "blob", "rendition", "rendition_history", "derivative", "icon_keyword", "icon_fts"
        }
        if schema_version == 2:
            required_tables.update({"icon_observation", "search_profile", "icon_fts_vocab",
                                    "icon_fts_instance"})
        existing = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = required_tables - existing
        if missing:
            errors.append(f"missing tables: {', '.join(sorted(missing))}")
            return errors
        for row in connection.execute("SELECT name,sql FROM sqlite_master WHERE sql IS NOT NULL"):
            if FORBIDDEN_EDITOR.search(row["name"]) or FORBIDDEN_EDITOR.search(row["sql"]):
                errors.append(f"editor-specific SQLite schema: {row['name']}")
        for table in sorted(required_tables - {"icon_fts", "icon_fts_vocab", "icon_fts_instance"}):
            for row in _db_rows(connection, table):
                _scan_text(dict(row), errors, f"SQLite {table}")

        state = _db_rows(connection, "catalog_state")
        if len(state) != 1:
            errors.append("catalog_state must contain exactly one row")
        else:
            if state[0]["catalog_id"] != "indexed-icon-pack":
                errors.append("unexpected catalog ID")
            if not _valid_id(state[0]["pack_id"], "pack_"):
                errors.append("invalid catalog pack ID")
            if state[0]["schema_version"] != schema_version:
                errors.append("catalog_state schema_version mismatch")
            if any(e.get("catalog_id") != state[0]["catalog_id"] for e in events):
                errors.append("identity registry catalog_id mismatch")
            expected_state = {1: "pending_model_choice", 2: "annotated_search_candidate"}.get(schema_version)
            if manifest is None and state[0]["annotation_status"] != expected_state:
                errors.append("unpublished candidate has an unexpected annotation state")
            if manifest is not None and state[0]["annotation_status"] == "pending_model_choice":
                errors.append("release manifest cannot publish a pre-annotation candidate")
        icons = _db_rows(connection, "icon")
        icon_by_id = {row["icon_id"]: row for row in icons}
        if len(icon_by_id) != len(icons):
            errors.append("duplicate icon ID")
        assignments = {event.get("icon_id"): event for event in events if event.get("event_kind") == "assign"}
        if set(assignments) != set(icon_by_id):
            errors.append("registry assignment IDs do not match SQLite icon IDs")
        for icon in icons:
            icon_id = icon["icon_id"]
            if not _valid_id(icon_id, "icon_"):
                errors.append(f"invalid SQLite icon ID: {icon_id}")
            event = assignments.get(icon_id)
            if event and (event.get("pack_id"), event.get("source_key")) != (icon["pack_id"], icon["source_key"]):
                errors.append(f"registry/SQLite binding mismatch: {icon_id}")
            if state and icon["pack_id"] != state[0]["pack_id"]:
                errors.append(f"catalog_state pack mismatch: {icon_id}")
            if state and state[0]["annotation_status"] == "pending_model_choice" and icon["description"]:
                errors.append(f"pre-annotation icon unexpectedly has a description: {icon_id}")
        if state and state[0]["annotation_status"] == "pending_model_choice" and _db_rows(connection, "icon_keyword"):
            errors.append("pre-annotation catalog unexpectedly has visual keywords")

        blob_rows = _db_rows(connection, "blob")
        blob_by_hash = {row["sha256"]: row for row in blob_rows}
        recorded_assets: set[Path] = set()
        for blob in blob_rows:
            sha = blob["sha256"]
            if not isinstance(sha, str) or not HEX.fullmatch(sha):
                errors.append(f"invalid blob hash: {sha!r}")
                continue
            expected = f"assets/sha256/{sha[:2]}/{sha}.png"
            if blob["relative_path"] != expected:
                errors.append(f"blob path is not content-addressed: {sha}")
            target = _relative(root, blob["relative_path"], errors, f"blob {sha}")
            if target is None:
                continue
            recorded_assets.add(target)
            if not target.is_file():
                errors.append(f"missing blob: {expected}")
                continue
            if target.stat().st_size != blob["byte_size"]:
                errors.append(f"blob byte size mismatch: {sha}")
            with target.open("rb") as stream:
                header = stream.read(33)
            if len(header) < 33 or header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR" or header[8:12] != b"\0\0\0\r":
                errors.append(f"invalid PNG header: {sha}")
            else:
                width, height = struct.unpack(">II", header[16:24])
                if not width or not height or header[25] not in (0, 2, 3, 4, 6):
                    errors.append(f"invalid PNG dimensions or color type: {sha}")
                if (width, height, header[25]) != (blob["width"], blob["height"], blob["color_type"]):
                    errors.append(f"PNG metadata mismatch: {sha}")
            if not fast and _digest(target) != sha:
                errors.append(f"blob SHA-256 mismatch: {sha}")
        assets_root = root / "assets" / "sha256"
        if assets_root.is_dir():
            for asset in assets_root.rglob("*"):
                if asset.is_file() and asset not in recorded_assets:
                    errors.append(f"unindexed asset: {asset.relative_to(root).as_posix()}")

        rendition_rows = _db_rows(connection, "rendition")
        current = {(row["icon_id"], row["blob_sha256"], row["stable_role"]) for row in rendition_rows}
        by_icon: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for row in rendition_rows:
            by_icon[row["icon_id"]].append(row)
        history = {(row["icon_id"], row["blob_sha256"], row["stable_role"]) for row in _db_rows(connection, "rendition_history")}
        if not current.issubset(history):
            errors.append("current rendition is missing from rendition_history")
        for icon_id, sha, role in history:
            if icon_id not in icon_by_id or sha not in blob_by_hash:
                errors.append(f"orphan rendition history: {icon_id}/{role}/{sha}")
        for icon in icons:
            if not any(row["stable_role"] == icon["preferred_role"] for row in by_icon[icon["icon_id"]]):
                errors.append(f"preferred rendition missing: {icon['icon_id']}")
        fts_rows = _db_rows(connection, "icon_fts")
        fts_ids = [row["icon_id"] for row in fts_rows]
        if len(fts_ids) != len(icons) or set(fts_ids) != set(icon_by_id):
            errors.append("FTS projection does not match icon table")
        for row in fts_rows:
            icon = icon_by_id.get(row["icon_id"])
            if icon and (row["title"], row["collection"], row["description"]) != (
                icon["title"], icon["collection"], icon["description"]
            ):
                errors.append(f"FTS text mismatch: {row['icon_id']}")
        if schema_version == 2:
            observation_rows = _db_rows(connection, "icon_observation")
            observation_by_id = {row["icon_id"]: row for row in observation_rows}
            if len(observation_rows) != len(icons) or set(observation_by_id) != set(icon_by_id):
                errors.append("accepted observations do not match icon table")
            fts_by_id = {row["icon_id"]: row for row in fts_rows}
            keywords_by_id: dict[str, set[tuple[str, str]]] = defaultdict(set)
            for row in _db_rows(connection, "icon_keyword"):
                keywords_by_id[row["icon_id"]].add((row["namespace"], row["value"]))
            accepted_digest = hashlib.sha256()
            raw_digests, accepted_digests, review_digests = set(), set(), set()
            for icon_id in sorted(observation_by_id):
                row = observation_by_id[icon_id]
                icon = icon_by_id[icon_id]
                try:
                    accepted = json.loads(row["observation_json"])
                    if row["observation_json"] != _canonical(accepted):
                        errors.append(f"accepted observation is not canonical: {icon_id}")
                    projection, expected_keywords = _v2_projection(icon, accepted)
                    fts = fts_by_id.get(icon_id)
                    if fts is None or any(fts[column] != projection[column]
                                          for column in V2_FTS_COLUMNS):
                        errors.append(f"structured FTS projection mismatch: {icon_id}")
                    if keywords_by_id[icon_id] != expected_keywords:
                        errors.append(f"structured facet projection mismatch: {icon_id}")
                    if icon["description"] != projection["description"]:
                        errors.append(f"accepted description mismatch: {icon_id}")
                    accepted_digest.update(_canonical({"icon_id": icon_id, **accepted}).encode("utf-8") + b"\n")
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    errors.append(f"invalid accepted observation {icon_id}: {exc}")
                preferred = next((item for item in by_icon[icon_id]
                                  if item["stable_role"] == icon["preferred_role"]), None)
                if preferred is None or preferred["blob_sha256"] != row["source_blob_sha256"]:
                    errors.append(f"observation source does not match preferred rendition: {icon_id}")
                if row["observation_schema_version"] != 1:
                    errors.append(f"unsupported observation schema: {icon_id}")
                for value, bucket, label in (
                    (row["raw_annotations_sha256"], raw_digests, "raw annotation"),
                    (row["accepted_annotations_sha256"], accepted_digests, "accepted annotation"),
                    (row["review_chain_sha256"], review_digests, "review chain"),
                ):
                    if not isinstance(value, str) or not HEX.fullmatch(value):
                        errors.append(f"invalid {label} hash: {icon_id}")
                    bucket.add(value)
            if len(raw_digests) != 1 or len(accepted_digests) != 1 or len(review_digests) != 1:
                errors.append("observation provenance is not uniform across the candidate")
            elif accepted_digests != {accepted_digest.hexdigest()}:
                errors.append("accepted annotation digest does not match projected observations")

            profiles = _db_rows(connection, "search_profile")
            profile = None
            if len(profiles) != 1:
                errors.append("search candidate must contain exactly one search profile")
            else:
                profile_row = profiles[0]
                try:
                    profile = json.loads(profile_row["profile_json"])
                    actual_profile_sha = hashlib.sha256(profile_row["profile_json"].encode()).hexdigest()
                    if (profile_row["profile_json"] != _canonical(profile)
                            or profile_row["profile_sha256"] != actual_profile_sha
                            or not HEX.fullmatch(profile_row["profile_sha256"])):
                        errors.append("search profile JSON or digest mismatch")
                    if (profile.get("profile_id") != profile_row["profile_id"]
                            or profile.get("schema_version") != 2
                            or tuple(profile.get("fts_columns", ())) != V2_FTS_COLUMNS
                            or set(profile.get("bm25_weights", {})) != set(V2_FTS_COLUMNS)):
                        errors.append("search profile does not match schema-v2 FTS")
                    fts_columns = tuple(row[1] for row in connection.execute("PRAGMA table_info(icon_fts)"))
                    fts_sql = connection.execute(
                        "SELECT sql FROM sqlite_master WHERE name='icon_fts'").fetchone()[0]
                    if fts_columns != V2_FTS_COLUMNS or profile.get("tokenizer") not in fts_sql:
                        errors.append("persisted FTS tokenizer or columns differ from search profile")
                except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
                    errors.append(f"invalid search profile: {exc}")
            profile_manifest_path = root / "manifests" / "search-profile.json"
            profile_manifest = (_json_file(profile_manifest_path, errors)
                                if profile_manifest_path.is_file() else None)
            if (not isinstance(profile_manifest, dict) or not profiles
                    or profile_manifest.get("search_profile_sha256") != profiles[0]["profile_sha256"]
                    or profile_manifest.get("profile") != profile):
                errors.append("search profile manifest does not match SQLite")
            provenance_path = root / "manifests" / "annotation-provenance.json"
            provenance = _json_file(provenance_path, errors) if provenance_path.is_file() else None
            if (not isinstance(provenance, dict)
                    or provenance.get("annotation_provenance_schema_version") != 1
                    or provenance.get("raw_annotations_sha256") not in raw_digests
                    or provenance.get("accepted_annotations_sha256") not in accepted_digests
                    or provenance.get("review_chain_sha256") not in review_digests):
                errors.append("annotation provenance manifest does not match SQLite")
        for row in rendition_rows:
            _relative(root, row["source_path"], errors, f"source path {row['icon_id']}")
        if len({row["source_path"] for row in rendition_rows}) != len(rendition_rows):
            errors.append("source path appears in more than one rendition")
        if len({unicodedata.normalize("NFC", row["source_path"]).casefold() for row in rendition_rows}) != len(rendition_rows):
            errors.append("source paths collide after case/Unicode normalization")
        expected_catalog = []
        for row in rendition_rows:
            icon = icon_by_id[row["icon_id"]]
            blob = blob_by_hash[row["blob_sha256"]]
            expected_catalog.append({
                "icon_id": row["icon_id"], "source_key": icon["source_key"],
                "stable_role": row["stable_role"], "source_path": row["source_path"],
                "blob_sha256": row["blob_sha256"], "byte_size": blob["byte_size"],
                "width": blob["width"], "height": blob["height"], "color_type": blob["color_type"],
            })
        if catalog_lines != sorted(expected_catalog, key=lambda row: (row["source_key"], row["stable_role"])):
            errors.append("catalog manifest does not match SQLite renditions")
        if state and state[0]["annotation_status"] == "pending_model_choice":
            for icon_id, event in assignments.items():
                evidence = [
                    {"role": row["stable_role"], "sha256": row["blob_sha256"], "source_path": row["source_path"]}
                    for row in sorted(by_icon[icon_id], key=lambda r: r["stable_role"])
                ]
                actual = hashlib.sha256(json.dumps(evidence, ensure_ascii=False, sort_keys=True,
                                                  separators=(",", ":")).encode()).hexdigest()
                if event.get("evidence_sha256") != actual:
                    errors.append(f"identity evidence mismatch: {icon_id}")
        recorded_thumbnails: set[Path] = set()
        derivatives = _db_rows(connection, "derivative")
        if len(derivatives) != len(icons):
            errors.append("thumbnail count does not match icon count")
        for derivative in derivatives:
            icon_id = derivative["icon_id"]
            expected = f"thumbnails/{icon_id}.png"
            if derivative["relative_path"] != expected:
                errors.append(f"invalid thumbnail path: {icon_id}")
            target = _relative(root, derivative["relative_path"], errors, f"thumbnail {icon_id}")
            if target is None:
                continue
            recorded_thumbnails.add(target)
            if not target.is_file():
                errors.append(f"missing thumbnail: {icon_id}")
            else:
                with target.open("rb") as stream:
                    header = stream.read(26)
                if len(header) < 26 or header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
                    errors.append(f"invalid thumbnail PNG: {icon_id}")
                elif struct.unpack(">II", header[16:24]) != (derivative["width"], derivative["height"]):
                    errors.append(f"thumbnail dimensions mismatch: {icon_id}")
                if not fast and _digest(target) != derivative["sha256"]:
                    errors.append(f"thumbnail SHA-256 mismatch: {icon_id}")
            icon = icon_by_id.get(icon_id)
            if icon and (icon_id, derivative["source_blob_sha256"], icon["preferred_role"]) not in current:
                errors.append(f"thumbnail source is not the preferred rendition: {icon_id}")
        thumbnail_root = root / "thumbnails"
        if thumbnail_root.is_dir():
            for file in thumbnail_root.rglob("*"):
                if file.is_file() and file not in recorded_thumbnails:
                    errors.append(f"unindexed thumbnail: {file.relative_to(root).as_posix()}")

        if manifest is not None and isinstance(manifest, dict):
            if (manifest.get("manifest_schema_version") != 1
                    or manifest.get("schema_version") != schema_version):
                errors.append("release manifest schema version mismatch")
            if not RELEASE_ID.fullmatch(str(manifest.get("release_id", ""))):
                errors.append("invalid release ID")
            if state and manifest.get("catalog_id") != state[0]["catalog_id"]:
                errors.append("release catalog_id mismatch")
            if manifest.get("identity_registry_sha256") != f"sha256:{hashlib.sha256(registry_bytes).hexdigest()}":
                errors.append("release identity registry hash mismatch")
            revision = manifest.get("catalog_revision")
            if not isinstance(revision, str) or not revision.startswith("sha256:") or not HEX.fullmatch(revision[7:]):
                errors.append("invalid logical catalog revision")
            if schema_version == 2:
                from catalog_revision import catalog_revision
                expected_revision, revision_record = catalog_revision(root, connection)
                if revision != expected_revision:
                    errors.append("logical catalog revision does not match canonical inputs")
                if _json_file(root / "manifests" / "catalog-revision.json", errors) != revision_record:
                    errors.append("logical catalog revision input record mismatch")
                if not profiles or manifest.get("search_profile_sha256") != "sha256:" + profiles[0]["profile_sha256"]:
                    errors.append("release search profile hash mismatch")
            event_range = manifest.get("identity_event_range")
            if event_range is not None and (
                not isinstance(event_range, dict)
                or not isinstance(event_range.get("first"), int)
                or not isinstance(event_range.get("last"), int)
                or event_range["first"] < 1
                or event_range["last"] > len(events)
                or event_range["first"] > event_range["last"]
            ):
                errors.append("invalid release identity event range")
            if manifest.get("predecessor_release_id") is None and event_range != {"first": 1, "last": len(events)}:
                errors.append("first release must bind the complete identity event range")
            payload = manifest.get("payload")
            if not isinstance(payload, list):
                errors.append("release payload must be an array")
            else:
                listed: set[str] = set()
                for entry in payload:
                    if not isinstance(entry, dict):
                        errors.append("release payload entry must be an object")
                        continue
                    name = entry.get("path")
                    target = _relative(root, name, errors, "release payload")
                    if target is None:
                        continue
                    if name in listed:
                        errors.append(f"duplicate release payload path: {name}")
                    listed.add(name)
                    if not target.is_file():
                        errors.append(f"missing release payload: {name}")
                        continue
                    if target.stat().st_size != entry.get("size"):
                        errors.append(f"release payload size mismatch: {name}")
                    expected_hash = entry.get("sha256")
                    if not isinstance(expected_hash, str) or not expected_hash.startswith("sha256:") or not HEX.fullmatch(expected_hash[7:]):
                        errors.append(f"invalid release payload hash: {name}")
                    elif not fast and _digest(target) != expected_hash[7:]:
                        errors.append(f"release payload hash mismatch: {name}")
                names = [entry.get("path") for entry in payload if isinstance(entry, dict)]
                if names != sorted(names):
                    errors.append("release payload is not sorted by path")
                actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
                actual.discard("manifests/release.json")
                if listed != actual:
                    errors.append(f"release payload file set mismatch: missing={sorted(actual - listed)[:5]}, extra={sorted(listed - actual)[:5]}")
    except (OSError, sqlite3.Error, KeyError, TypeError, ValueError) as exc:
        errors.append(f"cannot complete SQLite validation: {exc}")
    finally:
        connection.close()

    if previous is not None:
        prior_root = previous.resolve()
        prior_ledger = prior_root / "manifests" / "icon-identities.jsonl"
        if not prior_ledger.is_file():
            errors.append("previous registry is missing")
        else:
            old_bytes, _ = _registry(prior_ledger, errors)
            if not registry_bytes.startswith(old_bytes):
                errors.append("identity registry does not retain previous ledger as exact prefix")
            old_db = prior_root / "catalog.sqlite"
            if old_db.is_file():
                old_uri = "file:" + quote(old_db.as_posix(), safe="/:") + "?mode=ro"
                try:
                    with closing(sqlite3.connect(old_uri, uri=True)) as prior_connection:
                        old_ids = {row[0] for row in prior_connection.execute("SELECT icon_id FROM icon")}
                        old_history = set(prior_connection.execute("SELECT icon_id,blob_sha256,stable_role FROM rendition_history"))
                        old_blobs = {row[0] for row in prior_connection.execute("SELECT sha256 FROM blob")}
                    if not old_ids.issubset(set(icon_by_id)):
                        errors.append("candidate removed a previous icon ID")
                    if not old_history.issubset(history):
                        errors.append("candidate removed a previous icon-to-blob association")
                    if not old_blobs.issubset(set(blob_by_hash)):
                        errors.append("candidate removed a previous blob")
                except sqlite3.Error as exc:
                    errors.append(f"cannot inspect previous catalog: {exc}")
        prior_manifest_path = prior_root / "manifests" / "release.json"
        if isinstance(manifest, dict) and prior_manifest_path.is_file():
            prior_manifest = _json_file(prior_manifest_path, errors)
            if isinstance(prior_manifest, dict):
                if manifest.get("predecessor_release_id") != prior_manifest.get("release_id"):
                    errors.append("release predecessor ID mismatch")
                expected = "sha256:" + _digest(prior_manifest_path)
                if manifest.get("predecessor_release_manifest_sha256") != expected:
                    errors.append("release predecessor manifest hash mismatch")
                old_id = prior_manifest.get("release_id", "")
                new_id = manifest.get("release_id", "")
                if RELEASE_ID.fullmatch(str(old_id)) and RELEASE_ID.fullmatch(str(new_id)):
                    if int(new_id[5:]) <= int(old_id[5:]):
                        errors.append("release ID did not advance")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--fast", action="store_true", help="Skip full file hashes; still check paths, headers, schema, and sizes")
    parser.add_argument("--freeze", type=Path, help="Check the reviewed pre-release ID freeze against this candidate")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    problems = validate(args.package, fast=args.fast, previous=args.previous, freeze=args.freeze)
    has_manifest = (args.package / "manifests" / "release.json").is_file()
    result = {"ok": not problems, "package_status": "release_manifest_present" if has_manifest else "unreleased", "errors": problems}
    if args.json:
        print(json.dumps(result, separators=(",", ":")))
    else:
        print(f"{result['package_status']}: {'valid' if result['ok'] else 'INVALID'}")
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
