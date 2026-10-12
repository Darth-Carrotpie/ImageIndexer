---
name: indexed-icon-pack-ingest
description: Maintain an Indexed Icon Pack by staging new icon sets, preserving published IDs, preparing an annotation decision packet, and building reviewed successor releases.
---

# Indexed Icon Pack maintainer

Use only for an owner-authorized catalog maintenance task. Read the package-root
`INGESTION.md` before acting; it is the command and identity-continuity
contract. Work in a separate staging directory. Never alter supplied source
files, an installed or published release, or consumer repository records.

The initial fixed-corpus field test does not include a general successor
ingestion/publisher implementation. Do not build or publish r000002 using the
first-release builder. Preserve the full identity ledger and retained pixels;
report the missing successor workflow rather than improvising it.

Preserve the latest ever-published identity registry as the authority. Reuse an
`icon_id` only when the same logical icon's continuity is proven or explicitly
reviewed. Changed bytes, renames, merges, splits, and retirements require the
review described in `INGESTION.md`; hashes and filenames alone cannot decide
semantic identity. Stop on ambiguous cases rather than minting or rebinding a
published ID silently.

Deterministic tools may scan, hash, structure, preview, index, validate, and
prepare the model-choice packet. Unless the owner has already authorized the
specific model and bounded run, stop before sending images to a model. Present the pending icon count,
image-size distribution, proposed model choices, current provider prices,
quality rubric, and provisional budget; let the owner choose and authorize the
pilot. Use automated image-input judgments, immutable responses, metering and
hash-pinned evidence; no independent manual reviewer is required. Preserve
original captions and index grounded alternate readings as reviewed terms,
with explicit uncertainty, not asserted hard facets. A corpus pass requires
the measured configuration and spending envelope to be within owner authority.
Never let a deterministic script invent visual descriptions or keywords.

If the documented command for a step is not yet implemented, report that gap;
do not hand-edit SQLite or improvise a publication. Publication-head advancement
and activation of a deployed release are separate owner-controlled operations.
