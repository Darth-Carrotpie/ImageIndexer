# Search and structured-observation improvement plan

Date: 2026-10-10  
Status: automated initial-release finishing complete on 2026-10-11; `iip-r000001` is ready for local field testing. Section 8 supersedes the earlier review/stop gates for this pass. See [readiness](work/initial-release-v1/READINESS.json) and the [final report](work/initial-release-v1/FINAL_SEARCH_REPORT.md).

## 1. Decision and scope

Improve retrieval using the existing observations first: structured filters, field-weighted SQLite FTS5 ranking, and query-by-example ("More Like This"). Measure that change before commissioning any new image observations. Only then consider bounded 100-icon observation trials and, if justified, one full-corpus observation rerun.

This is a focused successor to the search and annotation sequencing in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). That parent plan still governs identity, ingestion, packaging, and publication. The latest owner instruction permits a few limited observation trials and at most one additional whole-set pass; it does not make another paid run the first step. Model choice, estimated cost, and the dispatch envelope must be explicit at the applicable gates below.

Use the Ponytail approach: reuse the catalog, current annotation artifacts, SQLite, CLI/API, evaluation tools, and metering. No vector database, search server, new runtime model, or new dependency is required for the first implementation. Do not change AgentSmith, publish a release, activate a deployment, or ingest this document into its wiki as part of this work.

### Next-session starting instruction

> Read this plan, the applicable repository instructions, and the connected code. Verify the frozen inputs. Implement Phases 0-3 with the existing reviewed observations, leaving historical artifacts untouched. Produce the search-only comparison and stop at Gate S for owner review before any new image-model dispatch. Continue with later phases only under their recorded approval. Do not publish or deploy.

### Non-negotiable constraints

- Preserve all 6,250 frozen logical icon IDs, their catalog/pack identity, and the existing identity-ledger prefix. Never regenerate or reuse IDs because an annotation, index, model, or release changes.
- Keep logical icon identity separate from exact rendition SHA-256 identity. An exclusion applies to the logical icon and therefore all its renditions.
- Keep raw observations, previous reviews, pilot outputs, evaluation records, and cost ledgers immutable. New work gets new directories and explicit provenance.
- The delivered package remains standalone and language-neutral. No Unity GUIDs, `.meta` files, editor-specific tables, or Unity runtime dependency enter it.
- Runtime search remains read-only and usable through SQLite or the bundled CLI/API. Python is a requirement of the bundled tools, not of native Go consumers. Retain standard-library runtime dependencies; Pillow remains build-time only unless an approved change requires otherwise.
- Do not turn uncertain or inferred metadata into an asserted visual fact. No manual description-writing campaign for the corpus: new visual observations come from an image-input-capable model; scripts validate, normalize, and index them.

## 2. Starting evidence and files to inspect

These are the workspace facts at plan creation. Recheck them at implementation start; do not assume this document is a substitute for current files.

| Input | Current state and use |
|---|---|
| [Pre-annotation candidate](work/preannotation-v1/) | Unpublished schema-v1 catalog; 6,250 logical icons, 127 collections, 10,200 PNG renditions, 10,193 unique blobs. Not an installable final release. |
| [Identity freeze](work/identity-freeze-v1/identity-freeze.json) and [explanation](work/identity-freeze-v1/README.md) | Frozen assignments; four approved Halloween No Background pairing corrections remain to be incorporated into the first release candidate. Preserve IDs. |
| [Full annotation run](work/full-annotation-gpt6-sol-high-v1/) | GPT-6 Sol High: 6,250 valid observations. Raw output and two ordered reviewed-correction layers are available; they have not yet been imported into a final persistent catalog. |
| [Annotation validation](work/full-annotation-gpt6-sol-high-v1/VALIDATION_REPORT.md) | Integrity evidence and earlier retrieval comparisons. Existing assessment builds an annotated database in memory. |
| [Supplemental comparison](work/supplemental-vocabulary-astra-max-v1/PILOT_REPORT.md) | Original, Sol supplement, and Astra supplement all reached 35/50 exact-target hits in the top five. Useful-result judgments were 38/50, 39/50, and 38/50 respectively. The exposed V4 benchmark is explicitly not release-gate evidence. |
| [Main plan](IMPLEMENTATION_PLAN.md), [deployment contract](DEPLOYMENT.md), [ingestion workflow](INGESTION.md) | Preserve the existing identity, provenance, release, and consumer boundaries. General successor ingestion/publication is still incomplete. |

Record and verify these starting pins:

```text
catalog_id: indexed-icon-pack
pack_id: pack_487c4a62-24eb-4e87-9d84-79855cf3ac62
identity_registry_sha256:
  b0d0fb2b08349ca735a7596e4655b4451cc82b042af79940c7022b54c339fb1e
source_catalog_manifest_sha256:
  e23ad53570076f3bad800e016544538aa200edf9aea2905f219f759f16f5a6db
raw_annotations_sha256:
  c4d100ff9ae7298ecaa12eb8497a177aac3f363bf38209f732d28b67f0fd65aa
```

