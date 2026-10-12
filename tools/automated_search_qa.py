"""Blinded, metered GPT-6 Sol High visual search QA; no runtime model dependency."""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import threading

from evaluate_search_v2 import canonical, score, sha256, write_new
from full_annotation_batch import client_for_api
from metered_calibration import annotation_from, cost, PRICE_PER_MILLION

MODEL = "gpt-6-sol"
JUDGE_PROMPT = """Judge the visual suitability of small, partly abstract game icons.
Use only the request, its required/optional visual properties, and supplied images.
Each image has an anonymous number. Judge every image independently.
useful: a reasonable reading visibly supports the required properties and intended
use. Accept synonymous names and plausible alternate interpretations of schematic
shapes. Do not demand a photorealistic object or one canonical label. Optional
details are not requirements. For functional requests accept a clear visual metaphor.
partial: relevant but a required visible property is missing, ambiguous beyond a
reasonable reading, or contradicted. unsuitable: unrelated or clearly contradictory.
Never invent unseen details, excuse a wrong required color/subject, or treat a
matching background as the required object. Explain briefly using visible evidence.
There is no quota of useful images. Do not infer usefulness from image order."""
JUDGE_SCHEMA = {"type": "object", "additionalProperties": False,
    "required": ["candidates"], "properties": {"candidates": {"type": "array",
    "items": {"type": "object", "additionalProperties": False,
    "required": ["number", "label", "reason"], "properties": {
        "number": {"type": "integer"},
        "label": {"type": "string", "enum": ["useful", "partial", "unsuitable"]},
        "reason": {"type": "string"}}}}}}


def image_input(path: Path, expected: str) -> dict:
    if sha256(path) != expected:
        raise ValueError("QA image hash changed")
    return {"type": "input_image", "detail": "high", "image_url":
            "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")}


def body(prompt: str, content: list[dict], schema: dict) -> dict:
    return {"model": MODEL, "reasoning": {"effort": "high"}, "store": False,
            "service_tier": "default", "max_output_tokens": 4096,
            "input": [{"role": "system", "content": prompt},
                      {"role": "user", "content": content}],
            "text": {"format": {"type": "json_schema", "name": "search_qa",
                                "strict": True, "schema": schema}}}


def judge_request(case: dict, package: Path) -> tuple[dict, list[str]]:
    candidates = sorted(case["results"][:5], key=lambda item: hashlib.sha256(
        (case["case_id"] + item["icon_id"]).encode()).digest())
    # IDs, metadata, ranks, scores and known targets never enter the model input.
    request = {key: case["request"][key] for key in ("text", "query", "require")
               if key in case["request"]}
    content = [{"type": "input_text", "text": json.dumps({"request": request,
        "required": case["required_visual_properties"],
        "optional": case["optional_visual_properties"]}, ensure_ascii=False)}]
    for number, item in enumerate(candidates, 1):
        path = (package / item["thumbnail_relative_path"]).resolve(strict=True)
        if not path.is_relative_to(package.resolve()):
            raise ValueError("QA thumbnail escapes package")
        content.extend([{"type": "input_text", "text": f"Image {number}"},
                        image_input(path, item["thumbnail_sha256"])])
    return body(JUDGE_PROMPT, content, JUDGE_SCHEMA), [x["icon_id"] for x in candidates]


def prepare_judge(package: Path, ranked: Path, output: Path) -> None:
    if output.exists():
        raise ValueError("QA output already exists")
    data = json.loads(ranked.read_text(encoding="utf-8"))
    if sha256(package / "catalog.sqlite") != data["catalog_sqlite_sha256"]:
        raise ValueError("ranked results do not match candidate")
    output.mkdir(parents=True)
    write_new(output / "ranked.json", data)
    requests = []
    for case in data["cases"]:
        if not case["results"]:
            continue
        payload, mapping = judge_request(case, package)
        request_path = output / "requests" / (case["case_id"] + ".json")
        write_new(request_path, payload)
        requests.append({"id": case["case_id"], "sha256": sha256(request_path),
                         "mapping": mapping})
    write_new(output / "plan.json", {"mode": "judge", "model": MODEL,
        "effort": "high", "source_ranked_sha256": sha256(ranked),
        "ranked_sha256": sha256(output / "ranked.json"), "requests": requests,
        "standard_price_per_million_usd": {k: str(v) for k, v in PRICE_PER_MILLION.items()},
        "pricing_date": "2026-10-11", "pricing_source": "https://developers.openai.com/api/docs/pricing",
        "max_attempts": 2, "max_output_tokens": 4096, "budget_usd": "25"})
    print(json.dumps({"prepared": len(requests), "mode": "judge"}), flush=True)


