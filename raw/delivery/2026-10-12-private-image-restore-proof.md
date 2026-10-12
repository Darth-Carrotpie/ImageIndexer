# Private image restoration into a clean public-data clone

> Source: Offline downloader, read-only CLI, SHA-256 checks and Git status in an isolated clone during release preparation
> Collected: 2026-10-12
> Published: 2026-10-12

The tested catalog database remains 79372288 bytes, with 6250 accepted
observations. Before hydration the isolated clone contained zero PNG files and
had already passed metadata-only search and all 53 regression tests. It was
cloned with core.autocrlf=true to exercise Windows checkout behavior.

## Executed restore and repeat proof

The copied downloader ran with --offline and the four original image ZIPs in
work/nextcloud-distribution-v1. Each archive was verified before extraction.
No URLs, passwords or network access were needed for this proof.

The first install and repeat install both finished with:

```json
{"ok":true,"package_status":"release_manifest_present","errors":[]}
```

Installation verified: release/iip-r000001

Recorded final checks:

```json
{
  "OfflineInstall": "passed",
  "RepeatInstall": "passed",
  "DeepValidation": "passed",
  "ExactMaterialization": "passed",
  "GitCleanAfterHydration": true,
  "RestoredImages": 16443
}
```

The query "gold key" returned an icon whose selected rendition was copied using
the CLI's explicit SHA-256 option. The copied file's hash matched
de6b6410949ab1fbc13984a5a8a6c9bbdce33ed165d3baf3a9bab52c62c80238.
A receipt was generated outside the cloned repository. Git status --porcelain
returned no entries after hydration. The public candidate guard still passed,
so restored images remained excluded from Git.

The clone's release-manifest hash stayed
9cd603812b940176e11de110a833cdc033728b057882c27fa405aa75c6075bc3 and its
SQLite hash stayed 960187d88ffd4999aebb2608a7f8a2fcb2a1b8795122bce10edf90a7a6d51968.
No database, descriptions, identities or image archives were rebuilt.

This is a local clone/offline proof. Live Nextcloud authentication and transfer,
the first GitHub push, a subsequent remote clone and production activation were
not performed. Those remain owner steps in the release checklist.
