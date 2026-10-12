import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import full_alternative_batch as full
from evaluate_search_v2 import write_new, sha256


class FullAlternativeTest(unittest.TestCase):
    def test_dispatch_is_bounded_and_uncertain_creation_is_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_new(root / "plan.json", {"model": "gpt-6-sol", "effort": "high",
                "requests": [{"id": str(i)} for i in range(6250)]})
            (root / "chunk.jsonl").write_bytes(b"{}\n")
            write_new(root / "dispatch-plan.json", {"plan_sha256": sha256(root / "plan.json"),
                "chunks": [{"input_file": "chunk.jsonl", "sha256": sha256(root / "chunk.jsonl"), "count": 500}] * 3})
            client = Mock()
            client.files.create.return_value = SimpleNamespace(id="file-test")
            client.batches.create.return_value = SimpleNamespace(id="batch-test", status="validating")
            with patch.object(full, "client_for_api", return_value=client), contextlib.redirect_stdout(io.StringIO()):
                full.step(root)
            self.assertEqual(client.batches.create.call_count, 1)
            state = json.loads((root / "state.json").read_text())
            state["batches"][0].pop("batch_id")
            (root / "state.json").write_text(json.dumps(state))
            with patch.object(full, "client_for_api", return_value=client):
                with self.assertRaisesRegex(ValueError, "uncertain batch"):
                    full.step(root)
            self.assertEqual(client.batches.create.call_count, 1)


if __name__ == "__main__":
    unittest.main()