Trace these connected paths before editing:

- [iconctl.py](iconctl.py): `search_icons`, CLI arguments, `/api/v1/search`, browser rendering, and materialization guards. Today search ORs tokens, prioritizes distinct-term coverage, then uses BM25. It silently limits the token list to 16 and does not consume the structured observation fields.
- [build_catalog.py](tools/build_catalog.py): schema, `icon_keyword`, FTS projection, bootstrap, and annotation-plan. Existing FTS columns are ID, title, collection, description, and keywords.
- [assess_annotations.py](tools/assess_annotations.py): source validation, in-memory annotation projection, ranking calls, and judgment scoring. Today exact-target hits are accepted automatically; the revised evaluator must visually assess all shortlisted results, not only misses.
- [annotation_review.py](tools/annotation_review.py) and [validate_catalog.py](tools/validate_catalog.py): correction provenance, database/schema/state validation, and search-index consistency.
- Existing [tests](tests/), [full-run runner](tools/full_annotation_batch.py), [calibration runner](tools/metered_calibration.py), and [supplemental runner](tools/supplemental_pilot.py). Reuse their applicable mechanisms after checking assumptions; a vocabulary supplement is not the same experiment as a new structured observation.
- [Consumer skill](agent-skill/indexed-icon-pack/SKILL.md), [maintainer skill](agent-skill/indexed-icon-pack-ingest/SKILL.md), [usage](USAGE.md), and [requirements](INSTALLATION_AND_REQUIREMENTS.md).

The historical token-based API estimate is $30.810141 across calibration, the first full annotation, and both supplements. It is not an invoice, excludes interactive-agent usage, and is not a price estimate for a different future prompt/model.

## 3. Proposed search contract

This section specifies the new behavior; it is not documentation of commands that already exist.

### Inputs and semantics

| Input | Contract |
|---|---|
| `text` | Optional ordinary language used for ranking. Treat it as text, not executable FTS syntax. Preserve the current simple CLI search entry point. Reject over-limit input explicitly instead of silently discarding words. |
| `query` | Optional explicit FTS5 expression used as a required matching predicate. Supports documented fields, quoted phrases, Boolean operators, parentheses, prefixes, and `NEAR`. It is not SQL and not full Lucene syntax. |
| `like` | One optional existing logical icon ID providing positive example terms. It is a soft preference, not a requirement to copy every attribute. Unknown or retired/unavailable seeds produce a clear validation error. |
| `require` | Typed metadata constraints, initially subject, action, state, effect, symbol, color, and material. Values within a field are OR alternatives; different fields are AND requirements. Canonical values/approved aliases match indexed metadata, not arbitrary substrings. |
| `except` | Set of logical icon IDs to omit, irrespective of score. Exclude before ranking-window truncation and final selection. This is not negative semantic feedback. A seed can also be excluded. Reject malformed IDs; valid but unknown IDs may be ignored with a diagnostic. |
| `limit` | Requested maximum result count, integer 1-100, retaining the existing default of 12. Return that many when sufficient matching eligible icons exist; otherwise return fewer with an explicit shortfall. Never silently relax constraints to fill the count. |
| Existing filters | Keep collection and rendition-role availability filters. Resolve their interaction with `require` as additional AND constraints. |

Typed constraints and `query`, when both supplied, are conjunctive. With neither ranking input, constrained results use a documented stable order; an empty request remains deterministic browsing, not a relevance claim. With ranking inputs, candidates must match the text or seed channel as well as every hard constraint. Explain when results came only from the seed channel because the new text had no matches.

No automatic natural-language parser or per-query LLM is required. The calling agent can translate an item's description into `text` plus explicit visual requirements. Plain text remains a useful best-effort entry point, but it does not promise logical interpretation of negation or part relationships. A browser may expose the same typed filters.

Example request; the ID strings below are placeholders, not valid catalog IDs:

```json
{
  "text": "A skill that protects against freezing attacks",
  "like": "<existing-shield-icon-id>",
  "require": {"subject": ["shield"], "effect": ["ice", "frost"]},
  "except": ["<existing-shield-icon-id>", "<another-used-icon-id>"],
  "limit": 8
}
```

Advanced query examples, using proposed indexed field names:

```text
subject:key AND color:(gold OR golden)
subject:(coat OR cloak) AND color:blue
(subject:shield AND effect:(ice OR frost)) NOT effect:fire
```