def run(output: Path, budget_root: Path) -> None:
    plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
    if plan["model"] != MODEL or plan["effort"] != "high":
        raise ValueError("QA model changed")
    if not output.resolve().is_relative_to(budget_root.resolve()):
        raise ValueError("QA run outside metering root")
    attempts = list(budget_root.rglob("attempt-*.json"))
    spent = Decimal(0)
    for path in attempts:
        record = json.loads(path.read_text(encoding="utf-8"))
        if not record.get("response") or not record["response"].get("usage"):
            raise ValueError("unknown API charge: reconcile " + str(path))
        spent += cost(record["response"]["usage"])
    state = {"spent": spent, "reserved": Decimal(0)}
    lock, stop = threading.Lock(), threading.Event()
    client = client_for_api()

    def dispatch(item: dict) -> None:
        request_path = output / "requests" / (item["id"] + ".json")
        if sha256(request_path) != item["sha256"]:
            raise ValueError("frozen QA request changed")
        payload = json.loads(request_path.read_text(encoding="utf-8"))
        if (payload["model"] != MODEL or payload["reasoning"] != {"effort": "high"}
                or payload["max_output_tokens"] != 4096 or payload["store"] is not False
                or payload["service_tier"] != "default"):
            raise ValueError("QA dispatch settings changed")
        target = output / "responses" / item["id"]
        target.mkdir(parents=True, exist_ok=True)
        for attempt in (1, 2):
            record_path = target / f"attempt-{attempt}.json"
            if record_path.exists():
                response = json.loads(record_path.read_text(encoding="utf-8"))["response"]
            else:
                if (target / f"started-{attempt}.json").exists():
                    raise ValueError("uncertain request outcome; do not resend")
                with lock:
                    # ponytail: conservative $0.15 reservation covers these small preview requests;
                    # use provider token counting before allowing larger images/contexts.
                    if stop.is_set():
                        return
                    if state["spent"] + state["reserved"] + Decimal(".15") > Decimal("25"):
                        stop.set()
                        raise ValueError("evaluation spend ceiling reached")
                    state["reserved"] += Decimal(".15")
                write_new(target / f"started-{attempt}.json", {"request_sha256": item["sha256"]})
                try:
                    response = client.responses.create(**payload).model_dump(mode="json")
                    write_new(record_path, {"request_sha256": item["sha256"], "response": response})
                    if not response.get("usage") or response.get("model") != MODEL:
                        raise ValueError("missing usage or unexpected response model")
                    charge = cost(response["usage"])
                    with lock:
                        state["spent"] += charge
                        state["reserved"] -= Decimal(".15")
                    print(json.dumps({"request": item["id"], "attempt": attempt,
                                      "status": response.get("status"), "usd": str(charge)}), flush=True)
                except Exception:
                    stop.set()
                    raise
            if response.get("status") == "completed":
                annotation_from(response, payload["text"]["format"]["schema"])
                return
            if response.get("status") != "incomplete":
                stop.set()
                raise ValueError("systemic QA response failure")
        stop.set()
        raise ValueError("QA request exhausted its two attempts")

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(dispatch, item) for item in plan["requests"]]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception:
                stop.set()
                for pending in futures:
                    pending.cancel()
                raise
    print(json.dumps({"evaluation_total_usd": str(state["spent"])}), flush=True)


