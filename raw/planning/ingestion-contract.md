# Successor ingestion contract

> Source: Local workbench file `INGESTION.md`
> Collected: 2026-10-11
> Published: Unknown
> Source-SHA256: 0831e79a130fc48f46a4831429c2c612380776501cd43973bcf8aa501a523952

# Icon Set Ingestion

Status: **deferred for the fixed-corpus field-test release**. The complete
reviewed successor-ingestion and publication commands below remain planned.
The implemented builder currently handles first-corpus bootstrap and
additive-only rebuilding from an unpublished candidate; changed or removed
source items stop for review.
The first corpus's 6,250 IDs are now pinned by the maintainer workspace's
`work/identity-freeze-v1/README.md` record (not bundled with consumers). Four
pilot-confirmed rendition associations are incorporated into schema-v2 search
candidates. The identity ledger remains unchanged. The field-test first-release
builder cannot create successors; do not use bootstrap to replace published IDs.
The following build commands are for the maintainer source workspace, not the
minimal consumer package.

This guide defines how an authorized agent adds a new icon set or updates an
existing set without changing any previously published `icon_id`. Ingestion is
offline: it reads an immutable base release and writes to an external staging
workspace and a new candidate release.

## Implemented pre-annotation commands

From the package root, the initial corpus can be built into a **new**
unpublished work directory. The output must not already exist:

```powershell
uv run --with Pillow==12.3.0 --no-project python .\tools\build_catalog.py bootstrap --source '..\..\Assets\Fantasy RPG Icons Pack\Asset' --output .\work\preannotation-v1
uv run --no-project python .\tools\build_catalog.py annotation-plan --workspace .\work\preannotation-v1 --output .\work\annotation-decision-v1.json
```

These exact outputs already exist in this delivered workbench. Both commands
refuse overwrite; use fresh output names for any deliberate rebuild, and use
the new candidate path for its annotation-plan input. A fresh bootstrap without
`--base` creates different provisional IDs, so it must never substitute for
the chosen identity registry after that registry is frozen.

`bootstrap --base <prior-unpublished-candidate>` can carry IDs forward only
when old source files and bytes are unchanged and the new input is additive.
It is not the general release-update workflow described later in this guide.
`annotation-plan` performs no image-model calls and stops at the owner
model-choice gate.

## Non-negotiable identity rules

- `catalog_id` is permanent for the catalog lineage.
- Each icon set receives one permanent `pack_id`.
- Each logical icon receives one opaque `icon_<lowercase UUIDv4>` exactly once.
- A published `icon_id` is never regenerated, rebound, deleted, or reused.
- Paths, names, ordinals, scan order, annotations, and file hashes never create
  identity after publication.
- A rename, move, reorder, new rendition, or intentional artwork refresh keeps
  the existing ID only after the workflow proves or explicitly reviews that it
  is still the same logical icon.
- A semantic replacement gets a new ID. The old ID becomes retired and may
  record a successor, but lookup never redirects silently.
- Removed icons remain as tombstones and keep their last published renditions.
- Reactivation requires explicit review of the same logical binding and appends
  history; it never erases retirement or repurposes the ID.
- Exact duplicate bytes may share storage facts but do not merge logical IDs.
- Every update starts from the latest ever-published identity registry, even if
  deployment has rolled back to an older release. If it is missing or stale,
  ingestion stops.

The authoritative registry is the append-only, hash-chained
`manifests/icon-identities.jsonl`. The predecessor ledger must be an exact byte
prefix of its successor. SQLite tables are projections of that registry, not a
second identity authority.

## Roles and write boundary

The consumer skill searches, inspects, and materializes icons. It cannot ingest.

The separate `indexed-icon-pack-ingest` maintainer skill may:

- create files in an explicitly supplied staging workspace;
- create a new candidate release directory;
- invoke the documented build and validation tools.

It must never edit a source set, installed release, published release, or
consumer repository; directly edit `catalog.sqlite`; delete identity history;
or guess an ambiguous continuity decision.

