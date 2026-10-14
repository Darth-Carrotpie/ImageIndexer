# Verified release and limitations

> Sources: Initial release readiness, final search report, distribution verification and live workbench audit, 2026-10-11; public-data directions and proof, 2026-10-12; guided installer direction and proof, 2026-10-14; live install and update direction, 2026-10-14
> Raw: [Readiness](../../raw/quality/2026-10-11-initial-release-readiness.md); [Search report](../../raw/quality/2026-10-11-final-search-report.md); [Distribution proof](../../raw/delivery/2026-10-11-distribution-verification.md); [Live audit](../../raw/quality/2026-10-11-live-workbench-audit.md); [Public-data decision](../../raw/planning/2026-10-12-public-data-directions.md); [Public catalog proof](../../raw/delivery/2026-10-12-public-catalog-proof.md); [Clone image-restore proof](../../raw/delivery/2026-10-12-private-image-restore-proof.md); [Guided installer proof](../../raw/delivery/2026-10-14-guided-installer-proof.md); [Live install and update](../../raw/delivery/2026-10-14-live-install-and-update-direction.md)
> Updated: 2026-10-14

## Current status

`iip-r000001` is ready for local field testing. Its Nextcloud transport is
prepared and locally verified; the actual cloud endpoint is not configured or
tested. This is not evidence of public publication or production activation.

> **Status: Outdated** (2026-10-14)
> The owner has published the source/catalog repository. The later Git Bash
> transcript confirms live Nextcloud authentication, all four archive downloads
> and a successful deep release check. Production activation and the new
> updater's post-push field test remain open.

| Pin | SHA-256, without prefix |
|---|---|
| Release manifest | `9cd603812b940176e11de110a833cdc033728b057882c27fa405aa75c6075bc3` |
| Logical catalog revision | `d96e65c62e0928fd11ceccd50f1a41217965704ae7257164ff930d0641b207f2` |
| SQLite payload | `960187d88ffd4999aebb2608a7f8a2fcb2a1b8795122bce10edf90a7a6d51968` |
| Search profile | `532bded885ae394f2586b9e260e3fb9f1781e2c6c064f1184971fa68feb2bd97` |

The later distribution build does not change any of those release bytes.

## Automated search acceptance

The owner-approved useful-top-five threshold is 80%. The sealed acceptance set
passed at 43/50 (86%), with 10/10 truthful negative results and zero contract
violations. Success means at least one plausible useful result among the first
five, not necessarily the exact preselected target.

Literal usefulness was 24/25; seed modification 9/15; functional queries 10/10.
All 50 target/query pairs passed automated audit before retrieval without query
repair. Alternative readings can count, but contradictions of required visual
properties cannot. The evaluation used the same model family for authoring,
audit and judging: automated checks do not establish independent human judgment.

The additive pass introduced 29,795 alternative phrases without replacing the
original captions, hard facets or icon identities. This broadened description
coverage but did not improve every query family. Seed modification is the main
known retrieval weakness. The opened holdout must not be used as a fresh gate
after tuning.

## Engineering checks

The initial readiness record contains 38 regression tests. The later live audit
passed 48 tests after adding ten transport tests; these are successive records,
not conflicting counts.

The public-data preparation then passed 53 tests in the workbench and an isolated
Git clone with Windows-style checkout enabled. The clone passed metadata checks
and a text query without images or credentials. A clean extraction of the new
standalone ZIP passed the same metadata checks. These are local proofs, not
evidence of a push or live Nextcloud authentication.

The same clone subsequently restored all 16443 private image files from the
existing ZIPs, passed deep verification and repeated installation, and copied
a selected exact rendition with a matching SHA-256 receipt. Git remained clean
after hydration. This proves the image ignore boundary and local install path;
the actual Nextcloud endpoint still needs owner configuration and testing.

Completed release proof covers deep payload/identity/revision checks, a clean
relocated copy, CLI search/show/version, HTTP parity and image hashes, full-corpus
exclusions, exact materialization with receipts and no overwrite, browser-shell
behavior, and isolated activation/rollback. The temporary successor in that
test is a fixture, not a released successor.

The transport proof restores a clean package from the deliverable ZIPs, verifies
it deeply, repeats installation without cloud configuration, and executes CLI
search. Authentication failures, Range resume/fallback, interrupted transfers,
corrupt archives and unsafe extraction have local automated coverage.

The guided installer update passed 61 tests. A real GitHub archive download
passed metadata checks and an interactive Windows Git Bash installation with
images declined. Piping the local script through curl into Bash reached the
terminal prompt and resumed the same snapshot without re-downloading. Source
and published downloader copies match; database and release manifest hashes
are unchanged. The new installer itself still needs committing and pushing.

> **Status: Outdated** (2026-10-14)
> The owner subsequently published and live-tested that installer. Only the
> updater changes described below await a new commit and push.

The owner subsequently provided a successful live private-share install log:
all four archives downloaded and `Installation verified: release/iip-r000001`
followed `{"ok":true,"package_status":"release_manifest_present","errors":[]}`.
The public evidence omits the share URL and token. The subsequent updater
implementation passed 65 tests, public catalog guard, Bash syntax and Git
whitespace checks. Mocked failure and rollback paths leave the local active
pointer unchanged. A smoke update fetched an existing remote commit into a
sibling metadata-only proof, then stopped at the share prompt because that
proof had no image ZIP cache; the original pointer was unchanged. Full remote
promotion awaits the updater commit.

## Limits and next evidence

- Live private-image installation is proven by the owner transcript; the
  uncommitted updater still needs a remote update and rollback rehearsal.
- Public repository download is proven; publishing the updater and production
  consumer integration remain open. Image rights remain separate.
- Windows Git Bash was tested; native Linux/macOS/WSL execution was not.
- No general new-icon successor ingestion or publication-head automation.
- Browser behavior is checked; pixel-level browser layout was not verified.
- The recorded timing probes did not flush OS caches; they are not a cold-disk
  latency guarantee. Prefer the release-specific readiness timings over older
  candidate timings if comparing performance.
- Same-model judgments can make correlated mistakes. Field feedback should
  retain release/profile pins, request, returned and chosen IDs, and reason.

API spending in the evidence is historical estimated usage, not an invoice or
current price quote. This wiki initialization and distribution work made no new
model calls or corpus rebuilds.

## See Also

- [Purpose and principles](../overview/purpose-and-principles.md)
- [Nextcloud installation](../delivery/nextcloud-installation.md)
- [Implementation roadmap](../planning/implementation-roadmap.md)
