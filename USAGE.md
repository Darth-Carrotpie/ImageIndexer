# Usage

Schema-v2 search is implemented. A packaged field-test release is usable only
when `version --json` reports a release ID and `verify --deep` passes. Unpublished
work candidates remain unsuitable for consumer assignments; materialization
is blocked until a verified release manifest exists.

## Current unpublished QA workspace

From this package root, after the bootstrap completes:

```powershell
uv run --no-project python .\iconctl.py --package .\work\preannotation-v1 version --json
uv run --no-project python .\iconctl.py --package .\work\preannotation-v1 verify --deep
uv run --no-project python .\iconctl.py --package .\work\preannotation-v1 search "shield" --json
```

Results in this workspace have no public release ID and descriptions remain
pending model choice. Do not store its candidate IDs in consuming products yet.

## Search from a neighboring repository

Human-readable output:

```powershell
python ..\IndexedIconPack_v1\iconctl.py search "blue shield with frost aura" --limit 12
```

Machine-readable output for an agent:

```powershell
python ..\IndexedIconPack_v1\iconctl.py search "open treasure chest glowing" --limit 8 --json
```

Search returns one row per logical icon, `match_reasons`, ranking scores,
requested/returned counts, truthful `shortfall`, diagnostics, and profile identity.
Scores are not confidence or visual proof. Inspect detail metadata and previews.

```powershell
python .\iconctl.py search "blue protective aura" --require subject=shield --limit 8 --json
python .\iconctl.py search --query 'subject:key AND color:(gold OR golden)' --json
python .\iconctl.py search --like icon_b5283aa4-b7a3-4d99-98be-231957fd5a7d --except icon_b5283aa4-b7a3-4d99-98be-231957fd5a7d --limit 8 --json
```

`--require` supports subject, action, state, effect, symbol, color, material.
Repeat it for alternatives (OR within a field, AND across fields). `--query`
is explicit SQLite FTS5, not SQL: phrases, Boolean operators, prefixes, `NEAR`
and the columns subject/action/state/effect/symbol/color/material/visible_text/
keywords/description/inferred_use/composition/title/collection are supported.
Ordinary text is ranking input, not a logical negation parser. `--like` supplies
one soft metadata example; it is not pixel-style similarity. `--except` omits
every rendition of a logical ID before the limit; it does not reserve the ID.
Collection and rendition-role filters are additional AND constraints. Limits
are 1-100. Invalid input is rejected; hard requirements are never relaxed.

## Inspect a result

```powershell
python ..\IndexedIconPack_v1\iconctl.py show icon_550e8400-e29b-41d4-a716-446655440000 --json
```

The result includes:

- permanent logical icon ID and lifecycle state;
- literal description and structured keywords;
- all available renditions;
- exact SHA-256 and dimensions for each rendition;
- thumbnail path;
- catalog and annotation provenance.

`keywords` contains namespaces including `subject`, `color`, `reviewed_term`,
`inferred_use`, and `uncertainty`. Read alternate terms and uncertainty alongside
the literal caption. Schematic art may reasonably support more than one name;
alternate labels are not asserted facets or proof of an exact visual property.

## Materialize one icon

Copy the preferred rendition into a project:

```powershell
python ..\IndexedIconPack_v1\iconctl.py materialize icon_550e8400-e29b-41d4-a716-446655440000 --to .\assets\icons\scan.png
```

Copy a specific pinned rendition:

```powershell
python ..\IndexedIconPack_v1\iconctl.py materialize icon_550e8400-e29b-41d4-a716-446655440000 `
  --sha256 sha256:0123456789abcdef... `
  --to .\assets\icons\scan.png
```

Materialization verifies the destination hash and writes a small receipt next to
the copied file. The receipt contains the stable handle, the materialized
rendition hash, the observed release ID and catalog revision, and original relative path; it
contains no icon-library or workstation path.

For an exact pin, the tool first verifies that the requested hash is a
historically published rendition of the supplied `icon_id`; the presence of the
same blob elsewhere in the catalog is insufficient.

The operation writes atomically and refuses to overwrite an existing destination
unless a future explicit replacement option is used. Agents must not infer or
construct destination paths from catalog metadata.

## Agent workflow

The consumer agent skill follows this sequence:

1. Read the target object's title, description, role, and requested visual constraints.
2. Search the catalog using literal and functional terms.
3. Inspect the top candidates and available renditions.
4. Return a stable handle by default; add an exact rendition pin when the caller requires reproducible pixels.
5. Record the selection in the consuming object's normal draft/versioning workflow.

An agent-facing response exposes both forms without confusing release provenance with identity:

