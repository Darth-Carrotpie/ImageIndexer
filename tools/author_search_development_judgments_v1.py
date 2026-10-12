#!/usr/bin/env python3
"""Write the complete, self-reviewed visual judgments for development set v1."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


LABELS = {
    "literal": [
        "UPPPP", "PXPPP", "UPPPP", "UXPPP", "PXPXX",
        "PUPPP", "UXPPP", "UXXXP", "UPPPP", "UUPPP",
        "UPPPP", "UXXXX", "PUPPP", "UPPXX", "PPPPP",
        "UPPPP", "UPPPP", "XPXPP", "PUXPP", "UPXXX",
        "UPXXX", "PPPPP", "PPPUP", "UPXXP", "PPPPP",
        "UPPPP", "PPUPP", "UPPXP", "UPPPP", "UPPPP",
        "UPPPP", "PPPPP", "PPPPP", "PPXPP", "PPPPP",
        "PPPPP", "UPXPP", "PPPPX", "PUXPP", "PXPUP",
    ],
    "seed_modification": [
        "PPPPP", "PPPUP", "PPPPP", "XUXXX", "PPPPX",
        "UPPPX", "PPUPP", "PPPPP", "PPPPP", "PPPUP",
        "PUPPP", "XXPUX", "PXXPP", "PXXXP", "PPPPP",
        "PPPPP", "UPPPP", "PXPPU", "PPPPP", "PPPPP",
        "UXXXX", "PUPXX", "PPPPP", "UPPPX", "PPPPP",
        "UPPPP", "UPPPP", "PPUXP", "UPPPP", "UPPPP",
    ],
    "functional": [
        "PPPXX", "UUXPP", "PPUPP", "PPXXX", "PUPXX",
        "PPPPX", "PPPPX", "PUPPP", "XXXXX", "XXXXX",
        "XPPPP", "XXXXX", "UPPPX", "PXXXX", "PPPPP",
        "XXPPP", "PUPXX", "PPXXX", "UPPPP", "PPPPP",
    ],
}

LABEL_NAMES = {"U": "useful", "P": "partial", "X": "unsuitable"}
REVIEWED_RANKED_SHA256 = "2fff1cd831f0f6089231c85b2deea6bdb7bb7ff4c002b2e4b47e849b5980e8f5"
REASONS = {
    "U": "Visible candidate matches the subject and every required property.",
    "P": "Matches the subject or some properties, but not the full required combination.",
    "X": "Does not depict the required subject-and-property combination.",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(ranked_path: Path) -> dict:
    if sha256(ranked_path) != REVIEWED_RANKED_SHA256:
        raise ValueError("ranked results differ from the visually reviewed artifact")
    ranked = json.loads(ranked_path.read_text(encoding="utf-8"))
    expected_ids = {
        f"{family.replace('_modification', '')}-{index:03d}"
        for family, rows in LABELS.items()
        for index in range(1, len(rows) + 1)
    } | {f"negative-{index:03d}" for index in range(1, 11)}
    actual_ids = {case["case_id"] for case in ranked["cases"]}
    if actual_ids != expected_ids or len(actual_ids) != len(ranked["cases"]):
        raise ValueError("ranked cases do not match the reviewed development set")

    cases = []
    for case in ranked["cases"]:
        case_id = case["case_id"]
        violations = case["contract_violations"]
        if case["family"] == "exclusion_negative":
            if case["results"] or violations:
                raise ValueError(f"reviewed negative case changed: {case_id}")
            cases.append({"case_id": case_id, "outcome": "expected_empty", "candidates": []})
            continue

        number = int(case_id.rsplit("-", 1)[1])
        codes = LABELS[case["family"]][number - 1]
        if len(codes) != 5 or len(case["results"]) < 5 or violations:
            raise ValueError(f"reviewed positive case changed: {case_id}")
        candidates = [
            {
                "icon_id": result["icon_id"],
                "label": LABEL_NAMES[code],
                "reason": REASONS[code],
            }
            for result, code in zip(case["results"][:5], codes, strict=True)
        ]
        cases.append({
            "case_id": case_id,
            "outcome": "useful_hit" if "U" in codes else "no_useful_hit",
            "candidates": candidates,
        })

    return {
        "judgment_schema_version": 2,
        "benchmark_sha256": ranked["benchmark_sha256"],
        "ranked_results_sha256": sha256(ranked_path),
        "reviewer": "Codex visual development review; not independent",
        "independent_review": False,
        "holdout_exposure": (
            "Development set and results were visible to the implementation agent; "
            "these judgments are not acceptance evidence."
        ),
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ranked_results", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    ranked_path = args.ranked_results.resolve(strict=True)
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(build(ranked_path), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
