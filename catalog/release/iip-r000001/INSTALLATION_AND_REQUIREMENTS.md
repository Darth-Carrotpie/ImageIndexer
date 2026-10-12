# Installation and Requirements

Use these instructions for a verified field-test release containing
`manifests/release.json`, not a `work/` candidate. Automated acceptance and deep
integrity verification gate the first-release builder. General successor
ingestion and production deployment remain outside this fixed-corpus beta.

## Runtime requirements

The core catalog is a language-neutral SQLite database plus ordinary files. A
native consumer requires only:

- read access to the package on Windows, Linux, or macOS;
- an SQLite reader with FTS5 support;
- enough disk space for the initial package, expected to be approximately 4-5 GiB after originals, thumbnails, metadata, and indexes are included.

Successor releases can grow because they add new sets and retain previously
published blobs so stable links and exact pins continue to work.

Python 3.11 or newer is required only for the bundled `iconctl.py` CLI, agent
skill workflow, and optional local browser service. A Go application such as
AgentSmith may instead use its own read-only catalog adapter and does not need
Python. A native adapter requires a SQLite driver with FTS5 support selected
by that application; the read-only HTTP API is the other integration route.

An image editor, Node.js, Docker, a database server, and a vision API will not be runtime requirements.

For the bundled tools, check Python and FTS5:

```powershell
python --version
python -c "import sqlite3; c=sqlite3.connect(':memory:'); c.execute('CREATE VIRTUAL TABLE t USING fts5(x)'); print(sqlite3.sqlite_version, 'FTS5 OK')"
```

On the current Windows workstation, `uv` is the preferred reliable Python launcher:

```powershell
uv run --no-project python --version
```

## Build-time requirements

This section describes the maintainer source workspace. The minimal consumer
package does not include the source corpus, build dependency file or ingestion
dispatcher, and cannot create a successor release.

Building or rebuilding the package requires:

- the source PNG collection;
- the latest ever-published verified release and its identity registry for every update build;
- the external publication-head state file for stale-base checks and atomic advancement;
- Python 3.11 or newer;
- Pillow, pinned in `requirements-build.txt`, for deterministic decoding and thumbnails;
- temporary free space for the base release, source, candidate, and annotation
  previews; reserve at least 10 GiB beyond the existing source for the initial
  corpus and recalculate for larger successor releases;
- an approved image-capable annotation run for descriptions and keywords.

Only the first catalog bootstrap may omit a base release. New or updated icon
sets are staged outside the installed package by following
[INGESTION.md](INGESTION.md).

## Installation

### 1. Place the package outside the consumer repository

Recommended sibling layout:

```text
workspace/
  IndexedIconPack_v1/
  MyProject/
```

Do not copy the whole package into `MyProject`.

### 2. Verify the package

From the package root:

```powershell
python .\iconctl.py verify --deep
```

The final-release validator checks the SQLite schema, foreign keys,
release manifest and payload hashes, recomputed logical catalog revision,
FTS projection, relative paths, and every asset hash. For schema v2 it recomputes
the logical revision using `tools/catalog_revision.py` and checks its input
record in `manifests/catalog-revision.json`.

### 3. Configure discovery when the package is not a sibling

Set a user- or process-scoped environment variable:

```powershell
$env:INDEXED_ICON_PACK_HOME = (Resolve-Path '..\IndexedIconPack_v1').Path
```

Never write that absolute path into a shared definition or provenance receipt. Persistent deployment configuration may hold the mount path; domain records hold only stable handles or exact rendition pins.

### 4. Install the agent skill

The package includes:

```text
agent-skill/indexed-icon-pack/SKILL.md
agent-skill/indexed-icon-pack-ingest/SKILL.md
```

Install only the consumer skill for ordinary search and selection. Install the
maintainer skill only for agents authorized to prepare new releases. The
consumer skill delegates to `iconctl.py`; the maintainer skill follows
`INGESTION.md`. Its build commands require the separate maintainer workspace;
general successor ingestion is deferred for this field-test release.

Copy the selected skill folder into your agent's configured skills directory;
do not overwrite a customized installation. The skill locates the catalog by
an explicit path or `INDEXED_ICON_PACK_HOME`; no model API is needed at runtime.

## Optional local browser

Start the package's read-only service:

```powershell
python .\iconctl.py serve
```

The planned default is `http://127.0.0.1:8765`. Binding another interface must be explicit.

## Deployed installation

Install verified, immutable releases side by side outside application source
code. [DEPLOYMENT.md](DEPLOYMENT.md) defines the release manifest, external
`active.json` pointer, activation checks, and rollback procedure.

The finalized SQLite database must not depend on writable WAL or journal sidecar
files. Consumers open it read-only; SQLite's `immutable=1` mode is appropriate
only when the mounted release really is immutable.

The application should either:

- call the package's read-only HTTP API; or
- use its own language-native adapter to query `catalog.sqlite` read-only and
  resolve files beneath the mounted catalog root.

Persist assignments as stable handles or exact pins, never deployment paths.

## Upgrades

Catalog releases are immutable and share one permanent ID namespace. Build and
verify a newer release against its predecessor, install it beside the older
one, and switch deployment configuration atomically. Stable consumer handles
remain unchanged. Exact pins also remain resolvable because successor releases
retain published blobs.

`release_id` identifies each published package. `catalog_revision` identifies
its logical catalog contents; a tooling-only release can have the same catalog
revision as its predecessor. Neither is part of stable icon lookup. The
consumer checks its supported `schema_version` and reports both identifiers
through its version endpoint. The publication head remains the newest
ever-published release during operational rollback. Application records using
icons or renditions first published after the rollback target must be rolled
back or held until that release is restored. See [DEPLOYMENT.md](DEPLOYMENT.md)
for the exact activation contract.