The candidate output must be distinct from and outside the base and staging
directories. No command may overwrite or create files beneath the base release.

## Requirements

An update requires:

- the latest ever-published Indexed Icon Pack release (the publication head);
- the external publication-head state file;
- a verified tool root containing the versioned `tools/` directory;
- the new or updated PNG source set;
- Python 3.11 or newer and pinned build dependencies;
- enough temporary space for source files, the base, the candidate, thumbnails,
  and annotation previews;
- an explicit staging and candidate-output path;
- identity decisions reviewed by the owner; a separate owner choice of
  image-input model and pilot scope before any new image-model call, followed
  by full-run approval after the pilot.

Every workflow in this guide requires a base release. The one-time initial v1
bootstrap is governed by the implementation plan and produces the first
identity registry before this maintainer workflow becomes available.

`<tool-root>` will normally be the publication-head release, but it is named
separately so commands never infer identity from their script path. Examples
use shell-neutral one-line commands and forward slashes; agents quote concrete
paths as required by their shell.

The publication head is maintainer state outside immutable packages: it names
the latest release ever published in this catalog lineage. Deployment may point
to an older release during rollback, but future ingestion still uses the
publication head.

The platform-neutral state contains no deployment path:

```json
{
  "schema_version": 1,
  "catalog_id": "indexed-icon-pack",
  "release_id": "iip-r000001",
  "catalog_revision": "sha256:...",
  "release_manifest_sha256": "sha256:...",
  "identity_registry_sha256": "sha256:..."
}
```

The initial publication creates this file. Later publication acquires an
exclusive lock, compares the expected predecessor release ID, revision,
registry hash, and release-manifest digest, writes a temporary successor
state, and atomically replaces it only after candidate validation. The
concrete base and candidate paths remain
command arguments. This is distinct from the deployed `active.json` pointer;
see [DEPLOYMENT.md](DEPLOYMENT.md).

## Canonical staging layout

```text
<ingest-root>/
  icon-set.json
  files/
    <collection>/<stable-source-key>/
      <stable-role>.png
  continuity.jsonl
```

Only rendition files that exist are included. The agent copies source PNGs into
this layout without modifying their bytes. Collection and source-key segments
must be portable relative paths. `continuity.jsonl` is omitted unless an update
needs explicit rename, move, split, merge, or replacement decisions.

A rename or move that retains logical identity is recorded as one JSON object
per line:

```json
{"action":"retain","pack_id":"pack_550e8400-e29b-41d4-a716-446655440000","icon_id":"icon_7a1c78a0-bb44-4f24-a908-3918ad6f4778","old_source_key":"shield-07","new_source_key":"frost-shield-07","reason":"renamed upstream"}
```

A semantic replacement uses `action: "replace"`; it names the retired
`old_icon_id` and a fresh new source key but never supplies or reuses the new ID. The
reviewed ingest plan mints that new ID. Split and merge decisions use their
dedicated schema forms and always require owner review. The implemented package
will provide validated shapes in `templates/continuity-examples.jsonl`; agents
must not invent fields outside `schemas/continuity.schema.json`.

Required `icon-set.json` fields:

```json
{
  "schema_version": 1,
  "pack_id": "pack_550e8400-e29b-41d4-a716-446655440000",
  "display_name": "Example Icon Set",
  "source_version": "2026-10-08",
  "provider": "example-provider",
  "permission_reference": "internal-record-id",
  "assets_root": "files",
  "ingest_mode": "snapshot",
  "preferred_role_order": ["transparent", "default", "background"]
}
```

For a new set, `init-set --new-pack` mints and writes `pack_id` once. For an
update, the agent copies the existing `pack_id` from the base release. The
pack-local source key supports reconciliation but is never exposed as the
public icon ID.

`snapshot` means `files/` is the complete new state of that pack; omitted prior
items are proposed as retirements and require review. `append` accepts only
genuinely new source keys and cannot change or retire existing items. This
explicit mode prevents a partial upload from silently looking like mass removal.

