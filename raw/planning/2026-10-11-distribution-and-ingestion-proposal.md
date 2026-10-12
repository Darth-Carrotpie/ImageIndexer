# Distribution and ingestion recommendation

> Source: Assistant-authored recommendation, grounded in the owner directions, current local code and official GitHub documentation cited below
> Collected: 2026-10-11
> Published: 2026-10-11

This is a proposal, not an approved implementation or evidence of publication.

## Public distribution

Recommend a standalone package source repository outside the Unity test project.
Use a curated export of the workbench rather than publishing the Unity root or
blindly adding the workbench. A local-only Git repository could alternatively
start at the package workbench after an exclusion policy is installed; the
standalone source-only repository is the preferred public destination.

Keep source, tests, agent skills, public documentation and explicitly selected
safe evidence in Git. Keep generated work directories, source/vendor assets,
PNGs, thumbnails, SQLite catalogs, ZIPs, caches, API requests/responses, permission
records, private feedback, real Nextcloud configuration and credentials out of
Git history. Do not ignore all JSON: safe example configurations and fixtures
may be appropriate source files. An ignore file is only a guard, not a secrecy
audit or a way to remove already committed content.

Use repository-local Markdown under wiki/ rather than a second documentation
authority in GitHub's Wiki tab. The documentation then travels with code
commits and can be checked together. GitHub Pages, a separate Wiki mirror, a
package registry, auto-updates and hosted search are not needed for the first
public source release.

After actual Nextcloud testing and publication-content clearance, attach the
original no-icon ZIP and SHA256SUMS.txt to a tagged GitHub prerelease. The
generated source-code ZIP is not the prepared consumer installer. Keep image
ZIPs in the password-protected Nextcloud share. Keep the public bootstrap's URL
and token blank; supply private nextcloud.json separately to authorized users,
and the password through a prompt or secret environment variable. Do not re-zip
a hydrated test installation. A no-icon ZIP still exposes descriptions,
provenance and catalog metadata; if those cannot be public, publish only code
and documentation and distribute the entire bootstrap privately too.

Use pinned release URLs and checksums for reproducible installs. A latest link
may serve discovery, not silently upgrade a consumer. Keep tooling version,
catalog release_id, schema_version, catalog_revision and manifest digest distinct.
Do not invent a tooling version, repository owner/name or software license.

Suggested publication order: configure and test the private share; curate and
scan a clean source export; owner selects license and repository; initialize
Git locally; run public-safe automated checks without private assets/secrets;
authorize the public push; draft a tagged prerelease with the pinned installer
and checksums; run a clean remote install; explicitly publish. No step has been
performed by writing this recommendation. Future CI must not require private
PNG data for ordinary public pull requests or expose cloud/API secrets to them.

## Provider facts checked against official documentation

GitHub releases are associated with tags, accept uploaded release assets, and
also expose automatically generated source archives. The prepared installer
should be an uploaded asset, distinct from those source archives.
Source: https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases

GitHub supports draft releases and prerelease marking. When release immutability
is enabled, attach all required assets to the draft before publishing.
Source: https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository

GitHub's Wiki uses its own .wiki.git clone URL. Keeping wiki/ inside the source
repository avoids introducing that separate documentation repository here.
Source: https://docs.github.com/en/communities/documenting-your-project-with-wikis/adding-or-editing-wiki-pages

GitHub documents both latest-release links and version-specific release links.
Source: https://docs.github.com/en/repositories/releasing-projects-on-github/linking-to-releases

Removing sensitive content from Git history is disruptive, and old clones or
forks can retain it. Prevention before the first public commit is preferable.
Source: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository

## Proposed implementation sequence for additional packages

First prove the existing fixed corpus in the field. Preserve the automated
80% initial useful-result criterion, negative-query and contract checks, and
same-model limitations. Never reuse the opened acceptance set as a fresh gate.

Then implement an append-only new-pack path using synthetic or redistributable
fixtures: explicit pack manifests and preferred roles, permanent pack IDs,
validated portable staging, latest-published-base pinning, and a deterministic
plan that proposes new icon IDs once. Preserve old IDs and byte hashes; reject
changes, omissions with ambiguous meaning and conflicting identities rather
than silently guessing. This delivers new-package ingestion without first
implementing all rename/retirement/replacement lifecycle semantics.

Audit the single-pack catalog_state and pack assumptions in builders, revision
encoding, validators, readers and fixtures before claiming multi-pack support.
Choose an explicit schema migration if required, while preserving old readers
and historical releases. Do not infer that the existence of pack_id already
makes the implementation a multi-pack catalog. Separate the initial corpus's
four pairing corrections from generic ingestion; preserve their immutable
provenance instead of applying them to unrelated new packs.

Implement frozen-plan apply outside the base release. Reuse unchanged accepted
annotations; meter and authorize only genuinely pending observation work.
Quality and identity consistency checks are automated; no independent manual
reviewer is required. Unresolved semantic continuity stops the candidate.
Owner decisions about identity ambiguity, new spend and publication are
authority boundaries, not a per-icon manual QA process. The earlier completed
corpus-run permission is not blanket authorization for future paid scopes.

Implement a generic successor builder and locked expected-head compare-and-
advance. Test ledger-prefix retention, old exact pins, stable IDs, deterministic
logical rebuilds, stale-base rejection, concurrent publisher conflict and
failure recovery. Then reuse the existing distribution wrapper and deployment
selector, adjusting only after real measurements and compatibility tests.

Defer changed-artwork classification, rename/move continuity, split/merge,
retirement/reactivation and semantic replacement until the append-only path is
proven. Those workflows require explicit lifecycle events, not ID regeneration.
Cross-release blob sharing and incremental downloads are later optimizations;
the present transport downloads all missing image parts for a complete release.

## Wiki governance proposal

Use immutable raw/ evidence, compiled wiki/ articles, wiki/index.md and an
append-only wiki/log.md. Preserve older evidence and add dated status blocks
when it is superseded. Label source findings, current implementation, owner
decisions and assistant recommendations separately. Validate links, index
coverage and evidence after changes. Keep runtime releases and shipped ZIPs
unchanged when maintaining the wiki. Before publishing, curate safe evidence
without severing the public articles' source links; never publish all work/
or all internal raw evidence by default.
