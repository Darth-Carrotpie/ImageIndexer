# Live private installation and requested update flow

> Source: Owner installation transcript and follow-up requests in this conversation; local implementation and verification output
> Collected: 2026-10-14
> Published: 2026-10-14

## Owner direction

"Ok. Leave the global path alone. Printed command is enough.
Add an update command (or/and script) with the suggested flow implementation and THAT commit I will dub as release. Both commands (install and update) should be in the git readme for future reference of installer."

The owner used the public curl-to-Bash installer in Git Bash on Windows, with a
destination path containing spaces. The transcript contains a private folder
share link; this publication snapshot deliberately omits that link and token.
The password was entered at the hidden prompt and is not present in the log.

## Live installation evidence (non-sensitive excerpt)

The log reported downloads and extraction for all four
`IndexedIconPack-iip-r000001-images-00N.zip` archives, then:

```text
Deep-verifying restored release...
{"ok":true,"package_status":"release_manifest_present","errors":[]}
Installation verified: release/iip-r000001
```

The original installation receipt records public source commit
`6043817ac5bdcfc0a07c9591aa4b8b56b17eb39d`. The owner confirmed that this
installation is the field test. The updater implementation in the current
worktree has not been committed or tagged; the owner said the next commit will
be designated a release.

## Update implementation proof

`ImageIndexerInstaller.sh` now accepts `install`, `update`, and `rollback`, while
the original one-path invocation remains an install. `update` resolves one
current GitHub `main` commit and creates a sibling directory ending with the
first 12 commit characters. The original directory holds the local launcher
`ImageIndexerRun.py` and the private `.imageindexer-active.json` pointer. The
updater reuses the original verified ZIP cache, copies private share
configuration if present, and runs the existing downloader's pinned-archive
and deep-release verification. It runs a version command before switching the
pointer atomically. The previous directory is retained. `rollback` deep
verifies that previous release before atomically switching back. Neither
command changes global PATH or environment variables; running services are
not restarted automatically.

`uv.exe run --no-project --with-requirements requirements-build.txt python -B -m unittest discover -s tests`
passed 65 tests. Focused updater tests cover legacy install compatibility,
source commit pinning, cache/config reuse, launcher routing, side-by-side
switching, and pointer preservation after failed update or rollback. The public
catalog publication guard, Bash syntax, and Git whitespace checks passed.

A smoke run against an older ignored metadata-only proof installation fetched
the existing remote `main` commit into a sibling. That proof had no private
image archive cache; the downloader requested a share link, so the run was
interrupted without entering credentials. The original active pointer was
absent and unchanged. The full updater still needs a remote run after its
implementation commit is published. The existing live owner install supplies
the independently proven image downloader and deep verification path.

The pinned SQLite database and release manifest have not been rebuilt or
rewritten. No model calls, new image ZIPs, cloud uploads, Git staging, commit,
push, or tag were performed in this implementation turn.