Preflight selects the first available role in `preferred_role_order` and
requires exactly one preferred rendition for every logical icon. A set may use
different role names, but their order is explicit and versioned.

## End-to-end agent workflow

### 1. Start from a verified base

```text
python <base>/iconctl.py verify --deep
```

Record its `catalog_id`, `catalog_revision`, and identity-registry hash. Refuse
an update if the base is corrupt, belongs to another catalog lineage, or lacks
the registry.

### 2. Initialize external staging

For a new set added to an existing catalog:

```text
python <tool-root>/tools/build_catalog.py init-set --staging <ingest-root> --base <base> --new-pack --mode snapshot --name "Example Icon Set" --source-version "2026-10-08" --provider "example-provider" --permission-reference "internal-record-id"
```

For an existing set:

```text
python <tool-root>/tools/build_catalog.py init-set --staging <ingest-root> --base <base> --pack-id pack_550e8400-e29b-41d4-a716-446655440000 --mode snapshot --source-version "2026-10-08"
```

Update mode can prefill immutable pack metadata from the base, but the agent
must review every required manifest field before planning.

Structure copied PNGs under `files/`. Do not place caches, generated project
state, unrelated documents, archives, or unsupported image formats in staging.

### 3. Generate a read-only ingestion plan

```text
python <tool-root>/tools/build_catalog.py ingest-plan --staging <ingest-root> --base <base> --publication-head <head-state> --output <ingest-root>/ingest-plan.json
```

Preflight validates:

- the set manifest and portable relative paths;
- declared snapshot or append semantics;
- PNG signatures, dimensions, and hashes;
- path containment and escaping links;
- case-folding and Unicode-normalization collisions;
- unique source keys and rendition roles within the pack;
- exactly one deterministic preferred rendition per source item;
- source-version and permission provenance;
- catalog and pack continuity;
- canonical UUIDv4 syntax and absence of collisions across the base registry and current plan;
- duplicate content and unsupported files.

The plan reports unchanged, renamed or moved, artwork-updated, new, retired,
duplicate, and ambiguous items. It contains the proposed ID for every confirmed
new logical icon, its base revision and registry hash, the input-manifest hash,
an ingest-plan ID, and its plan hash. The hash is calculated from canonical plan
JSON with the `plan_hash` field omitted, then inserted. Planning never mutates
the base or candidate and records base identity by revision/hash, never by an
absolute filesystem path. Apply receives the concrete base path separately and
verifies it against that frozen identity.

### 4. Review identity reconciliation

Automatic continuity is limited to an existing `pack_id + source_key` with an
unchanged rendition-hash set. Changed bytes always require an explicit reviewed
classification as the same logical icon or a replacement. Explicit continuity
records may preserve an ID across a known rename or move. Hash, filename, and
visual similarity are suggestions only.

The agent must stop for owner review when it encounters:

- an ambiguous rename or likely delete-plus-add;
- a split or merge;
- conflicting continuity declarations;
- a semantic replacement;
- any changed rendition bytes;
- an unexpected retirement;
- the same source key mapped to different IDs;
- any attempt to rebind or reuse a published ID.

After decisions are recorded, regenerate with the prior proposal ledger so IDs
already proposed for unchanged new source keys are retained:

```text
python <tool-root>/tools/build_catalog.py ingest-plan --staging <ingest-root> --base <base> --publication-head <head-state> --prior-plan <ingest-root>/ingest-plan.json --output <ingest-root>/ingest-plan-reviewed.json
```

Only the final approved plan is frozen. Applying a plan with unresolved items
is forbidden. Proposed IDs absent from every published registry are not public
references, but the planner still preserves them between review iterations to
keep the review legible.

### 5. Apply the frozen plan

```text
python <tool-root>/tools/build_catalog.py ingest-apply --plan <ingest-root>/ingest-plan-reviewed.json --base <base> --workspace <ingest-root>/work
```

`ingest-apply` verifies all frozen hashes, copies accepted PNGs, carries forward
the prior registry, published blobs, and historical rendition associations,
appends new identities and lifecycle events, and prepares only a candidate
workspace. It allocates no IDs.

