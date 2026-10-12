"""Package the fixed-corpus beta only after its automated acceptance gate passes."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile

from catalog_revision import canonical, catalog_revision, digest
from evaluate_search_v2 import score, sha256
from iconctl import open_catalog, run_search_request
from validate_catalog import validate

SOURCE = Path(__file__).resolve().parents[1]
FILES = ("iconctl.py", "USAGE.md", "INSTALLATION_AND_REQUIREMENTS.md", "DEPLOYMENT.md",
         "INGESTION.md", "tools/validate_catalog.py", "tools/deploy_catalog.py",
         "tools/catalog_revision.py", "tools/build_search_candidate.py",
         "tools/annotation_data.py", "tools/annotation_review.py",
         "agent-skill/indexed-icon-pack/SKILL.md", "agent-skill/indexed-icon-pack-ingest/SKILL.md")


def acceptance_evidence(candidate: Path, qa: Path) -> dict:
    evidence = {}
    for kind in ("positive", "negative"):
        folder = qa / ("acceptance-" + kind)
        actual = score(folder / "ranked.json", folder / "judgments.json")
        saved = json.loads((folder / "score.json").read_text(encoding="utf-8"))
        ranked = json.loads((folder / "ranked.json").read_text(encoding="utf-8"))
        if saved != actual or ranked["catalog_sqlite_sha256"] != sha256(candidate / "catalog.sqlite"):
            raise ValueError("acceptance evidence changed or belongs to another candidate")
        if actual["contract_violations"]:
            raise ValueError("acceptance contract violations block packaging")
        if ranked.get("benchmark_set_kind") != "acceptance_" + kind:
            raise ValueError("only sealed acceptance evidence can gate packaging")
        if kind == "positive" and {name: values["cases"] for name, values in actual["by_family"].items()} != {
                "literal": 25, "seed_modification": 15, "functional": 10}:
            raise ValueError("positive acceptance allocation must remain 25/15/10")
        if kind == "positive" and (actual["positive_cases"] != 50 or actual["useful_hit_at_5"] < 40):
            raise ValueError("positive acceptance requires at least 40/50 useful results")
        if kind == "negative" and (actual["negative_cases"] != 10 or actual["negative_successes"] != 10
                                  or any(case["returned_count"] for case in ranked["cases"])):
            raise ValueError("negative acceptance requires 10/10 truthful empty results")
        evidence[kind] = actual
    seal = json.loads((qa / "acceptance-seal.json").read_text(encoding="utf-8"))
    if (seal["catalog_sqlite_sha256"] != sha256(candidate / "catalog.sqlite")
            or seal["benchmark_sha256"] != evidence["positive"]["benchmark_sha256"]
            or seal["negative_benchmark_sha256"] != evidence["negative"]["benchmark_sha256"]
            or seal["target_audit_passed"] != 50):
        raise ValueError("acceptance seal/audit mismatch")
    evidence["seal"] = seal
    return evidence


def build(candidate: Path, qa: Path, output: Path) -> dict:
    candidate, qa, output = candidate.resolve(strict=True), qa.resolve(strict=True), output.resolve()
    if output.exists() or output.name != "iip-r000001":
        raise ValueError("first-release output must be a new iip-r000001 directory")
    if (candidate / "manifests/release.json").exists():
        raise ValueError("builder accepts an unpublished candidate only")
    evidence = acceptance_evidence(candidate, qa)
    errors = validate(candidate)
    if errors:
        raise ValueError("candidate validation failed: " + "; ".join(errors[:3]))
    profile = json.loads((candidate / "manifests/search-profile.json").read_text(encoding="utf-8"))
    for name, expected in profile["profile"]["implementation_sha256"].items():
        if name not in FILES or sha256(SOURCE / name) != expected:
            raise ValueError("search implementation no longer matches accepted profile")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".iip-r000001-building-", dir=output.parent))
    # Leave a failed stage for diagnosis; never alter a prior release or candidate.
    for folder in ("assets", "thumbnails", "manifests"):
        source = candidate / folder
        if source.exists():
            if any(x.is_symlink() for x in source.rglob("*")):
                raise ValueError("candidate contains symlink")
            shutil.copytree(source, stage / folder)
    shutil.copyfile(candidate / "catalog.sqlite", stage / "catalog.sqlite")
    for name in FILES:
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / name, target)
    shutil.copyfile(SOURCE / "RELEASE_README.md", stage / "README.md")
    (stage / "qa").mkdir()
    (stage / "qa/acceptance.json").write_bytes(canonical(evidence) + b"\n")
    shutil.copyfile(qa / "FINAL_SEARCH_REPORT.md", stage / "qa/FINAL_SEARCH_REPORT.md")
    db, _, _ = open_catalog(candidate)
    try:
        seed = run_search_request(db, {"text": "gold key", "limit": 1})["results"][0]["icon_id"]
        requests = [{"text": "gold key", "limit": 5},
                    {"like": seed, "except": [seed], "limit": 5},
                    {"query": "subject:key", "require": {"color": ["gold", "golden"]}, "limit": 5}]
        fixtures = []
        for request in requests:
            response = run_search_request(db, request)
            fixtures.append({"request": request, "expected_ids": [x["icon_id"] for x in response["results"]],
                             "returned_count": response["returned_count"], "shortfall": response["shortfall"]})
        (stage / "qa/consumer-fixtures.json").write_bytes(canonical({"schema_version": 1,
            "purpose": "language-neutral POST /api/v1/search parity fixtures", "cases": fixtures}) + b"\n")
    finally:
        db.close()
    with closing(sqlite3.connect(stage / "catalog.sqlite")) as db:
        revision, inputs = catalog_revision(stage, db)
        schema = db.execute("PRAGMA user_version").fetchone()[0]
        if schema != 2:
            raise ValueError("initial beta requires schema v2")
    (stage / "manifests/catalog-revision.json").write_bytes(canonical(inputs) + b"\n")
    ledger = (stage / "manifests/icon-identities.jsonl").read_bytes()
    payload = [{"path": path.relative_to(stage).as_posix(), "size": path.stat().st_size,
                "sha256": "sha256:" + sha256(path)}
               for path in sorted(stage.rglob("*")) if path.is_file()]
    payload.sort(key=lambda item: item["path"])
    manifest = {"manifest_schema_version": 1, "catalog_id": "indexed-icon-pack",
        "release_id": "iip-r000001", "schema_version": schema, "catalog_revision": revision,
        "predecessor_release_id": None, "predecessor_release_manifest_sha256": None,
        "identity_registry_sha256": digest(ledger),
        "identity_event_range": {"first": 1, "last": len(ledger.splitlines())},
        "search_profile_sha256": "sha256:" + profile["search_profile_sha256"],
        "release_channel": "field-test", "payload": payload}
    (stage / "manifests/release.json").write_bytes(canonical(manifest) + b"\n")
    errors = validate(stage)
    if errors:
        raise ValueError("release validation failed: " + "; ".join(errors[:5]))
    if stage.resolve().parent != output.parent or output.exists():
        raise ValueError("release destination changed")
    os.rename(stage, output)
    result = {"release_id": manifest["release_id"], "catalog_revision": revision,
              "release_manifest_sha256": "sha256:" + sha256(output / "manifests/release.json"),
              "payload_files": len(payload), "payload_bytes": sum(x["size"] for x in payload)}
    print(json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--qa", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.candidate, args.qa, args.output)
