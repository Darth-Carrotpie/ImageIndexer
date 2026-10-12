# Indexed Icon Pack v1 - Implementation Plan

## 1. Objective

Build a self-contained external icon catalog that can sit beside any repository, be searched and used by an agent during development, and be mounted read-only by a deployed application for agent or human icon selection.

This plan adopts the exploration's recommended hybrid: external ordinary image
files, a portable SQLite/FTS5 metadata catalog, one Python CLI used by a thin
agent skill, and an optional read-only browser/API exposed by that same CLI.

The smallest complete design is:

- original PNG files stored as ordinary files, not SQLite BLOBs;
- one SQLite catalog with FTS5;
- permanent logical icon IDs plus SHA-256 hashes for exact renditions;
- build-time generated descriptions and structured keywords;
- a standard-library Python CLI and read-only HTTP service;
- a small static browser plus separate consumer and maintainer agent skills;
- a repeatable ingestion workflow for adding or updating icon sets;
- no vector database, server database, JavaScript framework, or runtime vision dependency.

The owner approved starting deterministic implementation on 2026-10-08, then
selected GPT-6 Sol High and authorized the 100-icon pilot. That pilot is now
approved; see its [report](work/pilot-gpt6-sol-high-v2/PILOT_REPORT.md). The
plan's original GPT-6.1 Sol recommendation is historical. The full annotation
run was approved and completed on 2026-10-09; publication remains a separate
gate. The initial 6,250 IDs are pinned by
the [pre-release freeze](work/identity-freeze-v1/README.md); the
[metered calibration](CALIBRATION.md) is complete. See the
[full-run validation report](work/full-annotation-gpt6-sol-high-v1/VALIDATION_REPORT.md)
for the remaining search-quality work.