The planner retries a UUID collision before the plan is reviewed. Apply treats
any collision in a frozen plan as corruption and fails; it never remints IDs.

Each new identity event receives the next sequence, the previous-event hash,
and the frozen ingest-plan ID. The predecessor registry remains an exact byte
prefix. The final release manifest, not the event itself, binds appended event
sequences to the newly computed catalog revision.

### 6. Annotate pending icons

First reuse unchanged approved annotations and complete all deterministic
previews, identities, and baseline indexes. Create a decision packet without
calling an image-input model:

```text
python <tool-root>/tools/build_catalog.py annotation-plan --workspace <ingest-root>/work --output <ingest-root>/annotation-decision.json
```

The local command provides the pending logical-icon and rendition counts,
dimension distribution, stratified sample, preview assumptions, and proposed
prompt/schema. The agent then adds candidate image-capable models, freshly
verified official prices, and a provisional pilot/full-run cost range to the
owner-facing packet; a local script does not pretend to know current prices.
If no icons need new annotation and no reannotation was requested, reuse the
approved prior results and skip this gate without any image-model call.
Otherwise, **stop here and ask the owner to choose the model and authorize the
pilot.** This also applies to the initial v1 build. No pilot, one-off visual
description, or other image-model request is implied by approval of identity
reconciliation or deterministic build work.

Record that decision in a reviewed, workspace-local pilot decision file with
the exact provider/model, image detail, sample scope, spend ceiling, and packet
digest. `annotate` refuses a missing, mismatched, or exceeded decision. Then
run a stratified pilot of up to 100 new or changed logical icons:

```text
python <tool-root>/tools/build_catalog.py annotate --workspace <ingest-root>/work --scope pending --pilot 100 --decision <ingest-root>/pilot-decision.json
```

Review identity alignment, literal descriptions, structured keywords, and the
measured image/input/output tokens and cost. **Stop again** for owner approval
of the projected full-run scope and spend ceiling. Record that in a distinct
full-run decision file binding the pilot-report digest, selected model
identifier and provider-reported version/snapshot when available, image
detail, remaining icon set, and spend ceiling; a pilot decision cannot authorize
the remainder. The dispatcher reserves a conservative maximum cost before each
request, including retries, reconciles it with reported usage afterward, and
stops if the next request cannot fit under the ceiling:

```text
python <tool-root>/tools/build_catalog.py annotate --workspace <ingest-root>/work --scope pending --decision <ingest-root>/full-run-decision.json
```

Unchanged input and pipeline fingerprints reuse prior annotations. Changed
annotations append a new version instead of overwriting provenance. The
approved image-input agent supplies descriptions and visual keywords; Python
only prepares, dispatches, validates, and imports them. A changed model or
new paid scope requires a new decision unless explicitly covered already.

Review corrections must stay separate from immutable model output. Each
correction pins the raw annotation-file SHA-256 and the icon's preview hash,
records a visual reason, and may add search-only terms or fix a field. The
initial corpus demonstrates this with `REVIEWED_CORRECTIONS_V1.json`
and `REVIEWED_CORRECTIONS_V2.json` in the maintainer workspace's
`work/full-annotation-gpt6-sol-high-v1/` evidence directory,
passed as ordered, read-only `--review` inputs to `tools/assess_annotations.py`. Each
later review pins the preceding review hash, so accepted corrections can grow
without altering raw annotations or earlier evidence. The loader
rejects stale or malformed corrections; neither this review nor a search
assessment edits the raw results or calls a paid model. Release import must
bind both the raw digest and reviewed effective-annotation digest.

### 7. Build a candidate release

```text
python <tool-root>/tools/build_catalog.py release --workspace <ingest-root>/work --base <base> --output <candidate>
```

The build writes a new directory atomically. It generates thumbnails, canonical
manifests, the carried-forward identity registry, normalized SQLite tables,
FTS5, release metadata, and a machine-readable change report. The logical
`catalog_revision` is finalized only after approved annotation import. The
next `release_id` is derived from the expected publication head, and
`release.json` binds a sorted payload-hash inventory. It never mutates `<base>`.

