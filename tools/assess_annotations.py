"""Read-only annotation integrity and provisional FTS5 search assessment."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from iconctl import legacy_search_icons
from annotation_data import load_annotations, sha256


QUERIES = (
    "blue shield with frost aura",
    "open treasure chest glowing",
    "flaming sword",
    "purple crystal",
    "red potion bottle",
    "gold coin",
    "open book",
    "bow with arrow",
    "bat in front of moon",
    "green skull",
    "ice axe",
    "lightning staff",
    "sunflower seeds in a dish",
    "blue armored gauntlets",
    "copper pliers with curved jaws",
    "exploding spiked bomb",
    "glowing orange rune ring",
    "green potion bottle",
    "glowing green rune scroll",
    "hooded mage in blood rain",
    "blue magic arrows flying",
    "brown gourd with leaf",
    "red belt with fiery eye",
    "bundle of arrows tied",
)
TARGETS = {
    "open treasure chest glowing": "icon_3ad39f24-8b3d-4f10-a9d5-56911f3b3815",
    "flaming sword": "icon_b5bd04b3-c8a9-4181-a02a-922d3fec93c6",
    "purple crystal": "icon_dbb585c0-bb1d-4af2-b693-e3c1a7d06581",
    "red potion bottle": "icon_09df51c1-62c9-489a-bb19-5dda7fe08c13",
    "gold coin": "icon_1e0d7c7f-47d0-4ccf-a245-37c916ff9cc7",
    "open book": "icon_6f403d17-0c7b-4305-99ba-d044819f6186",
    "bow with arrow": "icon_335bff94-8033-47fe-823d-e3197680924b",
    "bat in front of moon": "icon_219dfadb-90fc-4f06-8e0d-de787704efe7",
    "green skull": "icon_de30461b-2ddb-486a-9395-23f01c11b19f",
    "sunflower seeds in a dish": "icon_a2182baa-a9af-4f3f-aaa6-6fa4d949355e",
    "blue armored gauntlets": "icon_e3f2190a-6d0b-4495-be6b-71c870a2d4a7",
    "copper pliers with curved jaws": "icon_469ecf01-fdfa-45de-aaeb-66bbf8fa9368",
    "exploding spiked bomb": "icon_037bd1dd-7f8a-4dec-969c-149280629331",
    "glowing orange rune ring": "icon_1abb09a9-e88b-4392-b585-d7b5729c3db0",
    "green potion bottle": "icon_2fbbc980-becc-4b05-9cac-8efd50133592",
    "glowing green rune scroll": "icon_5dc391bb-f8a2-4238-8145-c48759dea62b",
    "hooded mage in blood rain": "icon_72eb234e-6c12-4ffe-89bf-829b27995d23",
    "blue magic arrows flying": "icon_89cf534a-2099-46ca-9f2e-b64ef5128f76",
    "brown gourd with leaf": "icon_b7053bc0-bb8b-437f-8cdc-803d58de3966",
    "red belt with fiery eye": "icon_cf3d3379-3a33-4843-a985-f1049111227c",
    "bundle of arrows tied": "icon_fbbc8a1a-a4c6-464a-820c-34d40b85585a",
}
def ranked_digest(results: list[dict]) -> str:
    return hashlib.sha256(json.dumps(results, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def score_judgments(results: list[dict], benchmark_sha: str, review_sha: str | None,
                    judgments: Path) -> dict:
    data = json.loads(judgments.read_text(encoding="utf-8"))
    ranked_sha = ranked_digest(results)
    if (not isinstance(data, dict) or data.get("judgment_schema_version") != 1
            or data.get("benchmark_sha256") != benchmark_sha
            or data.get("review_sha256") != review_sha
            or data.get("ranked_results_sha256") != ranked_sha
            or not isinstance(data.get("rubric"), str) or not data["rubric"].strip()
            or not isinstance(data.get("misses"), list)):
        raise ValueError("visual judgments do not match this ranked benchmark")
    misses = {row["target"]: row for row in results
              if row["annotated_target_rank_top100"] is None
              or row["annotated_target_rank_top100"] > 5}
    reviewed = {}
    for item in data["misses"]:
        if (not isinstance(item, dict) or set(item) != {"target", "matching_icon_id", "reason"}
                or not isinstance(item["target"], str) or item["target"] in reviewed
                or item["target"] not in misses or not isinstance(item["reason"], str)
                or not item["reason"].strip()
                or (item["matching_icon_id"] is not None
                    and (not isinstance(item["matching_icon_id"], str)
                         or item["matching_icon_id"] not in misses[item["target"]]["annotated_top5"]))):
            raise ValueError("invalid or incomplete visual judgment")
        reviewed[item["target"]] = item
    if set(reviewed) != set(misses):
        raise ValueError("visual judgments do not cover every exact-target miss")
    issues = data.get("prompt_issues", [])
    targets = {row["target"] for row in results}
    if (not isinstance(issues, list) or any(not isinstance(item, dict)
            or set(item) != {"target", "status", "issue"}
            or not isinstance(item["target"], str) or item["target"] not in targets
            or item["status"] not in ("invalid", "ambiguous")
            or not isinstance(item["issue"], str) or not item["issue"].strip() for item in issues)
            or len({item["target"] for item in issues}) != len(issues)):
        raise ValueError("invalid benchmark prompt adjudication")
    alternatives = sum(item["matching_icon_id"] is not None for item in reviewed.values())
    return {"relevant_top5": len(results) - len(misses) + alternatives,
            "total_queries": len(results), "exact_target_top5": len(results) - len(misses),
            "relevant_alternative_hits": alternatives,
            "invalid_prompts": sum(item["status"] == "invalid" for item in issues),
            "ambiguous_prompts": sum(item["status"] == "ambiguous" for item in issues),
            "gate_eligible": not issues,
            "judgment_sha256": sha256(judgments), "ranked_results_sha256": ranked_sha}


def assess(candidate: Path, run: Path, benchmark: Path | None = None,
           review: Path | list[Path] | None = None, judgments: Path | None = None,
           supplemental: Path | None = None) -> dict:
    if judgments is not None and benchmark is None:
        raise ValueError("visual judgments require a benchmark")
    annotation_path = run / "annotations.jsonl"
    review_paths = [review] if isinstance(review, Path) else review or []
    loaded = load_annotations(run, review_paths)
    plan, metering = loaded["plan"], loaded["metering"]
    manifest = loaded["manifest"]
    annotations, effective = loaded["raw_annotations"], loaded["annotations"]
    reviewed_terms = loaded["reviewed_terms"]
    review_info = loaded["review_chain"][-1] if loaded["review_chain"] else None
    stats = loaded["stats"]
    input_tokens, output_tokens = loaded["input_tokens"], loaded["output_tokens"]
    batch_usd = loaded["estimated_batch_usd"]
    supplemental_terms, supplemental_failures = {}, []
    if supplemental is not None:
        pilot_plan = json.loads((supplemental / "plan.json").read_text(encoding="utf-8"))
        pilot_metering = json.loads((supplemental / "metering.json").read_text(encoding="utf-8"))
        result_path = supplemental / "results.jsonl"
        if (pilot_plan.get("source_annotations_sha256") != sha256(annotation_path)
                or pilot_plan.get("review_sha256") != (review_info or {}).get("review_sha256")
                or pilot_metering.get("results_sha256") != sha256(result_path)):
            raise ValueError("supplemental pilot is not pinned to these annotations and reviews")
        for row in map(json.loads, result_path.read_text(encoding="utf-8").splitlines()):
            icon_id, terms = row["icon_id"], row["terms"]
            if (icon_id not in manifest or icon_id in supplemental_terms or not isinstance(terms, list)
                    or len(terms) > 8 or any(not isinstance(term, str) or not term.strip()
                    or term != term.casefold() or len(term) > 80 for term in terms)):
                raise ValueError(f"invalid supplemental terms: {icon_id}")
            supplemental_terms[icon_id] = terms
        missing = set(pilot_plan["selected_ids"]) - set(supplemental_terms)
        if missing:
            failures_path = supplemental / "failures.json"
            if (pilot_metering.get("failures_sha256") != sha256(failures_path)
                    or pilot_metering.get("missing_icons") != 0):
                raise ValueError("supplemental failures are not fully accounted for")
            failed_rows = json.loads(failures_path.read_text(encoding="utf-8"))["failures"]
            if (len(failed_rows) != len(missing) or {row["icon_id"] for row in failed_rows} != missing
                    or pilot_metering["failed_icons"] != len(missing)):
                raise ValueError("supplemental missing results differ from recorded failures")
            supplemental_failures = sorted(missing)
        if (set(supplemental_terms) | set(supplemental_failures)) != set(pilot_plan["selected_ids"]):
            raise ValueError("supplemental result coverage differs from frozen pilot")

    blind_cases = []
    if benchmark is not None:
        data = json.loads(benchmark.read_text(encoding="utf-8"))
        if data.get("benchmark_schema_version") != 1 or not isinstance(data.get("cases"), list):
            raise ValueError("invalid search benchmark")
        blind_cases = data["cases"]
        if (not blind_cases or any(not isinstance(case, dict) for case in blind_cases)
                or len({case.get("icon_id") for case in blind_cases}) != len(blind_cases)
                or len({case.get("query") for case in blind_cases}) != len(blind_cases)
                or any(case.get("icon_id") not in annotations or not isinstance(case.get("query"), str)
                       or not case["query"].strip() for case in blind_cases)):
            raise ValueError("search benchmark has duplicate, unknown, or empty cases")

    source = sqlite3.connect(f"file:{(candidate / 'catalog.sqlite').resolve().as_posix()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    enriched = sqlite3.connect(":memory:")
    enriched.row_factory = sqlite3.Row
    try:
        source.backup(enriched)
        icons = {row["icon_id"]: row for row in enriched.execute(
            "SELECT icon_id,title,collection FROM icon")}
        if set(icons) != set(annotations):
            raise ValueError("candidate catalog IDs differ from annotation IDs")
        enriched.execute("DELETE FROM icon_fts")
        enriched.executemany("UPDATE icon SET description=? WHERE icon_id=?", (
            (annotation["description"], icon_id) for icon_id, annotation in effective.items()))
        enriched.executemany("INSERT INTO icon_fts VALUES (?,?,?,?,?)", (
            (icon_id, icons[icon_id]["title"], icons[icon_id]["collection"],
             annotation["description"], " ".join(
                 [keyword.casefold() for keyword in annotation["keywords"]]
                 + (reviewed_terms or {}).get(icon_id, []) + supplemental_terms.get(icon_id, [])))
            for icon_id, annotation in effective.items()))
        output = []
        for query in QUERIES:
            baseline = legacy_search_icons(source, query, 100)
            improved = legacy_search_icons(enriched, query, 100)
            target = TARGETS.get(query)
            if target is not None and target not in annotations:
                raise ValueError(f"benchmark target is missing: {query}")
            baseline_rank = next((index for index, row in enumerate(baseline, 1)
                                  if row["icon_id"] == target), None)
            annotated_rank = next((index for index, row in enumerate(improved, 1)
                                   if row["icon_id"] == target), None)
            output.append({"query": query,
                           "target": target, "baseline_target_rank_top100": baseline_rank,
                           "annotated_target_rank_top100": annotated_rank,
                           "baseline_top5": [{"icon_id": row["icon_id"],
                                              "source_key": manifest[row["icon_id"]]["source_key"],
                                              "description": annotations[row["icon_id"]]["description"]}
                                             for row in baseline[:5]],
                           "annotated_top5": [{"icon_id": row["icon_id"],
                                               "source_key": manifest[row["icon_id"]]["source_key"],
                                               "description": row["description"]}
                                              for row in improved[:5]]})
        blind_results = []
        for case in blind_cases:
            query, target = case["query"], case["icon_id"]
            baseline = legacy_search_icons(source, query, 100)
            improved = legacy_search_icons(enriched, query, 100)
            blind_results.append({
                "query": query, "target": target,
                "baseline_target_rank_top100": next((i for i, row in enumerate(baseline, 1)
                                                    if row["icon_id"] == target), None),
                "annotated_target_rank_top100": next((i for i, row in enumerate(improved, 1)
                                                     if row["icon_id"] == target), None),
                "annotated_top5": [row["icon_id"] for row in improved[:5]],
            })
    finally:
        source.close()
        enriched.close()
    quality = (score_judgments(blind_results, sha256(benchmark),
                               review_info["review_sha256"] if review_info else None, judgments)
               if judgments else None)
    return {"validated_icons": len(annotations), "input_tokens": input_tokens,
            "output_tokens": output_tokens, "estimated_batch_usd": batch_usd,
            "checks": stats, "queries": output,
            "review": review_info,
            "supplemental_pilot_results_sha256": sha256(supplemental / "results.jsonl") if supplemental else None,
            "supplemental_failed_icons_using_base_metadata": supplemental_failures,
            "blind_benchmark_sha256": sha256(benchmark) if benchmark else None,
            "blind_ranked_results_sha256": ranked_digest(blind_results) if benchmark else None,
            "blind_benchmark": blind_results, "visual_quality": quality}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path)
    parser.add_argument("--review", type=Path, nargs="+",
                        help="ordered preview-pinned corrections applied only in memory")
    parser.add_argument("--judgments", type=Path, help="preview-reviewed relevance for exact-target misses")
    parser.add_argument("--supplemental", type=Path, help="provisional pilot search phrases, not accepted catalog data")
    parser.add_argument("--output", type=Path, help="save the assessment JSON for reproducible comparisons")
    args = parser.parse_args()
    result = json.dumps(assess(args.candidate, args.run, args.benchmark, args.review, args.judgments,
                               args.supplemental), ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(result + "\n", encoding="utf-8")
        print(f"Assessment saved to {args.output}")
    else:
        print(result)


if __name__ == "__main__":
    main()
