import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile


# The standalone shell entry point embeds its stdlib bootstrap: test that exact code.
SOURCE = Path(__file__).resolve().parents[1]
script = (SOURCE / "ImageIndexerInstaller.sh").read_text(encoding="utf-8")
installer = types.ModuleType("installer")
exec(compile(script.split("<<'IMAGEINDEXER_PY'\n", 1)[1].rsplit("\nIMAGEINDEXER_PY", 1)[0],
             "ImageIndexerInstaller.sh", "exec"), installer.__dict__)


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.commit = "a" * 40

    def archive(self, members):
        content = io.BytesIO()
        with zipfile.ZipFile(content, "w") as zipped:
            for name, data in members:
                if isinstance(name, str):
                    info = zipfile.ZipInfo(name)
                    info.filename = name  # Preserve hostile backslashes on Windows for this test.
                else:
                    info = name
                zipped.writestr(info, data)
        return content.getvalue()

    def test_rejects_unsafe_archives_before_writing(self):
        prefix = "ImageIndexer-" + self.commit + "/"
        link = zipfile.ZipInfo(prefix + "link")
        link.external_attr = 0o120777 << 16
        for bad in (prefix + "../escape", prefix + "C:/escape", prefix + "a\\escape",
                    prefix + "a/./escape", prefix + "a//escape", prefix + "A.txt",
                    prefix + "con.txt", prefix + ".git/config", "wrong/root", link):
            with self.subTest(bad=bad):
                archive = io.BytesIO(self.archive([(prefix + "a.txt", b"safe"), (bad, b"unsafe")]))
                with self.assertRaises(ValueError):
                    installer.unpack(archive, self.root / "output", self.commit)
                self.assertFalse((self.root / "output").exists())

    def test_bootstrap_pins_one_commit_and_resume_does_not_redownload(self):
        target = self.root / "directory with spaces"
        target.mkdir()
        archive = self.archive([("ImageIndexer-" + self.commit + "/README.md", b"example")])
        requests = []
        def fetch(url, output, limit):
            requests.append(url)
            output.write(json.dumps({"object": {"sha": self.commit}}).encode() if len(requests) == 1 else archive)
        with patch.object(installer, "fetch", side_effect=fetch), patch.object(installer, "run") as run:
            installer.bootstrap(target)
            installer.bootstrap(target)
            self.assertEqual(run.call_count, 3)
        self.assertEqual(len(requests), 2)
        self.assertTrue(requests[1].endswith("/zip/" + self.commit))
        self.assertEqual(json.loads((target / installer.RECEIPT).read_text())["commit"], self.commit)
        self.assertEqual((target / "README.md").read_bytes(), b"example")

    def test_refuses_existing_directory_and_holds_exclusive_lock(self):
        (self.root / "user.txt").write_text("keep me")
        with self.assertRaisesRegex(ValueError, "not empty"):
            installer.install(self.root)
        self.assertEqual((self.root / "user.txt").read_text(), "keep me")
        self.assertFalse((self.root / ".installer.lock").exists())
        (self.root / ".installer.lock").touch()
        with self.assertRaisesRegex(ValueError, "lock exists"):
            installer.install(self.root)
        self.assertTrue((self.root / ".installer.lock").exists())

    def test_failed_metadata_check_never_publishes_snapshot(self):
        archive = self.archive([("ImageIndexer-" + self.commit + "/README.md", b"example")])
        def fetch(url, output, limit):
            output.write(json.dumps({"object": {"sha": self.commit}}).encode() if "/git/ref/" in url else archive)
        with patch.object(installer, "fetch", side_effect=fetch), \
                patch.object(installer, "run", side_effect=ValueError("metadata mismatch")):
            with self.assertRaisesRegex(ValueError, "metadata mismatch"):
                installer.install(self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_image_step_and_metadata_only_choice(self):
        catalog = self.root / "catalog"
        catalog.mkdir()
        (catalog / "distribution.json").write_text(json.dumps({"release_path": "release/iip-r000001"}))
        for answer, count in (("", 1), ("n", 0)):
            with patch.object(installer, "bootstrap"), patch("builtins.input", return_value=answer), \
                    patch.object(installer, "run") as run:
                installer.install(self.root)
                self.assertEqual(run.call_count, count)
                if count:
                    self.assertEqual(run.call_args.args[1], catalog / "download_icons.py")
            self.assertFalse((self.root / ".installer.lock").exists())

    def test_child_process_receives_prompt_terminal_not_script_stdin(self):
        with patch.object(installer.subprocess, "run") as run:
            installer.run(self.root, "example.py")
        self.assertIs(run.call_args.kwargs["stdin"], sys.stdin)


if __name__ == "__main__":
    unittest.main()
