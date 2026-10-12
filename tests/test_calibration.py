"""Offline checks for metered calibration arithmetic and stratification."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "tools/metered_calibration.py"
spec = importlib.util.spec_from_file_location("metered_calibration_under_test", SCRIPT)
calibration = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(calibration)
sys.dont_write_bytecode = True


class CalibrationTest(unittest.TestCase):
    def test_cost_accounts_for_cache_and_reasoning_output(self) -> None:
        usage = {"input_tokens": 100, "input_tokens_details": {"cached_tokens": 20,
                                                                  "cache_write_tokens": 10},
                 "output_tokens": 50, "output_tokens_details": {"reasoning_tokens": 30}}
        self.assertEqual(Decimal("0.000669"), calibration.cost(usage))
        usage["input_tokens_details"]["cached_tokens"] = 101
        with self.assertRaises(ValueError):
            calibration.cost(usage)

    def test_projection_weights_corpus_not_oversampled_ambiguities(self) -> None:
        groups = ["ambiguous"] * 4 + ["candidate"] * 4 + ["single"] * 4
        selected = [{"number": number, "categories": [group], "renditions": [{}]}
                    for number, group in enumerate(groups, 1)]
        prices = {"ambiguous": "0.01", "candidate": "0.02", "single": "0.03"}
        rows = [{"number": number, "estimated_standard_usd": prices[group],
                 "usage": {"input_tokens": 1, "output_tokens": 2}}
                for number, group in enumerate(groups, 1)]
        result = calibration.summary(rows, selected)
        self.assertEqual("147.96", result["projected_6250_standard_usd"])
        self.assertEqual(12, result["measured_input_tokens"])

    def test_missing_key_sends_nothing_and_creates_no_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt = root / "prompt.txt"
            schema = root / "schema.json"
            prompt.write_text("Describe the image.")
            schema.write_text(json.dumps({"required": []}))
            output = root / "run"
            with patch.object(calibration, "plan", return_value=([], {}, prompt, schema)):
                with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
                    with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY is unavailable"):
                        calibration.run(root, output, True)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
