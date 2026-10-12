# Public catalog preparation and metadata proof

> Source: Local implementation, preparation/check output, isolated Git-clone tests and ZIP inspection in the release preparation session
> Collected: 2026-10-12
> Published: 2026-10-12

## Scope and implemented flow

Repository: https://github.com/Darth-Carrotpie/ImageIndexer
The remote was publicly visible and empty when inspected. Local Git was already
initialized by the owner. Only .gitignore had been staged, and its worktree copy
had further edits. This preparation did not stage, commit, tag, configure a remote
or push in the owner's repository. An isolated temporary Git repository was
committed and cloned only to verify deployment checkout behavior.

The owner selected MIT and ordinary Git storage, not Git LFS. Public content
includes generated SQLite/FTS5 data, accepted descriptions and alternatives,
stable-ID and release manifests, source, tests, agent skills and safe docs.
Images, thumbnails, actual Nextcloud configuration, passwords, caches and private
work runs remain excluded. The README is an ordinary GitHub landing page linking
the wiki; the wiki stays in this repository rather than a separate GitHub Wiki.

tools/prepare_public_catalog.py implements prepare, check and zip. Preparation
uses the existing verified image-free bootstrap, copies non-image payload bytes,
adds the MIT license and image-rights notice, emits a blank nextcloud.example.json,
and exports accepted database observations without model calls or a DB rebuild.
Output must be new. The observation export is an inspection/diff format, not a
generic rebuild/import interface. General successor ingestion remains deferred.

The guard enforces metadata hashes, observation-export parity, required Git
candidates, private-file/known-secret patterns, no LFS or newline conversion on
pinned payloads, and a conservative 100 MiB per-file ceiling. GitHub documents a
50 MiB warning and a 100 MiB block threshold:
https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github
This is a bounded automated guard, not a complete secret or rights audit.

## Recorded preparation output

```json
{
  "database_bytes": 79372288,
  "observations": 6250,
  "public_bytes": 100316792,
  "public_files": 32,
  "release_manifest_sha256": "sha256:9cd603812b940176e11de110a833cdc033728b057882c27fa405aa75c6075bc3",
  "release_path": "release/iip-r000001",
  "status": "metadata_verified_images_not_checked"
}
```

SQLite SHA-256 remained 960187d88ffd4999aebb2608a7f8a2fcb2a1b8795122bce10edf90a7a6d51968.
Observation JSONL SHA-256: 63b759bf85b5f39c6a617fc59d529d605f77f762540468188bc298f169c4052e.
The public snapshot contains no PNG files. The manifest and original release
bytes were not rewritten; the four image archives are reused unchanged.

## Clone and regression evidence

- 53 tests passed in the workbench.
- 53 tests passed in an isolated Git clone with core.autocrlf=true.
- The clone had no image payload and no Nextcloud credentials when metadata
  verification and the query "gold key" succeeded.
- The clone retained the exact pinned SQLite and release-manifest hashes.
- New tests cover overwrite refusal, wrong pins, tampered exports/metadata,
  private files, secret patterns, file-size limits, forced image staging,
  byte-preserving attributes, and ZIP exclusion of installed images/config.
- A clean extraction of the revised standalone ZIP passed metadata validation.

Text search works without pixels. Previews, exact-image copying, deployment
activation and full deep verification require the private image payload. The
metadata-only status does not claim that those images have been installed.

## Revised optional standalone artifact

Path: work/public-distribution-v1/IndexedIconPack-iip-r000001-no-icons-public-v1.zip
Size: 27673922 bytes.
SHA-256: d0b57e70618cb3f1a1c8b59b7f2f7c368ad4d375ace424fcd6fd286549187149.
Contains the license, rights notice, accepted-observation export and example
configuration. No images or actual credentials are included. The older
25331175-byte no-icon ZIP is preserved as historical output, not overwritten.

## Owner handoff and versioning contract

After automated checks, the owner stages the checked candidate inventory,
inspects it, commits and pushes main to the supplied GitHub repository. Upload
the unchanged image ZIPs to a private read-only Nextcloud share. From a fresh
remote clone, configure private access, install, verify deeply, exercise search
and check clean Git status. Then tag code and data together and publish the
optional revised ZIP plus checksums as a prerelease. No upload has occurred here.

Keep one current snapshot per branch checkout and retain prior versions through
tags. Use a fresh deployment directory for another tag, hydrate its matching
images and verify the pins before activation. Git history still grows; future
ingestion must pass the ordinary-Git size gate. No silently enabled LFS.

Live Nextcloud access, a clone from the pushed remote, and owner publication
remain untested/manual. Local offline image restore has a separate proof record.
