# Technical stack and contracts

> Sources: Installation, deployment and usage contracts, Unknown; initial field-test report and live code audit, 2026-10-11; public-data directions and proof, 2026-10-12
> Raw: [Requirements](../../raw/architecture/runtime-and-build-requirements.md); [Deployment](../../raw/architecture/deployment-contract.md); [Usage](../../raw/architecture/consumer-usage.md); [Search report](../../raw/quality/2026-10-11-final-search-report.md); [Code audit](../../raw/quality/2026-10-11-live-workbench-audit.md); [Public-data decision](../../raw/planning/2026-10-12-public-data-directions.md); [Public catalog proof](../../raw/delivery/2026-10-12-public-catalog-proof.md)
> Updated: 2026-10-12

## Implemented stack

| Layer | Technology | Boundary |
|---|---|---|
| Catalog | SQLite with FTS5, normalized metadata, schema v2 | Read-only for consumers; images remain files |
| Retrieval | Field-weighted BM25, seed-term selection and reciprocal-rank fusion | Deterministic runtime, no embeddings or model calls |
| CLI and HTTP | Python 3.11 or newer, standard library | `iconctl.py` provides search, details, materialization, version and verification |
| Browser | HTML and JavaScript served by the same Python service | No separate frontend build or runtime Node dependency |
| Image preparation | Pillow==12.3.0 | Build-time decoding and thumbnails, not a consumer dependency |
| Visual annotation | Metered image-input model pipeline with immutable output and reviewed overlays | Initial finishing used GPT-6 Sol High; this is provenance, not a standing future-run authorization |
| Distribution | Ordinary Git with the generated SQLite index; optional ZIP; HTTPS/WebDAV and SHA-256 | Only private images and credentials are excluded from the public catalog snapshot |
| Tests and launch | Python unittest; optional uv launcher; Node for a browser-behavior test | Public tests should not depend on private assets or live paid APIs |

A native application may use SQLite directly or call the read-only HTTP API.
There is no required Docker service, vector database or Unity runtime dependency.

The public snapshot is under `catalog/`. Its observation JSONL exposes accepted
descriptions and alternatives for inspection; it does not implement a generic
rebuild/import interface. Metadata-only validation checks the existing database
and non-image payload hashes. Full release validation and activation still
require all image bytes. Git attributes preserve pinned files across checkout;
the publication guard rejects LFS filters and oversized ordinary-Git files.

## Search contract

`require` applies hard facet constraints; fielded `query` uses FTS5; `like`
provides a soft positive example. `except` removes logical icons and all their
renditions before ranking and limiting. Collection and rendition filters remain
available. CLI, HTTP and browser share retrieval logic.

Results report requested and returned counts, shortfall, match reasons and the
search-profile identity. Scores are ranking evidence, not calibrated confidence.
Detail lookup exposes descriptions, alternatives, uncertainty and possible uses.
Selected-image materialization checks the icon-to-rendition association, copies
the exact bytes, records a receipt and refuses an existing destination.

## Stable references and version pins

| Field | Meaning |
|---|---|
| `catalog_id` | Permanent catalog lineage |
| `pack_id` | Identity of a source package; generic multi-pack ingestion is not yet implemented |
| `icon_id` | Permanent logical icon identity |
| `rendition_sha256` | Exact historical pixels associated with that icon |
| `catalog_revision` | Canonical logical content, distinct from SQLite file layout |
| `release_id` | Immutable package release, independent of consumer assignments |
| `release_manifest_sha256` | Pin for the exact manifest and its payload inventory |
| `schema_version` | Consumer compatibility contract |
| `search_profile_sha256` | Retrieval implementation/configuration fingerprint |

The append-only identity ledger is authoritative; database rows are projections.
The general retirement, replacement and reactivation contract is future work:
current initial-corpus tooling must not be treated as a full lifecycle engine.

The current release uses schema v2. Older documentation examples with another
schema value are examples, not the installed version.

## Publication is not activation

The implemented local deployment selector verifies a release before changing an
external `active.json`. It does not copy files or restart a consumer. Readers
must report the loaded version after reload, and must keep database and asset
paths bound to the same release.

The intended publication head means newest ever published; deployment may select
an older release during rollback. General locked publication-head advancement
is deferred. A rollback never authorizes ID reuse or makes newer icons exist in
an older package.

## See Also

- [Purpose and principles](../overview/purpose-and-principles.md)
- [Release evidence](../quality/release-evidence.md)
- [Additional-package ingestion](../planning/package-ingestion.md)
