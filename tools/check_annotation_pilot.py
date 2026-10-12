"""Validate model-produced pilot annotations against the frozen sample manifest."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


LIST_FIELDS = ("keywords", "subjects", "materials", "colors", "effects", "symbols",
               "inferred_uses", "uncertainties")
TEXT_FIELDS = ("description", "composition")
OPTIONAL_TEXT_FIELDS = ("action", "visible_text", "state")
MOTIF_VALUES = {"yes", "no", "uncertain", "not_applicable"}


def validate(root: Path) -> dict:
    manifest = json.loads((root / "pilot-manifest.json").read_text(encoding="utf-8"))
    schema = json.loads((Path(__file__).with_name("annotation_response_schema_v1.json")).read_text(
        encoding="utf-8"))
    expected = {item["number"]: item for item in manifest["sample"]}
    if set(expected) != set(range(1, 101)):
        raise ValueError("pilot manifest does not contain exactly sample numbers 1..100")
    fields = set(schema["required"])
    found: dict[int, dict] = {}
    result_files = sorted((root / "results").glob("part_*.jsonl"))
    if not result_files:
        raise ValueError("no pilot annotation results found")
    for result_file in result_files:
        with result_file.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{result_file.name}:{line_number}: invalid JSON: {exc}") from exc
                number = row.get("number")
                if type(number) is not int or number not in expected or number in found:
                    raise ValueError(f"{result_file.name}:{line_number}: unknown or duplicate number")
                if row.get("icon_id") != expected[number]["icon_id"]:
                    raise ValueError(f"{result_file.name}:{line_number}: icon ID mismatch")
                annotation = row.get("annotation")
                if not isinstance(annotation, dict) or set(annotation) != fields:
                    raise ValueError(f"{result_file.name}:{line_number}: annotation fields differ from schema")
                for name in TEXT_FIELDS:
                    if not isinstance(annotation[name], str) or not annotation[name].strip():
                        raise ValueError(f"{result_file.name}:{line_number}: empty {name}")
                for name in OPTIONAL_TEXT_FIELDS:
                    if annotation[name] is not None and not isinstance(annotation[name], str):
                        raise ValueError(f"{result_file.name}:{line_number}: invalid {name}")
                for name in LIST_FIELDS:
                    values = annotation[name]
                    if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip()
                                                           for v in values):
                        raise ValueError(f"{result_file.name}:{line_number}: invalid {name}")
                    if len({v.casefold().strip() for v in values}) != len(values):
                        raise ValueError(f"{result_file.name}:{line_number}: duplicate {name}")
                if not annotation["keywords"]:
                    raise ValueError(f"{result_file.name}:{line_number}: no keywords")
                motif = annotation["same_motif_across_renditions"]
                if motif not in MOTIF_VALUES:
                    raise ValueError(f"{result_file.name}:{line_number}: invalid motif comparison")
                two_images = len(expected[number]["renditions"]) == 2
                if two_images == (motif == "not_applicable"):
                    raise ValueError(f"{result_file.name}:{line_number}: wrong motif applicability")
                found[number] = row
    missing = sorted(set(expected) - set(found))
    if missing:
        raise ValueError(f"missing sample numbers: {missing}")
    category_counts = Counter(category for item in expected.values() for category in item["categories"])
    motif_counts = Counter(row["annotation"]["same_motif_across_renditions"] for row in found.values())
    return {"ok": True, "icons": len(found), "result_files": [f.name for f in result_files],
            "categories": dict(sorted(category_counts.items())),
            "motif_comparisons": dict(sorted(motif_counts.items())),
            "with_uncertainties": sum(bool(row["annotation"]["uncertainties"]) for row in found.values()),
            "keyword_count_min": min(len(row["annotation"]["keywords"]) for row in found.values()),
            "keyword_count_max": max(len(row["annotation"]["keywords"]) for row in found.values())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.pilot), sort_keys=True))


if __name__ == "__main__":
    main()
