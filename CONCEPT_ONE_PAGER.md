# Indexed Icon Pack

Concept and target design; the v1 catalog is currently an unpublished,
pre-annotation candidate, not a finished release.

## A portable, searchable icon catalog for agents and people

Large icon libraries are useful but awkward to work with. Filenames rarely explain what an icon depicts, browsing thousands of images is slow, and copying the full collection into every project wastes repository space. Agents face an additional problem: they need structured metadata and stable identifiers, not a visual folder they cannot search reliably.

Indexed Icon Pack turns an ordinary image collection into an external, content-addressed catalog that can sit beside any project and serve many projects without becoming part of them.

## The idea

Keep the original icon files as files. Build a small SQLite catalog over them containing:

- permanent logical icon IDs that are never regenerated or reused;
- SHA-256 hashes for exact image renditions;
- dimensions, format, transparency, and other deterministic facts;
- generated titles, literal descriptions, and searchable keywords;
- collection, category, variant, and source information;
- a permanent catalog ID, logical catalog revision, schema version, and
  separately identified immutable package release;
- a full-text search index.

A logical icon may have several renditions, such as transparent, framed,
thumbnail, or alternate-resolution versions. Its logical identity remains
stable while every exact file is independently hash-addressed. An append-only
identity registry carries those IDs into every future release; removed icons
remain as tombstones instead of freeing an ID for reuse.

An image-input-capable LLM agent produces descriptions and visual keywords
during catalog construction rather than people writing them icon by icon.
Deterministic tools prepare and verify the files and index, but do not pretend
to see their subject matter. Before the first image-model call, the maintainer
presents the corpus size, image dimensions, model options, and estimated cost
for an owner decision. A small quality/cost pilot precedes full annotation.
Each accepted annotation records its model and pipeline provenance, keeping
machine interpretation separate from exact file facts.

## How it works

```text
Icon files
    |
    v
Index builder ------> manifest + SQLite catalog + thumbnails
                                |
                                v
                      CLI or read-only service
                           |             |
                           v             v
                      Agent skill     User browser
                           |             |
                           +------v------+
                                  |
                                  v
                       Stable icon handle,
                       exact pin, or verified copy
```

SQLite with FTS5 provides fast ranked search without requiring a database server. The original images remain outside the database, avoiding a duplicated multi-gigabyte BLOB store. A small cross-platform CLI exposes the same operations to agents, scripts, CI jobs, and applications.

A stable handle survives package upgrades and deployment changes:

```json
{
  "catalog_id": "indexed-icon-pack",
  "icon_id": "icon_550e8400-e29b-41d4-a716-446655440000"
}
```

When exact pixels matter, the same handle adds a content hash:

```json
{
  "catalog_id": "indexed-icon-pack",
  "icon_id": "icon_550e8400-e29b-41d4-a716-446655440000",
  "rendition_sha256": "sha256:..."
}
```

The logical `catalog_revision` identifies catalog content, while a monotonic
`release_id` and manifest hash identify the exact immutable package. The
schema version tells a consumer whether it can read that package. A consumer
can install N+1 beside N, verify it, switch an external active pointer, and
report the active IDs through a version endpoint. Publication of a newer
release and local activation are separate; rollback changes the active
pointer without rewriting icon references or publication history. Paths are
runtime configuration. The catalog may live in a sibling directory, mounted
volume, or shared cache without changing references held by consumers.

## Search and selection

Users and agents can search for literal subjects, appearance, state, effects, colors, composition, or likely interface purpose, for example:

```text
blue shield with frost aura
warning symbol red
open treasure chest glowing
healing action green
```

Search initially uses generated descriptions, controlled keywords, synonyms, categories, and SQLite full-text ranking. Vector search can be added later only if measured search quality shows that lexical retrieval is insufficient.

During development, an agent can search the neighboring catalog, inspect candidates, and materialize only the selected rendition into a project. The copy is verified against its SHA-256 hash and accompanied by a small provenance receipt.

A deployed application can mount the same catalog read-only, offer searchable thumbnails to users, and let an agent propose icons for versioned objects such as skills, equipment, actions, effects, or workflows.

Maintainer agents can also ingest new sets through a separate offline workflow:
stage PNGs, reconcile them against the previous identity registry, stop on
ambiguous matches or before a new image-model run, annotate only new or changed
icons after owner approval, build a candidate, and verify backward
compatibility before publishing another immutable release.

## Benefits

- Keeps large binary collections out of ordinary source repositories.
- Makes visually described icons searchable by agents and humans.
- Preserves logical links through permanent IDs and exact pixels through optional hashes.
- Works offline with a single database file and ordinary image files.
- Requires no database server for local or single-host use.
- Separates catalog construction from lightweight runtime search.
- Allows the package and storage layout to evolve without rewriting stable consumer handles.

## Non-goals

Indexed Icon Pack is not a general-purpose digital asset manager, image editor, or model-training system. It does not copy the full library into every consumer, store originals as SQLite BLOBs, require runtime image analysis, or let icon selection bypass the consuming product's versioning and approval rules.

The catalog answers: **Which icon is this, what does it show, where is its exact rendition, and how can I retrieve it?** The consuming project remains responsible for deciding where that reference belongs and when a proposed selection becomes published state.
