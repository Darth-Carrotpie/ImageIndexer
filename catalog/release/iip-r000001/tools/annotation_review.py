"""Apply preview-pinned visual corrections without changing raw model results."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def apply_review(annotations: dict[str, dict], manifest: dict[str, dict],
                 raw_sha256: str, review_path: Path,
                 prior_terms: dict[str, list[str]] | None = None,
                 prior_info: dict | None = None) -> tuple[dict[str, dict], dict[str, list[str]], dict]:
    if (prior_terms is None) != (prior_info is None):
        raise ValueError("prior review metadata and search terms must be supplied together")
    review_bytes = review_path.read_bytes()
    review = json.loads(review_bytes)
    if (not isinstance(review, dict) or review.get("review_schema_version") != 1
            or review.get("source_annotations_sha256") != raw_sha256
            or review.get("base_review_sha256") != (prior_info["review_sha256"] if prior_info else None)
            or not isinstance(review.get("review_method"), str)
            or not review["review_method"].strip()
            or not isinstance(review.get("items"), list) or not review["items"]):
        raise ValueError("review manifest schema, raw annotation hash, or base review mismatch")

    effective = annotations.copy()
    search_terms: dict[str, list[str]] = {icon_id: terms.copy()
                                           for icon_id, terms in (prior_terms or {}).items()}
    seen = set()
    required = {"icon_id", "preview_sha256", "reason"}
    optional = {"description", "visible_text", "add_uncertainties", "add_search_terms", "remove_keywords",
                "move_visible_text_to_uncertainties"}
    for item in review["items"]:
        if not isinstance(item, dict) or not required <= item.keys() or item.keys() - required - optional:
            raise ValueError("invalid review item fields")
        icon_id = item["icon_id"]
        if (not isinstance(icon_id, str) or icon_id in seen
                or icon_id not in annotations or icon_id not in manifest
                or item["preview_sha256"] != manifest[icon_id]["preview_sha256"]
                or not isinstance(item["reason"], str) or not item["reason"].strip()
                or not optional.intersection(item)):
            raise ValueError("duplicate, unpinned, or empty review item")
        seen.add(icon_id)
        current = annotations[icon_id].copy()
        current["uncertainties"] = current["uncertainties"].copy()
        current["keywords"] = current["keywords"].copy()
        if "description" in item:
            if not isinstance(item["description"], str) or not item["description"].strip():
                raise ValueError("review description must be nonblank")
            current["description"] = item["description"]
        if "visible_text" in item:
            if item["visible_text"] is not None and (not isinstance(item["visible_text"], str)
                                                    or not item["visible_text"].strip()):
                raise ValueError("review visible text must be literal text or null")
            current["visible_text"] = item["visible_text"]
        if "move_visible_text_to_uncertainties" in item:
            if (item["move_visible_text_to_uncertainties"] is not True
                    or "visible_text" in item or not isinstance(current["visible_text"], str)
                    or not current["visible_text"].strip()):
                raise ValueError("cannot move absent or overwritten visible text")
            if current["visible_text"] not in current["uncertainties"]:
                current["uncertainties"].append(current["visible_text"])
            current["visible_text"] = None
        additions = item.get("add_uncertainties", [])
        if (not isinstance(additions, list) or any(not isinstance(value, str)
                or not value.strip() for value in additions)):
            raise ValueError("invalid review uncertainty")
        for value in additions:
            if value not in current["uncertainties"]:
                current["uncertainties"].append(value)
        removed = item.get("remove_keywords", [])
        if (not isinstance(removed, list) or any(not isinstance(value, str)
                or value not in current["keywords"] for value in removed)
                or len(set(removed)) != len(removed)):
            raise ValueError("review keyword removal does not match raw annotation")
        for value in removed:
            current["keywords"].remove(value)
        if len(current["keywords"]) < 4:
            raise ValueError("review removed too many model keywords")
        terms = item.get("add_search_terms", [])
        if (not isinstance(terms, list) or any(not isinstance(term, str) or not term.strip()
                or term != term.casefold() or len(term) > 80 for term in terms)
                or len(set(terms)) != len(terms)):
            raise ValueError("invalid reviewed search terms")
        if terms:
            if set(terms) & set(search_terms.get(icon_id, [])):
                raise ValueError("review search term duplicates an earlier review")
            search_terms.setdefault(icon_id, []).extend(terms)
        effective[icon_id] = current

    accepted = hashlib.sha256()
    for icon_id in sorted(effective):
        row = {"icon_id": icon_id, "annotation": effective[icon_id],
               "reviewed_search_terms": search_terms.get(icon_id, [])}
        accepted.update(json.dumps(row, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")).encode("utf-8") + b"\n")
    info = {"review_sha256": hashlib.sha256(review_bytes).hexdigest(),
            "accepted_annotation_sha256": accepted.hexdigest(),
            "reviewed_icons": len(seen),
            "reviewed_search_terms": sum(map(len, search_terms.values()))}
    return effective, search_terms, info
