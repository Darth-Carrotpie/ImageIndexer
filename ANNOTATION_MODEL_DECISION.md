# Annotation model decision — pilot completed

Status: **owner selected GPT-6 Sol High; 100-icon pilot approved**.
This is not authorization for the full annotation run or publication. See the
[pilot report](work/pilot-gpt6-sol-high-v2/PILOT_REPORT.md) for results and
limitations, the [ID freeze](work/identity-freeze-v1/README.md), and the
[metered calibration status](CALIBRATION.md).
The machine-readable inventory is `work/annotation-decision-v1.json` (SHA-256
`91462c434b579fc141f9192e27bae5e491420f84ef0787a84113f06ad241f9195`).

## Workload and quality target

- 6,250 provisional logical icons and 10,200 original PNG renditions; 10,193
  unique image blobs. The unpublished candidate occupies 3,703,129,642 bytes.
- The default proposal is one image-input request per logical icon (6,250),
  using the preferred rendition. Inspect a second rendition where needed,
  especially four ambiguous Halloween background/transparent pairings. Do not
  treat a same-ordinal pair as proven identical merely because filenames agree.
- 10,050 original renditions fit within 512 × 512 pixels; 150 exceed that
  bound. Make annotation previews at no more than 512 pixels on the longest
  edge, preserving aspect ratio and the untouched originals. The existing
  256-pixel thumbnails are for browsing, not the annotation source.
- Each result should contain a literal visual description and searchable
  subjects, materials, colors, actions, effects, symbols, visible text, state,
  and composition. Possible UI uses are a separate inference field. Never
  infer visible content solely from source filenames or collection labels.

The prepared plan includes a fixed 100-icon sample spanning candidate pairs,
ambiguous pairs, and singles. It proposes this instruction: inspect the icon
image(s), describe only visibly supported content, separate observations from
possible uses, and flag uncertain cross-rendition identity. Output structured
data. The exact sample IDs and schema are in the JSON packet above.

## Original recommendation and owner choice

The original packet recommended **GPT-6.1 Sol** for the 100-icon pilot. It accepts image input and
supports structured output. For tiny, stylized fantasy art, the distinction
between a visible object and an inferred game meaning matters; choosing the
more capable of these two candidates is a quality-first hypothesis, not a
measured result for this corpus. Its published standard API rates are $2 per
million input tokens and $10 per million output tokens. See the
[official model page](https://developers.openai.com/api/docs/models/gpt-6.1-sol).

**GPT-6 Luna** is the lower-cost alternative. It also accepts image input and
structured output, with published standard rates of $0.10 per million input
tokens and $0.50 per million output tokens. We have not yet compared its icon
caption accuracy against Sol. See the
[official model page](https://developers.openai.com/api/docs/models/gpt-6-luna).

The owner selected **GPT-6 Sol** at High reasoning effort because GPT-6.1 Sol
was unavailable in their environment. The corrected 100-icon pilot used that
choice. Its agent route did not expose token or billable usage; therefore the
original metering requirement remains unmet.

Image-token usage depends on the chosen model, image dimensions, and detail
setting, so published token rates do **not** establish a trustworthy total for
6,250 icons. Obtain measured input/output tokens and cost on a metered route
before projecting the full run. The
[vision cost guide](https://developers.openai.com/api/docs/guides/images-vision)
explains image billing. If the pilot is accepted, the
[Batch API](https://developers.openai.com/api/docs/guides/batch) may lower the
cost of the later asynchronous run by 50%, subject to its turnaround and
operational limits. Recheck live pricing and availability at execution time.

## Next gates

1. Preserve the [frozen IDs](work/identity-freeze-v1/README.md) and apply the
   four recorded source-occurrence corrections before first publication.
2. Review the [completed metered calibration](CALIBRATION.md) and its preliminary
   $50.71 Standard-rate projection. The pilot agent route itself supplied no
   request IDs or usage figures; the separate API sample now supplies those
   figures for 12 icons.
3. Separately approve the full annotation run. Only validated annotations and
   resolved identity decisions can enter the first immutable release.

Until these gates pass, the catalog remains an **unreleased pre-annotation candidate**.
Its provisional IDs must not be stored in consumer products as published links.
