# Indexed Icon Pack: purpose and principles

> Sources: Project concept, Unknown; owner directions, Unknown; initial field-test report, 2026-10-11; public-data directions and proof, 2026-10-12
> Raw: [Concept](../../raw/overview/concept-one-pager.md); [Owner directions](../../raw/planning/2026-10-11-owner-directions.md); [Search report](../../raw/quality/2026-10-11-final-search-report.md); [Public-data decision](../../raw/planning/2026-10-12-public-data-directions.md); [Public catalog proof](../../raw/delivery/2026-10-12-public-catalog-proof.md)
> Updated: 2026-10-12

## The idea

Indexed Icon Pack turns large image collections into a portable, searchable
catalog for people and agents. Keep the library outside consuming projects;
search descriptions and structured properties, inspect candidates, then retain
a stable reference or copy only the selected exact image.

It separates expensive offline visual interpretation from lightweight runtime
retrieval. An image-capable model describes the art during catalog construction;
ordinary local search does not need a model, API key or database server. The
same library can serve multiple projects without being copied into every repo.

## Principles

- **Identity is not a filename.** Keep a permanent logical icon ID. Exact pixels
  have a separate SHA-256 rendition pin; duplicate bytes do not imply one identity.
- **Facts and interpretations are different.** Dimensions and hashes are
  deterministic facts. Literal captions, possible uses, alternative readings
  and uncertainty retain separate meanings and provenance.
- **Abstract images may have several useful readings.** Preserve plausible
  synonyms and schematic alternatives for retrieval and later LLM selection.
  Do not turn a speculative label into an asserted hard visual property.
- **Retrieve before choosing.** Search produces candidates, not confidence or
  proof of suitability. Consumers own assignment, reservation and approval.
- **Freeze released data.** Build new candidates outside installed releases;
  preserve prior IDs, raw observations and exact hashes. No silent replacement.
- **Automate quality checks.** No independent manual reviewer is required.
  Distinguish quality automation from the owner's authority over new spending,
  ambiguous identity changes and publication.
- **Measure before adding machinery.** Start with SQLite lexical retrieval.
  Embeddings, runtime rerankers and new infrastructure need demonstrated benefit.
- **Keep image bytes private.** Version generated metadata and the deployable
  SQLite index publicly, but distribute original images and thumbnails privately
  and materialize only selected images into consuming projects.

## What exists

The initial field-test corpus contains 6,250 stable logical icons in 127
collections, with 10,200 renditions backed by 10,193 unique PNG blobs. It retains
literal descriptions and exposes reviewed alternative terms and uncertainty.
Its useful-top-five acceptance result is 43/50 (86%) against an 80% requirement.
These are fixed-corpus results, not a guarantee for arbitrary future packs.

The concept snapshot still describes the catalog as pre-annotation and unfinished.

> **Status: Outdated** (2026-10-11)
> The initial field-test report supersedes that status. Its broader design for
> successor ingestion remains a target, not a claim of a completed ingestion tool.

## Non-goals

The public repository is both an explanation of the approach and a deployable
generated index. A clone includes the database, observations, identity records
and matching code in ordinary Git storage. Metadata search requires no cloud
access; downloading the private pixels is a separate authorized step.

This is not an image editor, a general asset-management platform, a model-training
system or a Unity-only package. Images are ordinary external files, not a large
SQLite BLOB store. A public code repository would not grant rights to the private
image collection. No production service or public repository is created by this wiki.

## See Also

- [Technical stack and contracts](../architecture/stack-and-contracts.md)
- [Verified release and limitations](../quality/release-evidence.md)
- [Distribution and repository proposal](../delivery/distribution-and-repository.md)
