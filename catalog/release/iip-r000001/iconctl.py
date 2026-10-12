#!/usr/bin/env python3
"""Read-only search, inspection, and verified export for Indexed Icon Pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, unquote, urlsplit


CATALOG_ID = "indexed-icon-pack"
HEX = re.compile(r"[0-9a-f]{64}\Z")
ICON_ID = re.compile(r"icon_[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")
SUPPORTED_SCHEMA_VERSIONS = (1, 2)
SEARCH_STOPWORDS = frozenset({"a", "an", "and", "for", "from", "in", "of", "on", "the", "to", "with"})
REQUIRE_FIELDS = frozenset({"subject", "action", "state", "effect", "symbol", "color", "material"})


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def safe_file(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise ValueError("invalid package-relative path")
    part = PurePosixPath(relative)
    if part.is_absolute() or any(segment in (".", "..", "") for segment in relative.split("/")):
        raise ValueError("invalid package-relative path")
    path = (root / Path(*part.parts)).resolve(strict=True)
    if not path.is_relative_to(root.resolve()):
        raise ValueError("package path escapes its root")
    if not path.is_file():
        raise ValueError("package path is not a file")
    return path


def sha_value(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("expected a lowercase SHA-256 digest")
    bare = value.removeprefix("sha256:")
    if not HEX.fullmatch(bare):
        raise ValueError("expected a lowercase SHA-256 digest")
    return bare


def release_info(root: Path, schema_version: int) -> tuple[dict, dict[str, dict]]:
    manifest_path = root / "manifests" / "release.json"
    if not manifest_path.exists():
        return {
            "catalog_id": CATALOG_ID,
            "release_id": None,
            "catalog_revision": None,
            "schema_version": schema_version,
            "release_manifest_sha256": None,
            "package_status": "unreleased",
        }, {}
    manifest_path = safe_file(root, "manifests/release.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("invalid release manifest")
    if manifest.get("manifest_schema_version") != 1:
        raise ValueError("unsupported release manifest schema")
    if manifest.get("catalog_id") != CATALOG_ID or manifest.get("schema_version") != schema_version:
        raise ValueError("release manifest catalog or schema mismatch")
    if not re.fullmatch(r"iip-r[0-9]{6,}", str(manifest.get("release_id", ""))):
        raise ValueError("invalid release ID")
    sha_value(manifest.get("catalog_revision", ""))
    payload = manifest.get("payload")
    if not isinstance(payload, list):
        raise ValueError("release manifest has no payload inventory")
    inventory = {}
    for entry in payload:
        if (not isinstance(entry, dict) or type(entry.get("size")) is not int
                or entry["size"] < 0):
            raise ValueError("invalid release payload entry")
        relative = entry.get("path")
        if (not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative
                or PurePosixPath(relative).is_absolute()
                or any(part in ("", ".", "..") for part in relative.split("/"))):
            raise ValueError("invalid release payload path")
        if relative in inventory or relative == "manifests/release.json":
            raise ValueError("duplicate or self-referential release payload")
        sha_value(entry.get("sha256", ""))
        inventory[relative] = entry
    db_entry = inventory.get("catalog.sqlite")
    if db_entry is None or db_entry["sha256"] != "sha256:" + digest(root / "catalog.sqlite"):
        raise ValueError("release database hash does not match its manifest")
    if db_entry["size"] != (root / "catalog.sqlite").stat().st_size:
        raise ValueError("release database size does not match its manifest")
    return {
        "catalog_id": CATALOG_ID,
        "release_id": manifest["release_id"],
        "catalog_revision": manifest["catalog_revision"],
        "schema_version": schema_version,
        "release_manifest_sha256": "sha256:" + digest(manifest_path),
        "package_status": "release_manifest_present",
    }, inventory


def open_catalog(root: Path) -> tuple[sqlite3.Connection, dict, dict[str, dict]]:
    root = root.resolve(strict=True)
    database = safe_file(root, "catalog.sqlite")
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
        schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
        if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(f"unsupported catalog schema version {schema_version}")
        state = connection.execute(
            "SELECT catalog_id, schema_version, annotation_status FROM catalog_state"
        ).fetchone()
        if state is None or state["catalog_id"] != CATALOG_ID or state["schema_version"] != schema_version:
            raise ValueError("catalog identity or schema mismatch")
        version, inventory = release_info(root, schema_version)
        if version["package_status"] == "release_manifest_present" and state["annotation_status"] == "pending_model_choice":
            raise ValueError("release manifest cannot package a pre-annotation catalog")
        version["annotation_status"] = state["annotation_status"]
        if schema_version == 2:
            profile = connection.execute(
                "SELECT profile_id,profile_sha256,profile_json FROM search_profile").fetchall()
            if len(profile) != 1:
                raise ValueError("catalog must contain exactly one search profile")
            parsed = json.loads(profile[0]["profile_json"])
            if (hashlib.sha256(profile[0]["profile_json"].encode()).hexdigest()
                    != profile[0]["profile_sha256"] or parsed.get("profile_id") != profile[0]["profile_id"]):
                raise ValueError("invalid catalog search profile")
            version["search_profile_id"] = profile[0]["profile_id"]
            version["search_profile_sha256"] = "sha256:" + profile[0]["profile_sha256"]
        else:
            version["search_profile_id"] = None
            version["search_profile_sha256"] = None
        return connection, version, inventory
    except Exception:
        connection.close()
        raise


def legacy_search_icons(connection: sqlite3.Connection, query: str, limit: int = 12,
                        collection: str | None = None, role: str | None = None) -> list[dict]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    if role is not None and role not in ("transparent", "default", "background"):
        raise ValueError("invalid rendition role")
    terms = [term for term in dict.fromkeys(re.findall(r"\w+", query.casefold(), re.UNICODE))
             if term not in SEARCH_STOPWORDS][:16]
    filters = ["i.lifecycle_status != 'retired'"]
    args: list[object] = []
    if collection:
        filters.append("i.collection = ?")
        args.append(collection)
    if role:
        filters.append("EXISTS (SELECT 1 FROM rendition r WHERE r.icon_id = i.icon_id AND r.stable_role = ?)")
        args.append(role)
    coverage = Counter()
    if terms:
        expression = " OR ".join(f'"{term}"' for term in terms)
        # ponytail: Rank the full OR candidate set in memory for this 6,250-icon pack;
        # move term coverage into an indexed search service if catalogs grow much larger.
        rows = connection.execute(
            "SELECT i.icon_id, i.title, i.collection, i.description, i.preferred_role, "
            "i.lifecycle_status, bm25(icon_fts, 0, 3, 2, 4, 1) AS score "
            "FROM icon_fts JOIN icon i ON i.icon_id = icon_fts.icon_id "
            "WHERE icon_fts MATCH ? AND " + " AND ".join(filters), [expression, *args]
        ).fetchall()
        if len(terms) == 1:
            coverage.update(row["icon_id"] for row in rows)
        else:
            candidate_ids = {row["icon_id"] for row in rows}
            for term in terms:
                coverage.update(icon_id for (icon_id,) in connection.execute(
                    "SELECT icon_id FROM icon_fts WHERE icon_fts MATCH ?", (f'"{term}"',))
                    if icon_id in candidate_ids)
        rows = sorted(rows, key=lambda row: (-coverage[row["icon_id"]], row["score"], row["icon_id"]))[:limit]
    else:
        rows = connection.execute(
            "SELECT i.icon_id, i.title, i.collection, i.description, i.preferred_role, "
            "i.lifecycle_status FROM icon i WHERE " + " AND ".join(filters) +
            " ORDER BY i.collection, i.ordinal, i.icon_id LIMIT ?", [*args, limit]
        ).fetchall()
    return [dict(row) | {"matched_query_terms": coverage[row["icon_id"]] if terms else 0,
                         "query_term_count": len(terms),
                         "thumbnail_url": "/api/v1/thumbnails/" + row["icon_id"]} for row in rows]


def _fts_quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _search_profile(connection: sqlite3.Connection) -> tuple[dict, str]:
    row = connection.execute("SELECT profile_sha256,profile_json FROM search_profile").fetchone()
    if row is None:
        raise ValueError("structured search requires a schema-v2 catalog")
    profile = json.loads(row["profile_json"])
    if hashlib.sha256(row["profile_json"].encode()).hexdigest() != row["profile_sha256"]:
        raise ValueError("search profile digest mismatch")
    return profile, row["profile_sha256"]


def _validate_fts_query(value: str | None, profile: dict) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("query must be a nonblank FTS5 expression")
    value = value.strip()
    limits = profile["request_limits"]
    if len(value) > limits["fts_expression_chars"] or "\0" in value:
        raise ValueError("query exceeds the FTS expression size limit")
    if len(re.findall(r"\w+|[()\"*:+-]", value, re.UNICODE)) > limits["fts_expression_tokens"]:
        raise ValueError("query exceeds the FTS expression complexity limit")
    unquoted = re.sub(r'"(?:[^"]|"")*"', "", value)
    fields = set(re.findall(r"(?<![\w])([A-Za-z_][A-Za-z0-9_]*)\s*:", unquoted))
    searchable = set(profile["fts_columns"]) - {"icon_id"}
    unsupported = fields - searchable
    if unsupported:
        raise ValueError("unsupported FTS field(s): " + ", ".join(sorted(unsupported)))
    return value


def _alias_values(field: str, value: str, profile: dict) -> list[str]:
    value = " ".join(value.casefold().split())
    for canonical, aliases in profile.get("alias_map", {}).get(field, {}).items():
        choices = [canonical, *aliases]
        if value in choices:
            return sorted(set(choices))
    return [value]


def _required_expression(require: dict | None, profile: dict) -> tuple[str | None, dict[str, list[str]]]:
    if require is None:
        return None, {}
    if not isinstance(require, dict) or any(field not in REQUIRE_FIELDS for field in require):
        raise ValueError("require fields must be subject, action, state, effect, symbol, color, or material")
    normalized = {}
    total = 0
    clauses = []
    for field in sorted(require):
        values = require[field]
        if (not isinstance(values, (list, tuple)) or not values
                or any(not isinstance(value, str) or not value.strip() or len(value) > 80
                       or "\0" in value for value in values)):
            raise ValueError(f"require.{field} must be a nonempty list of short text values")
        supplied = list(dict.fromkeys(" ".join(value.casefold().split()) for value in values))
        total += len(supplied)
        expanded = sorted({alias for value in supplied for alias in _alias_values(field, value, profile)})
        normalized[field] = supplied
        clauses.append(f"{field}: (" + " OR ".join(_fts_quote(value) for value in expanded) + ")")
    if total > profile["request_limits"]["require_values"]:
        raise ValueError("require has too many values")
    return " AND ".join(f"({clause})" for clause in clauses), normalized


def _ordinary_expression(text: str | None, profile: dict) -> tuple[str | None, list[str]]:
    if text is None:
        return None, []
    if not isinstance(text, str) or len(text) > profile["request_limits"]["text_chars"] or "\0" in text:
        raise ValueError("text exceeds the search text size limit")
    if not text.strip():
        return None, []
    terms = [term for term in dict.fromkeys(re.findall(r"\w+", text.casefold(), re.UNICODE))
             if term not in SEARCH_STOPWORDS]
    if not terms:
        raise ValueError("text contains no searchable terms")
    if len(terms) > profile["request_limits"]["text_terms"]:
        raise ValueError("text has too many terms")
    return " OR ".join(_fts_quote(term) for term in terms), terms


def _seed_expression(connection: sqlite3.Connection, icon_id: str, profile: dict,
                     overridden_fields: set[str]) -> tuple[str | None, list[dict]]:
    row = connection.execute(
        "SELECT f.rowid,i.lifecycle_status FROM icon_fts f JOIN icon i USING(icon_id) "
        "WHERE f.icon_id=?", (icon_id,)).fetchone()
    if row is None:
        raise LookupError("similarity seed not found")
    if row["lifecycle_status"] == "retired":
        raise ValueError("similarity seed is retired")
    columns = [field for field in profile["seed"]["columns"] if field not in overridden_fields]
    if not columns:
        return None, []
    placeholders = ",".join("?" for _ in columns)
    instances = connection.execute(
        f"SELECT term,col FROM icon_fts_instance WHERE doc=? AND col IN ({placeholders})",
        (row["rowid"], *columns)).fetchall()
    total = connection.execute("SELECT count(*) FROM icon").fetchone()[0]
    generic = set(profile["seed"]["generic_terms"])
    priority = {column: len(columns) - index for index, column in enumerate(columns)}
    candidates = {}
    for instance in instances:
        term, column = instance["term"], instance["col"]
        if term in generic:
            continue
        frequency = connection.execute(
            "SELECT doc FROM icon_fts_vocab WHERE term=?", (term,)).fetchone()
        if frequency is None or frequency[0] / total > profile["seed"]["max_document_frequency_ratio"]:
            continue
        score = priority[column] * math.log((total + 1) / (frequency[0] + 1))
        existing = candidates.get((column, term))
        if existing is None or score > existing:
            candidates[(column, term)] = score
    selected = sorted(candidates, key=lambda item: (-candidates[item], item[0], item[1]))[
        :profile["seed"]["max_terms"]]
    terms = [{"field": column, "term": term} for column, term in selected]
    expression = " OR ".join(f"{item['field']}: {_fts_quote(item['term'])}" for item in terms)
    return expression or None, terms


def _combined(*expressions: str | None) -> str | None:
    values = [expression for expression in expressions if expression]
    return " AND ".join(f"({expression})" for expression in values) if values else None


def _rank_channel(connection: sqlite3.Connection, expression: str, filters: list[str],
                  args: list[object], profile: dict) -> list[dict]:
    weights = ",".join(str(float(profile["bm25_weights"][column]))
                       for column in profile["fts_columns"])
    try:
        rows = connection.execute(
            "SELECT i.icon_id,i.title,i.collection,i.description,i.preferred_role,"
            "i.lifecycle_status,bm25(icon_fts," + weights + ") AS rank_score "
            "FROM icon_fts JOIN icon i ON i.icon_id=icon_fts.icon_id "
            "WHERE icon_fts MATCH ? AND " + " AND ".join(filters)
            + " ORDER BY rank_score,i.icon_id", [expression, *args]).fetchall()
    except sqlite3.OperationalError as error:
        raise ValueError(f"invalid FTS5 query: {error}") from error
    return [dict(row) for row in rows]


def search_icons(connection: sqlite3.Connection, text: str | None = "", limit: int = 12,
                 collection: str | None = None, role: str | None = None, *,
                 query: str | None = None, like: str | None = None,
                 require: dict | None = None,
                 except_ids: list[str] | tuple[str, ...] | set[str] | None = None) -> dict:
    """Run the shared schema-v2 search contract, with plain-text schema-v1 compatibility."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    if role is not None and role not in ("transparent", "default", "background"):
        raise ValueError("invalid rendition role")
    schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
    if schema_version == 1:
        if query is not None or like is not None or require or except_ids:
            raise ValueError("structured search requires a schema-v2 catalog")
        results = legacy_search_icons(connection, text or "", limit, collection, role)
        return {"text": text or "", "query": None, "like": None, "require": {}, "except": [],
                "requested_count": limit, "returned_count": len(results),
                "shortfall": limit - len(results), "result_source": "legacy_text",
                "search_profile_sha256": None, "diagnostics": [], "results": results}
    if schema_version != 2:
        raise ValueError(f"unsupported catalog schema version {schema_version}")

    profile, profile_sha256 = _search_profile(connection)
    text_expression, text_terms = _ordinary_expression(text, profile)
    query_expression = _validate_fts_query(query, profile)
    require_expression, normalized_require = _required_expression(require, profile)
    if collection is not None and (not isinstance(collection, str) or not collection.strip()
                                   or len(collection) > 200):
        raise ValueError("collection must be short nonblank text")
    if like is not None and (not isinstance(like, str) or not ICON_ID.fullmatch(like)):
        raise ValueError("invalid similarity seed icon ID")

    if except_ids is not None and not isinstance(except_ids, (list, tuple, set)):
        raise ValueError("except must be a collection of icon IDs")
    raw_excluded = list(except_ids or ())
    if any(not isinstance(icon_id, str) for icon_id in raw_excluded):
        raise ValueError("except contains malformed icon IDs")
    excluded = set(raw_excluded)
    if len(excluded) > profile["request_limits"]["excluded_ids"]:
        raise ValueError("except contains too many icon IDs")
    malformed = [icon_id for icon_id in excluded if not ICON_ID.fullmatch(icon_id)]
    if malformed:
        raise ValueError("except contains malformed icon IDs")
    known_ids = {row[0] for row in connection.execute("SELECT icon_id FROM icon")}
    unknown_excluded = sorted(excluded - known_ids)

    filters = ["i.lifecycle_status != 'retired'"]
    args: list[object] = []
    if collection:
        filters.append("i.collection = ?")
        args.append(collection)
    if role:
        filters.append("EXISTS (SELECT 1 FROM rendition r WHERE r.icon_id=i.icon_id AND r.stable_role=?)")
        args.append(role)
    seed_expression = None
    seed_terms = []
    if like is not None:
        seed_expression, seed_terms = _seed_expression(
            connection, like, profile, set(normalized_require))

    channels: dict[str, list[dict]] = {}
    if text_expression:
        channels["text"] = _rank_channel(
            connection, _combined(query_expression, require_expression, text_expression),
            filters, args, profile)
    if seed_expression:
        channels["seed"] = _rank_channel(
            connection, _combined(query_expression, require_expression, seed_expression),
            filters, args, profile)
    if not text_expression and like is None and query_expression:
        channels["query"] = _rank_channel(
            connection, _combined(query_expression, require_expression), filters, args, profile)
    for name in channels:
        channels[name] = [row for row in channels[name] if row["icon_id"] not in excluded]

    if channels:
        if set(channels) == {"text", "seed"}:
            ranks = {name: {row["icon_id"]: index for index, row in enumerate(rows, 1)}
                     for name, rows in channels.items()}
            by_id = {row["icon_id"]: row for rows in channels.values() for row in rows}
            fused = []
            for icon_id, row in by_id.items():
                score = sum(1 / (profile["rrf_rank_constant"] + rank[icon_id])
                            for rank in ranks.values() if icon_id in rank)
                fused.append((score, icon_id, row))
            ranked = [row | {"rank_score": score} for score, _, row in sorted(
                fused, key=lambda item: (-item[0], item[1]))]
            result_source = "fused_text_seed" if channels["text"] else "seed_only_after_text_no_match"
        else:
            result_source, ranked = next(iter(channels.items()))
    else:
        expression = require_expression
        if like is not None and not seed_expression and not text_expression:
            ranked = []
            result_source = "seed_no_terms"
        elif expression:
            try:
                ranked = [dict(row) | {"rank_score": None} for row in connection.execute(
                    "SELECT i.icon_id,i.title,i.collection,i.description,i.preferred_role,"
                    "i.lifecycle_status FROM icon_fts JOIN icon i ON i.icon_id=icon_fts.icon_id "
                    "WHERE icon_fts MATCH ? AND " + " AND ".join(filters)
                    + " ORDER BY i.collection,i.ordinal,i.icon_id", [expression, *args]).fetchall()]
            except sqlite3.OperationalError as error:
                raise ValueError(f"invalid typed constraint: {error}") from error
            result_source = "constrained_browse"
        else:
            ranked = [dict(row) | {"rank_score": None} for row in connection.execute(
                "SELECT i.icon_id,i.title,i.collection,i.description,i.preferred_role,i.lifecycle_status "
                "FROM icon i WHERE " + " AND ".join(filters)
                + " ORDER BY i.collection,i.ordinal,i.icon_id", args).fetchall()]
            result_source = "stable_browse"
        ranked = [row for row in ranked if row["icon_id"] not in excluded]

    diagnostics = []
    if unknown_excluded:
        diagnostics.append({"code": "unknown_excluded_ids", "icon_ids": unknown_excluded})
    if like is not None and not seed_terms:
        diagnostics.append({"code": "seed_has_no_eligible_terms", "icon_id": like})
    if text_expression and "text" in channels and not channels["text"] and channels.get("seed"):
        diagnostics.append({"code": "text_no_matches_used_seed_channel"})

    channel_ids = {name: {row["icon_id"] for row in rows} for name, rows in channels.items()}
    results = []
    for row in ranked[:limit]:
        reasons = [name for name, ids in channel_ids.items() if row["icon_id"] in ids]
        reasons.extend(f"require:{field}=" + "|".join(values)
                       for field, values in sorted(normalized_require.items()))
        if collection:
            reasons.append("collection:" + collection)
        if role:
            reasons.append("role:" + role)
        results.append(row | {"match_reasons": reasons,
                              "thumbnail_url": "/api/v1/thumbnails/" + row["icon_id"]})
    return {
        "text": text or "", "text_terms": text_terms, "query": query_expression,
        "like": like, "seed_terms": seed_terms, "require": normalized_require,
        "except": sorted(excluded), "requested_count": limit, "returned_count": len(results),
        "shortfall": limit - len(results), "result_source": result_source,
        "search_profile_sha256": "sha256:" + profile_sha256,
        "diagnostics": diagnostics, "results": results,
    }


