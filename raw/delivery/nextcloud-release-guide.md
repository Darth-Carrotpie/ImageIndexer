# Nextcloud transport guide

> Source: Local workbench file `NEXTCLOUD_RELEASE.md`
> Collected: 2026-10-11
> Published: Unknown
> Source-SHA256: 0fdeffbf751292c4684920324b0b9f1384f3107c81f8b04014a5b0828602a87e

# Nextcloud distribution of iip-r000001

This is a transport wrapper for the already verified field-test release, not a
new catalog release. No descriptions, database rows, pixels, IDs or release
manifest bytes are changed. The no-icon package excludes both full-size PNGs
and thumbnails. It is not ready for use until the downloader finishes.

## Finishing plan

1. Verify the immutable input; partition every asset and thumbnail into ordinary
   independent ZIPs of at most 1,000,000,000 bytes, including ZIP overhead.
2. Package the original non-image files and release manifest under
   `release/iip-r000001/`. Keep the downloader, editable configuration, transport
   manifest and cache outside that immutable directory.
3. Use Python's standard library for password-authenticated HTTPS downloads,
   partial-download resume, archive and extracted-file SHA-256 checks, safe
   extraction, refusal to overwrite conflicting files, and final deep validation.
4. Test authentication, interrupted downloads, bad hashes, unsafe archives and
   repeat installation automatically. Build the real ZIPs, restore a clean copy
   from them, deep-verify it and run a CLI search. Record sizes and hashes.
5. Hand off local artifacts. Upload, live Nextcloud testing and granting access
   remain the owner's steps; no cloud credentials are needed for preparation.

## Owner release process

1. Upload the four `IndexedIconPack-iip-r000001-images-*.zip` files to one
   Nextcloud folder, retaining their exact filenames. Do not recompress them.
   Create a read-only, password-protected folder share with downloads enabled.
2. Extract `IndexedIconPack-iip-r000001-no-icons.zip` into a dedicated local
   directory outside a Unity project or other consumer repository.
3. Edit the extracted `nextcloud.json`. For a share link
   `https://cloud.example/nextcloud/s/TOKEN`, set:

   ```json
   {
     "webdav_base_url": "https://cloud.example/nextcloud/public.php/dav/files/TOKEN/",
     "share_token": "TOKEN",
     "password_env": "IIP_NEXTCLOUD_PASSWORD"
   }
   ```

   Preserve any Nextcloud installation subpath. On older servers the endpoint
   may instead be `https://cloud.example/nextcloud/public.php/webdav/` (the
   token still goes in `share_token`). This is a folder WebDAV URL, not the
   browser `/s/TOKEN` page or a dynamically generated whole-folder ZIP.
   Nextcloud documents share-token Basic authentication and the public-share
   WebDAV endpoint in its [official manual](https://docs.nextcloud.com/server/latest/user_manual/en/files/access_webdav.html#accessing-public-shares-over-webdav).
4. From the extracted directory, run with Python 3.11+ and SQLite FTS5:

   ```powershell
   python -B download_icons.py
   ```

   Enter the share password at the hidden prompt. For unattended installation,
   supply `IIP_NEXTCLOUD_PASSWORD` through your secret manager/environment. Do
   not put it in the JSON, URL, command arguments, scripts, or distributed ZIP.
   A wrong password or expired link stops the install; it never installs a login
   page as an image. URLs and credentials are not printed in download errors.
5. Wait for `Installation verified`. Then, from the extracted directory:

   ```powershell
   python -B release/iip-r000001/iconctl.py --package release/iip-r000001 version --json
   python -B release/iip-r000001/iconctl.py --package release/iip-r000001 search "gold key" --limit 5 --json
   python -B release/iip-r000001/iconctl.py --package release/iip-r000001 serve
   ```

   The original release README and usage guide are under `release/iip-r000001/`.
   Confirm search and image previews through your actual share before distributing
   the no-icon ZIP (or its configured, re-zipped wrapper) to authorized testers.
   If re-zipping with your URLs, regenerate its SHA-256; do not change files
   under `release/` or the transport manifest. Deliver the password separately.

## Recovery, offline use and security

- Allow at least 8 GB of free disk space for the restored release plus cached
  ZIPs. PNGs use ZIP storage without recompression; each part is independently
  extractable, not a spanned ZIP requiring special software.
- Re-run the same command after interruption. Verified installed images and
  complete archives are reused; partial downloads resume when HTTP Range is
  supported and restart safely when the server ignores Range. Full SHA-256
  verification still happens before extraction. No automatic network retry loop.
- The cache is `download-cache/`. A corrupt cached ZIP or partial file produces
  an error naming that local file; remove only that file and retry. Conflicting
  installed files are never overwritten: investigate or extract a new bootstrap.
- One installation runs at a time. After a process crash, remove `.download.lock`
  only after confirming no downloader is running. Do not edit the release while
  installation is in progress. Interrupted installs are not usable releases.
- To install ZIPs copied locally, with no URL/password or network access:

  ```powershell
  python -B download_icons.py --offline --archives-dir "D:/copied-image-zips"
  ```

- HTTPS certificate verification is required. Redirects are refused so share
  credentials cannot be forwarded elsewhere; configure the final canonical
  HTTPS endpoint. Private CAs must be trusted by your Python installation.
  The script sends `X-Requested-With: XMLHttpRequest` for public WebDAV access.
  Proxy/Nextcloud authentication layers beyond a password-protected share are
  not implemented. Test your actual server before inviting users.
- Extraction uses an atomic no-overwrite hard link from a verified temporary
  file on the installation volume. Use NTFS/ext4/APFS or another filesystem
  supporting hard links, not FAT/exFAT. Keep the install directory trusted and
  free of symlinks/junctions. The download cache must be outside `release/`.
- After successful verification, cached ZIPs may be removed to reclaim space;
  a repeated run needs no network when all images are already intact.
- SHA-256 detects corruption and pins the exact release; it is not a digital
  signature. Distribute the bootstrap/checksums through a trusted channel.
  Private hosting does not itself establish redistribution permission; grant
  access only to users covered by your asset rights. Nothing is uploaded here.

## Maintainer reproduction

From the maintainer workbench (not the extracted consumer package):

```powershell
uv.exe run --no-project python -B -m unittest discover -s tests -p test_distribution.py
uv.exe run --no-project python -B tools/build_distribution.py --release work/initial-release-v1/releases/iip-r000001 --expected-manifest-sha256 9cd603812b940176e11de110a833cdc033728b057882c27fa405aa75c6075bc3 --output work/nextcloud-distribution-v1
```

The output must not already exist. A failed build is retained for diagnosis;
choose a new output directory after fixing the failure. `SHA256SUMS.txt` covers
all five deliverable ZIPs. The wrapper's `distribution.json` pins the original
release manifest and every image archive. No model/API or database rebuild is
part of this process.

