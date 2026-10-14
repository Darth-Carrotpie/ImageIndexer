# Nextcloud installation and current artifacts

> Sources: Nextcloud guide, Unknown; distribution build, restore proof and live audit, 2026-10-11; public catalog proof, 2026-10-12; guided installer direction and proof, 2026-10-14
> Raw: [Guide](../../raw/delivery/nextcloud-release-guide.md); [Build inventory](../../raw/delivery/2026-10-11-distribution-build.md); [Restore proof](../../raw/delivery/2026-10-11-distribution-verification.md); [Live audit](../../raw/quality/2026-10-11-live-workbench-audit.md); [Distribution recommendation](../../raw/planning/2026-10-11-distribution-and-ingestion-proposal.md); [Public catalog proof](../../raw/delivery/2026-10-12-public-catalog-proof.md); [Clone image-restore proof](../../raw/delivery/2026-10-12-private-image-restore-proof.md); [Guided installer proof](../../raw/delivery/2026-10-14-guided-installer-proof.md)
> Updated: 2026-10-14

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

## Guided installation

Upload the four unchanged image ZIPs to one read-only, password-protected
Nextcloud folder with downloads enabled. Preserve their names. The owner reports
GitHub and Nextcloud are prepared; the public source download is verified, but
private-share authentication still needs a real-server check.

The former consumer instructions required cloning and copying the example JSON.

> **Status: Outdated** (2026-10-14)
> The owner requested one guided installer. Cloning remains optional for
> development; creating configuration manually is no longer required.

After the installer change is committed and pushed, run in Bash:

```sh
curl -fsSL https://raw.githubusercontent.com/Darth-Carrotpie/ImageIndexer/main/ImageIndexerInstaller.sh | bash -s -- "/path/to/ImageIndexer"
```

On Windows use Git Bash and a path such as `"C:/ImageIndexer"`, not native
PowerShell. Linux/macOS/WSL use the same Bash entry point. Python 3.11+ with
SQLite FTS5 is required; existing uv can supply it. No system packages are
installed. Allow at least 8 GB for images and cached archives.

The script downloads a commit-pinned source/catalog snapshot without Git,
validates metadata, and asks whether to install images. Paste the private folder
share link and type the password at the hidden prompt. The downloader writes
`catalog/nextcloud.json` automatically without storing the password. An instance
subpath is preserved. Modern public DAV uses `anonymous` authentication; a
legacy `/public.php/webdav/` URL asks for the separate share token.

Keep links/tokens private and passwords separate. Nothing secret goes into the
tracked example. This flow trusts the current `main` entry point; its hashes
detect corruption, not repository compromise. The historical standalone ZIPs
above are unchanged and do not contain this newer guided setup/authentication fix.

Before installing images, text search and metadata lookup already work. The
publication guard reports `metadata_verified_images_not_checked`; image previews,
materialization, activation and deep verification require the private payload.

From `catalog/` in an existing source snapshot, run the downloader directly if
needed; it also prompts to create missing configuration:

```powershell
python -B download_icons.py
```

Python 3.11 or newer with SQLite FTS5 is sufficient. The password prompt is
hidden; unattended use reads `IIP_NEXTCLOUD_PASSWORD` with preconfigured JSON. No credential belongs in
the URL, command arguments or release files. Allow at least 8 GB of free space
for the installed catalog and cached archives. Use `--configure` to replace
saved configuration after confirmation. The installer prints a browser command
with the correct installed path; the commands below assume `catalog/` as cwd.

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

The top-level installer resumes only its recorded snapshot. It refuses unrelated
nonempty directories and symlink/junction paths; use a new destination for a
newer source version. An interrupted source copy without an install receipt is
also refused. Remove `.installer.lock` only after confirming no installer runs.

For offline installation, use `--offline --archives-dir <copied-zips>` with the
same downloader. There is no automatic network retry loop or partial/on-demand
image download mode: hydration installs the full image payload. Metadata-only
search is usable independently before hydration.

HTTPS certificate validation is mandatory; redirects are refused to avoid
forwarding credentials. Use the canonical folder WebDAV endpoint. The local
filesystem must support hard links, such as NTFS, ext4 or APFS; FAT/exFAT is not
supported by the atomic extraction path. Stale lock recovery requires confirming
that no installer is running. Exact recovery details remain in the preserved guide.

Local restore and repeat-install checks passed. The new installer passed a live
GitHub source download and Windows Git Bash terminal/pipeline checks, with
private images declined. Real Nextcloud connectivity/authentication is still
an open check; native Linux/macOS/WSL execution was not exercised.
Hashes detect corruption against trusted pins; they are not digital signatures.

## See Also

- [Distribution and repository proposal](distribution-and-repository.md)
- [Release evidence](../quality/release-evidence.md)
- [Implementation roadmap](../planning/implementation-roadmap.md)
