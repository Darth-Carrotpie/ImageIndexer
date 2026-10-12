"""Checks for schema-v2 benchmark validation and visual scoring."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
MODULE_PATH = PACKAGE / "tools" / "evaluate_search_v2.py"
SPEC = importlib.util.spec_from_file_location("search_evaluator_under_test", MODULE_PATH)
evaluator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(evaluator)


class SearchEvaluationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="search-evaluation-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.icon_id = "icon_11111111-1111-4111-8111-111111111111"

    def benchmark(self) -> Path:
        path = self.root / "benchmark.json"
        path.write_text(json.dumps({
            "benchmark_schema_version": 2,
            "set_kind": "development",
            "author": "test",
            "exposure": "fixture",
            "cases": [{
                "case_id": "literal-001",
                "family": "literal",
                "request": {"text": "shield", "limit": 5},
                "required_visual_properties": ["shield"],
                "optional_visual_properties": [],
                "known_suitable_ids": [self.icon_id],
            }],
        }), encoding="utf-8")
        return path

    def test_benchmark_rejects_overlap_and_missing_seed(self) -> None:
        path = self.benchmark()
        data = json.loads(path.read_text())
        data["cases"][0]["optional_visual_properties"] = ["shield"]
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "overlap"):
            evaluator.load_benchmark(path, strict_allocation=False)
        data["cases"][0].update(family="seed_modification",
                                optional_visual_properties=[])
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "no seed"):
            evaluator.load_benchmark(path, strict_allocation=False)

    def test_scoring_requires_every_ranked_candidate_in_order(self) -> None:
        benchmark = self.benchmark()
        ranked_path = self.root / "ranked.json"
        ranked = {
            "benchmark_sha256": evaluator.sha256(benchmark),
            "metrics": {"contract_violations": 0},
            "cases": [{
                "case_id": "literal-001", "family": "literal",
                "contract_violations": [],
                "results": [{"icon_id": self.icon_id}],
            }],
        }
        ranked_path.write_text(json.dumps(ranked), encoding="utf-8")
        judgments_path = self.root / "judgments.json"
        judgments = {
            "judgment_schema_version": 2,
            "benchmark_sha256": ranked["benchmark_sha256"],
            "ranked_results_sha256": evaluator.sha256(ranked_path),
            "reviewer": "test",
            "independent_review": False,
            "cases": [{
                "case_id": "literal-001", "outcome": "useful_hit",
                "candidates": [{"icon_id": self.icon_id, "label": "useful",
                                "reason": "visible shield"}],
            }],
        }
        judgments_path.write_text(json.dumps(judgments), encoding="utf-8")
        self.assertEqual(1, evaluator.score(ranked_path, judgments_path)["useful_hit_at_5"])
        judgments["cases"][0]["candidates"] = []
        judgments_path.write_text(json.dumps(judgments), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "top five"):
            evaluator.score(ranked_path, judgments_path)


if __name__ == "__main__":
    unittest.main()