def result_for(output: Path, item: dict) -> dict:
    request_path = output / "requests" / (item["id"] + ".json")
    if sha256(request_path) != item["sha256"]:
        raise ValueError("frozen request changed")
    schema = json.loads(request_path.read_text(encoding="utf-8"))["text"]["format"]["schema"]
    for attempt in (1, 2):
        path = output / "responses" / item["id"] / f"attempt-{attempt}.json"
        if path.exists():
            record = json.loads(path.read_text(encoding="utf-8"))
            response = record["response"]
            if response.get("status") == "completed":
                if record.get("request_sha256") != item["sha256"] or response.get("model") != MODEL:
                    raise ValueError("response does not match frozen request/model")
                return annotation_from(response, schema)
    raise ValueError("missing completed QA response: " + item["id"])


def finish_judge(output: Path) -> None:
    plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
    if sha256(output / "ranked.json") != plan["ranked_sha256"]:
        raise ValueError("frozen ranked results changed")
    data = json.loads((output / "ranked.json").read_text(encoding="utf-8"))
    items = {item["id"]: item for item in plan["requests"]}
    cases = []
    for case in data["cases"]:
        candidates = []
        if case["results"]:
            item = items[case["case_id"]]
            labels = result_for(output, item)["candidates"]
            if (len(labels) != len(item["mapping"]) or
                    sorted(x["number"] for x in labels) != list(range(1, len(labels) + 1))):
                raise ValueError("judge did not cover each anonymous image exactly once")
            mapped = {item["mapping"][x["number"] - 1]: x for x in labels}
            candidates = [{"icon_id": x["icon_id"], "label": mapped[x["icon_id"]]["label"],
                           "reason": mapped[x["icon_id"]]["reason"]} for x in case["results"][:5]]
        outcome = ("contract_failure" if case["contract_violations"] else
                   "useful_hit" if any(x["label"] == "useful" for x in candidates) else
                   "expected_empty" if not candidates else "no_useful_hit")
        cases.append({"case_id": case["case_id"], "outcome": outcome, "candidates": candidates})
    write_new(output / "judgments.json", {"judgment_schema_version": 2,
        "benchmark_sha256": data["benchmark_sha256"],
        "ranked_results_sha256": sha256(output / "ranked.json"),
        "reviewer": "gpt-6-sol high; stateless blinded image-only API judging",
        "independent_review": False, "cases": cases})
    result = score(output / "ranked.json", output / "judgments.json")
    write_new(output / "score.json", result)
    print(json.dumps(result), flush=True)


def batch_submit(output: Path) -> None:
    plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
    if (output / "batch-state.json").exists():
        raise ValueError("batch submission already attempted; resume with batch-collect")
    rows = []
    for item in plan["requests"]:
        try:
            result_for(output, item)
            continue
        except ValueError:
            pass
        folder = output / "responses" / item["id"]
        for started in folder.glob("started-*.json"):
            if not (folder / started.name.replace("started-", "attempt-")).exists():
                raise ValueError("unreconciled prior request outcome")
        path = output / "requests" / (item["id"] + ".json")
        if sha256(path) != item["sha256"]:
            raise ValueError("QA request changed")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["model"] != MODEL or payload["reasoning"] != {"effort": "high"}:
            raise ValueError("QA model changed")
        rows.append({"custom_id": item["id"], "method": "POST", "url": "/v1/responses", "body": payload})
    if not rows or len(rows) > 100:
        raise ValueError("QA batch must contain 1-100 requests")
    budget_root = output.parent
    budget_runs = [path.parent for path in budget_root.glob("*/plan.json")
                   if json.loads(path.read_text(encoding="utf-8")).get("mode") != "full-alternatives"]
    spent = Decimal(0)
    for prior in (path for run_root in budget_runs for path in run_root.rglob("attempt-*.json")):
        record = json.loads(prior.read_text(encoding="utf-8"))
        response = record.get("response") or {}
        if response.get("usage"):
            spent += cost(response["usage"]) * (Decimal(".5") if record.get("processing_tier") == "batch" else 1)
        elif response.get("status") != "rejected":
            raise ValueError("unknown API charge; reconcile before dispatch")
    reserved = sum((Decimal(".075") * json.loads(path.read_text(encoding="utf-8"))["count"]
                    for run_root in budget_runs for path in run_root.glob("batch-state.json")
                    if not path.with_name("batch-metering.json").exists()), Decimal(0))
    if spent + reserved + Decimal(".075") * len(rows) > Decimal("25"):
        raise ValueError("batch reservation would exceed the $25 evaluation/trial ceiling")
    path = output / "batch-input.jsonl"
    with path.open("xb") as stream:
        for row in rows:
            stream.write(canonical(row) + b"\n")
    client = client_for_api()
    with path.open("rb") as stream:
        uploaded = client.files.create(file=stream, purpose="batch")
    state = {"input_file_id": uploaded.id, "input_sha256": sha256(path),
             "plan_sha256": sha256(output / "plan.json"), "count": len(rows),
             "processing_tier": "batch", "discount": "0.5",
             "estimated_worst_case_reservation_usd": str(Decimal(".075") * len(rows)),
             "metered_prior_usd": str(spent)}
    write_new(output / "batch-state.json", state)
    batch = client.batches.create(input_file_id=uploaded.id, endpoint="/v1/responses",
                                  completion_window="24h", metadata={"run": output.name})
    write_new(output / "batch-created.json", {"batch_id": batch.id, "status": batch.status})
    print(json.dumps({"batch_id": batch.id, "status": batch.status, "count": len(rows)}), flush=True)


