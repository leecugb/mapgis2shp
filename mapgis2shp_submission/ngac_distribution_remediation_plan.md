# NGAC fixture redistribution remediation plan

Status: user-selected migration to user-supplied data is being implemented. Historical public copies require separate external actions.

## 1. Scope

This plan covers the 12 original J43C001002 vectors, five accompanying SLIB libraries and the 16 files under `reader_native` derived from the same dataset. The DOI is `10.23650/data.A.2018.NGA131703.K1.1.1.V1`.

The independent synthetic MapGIS fixtures and the user-authored Writer SHP batches are outside this NGAC-specific removal scope and remain required regression fixtures.

## 2. Current-source and future-package actions

- Move original data out of the Git working tree.
- Ignore `tests/fixtures/jwd`, `tests/fixtures/slib` and `tests/fixtures/reader_native` so local copies cannot be committed accidentally.
- Remove their Hatch wheel `force-include` entries.
- Make archive inspection fail if any covered data file appears in wheel or sdist.
- Retain the manifests and `DATA_ATTRIBUTION.md` as provenance and SHA-256 registries, not as substitutes for data.
- Resolve real integration data through `PYMAPGIS_JWD`, `PYMAPGIS_SLIB` and `PYMAPGIS_READER_NATIVE`.
- Produce explicit optional-integration skips when external data are absent. Invalid configured paths and checksum mismatches still fail.
- Run the real rendering example in CI only when external fixture directories are configured. Print the reason when it is not run.
- Update the manuscript, Quickstart, test counts and archive counts from a fresh build and CI run. Do not keep claims of a self-contained current wheel.

## 3. Historical GitHub objects

Removing files from a new commit does not remove historical blobs.

A complete history-remediation attempt would require:

1. Inform all maintainers and choose a maintenance window.
2. Rewrite affected history with a reviewed tool such as `git filter-repo`, preserving the original data only in an access-controlled backup.
3. Force-push every affected branch and tag after explicit maintainer approval.
4. Ask GitHub Support to clear relevant cached views and assess forks and pull-request refs.
5. Record that clones, forks, mirrors and downloaded archives cannot be recalled.

No history rewrite or force-push is authorized by this document.

## 4. Existing PyPI release

PyPI 2.7.1 wheel and sdist already contain covered data.

- Yanking only reduces default installation visibility and does not guarantee file removal.
- Deleting release files requires a separate explicit owner decision and does not purge mirrors or downloaded copies.
- Record the exact files, upload dates and requested remediation in any PyPI support request.

No release deletion, yank or support request is authorized by this document.

## 5. Existing Zenodo archive

Zenodo version archives are intended to be durable. Any covered data in the archived release requires a Zenodo support request and a documented explanation. A DOI or archived version must not be described as erased merely because a new Git commit excludes the data.

No Zenodo request is authorized by this document.

## 6. Permission alternative

The preferred way to regularize both existing and future distribution is a written entry-level authorization from NGAC or the publishing-system editorial office. Use `ngac_redistribution_request_draft.md` and attach the file manifest. The request has not been sent and is not evidence of authorization.

If written authorization is obtained, record its scope, channels, required notice and whether it covers historical distribution before considering any restoration of bundled fixtures.

## 7. Closure criteria

The future-distribution boundary may be marked complete only after a clean Git tree and fresh wheel/sdist pass the no-data inspection and the manuscript no longer claims current bundled data.

The historical-redistribution gate remains open until one of these occurs:

- written authorization covers the existing public copies; or
- the documented GitHub, PyPI and Zenodo remediation steps are completed, with an explicit acknowledgment that perfect recall is impossible.

Do not mark the complete NGAC gate closed solely because a new commit removes the files.
