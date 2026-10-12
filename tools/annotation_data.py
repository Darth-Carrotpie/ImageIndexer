"""Validate and load the accepted annotation view shared by build and QA tools."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path

from annotation_review import apply_review


LIST_FIELDS = ("keywords", "subjects", "materials", "colors", "effects", "symbols",
               "inferred_uses", "uncertainties")
TEXT_FIELDS = ("description", "composition")
OPTIONAL_TEXT_FIELDS = ("action", "visible_text", "state")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def accepted_sha256(annotations: dict[str, dict], reviewed_terms: dict[str, list[str]]) -> str:
    digest = hashlib.sha256()
    for icon_id in sorted(annotations):
        row = {"icon_id": icon_id, "annotation": annotations[icon_id],
               "reviewed_search_terms": reviewed_terms.get(icon_id, [])}
        digest.update(json.dumps(row, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")).encode("utf-8") + b"\n")
    return digest.hexdigest()


def load_annotations(run: Path, reviews: list[Path] | tuple[Path, ...] = ()) -> dict:
    """Return the complete, preview-pinned effective observation set."""
    run = run.resolve(strict=True)
    plan = json.loads((run / "plan.json").read_text(encoding="utf-8"))
    metering = json.loads((run / "metering.json").read_text(encoding="utf-8"))
    annotation_path = run / "annotations.jsonl"
    raw_sha256 = sha256(annotation_path)
    if raw_sha256 != metering.get("annotation_sha256"):
        raise ValueError("annotation file does not match metering digest")
    manifest_path = run / "icons.jsonl"
    if sha256(manifest_path) != plan.get("icons_manifest_sha256"):
        raise ValueError("icon manifest does not match frozen plan")

    manifest = {}
    for line in manifest_path.open(encoding="utf-8"):
        item = json.loads(line)
        icon_id = item.get("icon_id")
        if not isinstance(icon_id, str) or icon_id in manifest:
            raise ValueError(f"duplicate/invalid manifest ID: {icon_id}")
        manifest[icon_id] = item

    annotations = {}
    stats = Counter()
    input_tokens = output_tokens = 0
    batch_usd = Decimal(0)
    for line in annotation_path.open(encoding="utf-8"):
        row = json.loads(line)
        icon_id = row.get("icon_id")
        if icon_id in annotations or icon_id not in manifest:
            raise ValueError(f"duplicate/unknown annotation ID: {icon_id}")
        source = manifest[icon_id]
        for field in ("source_key", "source_blob_sha256", "preview_sha256"):
            if row.get(field) != source.get(field):
                raise ValueError(f"annotation input mismatch: {icon_id}/{field}")
        preview = run / "previews" / f"{icon_id}.png"
        if sha256(preview) != source.get("preview_sha256"):
            raise ValueError(f"annotation preview changed: {icon_id}")
        annotation = row.get("annotation")
        expected = set(LIST_FIELDS + TEXT_FIELDS + OPTIONAL_TEXT_FIELDS
                       + ("same_motif_across_renditions",))
        if not isinstance(annotation, dict) or set(annotation) != expected:
            raise ValueError(f"annotation fields mismatch: {icon_id}")
        if any(not isinstance(annotation[field], str) or not annotation[field].strip()
               for field in TEXT_FIELDS):
            raise ValueError(f"blank/non-text description or composition: {icon_id}")
        if any(annotation[field] is not None and (not isinstance(annotation[field], str)
               or not annotation[field].strip()) for field in OPTIONAL_TEXT_FIELDS):
            raise ValueError(f"invalid optional text: {icon_id}")
        if any(not isinstance(annotation[field], list) or any(
                not isinstance(value, str) or not value.strip() for value in annotation[field])
               for field in LIST_FIELDS):
            raise ValueError(f"invalid observation list: {icon_id}")
        keywords = annotation["keywords"]
        if not 4 <= len(keywords) <= 8 or annotation["same_motif_across_renditions"] != "not_applicable":
            raise ValueError(f"keyword count or motif flag invalid: {icon_id}")
        if len({keyword.casefold().strip() for keyword in keywords}) != len(keywords):
            stats["duplicate_keywords_within_icon"] += 1
        stats["non_lowercase_keywords"] += sum(keyword != keyword.lower() for keyword in keywords)
        stats["icons_with_uncertainties"] += bool(annotation["uncertainties"])
        stats["icons_with_visible_text"] += annotation["visible_text"] is not None
        stats["checkerboard_leaks"] += bool(re.search(
            r"checkerboard|checkered background", annotation["description"] + " "
            + " ".join(keywords), re.I))
        stats["description_mentions_ui_or_game"] += bool(re.search(
            r"\b(?:UI|game|skill|equipment)\b", annotation["description"], re.I))
        usage = row.get("usage", {})
        input_tokens += usage.get("input_tokens", 0)
        output_tokens += usage.get("output_tokens", 0)
        batch_usd += Decimal(row.get("estimated_batch_usd", "0"))
        annotations[icon_id] = annotation

    if (set(annotations) != set(manifest) or len(annotations) != plan.get("request_count")
            or len(annotations) != metering.get("completed_icons") or metering.get("failed_icons")
            or input_tokens != metering.get("input_tokens")
            or output_tokens != metering.get("output_tokens")
            or batch_usd != Decimal(metering.get("estimated_batch_usd", "0"))):
        raise ValueError("annotation coverage or metering mismatch")

    effective = annotations
    reviewed_terms: dict[str, list[str]] | None = None
    review_chain = []
    review_info = None
    for review_path in reviews:
        effective, reviewed_terms, review_info = apply_review(
            effective, manifest, raw_sha256, review_path, reviewed_terms, review_info)
        review_chain.append(review_info)
    reviewed_terms = reviewed_terms or {}
    accepted = accepted_sha256(effective, reviewed_terms)
    if review_info is not None and review_info["accepted_annotation_sha256"] != accepted:
        raise ValueError("accepted annotation digest mismatch")
    return {
        "annotations": effective,
        "raw_annotations": annotations,
        "reviewed_terms": reviewed_terms,
        "manifest": manifest,
        "plan": plan,
        "metering": metering,
        "stats": dict(stats),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_batch_usd": str(batch_usd),
        "raw_annotations_sha256": raw_sha256,
        "accepted_annotations_sha256": accepted,
        "review_chain": review_chain,
    }