def batch_collect(output: Path) -> None:
    state = json.loads((output / "batch-state.json").read_text(encoding="utf-8"))
    if (state["plan_sha256"] != sha256(output / "plan.json") or
            state["input_sha256"] != sha256(output / "batch-input.jsonl")):
        raise ValueError("frozen batch inputs changed")
    created = json.loads((output / "batch-created.json").read_text(encoding="utf-8"))
    client = client_for_api()
    batch = client.batches.retrieve(created["batch_id"])
    print(json.dumps({"status": batch.status, "counts": batch.request_counts.model_dump()}), flush=True)
    if batch.status not in {"completed", "failed", "expired", "cancelled"}:
        return
    for kind in ("output", "error"):
        file_id = getattr(batch, kind + "_file_id")
        path = output / ("batch-" + kind + ".jsonl")
        if file_id and not path.exists():
            with path.open("xb") as stream:
                stream.write(client.files.content(file_id).read())
    plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
    items = {x["id"]: x for x in plan["requests"]}
    total, completed, seen = Decimal(0), 0, set()
    for kind in ("output", "error"):
        path = output / ("batch-" + kind + ".jsonl")
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            key = row["custom_id"]
            if key not in items or key in seen:
                raise ValueError("duplicate or unknown batch request ID")
            seen.add(key)
            response = (row.get("response") or {}).get("body") or {}
            if response.get("usage"):
                total += cost(response["usage"]) * Decimal(".5")
            folder = output / "responses" / key
            first = folder / "attempt-1.json"
            previous = json.loads(first.read_text(encoding="utf-8")) if first.exists() else {}
            attempt = 2 if previous and previous.get("batch_id") != batch.id else 1
            target = folder / f"attempt-{attempt}.json"
            record = {"response": response, "request_sha256": items[key]["sha256"],
                      "processing_tier": "batch", "batch_id": batch.id, "error": row.get("error")}
            if not target.exists():
                write_new(target, record)
            if response.get("model") == MODEL and response.get("status") == "completed":
                completed += 1
    summary = {"completed": completed, "expected": state["count"], "responses": len(seen),
               "estimated_batch_usd": str(total), "batch_status": batch.status}
    if not (output / "batch-metering.json").exists():
        write_new(output / "batch-metering.json", summary)
    print(json.dumps(summary), flush=True)
    if completed != state["count"]:
        raise ValueError("batch incomplete; preserve evidence and reconcile before retry")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare-judge", "run", "finish-judge", "batch-submit", "batch-collect"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--ranked", type=Path)
    parser.add_argument("--budget-root", type=Path)
    args = parser.parse_args()
    if args.command == "prepare-judge":
        if not args.package or not args.ranked:
            parser.error("prepare-judge requires --package and --ranked")
        prepare_judge(args.package, args.ranked, args.output)
    elif args.command == "run":
        if not args.budget_root:
            parser.error("run requires --budget-root")
        run(args.output, args.budget_root)
    elif args.command == "batch-submit":
        batch_submit(args.output)
    elif args.command == "batch-collect":
        batch_collect(args.output)
    else:
        finish_judge(args.output)


if __name__ == "__main__":
    main()
