# Nextcloud installation and current artifacts

> Sources: Nextcloud guide, Unknown; distribution build, restore proof and live audit, 2026-10-11; public catalog proof, 2026-10-12
> Raw: [Guide](../../raw/delivery/nextcloud-release-guide.md); [Build inventory](../../raw/delivery/2026-10-11-distribution-build.md); [Restore proof](../../raw/delivery/2026-10-11-distribution-verification.md); [Live audit](../../raw/quality/2026-10-11-live-workbench-audit.md); [Distribution recommendation](../../raw/planning/2026-10-11-distribution-and-ingestion-proposal.md); [Public catalog proof](../../raw/delivery/2026-10-12-public-catalog-proof.md); [Clone image-restore proof](../../raw/delivery/2026-10-12-private-image-restore-proof.md)
> Updated: 2026-10-12

## Implemented transport

The distribution wrapper restores the already verified `iip-r000001`. The
original release manifest, database, descriptions and pixels are unchanged.
Both originals and thumbnails are excluded from the no-icon package.

| Artifact | Exact bytes |
|---|---:|
| `IndexedIconPack-iip-r000001-images-001.zip` | 999916163 |
| `IndexedIconPack-iip-r000001-images-002.zip` | 999830739 |
| `IndexedIconPack-iip-r000001-images-003.zip` | 999813019 |
| `IndexedIconPack-iip-r000001-images-004.zip` | 685494505 |
| `IndexedIconPack-iip-r000001-no-icons.zip` (historical wrapper) | 25331175 |
| `IndexedIconPack-iip-r000001-no-icons-public-v1.zip` (current public wrapper) | 27673922 |

Each image ZIP is independently extractable and below the 1,000,000,000-byte
cap, including headers. SHA-256 values are preserved in the raw build and
verification snapshots. The workbench's `work/nextcloud-distribution-v1/`
contains the deliverables and `SHA256SUMS.txt`; it is private generated output,
not something to commit to a source repository.

The revised public ZIP and its new `SHA256SUMS.txt` are under
`work/public-distribution-v1/`. They reference the same four unchanged image
archives. The new wrapper includes the MIT license, image-rights notice,
observation export and blank configuration example. Its SHA-256 is
`d0b57e70618cb3f1a1c8b59b7f2f7c368ad4d375ace424fcd6fd286549187149`.

The earlier flow required downloading a separate ZIP to obtain the database.

> **Status: Outdated** (2026-10-12)
> A public Git clone now includes the image-free catalog under `catalog/`.
> The revised ZIP is optional. The original wrapper remains historical evidence,
> not the recommended new public attachment.

`BUILD.json` records the intermediate built state. `VERIFICATION.json` is the
subsequent successful restore proof; its readiness supersedes the build's
pending-proof status without rewriting that earlier record.

## Configure and install

Upload the four unchanged image ZIPs to one read-only, password-protected
Nextcloud folder with downloads enabled. Preserve their names. Clone the public
repository or extract the revised no-icon ZIP. From `catalog/` in a clone, or
the standalone ZIP's root, copy `nextcloud.example.json` to `nextcloud.json`
and enter the private folder WebDAV URL/token. Distribute configuration privately
and the password separately. Nothing secret goes into the tracked example.

Before installing images, text search and metadata lookup already work. The
publication guard reports `metadata_verified_images_not_checked`; image previews,
materialization, activation and deep verification require the private payload.

From the extracted wrapper directory:

```powershell
python -B download_icons.py
```

Python 3.11 or newer with SQLite FTS5 is sufficient. The password prompt is
hidden; unattended use reads `IIP_NEXTCLOUD_PASSWORD`. No credential belongs in
the URL, command arguments or release files. Allow at least 8 GB of free space
for the installed catalog and cached archives.

After the downloader reports successful deep verification:

```powershell
python -B release/iip-r000001/iconctl.py --package release/iip-r000001 version --json
python -B release/iip-r000001/iconctl.py --package release/iip-r000001 search "gold key" --limit 5 --json
python -B release/iip-r000001/iconctl.py --package release/iip-r000001 serve
```

Keep the release directory immutable. Configuration, cache and temporary files
remain outside `release/`. Do not re-zip a hydrated installation for public delivery.

## Recovery and boundaries

Rerunning reuses intact images and archives, resumes partial transfers when
Range is supported, and safely restarts when it is not. Conflicting installed
files are not overwritten. Hash checks occur before extraction and on restored
files; deep catalog verification runs before success is reported.

For offline installation, use `--offline --archives-dir <copied-zips>` with the
same downloader. There is no automatic network retry loop or partial/on-demand
image download mode: hydration installs the full image payload. Metadata-only
search is usable independently before hydration.

HTTPS certificate validation is mandatory; redirects are refused to avoid
forwarding credentials. Use the canonical folder WebDAV endpoint. The local
filesystem must support hard links, such as NTFS, ext4 or APFS; FAT/exFAT is not
supported by the atomic extraction path. Stale lock recovery requires confirming
that no installer is running. Exact recovery details remain in the preserved guide.

Local restore and repeat-install checks passed. The real Nextcloud URL and
token are still blank, so cloud connectivity/authentication is an open check.
Hashes detect corruption against trusted pins; they are not digital signatures.

## See Also

- [Distribution and repository proposal](distribution-and-repository.md)
- [Release evidence](../quality/release-evidence.md)
- [Implementation roadmap](../planning/implementation-roadmap.md)
