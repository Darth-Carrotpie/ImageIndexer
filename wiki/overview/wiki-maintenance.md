# Wiki scope and maintenance

> Sources: Owner directions, Unknown; wiki governance recommendation and live workbench audit, 2026-10-11; public-data directions and proof, 2026-10-12
> Raw: [Owner directions](../../raw/planning/2026-10-11-owner-directions.md); [Governance recommendation](../../raw/planning/2026-10-11-distribution-and-ingestion-proposal.md); [Initialization audit](../../raw/quality/2026-10-11-live-workbench-audit.md); [Public-data decision](../../raw/planning/2026-10-12-public-data-directions.md); [Public catalog proof](../../raw/delivery/2026-10-12-public-catalog-proof.md)
> Updated: 2026-10-12

## Scope

This is the package's local knowledge base, rooted beside `iconctl.py` in the
maintainer workbench. It covers purpose, principles, implementation contracts,
verified evidence, distribution and proposed follow-up work. It is not a wiki
for the surrounding Unity test project and is not a deployed GitHub Wiki.

Start at the [index](../index.md). The root README is the GitHub landing page,
summarizing the [purpose page](purpose-and-principles.md) and linking this index.
It is an ordinary file, not a symlink. Keep this wiki in the same repository as
the source and public generated catalog, without a second documentation authority.

## Evidence and authority

- `raw/` preserves immutable source snapshots with origin, collected date and
  publication date when known. Local document snapshots record their source hash.
- `wiki/` contains compiled articles with Sources, Raw and Updated fields.
- `wiki/index.md` indexes every article; `wiki/log.md` is append-only.
- Owner directions establish decisions and authorization boundaries. Executable
  code and verification records establish current capabilities. Old plans do not
  prove implementation; assistant recommendations do not constitute owner approval.
- New evidence supersedes prior status explicitly; preserve old evidence and
  use dated Outdated or explained Disputed blocks rather than rewriting history.

Current workbench files may change after their snapshots. A future update must
capture new evidence and reconcile affected articles, not silently edit raw
snapshots to match current source. Release packages and ZIPs remain immutable
while documentation evolves outside them.

## Maintenance procedure

1. Fetch or snapshot the new source without overwriting prior evidence.
2. Search the complete wiki and classify the source as New, Update, Disputed
   or No material before writing articles.
3. Locate each load-bearing claim in its linked raw source. Separate measured
   results from targets and current behavior from roadmap recommendations.
4. Update affected articles and cross-references; refresh content dates and
   index entries. Append an operation record to the log.
5. Check evidence fidelity, links, Raw references, index coverage and dates.
   The installed Karpathy LLM Wiki skill provides `scripts/check_evidence.py`;
   run it with the package-workbench root. It reports findings without changing
   source facts. Links/index checks are also required.

Keep topic directories one level deep. Prefer relative repository paths, not
workstation locations or an invented future remote URL.

## Public export boundary

The wiki is local evidence-backed documentation, not an assertion that every
internal source is public. Before publication, curate safe evidence together
with articles so Raw links still resolve. Preserve internal originals privately;
create explicitly identified publishable sources where redaction is required.
Do not export vendor assets, secrets, private configuration, raw API runs or
unreviewed work directories merely because the public README links the wiki.

## See Also

- [Purpose and principles](purpose-and-principles.md)
- [Distribution and repository proposal](../delivery/distribution-and-repository.md)
- [Implementation roadmap](../planning/implementation-roadmap.md)
