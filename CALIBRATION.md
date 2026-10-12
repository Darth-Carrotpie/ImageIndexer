# Metered annotation calibration

Status: **completed 2026-10-09; full Batch annotation subsequently completed**.
See the
[metered result](work/calibration-gpt6-sol-high-v1/CALIBRATION_REPORT.md):
12 successful requests cost an estimated $0.106408 at Standard rates and
project to about $50.71 at Standard rates, or approximately $25.36 at the
[Batch API's 50% discount](https://developers.openai.com/api/docs/guides/batch),
for 6,250 icons. This remains a preliminary estimate, not an invoice. The
owner separately authorized the full run on 2026-10-09. Do not put an API key in this
repository or paste it into chat.

The fixed calibration uses `gpt-6-sol` with High reasoning and 512 px-or-less
checkerboard previews from the approved pilot. It makes 12 Responses API
requests (16 image inputs): four ambiguous pairs, four candidate-pair icons,
and four singles. The candidate and single samples include indexed-color and
originally larger-than-512-pixel icons. It uses the frozen
[`annotation_prompt_v1.txt`](tools/annotation_prompt_v1.txt) and
[`annotation_response_schema_v1.json`](tools/annotation_response_schema_v1.json),
one structured annotation per request, and `store: false`.

From this directory, inspect the offline plan:

```powershell
uv run --no-project python -B tools/metered_calibration.py --pilot work/pilot-gpt6-sol-high-v2 --output work/calibration-gpt6-sol-high-v1
```

With an OpenAI Platform key securely available in the **process environment**
as `OPENAI_API_KEY`, add `--execute` to that command. The script
does not print or save the key. It records each response ID, returned model,
service tier, token usage (including reasoning/output and cache details),
annotation, and standard-rate cost estimate in `results.jsonl`, then writes a
stratum-weighted 6,250-icon projection to `summary.json`. It can resume an
interrupted run without repeating already recorded successful requests; a
timed-out request may still have been billed, so review account usage before
retrying it.

The estimate used the [official GPT-6 Sol standard rates](https://developers.openai.com/api/docs/models/gpt-6-sol):
$2 per million uncached input tokens, $0.20 cached input, $2.50 cache writes,
and $10 output. Actual charges can differ by processing tier, region, caching,
or future price changes. [OpenAI's vision guidance](https://developers.openai.com/api/docs/guides/images-vision)
notes that image inputs consume tokens. This calibration is deliberately small;
its weighted projection is a planning estimate, not a bill or confidence
interval. See [FULL_ANNOTATION.md](FULL_ANNOTATION.md) for live metering.
