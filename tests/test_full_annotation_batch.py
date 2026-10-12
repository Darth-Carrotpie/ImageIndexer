"""Offline guard for safe Batch queue-limit retries."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from full_annotation_batch import rearm_queue_rejections, retryable_queue_rejection
from assess_annotations import assess, ranked_digest, score_judgments
from annotation_review import apply_review


class QueueRetryTest(unittest.TestCase):
    def test_only_zero_request_queue_rejection_is_retried(self) -> None:
        record = {"batch_id": "batch-old", "file_id": "file-input", "create_attempted": True,
                  "status": "failed", "request_counts": {"completed": 0, "failed": 0, "total": 0},
                  "batch_errors": {"data": [{"code": "token_limit_exceeded"}]}}
        self.assertTrue(retryable_queue_rejection(record))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = {"chunks": {"2": record}}
            rearm_queue_rejections(root, state)
            stored = json.loads((root / "state.json").read_text())["chunks"]["2"]
            self.assertEqual("batch-old", stored["attempts"][0]["batch_id"])
            self.assertEqual("file-input", stored["file_id"])
            self.assertNotIn("batch_id", stored)
        record["status"] = "failed"
        record["request_counts"] = {"completed": 1, "failed": 0, "total": 1}
        self.assertFalse(retryable_queue_rejection(record))

    def test_assessment_rejects_changed_annotation_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "plan.json").write_text("{}")
            (root / "metering.json").write_text('{"annotation_sha256":"wrong"}')
            (root / "annotations.jsonl").write_text("changed\n")
            with self.assertRaisesRegex(ValueError, "metering digest"):
                assess(root, root)

    def test_review_is_pinned_and_leaves_raw_annotation_untouched(self) -> None:
        icon_id = "icon_example"
        raw = {icon_id: {"description": "A marked scroll.", "visible_text": "Illegible marks",
                         "uncertainties": [], "keywords": ["scroll", "marked page", "unreadable text",
                                                         "old ink", "rolled parchment"]}}
        manifest = {icon_id: {"preview_sha256": "preview-hash"}}
        review = {"review_schema_version": 1, "source_annotations_sha256": "raw-hash",
                  "review_method": "visual preview inspection", "items": [{
                      "icon_id": icon_id, "preview_sha256": "preview-hash",
                      "reason": "Writing cannot be read", "move_visible_text_to_uncertainties": True,
                      "remove_keywords": ["unreadable text"],
                      "add_search_terms": ["marked scroll"]}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.json"
            path.write_text(json.dumps(review), encoding="utf-8")
            effective, terms, info = apply_review(raw, manifest, "raw-hash", path)
            self.assertEqual("Illegible marks", raw[icon_id]["visible_text"])
            self.assertIn("unreadable text", raw[icon_id]["keywords"])
            self.assertIsNone(effective[icon_id]["visible_text"])
            self.assertNotIn("unreadable text", effective[icon_id]["keywords"])
            self.assertEqual(["Illegible marks"], effective[icon_id]["uncertainties"])
            self.assertEqual(["marked scroll"], terms[icon_id])
            self.assertEqual(1, info["reviewed_icons"])
            next_review = {"review_schema_version": 1, "source_annotations_sha256": "raw-hash",
                           "base_review_sha256": info["review_sha256"],
                           "review_method": "second visual review", "items": [{
                               "icon_id": icon_id, "preview_sha256": "preview-hash",
                               "reason": "A paper ribbon is visible", "add_search_terms": ["paper ribbon"]}]}
            next_path = Path(directory) / "next-review.json"
            next_path.write_text(json.dumps(next_review), encoding="utf-8")
            later, later_terms, later_info = apply_review(
                effective, manifest, "raw-hash", next_path, terms, info)
            self.assertEqual(["marked scroll", "paper ribbon"], later_terms[icon_id])
            self.assertEqual("raw-hash", review["source_annotations_sha256"])
            self.assertNotEqual(info["accepted_annotation_sha256"],
                                later_info["accepted_annotation_sha256"])
            self.assertEqual(["marked scroll"], terms[icon_id])
            next_review["base_review_sha256"] = "wrong"
            next_path.write_text(json.dumps(next_review), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "base review mismatch"):
                apply_review(effective, manifest, "raw-hash", next_path, terms, info)
            with self.assertRaisesRegex(ValueError, "supplied together"):
                apply_review(effective, manifest, "raw-hash", next_path, prior_info=info)
            review["items"][0]["preview_sha256"] = "wrong"
            path.write_text(json.dumps(review), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unpinned"):
                apply_review(raw, manifest, "raw-hash", path)

    def test_visual_judgments_pin_ranking_and_cover_misses(self) -> None:
        results = [{"target": "one", "annotated_target_rank_top100": 1,
                    "annotated_top5": ["one"]},
                   {"target": "two", "annotated_target_rank_top100": 9,
                    "annotated_top5": ["alternative"]}]
        data = {"judgment_schema_version": 1, "benchmark_sha256": "benchmark",
                "review_sha256": "review", "ranked_results_sha256": ranked_digest(results),
                "rubric": "clear visual match", "misses": [{
                    "target": "two", "matching_icon_id": "alternative", "reason": "same motif"}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "judgments.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(2, score_judgments(results, "benchmark", "review", path)["relevant_top5"])
            data["prompt_issues"] = [{"target": "one", "status": "invalid",
                                       "issue": "The query mislabels its target."}]
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertFalse(score_judgments(results, "benchmark", "review", path)["gate_eligible"])
            data["misses"] = []
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "do not cover"):
                score_judgments(results, "benchmark", "review", path)


if __name__ == "__main__":
    unittest.main()
