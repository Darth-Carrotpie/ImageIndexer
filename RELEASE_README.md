# Indexed Icon Pack - initial field test

6,250 stable logical icons, 127 collections, 10,200 PNG renditions, and 10,193
content-addressed blobs. SQLite schema v2 provides offline structured FTS5 search,
metadata-based examples, hard constraints and logical-icon exclusions.

From this directory:

```powershell
python iconctl.py verify --deep
python iconctl.py version --json
python iconctl.py search "gold key" --limit 8 --json
python iconctl.py serve
```

Python 3.11+ with SQLite FTS5 is sufficient for bundled runtime tools. No API key
or model is used at runtime. Native consumers may read SQLite or use the localhost
HTTP API. Keep this package outside consumer repositories; copy only selected
renditions through `materialize` when requested.

Read [usage](USAGE.md), [installation](INSTALLATION_AND_REQUIREMENTS.md),
[deployment](DEPLOYMENT.md), and [automated QA evidence](qa/FINAL_SEARCH_REPORT.md).
Literal captions, alternative readings and uncertainty support later LLM
selection; a metadata hit is not visual proof. The initial useful-top-five gate
is 80% on 50 automated positive cases, plus 10 negative cases and zero contract
violations. Same-model evaluation can make correlated errors; this is a field
test, not a guarantee for arbitrary queries.

Record feedback with request, returned/chosen icon IDs, reason, release ID and
profile hash. Consumers own reservations and assignments. General successor
ingestion/publication is deferred; do not modify this immutable package or
publish a successor by hand. No production service is activated by unpacking it.
