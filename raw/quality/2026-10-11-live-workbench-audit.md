# Live workbench audit for wiki initialization

> Source: Read-only command results and source inspection in the local package workbench
> Collected: 2026-10-11
> Published: 2026-10-11

The Unity test-project root and its ancestors are not a Git repository:
`git rev-parse --show-toplevel` returned
`fatal: not a git repository (or any of the parent directories): .git`.
No raw/ or wiki/ existed in the package workbench before this ingestion.

The current package workbench is Builds/IndexedIconPack_v1 relative to the
Unity test project. Its siblings include generated Unity Library, Temp and
Logs directories and the source Assets tree. These are not a proposed public
source repository allowlist.

The test command run during this wiki task was:

    uv.exe run --no-project --with-requirements requirements-build.txt python -B -m unittest discover -s tests

Observed result: Ran 48 tests in 11.587s; OK. The earlier initial-release
readiness record reports 38 tests; ten transport tests were added afterward.
This task made no model/API calls and no database or image rebuilds.

The prepared bootstrap has no configured cloud URL or share token. A live
Nextcloud install is not verified. The original release manifest SHA-256
still equals 9cd603812b940176e11de110a833cdc033728b057882c27fa405aa75c6075bc3.
Distribution verification reports clean restore, repeat installation, deep
validation and a CLI search returning five results. No public Git remote,
public release, production activation or software license was created here.

requirements-build.txt contains exactly Pillow==12.3.0.
The consumer runtime and downloader use Python standard-library facilities.
The browser is served by iconctl.py; there is no separate frontend build.
Node is used by a browser-behavior regression test, not by the consumer runtime.

## Source findings, not implemented roadmap commands

tools/build_catalog.py registers only bootstrap and annotation-plan in its CLI.
The --base help specifies a prior unpublished candidate and unchanged/additive
inputs only. Its scanner requires collection/role/file paths, recognizes the
Background, No Background and PNG folders, and infers provisional grouping
from numbered filenames. It is not a general source-set adapter.

Its read_registry function sets a single pack_id from the first event and
rejects any later event whose pack_id differs. The logical revision helper
selects catalog_id,pack_id from catalog_state and requires one row. The
schema-v2 search builder's apply_corrections requires exactly four initial-
corpus pairing corrections. These assumptions must be reviewed before adding
a different pack, not bypassed by re-running bootstrap over a published base.

tools/build_initial_release.py requires a new output named iip-r000001 and
accepts an unpublished candidate only. General successor publication and
publication-head compare-and-advance remain deferred. The local deployment
selector is implemented, but does not copy files, restart services, or create
a general successor release.

Documentation samples that show schema_version: 1 or generic release/update
commands are examples or planned contracts, not evidence that the current
field-test catalog is schema v1 or that those commands are executable.
The accepted field-test catalog uses schema v2.