def parse_require_arguments(values: list[str]) -> dict[str, list[str]]:
    require: dict[str, list[str]] = {}
    for value in values:
        if not isinstance(value, str) or "=" not in value:
            raise ValueError("require must use FIELD=VALUE")
        field, choice = value.split("=", 1)
        if field not in REQUIRE_FIELDS or not choice.strip():
            raise ValueError("require must use a supported FIELD=VALUE")
        require.setdefault(field, []).append(choice.strip())
    return require


def run_search_request(connection: sqlite3.Connection, request: dict) -> dict:
    if not isinstance(request, dict):
        raise ValueError("search request must be a JSON object")
    allowed = {"text", "query", "like", "require", "except", "limit", "collection", "role"}
    extra = set(request) - allowed
    if extra:
        raise ValueError("unsupported search request field(s): " + ", ".join(sorted(extra)))
    except_ids = request.get("except", [])
    if not isinstance(except_ids, list):
        raise ValueError("except must be an array of icon IDs")
    return search_icons(
        connection, request.get("text", ""), request.get("limit", 12),
        request.get("collection"), request.get("role"), query=request.get("query"),
        like=request.get("like"), require=request.get("require"), except_ids=except_ids)


def show_icon(connection: sqlite3.Connection, icon_id: str, version: dict) -> dict:
    if not ICON_ID.fullmatch(icon_id):
        raise ValueError("invalid icon ID")
    row = connection.execute("SELECT * FROM icon WHERE icon_id = ?", (icon_id,)).fetchone()
    if row is None:
        raise LookupError("icon not found")
    renditions = connection.execute(
        "SELECT r.stable_role, b.sha256, b.byte_size, b.width, b.height, b.relative_path "
        "FROM rendition r JOIN blob b ON b.sha256 = r.blob_sha256 "
        "WHERE r.icon_id = ? ORDER BY r.stable_role", (icon_id,)
    ).fetchall()
    keywords = connection.execute(
        "SELECT namespace, value FROM icon_keyword WHERE icon_id = ? ORDER BY namespace, value", (icon_id,)
    ).fetchall()
    derivative = connection.execute(
        "SELECT relative_path, sha256, width, height FROM derivative WHERE icon_id = ?", (icon_id,)
    ).fetchone()
    result = dict(row) | {
        "renditions": [dict(r) | {"sha256": "sha256:" + r["sha256"]} for r in renditions],
        "keywords": [dict(k) for k in keywords],
        "thumbnail": (dict(derivative) | {"sha256": "sha256:" + derivative["sha256"]}) if derivative else None,
        "package_status": version["package_status"],
        "observed_release_id": version["release_id"],
        "observed_catalog_revision": version["catalog_revision"],
    }
    if version["package_status"] == "release_manifest_present":
        result["stable_handle"] = {"catalog_id": CATALOG_ID, "icon_id": icon_id}
    return result


