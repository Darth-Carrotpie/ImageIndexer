"""Small offline regression checks for the pre-annotation build and exact pins."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image


sys.dont_write_bytecode = True
PACKAGE = Path(__file__).resolve().parents[1]
BUILDER = PACKAGE / "tools" / "build_catalog.py"
VALIDATOR = PACKAGE / "tools" / "validate_catalog.py"
RUNTIME = PACKAGE / "iconctl.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


builder = load_module("icon_builder_under_test", BUILDER)
validator = load_module("icon_validator_under_test", VALIDATOR)
runtime = load_module("icon_runtime_under_test", RUNTIME)


class CatalogTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="icon-catalog-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.add_icon("Sword Icons", "Sword_Icon_01.png", (230, 40, 20, 255))
        self.add_icon("Shield Icons", "Shield_Icon_01.png", (30, 70, 190, 255))

    def add_icon(self, collection: str, name: str, color: tuple[int, int, int, int]) -> Path:
        target = self.source / collection / "PNG" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (4, 4), color).save(target)
        return target

    def build(self, output: Path, base: Path | None = None) -> None:
        command = [sys.executable, "-B", str(BUILDER), "bootstrap", "--source", str(self.source), "--output", str(output)]
        if base:
            command.extend(("--base", str(base)))
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode:
            self.fail(f"builder failed: {result.stderr}")

    def registry(self, candidate: Path) -> dict[str, str]:
        return {row["source_key"]: row["icon_id"] for row in map(
            json.loads, (candidate / "manifests" / "icon-identities.jsonl").read_text().splitlines()
        )}

    def published_fixture(self, candidate: Path) -> Path:
        """Synthetic release for consumer pin tests; never a real publication."""
        release = self.root / "synthetic-release"
        shutil.copytree(candidate, release)
        with closing(sqlite3.connect(release / "catalog.sqlite")) as connection:
            connection.execute("UPDATE catalog_state SET annotation_status='fixture_only'")
            connection.commit()
        registry = release / "manifests" / "icon-identities.jsonl"
        payload = []
        for path in sorted((p for p in release.rglob("*") if p.is_file()), key=lambda p: p.relative_to(release).as_posix()):
            payload.append({"path": path.relative_to(release).as_posix(), "size": path.stat().st_size,
                            "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()})
        manifest = {
            "manifest_schema_version": 1, "catalog_id": "indexed-icon-pack", "release_id": "iip-r000001",
            "predecessor_release_id": None, "predecessor_release_manifest_sha256": None,
            "catalog_revision": "sha256:" + hashlib.sha256(b"synthetic fixture only").hexdigest(),
            "schema_version": 1,
            "identity_registry_sha256": "sha256:" + hashlib.sha256(registry.read_bytes()).hexdigest(),
            "identity_event_range": {"first": 1, "last": len(self.registry(candidate))},
            "payload": payload,
        }
        (release / "manifests" / "release.json").write_text(json.dumps(manifest, sort_keys=True) + "\n")
        return release

    def test_bootstrap_addition_and_model_gate_are_offline(self) -> None:
        first = self.root / "candidate-1"
        # Any network attempt during deterministic build or plan generation fails the test.
        with patch("socket.socket", side_effect=AssertionError("unexpected network/model call")), redirect_stdout(io.StringIO()):
            builder.build(self.source, first, None)
            plan = self.root / "annotation-plan.json"
            builder.annotation_plan(first, plan)
        self.assertEqual([], validator.validate(first))
        decision = json.loads(plan.read_text())
        self.assertEqual("stop_before_any_image_model_call", decision["status"])
        self.assertEqual(2, decision["pending_logical_icons"])
        with closing(sqlite3.connect(first / "catalog.sqlite")) as connection:
            self.assertEqual(0, connection.execute("SELECT count(*) FROM icon WHERE description != ''").fetchone()[0])
            self.assertEqual(0, connection.execute("SELECT count(*) FROM icon_keyword").fetchone()[0])
        ids = self.registry(first)

        self.add_icon("Wand Icons", "Wand_Icon_01.png", (140, 30, 220, 255))
        second = self.root / "candidate-2"
        self.build(second, first)
        self.assertEqual([], validator.validate(second, previous=first))
        self.assertEqual(ids, {key: value for key, value in self.registry(second).items() if key in ids})
        self.assertTrue((second / "manifests" / "icon-identities.jsonl").read_bytes().startswith(
            (first / "manifests" / "icon-identities.jsonl").read_bytes()
        ))
        self.assertFalse((second / "manifests" / "release.json").exists())

        changed = self.source / "Sword Icons" / "PNG" / "Sword_Icon_01.png"
        Image.new("RGBA", (4, 4), (1, 2, 3, 255)).save(changed)
        attempt = subprocess.run(
            [sys.executable, "-B", str(BUILDER), "bootstrap", "--source", str(self.source),
             "--output", str(self.root / "refused-change"), "--base", str(second)],
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(0, attempt.returncode)
        self.assertIn("continuity review", attempt.stderr)
        self.assertFalse((self.root / "refused-change").exists())

    def test_identity_freeze_pins_ids_and_reviewed_cross_pairs(self) -> None:
        background = self.source / "Halloween Icons" / "Background"
        transparent = self.source / "Halloween Icons" / "No Background"
        background.mkdir(parents=True)
        transparent.mkdir(parents=True)
        matched_ordinals = {47: 49, 48: 50, 49: 48, 50: 47}
        for number, other in matched_ordinals.items():
            image = Image.new("RGBA", (4, 4), (number, 20, 100, 255))
            image.save(background / f"Halloween_Icon_{number}.png")
            image.save(transparent / f"Halloween_Icon_NoBG_{other}.png")
        candidate = self.root / "candidate"
        self.build(candidate)
        manifest = candidate / "manifests/catalog.jsonl"
        registry = candidate / "manifests/icon-identities.jsonl"
        rows = {row["source_path"]: row for row in map(json.loads, manifest.read_text().splitlines())}
        identities = self.registry(candidate)
        corrections = []
        for number, other in matched_ordinals.items():
            key = f"Halloween Icons/{number:04d}"
            path = f"Halloween Icons/Background/Halloween_Icon_{number}.png"
            corrections.append({"source_key": key, "icon_id": identities[key],
                                "background_source_path": path,
                                "matching_source_path": f"Halloween Icons/No Background/Halloween_Icon_NoBG_{other}.png",
                                "matching_blob_sha256": rows[path]["blob_sha256"]})
        event = json.loads(registry.read_text().splitlines()[0])
        freeze = {"freeze_schema_version": 1, "status": "frozen_ids_unpublished",
                  "catalog_id": event["catalog_id"], "pack_id": event["pack_id"],
                  "identity_event_count": len(identities),
                  "identity_registry_sha256": hashlib.sha256(registry.read_bytes()).hexdigest(),
                  "source_catalog_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                  "corrections": corrections}
        freeze_path = self.root / "freeze.json"
        freeze_path.write_text(json.dumps(freeze))
        self.assertEqual([], validator.validate(candidate, freeze=freeze_path))
        freeze["corrections"][0]["icon_id"] = identities["Halloween Icons/0048"]
        freeze_path.write_text(json.dumps(freeze))
        self.assertTrue(any("unproven identity correction" in error
                            for error in validator.validate(candidate, freeze=freeze_path)))
        freeze["corrections"][0]["icon_id"] = identities["Halloween Icons/0047"]
        freeze["identity_registry_sha256"] = "0" * 64
        freeze_path.write_text(json.dumps(freeze))
        self.assertTrue(any("frozen identity registry hash mismatch" in error
                            for error in validator.validate(candidate, freeze=freeze_path)))

    def test_search_prefers_distinct_query_term_coverage(self) -> None:
        self.add_icon("Wand Icons", "Wand_Icon_01.png", (10, 20, 30, 255))
        candidate = self.root / "candidate"
        self.build(candidate)
        with closing(sqlite3.connect(candidate / "catalog.sqlite")) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("SELECT icon_id,title,collection FROM icon").fetchall()
            ids = {row["collection"]: row["icon_id"] for row in rows}
            connection.execute("DELETE FROM icon_fts")
            for row in rows:
                description = ("blue frost shield" if row["collection"] == "Shield Icons"
                               else "frost frost frost" if row["collection"] == "Sword Icons"
                               else "blue wand")
                connection.execute("INSERT INTO icon_fts VALUES (?,?,?,?,?)",
                                   (row["icon_id"], row["title"], row["collection"], description, ""))
            results = runtime.legacy_search_icons(connection, "blue shield with frost", 2)
            self.assertEqual(ids["Shield Icons"], results[0]["icon_id"])
            self.assertEqual((3, 3), (results[0]["matched_query_terms"], results[0]["query_term_count"]))
            self.assertEqual(2, len(results))
            partial = runtime.legacy_search_icons(connection, "orange blue shield frost", 1)[0]
            self.assertEqual((3, 4), (partial["matched_query_terms"], partial["query_term_count"]))

    def test_exact_pin_requires_own_icon_and_release_manifest(self) -> None:
        candidate = self.root / "candidate"
        self.build(candidate)
        with closing(sqlite3.connect(candidate / "catalog.sqlite")) as connection:
            rows = connection.execute("SELECT icon_id,blob_sha256 FROM rendition ORDER BY icon_id").fetchall()
        first_id, first_sha = rows[0]
        second_id, second_sha = rows[1]
        with closing(sqlite3.connect(candidate / "catalog.sqlite")) as connection:
            connection.row_factory = sqlite3.Row
            self.assertEqual(first_sha, runtime.resolve_rendition(connection, first_id, "sha256:" + first_sha)["sha256"])
            with self.assertRaises(LookupError):
                runtime.resolve_rendition(connection, first_id, "sha256:" + second_sha)
        unreleased = subprocess.run(
            [sys.executable, "-B", str(RUNTIME), "--package", str(candidate), "materialize", first_id,
             "--to", str(self.root / "unreleased.png"), "--sha256", "sha256:" + first_sha],
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(0, unreleased.returncode)
        self.assertFalse((self.root / "unreleased.png").exists())

        release = self.published_fixture(candidate)
        self.assertEqual([], validator.validate(release))
        verification = subprocess.run(
            [sys.executable, "-B", str(RUNTIME), "--package", str(release), "verify", "--deep", "--json"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(0, verification.returncode, verification.stderr)
        self.assertEqual("release_manifest_present", json.loads(verification.stdout)["package_status"])
        destination = self.root / "selected.png"
        selected = subprocess.run(
            [sys.executable, "-B", str(RUNTIME), "--package", str(release), "materialize", first_id,
             "--to", str(destination), "--sha256", "sha256:" + first_sha],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(0, selected.returncode, selected.stderr)
        self.assertEqual(first_sha, hashlib.sha256(destination.read_bytes()).hexdigest())
        self.assertTrue(destination.with_name(destination.name + ".icon-receipt.json").is_file())
        wrong = subprocess.run(
            [sys.executable, "-B", str(RUNTIME), "--package", str(release), "materialize", first_id,
             "--to", str(self.root / "wrong.png"), "--sha256", "sha256:" + second_sha],
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(0, wrong.returncode)
        self.assertFalse((self.root / "wrong.png").exists())
        manifest_path = release / "manifests" / "release.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["payload"].pop()
        manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")
        self.assertTrue(any("payload file set mismatch" in error for error in validator.validate(release)))

    def test_validator_finds_tampering_and_editor_sidecars(self) -> None:
        candidate = self.root / "candidate"
        self.build(candidate)
        with closing(sqlite3.connect(candidate / "catalog.sqlite")) as connection:
            sha = connection.execute("SELECT sha256 FROM blob LIMIT 1").fetchone()[0]
        blob = candidate / "assets" / "sha256" / sha[:2] / f"{sha}.png"
        blob.write_bytes(blob.read_bytes() + b"tampered")
        self.assertTrue(any("blob SHA-256 mismatch" in error for error in validator.validate(candidate)))
        (candidate / "accidental.meta").write_text("editor sidecar")
        self.assertTrue(any("sidecar" in error for error in validator.validate(candidate)))
        with closing(sqlite3.connect(candidate / "catalog.sqlite")) as connection:
            connection.execute("UPDATE blob SET relative_path='../escaped.png' WHERE sha256=?", (sha,))
            connection.commit()
        self.assertTrue(any("invalid relative path" in error for error in validator.validate(candidate)))

    def test_read_only_http_reports_loaded_release(self) -> None:
        candidate = self.root / "candidate"
        self.build(candidate)
        release = self.published_fixture(candidate)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        process = subprocess.Popen(
            [sys.executable, "-B", str(RUNTIME), "--package", str(release), "serve", "--port", str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(50):
                if process.poll() is not None:
                    self.fail("read-only API exited before serving")
                try:
                    with urlopen(f"http://127.0.0.1:{port}/api/v1/version", timeout=0.2) as response:
                        version = json.load(response)
                    break
                except OSError:
                    time.sleep(0.05)
            else:
                self.fail("read-only API did not start")
            self.assertEqual("iip-r000001", version["release_id"])
            self.assertEqual("release_manifest_present", version["package_status"])
            with urlopen(f"http://127.0.0.1:{port}/api/v1/search?q=Sword", timeout=1) as response:
                matches = json.load(response)
            self.assertEqual(1, len(matches["results"]))
            self.assertEqual(self.registry(candidate)["Sword Icons/0001"], matches["results"][0]["icon_id"])
            # The transport must fit a full-catalog exclusion list (~282 KB).
            body = b" " * 300000 + json.dumps({"text": "Sword"}).encode()
            request = Request(f"http://127.0.0.1:{port}/api/v1/search", body,
                              {"Content-Type": "application/json"})
            with urlopen(request, timeout=2) as response:
                self.assertEqual(1, json.load(response)["returned_count"])
            request = Request(f"http://127.0.0.1:{port}/api/v1/search", b" " * 524289,
                              {"Content-Type": "application/json"})
            with self.assertRaises(HTTPError) as error:
                urlopen(request, timeout=2)
            self.assertEqual(400, error.exception.code)
            error.exception.close()
        finally:
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
