"""Small offline invariant check for the bounded paid pilot."""

import json
import tempfile
import unittest
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from metered_calibration import cost, digest
from supplemental_pilot import ASTRA_PRICES, checked_plan, collect, freeze_astra


def make_pilot(root):
    root.mkdir()
    ids = [f"icon_{n:036d}" for n in range(100)]
    rows = [{"custom_id": icon_id, "method": "POST", "url": "/v1/responses",
             "body": {"model": "gpt-6-sol", "reasoning": {"effort": "high"}, "store": False,
                      "max_output_tokens": 1500, "input": [{"type": "input_image", "image_url": "data:test"}]}}
            for icon_id in ids]
    request = root / "input.jsonl"
    request.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    (root / "plan.json").write_text(json.dumps({"model": "gpt-6-sol", "reasoning_effort": "high",
                                               "count": 100, "selected_ids": ids,
                                               "max_output_tokens_per_request": 1500,
                                               "input_sha256": digest(request)}), encoding="utf-8")
    return rows


class SupplementalPilotTest(unittest.TestCase):
    def test_frozen_input_cannot_change_after_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "sol"
            make_pilot(root)
            request = root / "input.jsonl"
            self.assertEqual(checked_plan(root)["count"], 100)
            request.write_text(request.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "changed"):
                checked_plan(root)

    def test_astra_preserves_payload_and_meters_its_own_rates(self):
        with tempfile.TemporaryDirectory() as temp:
            baseline, output = Path(temp) / "sol", Path(temp) / "astra"
            original = make_pilot(baseline)
            before = digest(baseline / "input.jsonl")
            freeze_astra(baseline, output)
            self.assertEqual(before, digest(baseline / "input.jsonl"))
            updated = [json.loads(line) for line in (output / "input.jsonl").read_text().splitlines()]
            for old, new in zip(original, updated):
                self.assertEqual("gpt-6-astra", new["body"]["model"])
                self.assertEqual("max", new["body"]["reasoning"]["effort"])
                for field in ("model", "reasoning", "max_output_tokens"):
                    old["body"].pop(field)
                    new["body"].pop(field)
                self.assertEqual(old, new)
            usage = {"input_tokens": 100, "output_tokens": 50,
                     "input_tokens_details": {"cached_tokens": 20, "cache_write_tokens": 10}}
            self.assertEqual(cost(usage) * 5, cost(usage, ASTRA_PRICES))

    def test_incomplete_response_still_contributes_to_metering(self):
        with tempfile.TemporaryDirectory() as temp:
            baseline, output = Path(temp) / "sol", Path(temp) / "astra"
            original = make_pilot(baseline)
            freeze_astra(baseline, output)
            responses = []
            for n, row in enumerate(original):
                body = {"id": str(n), "model": "gpt-6-astra", "status": "completed" if n else "incomplete",
                        "usage": {"input_tokens": 100, "output_tokens": 50},
                        "output": [{"type": "message", "content": [{"type": "output_text",
                            "text": json.dumps({"terms": ["blue orb"], "uncertainties": []})}]}]}
                responses.append({"custom_id": row["custom_id"], "response": {"status_code": 200, "body": body}})
            (output / "output.jsonl").write_text("".join(json.dumps(row) + "\n" for row in responses), encoding="utf-8")
            with patch("supplemental_pilot.status", return_value={"status": "completed"}), patch("supplemental_pilot.client_for_api"):
                collect(output)
            summary = json.loads((output / "metering.json").read_text())
            self.assertEqual(99, summary["completed_icons"])
            self.assertEqual(1, summary["failed_icons"])
            self.assertEqual(100, summary["requests_with_usage"])
            self.assertEqual(Decimal("0.175"), Decimal(summary["estimated_batch_usd"]))
            self.assertIsNone(summary["projected_6250_batch_usd"])
