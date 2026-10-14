# Indexed Icon Pack: public index, private images

The public repository contains code and the generated, searchable catalog.
Only image bytes (including thumbnails) and credentials stay private. Ordinary
Git storage is used: no Git LFS client, model call or database rebuild is needed
to use the current catalog.

The same image-free snapshot is available as a standalone no-icon ZIP. A Git
clone stores it under `catalog/`; in the standalone ZIP it is the top-level
directory. Run the following consumer commands from that directory.

## Recommended: one-command installation

No Git clone or manual JSON setup is needed. In Bash on Linux/macOS/WSL or
Git Bash on Windows (not directly in PowerShell), run:

```sh
curl -fsSL https://raw.githubusercontent.com/Darth-Carrotpie/ImageIndexer/main/ImageIndexerInstaller.sh | bash -s -- "/path/to/ImageIndexer"
```

Use `"C:/ImageIndexer"` as a Windows example. Requires curl, Bash and Python
3.11+ with SQLite FTS5, or an existing `uv` which can supply Python. No system
package installation or administrator rights are needed. Choose a new or empty
dedicated directory outside Unity's imported assets, on a hard-link-capable disk.

The installer fetches one commit-pinned public source/catalog snapshot, checks
the metadata, and prompts for image installation, the private folder share link
and a hidden password. It writes configuration, never the password. Declining
image installation leaves usable metadata, not a fully verified image release.
It prints the browser command after success. Rerun the same command/path to
resume; use a new path for a newer snapshot. The public entry point follows
`main`; review it before running if required by your deployment policy.

The remaining commands apply to an existing snapshot (`catalog/`) or standalone
wrapper. Historical published ZIPs are not silently updated by this change.

## Search without images

Python 3.11+ with SQLite FTS5 is required.

```sh
python -B release/iip-r000001/iconctl.py --package release/iip-r000001 search "gold key" --limit 5 --json
python -B release/iip-r000001/iconctl.py --package release/iip-r000001 version --json
```

This is metadata-only use: descriptions, structured properties and search work,
but previews, exact-image copying and full release verification require the
private image payload. A manifest being present is not proof that images have
been installed. The SQLite database includes the FTS5 index; `observations.jsonl`
is a deterministic, readable export of accepted observations and alternatives,
not a new annotation run or an implemented generic rebuild/import interface.

## Install private images

1. Obtain access to the image archive share only if your asset license permits
   it. Allow at least 8 GB of free disk space for installed images and cached ZIPs.
2. Run:

   ```sh
   python -B download_icons.py
   ```

   When configuration is missing, paste the folder link, such as
   `https://cloud.example/nextcloud/s/TOKEN`. The installation subpath and share
   token are extracted automatically. A full `/public.php/dav/files/TOKEN/`
   URL also works. For a legacy `/public.php/webdav/` URL, enter the share token
   separately when asked. The server must allow public-share WebDAV downloads.

   Enter the password at the hidden prompt, or supply `IIP_NEXTCLOUD_PASSWORD`
   through your secret environment. Wait for `Installation verified`. Use
   `python -B download_icons.py --configure` to replace saved configuration.
   Older standalone wrappers without guided setup still require copying/editing
   their example JSON; use the current installer for the guided flow.

   Modern public-share DAV uses the `anonymous` Basic Auth username; legacy
   WebDAV uses the token. See the [Nextcloud WebDAV documentation](https://docs.nextcloud.com/server/latest/developer_manual/client_apis/WebDAV/basic.html).
3. Open the browser or verify the fully installed release:

   ```sh
   python -B release/iip-r000001/iconctl.py --package release/iip-r000001 serve
   python -B release/iip-r000001/iconctl.py --package release/iip-r000001 verify --deep --json
   ```

Keep everything under `release/` immutable. The downloader adds only the
manifest-pinned images; private configuration and caches remain outside it.
In a Git checkout, restored images and thumbnails are ignored, not tracked.
Never commit them or re-zip a hydrated installation with a general ZIP tool.

## Recovery and offline installation

Rerun the downloader after interruption. Verified files are reused, partial
transfers resume when supported, and safe restart is used when Range is ignored.
There is no automatic retry loop. Corrupt archives and conflicting installed
files stop the process; investigate the named file or use a new install directory.
The top-level installer preserves its snapshot identity in
`.imageindexer-install.json`; it never upgrades an existing installation.
If a crash occurs while the public snapshot is being copied, an incomplete
directory without this receipt is refused; use a new directory. Remove a stale
`.installer.lock` only after confirming no installer is running.

For ZIPs supplied locally:

```sh
python -B download_icons.py --offline --archives-dir /path/to/private-image-zips
```

Use NTFS, ext4, APFS or another filesystem supporting hard links; FAT/exFAT is
not supported by atomic extraction. Keep installation paths free of symlinks
and junctions. The cache must stay outside `release/`. Remove a stale
`.download.lock` only after confirming no downloader is running.

HTTPS certificate validation is required. Redirects are refused to avoid
forwarding credentials; use the canonical endpoint and trust any private CA.
Authentication layers beyond a password-protected Nextcloud share are not
implemented. The actual server must be tested before granting tester access.

## Maintainers: publishing and versioning

The source repository is
[ImageIndexer](https://github.com/Darth-Carrotpie/ImageIndexer).
The repo's `README.md` is the landing page. This document is also copied into
the standalone installer; `RELEASE_README.md` is a separate, pinned catalog
README. Keep all three source documents in Git.

From the source checkout, validate the metadata and Git candidate inventory:

```sh
python -B tools/prepare_public_catalog.py check --repository .
```

This checks pinned non-image payloads, observation export parity, the blank
configuration template, ordinary-Git byte-preserving attributes, file sizes
and known private-file/secret patterns. It does not claim images are installed
or constitute a complete rights/security audit. Keep data files below the
100 MiB safety ceiling; expansion beyond it requires a new storage decision,
not silently enabling LFS or omitting data.

The preparation command copies an existing verified image-free bootstrap to a
new output, preserving the release and SQLite bytes:

```sh
python -B tools/prepare_public_catalog.py prepare --bootstrap work/nextcloud-distribution-v1/bootstrap --expected-manifest-sha256 9cd603812b940176e11de110a833cdc033728b057882c27fa405aa75c6075bc3
```

It refuses an existing output; do not overwrite an installed catalog. General
successor ingestion remains separate future work. Keep one current snapshot
per branch checkout and tag code, database, manifests and downloader together.
Use a fresh clone/check-out directory for another tagged deployment, install
its matching images, then validate before activation. A Git tag is not the same
thing as a catalog release ID or an activation pointer.

Use the explicit image-free ZIP builder, including after local hydration:

```sh
python -B tools/prepare_public_catalog.py zip --output work/IndexedIconPack-iip-r000001-no-icons-public-v1.zip
```

The ZIP allowlist includes the MIT license and this rights notice and excludes
credentials, caches and images. Publish its new checksum; do not replace the
older transport ZIP under an already published filename. Upload the four
original image ZIPs unchanged to a private, read-only Nextcloud folder. No image
archive or immutable catalog rebuild is needed for this transport change.

## License and image rights

Original project code and documentation are covered by the included MIT
`LICENSE`. Third-party source material and dependencies retain their own terms.
The image collection, thumbnails and vendor asset packs are not MIT-licensed
by this project. Public metadata or downloader access does not authorize
redistribution of images. Supply cloud access only to authorized users; keep
real share configuration private and deliver its password separately.
