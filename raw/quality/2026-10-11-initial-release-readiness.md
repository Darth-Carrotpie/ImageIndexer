# Initial release readiness

> Source: Local workbench file `work/initial-release-v1/READINESS.json`
> Collected: 2026-10-11
> Published: 2026-10-11
> Source-SHA256: 3c50d35327f4460e92e87b73854939ef5374995b8934bf1dfdb4d08b68b33119

{
  "readiness_schema_version": 1,
  "status": "ready_for_local_field_test",
  "date": "2026-10-11",
  "automated_only": true,
  "release_relative_path": "releases/iip-r000001",
  "release_id": "iip-r000001",
  "release_manifest_sha256": "sha256:9cd603812b940176e11de110a833cdc033728b057882c27fa405aa75c6075bc3",
  "catalog_revision": "sha256:d96e65c62e0928fd11ceccd50f1a41217965704ae7257164ff930d0641b207f2",
  "catalog_sqlite_sha256": "sha256:960187d88ffd4999aebb2608a7f8a2fcb2a1b8795122bce10edf90a7a6d51968",
  "search_profile_sha256": "sha256:532bded885ae394f2586b9e260e3fb9f1781e2c6c064f1184971fa68feb2bd97",
  "payload_files": 16468,
  "payload_bytes_excluding_manifest": 3767124351,
  "acceptance": {
    "useful_at_5": 43,
    "positive_cases": 50,
    "required_useful": 40,
    "negative_successes": 10,
    "negative_cases": 10,
    "contract_violations": 0,
    "literal": [24, 25],
    "seed_modification": [9, 15],
    "functional": [10, 10],
    "target_audit": [50, 50],
    "post_seal_query_or_ranking_changes": false
  },
  "verification": {
    "unit_tests_passed": 38,
    "bundled_skills_validated": 2,
    "deep_payload_and_revision_validation": true,
    "independent_relocated_copy": true,
    "cli_search_show_version": true,
    "exact_hash_materialization_receipt_and_no_overwrite": true,
    "http_parity_preview_and_blob_hashes": true,
    "http_all_6250_exclusions": true,
    "browser_shell_and_detail_javascript": true,
    "isolated_activation_and_rollback": true,
    "temporary_rehearsal_copies_cleaned": true,
    "fresh_warm_result_consistency_cases": 100
  },
  "runtime_ms": {
    "fresh_reader_including_hash_verification": {"p50": 163.4509, "p95": 244.5304},
    "warm_query": {"p50": 39.8001, "p95": 124.6349},
    "os_cache_flushed": false
  },
  "finishing_api_estimated_usd": "16.911966",
  "cumulative_recorded_api_estimated_usd": "47.722107",
  "api_estimate_is_invoice": false,
  "model": "gpt-6-sol",
  "reasoning_effort": "high",
  "corpus_new_requests": 6150,
  "corpus_reused_responses": 100,
  "corpus_failed_responses": 0,
  "unknown_api_charges": 0,
  "evidence_sha256": {
    "acceptance-positive/score.json": "e7ee77c04fd33fdf4e109a78cd5cbce1fec95d5477ace17e8a235d3d084abd45",
    "acceptance-negative/score.json": "d362d751e6a80c57eea151ca8cbc5f51e128632ea77c3c6b86dde538c8960fce",
    "acceptance-seal.json": "4c0b519c0e5129f13c23fdcf785c206353b7e83b685fce0fd07f2d289470dbb9",
    "relocation-smoke.json": "cc264068f31a0a48aa52ac3e57be179505fb7b3e2c13b6b375568e5f15223d77",
    "release-runtime.json": "e7400e2cea1f21a93196bf7b909804f42ee0945480fe5808d9b517ae2f95af42",
    "FINAL_SEARCH_REPORT.md": "d367cae489808e2bc62c8f4998bc8d2a21718ea23933dd41ca5dd32c8593a0b6"
  },
  "rejected_packaging_evidence": "rejected-packaging/FAILURE.md",
  "limitations": [
    "same-model stateless author/audit/judge; no human independence claimed",
    "seed-modification usefulness is 9/15 on acceptance and 17/30 on development",
    "pixel-level browser layout not verified because no browser was connected",
    "OS cold-cache performance and production consumer integration not tested",
    "general new-icon successor ingestion/publication deferred",
    "external distribution/licensing clearance not performed"
  ],
  "external_distribution_performed": false,
  "production_activation_performed": false,
  "consumer_repositories_changed": false
}

