# Guided installer direction and verification

> Source: Owner request in this conversation; current repository implementation and automated commands; GitHub remote; https://docs.nextcloud.com/server/latest/developer_manual/client_apis/WebDAV/basic.html
> Collected: 2026-10-14
> Published: 2026-10-14

## Owner direction (verbatim)

The manual step: Make a fresh GitHub clone **outside Unity**. Copy `catalog/nextcloud.example.json` to `catalog/nextcloud.json`
Should not be needed. Even GitClone, should also not be needed, instead we could have just one installation script, which prompts for when inputs are needed and is universal. Make an ImageIndexerInstaller.sh, which we could curl and run via a single command inputing only a path where to install the package. Then step by step it would do the nextcloud config input, passw, and other required steps.
I've already prepared github and nexcloud.

## Live repository observation

The working tree was clean at the start. `origin` is
https://github.com/Darth-Carrotpie/ImageIndexer.git. Local HEAD and remote main
both resolved to `b997ccb554cf65c123344f4e7757f84988374b28`, with subject
`Prepare public catalog and image-indexing tools`. The owner has published the
initial source and generated catalog. No Nextcloud URL or password was supplied
to this implementation turn; owner-reported preparation is not an authentication proof.

## Implemented behavior

`ImageIndexerInstaller.sh` accepts one install directory. It runs in Bash on
Linux, macOS, WSL or Windows Git Bash, not directly in PowerShell. It needs curl
for the documented one-liner and Python 3.11+ with SQLite FTS5. An existing uv
can select/download a compatible Python. It does not install system packages.
Allow at least 8 GB for image files and retained archive downloads.

The installer resolves main once through GitHub's Git-ref API, downloads the
archive for that exact commit, checks archive paths/types/size, and runs the
existing public catalog check. It stores the source commit and archive hash in
`.imageindexer-install.json`. It does not create a Git checkout. `main` is the
trusted code entry point; hashes here are integrity checks, not signatures.

It prompts whether to restore private images. The shared downloader now creates
missing `nextcloud.json` interactively from a folder share link or public DAV
endpoint, preserves an instance subpath, and requests the password invisibly
only when a network download needs it. The password is never persisted or
passed as a command-line argument. `--configure` explicitly replaces saved
configuration after confirmation. A saved endpoint/token is private even though
it contains no password. Temporary configuration files are ignored as well.

The official Nextcloud documentation states that modern public-share DAV is
`/public.php/dav/files/{share_token}` and uses the Basic Auth username
`anonymous` with the share password. The downloader was corrected to use this
username for modern endpoints, retaining token authentication for legacy
`/public.php/webdav/`. Existing credentialed redirects remain refused.

Existing unowned nonempty directories, symlink/junction paths, archive path
traversal, special-file entries, unsafe normalized names, conflicting images,
and concurrent installer locks are refused. Resume reuses the same installed
snapshot; a newer snapshot needs a new destination. No auto-upgrade, automatic
server startup, credential discovery or OS package manager was added.

The shared downloader still checks pinned archives and files and performs deep
catalog verification. Declining images explicitly reports metadata-only status.
The installer prints the browser command after successful completion. Config,
images and caches remain outside the immutable release payload.

## Observed verification

`uv.exe run --no-project --with-requirements requirements-build.txt python -B -m unittest discover -s tests`
completed with 61 tests passing. Bash syntax checking and help invocation passed.
New tests cover guided URL parsing, modern/legacy credentials, private config
creation and overwrite confirmation, no stored password, matching source and
published downloader, source-archive safety, source commit pinning, resume,
existing-directory preservation, locks, failed bootstrap isolation, image and
metadata-only choices, and child-terminal forwarding.

The actual GitHub source archive was downloaded by the installer into ignored
`work/installer-network-proof-v1/`. Public metadata checks passed before and
after publishing the snapshot. It contains the 79372288-byte database and 6250
observations. The interactive Git Bash run completed with images declined.
A second invocation piped the local installer through curl into Bash, reached
the terminal prompt, reused the recorded snapshot without downloading again,
and also completed metadata-only. This tested pipeline input separately from
the live HTTPS GitHub source fetch; the new installer is not on GitHub yet.

The public candidate guard and `git diff --check` passed. The database hash
remains `960187d88ffd4999aebb2608a7f8a2fcb2a1b8795122bce10edf90a7a6d51968`;
the release manifest hash remains
`9cd603812b940176e11de110a833cdc033728b057882c27fa405aa75c6075bc3`.
No database rewrite, description rebuild, paid model call or image ZIP rebuild
was performed. Existing standalone ZIPs remain unchanged historical artifacts;
they do not automatically gain guided setup or the modern-auth correction.

## Remaining boundary

Commit and push the installer, wrapper changes, tests and documentation before
using the public raw-GitHub installer URL. This turn did not stage, commit,
push, tag or upload. Test the newly published flow in a new destination using
the private share. Native Linux/macOS/WSL and actual private Nextcloud access
were not exercised. Windows Git Bash was exercised. No public credentials or
private image bytes were introduced.
