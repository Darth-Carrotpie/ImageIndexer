"""Rehearse relocation, read-only consumers, exact copies and rollback in isolation."""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from argparse import Namespace
from urllib.request import Request, urlopen

from deploy_catalog import activate, file_digest, read_active, verify_release
from evaluate_search_v2 import write_new
from validate_catalog import validate


def smoke(package: Path, output: Path) -> None:
    package = package.resolve(strict=True)
    if output.exists():
        raise ValueError("smoke report must be new")
    original_hash = file_digest(package / "manifests/release.json")
    with tempfile.TemporaryDirectory(prefix="indexed-icon-pack-release-proof-") as directory:
        root = Path(directory).resolve()
        release = root / "releases/iip-r000001"
        print("Copying release into an isolated relocation workspace", flush=True)
        shutil.copytree(package, release)
        assert not os.path.samefile(package / "catalog.sqlite", release / "catalog.sqlite")
        manifest = verify_release(root, "iip-r000001", original_hash)
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        environment.pop("INDEXED_ICON_PACK_HOME", None)
        def cli(*args, ok=True):
            result = subprocess.run([sys.executable, "-B", str(release / "iconctl.py"), *args],
                cwd=root, env=environment, capture_output=True, text=True, timeout=600)
            if ok and result.returncode:
                raise ValueError("relocated CLI failed: " + (result.stderr or result.stdout)[:1200])
            if not ok:
                assert result.returncode != 0
                return result
            return json.loads(result.stdout)
        assert cli("verify", "--deep", "--json")["ok"]
        version = cli("version", "--json")
        assert version["release_manifest_sha256"] == original_hash
        assert version["schema_version"] == 2
        search = cli("search", "gold key", "--limit", "5", "--json")
        assert search["returned_count"] == 5 and search["shortfall"] == 0
        key = search["results"][0]["icon_id"]
        detail = cli("show", key, "--json")
        pin = detail["renditions"][0]["sha256"]
        destination = root / "consumer/selected.png"
        destination.parent.mkdir()
        copied = cli("materialize", key, "--sha256", pin, "--to", str(destination), "--json")
        assert file_digest(destination) == pin
        receipt = json.loads(destination.with_name(destination.name + ".icon-receipt.json").read_text())
        assert receipt["stable_handle"]["icon_id"] == key
        cli("materialize", key, "--to", str(destination), ok=False)
        assert file_digest(destination) == pin
        with contextlib.closing(sqlite3.connect((release / "catalog.sqlite").as_uri() + "?mode=ro", uri=True)) as db:
            alternative_id = db.execute("SELECT icon_id FROM icon_keyword WHERE namespace='reviewed_term' LIMIT 1").fetchone()[0]
            all_ids = [row[0] for row in db.execute("SELECT icon_id FROM icon ORDER BY icon_id")]
        assert any(x["namespace"] == "reviewed_term" for x in cli("show", alternative_id, "--json")["keywords"])
        print("Relocated CLI, deep verification and exact materialization passed", flush=True)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        process = subprocess.Popen([sys.executable, "-B", str(release / "iconctl.py"), "serve", "--port", str(port)],
            cwd=root, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        base = f"http://127.0.0.1:{port}"
        def get(path):
            with urlopen(base + path, timeout=20) as response:
                return response.read()
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise ValueError("relocated HTTP server exited")
                try:
                    if json.loads(get("/api/v1/version")) == version:
                        break
                except OSError:
                    time.sleep(.1)
            else:
                raise ValueError("HTTP server did not become ready")
            with urlopen(Request(base + "/api/v1/search", data=json.dumps({"text": "gold key", "limit": 5}).encode(),
                                 headers={"Content-Type": "application/json"}), timeout=20) as response:
                http_search = json.load(response)
            assert [x["icon_id"] for x in http_search["results"]] == [x["icon_id"] for x in search["results"]]
            with urlopen(Request(base + "/api/v1/search", data=json.dumps({"except": all_ids}).encode(),
                                 headers={"Content-Type": "application/json"}), timeout=20) as response:
                assert json.load(response)["returned_count"] == 0
            assert json.loads(get("/api/v1/icons/" + key))["icon_id"] == key
            assert "sha256:" + hashlib.sha256(get("/api/v1/thumbnails/" + key)).hexdigest() == detail["thumbnail"]["sha256"]
            assert "sha256:" + hashlib.sha256(get("/api/v1/blobs/" + pin[7:])).hexdigest() == pin
            assert b"<html" in get("/").lower()
        finally:
            process.terminate()
            process.wait(timeout=20)
        print("Relocated HTTP and browser-shell checks passed", flush=True)
        def select(release_id, expected_hash, expected_active):
            with contextlib.redirect_stdout(io.StringIO()):
                activate(Namespace(deployment_root=str(root), release_id=release_id,
                    expected_manifest_sha256=expected_hash, expected_active=expected_active))
        select("iip-r000001", original_hash, "none")
        # Test-only packaging successor; never published or returned as a deliverable.
        second = root / "releases/iip-r000002"
        shutil.copytree(release, second)
        successor = dict(manifest, release_id="iip-r000002", predecessor_release_id="iip-r000001",
                         predecessor_release_manifest_sha256=original_hash, identity_event_range=None)
        (second / "manifests/release.json").write_text(json.dumps(successor, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        assert not validate(second, previous=release)
        second_hash = file_digest(second / "manifests/release.json")
        select("iip-r000002", second_hash, "iip-r000001")
        select("iip-r000001", original_hash, "iip-r000002")
        assert read_active(root)["release_id"] == "iip-r000001"
        assert file_digest(package / "manifests/release.json") == original_hash
        assert file_digest(release / "manifests/release.json") == original_hash
        print("Isolated activation and rollback passed", flush=True)
    write_new(output, {"ok": True, "release_manifest_sha256": original_hash,
        "checks": ["independent relocated copy", "deep payload/revision validation", "CLI search/show/version",
                   "CLI exact-hash materialization and no overwrite", "HTTP parity and preview/blob bytes",
                   "HTTP exclusion of all 6250 icons",
                   "browser HTML", "automated isolated packaging-successor activation/rollback"],
        "not_checked": ["production consumer integration", "general new-icon successor ingestion",
                        "human usability study", "pixel-level browser layout"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    smoke(args.package, args.output)