Use SQLite's actual [FTS5 query grammar](https://www.sqlite.org/fts5.html#full_text_query_syntax), including its binary `NOT`; do not invent a half-compatible parser. Document the whitelist of searchable fields and supported syntax. Bind SQL parameters, validate typed inputs, cap request size/query complexity, and convert FTS errors into clear client errors. Support exclusion sets up to the whole catalog without exceeding SQLite parameter limits; use bounded parameter chunks or membership filtering over an untruncated ranked stream. Do not write temporary exclusion state into the catalog.

### Results and consumer responsibilities

- Return each logical icon once, with stable ID, preview/rendition references, concise metadata-based match reasons, requested/returned count, shortfall when present, and relevant catalog/release/search-profile identifiers. Scores are ranking signals, never calibrated confidence percentages.
- Do not call a metadata match visual proof. For example, a global `colors` list cannot prove that the key rather than its background is gold; missing `fire` metadata cannot prove fire is absent. Such errors belong in visual QA and may justify the conditional observation phase.
- `like` alone does not implicitly exclude its seed in the core API. A browser's "find alternatives" action can explicitly add the seed to `except`. IDs in `except` exclude every rendition of those IDs, not other IDs merely resembling them.
- The consuming application owns its used-icon set and any atomic assignment/reservation. Search does not reserve icons and cannot guarantee concurrent uniqueness. If the application first needs to find a similar existing item, it performs that item lookup and passes the resulting icon ID here.
- Subject resemblance, suitability for a business function, and pixel-level style similarity are different objectives. Metadata-based MLT helps the first two; do not advertise it as reliable image-style matching.
- Keep existing GET search compatibility where possible. Add a read-only JSON search request route only if needed for the typed contract and large exclusion sets; it must use the same search function. Browser and CLI must not implement separate ranking logic.

## 4. Smallest recommended retrieval design

### A. Index facts already collected

Project the existing structured fields into searchable columns and normalized keyword namespaces. The full run already contains subjects, colors, materials, action, effects, symbols, state, composition, visible text, inferred uses, uncertainties, description, and keywords. Indexing only descriptions and keyword strings throws away useful distinctions.

Reuse `icon_keyword` for normalized facet values and extend the existing FTS projection. Keep literal observations and inferred uses separate. Keep original observations and their model/prompt/image provenance auditable. One shared projection/import path must feed persistent candidates, validation, and evaluation; do not leave assessment with a better private index than consumers receive.

Do not treat the first subject as a guaranteed primary subject or a global color as the main object's color. Existing data does not establish those relations. Handle English morphology through a tested FTS tokenizer choice and a small versioned, field-scoped alias map. Avoid broad synonym expansion that merges ambiguous meanings such as weapon bows and ribbon bows. A tokenizer/profile change must be measurable and reproducible.

### B. Apply constraints, then rank

Evaluate lifecycle, collection, role, required facets, explicit FTS predicates, and exclusions before selecting top results. Replace distinct-word-count-first ranking with field-weighted BM25. Start with subject/action/effect and literal labels above descriptive prose; inferred uses and generic collection/title terms receive less influence. Collection-plus-ordinal titles must not dominate because they are convenient labels.

