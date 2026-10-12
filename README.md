# Indexed Icon Pack

**[Read the project wiki](wiki/index.md)** for the purpose, architecture,
release evidence, distribution guide and implementation roadmap.

A portable, searchable icon catalog for people and AI agents. Keep a large
image library outside your projects, find useful candidates by description and
visual properties, then retain a stable reference or copy only the exact image
you choose.

## Why this exists

A folder of thousands of images is easy to store and hard to use. Filenames
rarely describe everything an icon depicts, especially when the artwork is
abstract or schematic. Copying an entire asset library into every project also
adds bulk without helping anyone find the right image.

Indexed Icon Pack separates visual interpretation from everyday retrieval.
An image-capable model describes the artwork during catalog construction.
Consumers then search those descriptions and structured properties locally,
without a model, API key or database server. An LLM can use the returned
descriptions and alternative readings to make a final selection, but is not
required to run search.

The catalog is editor-agnostic: it can serve Unity projects, other applications
and agent workflows without becoming part of their runtime.

## Principles

- **Stable identity, exact pixels.** A permanent logical icon ID identifies the
  icon; a separate SHA-256 pin identifies an exact rendition.
- **Facts are not interpretations.** Keep dimensions and hashes distinct from
  captions, possible uses, alternative readings and uncertainty.
- **Preserve plausible alternatives.** Abstract artwork may have several useful
  descriptions. Keep grounded synonyms without turning a speculative reading
  into a hard visual property.
- **Retrieve before choosing.** Search returns candidates and match reasons,
  not a guarantee of suitability. The consuming person or agent makes the choice.
- **Keep releases immutable.** Preserve existing IDs, observations and exact
  image bytes; build changes separately instead of silently replacing releases.
- **Automate quality checks.** Use repeatable tests and automated evaluation,
  without requiring independent manual reviewers. Spending and publication
  remain owner decisions.
- **Keep the runtime simple.** Start with local SQLite search; add embeddings,
  model-based reranking or infrastructure only when measurements justify them.
- **Keep image libraries out of source history.** Distribute binaries separately
  and copy only selected images into consuming projects.

See [Purpose and principles](wiki/overview/purpose-and-principles.md) for the
full rationale.

## What works today

The initial field-test catalog contains 6,250 logical icons in 127 collections,
with 10,200 renditions. It provides description and structured-property search,
similarity queries with exclusions, detailed metadata, a local browser and
read-only HTTP API, and exact-image copying with verification receipts.

The runtime uses Python 3.11+, SQLite FTS5 and a lightweight HTML/JavaScript
browser. Image preparation uses Pillow at build time; consumers do not need it.
There is no required vector database, Docker service or Unity dependency.
See [Technical stack and contracts](wiki/architecture/stack-and-contracts.md).

The recorded automated acceptance result for `iip-r000001` is **43/50 (86%)**,
above the **80% initial-release threshold**, with 10/10 negative checks and zero
contract violations. Success means at least one plausible useful result in the
first five, not necessarily the exact preselected icon. This is fixed-corpus
evidence, not a guarantee for arbitrary queries or future packs; automated
judgments can also be wrong.

Local release and download/restore checks have passed. Live Nextcloud
installation remains a release gate. General multi-package ingestion and
successor publication are planned, not complete.
See [Release evidence and limitations](wiki/quality/release-evidence.md).

## Get started

Clone [ImageIndexer](https://github.com/Darth-Carrotpie/ImageIndexer). The
repository includes the generated SQLite database and FTS5 index, identity and
release manifests, and a readable export of all accepted observations and
alternatives. These are public data, stored in ordinary Git; Git LFS is not used.

With Python 3.11+ and SQLite FTS5 available:

```sh
git clone https://github.com/Darth-Carrotpie/ImageIndexer.git
cd ImageIndexer
python -B tools/prepare_public_catalog.py check --repository .
python -B catalog/release/iip-r000001/iconctl.py --package catalog/release/iip-r000001 search "gold key" --limit 5 --json
```

Text search and metadata work immediately without credentials. Image previews,
copying selected images and full release verification require the private
images, including thumbnails. No model call or database rebuild is needed.

For authorized image access, copy `catalog/nextcloud.example.json` to
`catalog/nextcloud.json`, add the privately supplied share URL/token, and run:

```sh
python -B catalog/download_icons.py
python -B catalog/release/iip-r000001/iconctl.py --package catalog/release/iip-r000001 serve
```

Enter the password at the hidden prompt; wait for `Installation verified`
before using images. Credentials, restored images and caches remain ignored by
Git. Never force-add them. The separately downloadable no-icon ZIP is an
alternative to cloning, not the only home of the catalog.

The [installation guide](wiki/delivery/nextcloud-installation.md) covers
configuration, disk requirements, offline installation and recovery.
The [distribution guide](wiki/delivery/distribution-and-repository.md) explains
the source/installer/image split.

## Development and next steps

Run the public-data guard and automated suite from the source directory:

```powershell
uv.exe run --no-project python -B tools/prepare_public_catalog.py check --repository .
uv.exe run --no-project --with-requirements requirements-build.txt python -B -m unittest discover -s tests
```

`catalog/observations.jsonl` exposes the accepted descriptions and alternatives
for inspection and diffing. It is not yet a general-purpose import/rebuild
interface. Keep one current catalog snapshot per checkout and tag code and
data together. Use a fresh checkout for a different tagged deployment;
preserve its release/profile pins and verify its matching images before use.
The public guard stops files at the 100 MiB safety ceiling so future growth
cannot silently break ordinary GitHub storage. Do not normalize line endings
inside the pinned `catalog/release/` payload.

Next comes validation against the actual cloud share, field-test feedback and
an append-only path for adding packages without changing existing identities.
No full-corpus rebuild is required just to distribute the current release.

- [Implementation roadmap](wiki/planning/implementation-roadmap.md)
- [Additional-package ingestion plan](wiki/planning/package-ingestion.md)
- [Documentation maintenance and evidence](wiki/overview/wiki-maintenance.md)

The wiki holds the detailed design, evidence and decision history; this README
is the short project introduction.

## License

The project's original source code and documentation are licensed under the
[MIT License](LICENSE).

Third-party dependencies, quoted source material, icon artwork, thumbnails and
vendor asset packs retain their respective rights and licenses; they are not
relicensed by this project's MIT license. Access to the code or downloader does
not grant rights to the image collection. Image access and permitted use remain
separate from the software license.
