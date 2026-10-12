#!/usr/bin/env python3
"""Compare frozen legacy retrieval with a persistent schema-v2 search candidate."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
import platform
import sqlite3
import statistics
import time
from pathlib import Path

from annotation_data import load_annotations, sha256

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from iconctl import legacy_search_icons, search_icons


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def percentile(values: list[float], proportion: float) -> float:
    return sorted(values)[max(0, math.ceil(len(values) * proportion) - 1)]


def legacy_database(base: Path, loaded: dict) -> sqlite3.Connection:
    source = sqlite3.connect(f"file:{(base / 'catalog.sqlite').resolve().as_posix()}?mode=ro", uri=True)
    legacy = sqlite3.connect(":memory:")
    legacy.row_factory = sqlite3.Row
    try:
        source.backup(legacy)
    finally:
        source.close()
    icons = {row["icon_id"]: row for row in legacy.execute(
        "SELECT icon_id,title,collection FROM icon")}
    if set(icons) != set(loaded["annotations"]):
        legacy.close()
        raise ValueError("legacy candidate IDs differ from accepted observations")
    legacy.execute("DELETE FROM icon_fts")
    for icon_id, annotation in loaded["annotations"].items():
        legacy.execute("UPDATE icon SET description=? WHERE icon_id=?",
                       (annotation["description"], icon_id))
        terms = [*annotation["keywords"], *loaded["reviewed_terms"].get(icon_id, [])]
        legacy.execute("INSERT INTO icon_fts VALUES(?,?,?,?,?)", (
            icon_id, icons[icon_id]["title"], icons[icon_id]["collection"],
            annotation["description"], " ".join(term.casefold() for term in terms)))
    return legacy


def rank(icon_id: str, rows: list[dict]) -> int | None:
    return next((index for index, row in enumerate(rows, 1) if row["icon_id"] == icon_id), None)


def metrics(cases: list[dict]) -> dict:
    return {
        f"exact_target_hit_at_{cutoff}": sum(
            row["target_rank"] is not None and row["target_rank"] <= cutoff for row in cases)
        for cutoff in (1, 5, 10, 20)
    } | {"queries": len(cases)}


def compact(rows: list[dict], count: int = 20) -> list[dict]:
    return [{key: row[key] for key in ("icon_id", "title", "collection", "description")}
            for row in rows[:count]]


def compare(base: Path, candidate: Path, run: Path, reviews: list[Path], benchmark: Path) -> dict:
    loaded = load_annotations(run, reviews)
    data = json.loads(benchmark.read_text(encoding="utf-8"))
    cases = data.get("cases")
    if (data.get("benchmark_schema_version") != 1 or not isinstance(cases, list) or not cases
            or any(not isinstance(case, dict) or case.get("icon_id") not in loaded["annotations"]
                   or not isinstance(case.get("query"), str) or not case["query"].strip()
                   for case in cases)):
        raise ValueError("invalid or incompatible benchmark")
    legacy = legacy_database(base, loaded)
    candidate_db = candidate / "catalog.sqlite"
    current = sqlite3.connect(f"file:{candidate_db.resolve().as_posix()}?mode=ro", uri=True)
    current.row_factory = sqlite3.Row
    warm_ms = []
    legacy_cases, current_cases = [], []
    try:
        for case in cases:
            target, query = case["icon_id"], case["query"]
            old_rows = legacy_search_icons(legacy, query, 100)
            started = time.perf_counter()
            response = search_icons(current, query, 100)
            warm_ms.append((time.perf_counter() - started) * 1000)
            new_rows = response["results"]
            legacy_cases.append({"query": query, "target": target,
                                 "target_rank": rank(target, old_rows), "top20": compact(old_rows)})
            current_cases.append({"query": query, "target": target,
                                  "target_rank": rank(target, new_rows), "top20": compact(new_rows),
                                  "result_source": response["result_source"]})
    finally:
        legacy.close()
        current.close()

    connection_cold_ms = []
    for case in cases:
        opened = time.perf_counter()
        connection = sqlite3.connect(f"file:{candidate_db.resolve().as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            search_icons(connection, case["query"], 100)
        finally:
            connection.close()
        connection_cold_ms.append((time.perf_counter() - opened) * 1000)

    old_metrics, new_metrics = metrics(legacy_cases), metrics(current_cases)
    wins, regressions, ties = [], [], 0
    for old, new in zip(legacy_cases, current_cases, strict=True):
        old_rank = old["target_rank"] or 101
        new_rank = new["target_rank"] or 101
        summary = {"query": old["query"], "target": old["target"],
                   "legacy_rank": old["target_rank"], "new_rank": new["target_rank"]}
        if new_rank < old_rank:
            wins.append(summary)
        elif new_rank > old_rank:
            regressions.append(summary)
        else:
            ties += 1

    with sqlite3.connect(candidate_db) as facts:
        page_count = facts.execute("PRAGMA page_count").fetchone()[0]
        page_size = facts.execute("PRAGMA page_size").fetchone()[0]
        try:
            search_index_bytes = facts.execute(
                "SELECT coalesce(sum(pgsize),0) FROM dbstat WHERE name='icon_fts' "
                "OR name LIKE 'icon_fts_%' OR name IN ('icon_keyword','icon_observation','search_profile')"
            ).fetchone()[0]
        except sqlite3.Error:
            search_index_bytes = None
        profile_sha256 = facts.execute("SELECT profile_sha256 FROM search_profile").fetchone()[0]
    return {
        "comparison_schema_version": 1,
        "scope": "exposed_v4_development_regression_not_acceptance_evidence",
        "benchmark_sha256": sha256(benchmark),
        "accepted_annotations_sha256": loaded["accepted_annotations_sha256"],
        "search_profile_sha256": profile_sha256,
        "legacy": {"metrics": old_metrics, "cases": legacy_cases},
        "current": {"metrics": new_metrics, "cases": current_cases},
        "paired": {"improved_ranks": wins, "regressed_ranks": regressions, "unchanged_ranks": ties},
        "performance": {
            "definition": "warm reuses one read-only connection; connection_cold includes opening a new connection but not an OS cache flush",
            "warm_ms": {"p50": statistics.median(warm_ms), "p95": percentile(warm_ms, .95)},
            "connection_cold_ms": {"p50": statistics.median(connection_cold_ms),
                                   "p95": percentile(connection_cold_ms, .95)},
            "catalog_sqlite_bytes": candidate_db.stat().st_size,
            "sqlite_page_bytes": page_count * page_size,
            "search_projection_bytes": search_index_bytes,
        },
        "visual_judgment_status": "required_for_new_rankings; historical judgments were not transferred",
    }


def input_pins(base: Path, candidate: Path, run: Path, freeze: Path,
               reviews: list[Path], benchmark: Path) -> dict:
    registry = base / "manifests" / "icon-identities.jsonl"
    manifest = base / "manifests" / "catalog.jsonl"
    with sqlite3.connect(candidate / "catalog.sqlite") as connection:
        counts = {
            "logical_icons": connection.execute("SELECT count(*) FROM icon").fetchone()[0],
            "renditions": connection.execute("SELECT count(*) FROM rendition").fetchone()[0],
            "observations": connection.execute("SELECT count(*) FROM icon_observation").fetchone()[0],
        }
    legacy_source = inspect.getsource(legacy_search_icons).encode("utf-8")
    files = [
        registry, manifest, run / "annotations.jsonl", run / "icons.jsonl", run / "plan.json",
        freeze, benchmark, *reviews, candidate / "manifests" / "search-profile.json",
        Path(__file__), Path(__file__).with_name("annotation_data.py"),
        Path(__file__).resolve().parents[1] / "iconctl.py",
    ]
    return {
        "input_pins_schema_version": 1,
        "catalog_id": "indexed-icon-pack",
        "counts": counts,
        "files": {path.resolve().relative_to(Path(__file__).resolve().parents[1]).as_posix(): sha256(path)
                  for path in files},
        "legacy_search_function_sha256": hashlib.sha256(legacy_source).hexdigest(),
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "supplemental_pilots_accepted": False,
    }


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--review", type=Path, nargs="*", default=[])
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--legacy-output", type=Path, required=True)
    parser.add_argument("--pins-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = compare(args.base, args.candidate, args.run, args.review, args.benchmark)
        pins = input_pins(args.base, args.candidate, args.run, args.freeze,
                          args.review, args.benchmark)
        write_json(args.output, result)
        write_json(args.legacy_output, {
            "baseline_schema_version": 1,
            "benchmark_sha256": result["benchmark_sha256"],
            "legacy_search_function_sha256": pins["legacy_search_function_sha256"],
            **result["legacy"],
        })
        write_json(args.pins_output, pins)
        print(json.dumps({"legacy": result["legacy"]["metrics"],
                          "current": result["current"]["metrics"],
                          "output": args.output.as_posix()}, sort_keys=True))
    except (ValueError, OSError, sqlite3.Error, json.JSONDecodeError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