def resolve_rendition(connection: sqlite3.Connection, icon_id: str,
                      sha256: str | None = None, role: str | None = None) -> dict:
    """Resolve only bytes historically associated with this logical icon."""
    if not ICON_ID.fullmatch(icon_id):
        raise ValueError("invalid icon ID")
    if role is not None and role not in ("transparent", "default", "background"):
        raise ValueError("invalid rendition role")
    icon = connection.execute("SELECT preferred_role FROM icon WHERE icon_id = ?", (icon_id,)).fetchone()
    if icon is None:
        raise LookupError("icon not found")
    if sha256 is not None:
        bare = sha_value(sha256)
        sql = (
            "SELECT h.stable_role, b.sha256, b.byte_size, b.relative_path "
            "FROM rendition_history h JOIN blob b ON b.sha256 = h.blob_sha256 "
            "WHERE h.icon_id = ? AND h.blob_sha256 = ?"
        )
        params: list[object] = [icon_id, bare]
        if role:
            sql += " AND h.stable_role = ?"
            params.append(role)
        sql += " ORDER BY h.stable_role LIMIT 1"
    else:
        sql = (
            "SELECT r.stable_role, b.sha256, b.byte_size, b.relative_path "
            "FROM rendition r JOIN blob b ON b.sha256 = r.blob_sha256 "
            "WHERE r.icon_id = ? AND r.stable_role = ?"
        )
        params = [icon_id, role or icon["preferred_role"]]
    row = connection.execute(sql, params).fetchone()
    if row is None:
        raise LookupError("rendition is not associated with this icon")
    return dict(row)


