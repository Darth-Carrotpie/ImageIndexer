"""Prepare the fixed 100-icon pilot without changing the catalog or calling a model."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from PIL import Image, ImageDraw


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_file(root: Path, relative: str) -> Path:
    path = root / relative
    if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root):
        raise ValueError(f"file escapes candidate: {relative}")
    return path


def visible_preview(image: Image.Image) -> Image.Image:
    """Show alpha honestly; some source PNGs have colored pixels at zero alpha."""
    tile = 32
    matte = Image.new("RGBA", image.size, (208, 208, 208, 255))
    draw = ImageDraw.Draw(matte)
    for y in range(0, image.height, tile):
        for x in range(0, image.width, tile):
            if (x // tile + y // tile) % 2:
                draw.rectangle((x, y, min(x + tile - 1, image.width - 1),
                                min(y + tile - 1, image.height - 1)), fill=(144, 144, 144, 255))
    matte.alpha_composite(image.convert("RGBA"))
    return matte.convert("RGB")


def prepare(candidate: Path, decision: Path, output: Path) -> None:
    candidate = candidate.resolve(strict=True)
    if output.exists() or output.is_symlink():
        raise ValueError(f"pilot output already exists: {output}")
    plan = json.loads(decision.read_text(encoding="utf-8"))
    sample = plan["sample"]
    if len(sample) != 100 or len({item["icon_id"] for item in sample}) != 100:
        raise ValueError("decision packet must contain 100 distinct icons")
    max_edge = plan["cost_inputs"]["annotation_preview_max_edge_px"]
    if max_edge != 512:
        raise ValueError("unexpected preview policy")
    connection = sqlite3.connect(f"file:{(candidate / 'catalog.sqlite').as_posix()}?mode=ro", uri=True)
    output.mkdir(parents=True)
    previews = output / "previews"
    previews.mkdir()
    entries = []
    try:
        for number, item in enumerate(sample, 1):
            icon_id = item["icon_id"]
            preferred = connection.execute("SELECT preferred_role FROM icon WHERE icon_id=?", (icon_id,)).fetchone()
            if preferred is None:
                raise ValueError(f"missing icon: {icon_id}")
            rows = connection.execute(
                "SELECT r.stable_role,b.sha256,b.relative_path,b.width,b.height "
                "FROM rendition r JOIN blob b ON b.sha256=r.blob_sha256 "
                "WHERE r.icon_id=? ORDER BY r.stable_role", (icon_id,)
            ).fetchall()
            chosen = rows if "ambiguous" in item["categories"] else [
                row for row in rows if row[0] == preferred[0]
            ]
            if not chosen:
                raise ValueError(f"missing preferred rendition: {icon_id}")
            renditions = []
            for role, blob_hash, relative, width, height in chosen:
                source = safe_file(candidate, relative)
                if sha256(source) != blob_hash:
                    raise ValueError(f"blob hash mismatch: {icon_id}/{role}")
                preview = previews / f"{number:03d}_{icon_id}_{role}.png"
                with Image.open(source) as image:
                    image.load()
                    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
                    visible_preview(image).save(preview, format="PNG")
                    preview_size = [image.width, image.height]
                renditions.append({
                    "role": role, "source_blob_sha256": blob_hash,
                    "source_size": [width, height],
                    "preview": preview.relative_to(output).as_posix(),
                    "preview_sha256": sha256(preview), "preview_size": preview_size,
                })
            entries.append({"number": number, "icon_id": icon_id,
                            "categories": item["categories"], "renditions": renditions})
    finally:
        connection.close()
    manifest = {"schema_version": 1, "model": "gpt-6-sol", "reasoning_effort": "high",
                "decision_packet_sha256": sha256(decision), "candidate_registry_sha256": sha256(
                    candidate / "manifests/icon-identities.jsonl"),
                "preview_max_edge_px": max_edge,
                "preview_background": "32px gray checkerboard; ignore it when describing the icon",
                "sample": entries}
    (output / "pilot-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"icons": len(entries), "previews": sum(len(e["renditions"]) for e in entries),
                      "manifest": str(output / "pilot-manifest.json")}, sort_keys=True))


def check(output: Path) -> None:
    if visible_preview(Image.new("RGBA", (1, 1), (255, 0, 0, 0))).getpixel((0, 0)) != (208, 208, 208):
        raise ValueError("fully transparent source RGB leaked into preview")
    manifest = json.loads((output / "pilot-manifest.json").read_text(encoding="utf-8"))
    if len(manifest["sample"]) != 100:
        raise ValueError("pilot must contain 100 icons")
    for item in manifest["sample"]:
        for rendition in item["renditions"]:
            preview = safe_file(output.resolve(strict=True), rendition["preview"])
            if sha256(preview) != rendition["preview_sha256"]:
                raise ValueError(f"preview hash mismatch: {preview}")
            with Image.open(preview) as image:
                image.verify()
                if (image.mode != "RGB" or list(image.size) != rendition["preview_size"]
                        or max(image.size) > 512):
                    raise ValueError(f"invalid preview dimensions: {preview}")
    print(json.dumps({"ok": True, "icons": 100}, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    first = sub.add_parser("prepare")
    first.add_argument("--candidate", type=Path, required=True)
    first.add_argument("--decision", type=Path, required=True)
    first.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("check")
    verify.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.candidate, args.decision, args.output)
    else:
        check(args.output)


if __name__ == "__main__":
    main()
