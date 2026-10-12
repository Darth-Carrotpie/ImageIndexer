"""Schema-v2 logical revision: canonical data, never SQLite pages or packaging."""
import hashlib
import json
from pathlib import Path
import sqlite3


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def revision_inputs(root: Path, connection: sqlite3.Connection) -> dict:
    files = {}
    for name in ("icon-identities.jsonl", "catalog.jsonl", "annotation-provenance.json",
                 "rendition-corrections.json"):
        path = root / "manifests" / name
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root.resolve()):
            raise ValueError("logical revision input escapes package")
        data = path.read_bytes()
        files[name] = digest(canonical(json.loads(data)) if path.suffix == ".json" else data)
    tables = {}
    # Derived thumbnails, FTS/facets, tool hashes and release state are excluded.
    for name in ("icon", "blob", "rendition", "rendition_history", "icon_observation"):
        columns = [row[1] for row in connection.execute(f"PRAGMA table_info({name})")]
        rows = [dict(zip(columns, row)) for row in connection.execute(f"SELECT * FROM {name}")]
        if name == "blob":
            for row in rows:
                row.pop("relative_path", None)
        tables[name] = digest(b"\n".join(sorted(canonical(row) for row in rows)) + b"\n")
    identity = connection.execute("SELECT catalog_id,pack_id FROM catalog_state").fetchall()
    if len(identity) != 1:
        raise ValueError("logical revision needs one catalog identity")
    return {"revision_schema_version": 1, "catalog_id": identity[0][0],
            "pack_id": identity[0][1], "files": files, "logical_tables": tables}


def catalog_revision(root: Path, connection: sqlite3.Connection) -> tuple[str, dict]:
    inputs = revision_inputs(root, connection)
    return digest(canonical(inputs)), inputs
