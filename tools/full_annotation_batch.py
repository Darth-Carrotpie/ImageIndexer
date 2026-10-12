"""Prepare, submit, and meter the frozen 6,250-icon annotation through Batch API."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import time
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from PIL import Image

from metered_calibration import MODEL, annotation_from, cost, digest, request_body
from prepare_annotation_pilot import visible_preview
from validate_catalog import validate


MAX_CHUNK_BYTES = 150_000_000  # Batch input limit is 200 MB; leave room for format overhead.
MAX_CHUNK_ICONS = 500
CANARY_ICONS = 20
EXPECTED_ICONS = 6250
BATCH_RATE = Decimal("0.5")


def save_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def load_plan(root: Path) -> dict:
    plan = json.loads((root / "plan.json").read_text(encoding="utf-8"))
    if plan.get("model") != MODEL or plan.get("reasoning_effort") != "high":
        raise ValueError("full-run plan has an unexpected model/effort")
    for chunk in plan["chunks"]:
        path = root / chunk["input_file"]
        if not path.is_file() or digest(path) != chunk["sha256"] or path.stat().st_size > MAX_CHUNK_BYTES:
            raise ValueError(f"missing/changed/oversize Batch input: {chunk['number']}")
    return plan


def check(root: Path) -> dict:
    plan = load_plan(root)
    manifest = root / "icons.jsonl"
    if digest(manifest) != plan["icons_manifest_sha256"]:
        raise ValueError("icon manifest hash mismatch")
    icons = {}
    for line in manifest.open(encoding="utf-8"):
        row = json.loads(line)
        icon_id = row["icon_id"]
        if icon_id in icons:
            raise ValueError(f"duplicate icon ID: {icon_id}")
        icons[icon_id] = row
    if len(icons) != EXPECTED_ICONS or plan["request_count"] != EXPECTED_ICONS:
        raise ValueError("icon coverage mismatch")
    if sum(bool(row["pairing_correction"]) for row in icons.values()) != 4:
        raise ValueError("reviewed correction count mismatch")
    seen = set()
    for chunk in plan["chunks"]:
        count = 0
        with (root / chunk["input_file"]).open(encoding="utf-8") as stream:
            for line in stream:
                item = json.loads(line)
                icon_id = item["custom_id"]
                if (icon_id in seen or icon_id not in icons or icons[icon_id]["chunk"] != chunk["number"]
                        or item["method"] != "POST" or item["url"] != "/v1/responses"):
                    raise ValueError(f"duplicate/unknown/misrouted request: {icon_id}")
                body = item["body"]
                if body["model"] != MODEL or body["reasoning"]["effort"] != "high":
                    raise ValueError(f"model/effort mismatch: {icon_id}")
                images = [part for entry in body["input"] if isinstance(entry["content"], list)
                          for part in entry["content"] if part.get("type") == "input_image"]
                if len(images) != 1 or images[0]["detail"] != "high":
                    raise ValueError(f"image count/detail mismatch: {icon_id}")
                seen.add(icon_id)
                count += 1
        if count != chunk["requests"]:
            raise ValueError(f"request count mismatch in chunk {chunk['number']}")
    if seen != icons.keys():
        raise ValueError("not every icon has one request")
    result = {"validated_icons": len(seen), "chunks": len(plan["chunks"]),
              "input_bytes": sum(row["bytes"] for row in plan["chunks"])}
    print(json.dumps(result, sort_keys=True))
    return result


def prepare(candidate: Path, freeze_path: Path, output: Path) -> None:
    candidate = candidate.resolve(strict=True)
    freeze_path = freeze_path.resolve(strict=True)
    output = output.resolve()
    if output.exists() or output.is_symlink():
        raise ValueError("full-run output must be a new directory")
    problems = validate(candidate, fast=True, freeze=freeze_path)
    if problems:
        raise ValueError(f"candidate/freeze validation failed: {problems[:3]}")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    corrections = {row["icon_id"]: row for row in freeze["corrections"]}
    tools = Path(__file__).resolve().parent
    prompt_path = tools / "annotation_prompt_v1.txt"
    schema_path = tools / "annotation_response_schema_v1.json"
    prompt = prompt_path.read_text(encoding="utf-8")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    db = sqlite3.connect(f"file:{(candidate / 'catalog.sqlite').as_posix()}?mode=ro", uri=True)
    try:
        rows = db.execute(
            "SELECT i.icon_id,i.source_key,i.grouping_status,i.preferred_role,"
            "r.stable_role,b.sha256,b.relative_path,b.width,b.height "
            "FROM icon i JOIN rendition r USING(icon_id) JOIN blob b ON b.sha256=r.blob_sha256 "
            "ORDER BY i.source_key,r.stable_role").fetchall()
    finally:
        db.close()
    grouped: dict[str, list[tuple]] = defaultdict(list)
    for row in rows:
        grouped[row[0]].append(row)
    if len(grouped) != EXPECTED_ICONS:
        raise ValueError(f"expected {EXPECTED_ICONS} frozen icons, got {len(grouped)}")
    if len(corrections) != 4:
        raise ValueError("expected four reviewed pairing corrections")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.preparing-", dir=output.parent))
    (stage / "previews").mkdir()
    (stage / "inputs").mkdir()
    chunk_number = 0
    chunk_count = 0
    chunk_bytes = 0
    chunk_stream = None
    chunk_path = None
    chunks: list[dict] = []
    corrected = 0

    def finish_chunk() -> None:
        nonlocal chunk_count, chunk_bytes, chunk_stream, chunk_path
        if chunk_stream is not None:
            chunk_stream.close()
            assert chunk_path is not None
            chunks.append({"number": chunk_number, "input_file": chunk_path.relative_to(stage).as_posix(),
                           "requests": chunk_count, "bytes": chunk_bytes, "sha256": digest(chunk_path)})
            chunk_stream = None

    with (stage / "icons.jsonl").open("w", encoding="utf-8", newline="\n") as manifest_stream:
        for index, (icon_id, entries) in enumerate(grouped.items(), 1):
            first = entries[0]
            source_key, grouping, preferred_role = first[1:4]
            if icon_id in corrections:
                chosen = next((row for row in entries if row[4] == "background"), None)
                if chosen is None or source_key != corrections[icon_id]["source_key"]:
                    raise ValueError(f"approved correction is not available: {icon_id}")
                corrected += 1
            else:
                chosen = next((row for row in entries if row[4] == preferred_role), None)
                if chosen is None:
                    raise ValueError(f"preferred rendition missing: {icon_id}")
            role, blob_hash, relative, width, height = chosen[4:9]
            source = candidate / relative
            if not source.is_file() or source.is_symlink() or not source.resolve().is_relative_to(candidate):
                raise ValueError(f"source blob missing/escaping: {icon_id}")
            if digest(source) != blob_hash:
                raise ValueError(f"source blob hash mismatch: {icon_id}")
            preview = stage / "previews" / f"{icon_id}.png"
            with Image.open(source) as image:
                image.load()
                image.thumbnail((512, 512), Image.Resampling.LANCZOS)
                visible_preview(image).save(preview, format="PNG")
                preview_size = [image.width, image.height]
            item = {"renditions": [{"preview": preview.relative_to(stage).as_posix()}]}
            line = (json.dumps({"custom_id": icon_id, "method": "POST", "url": "/v1/responses",
                               "body": request_body(item, stage, prompt, schema)},
                              ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            limit = CANARY_ICONS if chunk_number == 1 else MAX_CHUNK_ICONS
            if chunk_stream is not None and (chunk_count >= limit or chunk_bytes + len(line) > MAX_CHUNK_BYTES):
                finish_chunk()
            if chunk_stream is None:
                chunk_number += 1
                chunk_path = stage / "inputs" / f"batch-{chunk_number:04d}.jsonl"
                chunk_stream = chunk_path.open("wb")
                chunk_count = 0
                chunk_bytes = 0
            if len(line) > MAX_CHUNK_BYTES:
                raise ValueError(f"one icon exceeds Batch file limit: {icon_id}")
            chunk_stream.write(line)
            chunk_count += 1
            chunk_bytes += len(line)
            manifest_stream.write(json.dumps({"icon_id": icon_id, "source_key": source_key,
                                              "grouping_status": grouping, "selected_role": role,
                                              "source_blob_sha256": blob_hash,
                                              "preview_sha256": digest(preview),
                                              "preview_size": preview_size,
                                              "chunk": chunk_number,
                                              "pairing_correction": icon_id in corrections},
                                             ensure_ascii=False, sort_keys=True) + "\n")
            if index % 500 == 0:
                print(f"prepared {index}/{EXPECTED_ICONS} icons", flush=True)
    finish_chunk()
    if corrected != 4 or sum(chunk["requests"] for chunk in chunks) != EXPECTED_ICONS:
        raise ValueError("full-run coverage/correction count mismatch")
    plan = {"schema_version": 1, "catalog_id": freeze["catalog_id"], "pack_id": freeze["pack_id"],
            "model": MODEL, "reasoning_effort": "high", "image_detail": "high",
            "request_count": EXPECTED_ICONS, "image_count": EXPECTED_ICONS,
            "identity_registry_sha256": freeze["identity_registry_sha256"],
            "identity_freeze_sha256": digest(freeze_path),
            "candidate_catalog_manifest_sha256": digest(candidate / "manifests/catalog.jsonl"),
            "prompt_sha256": digest(prompt_path), "schema_sha256": digest(schema_path),
            "icons_manifest_sha256": digest(stage / "icons.jsonl"),
            "preview_policy": "max 512px, 32px gray checkerboard, one verified motif per icon",
            "pairing_corrections_applied_for_annotation": corrected,
            "max_output_tokens_per_request": 4096,
            "processing_tier": "batch", "chunks": chunks}
    save_json(stage / "plan.json", plan)
    if output.exists():
        raise ValueError("full-run output appeared during preparation")
    os.replace(stage, output)
    print(json.dumps({"prepared_icons": EXPECTED_ICONS, "chunks": len(chunks),
                      "input_bytes": sum(chunk["bytes"] for chunk in chunks),
                      "output": output.as_posix()}, sort_keys=True))


def state_for(root: Path, plan: dict) -> dict:
    path = root / "state.json"
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "schema_version": 1, "plan_sha256": digest(root / "plan.json"), "chunks": {}}
    if state.get("plan_sha256") != digest(root / "plan.json"):
        raise ValueError("Batch state belongs to a different plan")
    return state


def client_for_api():
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is unavailable; no API call was made")
    from openai import OpenAI
    return OpenAI(max_retries=0, timeout=300)


def submit(root: Path, maximum: int) -> dict:
    plan = load_plan(root)
    state = state_for(root, plan)
    client = client_for_api()
    submitted = 0
    for chunk in plan["chunks"]:
        key = str(chunk["number"])
        record = state["chunks"].setdefault(key, {})
        if record.get("batch_id"):
            continue
        if record.get("create_attempted"):
            raise ValueError(f"batch creation outcome for chunk {key} is uncertain; reconcile before retry")
        if submitted >= maximum:
            break
        if not record.get("file_id"):
            with (root / chunk["input_file"]).open("rb") as stream:
                uploaded = client.files.create(file=stream, purpose="batch")
            record["file_id"] = uploaded.id
            save_json(root / "state.json", state)
        record["create_attempted"] = True
        save_json(root / "state.json", state)
        batch = client.batches.create(input_file_id=record["file_id"], endpoint="/v1/responses",
                                      completion_window="24h",
                                      metadata={"catalog": "indexed-icon-pack", "run": "full-annotation-v1",
                                                "chunk": key, "input_sha256": chunk["sha256"]})
        record.update({"batch_id": batch.id, "status": batch.status,
                       "output_file_id": batch.output_file_id, "error_file_id": batch.error_file_id})
        save_json(root / "state.json", state)
        submitted += 1
        print(json.dumps({"chunk": chunk["number"], "requests": chunk["requests"],
                          "batch_id": batch.id, "status": batch.status}), flush=True)
    return {"new_batches": submitted, "submitted_batches": sum(bool(x.get("batch_id"))
                                                                    for x in state["chunks"].values())}


def status(root: Path) -> dict:
    plan = load_plan(root)
    state = state_for(root, plan)
    client = client_for_api()
    counts: dict[str, int] = defaultdict(int)
    for record in state["chunks"].values():
        if not record.get("batch_id"):
            continue
        batch = client.batches.retrieve(record["batch_id"])
        record.update({"status": batch.status, "output_file_id": batch.output_file_id,
                       "error_file_id": batch.error_file_id,
                       "batch_errors": batch.errors.model_dump() if batch.errors else None,
                       "request_counts": batch.request_counts.model_dump() if batch.request_counts else None})
        counts[batch.status] += 1
        save_json(root / "state.json", state)
    result = {"batch_status_counts": dict(sorted(counts.items())),
              "submitted_batches": sum(bool(x.get("batch_id")) for x in state["chunks"].values()),
              "total_batches": len(plan["chunks"])}
    print(json.dumps(result, sort_keys=True))
    return result


def collect(root: Path) -> dict:
    plan = load_plan(root)
    state = state_for(root, plan)
    expected = {row["icon_id"]: row for row in map(json.loads, (root / "icons.jsonl").read_text(
        encoding="utf-8").splitlines())}
    if len(expected) != EXPECTED_ICONS or digest(root / "icons.jsonl") != plan["icons_manifest_sha256"]:
        raise ValueError("full-run icon manifest changed")
    schema = json.loads((Path(__file__).with_name("annotation_response_schema_v1.json")).read_text(encoding="utf-8"))
    client = None
    results: dict[str, dict] = {}
    failures: list[dict] = []
    (root / "outputs").mkdir(exist_ok=True)
    for chunk in plan["chunks"]:
        record = state["chunks"].get(str(chunk["number"]), {})
        for kind in ("output", "error"):
            file_id = record.get(f"{kind}_file_id")
            local = root / "outputs" / f"batch-{chunk['number']:04d}.{kind}.jsonl"
            if file_id and not local.exists():
                client = client or client_for_api()
                content = client.files.content(file_id).read()
                temporary = local.with_name(local.name + ".tmp")
                temporary.write_bytes(content)
                os.replace(temporary, local)
            if not local.exists():
                continue
            for line in local.read_text(encoding="utf-8").splitlines():
                item = json.loads(line)
                icon_id = item.get("custom_id")
                if icon_id not in expected or expected[icon_id]["chunk"] != chunk["number"]:
                    raise ValueError(f"unknown/cross-chunk result: {icon_id}")
                response = item.get("response") or {}
                if kind == "error" or response.get("status_code") != 200:
                    failures.append({"icon_id": icon_id, "batch_id": record.get("batch_id"),
                                     "error": item.get("error") or response.get("status_code")})
                    continue
                if icon_id in results:
                    raise ValueError(f"duplicate successful result: {icon_id}")
                body = item["response"]["body"]
                if body.get("model") != MODEL or not isinstance(body.get("usage"), dict):
                    raise ValueError(f"model/usage mismatch: {icon_id}")
                annotation = annotation_from(body, schema)
                if annotation["same_motif_across_renditions"] != "not_applicable":
                    raise ValueError(f"one-image motif comparison invalid: {icon_id}")
                usage = body["usage"]
                results[icon_id] = {"icon_id": icon_id, "source_key": expected[icon_id]["source_key"],
                                    "source_blob_sha256": expected[icon_id]["source_blob_sha256"],
                                    "preview_sha256": expected[icon_id]["preview_sha256"],
                                    "batch_id": record["batch_id"], "response_id": body.get("id"),
                                    "usage": usage, "standard_equivalent_usd": str(cost(usage)),
                                    "estimated_batch_usd": str(cost(usage) * BATCH_RATE),
                                    "annotation": annotation}
    if set(results) & {row["icon_id"] for row in failures}:
        raise ValueError("same icon appears as both success and failure")
    result_path = root / "annotations.jsonl"
    temporary = result_path.with_name(result_path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for icon_id in sorted(results):
            stream.write(json.dumps(results[icon_id], ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(temporary, result_path)
    done = len(results)
    summary = {"expected_icons": EXPECTED_ICONS, "completed_icons": done,
               "failed_icons": len(failures), "remaining_icons": EXPECTED_ICONS - done - len(failures),
               "input_tokens": sum(row["usage"]["input_tokens"] for row in results.values()),
               "output_tokens": sum(row["usage"]["output_tokens"] for row in results.values()),
               "standard_equivalent_usd": str(sum(Decimal(row["standard_equivalent_usd"])
                                                  for row in results.values())),
               "estimated_batch_usd": str(sum(Decimal(row["estimated_batch_usd"])
                                              for row in results.values())),
               "annotation_sha256": digest(result_path)}
    save_json(root / "metering.json", summary)
    save_json(root / "failures.json", {"failures": failures})
    print(json.dumps(summary, sort_keys=True))
    return summary


def retryable_queue_rejection(record: dict) -> bool:
    errors = (record.get("batch_errors") or {}).get("data") or []
    counts = record.get("request_counts") or {}
    return (record.get("status") == "failed" and bool(errors)
            and all(error.get("code") == "token_limit_exceeded" for error in errors)
            and counts.get("completed", 0) == 0 and counts.get("failed", 0) == 0)


def rearm_queue_rejections(root: Path, state: dict) -> None:
    changed = False
    for key, record in state["chunks"].items():
        if not retryable_queue_rejection(record):
            continue
        attempts = record.setdefault("attempts", [])
        if len(attempts) >= 3:
            raise ValueError(f"Batch chunk {key} reached three queue-limit retries")
        attempts.append({"batch_id": record["batch_id"], "status": record["status"],
                         "batch_errors": record["batch_errors"]})
        for field in ("batch_id", "create_attempted", "status", "batch_errors",
                      "output_file_id", "error_file_id", "request_counts"):
            record.pop(field, None)
        changed = True
    if changed:
        save_json(root / "state.json", state)


def run(root: Path, poll_seconds: int) -> None:
    plan = check(root)
    if plan["chunks"] < 1:
        raise ValueError("no Batch inputs to run")
    while True:
        status(root)
        state = state_for(root, load_plan(root))
        chunks = state["chunks"]
        for key, record in chunks.items():
            if record.get("status") in {"failed", "expired", "cancelled"} and not retryable_queue_rejection(record):
                raise ValueError(f"Batch chunk {key} ended as {record['status']}; inspect state before resuming")
        metering = collect(root)
        if metering["failed_icons"]:
            raise ValueError("Batch returned per-icon errors; inspect failures.json before resuming")
        canary = chunks.get("1", {})
        if canary.get("status") == "completed":
            if not (root / "outputs" / "batch-0001.output.jsonl").is_file():
                raise ValueError("completed canary has no output file")
            canary_count = json.loads((root / "plan.json").read_text(encoding="utf-8"))["chunks"][0]["requests"]
            with (root / "outputs" / "batch-0001.output.jsonl").open(encoding="utf-8") as stream:
                if sum(1 for _ in stream) != canary_count:
                    raise ValueError("canary result count mismatch")
            active = sum(record.get("status") not in {"completed", "failed", "expired", "cancelled"}
                         for record in chunks.values() if record.get("batch_id"))
            if active == 0:
                rearm_queue_rejections(root, state)
                submit(root, 1)
        if metering["completed_icons"] == EXPECTED_ICONS:
            print(json.dumps({"full_annotation_complete": True, "metering": metering}, sort_keys=True))
            return
        time.sleep(poll_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--candidate", type=Path, required=True)
    prep.add_argument("--freeze", type=Path, required=True)
    prep.add_argument("--output", type=Path, required=True)
    for command in ("check", "submit", "status", "collect", "run"):
        part = sub.add_parser(command)
        part.add_argument("--run", type=Path, required=True)
        if command == "submit":
            part.add_argument("--max-chunks", type=int, default=1)
        if command == "run":
            part.add_argument("--poll-seconds", type=int, default=120)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare(args.candidate, args.freeze, args.output)
        elif args.command == "check":
            check(args.run)
        elif args.command == "submit":
            if args.max_chunks < 1:
                raise ValueError("--max-chunks must be positive")
            print(json.dumps(submit(args.run, args.max_chunks), sort_keys=True))
        elif args.command == "status":
            status(args.run)
        elif args.command == "collect":
            collect(args.run)
        else:
            if args.poll_seconds < 30:
                raise ValueError("--poll-seconds must be at least 30")
            run(args.run, args.poll_seconds)
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
