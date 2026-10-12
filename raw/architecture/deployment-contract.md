# Deployment and version contract

> Source: Local workbench file `DEPLOYMENT.md`
> Collected: 2026-10-11
> Published: Unknown
> Source-SHA256: a4f1b7a9bddd9921650a018dbf8acc207a869f119519cefeacfbac64ed4793d2

# Deployment and Version Contract

Initial field-test scope: immutable schema-v2 packaging, canonical revision
verification and local active-pointer selection are implemented. Automated QA
must pass before the first-release builder emits a package. General successor
ingestion and publication-head advancement remain deferred; the contract below
does not authorize r000002 or any production activation. A work candidate is
not a deployable release.

## Identities and compatibility

| Field | Meaning | Changes when |
|---|---|---|
| `catalog_id` | Permanent catalog lineage, `indexed-icon-pack` | Never within this lineage |
| `icon_id` | Permanent identity of one logical icon | Never for that icon |
| `catalog_revision` | SHA-256 of canonical logical catalog data, including identity bindings, rendition relations, and accepted annotations | Catalog data changes |
| `release_id` | Monotonic publication number, beginning with `iip-r000001` | Every published package, including tooling-only rebuilds |
| `schema_version` | Catalog/SQLite data-contract version | The catalog schema changes |

A consumer persists `catalog_id` plus `icon_id` as a stable handle. It adds
`rendition_sha256` when it must retain exact pixels. It may record the observed
`release_id` and `catalog_revision` for audit; neither is part of icon lookup.

`release_id` is allocated as one greater than the latest publication-head
sequence. Two candidates from the same head may initially claim the same next
number; only one may advance the head. The other must rebuild against the new
head before publication. The number is never reused after publication, even
when a deployment rolls back. The prefix and zero padding are presentation;
consumers compare the parsed sequence and predecessor chain, not string order.

`catalog_revision` is derived from canonical logical catalog inputs, not from
`release.json`, SQLite page bytes, build timestamps, tooling, or documentation.
Thus a packaging-only release may have a new `release_id` and the same
`catalog_revision`. Schema-v2 revision encoding is UTF-8 canonical JSON (sorted
keys, no whitespace, unescaped Unicode), SHA-256-prefixed `sha256:`. The input
record hashes the identity ledger, logical catalog manifest, annotation
provenance, pairing corrections, and sorted canonical rows of icon, blob,
rendition, rendition_history and icon_observation. It includes catalog/pack IDs.
JSON provenance inputs are canonicalized before hashing; canonical JSONL inputs
retain their exact validated bytes. The blob's packaged `relative_path` is not
logical identity. FTS/facet projections, thumbnails, profile/tool hashes, docs
and packaging are excluded. `tools/catalog_revision.py` is the executable definition and the
exact record ships as `manifests/catalog-revision.json`.

A consumer declares the `schema_version` values it supports. It refuses an
unsupported version before opening the catalog. The read-only HTTP API has
its own `/api/v1` contract; changing the SQLite schema does not silently
change that API or a stored icon handle.

## Immutable release manifest

Every release contains `manifests/release.json`. Its planned shape is:

```json
{
  "manifest_schema_version": 1,
  "catalog_id": "indexed-icon-pack",
  "release_id": "iip-r000001",
  "predecessor_release_id": null,
  "predecessor_release_manifest_sha256": null,
  "catalog_revision": "sha256:<64 lowercase hex digits>",
  "schema_version": 2,
  "identity_registry_sha256": "sha256:<64 lowercase hex digits>",
  "identity_event_range": {"first": 1, "last": 6250},
  "payload": [
    {
      "path": "catalog.sqlite",
      "size": 123,
      "sha256": "sha256:<64 lowercase hex digits>"
    }
  ]
}
```

`payload` is a sorted inventory of every packaged file other than
`manifests/release.json`. It includes the database, assets, thumbnails,
scripts, documentation, and identity registry. Paths are relative to the
release root, use `/`, and cannot escape that root. The manifest is finalized
before publication and cannot be edited in place. The SHA-256 of its exact
bytes is the `release_manifest_sha256` used by external publication and
deployment state; the manifest does not hash itself. Final-release deep
verification must check every payload size and hash, recompute the logical
catalog revision, and validate the registry, database, and all path
boundaries. Schema-v2 revision recomputation is implemented. `identity_event_range` names only events
appended by this release; it is `null` when a packaging-only release appends
none. The predecessor manifest digest is `null` only for the first release.

The manifest hash detects accidental changes against a trusted publication
record or approved release handoff. A hash read only from the same untrusted
package is an integrity check, not proof of its origin.

## Publication and active deployment

