import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import download_icons as downloader
from build_distribution import add_file, partition, write_json


class DistributionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.release = self.root / "release/iip-r000001"
        self.release.mkdir(parents=True)
        self.cache = self.root / "cache"
        self.cache.mkdir()
        self.content = b"test-image-bytes" * 100
        self.image = self.root / "source.png"
        self.image.write_bytes(self.content)
        self.record = {"path": "assets/sha256/aa/image.png", "size": len(self.content),
                       "sha256": downloader.digest(self.image)}
        self.archive = self.cache / "IndexedIconPack-iip-r000001-images-001.zip"
        with zipfile.ZipFile(self.archive, "x") as zipped:
            add_file(zipped, self.image, self.record["path"])
        self.part = {"filename": self.archive.name, "size": self.archive.stat().st_size,
                     "sha256": downloader.digest(self.archive), "paths": [self.record["path"]]}
        self.records = {self.record["path"]: self.record}

    def server(self, mode):
        payload = self.archive.read_bytes()
        requests = []
        auth = "Basic " + base64.b64encode(b"token:private password").decode()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_GET(self):
                requests.append(dict(self.headers))
                if mode == "unauthorized" or self.headers.get("Authorization") != auth:
                    self.send_response(401)
                    self.end_headers()
                    return
                if mode == "redirect":
                    self.send_response(302)
                    self.send_header("Location", "http://127.0.0.1:1/do-not-forward-password")
                    self.end_headers()
                    return
                start = int(self.headers.get("Range", "bytes=0-")[6:-1])
                ranged = "Range" in self.headers and mode != "ignore-range"
                if not ranged:
                    start = 0
                self.send_response(206 if ranged else 200)
                if ranged:
                    offset = start + (1 if mode == "bad-range" else 0)
                    self.send_header("Content-Range", f"bytes {offset}-{len(payload)-1}/{len(payload)}")
                self.send_header("Content-Length", str(len(payload) - start))
                self.end_headers()
                content = payload[start:]
                if mode == "truncated":
                    content = content[:len(content) // 2]
                if mode == "corrupt":
                    content = b"X" * len(content)
                self.wfile.write(content)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def close():
            server.shutdown()
            server.server_close()
            thread.join()
        self.addCleanup(close)
        return f"http://127.0.0.1:{server.server_port}/part.zip", auth, requests

    def download(self, mode, prefix=b""):
        url, auth, requests = self.server(mode)
        cache = self.root / ("download-" + mode)
        cache.mkdir()
        partial = cache / (self.archive.name + ".part")
        if prefix:
            partial.write_bytes(prefix)
        result = downloader.download(self.part, cache, url, auth)
        self.assertEqual(result.read_bytes(), self.archive.read_bytes())
        self.assertFalse(partial.exists())
        return requests

    def test_password_download_and_verified_resume(self):
        requests = self.download("range", self.archive.read_bytes()[:101])
        self.assertEqual(requests[0]["Range"], "bytes=101-")
        self.assertEqual(requests[0]["X-Requested-With"], "XMLHttpRequest")
        self.download("ignore-range", self.archive.read_bytes()[:101])

    def test_network_failures_preserve_partial_and_do_not_create_archive(self):
        for mode in ("unauthorized", "redirect", "truncated", "corrupt", "bad-range"):
            with self.subTest(mode=mode):
                url, auth, requests = self.server(mode)
                cache = self.root / mode
                cache.mkdir()
                partial = cache / (self.archive.name + ".part")
                partial.write_bytes(self.archive.read_bytes()[:101])
                with self.assertRaises(ValueError) as caught:
                    downloader.download(self.part, cache, url, auth)
                self.assertNotIn("private password", str(caught.exception))
                self.assertNotIn(url, str(caught.exception))
                self.assertFalse((cache / self.archive.name).exists())
                self.assertTrue(partial.exists())
                self.assertEqual(len(requests), 1)

    def test_complete_partial_needs_no_network(self):
        partial = self.cache / (self.archive.name + ".part")
        self.archive.rename(partial)
        result = downloader.download(self.part, self.cache, "https://invalid.example/", "unused")
        self.assertTrue(downloader.matches(result, self.part))

    def test_truncated_download_can_resume_and_bad_cache_is_preserved(self):
        cache = self.root / "interrupted"
        cache.mkdir()
        url, auth, _ = self.server("truncated")
        with self.assertRaisesRegex(ValueError, "Incomplete download"):
            downloader.download(self.part, cache, url, auth)
        partial = cache / (self.archive.name + ".part")
        offset = partial.stat().st_size
        self.assertGreater(offset, 0)
        url, auth, requests = self.server("range")
        restored = downloader.download(self.part, cache, url, auth)
        self.assertEqual(requests[0]["Range"], f"bytes={offset}-")
        restored.write_bytes(b"do not overwrite")
        with self.assertRaisesRegex(ValueError, "Corrupt cached archive"):
            downloader.download(self.part, cache, url, auth)
        self.assertEqual(restored.read_bytes(), b"do not overwrite")
        self.assertEqual(len(requests), 1)

    def test_restore_is_repeatable_and_conflicts_are_not_overwritten(self):
        for _ in range(2):
            downloader.extract(self.archive, self.part, self.release, self.records, self.root)
        target = self.release / self.record["path"]
        self.assertEqual(target.read_bytes(), self.content)
        target.write_bytes(b"user data")
        with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
            downloader.extract(self.archive, self.part, self.release, self.records, self.root)
        self.assertEqual(target.read_bytes(), b"user data")
        self.assertEqual(list(self.root.glob(".icon-extract-*")), [])

    def test_corruption_rejected_before_install(self):
        with self.archive.open("ab") as stream:
            stream.write(b"corruption")
        with self.assertRaisesRegex(ValueError, "Archive hash/size mismatch"):
            downloader.extract(self.archive, self.part, self.release, self.records, self.root)
        self.assertEqual(list(self.release.rglob("*.png")), [])

    def test_safe_paths_zip_slip_symlinks_duplicates_and_wrong_pixel_hash(self):
        for name in ("../escape.png", "/absolute.png", "C:/drive.png", "assets\\bad.png",
                     "assets/a:stream.png", "assets/./a.png", "assets//a.png"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                downloader.safe_path(self.release, name)
        for kind in ("slip", "link", "duplicate", "hash"):
            with self.subTest(kind=kind):
                path = self.root / (kind + ".zip")
                name = "../escape.png" if kind == "slip" else self.record["path"]
                with zipfile.ZipFile(path, "x") as zipped:
                    if kind == "link":
                        info = zipfile.ZipInfo(name)
                        info.create_system = 3
                        info.external_attr = 0o120777 << 16
                        zipped.writestr(info, self.content)
                    else:
                        zipped.writestr(name, self.content)
                        if kind == "duplicate":
                            with self.assertWarns(UserWarning):
                                zipped.writestr(name, self.content)
                part = {**self.part, "size": path.stat().st_size,
                        "sha256": downloader.digest(path), "paths": [name]}
                record = {**self.record, "path": name}
                if kind == "hash":
                    record["sha256"] = "sha256:" + "0" * 64
                with self.assertRaises(ValueError):
                    downloader.extract(path, part, self.release, {name: record}, self.root)
                self.assertEqual(list(self.release.rglob("*.png")), [])

    def test_partition_includes_exact_zip_overhead(self):
        records = [{**self.record, "path": f"assets/{i}.png"} for i in range(5)]
        groups = partition(records, 3500)
        self.assertEqual([len(g) for g in groups], [2, 2, 1])
        for i, group in enumerate(groups):
            path = self.root / f"part-{i}.zip"
            with zipfile.ZipFile(path, "x", allowZip64=False) as zipped:
                for record in group:
                    add_file(zipped, self.image, record["path"])
            expected = 22 + sum(r["size"] + 76 + 2 * len(r["path"]) for r in group)
            self.assertEqual(path.stat().st_size, expected)
            self.assertLessEqual(path.stat().st_size, 3500)
        with self.assertRaises(ValueError):
            partition(records, 100)

    def test_config_requires_https_no_embedded_credentials_and_uses_env(self):
        config = self.root / "nextcloud.json"
        for url in ("http://cloud.example/dav", "https://name:secret@cloud.example/dav",
                    "https://cloud.example/dav?password=secret", "https://cloud.example/dav#fragment"):
            config.write_text(json.dumps({"webdav_base_url": url, "share_token": "token"}))
            with self.assertRaises(ValueError):
                downloader.credentials(config)
        config.write_text(json.dumps({"webdav_base_url": "https://cloud.example/dav/token",
                                      "share_token": "token", "password_env": "IIP_TEST_PASSWORD"}), encoding="utf-8-sig")
        with patch.dict(os.environ, {"IIP_TEST_PASSWORD": "private password"}):
            base, auth = downloader.credentials(config)
        self.assertEqual(base, "https://cloud.example/dav/token/")
        self.assertEqual(base64.b64decode(auth[6:]), b"token:private password")

    def test_plan_pins_metadata_and_exact_image_coverage(self):
        (self.release / "manifests").mkdir()
        metadata = self.release / "catalog.sqlite"
        metadata.write_bytes(b"database")
        manifest = self.release / "manifests/release.json"
        write_json(manifest, {"payload": [self.record, {"path": "catalog.sqlite",
            "size": metadata.stat().st_size, "sha256": downloader.digest(metadata)}]})
        plan = {"schema_version": 1, "release_path": "release/iip-r000001",
                "release_manifest_sha256": downloader.digest(manifest), "parts": [self.part]}
        plan_path = self.root / "distribution.json"
        write_json(plan_path, plan)
        downloader.load_plan(self.root)
        with patch.object(downloader.subprocess, "run") as validate:
            downloader.install(self.root, self.root / "missing-config.json", self.cache, offline=True)
            downloader.install(self.root, self.root / "missing-config.json", self.cache, offline=True)
            self.assertEqual(validate.call_count, 2)
        with self.assertRaisesRegex(ValueError, "outside"):
            downloader.install(self.root, self.root / "missing", self.release / "cache", offline=True)
        plan["parts"] = [self.part, self.part]
        plan_path.write_text(json.dumps(plan))
        with self.assertRaises(ValueError):
            downloader.load_plan(self.root)
        plan["parts"] = []
        plan_path.write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError, "exactly cover"):
            downloader.load_plan(self.root)
        plan["parts"] = [self.part]
        plan_path.write_text(json.dumps(plan))
        metadata.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "Bootstrap payload changed"):
            downloader.load_plan(self.root)
        manifest.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "manifest hash mismatch"):
            downloader.load_plan(self.root)


if __name__ == "__main__":
    unittest.main()
