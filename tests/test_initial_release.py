import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_initial_release import acceptance_evidence
import build_initial_release as release_builder
from evaluate_search_v2 import score, sha256, write_new


class ReleaseGateTest(unittest.TestCase):
    def test_read_only_tools_do_not_create_local_bytecode(self):
        for entry in ("validate_catalog.py", "deploy_catalog.py"):
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for name in ("validate_catalog.py", "deploy_catalog.py", "catalog_revision.py"):
                    shutil.copyfile(Path(release_builder.__file__).parent / name, root / name)
                check = "import runpy,sys; sys.path.insert(0,sys.argv[1]); runpy.run_path(sys.argv[2]); import catalog_revision"
                result = subprocess.run([sys.executable, "-c", check, str(root), str(root / entry)],
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(list(root.rglob("__pycache__")), [])

    def test_database_handle_is_closed_before_directory_rename(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, qa = root / "candidate", root / "qa"
            (candidate / "manifests").mkdir(parents=True)
            qa.mkdir()
            (candidate / "catalog.sqlite").write_bytes(b"fixture")
            (candidate / "manifests/icon-identities.jsonl").write_text("fixture\n")
            write_new(candidate / "manifests/search-profile.json", {
                "search_profile_sha256": "a" * 64, "profile": {"implementation_sha256": {}}})
            (qa / "FINAL_SEARCH_REPORT.md").write_text("fixture")
            (root / "RELEASE_README.md").write_text("fixture")
            connection = MagicMock()
            connection.execute.return_value.fetchone.return_value = (2,)
            original_rename = release_builder.os.rename
            def checked_rename(source, destination):
                connection.close.assert_called_once()
                original_rename(source, destination)
            with (patch.object(release_builder, "SOURCE", root),
                  patch.object(release_builder, "FILES", ()),
                  patch.object(release_builder, "acceptance_evidence", return_value={}),
                  patch.object(release_builder, "validate", return_value=[]),
                  patch.object(release_builder, "open_catalog", return_value=(MagicMock(), {}, {})),
                  patch.object(release_builder, "run_search_request", return_value={
                      "results": [{"icon_id": "fixture"}], "returned_count": 1, "shortfall": 4}),
                  patch.object(release_builder, "catalog_revision", return_value=("sha256:" + "b" * 64, {})),
                  patch.object(release_builder.sqlite3, "connect", return_value=connection),
                  patch.object(release_builder.os, "rename", side_effect=checked_rename)):
                release_builder.build(candidate, qa, root / "releases/iip-r000001")

    def prepare(self, root, useful):
        candidate, qa = root / "candidate", root / "qa"
        candidate.mkdir()
        (candidate / "catalog.sqlite").write_bytes(b"fixed candidate")
        for kind, count in (("positive", 50), ("negative", 10)):
            folder = qa / ("acceptance-" + kind)
            cases, labels = [], []
            for i in range(count):
                positive = kind == "positive"
                result = [{"icon_id": "icon-example"}] if positive else []
                family = ("literal" if i < 25 else "seed_modification" if i < 40 else "functional") if positive else "exclusion_negative"
                cases.append({"case_id": str(i), "family": family,
                              "results": result, "returned_count": len(result), "contract_violations": []})
                label = "useful" if i < useful else "unsuitable"
                labels.append({"case_id": str(i), "outcome": "useful_hit" if positive and i < useful else
                               "no_useful_hit" if positive else "expected_empty",
                               "candidates": [{"icon_id": "icon-example", "label": label, "reason": "visible evidence"}]
                               if positive else []})
            write_new(folder / "ranked.json", {"benchmark_sha256": "a" * 64,
                "benchmark_set_kind": "acceptance_" + kind,
                "catalog_sqlite_sha256": sha256(candidate / "catalog.sqlite"),
                "metrics": {"contract_violations": 0}, "cases": cases})
            write_new(folder / "judgments.json", {"judgment_schema_version": 2,
                "benchmark_sha256": "a" * 64, "ranked_results_sha256": sha256(folder / "ranked.json"),
                "reviewer": "fixture", "independent_review": False, "cases": labels})
            write_new(folder / "score.json", score(folder / "ranked.json", folder / "judgments.json"))
        write_new(qa / "acceptance-seal.json", {"catalog_sqlite_sha256": sha256(candidate / "catalog.sqlite"),
            "benchmark_sha256": "a" * 64, "negative_benchmark_sha256": "a" * 64,
            "target_audit_passed": 50})
        return candidate, qa

    def test_80_percent_passes_and_39_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate, qa = self.prepare(Path(directory), 40)
            self.assertEqual(acceptance_evidence(candidate, qa)["positive"]["useful_hit_at_5"], 40)
            seal_path = qa / "acceptance-seal.json"
            seal = json.loads(seal_path.read_text())
            seal_path.write_text(json.dumps(dict(seal, negative_benchmark_sha256="b" * 64)))
            with self.assertRaisesRegex(ValueError, "seal/audit mismatch"):
                acceptance_evidence(candidate, qa)
            seal_path.write_text(json.dumps(seal))
            (candidate / "catalog.sqlite").write_bytes(b"changed candidate")
            with self.assertRaisesRegex(ValueError, "another candidate"):
                acceptance_evidence(candidate, qa)
        with tempfile.TemporaryDirectory() as directory:
            candidate, qa = self.prepare(Path(directory), 39)
            with self.assertRaisesRegex(ValueError, "40/50"):
                acceptance_evidence(candidate, qa)


if __name__ == "__main__":
    unittest.main()
