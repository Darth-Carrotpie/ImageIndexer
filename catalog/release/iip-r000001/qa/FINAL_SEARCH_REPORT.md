# Initial field-test search report

Date: 2026-10-11. **Automated acceptance passed: 43/50 (86%) useful top-five
results, 10/10 truthful negative results, zero contract violations.** The owner
authorized an 80% initial-release requirement and automated evaluation without
independent manual reviewers. No threshold, target, query, or denominator was
changed after the holdout was sealed and retrieval was run.

This report permits first-release packaging. The release-specific manifest
digest and completed relocation/rollback proof belong to the separate trusted
handoff (`READINESS.json` in the maintainer evidence directory); they cannot
be embedded here without making the release hash self-referential. No external
distribution, consumer-repository edits, or production activation is implied.

## What changed

- Preserve all 6,250 stable icon IDs, 127 collections, 10,200 renditions and
  10,193 unique content-addressed PNG blobs, including the four previously
  approved pre-release pairing corrections.
- Retain original literal captions, hard visual facets, rendition bindings and
  historical model output. Read-only SQL comparisons found zero changes to
  icon rows/descriptions/renditions and zero added or removed hard-facet rows.
- Add 29,795 image-grounded alternative phrases through the existing review
  layer, giving 29,819 total reviewed terms and 7,268 uncertainty notes. These
  phrases are retrieval hypotheses, not asserted hard facets. `show`, the
  consumer skill and browser details expose the alternatives and uncertainty
  for later LLM selection.
- Keep the existing FTS5/BM25, seed-term selection and RRF ranking policy.
  No embeddings, runtime model, new database or new runtime dependency.
- Fix the shared HTTP request-size bound to 512 KiB, sufficient for all 6,250
  excluded IDs; oversized bodies remain rejected.
- Add schema-v2 logical revision verification, bounded first-release packaging,
  schema-v2 local deployment verification, language-neutral consumer fixtures
  and isolated relocation/materialization/rollback checks.

The corpus pass used only `gpt-6-sol` with high reasoning, frozen image-only
inputs and a 4,096-output-token limit. It reused 100 byte-identical trial requests
and requested the other 6,150 once. All 6,250 responses completed with usage.
The prompt targets 2-8 phrases. One response supplied nine valid phrases,
including both `wooden wand` and `wooden pestle`; a documented ten-phrase import
ceiling preserves these alternatives. All phrases passed uniqueness, lowercase,
nonblank and 80-character checks. Raw prompts/responses were not edited.

## Automated evaluation

Positive success means at least one of the first five images plausibly satisfies
the required visual properties and intended use. Synonyms and reasonable
schematic readings count; contradicted required subjects/colors do not.
Judges saw anonymous shuffled images and required/optional properties, not
captions, IDs, rank scores, known targets, prior judgments or a success quota.
An exact-target hit never received an automatic useful label.

### Exposed development set

These 90 positive cases plus 10 negatives informed development and are not
acceptance evidence. The historical implementation-agent score was 52/90;
the following table uses the new stateless API rubric consistently.

| Candidate | Useful@5 | Literal | Seed modification | Functional | Negatives | Contract violations |
|---|---:|---:|---:|---:|---:|---:|
| Original structured candidate | 62/90 | 32/40 | 20/30 | 10/20 | 10/10 | 0 |
| Targeted 100-icon alternatives trial | 67/90 | 37/40 | 21/30 | 9/20 | 10/10 | 0 |
| Full alternatives candidate | 65/90 | 36/40 | 17/30 | 12/20 | 10/10 | 0 |

Exact-target @1/5/10/20 changed from 28/45/54/64 to 35/55/62/69 in the trial,
then 35/56/67/73 in the full candidate. Exact targets are diagnostics, not the
acceptance rubric. Broad alternatives improve coverage but do not improve every
query family; seed-modification retrieval remains the main weakness.

Paired original-to-final usefulness gains: literal-002, 022, 032, 034, 035;
seed-009; functional-007, 009, 018, 020. Losses: literal-025; seed-001, 007,
013, 028; functional-006, 019. Nine original/final judge inputs were identical
and none changed outcome; retaining original labels for them still gives 65/90.
In the earlier trial, two of 69 identical-input outcomes changed in opposite
directions. These are same-model measurements with judgment variability, not
a controlled estimate of causal improvement.

### Sealed acceptance set

