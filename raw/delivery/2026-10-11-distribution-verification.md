# Distribution restore verification

> Source: Local workbench file `work/nextcloud-distribution-v1/VERIFICATION.json`
> Collected: 2026-10-11
> Published: 2026-10-11
> Source-SHA256: 2d8f4fa335f6af1fbaa6cbd29a0f3839d6220f634738b23842eb1c95f5957fb9

{
  "artifacts": [
    {
      "filename": "IndexedIconPack-iip-r000001-images-001.zip",
      "sha256": "sha256:77304aace6da410253d2011e3961fdaae85c6bc897e271895513c33a2456b36c",
      "size": 999916163
    },
    {
      "filename": "IndexedIconPack-iip-r000001-images-002.zip",
      "sha256": "sha256:49043b30dab63742eb0a635585c5fa59e0090ee7d71646c37c945358d73b1d35",
      "size": 999830739
    },
    {
      "filename": "IndexedIconPack-iip-r000001-images-003.zip",
      "sha256": "sha256:9cec13ae6dd6fd6933eb22ec4a75c94bad7469506eb58cb3bab225fe5fb78537",
      "size": 999813019
    },
    {
      "filename": "IndexedIconPack-iip-r000001-images-004.zip",
      "sha256": "sha256:91aa03a022a5d0789cd660a680eb35dea6b59456824cfe306097847a2d4c03f8",
      "size": 685494505
    },
    {
      "filename": "IndexedIconPack-iip-r000001-no-icons.zip",
      "sha256": "sha256:188da5aacc7727b5451685d573b2ffaf55529023d170f3336da7a6f6a50c5d3b",
      "size": 25331175
    }
  ],
  "checks": {
    "clean_restore": true,
    "cli_search_returned": 5,
    "deep_validation": true,
    "live_nextcloud_tested": false,
    "no_images_in_bootstrap": true,
    "repeat_install": true,
    "temporary_copy_removed": true
  },
  "release_manifest_sha256": "sha256:9cd603812b940176e11de110a833cdc033728b057882c27fa405aa75c6075bc3",
  "status": "ready_for_nextcloud_configuration"
}