The maintainer's `publication-head.json` lives outside immutable releases. It
records the newest release ever published and is the required base for future
ingestion. Its planned fields are `schema_version`, `catalog_id`, `release_id`,
`catalog_revision`, `identity_registry_sha256`, and
`release_manifest_sha256`. Here `schema_version` is the catalog schema version.
Promotion compares the expected predecessor under
an exclusive lock and advances this file atomically. Runtime rollback never
rewinds it.

Each deployment has its own `active.json` outside the releases. It selects the
release that readers should load, which may be older than the publication head.
During reload, a reader may briefly still serve the previous release; its
version endpoint reports what it actually loaded:

```json
{
  "catalog_id": "indexed-icon-pack",
  "release_id": "iip-r000001",
  "release_manifest_sha256": "sha256:<64 lowercase hex digits>",
  "relative_release_path": "releases/iip-r000001"
}
```

`relative_release_path` is relative to the deployment root. The installer and reader
reject absolute paths, traversal, and resolved paths outside that root.
Runtime configuration may instead supply one verified release directory
directly; in that case the deployment manager owns the atomic configuration
switch. Neither external state file is copied into an immutable release.

## Install and activate

Planned deployment layout:

```text
icon-catalog-deployment/
  active.json
  releases/
    iip-r000001/
      manifests/release.json
      catalog.sqlite
      assets/
      ...
    iip-r000002/
      ...
```

1. Receive the immutable release and its expected manifest hash from the
   approved publication handoff. Verify it deeply in staging.
2. Install it in a new `releases/<release_id>/` directory without overwriting
   an existing release. Keep the prior active release available for rollback.
3. Check `catalog_id`, expected manifest hash, `schema_version`, and consumer
   compatibility. Compare the predecessor ID and manifest hash with the prior
   installed release when present and with the approved publication handoff;
   the publisher's deep validation proves full identity continuity. Verify
   the installed copy again.
4. Write a complete new `active.json` to a temporary file in the same
   directory, then atomically replace the pointer. Never modify a release to
   activate it.
5. Restart or explicitly reload the consumer. It reads the pointer once,
   verifies the selected release, and holds that release root and database
   together for the lifetime of its reader. In-flight reads finish against
   their original release.
6. Read `GET /api/v1/version` (or the native equivalent) from each affected
   consumer and compare its loaded release ID and manifest digest with the
   pointer. Activation is complete only after they match. If reload or
   verification fails, restore the prior pointer atomically, restart/reload
   the prior reader, and report the failed activation without changing the
   publication head.

The implemented local selector checks the approved manifest hash, all listed
payload bytes, and the catalog's deep structural validation before changing
only the external pointer:

```text
python tools/deploy_catalog.py activate --deployment-root <deployment-root> --release-id iip-r000002 --expected-manifest-sha256 sha256:<64-hex-digits> --expected-active iip-r000001
python tools/deploy_catalog.py check-loaded --deployment-root <deployment-root> --version-url http://127.0.0.1:8765/api/v1/version
```

Use `--expected-active none` for first activation. The selector does not copy
files or restart a service. A
failed version check means activation has not completed; select the prior
release with `activate` and the current ID as `--expected-active`, then reload
the reader.

An adapter must not resolve a file from one release while querying another
release's database. Finalized SQLite files must not require writable journal
or WAL sidecars. The release mount is read-only after installation.

## What consumers report

`iconctl.py version --json` and `GET /api/v1/version` expose the selected
release in the same planned shape:

```json
{
  "catalog_id": "indexed-icon-pack",
  "release_id": "iip-r000001",
  "catalog_revision": "sha256:<64 lowercase hex digits>",
  "schema_version": 1,
  "release_manifest_sha256": "sha256:<64 lowercase hex digits>"
}
```

Search and lookup results may include `observed_release_id` and
`observed_catalog_revision` for diagnostics. Stored stable handles remain
`catalog_id` plus `icon_id`. Consumers report an unsupported schema, missing
release, corrupt payload, or unresolved icon as an error; they do not silently
switch releases or icons.

A Go consumer can call the read-only API or use a SQLite driver with FTS5 to
open the selected release read-only. The native adapter validates the manifest
and schema, keeps path resolution inside that same release root, and checks an
exact pin's historical icon-to-rendition association. A native adapter needs
a SQLite driver selected by the consuming project; the package does not imply
one is already present.

## Rollback

Verify a retained older release and atomically point `active.json` at it,
then restart or reload readers. Do not edit immutable releases, stored stable
handles, or the publication head. A handle or exact rendition pin first
published after the rollback target cannot resolve there. Before activation,
the consuming application must identify dependent records and roll them back,
hold them, or keep serving the newer release. The application must also
support the rollback target's `schema_version` before activating it.

