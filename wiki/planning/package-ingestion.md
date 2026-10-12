# Implementation plan for additional icon packages

> Sources: Successor-ingestion contract, Unknown; owner directions, Unknown; live source audit and proposed implementation sequence, 2026-10-11; public-data directions and proof, 2026-10-12
> Raw: [Ingestion contract](../../raw/planning/ingestion-contract.md); [Owner directions](../../raw/planning/2026-10-11-owner-directions.md); [Code audit](../../raw/quality/2026-10-11-live-workbench-audit.md); [Proposed sequence](../../raw/planning/2026-10-11-distribution-and-ingestion-proposal.md); [Deployment contract](../../raw/architecture/deployment-contract.md); [Public-data decision](../../raw/planning/2026-10-12-public-data-directions.md); [Public catalog proof](../../raw/delivery/2026-10-12-public-catalog-proof.md)
> Updated: 2026-10-12

## Status: planned, not an available CLI workflow

The current `build_catalog.py` exposes `bootstrap` and `annotation-plan`.
Bootstrap can preserve an unpublished candidate only for unchanged/additive
inputs; it is not a successor-release builder. The first-release packager is
bounded to the initial release. Never run a fresh bootstrap to replace frozen
or published icon identities.

The detailed ingestion contract includes planned commands for initialization,
planning, apply, annotation, release and publication-head advancement. Their
appearance in documentation does not make them executable. This page proposes
an implementation sequence; it does not approve changes or new paid runs.

## Start with append-only new packages

The smallest useful extension adds a new pack without editing or retiring old
icons. Defer changed-artwork and lifecycle decisions until that path works.
Reuse the existing deterministic scanning, hashing, annotation import, validation
and distribution components where their assumptions remain valid.

### Phase A: make the contract genuinely multi-pack

Define a portable pack manifest with permanent `pack_id`, source version,
permission reference, source keys, explicit rendition roles and preferred-role
order. Separate the generic staged layout from the current vendor-folder scanner.

Inspect `catalog_state`, identity-registry parsing, canonical revision inputs,
builders, validators, readers and fixtures together. Current registry parsing
assumes one pack, and the revision carries one pack identity. Existing `pack_id`
fields are not proof of multi-pack support. Choose and document a schema migration
if necessary; retain historical releases and supported reader behavior.

The initial search builder also requires four specific pairing corrections.
Preserve those corrections as initial-corpus provenance; do not require or
reapply them to an unrelated package.

**Exit gate:** a synthetic fixture with distinct packs and duplicate source
names proves pack-scoped keys, globally stable icon IDs, deduplicated bytes
without identity merging, and explicit unsupported-schema rejection.

### Phase B: deterministic plan and frozen apply

Pin the latest ever-published base and identity registry. A planner validates
paths, PNGs, role uniqueness and source provenance; proposes new IDs once; and
freezes input/base/plan hashes. Do not use the currently deployed rollback target
as the ingestion base. Start with append semantics that reject old-content
changes and ambiguous omissions.

Apply the frozen plan only in a new candidate workspace. Revalidate every pin,
carry the old ledger forward byte-for-byte, append new assignments and allocate
no new IDs during apply. Refuse stale inputs, unresolved identity ambiguity or
any write into the base release.

**Exit gate:** repeated planning with the same proposal ledger preserves proposed
IDs; changed inputs invalidate apply; unsafe paths fail; interrupted apply leaves
the old release intact; all prior IDs and exact rendition pins still resolve.

### Phase C: reuse annotations and automate acceptance

Reuse unchanged approved observations and their provenance. Produce a pending-
work and cost decision packet before any new model call. Run only the explicitly
authorized pilot/full scope; keep raw responses immutable and corrections in
hash-pinned overlays. Preserve literal captions, alternate descriptions,
uncertainties and hard facets as different kinds of evidence.

No independent manual reviewers are required. Automate format, identity,
retrieval, negative-query and contract checks. An unresolved semantic identity
decision stops the candidate; it is not guessed by a similarity threshold.
Owner decisions for exceptional identity ambiguity, spending and publication
remain authority boundaries, not a manual per-icon quality workflow.

The completed corpus-run authorization does not authorize arbitrary future
packages or reannotation. Stop for a new model/spend decision unless an explicit
current authorization covers that scope. Never silently rebuild the full corpus.

**Exit gate:** unchanged inputs produce no paid requests; retries are bounded
and metered; new evidence covers the new pack and regressions on the existing
catalog. Use a fresh sealed acceptance set and an explicitly adopted threshold,
not the already opened initial holdout.

### Phase D: successor packaging and publication head

Generalize the bounded first-release builder only after the previous gates.
Build outside the base, compute the logical revision, bind predecessor identity
and manifest pins, retain old blobs/associations, and emit a complete inventory.
Implement locked expected-head compare-and-advance as a separate publication
operation, not as a side effect of building or deploying.

**Exit gate:** automated tests cover ledger prefix and hash-chain continuity,
old exact-pin bytes, deterministic logical rebuilds, stale-base refusal,
concurrent publication conflict and recovery. A candidate cannot overwrite an
existing release or silently advance an unexpected publication head.

### Phase E: transport and rollout

Reuse the no-icon/Nextcloud split and the existing local deployment selector.
Keep the successor's generated database, observations and manifests in the
public Git snapshot while image bytes remain private. Pass the ordinary-Git
size guard and export parity check, and tag code and data together. The current
observation export is not an implemented generic ingestion/rebuild interface.
Restore a clean copy, deep-verify it, exercise CLI/HTTP/materialization, then
rehearse activation and rollback in a disposable deployment. Publish only after
the owner authorizes it; activation remains a separate operation.

**Exit gate:** older consumers retain their stable references; a consumer
requiring an icon introduced later is held or rolled back coherently when the
runtime rolls back. Reader-reported pins match the selected package.

## Deferred lifecycle work

Rename/move continuity, changed artwork, retirement/reactivation, semantic
replacement and split/merge require explicit lifecycle semantics and history.
The existing full ingestion contract specifies the target behavior. Implement
and test these deliberately after append-only new-pack ingestion; never reuse
an old ID or merge logical identities merely because image bytes match.

Shared blobs across releases and incremental downloads are later storage
optimizations. They are not implemented by the current all-images transport.

## See Also

- [Technical stack and contracts](../architecture/stack-and-contracts.md)
- [Implementation roadmap](implementation-roadmap.md)
- [Release evidence](../quality/release-evidence.md)
