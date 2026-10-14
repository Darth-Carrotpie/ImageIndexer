# Public repository and release process

> Sources: Owner public-data directions, 2026-10-12; public catalog preparation and verification, 2026-10-12; earlier distribution proposal, 2026-10-11; guided installer direction and proof, 2026-10-14; live install and update direction, 2026-10-14
> Raw: [Owner decision](../../raw/planning/2026-10-12-public-data-directions.md); [Implementation proof](../../raw/delivery/2026-10-12-public-catalog-proof.md); [Earlier proposal](../../raw/planning/2026-10-11-distribution-and-ingestion-proposal.md); [Clone image-restore proof](../../raw/delivery/2026-10-12-private-image-restore-proof.md); [Guided installer proof](../../raw/delivery/2026-10-14-guided-installer-proof.md); [Live install and update](../../raw/delivery/2026-10-14-live-install-and-update-direction.md)
> Updated: 2026-10-14

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
not the enclosing Unity project. Deploy into a dedicated directory outside
Unity's imported assets. Consumers can use the guided installer without cloning;
ordinary Git remains the public versioned source/data store.

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

## Owner step A: publish the updater release candidate

The earlier handoff described initializing Git and publishing the first commit.

> **Status: Outdated** (2026-10-14)
> The owner has published the guided installer and configured `origin`.
> Its live Nextcloud field test passed. Only the updater implementation needs
> committing and pushing; do not initialize or add the remote again.

This implementation turn has not staged, committed or pushed changes.

After the checks above pass, inspect and commit the public candidate set:

```powershell
git add -- .
git diff --cached --stat
git diff --cached --name-only
git diff --cached --check
git commit -m "Add verified side-by-side installation updates"
git push origin main
```

The `git add` step follows the publication guard, not an unchecked bulk add.
Never use `git add -f` for the catalog. Check `git remote -v`. If the remote has gained
commits, stop and reconcile normally; do not force-push.

The database exceeds GitHub's warning threshold but remains below its block
threshold. Use Git push, not browser file upload. The automatic source archive
now contains `catalog/` too; its entry point is there. The standalone no-icon
ZIP is only a convenient alternative.

## Owner step B: verify the updater against the live installation

Upload the four unchanged image ZIPs from
`work/nextcloud-distribution-v1/` to one password-protected, read-only Nextcloud
folder with downloads enabled. Preserve their exact filenames. Share access
only with people covered by the applicable asset rights.

The owner installed all four private image ZIPs through the live Nextcloud
share and received `Installation verified: release/iip-r000001`. Keep those
same image ZIPs; this updater change needs no archive or database rebuild. The
former fresh-clone and manual JSON-copy consumer steps remain superseded.

After pushing, update the original tested installation with Bash (Git Bash on
Windows, not PowerShell). Use its original directory, including if its name
contains spaces:

```sh
curl -fsSL https://raw.githubusercontent.com/Darth-Carrotpie/ImageIndexer/main/ImageIndexerInstaller.sh | bash -s -- update "/path/to/ImageIndexer"
```

The command creates a commit-named sibling of the original directory. It
copies the saved private share configuration, reuses verified cached image
ZIPs, deeply verifies the new release and runs `version` before switching the
local `.imageindexer-active.json` pointer. Check the printed source commit and
launch through the original directory's `ImageIndexerRun.py`. Rerun `update`
to confirm the current-commit no-op. For a rollback check, run:

```sh
curl -fsSL https://raw.githubusercontent.com/Darth-Carrotpie/ImageIndexer/main/ImageIndexerInstaller.sh | bash -s -- rollback "/path/to/ImageIndexer"
```

Rollback deeply verifies the previous installation and switches the pointer
back. The directories remain intact. Existing services need a restart to load
the selected version. No global PATH or environment variable is modified.
The [Nextcloud guide](nextcloud-installation.md) covers recovery and limits.

## Manual step C: tag and publish the field-test download

After the updater's real remote installation passes, tag the checked
source/data commit. For example, if the owner chooses `v0.1.0`:

```powershell
git tag -a v0.1.0 -m "ImageIndexer release"
git push origin v0.1.0
```

The prior handoff recommended attaching
`work/public-distribution-v1/IndexedIconPack-iip-r000001-no-icons-public-v1.zip`
and its adjacent `SHA256SUMS.txt` to a GitHub prerelease.

> **Status: Outdated** (2026-10-14)
> Prefer the guided repository installer for new consumers. A prerelease can
> document that entry point without attaching a standalone ZIP.

The existing standalone attachment predates guided configuration and the modern
Nextcloud authentication correction. It remains a historical fallback, not the
recommended new consumer path. To publish updated standalone bytes, use the
allowlisted ZIP builder with a new filename and checksum; do not replace a
previously published artifact in place. The guided installer uses the repository
snapshot and does not need a GitHub Release attachment.

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

The original one-path install command resumes its recorded source commit.
The explicit `update` command fetches the latest `main` commit into a sibling
and changes only a local launcher pointer after successful verification.
`rollback` reverses that pointer after checking the previous release. The
original install and previous version are retained. This installer pointer is
different from the deployment tool's external `active.json`; both differ from
Git tags and catalog release IDs. Choosing an arbitrary tagged installer
snapshot is not yet implemented.

## See Also

- [Purpose and principles](../overview/purpose-and-principles.md)
- [Nextcloud installation](nextcloud-installation.md)
- [Release evidence](../quality/release-evidence.md)
- [Implementation roadmap](../planning/implementation-roadmap.md)
- [Wiki maintenance](../overview/wiki-maintenance.md)