def materialize(root: Path, connection: sqlite3.Connection, version: dict,
                inventory: dict[str, dict], icon_id: str, destination: Path,
                sha256: str | None, role: str | None) -> dict:
    if version["package_status"] != "release_manifest_present":
        raise ValueError("materialization requires a release manifest")
    rendition = resolve_rendition(connection, icon_id, sha256, role)
    relative = rendition["relative_path"]
    source = safe_file(root, relative)
    entry = inventory.get(relative)
    if entry is None or entry["sha256"] != "sha256:" + rendition["sha256"]:
        raise ValueError("rendition is not bound by the release manifest")
    if entry["size"] != rendition["byte_size"]:
        raise ValueError("rendition size does not match the release manifest")
    destination = destination.absolute()
    if destination.resolve(strict=False).is_relative_to(root.resolve()):
        raise ValueError("destination must be outside the immutable package")
    destination.parent.mkdir(parents=True, exist_ok=True)
    receipt_path = destination.with_name(destination.name + ".icon-receipt.json")
    if os.path.lexists(destination) or os.path.lexists(receipt_path):
        raise FileExistsError("destination or receipt already exists")
    receipt = {
        "stable_handle": {"catalog_id": CATALOG_ID, "icon_id": icon_id},
        "rendition_sha256": "sha256:" + rendition["sha256"],
        "stable_role": rendition["stable_role"],
        "observed_release_id": version["release_id"],
        "observed_catalog_revision": version["catalog_revision"],
        "source_relative_path": relative,
        "materialized_file": destination.name,
    }
    file_fd, staged_file = tempfile.mkstemp(prefix=".icon-", dir=destination.parent)
    os.close(file_fd)
    try:
        receipt_fd, staged_receipt = tempfile.mkstemp(prefix=".icon-receipt-", dir=destination.parent)
        os.close(receipt_fd)
    except Exception:
        os.unlink(staged_file)
        raise
    linked = False
    try:
        hasher = hashlib.sha256()
        copied = 0
        with source.open("rb") as original, Path(staged_file).open("wb") as copy:
            while block := original.read(1024 * 1024):
                copy.write(block)
                hasher.update(block)
                copied += len(block)
            copy.flush()
            os.fsync(copy.fileno())
        if hasher.hexdigest() != rendition["sha256"] or copied != rendition["byte_size"]:
            raise ValueError("source rendition hash or size mismatch")
        with Path(staged_receipt).open("w", encoding="utf-8", newline="\n") as output:
            json.dump(receipt, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        # ponytail: atomic no-overwrite needs local hard-link support; add a platform fallback only if required.
        os.link(staged_file, destination)
        linked = True
        os.link(staged_receipt, receipt_path)
        return receipt
    except Exception:
        if linked and destination.exists():
            staged = os.stat(staged_file)
            current = os.stat(destination)
            if (staged.st_dev, staged.st_ino) == (current.st_dev, current.st_ino):
                destination.unlink()
        raise
    finally:
        for staged in (staged_file, staged_receipt):
            if os.path.exists(staged):
                os.unlink(staged)


BROWSER = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Indexed Icon Pack</title>
<style>body{font:16px system-ui;max-width:1100px;margin:auto;padding:1rem;color:#202430;background:#f6f7fa}
form{margin:1rem 0}.row{display:flex;gap:.5rem;align-items:center}.row input{flex:1}input{padding:.55rem}
button{padding:.55rem;cursor:pointer}.filters{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.5rem;margin:.8rem 0}
.filters label{display:flex;flex-direction:column;gap:.2rem}#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:.7rem;list-style:none;padding:0}
#grid button{width:100%;height:100%;background:white;border:1px solid #bbb;border-radius:.4rem}
#grid img{width:128px;height:128px;object-fit:contain}#detail{background:white;padding:1rem;min-height:4rem}
button:focus-visible,input:focus-visible{outline:3px solid #125cc9}small{display:block;word-break:break-word}</style></head>
<body><h1>Indexed Icon Pack</h1><p id="version" role="status"></p>
<form id="search"><div class="row"><label for="q">Describe an icon</label><input id="q" name="q" autocomplete="off"><button>Search</button></div>
<details><summary>Structured filters</summary><div class="filters">
<label>Advanced FTS query<input id="fts"></label>
<label>Subject (comma-separated OR)<input data-require="subject"></label>
<label>Action<input data-require="action"></label><label>State<input data-require="state"></label>
<label>Effect<input data-require="effect"></label><label>Symbol<input data-require="symbol"></label>
<label>Color<input data-require="color"></label><label>Material<input data-require="material"></label>
</div></details><button type="button" id="clear">Clear exclusions and seed</button></form>
<p id="count" aria-live="polite"></p><ul id="grid"></ul>
<h2>Selected icon</h2><section id="detail" aria-live="polite">Choose an icon to inspect it.</section>
<script>
const grid=document.querySelector('#grid'),detail=document.querySelector('#detail'),excluded=new Set();let seed=null;
async function json(path,options){const r=await fetch(path,options);if(!r.ok)throw Error(await r.text());return r.json()}
async function select(id){try{const x=await json('/api/v1/icons/'+encodeURIComponent(id));detail.replaceChildren();
const h=document.createElement('h3');h.textContent=x.title;detail.append(h);
const p=document.createElement('p');p.textContent=x.description||'Description pending model annotation.';detail.append(p);
for(const [ns,label] of [['reviewed_term','Alternative readings'],['inferred_use','Possible uses'],['uncertainty','Uncertainty']]){
const values=x.keywords.filter(k=>k.namespace===ns).map(k=>k.value);if(values.length){const line=document.createElement('p');line.textContent=label+': '+values.join('; ');detail.append(line)}}
const facts=document.createElement('p');facts.textContent=x.collection+' / '+x.icon_id+' / '+x.lifecycle_status;detail.append(facts);
for(const r of x.renditions){const line=document.createElement('small');line.textContent=r.stable_role+' / '+r.width+'x'+r.height+' / '+r.sha256;detail.append(line);
if(x.stable_handle){const pin=document.createElement('button');pin.textContent='Copy exact pin for '+r.stable_role;
pin.onclick=()=>navigator.clipboard.writeText(JSON.stringify({...x.stable_handle,rendition_sha256:r.sha256}));detail.append(pin)}}
const similar=document.createElement('button');similar.textContent='Find alternatives';similar.onclick=()=>{seed=id;excluded.add(id);search()};detail.append(similar);
const omit=document.createElement('button');omit.textContent='Exclude this icon';omit.onclick=()=>{excluded.add(id);search()};detail.append(omit);
if(x.stable_handle){const b=document.createElement('button');b.textContent='Copy stable handle';b.onclick=()=>navigator.clipboard.writeText(JSON.stringify(x.stable_handle));detail.append(b)}
}catch(e){detail.textContent=String(e)}}
function request(){const require={};for(const input of document.querySelectorAll('[data-require]')){const values=input.value.split(',').map(x=>x.trim()).filter(Boolean);if(values.length)require[input.dataset.require]=values}
return {text:document.querySelector('#q').value,query:document.querySelector('#fts').value||null,like:seed,require,except:[...excluded],limit:60}}
async function search(){try{const x=await json('/api/v1/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request())});
grid.replaceChildren();let status=x.returned_count+' of '+x.requested_count+' results';if(x.shortfall)status+=' ('+x.shortfall+' short)';if(seed)status+=' / alternatives to '+seed;document.querySelector('#count').textContent=status;
for(const item of x.results){const li=document.createElement('li'),b=document.createElement('button'),img=document.createElement('img');
img.src=item.thumbnail_url;img.alt='';img.loading='lazy';b.append(img,document.createElement('br'),document.createTextNode(item.title));
b.setAttribute('aria-label','Inspect '+item.title);b.onclick=()=>select(item.icon_id);li.append(b);grid.append(li)}
}catch(e){document.querySelector('#count').textContent=String(e)}}
document.querySelector('#search').onsubmit=e=>{e.preventDefault();search()};
document.querySelector('#clear').onclick=()=>{excluded.clear();seed=null;search()};
json('/api/v1/version').then(v=>{document.querySelector('#version').textContent=(v.release_id||'Unpublished QA catalog')+(v.search_profile_id?' / '+v.search_profile_id:'');search()});
</script></body></html>"""


def serve(root: Path, connection: sqlite3.Connection, version: dict,
          inventory: dict[str, dict], port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            url = urlsplit(self.path)
            path = unquote(url.path)
            try:
                if path == "/":
                    self.respond(BROWSER.encode(), "text/html; charset=utf-8")
                elif path == "/api/v1/version":
                    self.respond_json(version)
                elif path == "/api/v1/search":
                    params = parse_qs(url.query)
                    request = {
                        "text": params.get("q", [""])[0],
                        "limit": int(params.get("limit", ["12"])[0]),
                    }
                    for name in ("query", "like", "collection", "role"):
                        if name in params:
                            request[name] = params[name][0]
                    require = {field: params[f"require.{field}"] for field in REQUIRE_FIELDS
                               if f"require.{field}" in params}
                    if require:
                        request["require"] = require
                    if "except" in params:
                        request["except"] = params["except"]
                    self.respond_json(run_search_request(connection, request) | {"version": version})
                elif path.startswith("/api/v1/icons/"):
                    self.respond_json(show_icon(connection, path.removeprefix("/api/v1/icons/"), version))
                elif path.startswith("/api/v1/thumbnails/"):
                    icon_id = path.removeprefix("/api/v1/thumbnails/")
                    if not ICON_ID.fullmatch(icon_id):
                        raise ValueError("invalid icon ID")
                    derivative = connection.execute(
                        "SELECT relative_path, sha256 FROM derivative WHERE icon_id = ?", (icon_id,)
                    ).fetchone()
                    if derivative is None:
                        raise LookupError("thumbnail not found")
                    asset = safe_file(root, derivative["relative_path"])
                    if digest(asset) != derivative["sha256"]:
                        raise ValueError("thumbnail hash mismatch")
                    if version["package_status"] == "release_manifest_present":
                        entry = inventory.get(derivative["relative_path"])
                        if entry is None or entry["sha256"] != "sha256:" + derivative["sha256"]:
                            raise ValueError("thumbnail is not bound by the release manifest")
                    self.respond(asset.read_bytes(), "image/png")
                elif path.startswith("/api/v1/blobs/"):
                    bare = sha_value(path.removeprefix("/api/v1/blobs/"))
                    blob = connection.execute("SELECT relative_path FROM blob WHERE sha256 = ?", (bare,)).fetchone()
                    if blob is None:
                        raise LookupError("blob not found")
                    asset = safe_file(root, blob["relative_path"])
                    if digest(asset) != bare:
                        raise ValueError("blob hash mismatch")
                    if version["package_status"] == "release_manifest_present":
                        entry = inventory.get(blob["relative_path"])
                        if entry is None or entry["sha256"] != "sha256:" + bare:
                            raise ValueError("blob is not bound by the release manifest")
                    self.respond(asset.read_bytes(), "image/png")
                else:
                    raise LookupError("not found")
            except (ValueError, sqlite3.Error) as error:
                self.send_error(400, str(error))
            except LookupError as error:
                self.send_error(404, str(error))

        def do_POST(self) -> None:
            try:
                if unquote(urlsplit(self.path).path) != "/api/v1/search":
                    raise LookupError("not found")
                if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
                    raise ValueError("search POST requires application/json")
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= 524288:
                    raise ValueError("search request body must be between 1 and 524288 bytes")
                request = json.loads(self.rfile.read(length).decode("utf-8"))
                self.respond_json(run_search_request(connection, request) | {"version": version})
            except (ValueError, sqlite3.Error, json.JSONDecodeError, UnicodeError) as error:
                self.send_error(400, str(error))
            except LookupError as error:
                self.send_error(404, str(error))

        def respond_json(self, value: object) -> None:
            self.respond(json.dumps(value, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def respond(self, body: bytes, kind: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    print(f"Read-only icon browser: http://127.0.0.1:{port}")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parent)
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search")
    search.add_argument("text", nargs="?", default="")
    search.add_argument("--query", dest="fts_query", help="explicit FTS5 predicate")
    search.add_argument("--like", help="logical icon ID used as a positive example")
    search.add_argument("--require", action="append", default=[], metavar="FIELD=VALUE")
    search.add_argument("--except", dest="excluded", action="append", default=[], metavar="ICON_ID")
    search.add_argument("--limit", type=int, default=12)
    search.add_argument("--collection")
    search.add_argument("--role")
    search.add_argument("--json", action="store_true")
    show = commands.add_parser("show")
    show.add_argument("icon_id")
    show.add_argument("--json", action="store_true")
    copy = commands.add_parser("materialize")
    copy.add_argument("icon_id")
    copy.add_argument("--to", "--output", dest="destination", type=Path, required=True)
    copy.add_argument("--sha256")
    copy.add_argument("--role")
    copy.add_argument("--json", action="store_true")
    verify = commands.add_parser("verify")
    verify.add_argument("--deep", action="store_true")
    verify.add_argument("--json", action="store_true")
    version_command = commands.add_parser("version")
    version_command.add_argument("--json", action="store_true")
    server = commands.add_parser("serve")
    server.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    try:
        root = args.package.resolve(strict=True)
        if args.command == "verify":
            validator = Path(__file__).resolve().parent / "tools" / "validate_catalog.py"
            if not validator.is_file():
                raise ValueError("catalog validator is unavailable")
            command = [sys.executable, str(validator), "--package", str(root)]
            if not args.deep:
                command.append("--fast")
            if args.json:
                command.append("--json")
            return subprocess.call(command)
        connection, version, inventory = open_catalog(root)
        try:
            if args.command == "search":
                request = {"text": args.text, "query": args.fts_query, "like": args.like,
                           "require": parse_require_arguments(args.require),
                           "except": args.excluded, "limit": args.limit,
                           "collection": args.collection, "role": args.role}
                result = run_search_request(connection, request) | {"version": version}
            elif args.command == "show":
                result = show_icon(connection, args.icon_id, version)
            elif args.command == "materialize":
                result = materialize(root, connection, version, inventory, args.icon_id,
                                     args.destination, args.sha256, args.role)
            elif args.command == "version":
                result = version
            elif args.command == "serve":
                if not 1 <= args.port <= 65535:
                    raise ValueError("port must be between 1 and 65535")
                serve(root, connection, version, inventory, args.port)
                return 0
            else:
                raise AssertionError("unhandled command")
            if args.json or args.command == "version":
                print(json.dumps(result, ensure_ascii=False, indent=2))
            elif args.command == "search":
                for item in result["results"]:
                    print(f"{item['icon_id']}  {item['title']}  [{item['collection']}]")
                print(f"{result['returned_count']}/{result['requested_count']} results "
                      f"({version['package_status']}, shortfall {result['shortfall']})")
            elif args.command == "show":
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"Copied {result['rendition_sha256']} ({result['stable_role']})")
            return 0
        finally:
            connection.close()
    except (OSError, ValueError, LookupError, sqlite3.Error, json.JSONDecodeError) as error:
        print(f"iconctl: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
