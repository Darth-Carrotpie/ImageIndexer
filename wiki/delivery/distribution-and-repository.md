# Public repository and release process

> Sources: Owner public-data directions, 2026-10-12; public catalog preparation and verification, 2026-10-12; earlier distribution proposal, 2026-10-11
> Raw: [Owner decision](../../raw/planning/2026-10-12-public-data-directions.md); [Implementation proof](../../raw/delivery/2026-10-12-public-catalog-proof.md); [Earlier proposal](../../raw/planning/2026-10-11-distribution-and-ingestion-proposal.md); [Clone image-restore proof](../../raw/delivery/2026-10-12-private-image-restore-proof.md)
> Updated: 2026-10-12

## Approved boundary

[ImageIndexer](https://github.com/Darth-Carrotpie/ImageIndexer) is the public
home of both generated data and source. The owner selected MIT for the software
and ordinary Git storage, without Git LFS.

| Public and versioned together | Private and excluded |
|---|---|
| Code, tests, agent skills, documentation and safe evidence | Work candidates, raw API runs and private feedback |
| SQLite database including its FTS5 index | Original images and thumbnails |
| Accepted observations, alternatives, stable IDs and manifests | Vendor source and permission records |
| Downloader, archive hashes and blank configuration template | Real cloud configuration, passwords and download caches |

The source-only proposal previously excluded every database and put the useful
catalog only in a separate release download.

> **Status: Outdated** (2026-10-12)
> The owner requires a cloneable public index. The deliberate exception is the
> pinned database under `catalog/release/`; private working databases remain
> ignored. The old proposal remains preserved as raw evidence.

Cloning supplies a searchable metadata example and deployment index. Only
authorized users can fetch images. Public metadata and MIT code do not confer
rights to vendor artwork. The repository belongs at the package-workbench root,
not the enclosing Unity project; a deployment clone should live outside Unity.

## Prepared layout and checks

`catalog/` holds the image-free snapshot: downloader, blank example config,
MIT license and image-rights notice, distribution manifest, readable observation
export, and the byte-preserved release under `release/iip-r000001/`.

The database is 79372288 bytes; its FTS5 index is already built. The export
contains 6250 accepted observation records. It is useful for inspection/diffs,
but is not a general-purpose rebuild/import command. No model calls or database
rebuild were needed to prepare it.

`.gitattributes` disables text conversion and filters for pinned release files.
This is necessary because even documentation inside the release is hash-pinned.
Keep these attributes; do not normalize an immutable payload on Windows checkout.

From the source checkout:

```powershell
uv.exe run --no-project python -B tools/prepare_public_catalog.py check --repository .
uv.exe run --no-project --with-requirements requirements-build.txt python -B -m unittest discover -s tests
```

The guard checks metadata hashes, export parity, required Git candidates,
private-file/known-secret patterns and a conservative 100 MiB per-file ceiling.
It is not a full rights or secret audit. Its metadata-only result does not
claim that images are installed. Full verification remains the downloader's
post-install gate. Future growth must pass the size gate or trigger a new
storage decision; do not silently switch to LFS or omit the database.

## Manual step A: commit and push the prepared repository

The owner has initialized local Git. Agent work has not changed its staging,
committed, added a remote or pushed. At preparation time only the older
`.gitignore` was staged; stage the updated rules with the rest of the files.

After the checks above pass, inspect and commit the public candidate set:

```powershell
git add -- .
git diff --cached --stat
git diff --cached --name-only
git diff --cached --check
git commit -m "Prepare public catalog and image-indexing tools"
git branch -M main
git remote add origin https://github.com/Darth-Carrotpie/ImageIndexer.git
git push -u origin main
```

The `git add` step follows the publication guard, not an unchecked bulk add.
Never use `git add -f` for the catalog. If `origin` has already been configured,
check `git remote -v` and skip the add when it matches. If the remote has gained
commits, stop and reconcile normally; do not force-push.

The database exceeds GitHub's warning threshold but remains below its block
threshold. Use Git push, not browser file upload. The automatic source archive
now contains `catalog/` too; its entry point is there. The standalone no-icon
ZIP is only a convenient alternative.

## Manual step B: upload and configure private images

Upload the four unchanged image ZIPs from
`work/nextcloud-distribution-v1/` to one password-protected, read-only Nextcloud
folder with downloads enabled. Preserve their exact filenames. Share access
only with people covered by the applicable asset rights.

Make a fresh clone in a new directory outside Unity, then verify public search:

```powershell
git clone https://github.com/Darth-Carrotpie/ImageIndexer.git
cd ImageIndexer
uv.exe run --no-project python -B tools/prepare_public_catalog.py check --repository .
uv.exe run --no-project python -B catalog/release/iip-r000001/iconctl.py --package catalog/release/iip-r000001 search "gold key" --limit 5 --json
```

Copy `catalog/nextcloud.example.json` to `catalog/nextcloud.json`, fill the
private folder WebDAV URL/token, and use the password prompt:

```powershell
uv.exe run --no-project python -B catalog/download_icons.py
uv.exe run --no-project python -B catalog/release/iip-r000001/iconctl.py --package catalog/release/iip-r000001 verify --deep --json
uv.exe run --no-project python -B catalog/release/iip-r000001/iconctl.py --package catalog/release/iip-r000001 serve
git status --short
```

Require installation verification and clean Git status after hydration. The
[Nextcloud guide](nextcloud-installation.md) supplies endpoint and recovery
details. Live cloud authentication still needs this owner-supplied setup.

## Manual step C: tag and publish the field-test download

After the real remote install passes, tag the checked source/data commit:

```powershell
git tag -a iip-r000001-public-v1 -m "Public catalog field test"
git push origin iip-r000001-public-v1
```

Create a GitHub prerelease using that tag. Attach
`work/public-distribution-v1/IndexedIconPack-iip-r000001-no-icons-public-v1.zip`
and the adjacent `SHA256SUMS.txt`. This revised wrapper includes the license,
rights notice, example config and observation export. The earlier no-icon ZIP
is preserved as historical output, not the recommended public attachment.

Do not attach image ZIPs, private configuration or a general ZIP of a hydrated
checkout. The explicit ZIP builder excludes those files. Deliver actual
configuration privately and the password separately. No upload or public
release has been performed by the preparation tools.

## Versioning

Keep one current generated snapshot in each branch checkout and tag code,
data, manifests and downloader together. Previous tags retain earlier snapshots;
do not keep accumulating every historical database in the current tree.
Full Git history still grows, so monitor it before future package ingestion.

Use a fresh checkout directory when switching a deployed catalog version;
ignored images from one version should not be mistaken for another. Verify the
matching images and release/profile pins before activation. A Git tag,
catalog release ID, logical revision and deployment's active pointer are
different identities. Preserve the [deployment contract](../architecture/stack-and-contracts.md).

## See Also

- [Purpose and principles](../overview/purpose-and-principles.md)
- [Nextcloud installation](nextcloud-installation.md)
- [Release evidence](../quality/release-evidence.md)
- [Implementation roadmap](../planning/implementation-roadmap.md)
- [Wiki maintenance](../overview/wiki-maintenance.md)