The candidate was frozen before image-only query authoring. Deterministic
SHA-256 ordering selected 50 targets from 50 different collections, excluding
V1-V4/development targets, exposed seeds and the targeted 100-icon trial IDs.
Whole-corpus observation of images is disclosed; the annotation pass never
received holdout queries or expected answers. A separate stateless image audit
accepted all 50 target/query pairs before retrieval, with no query repairs.

| Family | Useful@5 |
|---|---:|
| Literal | 24/25 |
| Seed modification | 9/15 |
| Functional | 10/10 |
| **Total** | **43/50 (86%)** |

The negative suite contains five completely excluded collections and five
absent conjunctions of independently present hard facets: **10/10 empty**.
There are **zero exclusion, count, duplicate-ID or typed-contract violations**.
Known suitable target @1/5/10/20 is 16/30/37/45 out of 50.

Seven unsuccessful cases remain in the denominator: acceptance-006, 026, 027,
028, 029, 039 and 040. Six known targets appear at ranks 14, 6, 18, 8, 11 and
11 respectively (all except 026); 026 is outside the first twenty. No ranking
or annotation changes were made from these outcomes. Preserve this evidence;
do not reuse the exposed set as a fresh acceptance test for a retuned successor.

All author/audit/judge calls use the same model in separate stateless requests.
This is **automated, not independent human evaluation**; correlated model errors
and a small 50-case sample limit generalization. Passing is permission for a
bounded field test, not a guarantee for arbitrary queries.

## Integrity and reproducibility pins

SHA-256 values (without the `sha256:` prefix):

| Record | Digest |
|---|---|
| Frozen identity ledger | `b0d0fb2b08349ca735a7596e4655b4451cc82b042af79940c7022b54c339fb1e` |
| Original source catalog manifest | `e23ad53570076f3bad800e016544538aa200edf9aea2905f219f759f16f5a6db` |
| Original raw annotation output | `c4d100ff9ae7298ecaa12eb8497a177aac3f363bf38209f732d28b67f0fd65aa` |
| Additive review V3 | `a21dea76f138edef46ad83eccabcc1ee78d02d5c332be4dcc795a2ea808c4d8c` |
| Final database | `960187d88ffd4999aebb2608a7f8a2fcb2a1b8795122bce10edf90a7a6d51968` |
| Search profile | `532bded885ae394f2586b9e260e3fb9f1781e2c6c064f1184971fa68feb2bd97` |
| Positive benchmark | `427be0b519ec0c5d2dcf2d9710f706ebe389dc63a7122a72daccd73a3ccc87d3` |
| Negative benchmark | `3c354ab0c256750992467db3445cb0f143dd0f98068e412476d87a2f045f4986` |

The search-profile fingerprint changes because shipped browser/HTTP code is
part of the implementation fingerprint, not because the ranking policy changed.
The first-release builder recomputes scores, checks both sealed benchmark hashes,
the candidate database and current implementation fingerprint, deeply validates,
copies payloads without hardlinks, computes the logical revision and inventories
every payload file. It refuses an existing destination or an unmet gate.

Maintainer evidence is under `work/initial-release-v1/`: immutable request plans,
requests, raw responses, usage, reviewed alternatives, ranked results, judgments,
scores and acceptance seal. `EXECUTION.md` gives runnable build/evaluation/proof
commands. Raw work logs, API dispatchers, credentials and caches are not bundled
with the consumer release.

## Checks and measured runtime

- 38 regression tests pass, including identity/pins, structured retrieval,
  full-catalog exclusions, HTTP body bounds, release gating, logical revisions,
  deployment validation and browser detail rendering as text.
- Relocation caught two packaging defects before handoff: a SQLite handle
  blocked Windows directory finalization, and helper imports could write
  bytecode caches into an otherwise immutable copy. Explicit connection closure
  and cache-free verification/deployment now have regression checks. The first
  packaging attempt is retained as rejected evidence; the accepted database,
  profile and all search judgments remain unchanged.
- Both bundled skills pass skill-structure validation.
- Final candidate deep payload, identity-freeze, foreign-key, FTS projection
  and annotation/provenance validation passed in the builder.
- The release proof checks an independent relocated copy, deep verification,
  CLI search/show/version, HTTP search/show/thumbnail/blob parity, all-6,250-ID
  HTTP exclusion, exact-hash materialization/receipt and refusal to overwrite.
  It also activates and rolls back a disposable packaging-only successor in
  an isolated temporary deployment. Its actual outcome is in `relocation-smoke.json`.