Use [FTS5's native column weights and BM25](https://www.sqlite.org/fts5.html#the_bm25_function), not a new implementation of BM25F. SQLite's lower BM25 score ranks better; its built-in algorithm constants are not an exposed tuning surface. Record the actual selected weights, tokenizer, alias digest, and implementation fingerprint in one search profile. Tune on development cases only.

### C. Add query-by-example

Use an icon's existing metadata as the seed document. Select a bounded set of informative terms using term/document frequencies available through SQLite, rather than copying the whole caption. Favor specific subject/action/effect terms and omit generic display/background boilerplate. Short icon observations need terms occurring once; do not blindly apply document-oriented frequency defaults that discard them. This follows the established [More Like This method](https://www.elastic.co/docs/reference/query-languages/query-dsl/query-dsl-mlt-query), without adding Elasticsearch.

When the request explicitly specifies a different color/effect, remove the conflicting seed preference from that field. The new requirement wins. A fire-shield seed plus required ice must not favor fire just because the seed description repeats it.

Rank text and seed channels independently, then use a small, fixed [reciprocal-rank fusion](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf) implementation when both exist. Start with rank constant 60, record it, and evaluate rather than treating it as universally optimal. With only one channel, use its ranking. At this corpus size, prefer scanning the complete matching ranked lists over an approximate cutoff that can strand valid results after exclusions. Break final ties by stable icon ID.

### D. Defer unproven additions

Do not add embeddings, learned rerankers, an ontology/scene graph, a server database, or automatic diversity penalties in the first pass. If later failure analysis shows lexical gaps or a genuine need for image-style/reference-plus-modification retrieval, propose a separate bounded experiment. [Composed image retrieval](https://arxiv.org/abs/1812.07119) is a relevant escalation, not proof that it will work on this collection. [MMR](https://www.cs.cmu.edu/~jgc/publication/The_Use_MMR_Diversity_Based_LTMIR_1998.pdf) is an optional response to demonstrated repetitive shortlists, not a default that suppresses close alternatives. Hashes remain identity/integrity tools, not semantic similarity measures.

## 5. Phased execution and gates

### Phase 0 - Freeze a reproducible baseline and evaluation protocol

1. Read the source map above and trace all callers of the shared search function. Check local changes and preserve unrelated work; do not assume the surrounding directory is a Git checkout.
2. Validate input hashes, reviewed-layer order, identity freeze, observation coverage, and preview/rendition linkage. Inspect the four recorded grouping corrections and their effect on seed/preview mapping before any candidate is used.
3. Create a new work area, proposed `work/search-retrieval-v1/`. Snapshot or hash-pin the legacy search implementation and effective reviewed observations so the old result can be reproduced after code changes. Leave both supplemental pilots unaccepted unless separately justified; the baseline is the original full observations plus accepted review layers.
4. Record corpus, tool, SQLite, profile, and benchmark fingerprints. Do not duplicate multi-gigabyte assets merely for offline comparisons; a private diagnostic database may resolve previews through verified existing artifacts. Such a diagnostic is not a publishable package.
5. Establish development cases and seal a fresh acceptance holdout before tuning. Keep the old V4 queries as exposed development regressions only. Record the proposed case allocation below and any owner adjustment before looking at final holdout results.

Output: `BASELINE_AND_PROTOCOL.md`, machine-readable input pins, frozen benchmark/judgment schemas, and reproducible legacy result files in the new work area.

### Phase 1 - Build a persistent structured search candidate

1. Implement the shared validated annotation import/projection using the existing builder and review mechanisms. Extend the review schema only if needed to correct structured fields; preserve raw hashes and reviewed provenance.
2. Build a new unpublished candidate, leaving `work/preannotation-v1/` untouched. Incorporate the approved rendition-pairing corrections without changing logical IDs or rewriting the frozen history; append the necessary correction history.
3. Add the structured FTS/facet projection and indexes. Version the persisted schema explicitly if its contract changes; do not silently reinterpret schema v1. Add an explicit unpublished annotated/search-candidate state rather than pretending it is pending annotation or published.
4. Make validation verify the full logical FTS/facet projection against the accepted observations, not just row IDs and descriptions. Enforce identity, rendition hashes, lifecycle, provenance, and manifest/state consistency. Keep unreleased materialization blocked.

Output: a reproducible annotated search candidate, profile manifest, and focused import/index tests. No new image-model calls.

### Phase 2 - Implement the shared search contract and consumer paths

1. Implement hard constraints, field-weighted BM25, morphology/approved aliases, and deterministic ordering in the shared search path. Remove word-coverage-first ranking as the primary policy; retain old coverage fields only if compatibility warrants clearly labeling them diagnostic.
2. Add one-seed MLT and rank fusion, with explicit new-requirement precedence and exclusion-before-limit behavior.
3. Wire the same request semantics into CLI, HTTP, and the existing browser. Keep the UI small: filters, "find alternatives," exclude selected IDs, and result-count/shortfall feedback. No redesigned application.
4. Add contract tests before running the corpus comparison. Keep the legacy baseline executable independently rather than making old tests assert the new policy accidentally.

Output: working offline search across real consumer entry points and concise proposed-contract documentation. No new image-model calls.

### Phase 3 - Measure search-only improvement; mandatory Gate S

Hold observations fixed. Compare legacy retrieval with the new system on identical requests where applicable, and report the additional typed/seed capability separately. Do not attribute benefits from better query formulation to ranking changes alone.

Use the evaluation protocol in Section 6. Classify failures as: missing/incorrect observation, discarded structured data, constraint/parser bug, ranking problem, vocabulary mismatch, ambiguous request, or genuinely absent suitable asset. Inspect previews rather than assigning every miss to the model.

Produce `SEARCH_ONLY_REPORT.md` with per-query results, aggregate metrics, representative wins/regressions, exclusion/constraint compliance, runtime measurements, and a recommendation. Include ablations for structured ranking versus seed assistance where relevant, without proliferating arbitrary weight experiments.

**Gate S - stop and present this report before new observations.**

- If development results are sufficient and remaining failures are not observation-related, skip Phases 4-5 and proceed to final validation after review.
- If search/constraint bugs dominate, fix those offline; another observation run is not the remedy.
- If visible omissions, wrong subjects, or unbound attributes are a material residual cause, propose the bounded observation trial and model/cost decision.
- If a suitable asset is absent, report that limitation. Reannotation cannot create it.

The search-only report is required even if the owner has already allowed another full observation pass in principle.

### Phase 4 - Conditional 100-icon structured-observation trials

Planning envelope: up to three trials of at most 100 icons each, as a concrete interpretation of "a few." Confirm the trial count, model configuration, and maximum spend before dispatch; this is a ceiling proposal, not an instruction to run all three. These are observation trials, distinct from the 100-query development benchmark.

1. At the model-choice gate, inspect actual preview sizes, detail requirements, observed ambiguity, and the 6,250-icon total. Recommend an available image-input model and reasoning effort using current authoritative model/pricing information. Pause for the owner's choice. Previous Astra Max supplemental results do not automatically select or disqualify a model for a different structured task.
2. Define the smallest observation-schema revision justified by Gate S. Candidates include an explicit nullable primary subject, secondary subjects, and simple subject/part/background attribute binding. Keep literal description, visible text, uncertainty, and inferred uses separate. Do not require a full scene graph or inflate every icon with speculative synonyms.
3. Use an image-grounded prompt, not benchmark answers. Freeze prompt/schema/model/effort/image-detail/token limits. Do not insert held-out queries, target terms, or judgments into prompts. Preserve the old observation alongside the new version.
4. Prefer a sample containing 70 stratified representative icons and 30 diagnosed difficult icons, excluding acceptance-holdout targets from targeted prompt tuning. Cover subject types, collections, image sizes/detail, and ambiguity. Label the two strata so oversampled difficult cases do not distort whole-set cost estimates.
5. Use paired icons when comparing trial configurations. A fresh sample for confirmation is appropriate if needed within the agreed trial count. Record selection rules and membership before dispatch; do not cherry-pick successful outputs.
6. Validate all outputs, then compare old versus new observations under the already-fixed search profile. Inspect for changed subject, color/background confusion, hallucinated material, lost details, and uncertainty handling. More keywords alone is not success.
7. Reuse existing request metering, resume, and failure handling where correct. Report token/cost distributions, incomplete responses and retries, expected whole-set cost with uncertainty, and the projected cumulative package estimate.

**Gate O - present trial evidence and stop.** Recommend either keeping existing observations, accepting only a justified reviewed subset, or using the one whole-set pass. Obtain explicit approval of the chosen full-run configuration and spend envelope before that pass. Do not silently apply old correction layers to new raw observations; their source hashes and claims must be reconciled.

### Phase 5 - Conditional one-time whole-set observation pass

Run only after Gates S and O. Allow at most one additional logical full-corpus observation pass over the existing 6,250 IDs. It can reuse pilot outputs only when their image, prompt, schema, model/configuration, and provenance exactly match the approved full-run fingerprint. Record reused versus newly requested IDs.

1. Create a new immutable run directory and coverage manifest; preserve the prior complete run as the fallback. No ID changes and no hidden replacement of raw observations.
2. Record model/version availability, prompt/schema and input-image hashes, request/response IDs, batch mode if used, start/end state, and every attempt's usage. Count failed, incomplete, and retried requests whenever usage is available; distinguish unknown charges from zero.
3. Pin the current price assumptions with date/source and preserve raw usage units. Report new-run estimate, earlier-run total, and cumulative package estimate separately. Do not count reasoning/cached tokens twice. Provider invoices may differ; retain enough information for reconciliation.
4. Enforce approved output/retry and total-spend bounds. Resume only incomplete work. Targeted repairs must remain within the explicitly approved envelope and be metered; they do not justify a second whole-corpus sweep. An unbounded retry loop is not permitted.
5. Keep API keys in the approved secret mechanism, never manifests, logs, committed files, or documentation. Stop safely on budget exhaustion, systemic errors, or incompatible model responses; preserve completed work.
6. Validate coverage, schema, provenance, review reconciliation, and visual samples. Do not silently fill missing observations with old data and claim a complete new run. An explicit mixed-version fallback is reviewable, not automatic acceptance.

This one-pass limit applies to new model observations, not repeated offline integrity checks or search evaluations, which may run without consuming the observation allowance.

### Phase 6 - Final comparison, acceptance, and implementation handoff

1. Compare these separately: old observations + old search; old observations + new search; and, if available, new observations + the same new search profile. Recompute index statistics as required by changed data but do not retune ranking using held-out answers.
2. Freeze the chosen observation set, search profile, and candidate before opening the fresh holdout. Run the final visual and contract checks in Section 6. If the holdout fails, report the failure; do not alter its denominator, shop for another test set, or invoke another full annotation run automatically.
3. Update existing usage, requirements, ingestion, deployment, and consumer/maintainer skill instructions to match implemented behavior. Before editing agent skills, follow the applicable skill-authoring instructions. Explain structured query formulation, seed use, exclusions, shortfalls, and assignment ownership with runnable examples.
4. Persist accepted observation provenance and a `search_profile_sha256` covering tokenizer, field weights, aliases, seed extraction/fusion policy, and relevant implementation version. Expose it in diagnostics/results and release metadata. Record benchmark/judgment fingerprints in QA evidence.
5. Preserve version meanings: accepted canonical metadata changes affect `catalog_revision`; search/tool-only changes affect release identity and search profile without changing logical IDs. Persisted schema changes affect `schema_version`; API compatibility remains separately versioned. Exact reproduction needs the catalog, search profile/tool version, and relevant SQLite environment, not catalog revision alone.
6. For ingestion, index new icons through the same projection/profile; regenerate dependent term statistics deterministically. Reuse observations by validated image/configuration provenance where allowed, never by ordinal filename alone. Compare successor catalogs against a fixed regression suite and preserve consumer ID/pixel pins.
7. Produce `FINAL_SEARCH_REPORT.md`, cost reconciliation if applicable, known limitations, and a release-readiness handoff. Include language-neutral request/response fixtures for Go or other consumers without modifying those consumers.

Passing this search plan does not itself publish or activate the package. Resume the remaining builder, ingestion, final-package validation, and publication work in the parent implementation plan. Never manufacture release readiness by adding a manifest to an unvalidated candidate.

## 6. Evaluation protocol and acceptance criteria

### Keep development and acceptance evidence separate

- Keep the exposed historical V4 set for continuity only. Its 35/50 exact-target rate means the originally selected icon appeared somewhere in the first five results for 35 queries; it is neither exhaustive recall nor proof that the other 15 queries lacked useful alternatives.
- Proposed new development set: 100 query cases, comprising 40 literal/attribute searches, 30 seed-plus-modification searches, 20 functional item descriptions, and 10 exclusion/no-suitable-result cases. These can be inspected and reused for offline tuning.
- Proposed sealed acceptance set: 50 positive, prompt-audited cases, comprising 25 literal, 15 seed-plus-modification, and 10 functional queries, plus 10 separate negative/exclusion cases. The owner revised the initial-release useful-top-five bar on 2026-10-10 to **at least 40/50 (80%)** positive cases. Confirm any allocation changes before final evaluation, not after seeing scores.
- Each positive acceptance case must have at least one independently verified suitable, non-excluded asset. Define required versus optional visual properties before running retrieval. Ambiguous or impossible requests must be resolved before sealing; once evaluated, report defects rather than silently removing them.
- Holdout cases/labels must not guide ranking or annotation-prompt tuning. Seeing the underlying images in a whole-corpus observation run is normal; feeding the test descriptions or expected answers into that run is not. Record who authored and judged the cases and any exposure; if independent review is unavailable, label that limitation and do not present self-review as independent release evidence.

### Judge the task, not just one chosen ID

Inspect the top five images for every positive case, including exact-target hits. A case succeeds when at least one candidate visibly satisfies its required properties and intended use; multiple acceptable IDs are allowed. Label candidates useful, partial, or unsuitable with a brief reason. A correct color on the wrong object is not a success for a required subject-and-color query. In functional searches, clearly state the accepted visual metaphor rather than assuming a single canonical icon.

Report:

| Measure | Meaning and gate |
|---|---|
| Useful Hit@5 | Fraction of positive queries with at least one visually acceptable result among the first five. Initial-release bar: at least 40/50 (80%). Report by query family as well as overall. |
| Exact-target ranks / Hit@1, @5, @10 | Historical diagnostic only; does not reject acceptable alternatives. |
| Acceptable-candidate Hit@20 | Whether a known acceptable result was retrieved before final shortlist selection. Helps distinguish candidate generation from ranking failures. Do not call this exhaustive Recall@20 without a complete relevance set. |
| Exclusion/typed-contract violations | Zero allowed: used IDs must not appear, constraints must be honored against indexed facts, and required syntax must not be silently relaxed. Separately report visual observation errors. |
| Count/empty-result behavior | Exactly the requested count when enough matching eligible logical icons exist; truthful shortfalls otherwise. No duplicate logical IDs or fabricated matches. |
| Performance | Warm/cold p50/p95 latency, memory, and index size on recorded hardware and SQLite version. Establish a practical budget from measurements; no unmeasured latency SLA. |

Show paired query outcomes and actual denominators, not only rounded percentages. A 50-case holdout is a practical acceptance sample, not a guarantee across every possible description. Record uncertainty and difficult families explicitly.

### Focused runnable checks

Extend the existing test suite rather than introduce a new framework. Cover at least:

- Required subject versus decorative/background words; phrase/Boolean precedence; malformed syntax and unsupported fields; English morphology and ambiguous aliases.
- Seed fire replaced by required ice; seed plus `except`; no seed terms remaining; unknown seed; valid unknown excluded ID; no-match text with seed-only candidates explained.
- Exclusion sets larger than the initial top results and larger than ordinary SQL placeholder limits; all renditions excluded; refill to `limit`; limits 1 and 100; invalid limits; all candidates excluded.
- Deterministic ties, no logical duplicates, rebuilding the same profile, and explicit profile changes without ID changes.
- Complete annotation-to-facet/FTS projection; uncertain/absent fields; correction hashes; old schema compatibility or explicit rejection; unpublished candidate still blocked from materialization.
- Visual evaluation not automatically accepting exact hits; multiple acceptable IDs; denominator preservation; holdout exposure recorded; failed/retried model calls retained in cost reporting.

Existing baseline validation command, from this delivery directory:

```powershell
uv run --no-project python -B tools/validate_catalog.py --package work/preannotation-v1 --freeze work/identity-freeze-v1/identity-freeze.json --json
```

Run the existing unit tests using the documented build environment, with `python -B -m unittest discover -s tests`. The new implementation must document its actual candidate-build and benchmark commands in the work report; do not invent commands here that the current tools do not support. Tests do not replace browser/API smoke checks or visual retrieval judgments.

## 7. Completion checklist

- [x] Historical inputs and stable IDs preserved; approved pairing corrections reconciled.
- [x] Persistent structured index, CLI, HTTP, browser, and evaluator share the real search implementation.
- [x] Free text, explicit queries, one-seed similarity, exclusions, and result counts follow the documented contract.
- [x] Search-only comparison delivered before new observations; the owner's 2026-10-11 instruction authorizes automated continuation under Section 8.
- [x] Observation trial and whole-set pass stayed within recorded model, count, retry, and spending approvals.
- [x] Fresh holdout, negative cases, contract tests, automated image judgments, and measured performance are reported without inflated claims.
- [x] Consumer and ingestion instructions, schema/profile/release identification, and reproducibility records match the fixed-corpus release scope.
- [x] Local packaging, relocation and isolated rollback passed. External publication, production activation and general successor ingestion remain outside this completed pass; no consumer repository was changed.

The default implementation path is Phases 0-3, review, then Phase 6. Phases 4-5 are available when measured observation deficiencies justify them, not prerequisites to making search useful.

## 8. Automated initial-release finishing pass (owner authorization, 2026-10-11)

The owner requires automated evaluation, with no independent manual reviewers.
The useful-top-five requirement is **40/50 (80%)**, not 90%. Plausible alternate
readings of schematic art count when visually supported; an exact noun match
or one preferred target ID is not required. Contradictory visible properties
still fail. Preserve literal descriptions, alternate search terms, and explicit
uncertainties separately; alternatives must not become hard visual facets.

This section replaces the human/custodian and repeat-approval requirements
above. GPT-6 Sol (`gpt-6-sol`, `reasoning.effort=high`) API calls are authorized;
do not substitute another model. If API access is unavailable or a session-model
change is necessary for a corpus run, stop for the owner's swap. Offline index
rebuilds preserve all original observations and do not require a model swap.
No external package distribution, consumer-repository change, or production activation is
implied. Produce a verified local field-test package, not a claim of production
quality. General successor ingestion is deferred from this fixed-corpus beta;
do not publish r000002 until its identity/reuse/retirement workflow is proven.

Execute these steps in order, retaining immutable evidence under
`work/initial-release-v1/`:

1. **Automated baseline judgment.** Rejudge all development top-five images in
   fresh stateless image-input API requests. Supply the request and required /
   optional properties, but no catalog captions, scores, target IDs, previous
   judgments, or expected success rate. Shuffle candidates and map labels back
   to ranks. Keep every response, image/input hash, usage and failure. Same-model
   author/judge correlation is a disclosed limitation, not human independence.
2. **Smallest justified improvement.** Reuse the existing reviewed-term and
   uncertainty layer for image-grounded alternate readings; preserve original
   captions. Fix shared retrieval behavior only where development evidence
   supports it. Do not add embeddings, a runtime LLM, or a new database. Run a
   bounded 100-icon API trial only if broader observations are needed. A full
   6,250-icon pass is conditional on trial benefit and uses the same frozen
   GPT-6 Sol High configuration, at most once. Record cost forecast before
   dispatch. Stop on systemic API failure, unknown charging, or required model
   substitution; never silently retry the whole corpus.
3. **Freeze and automated acceptance.** Freeze the selected candidate/profile
   first. Select 50 untouched target IDs deterministically across collections,
   excluding prior development/V4 targets. Stateless API authoring sees only
   target/seed images, not stored annotations or ranked results: 25 literal,
   15 seed-modification, 10 functional. A separate stateless image audit verifies
   target suitability before retrieval. Seal benchmark hashes, run once, and
   judge every top-five image with the same blinded rubric. Add 10 deterministic
   negative/exclusion checks. Require 40/50 useful, 10/10 truthful negatives,
   zero contract violations. Never replace failed cases or tune after opening.
4. **Consumer handoff.** Document `show`'s existing reviewed-term and uncertainty
   namespaces; require selection agents to read them and inspect previews when
   needed. Update CLI/API examples, language-neutral fixtures, installation and
   both bundled skills. Distinguish search score from confidence and consumer
   assignment from retrieval. Validate skill structure and runnable examples.
5. **Release integrity.** Implement the missing first-release builder using
   existing schema-v2 candidate/validator/deployment functions. Copy payloads
   into a new directory (no hardlinks), compute a canonical logical revision,
   bind the database/profile/identity ledger and sorted payload hashes in the
   immutable release manifest, and retain original IDs/history. Reject overwrite,
   escaping paths, corruption, and unsupported schema; teach deployment to
   validate schema v2 without weakening v1 support. No credentials, work logs,
   caches, or absolute workstation paths enter the consumer package.
6. **Automated release proof.** Run focused unit tests, full payload/identity/
   projection validation, clean relocation, CLI + HTTP search/show/thumbnail,
   exact-hash materialization/receipt, and isolated activation/rollback checks.
   Verify relocation does not depend on the development workspace. If acceptance
   fails, finish reusable implementation/checks but keep the package unreleased.
7. **Handoff.** Write `FINAL_SEARCH_REPORT.md` and machine-readable readiness
   evidence with actual denominators, costs, hashes, known failures, exact local
   install command, rollback command, and a field-feedback record format (query,
   candidate IDs, chosen ID, reason, release/profile pins). Report any unfinished
   gate honestly. No manual review is a release prerequisite.

API execution envelope for evaluation: Standard or Batch tier, max 4,096 output tokens,
at most two recorded attempts per request, concurrency at most four, and a
conservative $25 evaluation ceiling. Reuse the current metering and protected
local credential. Pricing checked 2026-10-11: $2 input / $0.20 cached input /
$2.50 cache-write / $10 output per million tokens, per
[official pricing](https://developers.openai.com/api/docs/pricing).
Observation trial/full-run spending is forecast separately before dispatch;
the evaluation allowance does not silently authorize unlimited annotation.

### Recorded trial decision, 2026-10-11

Blinded automated development Useful@5 improved from 62/90 to 67/90 with a
100-icon image-only alternative-label trial; exact-target @5 improved 45/90 to
55/90. Literal usefulness improved 32/40 to 37/40; functional usefulness remained
weak (10/20 to 9/20). Both candidates had zero contract violations. The trial
produced 465 additive phrases for $0.247680 estimated Batch cost, with no failed
responses. This supports one broader alternative-label pass, not replacement
of original descriptions or a claim that acceptance already passes.

The authorized API path uses the identical frozen GPT-6 Sol High prompt/schema,
4096-output-token limit and preview policy. Reuse the 100 exact-input trial
responses; request only the other 6,150 IDs. Linear new-call forecast is
$15.232320 (whole pass including trial: $15.480000); sample selection limits
that forecast. Set a $60 new-call ceiling including in-flight reservations,
at most two 500-request/150-MB batches active, and preserve every response.
Stop on incomplete/unknown-charge batches rather than rerunning the corpus.
This is the sole additional logical full-corpus observation pass in this plan.

Execution result: 6,150 new responses plus 100 exact-input reuses completed,
with zero inference failures and $15.467490 estimated new Batch cost. The prompt
requests 2-8 phrases; the import ceiling is ten to preserve one nine-phrase
response without deleting a wand/pestle alternative. All 6,250 responses still
require unique, lowercase, nonblank phrases of at most 80 characters. This
documented format tolerance does not change the 40/50 acceptance requirement.

### Completed finishing outcome

All seven Section 8 steps completed. The unchanged sealed holdout passed at
**43/50 (86%)**, with 10/10 negative cases and zero contract violations. Family
results are literal 24/25, seed modification 9/15 and functional 10/10. All
50 target/query pairs passed automated audit before retrieval, without repair.
The model remains GPT-6 Sol High throughout; finishing API estimate is
**$16.911966**. Original descriptions, IDs, hard facets and renditions remain
unchanged; 29,795 new alternative phrases were added to the existing review layer.

The local release is `work/initial-release-v1/releases/iip-r000001`, manifest
`sha256:9cd603812b940176e11de110a833cdc033728b057882c27fa405aa75c6075bc3`.
38 tests, both skill validators, deep integrity checks, clean relocation,
CLI/HTTP/browser-shell checks, exact materialization and isolated activation/
rollback pass. A rejected packaging attempt is preserved with its failure
diagnosis; it is not the deliverable. Pixel-level browser layout, external
distribution/licensing clearance, production integration and general successor
ingestion were not performed. No manual-review gate remains.

Use [READINESS.json](work/initial-release-v1/READINESS.json) for trusted release
pins and proof hashes, [the report](work/initial-release-v1/FINAL_SEARCH_REPORT.md)
for limitations and field-feedback format, and
[EXECUTION.md](work/initial-release-v1/EXECUTION.md) for the reproducible commands
and recovery history. Next work is field feedback, especially seed modifications;
do not tune the released package or reuse this opened holdout as a fresh gate.
