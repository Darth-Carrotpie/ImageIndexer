"""One bounded additive corpus pass, reusing the frozen 100-icon Sol High trial."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import shutil
import time

from automated_search_qa import body, image_input, result_for, MODEL
from evaluate_search_v2 import canonical, sha256, write_new
from full_annotation_batch import client_for_api, save_json, MAX_CHUNK_BYTES, MAX_CHUNK_ICONS, retryable_queue_rejection
from metered_calibration import cost
from prepare_release_qa import ALTERNATIVE_PROMPT, ALTERNATIVE_SCHEMA, freeze, rows, read, finish_alternatives


def prepare(package: Path, trial: Path, output: Path) -> None:
    icons = rows(package)
    prior = read(trial / "plan.json")
    if len(icons) != 6250 or len(prior["requests"]) != 100:
        raise ValueError("expected frozen 6250 corpus and complete 100-icon trial")
    trial_requests = {x["id"]: x for x in prior["requests"]}
    requests = []
    for key in sorted(icons):
        icon = icons[key]
        payload = body(ALTERNATIVE_PROMPT, [image_input(package / icon["path"], icon["sha256"])], ALTERNATIVE_SCHEMA)
        if key in trial_requests:
            old = read(trial / "requests" / (key + ".json"))
            if old != payload:
                raise ValueError("trial reuse requires identical image/prompt/schema/model configuration")
            result_for(trial, trial_requests[key])
        requests.append((key, payload, {"icon_id": key, "thumbnail_sha256": icon["sha256"],
                                       "stratum": "corpus", "reused": key in trial_requests}))
    metering = read(trial / "batch-metering.json")
    projected = Decimal(metering["estimated_batch_usd"]) * Decimal(6150) / 100
    freeze(output, "full-alternatives", requests, {"catalog_sqlite_sha256": sha256(package / "catalog.sqlite"),
        "identity_registry_sha256": sha256(package / "manifests/icon-identities.jsonl"),
        "reused_trial_plan_sha256": sha256(trial / "plan.json"), "new_requests": 6150,
        "reused_requests": 100, "projected_new_batch_usd": str(projected), "spend_ceiling_usd": "60",
        "selection": "All 6250 frozen IDs once; exact-input reuse of 100 trial responses",
        "authorization": "Owner 2026-10-11: GPT-6 Sol High API corpus run allowed without session-model swap"})
    for key in trial_requests:
        shutil.copytree(trial / "responses" / key, output / "responses" / key)
    chunks, chunk, size = [], [], 0
    def flush():
        nonlocal chunk, size
        if not chunk:
            return
        name = f"inputs/batch-{len(chunks)+1:04d}.jsonl"
        path = output / name
        path.parent.mkdir(exist_ok=True)
        with path.open("xb") as stream:
            for line in chunk:
                stream.write(line)
        chunks.append({"input_file": name, "sha256": sha256(path), "count": len(chunk)})
        chunk, size = [], 0
    for item in read(output / "plan.json")["requests"]:
        if item["reused"]:
            continue
        payload = read(output / "requests" / (item["id"] + ".json"))
        line = canonical({"custom_id": item["id"], "method": "POST", "url": "/v1/responses", "body": payload}) + b"\n"
        if len(line) > MAX_CHUNK_BYTES:
            raise ValueError("one request exceeds Batch byte limit")
        if len(chunk) == MAX_CHUNK_ICONS or size + len(line) > MAX_CHUNK_BYTES:
            flush()
        chunk.append(line)
        size += len(line)
    flush()
    write_new(output / "dispatch-plan.json", {"plan_sha256": sha256(output / "plan.json"), "chunks": chunks,
        "max_active_batches": 2, "max_attempts_per_icon": 2, "new_spend_ceiling_usd": "60",
        "reservation_per_request_usd": "0.03", "processing_tier": "batch"})
    print(json.dumps({"new": 6150, "reused": 100, "chunks": len(chunks), "estimated_new_usd": str(projected)}), flush=True)


def step(output: Path) -> None:
    dispatch = read(output / "dispatch-plan.json")
    if dispatch["plan_sha256"] != sha256(output / "plan.json"):
        raise ValueError("corpus plan changed")
    plan = read(output / "plan.json")
    if plan["model"] != MODEL or plan["effort"] != "high" or len(plan["requests"]) != 6250:
        raise ValueError("corpus/model mismatch")
    state_path = output / "state.json"
    state = read(state_path) if state_path.exists() else {"dispatch_plan_sha256": sha256(output / "dispatch-plan.json"), "batches": []}
    if state["dispatch_plan_sha256"] != sha256(output / "dispatch-plan.json"):
        raise ValueError("dispatch plan changed")
    client = client_for_api()
    items = {x["id"]: x for x in plan["requests"]}
    for record in state["batches"]:
        if record.get("collected"):
            continue
        if not record.get("batch_id"):
            raise ValueError("uncertain batch creation: reconcile before resubmission")
        batch = client.batches.retrieve(record["batch_id"])
        record["status"] = batch.status
        record["counts"] = batch.request_counts.model_dump()
        if batch.status not in {"completed", "failed", "expired", "cancelled"}:
            continue
        folder = output / "batch-results" / f"batch-{record['chunk']:04d}"
        folder.mkdir(parents=True, exist_ok=True)
        total, completed, seen, no_usage = Decimal(0), 0, set(), 0
        for kind in ("output", "error"):
            file_id = getattr(batch, kind + "_file_id")
            path = folder / (kind + ".jsonl")
            if file_id and not path.exists():
                with path.open("xb") as stream:
                    stream.write(client.files.content(file_id).read())
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                key = row["custom_id"]
                if key not in items or items[key]["reused"] or key in seen:
                    raise ValueError("duplicate/unknown/reused corpus response")
                seen.add(key)
                response = (row.get("response") or {}).get("body") or {}
                if response.get("usage"):
                    total += cost(response["usage"]) * Decimal(".5")
                else:
                    no_usage += 1
                target = output / "responses" / key / "attempt-1.json"
                value = {"response": response, "request_sha256": items[key]["sha256"],
                         "processing_tier": "batch", "batch_id": batch.id, "error": row.get("error")}
                if target.exists():
                    if read(target) != value:
                        raise ValueError("corpus response changed on recollection")
                else:
                    write_new(target, value)
                if response.get("status") == "completed" and response.get("model") == MODEL:
                    result_for(output, items[key])
                    completed += 1
        record.update({"collected": True, "estimated_batch_usd": str(total),
                       "completed": completed, "responses": len(seen), "without_usage": no_usage,
                       "errors": batch.errors.model_dump() if batch.errors else None})
    save_json(state_path, state)
    def queue_rejected(record):
        return retryable_queue_rejection({"status": record.get("status"),
            "batch_errors": record.get("errors"), "request_counts": record.get("counts")})
    if any(x.get("collected") and not queue_rejected(x) and (x["completed"] != dispatch["chunks"][x["chunk"]-1]["count"]
                                  or x["without_usage"]) for x in state["batches"]):
        raise ValueError("corpus batch incomplete; stop dispatch and reconcile, never rerun entire corpus")
    spent = sum((Decimal(x.get("estimated_batch_usd", "0")) for x in state["batches"]), Decimal(0))
    active = [x for x in state["batches"] if not x.get("collected")]
    reserved = sum((Decimal(".03") * dispatch["chunks"][x["chunk"]-1]["count"] for x in active), Decimal(0))
    # Observed account queue limit is 900k, below its public model-tier ceiling.
    while not active:
        rejected = next((x for x in state["batches"] if queue_rejected(x) and not x.get("rearmed")), None)
        submitted = {x["chunk"] for x in state["batches"]}
        remaining = sorted(set(range(1, len(dispatch["chunks"]) + 1)) - submitted)
        if rejected:
            number = rejected["chunk"]
            if sum(x["chunk"] == number for x in state["batches"]) >= 2:
                raise ValueError("bounded queue retry exhausted")
        elif remaining:
            number = remaining[0]
        else:
            break
        chunk = dispatch["chunks"][number-1]
        allowance = Decimal(".03") * chunk["count"]
        if spent + reserved + allowance > Decimal("60"):
            raise ValueError("corpus spend reservation ceiling reached")
        path = output / chunk["input_file"]
        if sha256(path) != chunk["sha256"]:
            raise ValueError("frozen corpus chunk changed")
        if rejected:
            file_id = rejected["input_file_id"]
            rejected["rearmed"] = True
        else:
            with path.open("rb") as stream:
                file_id = client.files.create(file=stream, purpose="batch").id
        record = {"chunk": number, "input_file_id": file_id, "create_attempted": True}
        if rejected:
            record["retry_of_admission_rejection"] = rejected["batch_id"]
        state["batches"].append(record)
        save_json(state_path, state)
        batch = client.batches.create(input_file_id=file_id, endpoint="/v1/responses", completion_window="24h",
                                      metadata={"run": "initial-release-alternatives-v1", "chunk": str(number)})
        record.update({"batch_id": batch.id, "status": batch.status})
        save_json(state_path, state)
        active.append(record)
        reserved += allowance
    completed = sum(x.get("completed", 0) for x in state["batches"])
    print(json.dumps({"completed_new": completed, "reused": 100, "active": len(active),
        "submitted_chunks": len({x["chunk"] for x in state["batches"]}), "total_chunks": len(dispatch["chunks"]),
        "estimated_new_usd": str(spent), "reserved_usd": str(reserved),
        "statuses": [{"chunk": x["chunk"], "status": x["status"], "counts": x.get("counts")} for x in active]}), flush=True)
    if completed == 6150 and not active and not (output / "metering.json").exists():
        write_new(output / "metering.json", {"new_completed": completed, "reused": 100,
            "estimated_new_batch_usd": str(spent), "failed": 0, "unknown_charges": 0,
            "model": MODEL, "reasoning_effort": "high"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "step", "run", "finish"))
    parser.add_argument("--package", type=Path)
    parser.add_argument("--trial", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.package, args.trial, args.output)
    elif args.command == "step":
        step(args.output)
    elif args.command == "run":
        while not (args.output / "metering.json").exists():
            step(args.output)
            if not (args.output / "metering.json").exists():
                time.sleep(30)
    else:
        if not (args.output / "metering.json").exists():
            raise ValueError("complete metering is required before applying corpus alternatives")
        finish_alternatives(args.output)