On Windows 11, Intel64 Family 6 Model 154, 16 logical CPUs, Python 3.14.5 and
SQLite 3.50.4, 100 development requests returned identical fresh/warm IDs.
Fresh-reader-inclusive p50/p95 was 65.3/183.0 ms; warmed-query p50/p95 was
55.1/179.0 ms. Database size is 79,372,288 bytes; FTS storage 8,331,264 bytes;
probe peak working set 46,092,288 bytes. Another local evaluator ran during
part of this probe. OS cache was not flushed: fresh reader is not cold disk.
Release startup additionally verifies the database payload hash; its separately
recorded measurements must not be conflated with unpublished-candidate startup.
No latency SLA is claimed.

## API usage estimate

| Finishing work | Estimated USD |
|---|---:|
| Original-candidate automated judgment (Standard + Batch) | 0.302885 |
| 100-icon alternative-label trial | 0.247680 |
| Trial-candidate automated judgment | 0.288518 |
| Remaining 6,150 alternative-label requests | 15.467490 |
| Final development judgment | 0.296763 |
| Holdout authoring | 0.106015 |
| Holdout target audit | 0.043690 |
| Holdout top-five judging | 0.158925 |
| **This finishing pass** | **16.911966** |

Prior recorded API estimates were $30.810141; cumulative recorded estimate is
$47.722107, excluding interactive-agent usage. The 100 reused corpus responses
are charged only once. These are response-usage estimates, not invoices, using
the [official pricing](https://developers.openai.com/api/docs/pricing) checked
2026-10-11 and the Batch discount. The full-run forecast was $15.232320 new;
actual estimated new usage was $15.467490, below the $60 new-call ceiling.
Evaluation/trial calls stayed below their separate $25 ceiling.

One live evaluation request was rejected at the account's 3-RPM limit before
inference. One attempted second simultaneous corpus batch was rejected at the
account's actual 900,000 queued-token limit before inference; dispatch switched
to one active chunk and resubmitted that rejected input once. Both admission
failures are preserved. No completed request was repeated and no charge remains
unreconciled. All real finishing calls used GPT-6 Sol High; Astra output in unit
test logs belongs only to synthetic historical fixtures.

## Field-test handoff

Place the immutable release outside consumer repositories. From its root:

```powershell
uv run --no-project python -B iconctl.py --package . verify --deep
uv run --no-project python -B iconctl.py --package . version --json
uv run --no-project python -B iconctl.py --package . search "gold key" --limit 8 --json
uv run --no-project python -B iconctl.py --package . serve
```

Ordinary Python 3.11+ with SQLite FTS5 is sufficient; `uv` is only a launcher
alternative for this workstation. No model or API key is required at runtime.
Use `show` and the supplied previews before final selection. Read literal
description, reviewed terms, uncertainty and inferred uses separately. For
difficult seed modifications, inspect a larger shortlist and state known hard
requirements explicitly; matching text alone is not proof of suitability.

Local activation is optional and separately authorized. A trusted installed
release under `releases/<id>/` can be selected with `tools/deploy_catalog.py
activate --deployment-root <root> --release-id <id> --expected-manifest-sha256
<trusted-digest> --expected-active <prior-id-or-none>`. Rollback uses that same
command with the retained prior release/digest and current ID, followed by reader
reload and `check-loaded`. The proof's r000002 is a temporary fixture, not a
delivered successor. General successor ingestion/publication remains deferred.

Record field feedback as an external append-only record, for example:

```json
{"release_id":"iip-r000001","search_profile_sha256":"sha256:532bded885ae394f2586b9e260e3fb9f1781e2c6c064f1184971fa68feb2bd97","request":{"text":"gold key","limit":8},"returned_icon_ids":[],"chosen_icon_id":null,"outcome":"useful_or_no_fit","reason":"visible evidence and intended use","consumer_context":"optional"}
```

Consumers own assignments and reservations; retrieval does not reserve icons.
Keep field feedback outside the immutable package. Prioritize real seed-query
failures for the next ranking-only investigation before paying for more corpus
observations. Do not tune this release against the opened holdout.

Not verified here: external distribution/licensing clearance, production consumer integration, general new-icon successor
ingestion, OS cold-cache performance, or pixel-level browser layout. No browser
was connected to UI automation; JavaScript behavior and HTTP/browser-shell checks
cover function but not rendered appearance. No manual-review gate is outstanding.