```json
{
  "stable_handle": {
    "catalog_id": "indexed-icon-pack",
    "icon_id": "icon_550e8400-e29b-41d4-a716-446655440000"
  },
  "exact_pin": {
    "catalog_id": "indexed-icon-pack",
    "icon_id": "icon_550e8400-e29b-41d4-a716-446655440000",
    "rendition_sha256": "sha256:..."
  },
  "observed_release_id": "iip-r000001",
  "observed_catalog_revision": "sha256:...",
  "description": "A steel shield surrounded by pale blue frost.",
  "materialized_path": "assets/icons/scan.png"
}
```

`observed_release_id`, `observed_catalog_revision`, and `materialized_path`
are audit/output information, not part of the stable handle.

## Browse as a user

Start the local service:

```powershell
python .\iconctl.py serve
```

Open `http://127.0.0.1:8765` and:

- enter natural-language or keyword queries;
- navigate the grid by keyboard;
- inspect available descriptions and exact rendition facts;
- copy a stable handle or exact pin once a release is present.

The browser uses the same search function as the CLI/API, with typed filters,
seed-based alternatives, exclusions and shortfall feedback. Grids use thumbnails
instead of downloading every original.

## Read-only API

Implemented endpoints:

```text
GET /api/v1/version
GET /api/v1/search?q=shield+frost&limit=12
POST /api/v1/search
GET /api/v1/icons/{icon_id}
GET /api/v1/thumbnails/{icon_id}
GET /api/v1/blobs/{sha256}
```

The service has no mutation or assignment endpoint. A deployed application owns authorization, assignment, proposal, and publication behavior.

The POST route is read-only and accepts `text`, `query`, `like`, `require`,
`except`, `limit`, `collection`, `role`; for example:

```json
{"text":"icy protection","require":{"subject":["shield"]},"except":[],"limit":8}
```

Read detail with `GET /api/v1/icons/{icon_id}` before choosing. Record field-test
feedback as request, returned IDs, chosen ID (or none), reason, release ID and
search-profile hash. Do not log credentials or consumer-sensitive descriptions
without that application's permission.

A standalone service may skip the Python CLI and use a native read-only adapter
over `catalog.sqlite`. It validates the installed manifest, schema, and revision for
integrity but does not require a stable handle to match the revision where it
was first selected. It must enforce the FTS5 query contract, package-root path
boundary, rendition hashes, and the historical icon-to-rendition association.
This is an integration route for Go services such as AgentSmith when the
application provides a SQLite driver with FTS5 support. The read-only HTTP
API is the alternative. [DEPLOYMENT.md](DEPLOYMENT.md) defines how both routes
identify and verify the active release.

## Store a reference in a consumer

Store a stable handle when the assignment should survive package upgrades and
follow the current preferred rendition of the same logical icon:

```json
{
  "catalog_id": "indexed-icon-pack",
  "icon_id": "icon_550e8400-e29b-41d4-a716-446655440000"
}
```

If that icon is later retired, lookup still returns its retained last rendition
and reports the retired lifecycle state. It never redirects to a successor ID.

Add `rendition_sha256` when the owning record must reproduce exact pixels:

```json
{
  "catalog_id": "indexed-icon-pack",
  "icon_id": "icon_550e8400-e29b-41d4-a716-446655440000",
  "rendition_sha256": "sha256:..."
}
```

For AgentSmith-like versioned systems:

- Node and Skill definitions store the reference with their owning immutable definition version;
- Equipment presentation stores it with the Equipment version;
- Workbook presentation stores it with the published Workbook metadata;
- runtime-only decoration stores it in operational state;
- an agent proposal uses the same approval/publication path as the object it decorates.

Immutable published definitions normally add the exact hash. Draft or
operational presentation that intentionally follows approved package updates
may keep only the stable handle. In both cases, `icon_id` never changes.

## Add or update an icon set

General successor ingestion is deferred for this fixed-corpus field test. Do
not modify the installed package or generate replacement IDs with bootstrap.

Package maintainers use the separate ingestion skill and follow
[INGESTION.md](INGESTION.md) when that workflow is implemented. Ingestion runs outside the installed package,
requires the latest ever-published release as its base, and produces a new
candidate release plus an identity/change report for review.

## Verify and diagnose

Fast structural verification:

```powershell
python .\iconctl.py verify
```

Full byte verification:

```powershell
python .\iconctl.py verify --deep
```

Display release identity:

```powershell
python .\iconctl.py version --json
```

The `GET /api/v1/version` response and CLI JSON include `catalog_id`,
monotonic `release_id`, logical `catalog_revision`, supported `schema_version`,
and `release_manifest_sha256`. See [DEPLOYMENT.md](DEPLOYMENT.md) for the
response shape and upgrade/rollback rules.

A self-contained `release.json` is not proof that its directory was approved
or published. Consumers should use the expected manifest hash from the trusted
publication handoff or deployment pointer, as described in
[DEPLOYMENT.md](DEPLOYMENT.md).

A stable handle resolves across verified package upgrades. An unresolved ID,
unresolved pinned hash, corrupt copy, missing retained blob, or schema mismatch
is an error; the tool never silently changes logical identity or substitutes
different bytes for a pin.
