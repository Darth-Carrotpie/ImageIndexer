import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from catalog_revision import catalog_revision


class RevisionTest(unittest.TestCase):
    def test_revision_tracks_logical_data_not_layout_or_packaging(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifests").mkdir()
            for name in ("icon-identities.jsonl", "catalog.jsonl", "annotation-provenance.json",
                         "rendition-corrections.json"):
                (root / "manifests" / name).write_text("{}\n", encoding="utf-8")
            db = sqlite3.connect(":memory:")
            self.addCleanup(db.close)
            db.execute("CREATE TABLE catalog_state(catalog_id,pack_id)")
            db.execute("INSERT INTO catalog_state VALUES('catalog','pack')")
            for name in ("icon", "blob", "rendition", "rendition_history", "icon_observation"):
                db.execute(f"CREATE TABLE {name}(id,description)")
                db.executemany(f"INSERT INTO {name} VALUES(?,?)", [(2, "second"), (1, "first")])
            original, inputs = catalog_revision(root, db)
            (root / "README.md").write_text("different documentation", encoding="utf-8")
            (root / "manifests/annotation-provenance.json").write_text("{  }\n", encoding="utf-8")
            db.execute("ALTER TABLE blob ADD COLUMN relative_path")
            db.execute("UPDATE blob SET relative_path='different/package/layout.png'")
            self.assertEqual(original, catalog_revision(root, db)[0])
            db.execute("DELETE FROM icon WHERE id=2")
            db.execute("INSERT INTO icon VALUES(2,'second')")
            db.commit()
            db.execute("VACUUM")
            self.assertEqual(original, catalog_revision(root, db)[0])
            db.execute("UPDATE icon SET description='changed' WHERE id=2")
            self.assertNotEqual(original, catalog_revision(root, db)[0])
            self.assertEqual(json.loads(json.dumps(inputs)), inputs)


if __name__ == "__main__":
    unittest.main()
