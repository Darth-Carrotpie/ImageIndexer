import contextlib
import io
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
import sys
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import deploy_catalog  # noqa: E402


class DeploymentTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "releases").mkdir()

    def release(self, number, predecessor=None, schema_version=1):
        release_id = f"iip-r{number:06d}"
        root = self.root / "releases" / release_id
        (root / "manifests").mkdir(parents=True)
        (root / "catalog.sqlite").write_bytes(b"fixture")
        manifest = {
            "manifest_schema_version": 1,
            "catalog_id": "indexed-icon-pack",
            "release_id": release_id,
            "predecessor_release_id": predecessor[0] if predecessor else None,
            "predecessor_release_manifest_sha256": predecessor[1] if predecessor else None,
            "catalog_revision": deploy_catalog.digest(b"logical"),
            "schema_version": schema_version,
            "identity_registry_sha256": deploy_catalog.digest(b"identities"),
            "identity_event_range": {"first": 1, "last": 1} if number == 1 else None,
            "payload": [{"path": "catalog.sqlite", "size": 7,
                         "sha256": deploy_catalog.digest(b"fixture")}],
        }
        data = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        (root / "manifests" / "release.json").write_bytes(data)
        return release_id, deploy_catalog.digest(data)

    def activate(self, release, expected):
        args = Namespace(deployment_root=str(self.root), release_id=release[0],
                         expected_manifest_sha256=release[1], expected_active=expected)
        with contextlib.redirect_stdout(io.StringIO()), patch.object(
            deploy_catalog.validate_catalog, "validate", return_value=[]
        ):
            deploy_catalog.activate(args)

    def test_activate_and_rollback_without_changing_releases(self):
        first = self.release(1)
        second = self.release(2, first)
        self.activate(first, "none")
        self.assertEqual(deploy_catalog.read_active(self.root)["release_id"], first[0])
        self.activate(second, first[0])
        with self.assertRaisesRegex(ValueError, "active pointer changed"):
            self.activate(first, "none")
        self.activate(first, second[0])
        self.assertEqual(deploy_catalog.read_active(self.root)["release_id"], first[0])

    def test_corrupt_payload_fails_without_pointer_change(self):
        release = self.release(1)
        (self.root / "releases" / release[0] / "catalog.sqlite").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "payload hash mismatch"):
            self.activate(release, "none")
        self.assertIsNone(deploy_catalog.read_active(self.root))

    def test_deep_catalog_failure_blocks_activation(self):
        release = self.release(1)
        args = Namespace(deployment_root=str(self.root), release_id=release[0],
                         expected_manifest_sha256=release[1], expected_active="none")
        with patch.object(deploy_catalog.validate_catalog, "validate", return_value=["bad FTS"]):
            with self.assertRaisesRegex(ValueError, "deep catalog validation failed"):
                deploy_catalog.activate(args)
        self.assertIsNone(deploy_catalog.read_active(self.root))

    def test_schema_v2_supported_but_unknown_schema_rejected(self):
        release = self.release(1, schema_version=2)
        self.activate(release, "none")
        unsupported = self.release(2, release, schema_version=3)
        with self.assertRaisesRegex(ValueError, "incompatible release manifest"):
            self.activate(unsupported, release[0])
        self.assertEqual(deploy_catalog.read_active(self.root)["release_id"], release[0])


if __name__ == "__main__":
    unittest.main()
