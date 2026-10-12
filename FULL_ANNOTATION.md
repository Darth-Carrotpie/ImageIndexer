# Full icon annotation run

Status: **completed**, 2026-10-09 after owner approval. This is a build-time
work run, not a published package or a deployed dependency. It uses `gpt-6-sol`
with High reasoning, one 512-pixel-or-less checkerboard preview per frozen icon,
the unchanged v1 prompt/schema, and OpenAI Batch `/v1/responses`. The four
reviewed Halloween pairing exceptions use their verified background motif for
annotation; the catalog rendition reassociation remains a pre-release task.

The local [run directory](work/full-annotation-gpt6-sol-high-v1) contains:

- `plan.json`, `icons.jsonl`, `inputs/`, and `previews/`: 6,250 hash-checked,
  one-request-per-ID inputs split into 15 files below 150 MB each.
- `state.json`: uploaded file IDs, Batch IDs, statuses, and request counts.
- `outputs/`, `annotations.jsonl`, `failures.json`: retrieved results and any
  per-icon errors. All 6,250 results are now present; there are zero failures.
- `metering.json`: completed-icon count, token totals, estimated Standard and
  Batch charges, and a digest of the annotation result file.
- `runner-outcome.json`: `running`, `completed`, or `failed` for the unattended
  local runner; `runner.log` contains its progress and errors.

The completed run used 4,263,330 input tokens and 4,206,319 output tokens.
Its usage-based Batch charge estimate is **$25.294925** (not an invoice), close
to the earlier stratified $25.36 projection. The 12-icon Standard calibration
was an additional estimated $0.106408. See the
[validation report](work/full-annotation-gpt6-sol-high-v1/VALIDATION_REPORT.md)
for annotation and search-quality findings.

The background runner submitted one large batch at a time after the canary.
An initial four-batch wave found this account's actual 900,000-token Batch
queue limit: three files were rejected before processing, and one was accepted.
The rejected Batch IDs remain in `state.json`; they were retried from the same
input files after the active batch finished. The runner would have stopped on
other Batch failures, per-icon errors, invalid model responses, or an uncertain
submission outcome. It finished successfully. The key stayed in the user's DPAPI-protected file
under `%LOCALAPPDATA%\IndexedIconPack\openai-api-key.xml`, outside this tree;
the runner only exposes it to its child process and clears it on exit.

The [Batch API guide](https://developers.openai.com/api/docs/guides/batch)
documents the 50% processing discount and 24-hour window. The
[GPT-6 Sol model page](https://developers.openai.com/api/docs/models/gpt-6-sol)
lists the Standard token rates used for per-response estimates. Importing
annotations into a corrected release catalog and publishing that release are
separate, not-yet-completed steps.
