"""Meter a fixed 12-icon GPT-6 Sol High vision sample with the Responses API."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


MODEL = "gpt-6-sol"
PILOT_SHA256 = "0d36dfb469401961652f3cc5d98b34cbf9436a10a8a4addbcd7a8b59507d76eb"
SAMPLE = (1, 2, 3, 4, 5, 10, 15, 20, 25, 30, 35, 40)
GROUP_COUNTS = {"ambiguous": 4, "candidate": 3946, "single": 2300}
PRICE_PER_MILLION = {"input": Decimal("2"), "cached_input": Decimal("0.2"),
                     "cache_write": Decimal("2.5"), "output": Decimal("10")}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def plan(pilot: Path) -> tuple[list[dict], dict, Path, Path]:
    manifest_path = pilot / "pilot-manifest.json"
    if digest(manifest_path) != PILOT_SHA256:
        raise ValueError("pilot manifest changed since the approved run")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("model") != MODEL or manifest.get("reasoning_effort") != "high":
        raise ValueError("pilot model/effort mismatch")
    by_number = {item["number"]: item for item in manifest["sample"]}
    if len(by_number) != 100 or any(number not in by_number for number in SAMPLE):
        raise ValueError("pilot sample numbers are incomplete")
    selected = [by_number[number] for number in SAMPLE]
    counts = {group: sum(group in item["categories"] for item in selected) for group in GROUP_COUNTS}
    if counts != {"ambiguous": 4, "candidate": 4, "single": 4}:
        raise ValueError(f"calibration strata changed: {counts}")
    for item in selected:
        if len(item["renditions"]) != (2 if "ambiguous" in item["categories"] else 1):
            raise ValueError(f"unexpected rendition count: {item['number']}")
        for rendition in item["renditions"]:
            preview = pilot / rendition["preview"]
            if not preview.is_file() or not preview.resolve().is_relative_to(pilot.resolve()):
                raise ValueError(f"missing/escaping preview: {item['number']}")
            if digest(preview) != rendition["preview_sha256"]:
                raise ValueError(f"preview hash mismatch: {item['number']}")
    tools = Path(__file__).resolve().parent
    return selected, manifest, tools / "annotation_prompt_v1.txt", tools / "annotation_response_schema_v1.json"


def cost(usage: dict, prices: dict | None = None) -> Decimal:
    prices = PRICE_PER_MILLION if prices is None else prices
    input_tokens = usage["input_tokens"]
    output_tokens = usage["output_tokens"]
    details = usage.get("input_tokens_details") or {}
    cached = details.get("cached_tokens") or 0
    written = details.get("cache_write_tokens") or 0
    if any(type(value) is not int or value < 0 for value in (input_tokens, output_tokens, cached, written)):
        raise ValueError("invalid token usage")
    uncached = input_tokens - cached - written
    if uncached < 0:
        raise ValueError("input usage breakdown exceeds total")
    return (Decimal(uncached) * prices["input"]
            + Decimal(cached) * prices["cached_input"]
            + Decimal(written) * prices["cache_write"]
            + Decimal(output_tokens) * prices["output"]) / 1_000_000


def request_body(item: dict, pilot: Path, prompt: str, schema: dict) -> dict:
    images = []
    for index, rendition in enumerate(item["renditions"], 1):
        image = (pilot / rendition["preview"]).read_bytes()
        images.append({"type": "input_text", "text": f"Preview image {index} follows."})
        images.append({"type": "input_image", "image_url": "data:image/png;base64," +
                       base64.b64encode(image).decode("ascii"), "detail": "high"})
    return {"model": MODEL, "reasoning": {"effort": "high"}, "store": False,
            "max_output_tokens": 4096,
            "input": [{"role": "system", "content": prompt},
                      {"role": "user", "content": images}],
            "text": {"format": {"type": "json_schema", "name": "icon_annotation_v1",
                                "strict": True, "schema": schema}}}


def annotation_from(response: dict, schema: dict) -> dict:
    if response.get("status") != "completed":
        raise ValueError(f"model response incomplete: {response.get('status')}")
    text = [part["text"] for item in response.get("output", []) if item.get("type") == "message"
            for part in item.get("content", []) if part.get("type") == "output_text"]
    if len(text) != 1:
        raise ValueError("model response did not contain one JSON text result")
    annotation = json.loads(text[0])
    if not isinstance(annotation, dict) or set(annotation) != set(schema["required"]):
        raise ValueError("model annotation did not match required fields")
    return annotation


def summary(rows: list[dict], selected: list[dict]) -> dict:
    by_number = {item["number"]: item for item in selected}
    totals = {group: [] for group in GROUP_COUNTS}
    for row in rows:
        group = next(group for group in GROUP_COUNTS if group in by_number[row["number"]]["categories"])
        totals[group].append(Decimal(row["estimated_standard_usd"]))
    if any(len(values) != 4 for values in totals.values()):
        raise ValueError("calibration sample is incomplete")
    projection = sum((sum(values) / len(values)) * GROUP_COUNTS[group]
                     for group, values in totals.items())
    return {"requests": len(rows), "image_inputs": sum(len(item["renditions"]) for item in selected),
            "measured_input_tokens": sum(row["usage"]["input_tokens"] for row in rows),
            "measured_output_tokens": sum(row["usage"]["output_tokens"] for row in rows),
            "sample_estimated_standard_usd": str(sum(Decimal(row["estimated_standard_usd"]) for row in rows)),
            "projected_6250_standard_usd": str(projection.quantize(Decimal("0.01"))),
            "note": "Stratum-weighted projection from four requests per group; not an invoice or confidence interval."}


def run(pilot: Path, output: Path, execute: bool) -> None:
    selected, manifest, prompt_path, schema_path = plan(pilot)
    prompt = prompt_path.read_text(encoding="utf-8")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    run_meta = {"model": MODEL, "reasoning_effort": "high", "image_detail": "high",
                "sample_numbers": list(SAMPLE), "group_counts": GROUP_COUNTS,
                "pilot_manifest_sha256": PILOT_SHA256, "prompt_sha256": digest(prompt_path),
                "schema_sha256": digest(schema_path), "calibration_script_sha256": digest(Path(__file__)),
                "max_output_tokens_per_request": 4096,
                "standard_price_per_million_usd": {name: str(rate) for name, rate in PRICE_PER_MILLION.items()},
                "pricing_checked_on": "2026-10-09",
                "pricing_source": "https://developers.openai.com/api/docs/models/gpt-6-sol"}
    if not execute:
        print(json.dumps({"ready": True, "requests": len(selected),
                          "image_inputs": sum(len(item["renditions"]) for item in selected),
                          "sample_numbers": list(SAMPLE), "model": MODEL, "reasoning_effort": "high",
                          "api_key_available": bool(os.environ.get("OPENAI_API_KEY"))}, sort_keys=True))
        return
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY is unavailable; no metered request was sent")
    if output.exists():
        existing_meta = json.loads((output / "run.json").read_text(encoding="utf-8"))
        if existing_meta != run_meta:
            raise ValueError("existing calibration has different inputs")
    else:
        output.mkdir(parents=True)
        (output / "run.json").write_text(json.dumps(run_meta, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    rows_path = output / "results.jsonl"
    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines()] if rows_path.exists() else []
    done = {row["number"] for row in rows}
    if len(done) != len(rows) or not done.issubset(SAMPLE):
        raise ValueError("calibration results contain duplicates or unknown items")
    if any(row.get("validation_error") for row in rows):
        raise ValueError("a metered response was invalid; review its recorded usage before retrying")
    for item in selected:
        if item["number"] in done:
            continue
        body = json.dumps(request_body(item, pilot, prompt, schema)).encode("utf-8")
        request = Request("https://api.openai.com/v1/responses", data=body,
                          headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                          method="POST")
        try:
            with urlopen(request, timeout=180) as stream:
                response = json.load(stream)
        except HTTPError as exc:
            raise RuntimeError(f"OpenAI API HTTP {exc.code}; stopped before the next request") from exc
        except URLError as exc:
            raise RuntimeError(f"OpenAI API connection failed: {exc.reason}") from exc
        usage = response.get("usage")
        if not isinstance(usage, dict):
            raise ValueError("completed response has no metered usage")
        validation_error = None
        try:
            annotation = annotation_from(response, schema)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            annotation = None
            validation_error = str(exc)
        row = {"number": item["number"], "icon_id": item["icon_id"],
               "response_id": response.get("id"), "response_model": response.get("model"),
               "service_tier": response.get("service_tier"), "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
               "usage": usage, "estimated_standard_usd": str(cost(usage)),
               "annotation": annotation, "validation_error": validation_error}
        with rows_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        rows.append(row)
        print(json.dumps({"number": item["number"], "input_tokens": usage["input_tokens"],
                          "output_tokens": usage["output_tokens"],
                          "estimated_standard_usd": row["estimated_standard_usd"]}), flush=True)
        if validation_error:
            raise ValueError(f"metered response {item['number']} was invalid: {validation_error}")
    result = summary(rows, selected)
    (output / "summary.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="Send the 12 billable API requests")
    args = parser.parse_args()
    try:
        run(args.pilot, args.output, args.execute)
    except (ValueError, OSError, HTTPError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