### 8. Validate backward compatibility

```text
python <tool-root>/tools/validate_catalog.py --package <candidate> --previous <base> --json
```

This is the implemented deep-validation syntax (`--fast` is the explicit
weaker mode). It checks predecessor retention and recomputes schema-v2 logical
catalog revisions. It does not yet compare an external publication-head state
file; that check remains required before general successor publication.

Validation must prove:

- every base `icon_id` remains present and bound to the same logical icon;
- no retired ID was reused and no active ID disappeared;
- every previously published blob remains available by hash;
- every historical icon-to-blob rendition association remains queryable;
- stable handles resolve in the candidate;
- exact rendition pins return the same bytes only after validating that the
  hash was a published rendition of the supplied icon;
- new IDs occur only in the reviewed plan;
- the predecessor identity ledger is an exact prefix and the appended sequence
  and hash chain are valid;
- the registry, manifests, database, FTS rows, files, and change report reconcile;
- the release ID is the next monotonic value after the publication head, its
  manifest digest and payload inventory match every delivered file, and the
  logical revision includes the approved annotation set;
- the release manifest binds the appended identity-event sequence range and
  exact predecessor manifest digest (or `null` on first publication);
- the candidate is outside and does not overwrite the base or ingestion root;
- the candidate asset tree contains PNG blobs only and contains no editor-specific
  state, caches, sidecars, absolute paths, or platform-specific schema fields;
- all resolved paths remain inside the candidate and contain no workstation location;
- the supplied base equals the current publication head;
- rebuilding from the same base, plan, inputs, frozen accepted annotation
  results, and pipeline versions reproduces
  the same identity assignments, canonical manifests, catalog revision,
  logical database rows, and asset hashes. SQLite file layout and timestamps
  are not required to be byte-identical.

The N to N+1 fixture includes a rename, directory move, reordered input, artwork
refresh, new icon, retirement, duplicate bytes, and semantic replacement.

### 9. Review and promote

The owner reviews the identity report, new/retired counts, annotation sample,
search smoke results, package-size change, and validation report. Publication
fails if another release has advanced the publication head. Otherwise it
records the validated candidate as a new immutable release and advances only
the external publication head.

```text
python <tool-root>/tools/build_catalog.py advance-head --candidate <candidate> --expected-base <base> --publication-head <head-state>
```

`advance-head` performs the locked compare-and-advance only. Copying a
published release to a consumer host, deep-verifying it, and activating its
external `active.json` pointer are separate local deployment operations in
[DEPLOYMENT.md](DEPLOYMENT.md). They may happen later or not at all.

Stable consumer handles do not change. Exact pins remain valid because
published blobs are retained. Distribution and remote publication are outside
this workflow.

### 10. Roll back a deployment

Restore the previous immutable release through the external active pointer.
Do not
rewrite consumer references, reverse database rows, or delete newly assigned
IDs. An unpublished candidate may be discarded; an ID in a published release
remains reserved forever.

Rollback does not move the publication head backward. Stable handles or pins
first published in the newer release will not resolve while an older runtime is
deployed, so dependent application records must be rolled back together or held
until the newer package is restored. Future ingestion still bases on the newer
publication head.

## Agent completion report

The maintainer agent reports:

- base and candidate revisions;
- base and candidate release IDs and release-manifest digests;
- publication-head revision before and after promotion;
- `pack_id` and source version;
- counts of retained, changed, new, retired, duplicate, and ambiguous icons;
- new permanent IDs and explicit continuity decisions;
- annotation pilot/full-run status;
- selected annotation model and decision-record references, or a clear note
  that work stopped at the model-choice gate;
- verification result and change-report path;
- whether publication occurred and, separately, whether any deployment was
  activated.

If any ambiguity or validation failure remains, the correct result is a stopped
candidate with a clear review request, not a guessed identity or partial
publication.

