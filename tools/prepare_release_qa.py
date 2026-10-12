"""Prepare bounded image-only alternatives and untouched automated acceptance cases."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

from automated_search_qa import body, image_input, result_for, MODEL
from evaluate_search_v2 import sha256, write_new, load_benchmark, evaluate
from metered_calibration import PRICE_PER_MILLION

PACKAGE = Path(__file__).resolve().parents[1]
STRINGS = {"type": "array", "items": {"type": "string"}}
ALTERNATIVE_SCHEMA = {"type": "object", "additionalProperties": False,
    "required": ["terms", "uncertainties"], "properties": {"terms": STRINGS, "uncertainties": STRINGS}}
ALTERNATIVE_PROMPT = """Observe this small schematic game icon. Supply 2-8 concise lowercase
search labels or phrases grounded in the visible artwork. Lead with recognizable
object/effect names, not tiny incidental details. Preserve multiple common names:
if an abstract shape reasonably reads as two objects, include both plausible
readings, with the ambiguity explained under uncertainties. Synonyms such as
orb/sphere, cuff/bracer, wisps/smoke are useful. Bind distinctive visible modifiers
to their object where possible. Do not force alternatives on an unambiguous image.
Do not invent lore, hidden material, abilities, names, text, or invisible objects.
Terms are retrieval hypotheses, not asserted hard facets. Each term <=80 characters.
Do not describe a checkerboard transparency preview as part of the icon."""
AUTHOR_SCHEMA = {"type": "object", "additionalProperties": False,
    "required": ["text", "required", "optional", "metaphor"], "properties": {
        "text": {"type": "string"}, "required": STRINGS, "optional": STRINGS,
        "metaphor": {"type": "string"}}}
AUTHOR_PROMPT = """Author ONE realistic icon-search request from these images, without
using filenames or catalog metadata. Image 1 is an example of a suitable target.
The supplied family determines the request: literal = visual object/effect plus
distinctive attributes; seed_modification = an alternative to Image 2, describing
the visible change represented by Image 1; functional = an ordinary game item or
ability purpose with a visual cue that Image 1 can reasonably symbolize.
Write natural English, typically 5-14 words, never FTS syntax. Identify 1-3 required
visible properties and optional details separately. Do not require an uncertain
count, tiny decoration or guessed material. Accept plausible alternate readings
of schematic art. State the accepted metaphor for functional cases. The target
must satisfy every required property. Required properties must stand alone:
name the target's visible attributes, not 'more X than the seed'. Do not
reverse-engineer search keywords."""


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(package: Path) -> dict:
    with sqlite3.connect((package.resolve() / "catalog.sqlite").as_uri() + "?mode=ro", uri=True) as db:
        return {x[0]: {"icon_id": x[0], "collection": x[1], "path": x[2], "sha256": x[3]}
                for x in db.execute("SELECT i.icon_id,i.collection,d.relative_path,d.sha256 "
                                    "FROM icon i JOIN derivative d USING(icon_id)")}


def ordered(ids, salt):
    return sorted(ids, key=lambda x: hashlib.sha256((salt + x).encode()).digest())


def freeze(output: Path, mode: str, requests: list, metadata: dict) -> None:
    if output.exists():
        raise ValueError("QA output must be new")
    output.mkdir(parents=True)
    items = []
    for key, payload, details in requests:
        path = output / "requests" / (key + ".json")
        write_new(path, payload)
        items.append({"id": key, "sha256": sha256(path), **details})
    write_new(output / "plan.json", {"mode": mode, "model": MODEL, "effort": "high",
        "requests": items, "max_output_tokens": 4096, "max_attempts": 2,
        "standard_price_per_million_usd": {k: str(v) for k, v in PRICE_PER_MILLION.items()},
        "pricing_date": "2026-10-11", **metadata})
    print(json.dumps({"prepared": len(items), "mode": mode}), flush=True)


def exposed_ids() -> set:
    dev = read(PACKAGE / "work/search-retrieval-v2/development-benchmark-v1.json")
    v4 = read(PACKAGE / "work/full-annotation-gpt6-sol-high-v1/SEARCH_BENCHMARK_V4.json")
    return {x for case in dev["cases"] for x in case["known_suitable_ids"]} | {
        case["icon_id"] for case in v4["cases"]} | {
        case["request"]["like"] for case in dev["cases"] if case["request"].get("like")}


def prepare_alternatives(package: Path, output: Path) -> None:
    icons = rows(package)
    v4 = read(PACKAGE / "work/full-annotation-gpt6-sol-high-v1/SEARCH_BENCHMARK_V4.json")
    difficult = [v4["cases"][i - 1]["icon_id"] for i in (3,14,16,22,24,25,26,27,30,33,34,39,43,47)]
    dev = read(PACKAGE / "work/search-retrieval-v2/v1-development-ranked.json")
    judgments = read(PACKAGE / "work/search-retrieval-v2/v1-development-judgments.json")
    failed = {x["case_id"] for x in judgments["cases"] if x["outcome"] == "no_useful_hit"}
    difficult += [x for case in dev["cases"] if case["case_id"] in failed for x in case["known_suitable_ids"]]
    difficult = list(dict.fromkeys(difficult))[:30]
    if len(difficult) != 30:
        raise ValueError("expected 30 unique diagnosed difficult icons")
    controls, seen = [], set()
    for key in ordered(set(icons) - exposed_ids(), "alternative-controls-v1"):
        if icons[key]["collection"] not in seen:
            controls.append(key)
            seen.add(icons[key]["collection"])
        if len(controls) == 70:
            break
    if len(controls) != 70:
        raise ValueError("not enough untouched collections")
    requests = []
    for key in difficult + controls:
        item = icons[key]
        requests.append((key, body(ALTERNATIVE_PROMPT, [image_input(package / item["path"], item["sha256"])],
                                   ALTERNATIVE_SCHEMA), {"icon_id": key,
            "thumbnail_sha256": item["sha256"], "stratum": "difficult" if key in difficult else "representative"}))
    freeze(output, "alternatives", requests, {"catalog_sqlite_sha256": sha256(package / "catalog.sqlite"),
        "selection": "30 exposed difficult IDs and 70 hash-ranked untouched distinct-collection controls",
        "purpose": "additive labels; original descriptions/facets unchanged; no query text supplied"})


def finish_alternatives(output: Path) -> None:
    plan = read(output / "plan.json")
    run = PACKAGE / "work/full-annotation-gpt6-sol-high-v1"
    manifest = {x["icon_id"]: x for x in map(json.loads, (run / "icons.jsonl").read_text(encoding="utf-8").splitlines())}
    prior = {}
    for layer in (1, 2):
        for item in read(run / f"REVIEWED_CORRECTIONS_V{layer}.json")["items"]:
            prior.setdefault(item["icon_id"], set()).update(item.get("add_search_terms", []))
    items = []
    for request in plan["requests"]:
        value = result_for(output, request)
        terms, uncertainties = value["terms"], value["uncertainties"]
        # Prompt targets 2-8; retain a small overrun instead of dropping alternate readings.
        if (not 2 <= len(terms) <= 10 or len(terms) != len(set(terms)) or
                any(not isinstance(x, str) or not x.strip() or x != x.casefold() or len(x) > 80 for x in terms)
                or any(not isinstance(x, str) or not x.strip() for x in uncertainties)):
            raise ValueError("invalid bounded alternative labels")
        key = request["icon_id"]
        items.append({"icon_id": key, "preview_sha256": manifest[key]["preview_sha256"],
            "reason": "Automated image-grounded alternative readings; source QA plan sha256:" + sha256(output / "plan.json"),
            "add_search_terms": [x for x in terms if x not in prior.get(key, set())],
            "add_uncertainties": uncertainties})
    write_new(output / "REVIEWED_ALTERNATIVES_V3.json", {"review_schema_version": 1,
        "source_annotations_sha256": sha256(run / "annotations.jsonl"),
        "base_review_sha256": sha256(run / "REVIEWED_CORRECTIONS_V2.json"),
        "review_method": "GPT-6 Sol High image-only API additive alternatives; automated schema/hash checks; development-tested",
        "items": items})
    print(json.dumps({"reviewed_icons": len(items), "terms": sum(len(x["add_search_terms"]) for x in items)}))


def prepare_author(package: Path, alternatives: Path, output: Path) -> None:
    icons = rows(package)
    excluded = exposed_ids() | {x["icon_id"] for x in read(alternatives / "plan.json")["requests"]}
    for version in (1, 2, 3):
        historical = read(PACKAGE / f"work/full-annotation-gpt6-sol-high-v1/SEARCH_BENCHMARK_V{version}.json")
        excluded.update(case["icon_id"] for case in historical["cases"])
    targets, seen = [], set()
    for key in ordered(set(icons) - excluded, "acceptance-targets-2026-10-11-v1"):
        if icons[key]["collection"] not in seen:
            targets.append(key)
            seen.add(icons[key]["collection"])
        if len(targets) == 50:
            break
    if len(targets) != 50:
        raise ValueError("insufficient distinct untouched target collections")
    requests = []
    for i, key in enumerate(targets):
        family = "literal" if i < 25 else "seed_modification" if i < 40 else "functional"
        content = [{"type": "input_text", "text": "Family: " + family + ". Image 1 (suitable target):"},
                   image_input(package / icons[key]["path"], icons[key]["sha256"])]
        details = {"family": family, "target": key, "target_sha256": icons[key]["sha256"]}
        if family == "seed_modification":
            seeds = [x for x in icons if x != key and x not in excluded and x not in targets
                     and icons[x]["collection"] == icons[key]["collection"]]
            seed = ordered(seeds, "acceptance-seed-" + key)[0]
            details["seed"] = seed
            content.extend([{"type": "input_text", "text": "Image 2 (seed to find an alternative to):"},
                            image_input(package / icons[seed]["path"], icons[seed]["sha256"])])
        requests.append((f"acceptance-{i+1:03d}", body(AUTHOR_PROMPT, content, AUTHOR_SCHEMA), details))
    freeze(output, "author", requests, {"catalog_sqlite_sha256": sha256(package / "catalog.sqlite"),
        "candidate_profile_manifest_sha256": sha256(package / "manifests/search-profile.json"),
        "selection": "50 SHA-256-ranked distinct-collection targets excluding V1-V4/development/trial IDs"})


def finish_author(package: Path, output: Path, audit_output: Path) -> None:
    plan = read(output / "plan.json")
    if sha256(package / "catalog.sqlite") != plan["catalog_sqlite_sha256"]:
        raise ValueError("candidate changed after authoring freeze")
    icons, cases, requests = rows(package), [], []
    for item in plan["requests"]:
        authored = result_for(output, item)
        if not 1 <= len(authored["required"]) <= 3 or not authored["text"].strip():
            raise ValueError("author must supply a request and 1-3 required visual properties")
        request = {"text": authored["text"], "limit": 20}
        if item.get("seed"):
            request.update({"like": item["seed"], "except": [item["seed"]]})
        case = {"case_id": item["id"], "family": item["family"], "request": request,
            "required_visual_properties": authored["required"], "optional_visual_properties": authored["optional"],
            "known_suitable_ids": [item["target"]], "notes": authored["metaphor"]}
        cases.append(case)
        from automated_search_qa import judge_request
        icon = icons[item["target"]]
        audit = {**case, "results": [{"icon_id": item["target"], "thumbnail_relative_path": icon["path"],
                                       "thumbnail_sha256": icon["sha256"]}]}
        payload, mapping = judge_request(audit, package)
        requests.append((item["id"], payload, {"mapping": mapping}))
    benchmark = {"benchmark_schema_version": 2, "set_kind": "acceptance_positive",
        "author": "gpt-6-sol high; stateless image-only API",
        "exposure": "Candidate frozen before authoring; author saw target/seed images only; same-model audit/judge; no human independence claimed",
        "cases": cases}
    write_new(output / "benchmark.json", benchmark)
    load_benchmark(output / "benchmark.json")
    freeze(audit_output, "audit", requests, {"benchmark_sha256": sha256(output / "benchmark.json"),
        "catalog_sqlite_sha256": plan["catalog_sqlite_sha256"]})


def seal(package: Path, author: Path, audit: Path, output: Path) -> None:
    plan = read(audit / "plan.json")
    if (plan["benchmark_sha256"] != sha256(author / "benchmark.json") or
            plan["catalog_sqlite_sha256"] != sha256(package / "catalog.sqlite")):
        raise ValueError("candidate or benchmark changed before sealing")
    rejected = []
    for item in plan["requests"]:
        labels = result_for(audit, item)["candidates"]
        if len(labels) != 1 or labels[0]["number"] != 1 or labels[0]["label"] != "useful":
            rejected.append({"case_id": item["id"], "labels": labels})
    if rejected:
        write_new(audit / "target-audit-failures.json", rejected)
        raise ValueError(f"{len(rejected)} authored targets need pre-retrieval repair; no acceptance search run")
    positive = load_benchmark(author / "benchmark.json")
    if len(plan["requests"]) != 50:
        raise ValueError("target audit must cover all 50 cases")
    icons = rows(package)
    collections = sorted({x["collection"] for x in icons.values()})[:5]
    cases = [{"case_id": f"negative-{i+1:03d}", "family": "exclusion_negative",
              "request": {"collection": name, "except": sorted(key for key, value in icons.items()
                          if value["collection"] == name), "limit": 20},
              "required_visual_properties": [], "optional_visual_properties": [], "known_suitable_ids": [],
              "notes": "Every icon in the selected collection is explicitly excluded."}
             for i, name in enumerate(collections)]
    with sqlite3.connect((package.resolve() / "catalog.sqlite").as_uri() + "?mode=ro", uri=True) as db:
        subjects, colors = {}, {}
        for key, namespace, value in db.execute("SELECT icon_id,namespace,value FROM icon_keyword WHERE namespace IN ('subject','color')"):
            (subjects if namespace == "subject" else colors).setdefault(value, set()).add(key)
        for subject in sorted(subjects):
            for color in sorted(colors):
                if subjects[subject].isdisjoint(colors[color]):
                    request = {"require": {"subject": [subject], "color": [color]}, "limit": 20}
                    # Alias-aware execution below is the final truth, not this raw-set prefilter.
                    from iconctl import run_search_request
                    db.row_factory = sqlite3.Row
                    if run_search_request(db, request)["returned_count"]:
                        continue
                    cases.append({"case_id": f"negative-{len(cases)+1:03d}", "family": "exclusion_negative",
                                  "request": request, "required_visual_properties": [], "optional_visual_properties": [],
                                  "known_suitable_ids": [], "notes": "Both facet values exist independently; their conjunction is absent."})
                    break
            if len(cases) == 10:
                break
    write_new(output / "negative-benchmark.json", {"benchmark_schema_version": 2,
        "set_kind": "acceptance_negative", "author": "deterministic contract generator",
        "exposure": "Negative cases generated and verified before sealing; no positive results inspected", "cases": cases})
    load_benchmark(output / "negative-benchmark.json")
    write_new(output / "acceptance-seal.json", {"catalog_sqlite_sha256": sha256(package / "catalog.sqlite"),
        "benchmark_sha256": sha256(author / "benchmark.json"),
        "negative_benchmark_sha256": sha256(output / "negative-benchmark.json"),
        "author_plan_sha256": sha256(author / "plan.json"), "audit_plan_sha256": sha256(audit / "plan.json"),
        "target_audit_passed": 50, "threshold": "40/50 positive; 10/10 negative; zero contract violations",
        "limitations": "Automated same-model author/audit/judge, not independent human review"})
    for kind, path in (("positive", author / "benchmark.json"), ("negative", output / "negative-benchmark.json")):
        write_new(output / (kind + "-ranked.json"), evaluate(package, path))
    print(json.dumps({"sealed_and_evaluated": 50, "negatives": 10}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("alternatives", "finish-alternatives", "author", "finish-author", "seal"))
    parser.add_argument("--package", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--alternatives", type=Path)
    parser.add_argument("--audit-output", type=Path)
    parser.add_argument("--author", type=Path)
    args = parser.parse_args()
    if args.command == "alternatives":
        prepare_alternatives(args.package, args.output)
    elif args.command == "finish-alternatives":
        finish_alternatives(args.output)
    elif args.command == "author":
        prepare_author(args.package, args.alternatives, args.output)
    elif args.command == "finish-author":
        finish_author(args.package, args.output, args.audit_output)
    else:
        seal(args.package, args.author, args.audit_output, args.output)


if __name__ == "__main__":
    main()
