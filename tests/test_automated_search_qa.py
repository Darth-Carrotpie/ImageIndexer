import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from automated_search_qa import judge_request
from evaluate_search_v2 import sha256
from prepare_release_qa import freeze, ordered


class AutomatedQATests(unittest.TestCase):
    def test_judge_is_blinded_and_image_hash_pinned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "preview.png"
            image.write_bytes(b"test image")
            case = {"case_id": "test", "request": {"text": "gold ring", "like": "SECRET-SEED"},
                    "required_visual_properties": ["ring"], "optional_visual_properties": [],
                    "known_suitable_ids": ["SECRET-TARGET"], "results": [{
                        "icon_id": "SECRET-ID", "rank_score": 100, "description": "SECRET-CAPTION",
                        "thumbnail_relative_path": "preview.png", "thumbnail_sha256": sha256(image)}]}
            payload, mapping = judge_request(case, root)
            self.assertNotIn("SECRET", json.dumps(payload))
            self.assertEqual(mapping, ["SECRET-ID"])
            self.assertEqual(payload["reasoning"]["effort"], "high")
            image.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "hash changed"):
                judge_request(case, root)

    def test_freeze_is_immutable_and_selection_is_deterministic(self):
        self.assertEqual(ordered(["a", "b", "c"], "fixed"), ordered(["c", "a", "b"], "fixed"))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            freeze(output, "test", [("case", {"input": "frozen"}, {})], {})
            plan = json.loads((output / "plan.json").read_text())
            self.assertEqual(plan["requests"][0]["sha256"], sha256(output / "requests/case.json"))
            with self.assertRaisesRegex(ValueError, "new"):
                freeze(output, "test", [], {})


if __name__ == "__main__":
    unittest.main()
