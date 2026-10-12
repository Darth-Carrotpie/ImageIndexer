"""Measure development requests with fresh and warmed readers, never flush OS caches."""
import argparse
import json
import os
from pathlib import Path
import platform
import sqlite3
import time

from evaluate_search_v2 import load_benchmark, peak_working_set_bytes, percentile, sha256, write_new
from iconctl import open_catalog, run_search_request


def measure(package: Path, benchmark: Path, output: Path) -> None:
    if output.exists():
        raise ValueError("performance evidence must be new")
    data = load_benchmark(benchmark)
    if data["set_kind"] != "development":
        raise ValueError("performance rehearsal uses only exposed development cases")
    requests = [case["request"] for case in data["cases"]]
    fresh, warm, expected = [], [], []
    for request in requests:
        started = time.perf_counter()
        db, _, _ = open_catalog(package)
        try:
            result = run_search_request(db, request)
            fresh.append((time.perf_counter() - started) * 1000)
            expected.append([item["icon_id"] for item in result["results"]])
        finally:
            db.close()
    db, version, _ = open_catalog(package)
    try:
        for request in requests:
            run_search_request(db, request)
        for request, ids in zip(requests, expected):
            started = time.perf_counter()
            result = run_search_request(db, request)
            warm.append((time.perf_counter() - started) * 1000)
            if [item["icon_id"] for item in result["results"]] != ids:
                raise ValueError("fresh/warm results differ")
        fts_bytes = db.execute("SELECT sum(pgsize) FROM dbstat WHERE name LIKE 'icon_fts%'").fetchone()[0]
    finally:
        db.close()
    report = {
        "catalog_sqlite_sha256": sha256(package / "catalog.sqlite"),
        "benchmark_sha256": sha256(benchmark), "version": version,
        "requests_per_mode": len(requests), "identical_result_ids": True,
        "milliseconds": {name: {"p50": percentile(values, .5), "p95": percentile(values, .95)}
                         for name, values in (("fresh_reader_including_open", fresh), ("warm_query", warm))},
        "database_bytes": (package / "catalog.sqlite").stat().st_size,
        "fts_storage_bytes": fts_bytes, "process_peak_working_set_bytes": peak_working_set_bytes(),
        "environment": {"os": platform.platform(), "python": platform.python_version(),
                        "sqlite": sqlite3.sqlite_version, "logical_cpus": os.cpu_count(),
                        "processor": platform.processor()},
        "limitations": "OS file cache not flushed; fresh reader is not cold disk. One workstation, no latency SLA.",
    }
    write_new(output, report)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    measure(args.package.resolve(strict=True), args.benchmark, args.output)
