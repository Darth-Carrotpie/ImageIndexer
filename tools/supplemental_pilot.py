"""Freeze, submit, collect and meter a 100-icon supplemental-search-vocabulary pilot."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from annotation_review import apply_review
from full_annotation_batch import client_for_api, save_json
from metered_calibration import PRICE_PER_MILLION, annotation_from, cost, digest

MODEL = "gpt-6-sol"
RUN_NAME = "supplemental-vocabulary-pilot-v1"
SOURCE = "full-annotation-gpt6-sol-high-v1"
TERMINAL = {"completed", "failed", "expired", "cancelled"}
ASTRA_PRICES = {"input": Decimal("10"), "cached_input": Decimal("1"),
                "cache_write": Decimal("12.5"), "output": Decimal("50")}


def freeze_astra(baseline: Path, output: Path) -> None:
    plan = checked_plan(baseline)
    if plan["model"] != MODEL or plan["reasoning_effort"] != "high" or output.exists():
        raise ValueError("Astra comparison needs the existing Sol pilot and a new output directory")
    rows = [json.loads(line) for line in (baseline / "input.jsonl").read_text(encoding="utf-8").splitlines()]
    for row in rows:
        row["body"]["model"] = "gpt-6-astra"
        row["body"]["reasoning"]["effort"] = "max"
        row["body"]["max_output_tokens"] = 4096
    output.mkdir(parents=True)
    with (output / "input.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    plan.update({"model": "gpt-6-astra", "reasoning_effort": "max",
                 "max_output_tokens_per_request": 4096,
                 "baseline_plan_sha256": digest(baseline / "plan.json"),
                 "baseline_input_sha256": plan["input_sha256"],
                 "input_sha256": digest(output / "input.jsonl"),
                 "comparison_changes": ["model", "reasoning.effort", "max_output_tokens"],
                 "standard_price_per_million_usd": {k: str(v) for k, v in ASTRA_PRICES.items()},
                 "pricing_checked_at_utc": datetime.now(timezone.utc).isoformat()})
    save_json(output / "plan.json", plan)
    checked_plan(output)
    print(json.dumps({"frozen": 100, "model": plan["model"], "reasoning_effort": "max",
                      "plan_sha256": digest(output / "plan.json"), "input_bytes": (output / "input.jsonl").stat().st_size}))


def sources(package: Path) -> tuple[Path, Path]:
    return package / "work" / SOURCE, package / "work" / "preannotation-v1"


def freeze(package: Path, output: Path) -> None:
    if output.exists():
        raise ValueError("pilot output already exists")
    run, candidate = sources(package)
    metering = json.loads((run / "metering.json").read_text(encoding="utf-8"))
    if digest(run / "annotations.jsonl") != metering["annotation_sha256"]:
        raise ValueError("source annotations changed")
    source_plan = json.loads((run / "plan.json").read_text(encoding="utf-8"))
    if digest(run / "icons.jsonl") != source_plan["icons_manifest_sha256"]:
        raise ValueError("source icon manifest changed")
    manifest = {x["icon_id"]: x for x in map(json.loads, (run / "icons.jsonl").read_text(encoding="utf-8").splitlines())}
    annotations = {x["icon_id"]: x["annotation"] for x in map(json.loads, (run / "annotations.jsonl").read_text(encoding="utf-8").splitlines())}
    if len(manifest) != len(annotations) or set(manifest) != set(annotations):
        raise ValueError("source coverage mismatch")
    reviews = [run / f"REVIEWED_CORRECTIONS_V{i}.json" for i in (1, 2)]
    effective, reviewed_terms, review_info = annotations, None, None
    for path in reviews:
        effective, reviewed_terms, review_info = apply_review(
            effective, manifest, metering["annotation_sha256"], path, reviewed_terms, review_info)
    benchmark_path = run / "SEARCH_BENCHMARK_V4.json"
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    benchmark_ids = [row["icon_id"] for row in benchmark["cases"]]
    if len(benchmark_ids) != 50 or len(set(benchmark_ids)) != 50:
        raise ValueError("V4 benchmark does not contain 50 unique targets")
    db = sqlite3.connect(f"file:{(candidate / 'catalog.sqlite').resolve().as_posix()}?mode=ro", uri=True)
    try:
        collection = dict(db.execute("SELECT icon_id, collection FROM icon"))
    finally:
        db.close()
    if set(collection) != set(manifest):
        raise ValueError("candidate icon IDs changed")
    seen_collections = {collection[icon_id] for icon_id in benchmark_ids}
    controls = []
    for icon_id in sorted(set(manifest) - set(benchmark_ids), key=lambda item: hashlib.sha256(
            (RUN_NAME + ":" + item).encode()).digest()):
        name = collection[icon_id]
        if name not in seen_collections:
            controls.append(icon_id)
            seen_collections.add(name)
        if len(controls) == 50:
            break
    if len(controls) != 50:
        raise ValueError("not enough distinct untouched collections for controls")
    selected = benchmark_ids + controls
    prompt_path = Path(__file__).with_name("supplemental_prompt_v1.txt")
    schema_path = Path(__file__).with_name("supplemental_schema_v1.json")
    prompt = prompt_path.read_text(encoding="utf-8")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    output.mkdir(parents=True)
    input_path = output / "input.jsonl"
    with input_path.open("w", encoding="utf-8", newline="\n") as stream:
        for icon_id in selected:
            preview = run / "previews" / f"{icon_id}.png"
            if digest(preview) != manifest[icon_id]["preview_sha256"]:
                raise ValueError(f"preview changed: {icon_id}")
            annotation = effective[icon_id]
            prior = {"description": annotation["description"], "keywords": annotation["keywords"],
                     "reviewed_terms": reviewed_terms.get(icon_id, [])}
            body = {"model": MODEL, "reasoning": {"effort": "high"}, "store": False,
                    "max_output_tokens": 1500,
                    "input": [{"role": "system", "content": prompt},
                              {"role": "user", "content": [
                                  {"type": "input_text", "text": "Existing metadata: " + json.dumps(prior, ensure_ascii=False)},
                                  {"type": "input_image", "detail": "high", "image_url":
                                   "data:image/png;base64," + base64.b64encode(preview.read_bytes()).decode("ascii")}
                              ]}],
                    "text": {"format": {"type": "json_schema", "name": "supplemental_vocabulary_v1",
                                        "strict": True, "schema": schema}}}
            stream.write(json.dumps({"custom_id": icon_id, "method": "POST", "url": "/v1/responses",
                                     "body": body}, ensure_ascii=False, separators=(",", ":")) + "\n")
    plan = {"schema_version": 1, "model": MODEL, "reasoning_effort": "high", "count": 100,
            "selection": "50 V4 targets in benchmark order plus 50 SHA-256-ranked icons from distinct non-V4 collections",
            "benchmark_sha256": digest(benchmark_path), "source_annotations_sha256": metering["annotation_sha256"],
            "source_manifest_sha256": source_plan["icons_manifest_sha256"],
            "effective_annotation_sha256": review_info["accepted_annotation_sha256"],
            "review_sha256": review_info["review_sha256"], "prompt_sha256": digest(prompt_path),
            "schema_sha256": digest(schema_path), "input_sha256": digest(input_path),
            "selected_ids": selected, "max_output_tokens_per_request": 1500,
            "pricing_source": "https://developers.openai.com/api/docs/pricing", "processing_tier": "batch"}
    save_json(output / "plan.json", plan)
    print(json.dumps({"frozen": 100, "benchmark_targets": 50, "controls": 50,
                      "input_bytes": input_path.stat().st_size, "plan_sha256": digest(output / "plan.json")}))


def checked_plan(output: Path) -> dict:
    plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
    if ((plan["model"], plan["reasoning_effort"]) not in {(MODEL, "high"), ("gpt-6-astra", "max")}
            or plan["count"] != 100
            or len(set(plan["selected_ids"])) != 100 or digest(output / "input.jsonl") != plan["input_sha256"]):
        raise ValueError("pilot plan or input changed")
    rows = [json.loads(line) for line in (output / "input.jsonl").read_text(encoding="utf-8").splitlines()]
    if len(rows) != 100 or [row["custom_id"] for row in rows] != plan["selected_ids"]:
        raise ValueError("pilot request IDs changed")
    for row in rows:
        body = row["body"]
        if (row["method"] != "POST" or row["url"] != "/v1/responses"
                or body["model"] != plan["model"] or body["reasoning"]["effort"] != plan["reasoning_effort"]
                or body["max_output_tokens"] != plan["max_output_tokens_per_request"]
                or body["store"] is not False):
            raise ValueError("pilot request settings differ from plan")
    expected_prices = ASTRA_PRICES if plan["model"] == "gpt-6-astra" else PRICE_PER_MILLION
    prices = {k: Decimal(v) for k, v in plan.get("standard_price_per_million_usd", expected_prices).items()}
    if prices != expected_prices or plan["max_output_tokens_per_request"] not in (1500, 4096):
        raise ValueError("pilot prices or output limit differ from approved profiles")
    return plan


def submit(output: Path) -> None:
    plan = checked_plan(output)
    if (output / "state.json").exists():
        raise ValueError("pilot submission already attempted; inspect state before retrying")
    client = client_for_api()
    with (output / "input.jsonl").open("rb") as stream:
        uploaded = client.files.create(file=stream, purpose="batch")
    state = {"plan_sha256": digest(output / "plan.json"), "input_file_id": uploaded.id,
             "create_attempted": True}
    save_json(output / "state.json", state)
    batch = client.batches.create(input_file_id=uploaded.id, endpoint="/v1/responses",
                                  completion_window="24h", metadata={"run": output.name,
                                                                       "input_sha256": plan["input_sha256"]})
    state.update({"batch_id": batch.id, "status": batch.status})
    save_json(output / "state.json", state)
    print(json.dumps({"batch_id": batch.id, "status": batch.status, "requests": 100}))


def status(output: Path) -> dict:
    checked_plan(output)
    state = json.loads((output / "state.json").read_text(encoding="utf-8"))
    if state["plan_sha256"] != digest(output / "plan.json") or not state.get("batch_id"):
        raise ValueError("batch creation outcome uncertain; reconcile manually")
    batch = client_for_api().batches.retrieve(state["batch_id"])
    state.update({"status": batch.status, "output_file_id": batch.output_file_id,
                  "error_file_id": batch.error_file_id,
                  "errors": batch.errors.model_dump() if batch.errors else None,
                  "request_counts": batch.request_counts.model_dump() if batch.request_counts else None})
    save_json(output / "state.json", state)
    print(json.dumps({"status": batch.status, "request_counts": state["request_counts"]}))
    return state


def collect(output: Path) -> None:
    plan = checked_plan(output)
    state = status(output)
    if state["status"] not in TERMINAL:
        raise ValueError("batch is not finished")
    client = client_for_api()
    for kind in ("output", "error"):
        file_id = state.get(kind + "_file_id")
        path = output / (kind + ".jsonl")
        if file_id and not path.exists():
            path.write_bytes(client.files.content(file_id).read())
    rows = [json.loads(line) for kind in ("output", "error") if (output / (kind + ".jsonl")).exists()
            for line in (output / (kind + ".jsonl")).read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = set(plan["selected_ids"])
    results, seen, failures, usage_rows = {}, set(), [], []
    fallback_prices = ASTRA_PRICES if plan["model"] == "gpt-6-astra" else PRICE_PER_MILLION
    prices = {k: Decimal(v) for k, v in plan.get("standard_price_per_million_usd", fallback_prices).items()}
    for row in rows:
        icon_id = row["custom_id"]
        if icon_id not in ids or icon_id in seen:
            raise ValueError(f"duplicate or unknown response: {icon_id}")
        seen.add(icon_id)
        response = row.get("response") or {}
        body = response.get("body") or {}
        usage = body.get("usage")
        if isinstance(usage, dict):
            usage_rows.append({"icon_id": icon_id, "usage": usage,
                               "estimated_batch_usd": str(cost(usage, prices) * Decimal("0.5"))})
        try:
            if response.get("status_code") != 200 or body.get("model") != plan["model"]:
                raise ValueError("unsuccessful response or unexpected model")
            value = annotation_from(body, {"required": ["terms", "uncertainties"]})
            if (any(not isinstance(value[key], list) or any(not isinstance(x, str) or not x.strip()
                    for x in value[key]) for key in value) or len(value["terms"]) > 8
                    or len(set(value["terms"])) != len(value["terms"])
                    or any(term != term.casefold() or len(term) > 80 for term in value["terms"])
                    or not isinstance(usage, dict)):
                raise ValueError("invalid structured result or absent metering")
        except (ValueError, KeyError) as exc:
            failures.append({"icon_id": icon_id, "reason": str(exc),
                             "error": row.get("error"), "incomplete_details": body.get("incomplete_details")})
            continue
        results[icon_id] = {"icon_id": icon_id, "response_id": body.get("id"), "usage": usage,
                            "response_model": body["model"],
                            "estimated_batch_usd": str(cost(usage, prices) * Decimal("0.5")), **value}
    path = output / "results.jsonl"
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for icon_id in plan["selected_ids"]:
            if icon_id in results:
                stream.write(json.dumps(results[icon_id], ensure_ascii=False, sort_keys=True) + "\n")
    total_cost = sum((Decimal(x["estimated_batch_usd"]) for x in usage_rows), Decimal(0))
    summary = {"completed_icons": len(results), "failed_icons": len(failures), "missing_icons": len(ids - seen),
               "model": plan["model"], "reasoning_effort": plan["reasoning_effort"],
               "requests_with_usage": len(usage_rows), "requests_without_usage": len(seen) - len(usage_rows),
               "input_tokens": sum(x["usage"]["input_tokens"] for x in usage_rows),
               "output_tokens": sum(x["usage"]["output_tokens"] for x in usage_rows),
               "estimated_batch_usd": str(total_cost),
               "projected_6250_attempts_batch_usd": str((total_cost * 6250 / 100).quantize(Decimal("0.01"))) if len(usage_rows) == 100 else None,
               "projected_6250_batch_usd": str((total_cost * 6250 / 100).quantize(Decimal("0.01"))) if len(results) == 100 else None,
               "results_sha256": digest(path), "input_sha256": plan["input_sha256"]}
    save_json(output / "failures.json", {"failures": failures, "metered_requests": usage_rows})
    summary["failures_sha256"] = digest(output / "failures.json")
    save_json(output / "metering.json", summary)
    print(json.dumps(summary, sort_keys=True))
    if len(seen) == 100 and "baseline_plan_sha256" in plan and "benchmark_sha256" in plan:
        from assess_annotations import assess
        work = output.resolve().parent
        source = work / SOURCE
        judgments = output / "ASTRA_V4_JUDGMENTS.json"
        assessment = assess(work / "preannotation-v1", source, source / "SEARCH_BENCHMARK_V4.json",
                            [source / "REVIEWED_CORRECTIONS_V1.json", source / "REVIEWED_CORRECTIONS_V2.json"],
                            judgments=judgments if judgments.exists() else None, supplemental=output)
        save_json(output / "assessment-astra.json", assessment)
        hits = sum((row["annotated_target_rank_top100"] or 101) <= 5 for row in assessment["blind_benchmark"])
        print(json.dumps({"astra_exact_target_top5": hits, "queries": len(assessment["blind_benchmark"])}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "freeze-astra", "submit", "status", "collect"))
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, help="frozen Sol pilot used for the Astra comparison")
    args = parser.parse_args()
    if args.command == "freeze":
        freeze(args.package, args.output)
    elif args.command == "freeze-astra":
        if args.baseline is None:
            parser.error("freeze-astra requires --baseline")
        freeze_astra(args.baseline, args.output)
    elif args.command == "submit":
        submit(args.output)
    elif args.command == "status":
        status(args.output)
    else:
        collect(args.output)


if __name__ == "__main__":
    main()
