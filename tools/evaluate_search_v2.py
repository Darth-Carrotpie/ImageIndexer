#!/usr/bin/env python3
"""Run and score schema-v2 search benchmarks against one immutable candidate."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import platform
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from iconctl import ICON_ID, open_catalog, run_search_request


FAMILIES = frozenset({"literal", "seed_modification", "functional", "exclusion_negative"})
ALLOCATIONS = {
    "development": {"literal": 40, "seed_modification": 30,
                    "functional": 20, "exclusion_negative": 10},
    "acceptance_positive": {"literal": 25, "seed_modification": 15,
                            "functional": 10, "exclusion_negative": 0},
    "acceptance_negative": {"literal": 0, "seed_modification": 0,
                            "functional": 0, "exclusion_negative": 10},
}


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def percentile(values: list[float], proportion: float) -> float:
    return sorted(values)[max(0, math.ceil(len(values) * proportion) - 1)]


def peak_working_set_bytes() -> int | None:
    if os.name != "nt":
        return None

    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD), ("page_fault_count", wintypes.DWORD),
            ("peak_working_set_size", ctypes.c_size_t), ("working_set_size", ctypes.c_size_t),
            ("quota_peak_paged_pool_usage", ctypes.c_size_t),
            ("quota_paged_pool_usage", ctypes.c_size_t),
            ("quota_peak_non_paged_pool_usage", ctypes.c_size_t),
            ("quota_non_paged_pool_usage", ctypes.c_size_t),
            ("pagefile_usage", ctypes.c_size_t), ("peak_pagefile_usage", ctypes.c_size_t),
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        ok = psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
        return counters.peak_working_set_size if ok else None
    except (AttributeError, OSError):
        return None


def _text_list(value: object, label: str) -> list[str]:
    if (not isinstance(value, list) or any(not isinstance(item, str) or not item.strip()
                                           for item in value)):
        raise ValueError(f"{label} must be an array of nonblank strings")
    return value


def load_benchmark(path: Path, *, strict_allocation: bool = True) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("benchmark_schema_version") != 2
            or data.get("set_kind") not in ALLOCATIONS
            or not isinstance(data.get("author"), str) or not data["author"].strip()
            or not isinstance(data.get("exposure"), str) or not data["exposure"].strip()
            or not isinstance(data.get("cases"), list) or not data["cases"]):
        raise ValueError("invalid schema-v2 search benchmark header")
    seen = set()
    counts = {family: 0 for family in FAMILIES}
    for case in data["cases"]:
        if not isinstance(case, dict) or set(case) - {
                "case_id", "family", "request", "required_visual_properties",
                "optional_visual_properties", "known_suitable_ids", "notes"}:
            raise ValueError("invalid benchmark case fields")
        case_id, family, request = case.get("case_id"), case.get("family"), case.get("request")
        if (not isinstance(case_id, str) or not case_id
                or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in case_id)
                or case_id in seen or family not in FAMILIES or not isinstance(request, dict)):
            raise ValueError(f"invalid or duplicate benchmark case: {case_id}")
        seen.add(case_id)
        counts[family] += 1
        required = _text_list(case.get("required_visual_properties"), f"{case_id} required properties")
        optional = _text_list(case.get("optional_visual_properties"), f"{case_id} optional properties")
        if set(map(str.casefold, required)) & set(map(str.casefold, optional)):
            raise ValueError(f"required and optional properties overlap: {case_id}")
        suitable = case.get("known_suitable_ids")
        if (not isinstance(suitable, list) or len(suitable) != len(set(suitable))
                or any(not isinstance(icon_id, str) or not ICON_ID.fullmatch(icon_id)
                       for icon_id in suitable)):
            raise ValueError(f"invalid suitable icon IDs: {case_id}")
        if family != "exclusion_negative" and not suitable:
            raise ValueError(f"positive case has no known suitable icon: {case_id}")
        if family == "seed_modification" and not request.get("like"):
            raise ValueError(f"seed-modification case has no seed: {case_id}")
    if strict_allocation and counts != ALLOCATIONS[data["set_kind"]]:
        raise ValueError(f"benchmark allocation mismatch: {counts}")
    return data | {"family_counts": counts}


def _aliases(field: str, value: str, profile: dict) -> set[str]:
    normalized = " ".join(value.casefold().split())
    for canonical_value, aliases in profile.get("alias_map", {}).get(field, {}).items():
        choices = {canonical_value, *aliases}
        if normalized in choices:
            return choices
    return {normalized}


def contract_violations(connection: sqlite3.Connection, request: dict,
                        response: dict, profile: dict) -> list[str]:
    violations = []
    results = response["results"]
    result_ids = [item["icon_id"] for item in results]
    excluded = set(request.get("except", []))
    if len(result_ids) != len(set(result_ids)):
        violations.append("duplicate logical icon IDs")
    if excluded & set(result_ids):
        violations.append("excluded logical icon returned")
    if response["returned_count"] != len(results):
        violations.append("returned_count differs from result length")
    if response["shortfall"] != response["requested_count"] - len(results):
        violations.append("shortfall is not truthful")
    if len(results) > response["requested_count"]:
        violations.append("returned more than requested")
    for item in results:
        icon_id = item["icon_id"]
        if item["lifecycle_status"] == "retired":
            violations.append(f"retired icon returned: {icon_id}")
        if request.get("collection") and item["collection"] != request["collection"]:
            violations.append(f"collection constraint failed: {icon_id}")
        if request.get("role") and connection.execute(
                "SELECT 1 FROM rendition WHERE icon_id=? AND stable_role=?",
                (icon_id, request["role"])).fetchone() is None:
            violations.append(f"role constraint failed: {icon_id}")
        facts: dict[str, set[str]] = {}
        for namespace, value in connection.execute(
                "SELECT namespace,value FROM icon_keyword WHERE icon_id=?", (icon_id,)):
            facts.setdefault(namespace, set()).add(value)
        for field, choices in response["require"].items():
            accepted = {alias for choice in choices for alias in _aliases(field, choice, profile)}
            if not accepted & facts.get(field, set()):
                violations.append(f"require.{field} constraint failed: {icon_id}")
        if request.get("query") and connection.execute(
                "SELECT 1 FROM icon_fts WHERE icon_id=? AND icon_fts MATCH ?",
                (icon_id, request["query"])).fetchone() is None:
            violations.append(f"explicit FTS predicate failed: {icon_id}")
    return sorted(set(violations))


def evaluate(package: Path, benchmark_path: Path, *, strict_allocation: bool = True) -> dict:
    benchmark = load_benchmark(benchmark_path, strict_allocation=strict_allocation)
    connection, version, _ = open_catalog(package)
    try:
        profile_row = connection.execute("SELECT profile_json FROM search_profile").fetchone()
        profile = json.loads(profile_row[0])
        known_ids = {row[0] for row in connection.execute("SELECT icon_id FROM icon")}
        cases, durations = [], []
        for case in benchmark["cases"]:
            unknown = set(case["known_suitable_ids"]) - known_ids
            if unknown:
                raise ValueError(f"unknown suitable IDs in {case['case_id']}: {sorted(unknown)}")
            started = time.perf_counter()
            response = run_search_request(connection, case["request"])
            durations.append((time.perf_counter() - started) * 1000)
            violations = contract_violations(connection, case["request"], response, profile)
            results = []
            for rank, item in enumerate(response["results"], 1):
                derivative = connection.execute(
                    "SELECT relative_path,sha256 FROM derivative WHERE icon_id=?",
                    (item["icon_id"],)).fetchone()
                results.append({
                    "rank": rank,
                    "icon_id": item["icon_id"],
                    "title": item["title"],
                    "collection": item["collection"],
                    "description": item["description"],
                    "thumbnail_relative_path": derivative["relative_path"],
                    "thumbnail_sha256": derivative["sha256"],
                    "match_reasons": item["match_reasons"],
                    "rank_score": item["rank_score"],
                })
            ranks = {item["icon_id"]: item["rank"] for item in results}
            cases.append({
                "case_id": case["case_id"], "family": case["family"],
                "request": case["request"],
                "required_visual_properties": case["required_visual_properties"],
                "optional_visual_properties": case["optional_visual_properties"],
                "known_suitable_ids": case["known_suitable_ids"],
                "known_suitable_ranks": {icon_id: ranks.get(icon_id)
                                         for icon_id in case["known_suitable_ids"]},
                "result_source": response["result_source"],
                "requested_count": response["requested_count"],
                "returned_count": response["returned_count"],
                "shortfall": response["shortfall"],
                "diagnostics": response["diagnostics"],
                "contract_violations": violations,
                "results": results,
            })
        exact = {}
        positives = [case for case in cases if case["family"] != "exclusion_negative"]
        for cutoff in (1, 5, 10, 20):
            exact[f"known_suitable_hit_at_{cutoff}"] = sum(any(
                rank is not None and rank <= cutoff for rank in case["known_suitable_ranks"].values())
                for case in positives)
        return {
            "evaluation_schema_version": 1,
            "benchmark_sha256": sha256(benchmark_path),
            "benchmark_set_kind": benchmark["set_kind"],
            "benchmark_author": benchmark["author"],
            "benchmark_exposure": benchmark["exposure"],
            "family_counts": benchmark["family_counts"],
            "catalog_sqlite_sha256": sha256(package / "catalog.sqlite"),
            "version": version,
            "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version,
            "metrics": exact | {
                "positive_cases": len(positives),
                "contract_violations": sum(bool(case["contract_violations"]) for case in cases),
            },
            "performance": {
                "single_connection_ms": {
                    "p50": sorted(durations)[len(durations) // 2],
                    "p95": percentile(durations, .95),
                },
                "process_peak_working_set_bytes": peak_working_set_bytes(),
            },
            "cases": cases,
        }
    finally:
        connection.close()


def score(ranked_path: Path, judgments_path: Path) -> dict:
    ranked = json.loads(ranked_path.read_text(encoding="utf-8"))
    judgments = json.loads(judgments_path.read_text(encoding="utf-8"))
    if (not isinstance(judgments, dict) or judgments.get("judgment_schema_version") != 2
            or judgments.get("benchmark_sha256") != ranked.get("benchmark_sha256")
            or judgments.get("ranked_results_sha256") != sha256(ranked_path)
            or not isinstance(judgments.get("reviewer"), str) or not judgments["reviewer"].strip()
            or type(judgments.get("independent_review")) is not bool
            or not isinstance(judgments.get("cases"), list)):
        raise ValueError("judgments are not pinned to these ranked results")
    ranked_cases = {case["case_id"]: case for case in ranked["cases"]}
    reviewed = {}
    for judgment in judgments["cases"]:
        if (not isinstance(judgment, dict) or set(judgment) - {
                "case_id", "outcome", "candidates", "contract_notes"}):
            raise ValueError("invalid judgment fields")
        case_id = judgment.get("case_id")
        if case_id not in ranked_cases or case_id in reviewed:
            raise ValueError(f"unknown or duplicate judgment case: {case_id}")
        candidates = judgment.get("candidates")
        if not isinstance(candidates, list) or len(candidates) > 5:
            raise ValueError(f"invalid candidate judgments: {case_id}")
        expected_ids = [item["icon_id"] for item in ranked_cases[case_id]["results"][:5]]
        actual_ids = []
        for candidate in candidates:
            if (not isinstance(candidate, dict) or set(candidate) != {"icon_id", "label", "reason"}
                    or candidate.get("label") not in {"useful", "partial", "unsuitable"}
                    or not isinstance(candidate.get("reason"), str) or not candidate["reason"].strip()):
                raise ValueError(f"invalid candidate judgment: {case_id}")
            actual_ids.append(candidate["icon_id"])
        if actual_ids != expected_ids:
            raise ValueError(f"judgments do not cover the ranked top five in order: {case_id}")
        violations = ranked_cases[case_id]["contract_violations"]
        useful = any(candidate["label"] == "useful" for candidate in candidates)
        expected_outcome = ("contract_failure" if violations else "useful_hit" if useful
                            else "expected_empty" if not candidates else "no_useful_hit")
        if judgment.get("outcome") != expected_outcome:
            raise ValueError(f"judgment outcome disagrees with labels/results: {case_id}")
        reviewed[case_id] = judgment
    if set(reviewed) != set(ranked_cases):
        raise ValueError("judgments do not cover every ranked case")
    positives = [case for case in ranked["cases"] if case["family"] != "exclusion_negative"]
    negatives = [case for case in ranked["cases"] if case["family"] == "exclusion_negative"]
    useful_hits = sum(reviewed[case["case_id"]]["outcome"] == "useful_hit" for case in positives)
    negative_successes = sum(reviewed[case["case_id"]]["outcome"] in {
        "expected_empty", "no_useful_hit"} for case in negatives)
    return {
        "score_schema_version": 1,
        "benchmark_sha256": ranked["benchmark_sha256"],
        "ranked_results_sha256": sha256(ranked_path),
        "judgments_sha256": sha256(judgments_path),
        "reviewer": judgments["reviewer"],
        "independent_review": judgments["independent_review"],
        "positive_cases": len(positives),
        "useful_hit_at_5": useful_hits,
        "negative_cases": len(negatives),
        "negative_successes": negative_successes,
        "contract_violations": ranked["metrics"]["contract_violations"],
        "by_family": {family: {
            "cases": sum(case["family"] == family for case in positives),
            "useful_hits": sum(case["family"] == family
                               and reviewed[case["case_id"]]["outcome"] == "useful_hit"
                               for case in positives),
        } for family in sorted(FAMILIES - {"exclusion_negative"})},
    }


def write_new(path: Path, value: object) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError(f"refusing to overwrite output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, ensure_ascii=False, indent=2,
                                sort_keys=True).encode("utf-8") + b"\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--benchmark", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ranked-results", type=Path,
                        help="score this prior output instead of running retrieval")
    parser.add_argument("--judgments", type=Path,
                        help="visual labels used with --ranked-results")
    args = parser.parse_args()
    try:
        if args.ranked_results:
            if not args.judgments or args.package or args.benchmark:
                raise ValueError("scoring requires only --ranked-results and --judgments")
            result = score(args.ranked_results.resolve(strict=True),
                           args.judgments.resolve(strict=True))
        else:
            if not args.package or not args.benchmark or args.judgments:
                raise ValueError("evaluation requires --package and --benchmark")
            result = evaluate(args.package.resolve(strict=True),
                              args.benchmark.resolve(strict=True))
        write_new(args.output.resolve(), result)
        print(json.dumps({"output": args.output.as_posix(),
                          "metrics": result.get("metrics", result)}, sort_keys=True))
    except (ValueError, OSError, sqlite3.Error, json.JSONDecodeError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