Owner finishing authorization, 2026-10-11: execute
[search-plan Section 8](SEARCH_RETRIEVAL_IMPLEMENTATION_PLAN.md#8-automated-initial-release-finishing-pass-owner-authorization-2026-10-11).
For the fixed-corpus initial field test, acceptance is 40/50 (80%) useful
positive cases, 10 truthful negatives and zero contract violations, all judged
automatically. No independent manual reviewer is required. Preserve literal
captions plus image-grounded alternate readings and uncertainty. GPT-6 Sol High
API execution is authorized within the recorded finishing envelope; pause for
a session-model swap only when the API path cannot perform the needed run.
General successor ingestion and publication-head promotion are deferred beyond
this first local field-test package; the Phase 7/8 successor gates remain
mandatory before r000002. Stable identity, payload integrity, clean relocation,
materialization, and isolated activation/rollback tests are not deferred.

## 2. Confirmed inputs and constraints

- Initial source corpus: 127 collections, 6,250 apparent logical icons, and 10,200 PNG renditions.
- Source PNG size: approximately 2.96 GiB.
- PNG header scan: 10,050 renditions fit within 512 x 512 pixels;
  150 exceed that size (149 are 1024 x 1024).
- Variant structure: 3,950 apparent background/transparent pairs and 2,300 single-rendition icons.
- Exact content: 10,193 unique SHA-256 hashes; seven duplicate hash groups remain as source aliases.
- Source names identify collection and ordinal but not the pictured subject.
- Some Halloween variants are duplicated or ordinally permuted, so filename-based pairing is only a candidate relationship.
- One achievement image is 1023 x 1024 instead of the expected 1024 x 1024.
- Internal indexing permission has been confirmed by the project owner through email.
- The completed catalog is an external package. Consumer repositories receive
  only selected icons, stable handles, or exact pins.
- No absolute workstation paths may be written to the database, manifests, receipts, skill, or documentation.
- `catalog_id` and every published `icon_id` are permanent across releases and deployments.
- Released IDs are never regenerated, rebound, deleted, or reused; removals become tombstones.
- Stable handles may follow the current preferred rendition of the same logical
  icon. Exact rendition pins never float to different bytes.
- Update builds require the previous identity registry and never mutate a published release in place.

## 3. Architecture

```text
source PNGs
                 |
                 v
       deterministic scanner
        |        |         |
        |        |         +--> thumbnails
        |        +------------> annotation jobs
        +---------------------> exact manifest
                                      |
                                      v
                          SQLite tables + FTS5
                             |              |
                             v              v
                        Python CLI    read-only API/browser
                             |              |
                             +-------> stable handle, exact pin,
                                      or verified copy
```

### 3.1 Authority and derivation

- Source PNG bytes and the release manifest are durable evidence.
- The append-only icon identity registry is the authority for every published
  `icon_id`; source paths, hashes, and scan order never regenerate identity.
- Image-input LLM annotations are durable, versioned catalog data with generator provenance. Scripts may prepare inputs, validate outputs, and import them, but must not invent visual descriptions or keywords.
- `catalog.sqlite`, FTS5 rows, and thumbnails are reproducible build outputs.
- A SQLite file hash is not the logical catalog revision because equivalent databases can have different page layouts. `catalog_revision` is SHA-256 over a canonical, sorted digest record of the identity registry, logical catalog manifest, approved annotation set, and source/provenance metadata. It is finalized only after annotation import; it excludes release packaging and volatile build facts.
- `release_id` labels an immutable packaged release. `release.json` binds it to `catalog_revision`, catalog and manifest schema versions, predecessor, and a sorted inline inventory of payload sizes and SHA-256 hashes. The SHA-256 of that finalized manifest is the exact release-manifest digest used by external pointers. A packaging-only rebuild may have a new `release_id` but the same logical `catalog_revision`.
- Each successor release carries every prior identity, tombstone, and published
  rendition blob so existing stable handles and exact pins remain resolvable.
- The icon catalog owns visual discovery metadata. It does not own a consumer's assignment or publication state.

### 3.2 Permanent identity and release identity

1. `catalog_id` identifies this catalog lineage and never changes.
2. `pack_id` permanently identifies one ingested icon set.
3. `icon_id` permanently identifies one logical icon across its renditions and releases.
4. `sha256:<hex>` identifies one exact file's bytes.
5. `catalog_revision` identifies one immutable logical catalog state, not an icon or deployment.
6. `release_id` is a monotonic, never-reused label (`iip-r000001`, then `iip-r000002`, etc.) for an exact packaged release in this catalog lineage.
7. `schema_version` is the reader-compatibility contract; a consumer rejects an unsupported version instead of guessing.

`icon_id` uses `icon_<lowercase UUIDv4>` and is minted once in a reviewed ingest
plan. Paths, filenames, ordinals, annotations, hashes, and input order are
metadata, not identity. The saved registry, rather than re-running an ID
formula, is authoritative after first publication.

## 4. Final delivery layout

```text
IndexedIconPack_v1/
  README.md
  IMPLEMENTATION_PLAN.md
  INSTALLATION_AND_REQUIREMENTS.md
  USAGE.md
  INGESTION.md
  DEPLOYMENT.md
  CONCEPT_ONE_PAGER.md
  catalog.sqlite
  iconctl.py
  assets/
    sha256/<first-two-hex>/<full-sha256>.png
  thumbnails/
    <icon-id>.png
  manifests/
    release.json
    icon-identities.jsonl
    catalog.jsonl
    annotations.jsonl
    anomalies.json
  browser/
    index.html
    app.js
    styles.css
  agent-skill/
    indexed-icon-pack/
      SKILL.md
    indexed-icon-pack-ingest/
      SKILL.md
  provenance/
    packs/
      <pack-id>.json
  schemas/
    icon-set.schema.json
    continuity.schema.json
    icon-identity-event.schema.json
    publication-head.schema.json
    active-pointer.schema.json
  templates/
    icon-set.json
    continuity-examples.jsonl
    publication-head.json
    active-pointer.json
  reports/
    <release-revision>-changes.json
  tools/
    build_catalog.py
    validate_catalog.py
  tests/
    test_catalog.py
  requirements-build.txt
```

Rules:

- Do not copy editor caches, generated project state, scenes, or project settings into the build.
- The `assets/` tree contains PNG files only; source-adjacent sidecar files are never copied.
- Store each unique PNG blob once by SHA-256 while preserving every source path,
  logical alias, collection, and rendition relation in metadata.
- Exclude all editor-specific identifiers, sidecars, and settings.
- Store only catalog-relative POSIX-style paths in records.
- Carry `manifests/icon-identities.jsonl` forward on every update. Bootstrap is
  the only build allowed to start without a previous registry.
- Never remove a previously published identity, blob, or icon-to-blob rendition
  association from a successor release. Retired icons remain resolvable but are
  hidden from normal search.
- Keep ingestion staging and annotation work files outside immutable release directories.
- Future schema migrations import the identity ledger unchanged; they never reseed IDs.

## 5. Database formulation

### 5.1 Core tables

| Table | Purpose |
|---|---|
| `catalog_release` | Permanent catalog ID, release ID, schema version, logical revision, predecessor release/revision, build time, identity-registry hash, source-manifest hash, annotation-set hash |
| `pack` | Permanent `pack_id`, provider, source product ID, package name/version, permission reference, source metadata |
| `icon` | Permanent `icon_id`, pack, collection, ordinal, title, preferred rendition, lifecycle status, optional successor ID |
| `blob` | SHA-256 primary key, byte size, MIME type, width, height, PNG color type, alpha facts, content-addressed relative path |
| `rendition` | Rendition ID, icon ID, blob hash, stable role, lifecycle status, first and last release |
| `source_item` | Permanent `(pack_id, source_key)` mapping to one icon ID, collection, lifecycle state, and prior aliases |
| `source_occurrence` | One physical source file: source item, source version, relative path, stable role, blob hash, ordinal, and grouping evidence |
| `annotation` | Literal description, structured observation JSON, generator/model, prompt hash, input fingerprint, confidence, status |
| `keyword` | Unique normalized namespace/value pair, such as `subject:sword` |
| `icon_keyword` | Icon/keyword relation with provenance and confidence |
| `derivative` | Thumbnail hash, source rendition hash, purpose, pipeline version, relative path |
| `icon_fts` | Rebuildable FTS5 projection of title, collection, description, keywords, and suggested uses |

### 5.2 Required constraints and indexes

- Primary key on `blob.sha256`.
- Primary key on `icon.icon_id`; published values are immutable.
- Unique permanent `pack.pack_id`.
- Unique `(source_item.pack_id, source_item.source_key)`.
- Unique `(source_occurrence.pack_id, source_occurrence.source_version, source_occurrence.relative_path)`.
- Unique `blob.relative_path` matching its SHA-256 object path.
- Index on `(rendition.icon_id, rendition.stable_role)`.
- Unique `(keyword.namespace, keyword.value)`.
- Indexes in both directions of `icon_keyword`.
- Index on `(icon.collection, icon.ordinal)` without treating it as immutable identity.
- Unique annotation pipeline fingerprint per icon and annotation kind.
- Foreign keys enabled and checked during validation.
- `PRAGMA user_version = 1`.
- FTS5 external-content or rebuild procedure tested from normalized source tables.

`manifests/icon-identities.jsonl` is the identity authority. The `icon` and
`source_item` identity/lifecycle rows are runtime projections checked against
its hash; physical `source_occurrence` rows come from the source manifest. A
tombstoned icon remains addressable by ID but is omitted from default search.

The registry is an append-only, hash-chained event ledger governed by
`schemas/icon-identity-event.schema.json`. Assignment, continuity, retirement,
reviewed reactivation, and optional successor events record a monotonically
increasing sequence, event ID, previous-event hash, ingest-plan ID, affected
`pack_id`, `icon_id`, pack-local source key, and evidence digest. A candidate
registry must contain the predecessor ledger as an exact byte prefix before
appending events. `release.json` binds the appended sequence range to the final
catalog revision, avoiding a circular revision field inside the ledger.

Ledger encoding is UTF-8 with LF endings and one canonical JSON object per line
using sorted keys and no insignificant whitespace. `previous_event_sha256` is
the SHA-256 of the preceding canonical line; the first event uses `null`.

Reactivation is allowed only for the exact same reviewed logical binding. It
appends history; it never erases retirement or repurposes an ID.

Frequently filtered values remain typed columns. Extensible model observations may use validated canonical JSON.

### 5.3 Stable handles and exact pins

A stable handle survives package versions, deployment locations, and source
renames. It resolves the currently preferred rendition of the same logical
icon:

```json
{
  "catalog_id": "indexed-icon-pack",
  "icon_id": "icon_550e8400-e29b-41d4-a716-446655440000"
}
```

An exact rendition pin adds the byte identity:

```json
{
  "catalog_id": "indexed-icon-pack",
  "icon_id": "icon_550e8400-e29b-41d4-a716-446655440000",
  "rendition_sha256": "sha256:..."
}
```

`observed_catalog_revision` may accompany either form as audit provenance, but
is not lookup identity. A stable handle continues to resolve after a verified
upgrade. A pin returns exactly the requested bytes or fails; it never
substitutes the preferred rendition. Successor releases retain published blobs
so valid pins remain resolvable. A retired stable handle resolves its last
published preferred rendition with `lifecycle_status: retired`; it never follows
an optional successor automatically.

Exact-pin resolution must prove that the requested hash is a published
historical rendition of the supplied `icon_id`, not merely that the blob exists
somewhere in the catalog.

## 6. Search and annotation design

### 6.1 Deterministic metadata

The scanner streams each PNG once to collect SHA-256, byte size, signature, dimensions, color type, source path, and variant candidates. It rejects paths outside the configured source root and records every anomaly rather than normalizing it away.

Pairing is a separate relationship-building step:

- collection and ordinal generate candidates;
- exact hashes and deterministic image comparison detect aliases or mismatches;
- uncertain pairs remain separate or are marked for annotation-assisted verification;
- the build never overwrites source files to make the structure appear cleaner.

### 6.2 Generated annotations

An image-input-capable LLM agent, not a filename parser or deterministic script,
supplies the visual description and literal keywords. One logical icon receives
one current literal annotation, with rendition-specific technical facts kept
separately. The annotation schema requests:

- a one-sentence literal description;
- primary and secondary visible subjects;
- visible action or state;
- dominant colors and materials;
- effects such as glow, fire, frost, smoke, aura, or sparks;
- composition, count, and orientation;
- visible symbols or text;
- literal keywords;
- separately labeled inferred UI uses.

Every annotation stores its input rendition hashes, preview hash, exact
provider/model identifier, prompt hash, schema version, settings, generation
time, raw structured result, confidence, and validation state. Python may
create previews, dispatch approved requests, validate the schema, normalize
keywords, and import results. It must not fabricate missing visual facts from
paths or substitute unreviewed model output. Re-running a changed pipeline
appends a new annotation version; it does not silently replace history.

Captioning is a build-time operation. Runtime search has no vision-provider or network dependency.

### 6.3 Annotation rollout

1. Finish deterministic scanning, identity review, previews, baseline SQLite/FTS5,
   and a stratified sample list **without calling an image model**. Produce an
   owner-facing decision packet: pending logical-icon/request counts, rendition
   dimension and preview-size distribution, sample contact sheets, proposed
   structured schema and prompt, model options, current prices, image-detail
   assumptions, and a provisional cost range with its uncertainties.
2. **Stop before the first image-input request, including the pilot.** The owner
   chooses the image-capable model and authorizes the pilot scope. A different
   model or later paid run requires new approval unless an earlier approval
   explicitly covers that model, scope, and spending limit.
3. Run a stratified pilot of up to 100 logical icons covering paired, single,
   achievement, transparent, indexed-color, duplicate, and anomalous cases.
   Compare one-icon requests with small grouped requests only if IDs cannot be
   confused; measure actual image/input/output tokens, cost, latency, and
   literal-description quality.
4. Present the pilot quality and projected full-run cost to the owner. Continue
   only after the owner approves the full-run scope and budget. Freeze the
   model identifier and provider-reported version/snapshot when available,
   image detail, schema, prompt, and normalizer for that run.
5. Process the remaining catalog with checkpoint/resume and cache keyed by the
   pipeline fingerprint. Validate every result automatically and review a
   sampled quality set; per-icon manual authorship is not required.

Provisional recommendation for the first decision packet (checked 2026-10-08):
[GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
because these are stylized icons with small visual details and Sol balances
visual reasoning with cost. The initial corpus has about 6,250 logical icons,
10,200 renditions, and 10,050 images no larger than 512 x 512; this is a
moderate offline batch, not a runtime task. This is an inference, not measured
icon-captioning superiority; the pilot tests it. [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna)
is the lower-cost option to compare when budget dominates. Both support image
input and structured output. At the checked Standard rates Sol is $2 per
million input tokens and $10 per million output tokens; Luna is $0.10 and
$0.50 respectively. [Batch API](https://developers.openai.com/api/docs/guides/batch)
may halve those rates if the approved provider and turnaround fit. The actual
total must be estimated from model-specific image tokenization plus prompt and
output tokens, then recalculated from pilot usage; image count alone is not a
reliable dollar estimate. Recheck model availability, [image-input rules](https://developers.openai.com/api/docs/guides/images-vision),
and prices immediately before the owner chooses.
The owner may choose another image-input-capable provider/model; the catalog
schema and runtime must not depend on the provisional recommendation.

### 6.4 Keywords and ranking

Use controlled namespaces such as:

- `subject`, `action`, `state`, `effect`, `symbol`;
- `color`, `material`, `composition`, `style`;
- `use` for explicitly inferred interface purposes.

Initial ranking uses FTS5 BM25 with this priority:

1. exact title or normalized keyword;
2. subject/action/state/effect terms;
3. literal description;
4. collection name and inferred uses.

Exact filters are applied before text ranking, and `icon_id` is the deterministic final tie-breaker. Vector search is excluded from v1 until a measured query benchmark demonstrates an actual lexical-search gap.

## 7. Consumer interfaces

### 7.1 Python CLI

`iconctl.py` is the bundled reference implementation and the single package-side
implementation used by the CLI, agent skill, and optional local service. Planned
commands:

- `verify` - validate schema, manifests, hashes, FTS consistency, and paths;
- `search` - ranked text search with filters and JSON output;
- `show` - return one logical icon, renditions, annotation, and provenance;
- `materialize` - copy the preferred rendition for a stable handle or an explicitly pinned rendition, then verify its hash;
- `serve` - start the read-only API and browser;
- `version` - report catalog ID, immutable release ID, logical revision,
  schema version, and release-manifest digest.

The `serve` command reuses the same query and resolution code as the other
commands. It is not a second catalog implementation or a separately deployed
service.

Storage resolution order:

1. explicit `--catalog-root`;
2. `INDEXED_ICON_PACK_HOME`;
3. package root containing `iconctl.py`;
4. documented sibling-directory discovery used by the agent skill.

### 7.2 Consumer agent skill

The portable skill calls the CLI with `--json`; it contains no duplicate search logic. It guides an agent through:

1. converting the desired role/appearance into search terms;
2. inspecting top candidates and available renditions;
3. returning a stable handle by default, or an exact pin when reproducible pixels are required;
4. writing a small provenance receipt;
5. refusing to modify unrelated target files.

### 7.3 Maintainer ingestion skill

The separate `indexed-icon-pack-ingest` skill follows [INGESTION.md](INGESTION.md)
and delegates to `tools/build_catalog.py`. It may write only to an external
staging workspace and a new candidate release. It never edits an installed or
published release, directly edits SQLite, guesses ambiguous identity matches,
or deletes registry history.

### 7.4 Read-only API and browser

The standard-library HTTP service binds to `127.0.0.1` by default and exposes:

- `GET /api/v1/version`;
- `GET /api/v1/search`;
- `GET /api/v1/icons/{icon_id}`;
- `GET /api/v1/thumbnails/{icon_id}`;
- `GET /api/v1/blobs/{sha256}`.

There are no upload, mutation, assignment, or publication endpoints in v1. The static browser supplies search, filters, keyboard navigation, accessible labels, a detail panel, rendition selection, and copyable stable handles or exact pins.

### 7.5 Native consumer adapters

The versioned SQLite schema, release manifest, relative asset paths, stable
handle, and exact pin are the language-neutral data contract. A standalone Go or
other native service may open the database read-only and implement the same
search and resolution behavior without Python.

A native adapter checks the installed schema, logical revision, and exact
release-manifest digest for integrity but does not require a stored stable
handle to name that same revision. It must require FTS5 support, keep all
resolved paths beneath the configured package root, and verify an asset hash
before first use. It stores assignments in the consuming system's own records;
the catalog remains immutable. A deployed adapter reports the exact active
release through `GET /api/v1/version` and reopens or restarts cleanly after an
active-pointer switch. Building an AgentSmith adapter is outside this
package's v1 implementation scope.

## 8. Temporary UnitySkills role

UnitySkills is a disposable construction and QA tool, not part of the product
architecture. It may be used to open representative source textures, verify
that the source corpus renders, and cross-check a sample of dimensions and
transparency against the raw-file scanner.

Its responses and project-specific state are transient. None of them may enter
the database, manifests, receipts, paths, CLI/API contracts, requirements, or
delivered files. The streaming Python scanner over source PNG bytes is the sole
authority for full-corpus hashing and manifest construction.

Release validation scans the completed package for editor-specific identifiers,
sidecars, settings, and paths. Any occurrence fails the build. This keeps the
package equally usable by AgentSmith's standalone Go runtime and future
non-editor consumers.

## 9. Agent-maintained ingestion workflow

Ingestion is offline and produces a new immutable candidate release. The
installed package remains read-only throughout.

### 9.1 Staging contract

The maintainer agent works in an external staging directory:

```text
<ingest-root>/
  icon-set.json
  files/
    <collection>/<stable-source-key>/
      <stable-role>.png
  continuity.jsonl
```

Only available rendition files are present. `continuity.jsonl` is optional and
records explicit rename, move, split, merge, or replacement decisions. The
agent may copy and structure supplied files in staging but never changes the
supplied source or a published package.

`icon-set.json` requires a schema version, permanent `pack_id`, display name,
source version, provider, permission reference, `files/` as its asset root, and
a declared `snapshot` or `append` ingest mode plus a deterministic
`preferred_role_order`. Snapshot omissions propose reviewed retirement; append
mode accepts only new source keys. Preflight requires at least one role
from that order for every source item and records exactly one preferred rendition.
A new set receives `pack_<lowercase UUIDv4>` once. An update reuses its existing
`pack_id`. The pack-local source key assists reconciliation but is not a public
icon identifier.

### 9.2 Identity reconciliation rules

The ingestion plan classifies every item as unchanged, renamed or moved,
artwork-updated, new, retired, duplicate, or ambiguous:

1. An existing `pack_id + source_key` with the same rendition-hash set retains
   its `icon_id` automatically.
2. Any changed rendition hash set requires an explicit reviewed choice between
   the same logical icon and a semantic replacement, even when the key matches.
3. An explicit continuity record may retain an ID across a rename or move.
4. Hash and visual similarity may suggest a match but never decide identity.
5. A confirmed new logical icon receives one new ID in the ingest plan.
6. Removal creates a tombstone and retains the last published renditions.
7. A semantic replacement receives a new ID; the old ID may name it as a
   successor but never redirects silently.
8. Splits, merges, conflicting mappings, and other ambiguities stop for review.

The reviewed ingest plan freezes all new IDs. The build step consumes that plan
and is forbidden from allocating or changing IDs. UUID allocation validates
canonical syntax and version, checks the predecessor registry plus the current
plan, and retries collisions before review. A collision found in a frozen plan
fails apply rather than regenerating an ID.

### 9.3 Agent workflow

1. Start from the latest ever-published release (the publication head), which
   may differ from the deployed release after an operational rollback.
2. Create or update `icon-set.json` and stage PNG files in the canonical layout.
3. Preflight schemas, signatures, portable paths, case and Unicode collisions,
   unique source keys/renditions, source version, and permission reference.
4. Generate a read-only ingest plan against the base identity registry.
5. Review retained, new, changed, retired, duplicate, and ambiguous entries;
   changed bytes never receive automatic identity continuity.
6. Stop for explicit continuity decisions wherever identity is uncertain.
7. Apply the reviewed plan to a new candidate workspace atomically.
8. Reuse unchanged annotations and finish deterministic previews/index work.
   Before any new image-input call, present the pending-count, model, and cost
   decision packet and stop for owner choice. Pilot and full run have separate
   approval gates as described in section 6.3.
9. After approved annotation import, finalize the logical catalog revision;
   generate the immutable release manifest, SQLite/FTS5, and change report.
10. Deep-validate the candidate against its base, including every prior ID and blob.
11. Reject stale-base publication and atomically compare-and-advance the
    external publication head. Installation and activation of the verified
    release are separate actions documented in [DEPLOYMENT.md](DEPLOYMENT.md).
    Operational rollback never moves the publication head backward.

`ingest-plan` is the identity-review boundary; the image-model and full-run
gates are additional mandatory boundaries. [INGESTION.md](INGESTION.md) is the
sole authority for planned command signatures and cross-platform examples,
preventing duplicate command documentation from drifting.

## 10. Implementation phases and gates

### Phase 1 - Freeze contracts and skeleton

- Create the final directory skeleton, schema SQL, identity/ingestion JSON schemas, and CLI command contract.
- Freeze the permanent ID lifecycle, stable-handle, exact-pin, tombstone, and
  predecessor-release rules.
- Record source counts and known anomalies as fixtures.
- Add one runnable stdlib test harness.

Gate: schema and command contract reviewed; no source files modified.

### Phase 2 - Deterministic scanner, identity registry, and manifest

- Stream PNGs, hash bytes, parse headers, and collect relative paths.
- Bootstrap or load the predecessor identity registry and generate a reviewed
  reconciliation plan before building.
- Carry forward existing IDs, allocate only confirmed new IDs in the plan, and
  build candidate rendition relations.
- Preserve exact duplicate aliases and emit anomalies.
- Write the canonical identity registry and sorted pre-annotation catalog
  manifest. Record an inventory digest for the decision packet, not a final
  `catalog_revision`; approved annotations are still missing.

Gate: the initial 10,200 renditions and 10,193 unique hashes are reproduced;
update fixtures retain every predecessor ID and blob; zero missing/orphan
records remain; the same approved plan reproduces canonical pre-annotation
manifests, identity assignments, and asset hashes.

### Phase 3 - SQLite catalog, FTS5, and verification

- Create normalized tables and indexes in one transaction.
- Populate a deterministic baseline catalog and rebuild FTS5 without inventing
  visual descriptions or keywords.
- Finalize the database with an integrity check and atomic replacement.
- Implement `verify`, `show`, and deterministic baseline search; `version`
  reports final release identity only after Phase 7 packaging.

Gate: foreign-key and integrity checks pass; manifest/DB counts agree; no absolute paths; catalog rebuild passes the same query checks.

### Phase 4 - Previews, model-choice stop, and annotation pilot

- Generate deterministic 256 x 256 PNG thumbnails from preferred renditions.
- Build paired previews for annotation without altering originals.
- Prepare the stratified sample and decision packet described in section 6.3.
- **Stop and ask the owner to choose/approve the image-input model before even
  the first pilot request.** Do not infer consent from approval of this plan.
- After that choice, run and evaluate the pilot; stop again for full-run quality
  and cost approval. Freeze the selected annotation pipeline and controlled
  keyword vocabulary only after the pilot passes.

Gate: no image-model invocation precedes owner selection; every thumbnail and
pilot annotation has complete provenance; no icon/result ID mismatch; sampled
literal descriptions meet the agreed quality threshold.

### Phase 5 - Full annotation and search tuning

- Run resumable full-catalog annotation only within the owner-approved model,
  scope, and budget.
- Validate, normalize, and import descriptions/keywords.
- Freeze accepted annotation results as versioned build inputs; release rebuilds
  never depend on repeating a nondeterministic model call.
- Assemble a compact benchmark of representative natural-language queries.
- Tune FTS weights and synonyms without adding vectors.

Gate: every searchable icon has a current valid annotation or an explicit failure status; benchmark results meet the agreed top-five relevance target.

### Phase 6 - Materialization, agent skills, API, and browser

- Complete `search`, `materialize`, and `serve`.
- Add atomic copying, default refusal to overwrite, post-copy hash verification,
  and provenance receipts.
- Require exact-pin materialization to validate the historical
  `(icon_id, rendition_sha256)` association before copying.
- Add the portable consumer skill and separate maintainer ingestion skill.
- Add the dependency-free browser and read-only API.

Gate: neighboring-repository workflow succeeds from a clean location; API and CLI return the same ranked IDs; browser passes keyboard/accessibility smoke checks; attempted writes are unavailable.

### Phase 7 - Package and release validation

- Copy only required source assets and portable provenance into the build.
- Compute `catalog_revision` from the approved logical manifest inputs,
  including annotations. Allocate the next `release_id` against the expected
  publication head; finalize the sorted inline payload inventory in
  `release.json` and verify the manifest digest.
- Compare the candidate with its predecessor: every published ID keeps its
  logical binding, every published blob remains, and only confirmed new icons
  receive new IDs.
- Require the predecessor ledger as an exact registry prefix and reject a base
  that does not match the external publication-head state.
- Run full deep verification from the build folder.
- Test installation and usage instructions on a clean shell.
- Scan all text, manifests, and SQLite text values for absolute workstation paths.
- Scan the asset tree, runtime-facing documentation, manifests, database schema
  and column names, and SQLite values for editor-specific state, identifiers,
  paths, or consumer options. This build-process section may name the temporary
  QA tool, but none of its output is retained.
- Record final sizes, counts, catalog revision, release ID, schema version,
  release-manifest digest, and known limitations.

Gate: the package works after being moved beside a different test repository;
stable handles and exact rendition pins resolve after an N to N+1 update;
agent-driven ingestion succeeds from a clean staging directory; all documented
commands execute as written.

### Phase 8 - Publication and local deployment rehearsal

- Publish the verified immutable release by locked compare-and-advance of the
  external publication head; a stale candidate cannot publish.
- Install two releases side by side, deep-verify the installed copy, and
  atomically switch a separate deployment `active.json` pointer.
- Reopen or restart consumers, verify that `GET /api/v1/version` reports the
  active `catalog_id`, `release_id`, `catalog_revision`, and `schema_version`,
  and test rollback without moving the publication head backward.
- Verify that old handles and pins still resolve on N+1 and that new-only IDs
  fail clearly if the runtime is rolled back to N.

Gate: [DEPLOYMENT.md](DEPLOYMENT.md) can be followed on a clean local test
installation; publication and activation remain separate and auditable;
manifest or schema mismatch prevents activation.

## 11. Acceptance checklist

- [ ] All 10,200 initial source renditions are represented exactly once as source occurrences.
- [ ] Every blob has verified SHA-256, byte size, detected PNG type, and dimensions.
- [ ] Exact duplicate files retain all logical/source aliases.
- [ ] Logical pair uncertainty is represented rather than silently guessed.
- [ ] Every logical icon has a permanent opaque ID recorded in the identity registry.
- [ ] Every icon has exactly one preferred rendition selected by the declared role order.
- [ ] Stable handles resolve after package relocation and N to N+1 upgrades.
- [ ] Every prior ID remains bound to the same logical icon; retired IDs remain tombstones and no ID is reused.
- [ ] Rename, move, reorder, artwork-update, addition, retirement, duplicate,
      and semantic-replacement fixtures produce the specified identity outcome.
- [ ] Update builds fail if a predecessor release exists but its identity registry is omitted.
- [ ] Candidate registries preserve the predecessor ledger as an exact prefix
      and pass sequence and hash-chain validation.
- [ ] Stale-base promotion fails against the latest publication head.
- [ ] Publication-head advancement compares the expected predecessor release
      ID, revision, registry hash, and manifest digest, then atomically records
      the candidate only after validation.
- [ ] Changed rendition bytes require an explicit same-identity or replacement decision.
- [ ] UUID allocation checks the predecessor and current plan; frozen collisions fail without reminting.
- [ ] The same base, reviewed ingest plan, inputs, frozen accepted annotation
      results, and pipeline versions reproduce the same identity assignments,
      canonical manifests, revision, logical rows, and hashes.
- [ ] No image-input model call, including a pilot call, occurs before the owner
      selects a model from a corpus-aware cost and quality decision packet.
- [ ] Visual descriptions and literal keywords come from the approved
      image-input agent; scripts only orchestrate and validate them.
- [ ] Full-corpus annotation remains stopped until the pilot's measured quality
      and projected spend receive separate owner approval.
- [ ] Every exact pin resolves the pinned bytes or fails; it never floats.
- [ ] Exact-pin resolution rejects a valid catalog blob that was never a rendition of the supplied icon.
- [ ] Successor releases retain every previously published blob.
- [ ] Successor releases retain every published icon-to-blob association so a
      hash cannot be reassigned to another logical icon during pin resolution.
- [ ] FTS5 searches descriptions, structured keywords, titles, and collections.
- [ ] Search order is deterministic for an unchanged catalog revision.
- [ ] Generated annotations include complete pipeline provenance.
- [ ] `catalog_revision` includes approved annotations and excludes packaging
      noise; `release_id` and release-manifest digest identify exact packages.
- [ ] `GET /api/v1/version` reports active catalog, release, logical revision,
      and schema version; unsupported schema or hash mismatch fails closed.
- [ ] A verified N+1 release installs beside N and activates atomically via an
      external pointer; rollback changes only that pointer, not publication head.
- [ ] Thumbnails are rebuildable and originals remain unchanged.
- [ ] `materialize` verifies the copied digest and emits a receipt.
- [ ] `materialize` refuses unexpected overwrites and path traversal.
- [ ] Runtime CLI/API/browser work without an editor or a vision provider.
- [ ] No editor-specific identifiers, sidecars, settings, paths, schema fields,
      or materialization options occur in completed runtime artifacts.
- [ ] API is read-only and localhost-bound by default.
- [ ] Browser is keyboard usable and supplies accessible text.
- [ ] No absolute workstation paths occur in delivery artifacts.
- [ ] Installation and usage documentation pass from a clean directory.
- [ ] A clean agent-driven ingestion run produces a reviewed, verified candidate without modifying its base release.
- [ ] Full validation is runnable with one documented command.

## 12. Explicitly out of scope for v1

- Vector embeddings, ANN indexes, or a vector database.
- PostgreSQL, object storage, synchronization, HA, or multi-writer publication.
- Editing or generating icon artwork.
- General digital-asset management.
- Automatic mutation of a consuming project's versioned records.
- AgentSmith repository changes; v1 supplies the reference/search interface it can integrate later.
- Deleting or reorganizing the source project.

## 13. Proposed defaults requiring approval

Unless the project owner changes them before implementation:

- represent all 10,200 initial source occurrences and store each of the 10,193
  unique PNG blobs once in the self-contained build;
- use permanent `icon_<lowercase UUIDv4>` and `pack_<lowercase UUIDv4>` identifiers;
- make `manifests/icon-identities.jsonl` append-only authority and require the
  previous verified registry for every update;
- retain tombstones and all previously published rendition blobs in successor releases;
- store duplicate bytes once while preserving every original collection/path as provenance;
- generate one 256 x 256 PNG thumbnail per logical icon;
- use English descriptions and normalized lowercase keywords;
- recommend GPT-6.1 Sol for the first image-input annotation pilot, but stop
  before any image-model request and let the owner choose the actual model;
- require a second owner decision on measured pilot quality and full-run cost;
- ship a standard-library runtime CLI/service, with Pillow as a build-only dependency;
- exclude all editor-specific metadata and materialize PNG files only;
- use lexical FTS5 search only;
- keep all API operations read-only;
- keep ingestion offline in a separate staging workspace and a maintainer-only skill;
- treat this plan's approval as authorization for deterministic implementation
  phases and release tooling only; image-model selection, pilot invocation,
  full annotation, and publication retain their stated explicit gates.

## 14. Community one-pager

The shareable summary of this concept, deliberately free of workstation paths
and private permission details, is [CONCEPT_ONE_PAGER.md](CONCEPT_ONE_PAGER.md).
