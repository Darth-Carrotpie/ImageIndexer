import json
from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_public_catalog as publication
from download_icons import digest
from build_distribution import write_json


class PublicCatalogTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bootstrap = self.root / "bootstrap"
        self.release = self.bootstrap / "release/iip-r000001"
        (self.release / "manifests").mkdir(parents=True)
        database = self.release / "catalog.sqlite"
        with closing(sqlite3.connect(database)) as db:
            db.execute("CREATE TABLE icon(icon_id TEXT PRIMARY KEY)")
            db.execute("CREATE TABLE icon_observation(icon_id TEXT PRIMARY KEY, observation_json TEXT)")
            for key in ("b", "a"):
                db.execute("INSERT INTO icon VALUES (?)", (key,))
                db.execute("INSERT INTO icon_observation VALUES (?, ?)",
                           (key, json.dumps({"caption": "key", "alternatives": ["unlock", "access"]})))
            db.commit()
        image = {"path": "assets/sha256/test.png", "size": 1, "sha256": "sha256:" + "a" * 64}
        manifest = self.release / "manifests/release.json"
        write_json(manifest, {"payload": [image, {"path": "catalog.sqlite", "size": database.stat().st_size,
                                                "sha256": digest(database)}]})
        self.pin = digest(manifest)
        write_json(self.bootstrap / "distribution.json", {"schema_version": 1,
            "release_path": "release/iip-r000001", "release_manifest_sha256": self.pin,
            "parts": [{"filename": "IndexedIconPack-iip-r000001-images-001.zip", "size": 1,
                       "sha256": "sha256:" + "b" * 64, "paths": [image["path"]]}]})
        self.output = self.root / "catalog"

    def prepare(self):
        return publication.prepare(self.bootstrap, self.output, self.pin)

    def test_preparation_preserves_release_and_exports_all_observations(self):
        before = digest(self.release / "catalog.sqlite")
        result = self.prepare()
        self.assertEqual(result["observations"], 2)
        self.assertEqual(result["status"], "metadata_verified_images_not_checked")
        self.assertEqual(digest(self.output / "release/iip-r000001/catalog.sqlite"), before)
        rows = [json.loads(line) for line in (self.output / "observations.jsonl").read_text().splitlines()]
        self.assertEqual([r["icon_id"] for r in rows], ["a", "b"])
        self.assertEqual(rows[0]["observation"]["alternatives"], ["unlock", "access"])
        self.assertTrue((self.output / "LICENSE").is_file())
        self.assertFalse((self.output / "nextcloud.json").exists())
        self.assertFalse(list(self.output.rglob("*.png")))
        with self.assertRaisesRegex(ValueError, "new directory"):
            self.prepare()

    def test_bad_pin_tampered_metadata_and_export_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "trusted manifest"):
            publication.prepare(self.bootstrap, self.output, "0" * 64)
        self.assertFalse(self.output.exists())
        self.prepare()
        export = self.output / "observations.jsonl"
        export.write_text(export.read_text() + "{}\n", encoding="utf-8", newline="\n")
        with self.assertRaisesRegex(ValueError, "extra records"):
            publication.check_catalog(self.output)
        (self.output / "release/iip-r000001/catalog.sqlite").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "payload changed"):
            publication.check_catalog(self.output)

    def test_zip_excludes_restored_images_and_private_config(self):
        self.prepare()
        image = self.output / "release/iip-r000001/assets/sha256/test.png"
        image.parent.mkdir(parents=True)
        image.write_bytes(b"private")
        (self.output / "nextcloud.json").write_text('{"share_token":"private"}')
        output = self.root / "public.zip"
        publication.make_zip(self.output, output)
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
            self.assertIn("LICENSE", names)
            self.assertIn("nextcloud.example.json", names)
            self.assertIn("observations.jsonl", names)
            self.assertNotIn("nextcloud.json", names)
            self.assertFalse(any(n.endswith(".png") for n in names))
        with self.assertRaisesRegex(ValueError, "must be new"):
            publication.make_zip(self.output, output)

    def test_private_files_secrets_and_oversized_files_are_rejected(self):
        sample = self.root / "sample.txt"
        sample.write_text("normal")
        for name in ("work/run.txt", "art.png", "nextcloud.json", ".env", "other.sqlite-wal"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("private")
            with self.assertRaisesRegex(ValueError, "Private/generated"):
                publication.inspect_public_file(path, name, "catalog/catalog.sqlite")
        with patch.object(publication, "MAX_FILE_BYTES", 6), self.assertRaisesRegex(ValueError, "ceiling"):
            publication.inspect_public_file(sample, "sample.txt", "catalog/catalog.sqlite")
        sample.write_text("sk-" + "a" * 30)
        with self.assertRaisesRegex(ValueError, "Potential secret"):
            publication.inspect_public_file(sample, "sample.txt", "catalog/catalog.sqlite")

    def test_git_inventory_respects_byte_preservation_and_detects_force_added_images(self):
        self.prepare()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / ".gitignore").write_text("/bootstrap/\n*.png\n", encoding="utf-8")
        attrs = self.root / ".gitattributes"
        attrs.write_text("catalog/release/** -text -filter\ncatalog/distribution.json -text -filter\n")
        publication.check_repository(self.root, self.output)
        attrs.write_text("catalog/release/** text\n")
        with self.assertRaisesRegex(ValueError, "attributes"):
            publication.check_repository(self.root, self.output)
        attrs.write_text("catalog/release/** -text -filter\ncatalog/distribution.json -text -filter\n")
        image = self.root / "private.png"
        image.write_bytes(b"private image")
        subprocess.run(["git", "-C", str(self.root), "add", "-f", "private.png"], check=True)
        with self.assertRaisesRegex(ValueError, "Private/generated"):
            publication.check_repository(self.root, self.output)


if __name__ == "__main__":
    unittest.main()
