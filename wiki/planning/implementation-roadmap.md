# Implementation and public-release roadmap

> Sources: Initial readiness, 2026-10-11; owner public-data directions and public catalog proof, 2026-10-12; earlier distribution proposal, 2026-10-11
> Raw: [Initial readiness](../../raw/quality/2026-10-11-initial-release-readiness.md); [Owner decision](../../raw/planning/2026-10-12-public-data-directions.md); [Public catalog proof](../../raw/delivery/2026-10-12-public-catalog-proof.md); [Earlier proposal](../../raw/planning/2026-10-11-distribution-and-ingestion-proposal.md); [Clone image-restore proof](../../raw/delivery/2026-10-12-private-image-restore-proof.md)
> Updated: 2026-10-12

## Completed baseline

- Fixed-corpus structured search, alternative descriptions and automated
  acceptance at the owner's 80% initial-release requirement.
- Immutable first release, stable identities and exact-rendition materialization.
- Private image archives and resumable verified installation.
- Public `catalog/` containing the original database and manifests, readable
  observation export, pinned runtime and downloader.
- Ordinary Git rules that include the published database but exclude private
  images, configuration, caches and working databases.
- Byte-preserving checkout attributes and automated publication checks.
- MIT software license, separate image-rights notice and revised no-icon ZIP.
- Automated suite: 53 passing tests in the workbench and isolated Git clone.
- Clone hydration from existing private ZIPs, deep and repeat verification,
  exact-image copying, and clean Git status after installation.

The prior plan called for a source-only export and a separate data download.

> **Status: Outdated** (2026-10-12)
> The owner requires generated data in the clone. Public catalog preparation is
> complete locally; remote upload and actual cloud installation remain open.

## Next: owner publication and actual cloud proof

Follow the exact [manual release steps](../delivery/distribution-and-repository.md):
commit/push the checked public files, upload the unchanged private image archives,
then configure and test a fresh clone through the actual Nextcloud share.

**Acceptance:** clone-only search works without credentials; private-image
installation passes deep verification; repeated installation is safe; restored
images/configuration remain untracked. Failed credentials, corruption and
resume behavior have local automated coverage, not yet real-server proof.

No annotation or database rebuild is needed. No independent manual reviewer is
required; the owner supplies access and decides when to publish.

## Then: tag and publish the field-test download

Tag code and data together after the real remote proof. Publish the revised
no-icon ZIP and checksums as optional prerelease assets. Keep all private images,
configuration and passwords out of the public repository and attached assets.

**Acceptance:** the tagged clone and standalone ZIP expose the same pinned
catalog. Metadata-only readiness is distinct from a fully installed release.
Do not replace already published bytes under an immutable identity.

## After feedback: additional packages

Prioritize actual seed-query failures before new ranking machinery or a paid
corpus rerun. Feedback remains outside immutable releases and includes request,
candidate/chosen IDs, reason and release/profile pins.

Implement the [append-only ingestion plan](package-ingestion.md), including the
single-pack assumptions and successor-publication gaps. The new observation
JSONL is an inspection/export format, not proof that this ingestion path exists.

**Gate:** preserve earlier IDs and pixels, run automated acceptance, and pass the
ordinary-Git size/publication checks before exporting a successor. A full-corpus
rebuild or new paid scope remains an owner stop point. Growth beyond ordinary
Git storage requires an explicit new decision.

## Runnable checks

From the source checkout:

```powershell
uv.exe run --no-project python -B tools/prepare_public_catalog.py check --repository .
uv.exe run --no-project --with-requirements requirements-build.txt python -B -m unittest discover -s tests
```

From a clone with installed images:

```powershell
python -B catalog/release/iip-r000001/iconctl.py --package catalog/release/iip-r000001 verify --deep --json
python -B catalog/release/iip-r000001/iconctl.py --package catalog/release/iip-r000001 version --json
```

These commands do not publish or activate a service. Future ingestion commands
in older planning documents remain non-runnable until implemented.

## See Also

- [Distribution and repository](../delivery/distribution-and-repository.md)
- [Additional-package ingestion](package-ingestion.md)
- [Nextcloud installation](../delivery/nextcloud-installation.md)
- [Verified release and limitations](../quality/release-evidence.md)
