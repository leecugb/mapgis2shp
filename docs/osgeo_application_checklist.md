# OSGeo Community Project application checklist

- **Project:** mapgis2shp
- **Prepared:** 2026-10-17
- **Purpose:** Internal preparation and hand-off for the project team. This is not
  an OSGeo approval document.

## Checklist status

| OSGeo item | Current evidence | Status before public actions |
|---|---|---|
| Geospatial purpose | [README](../README.md) and [project-page draft](osgeo_community_project.md) | Ready locally |
| User documentation | README installation, quick start, CLI and API; [format reference](MapGIS_Vector_Format.md) | Ready |
| OSI-approved licence | [Apache-2.0](../LICENSE), package metadata, GitHub licence detection | Ready |
| File-header and provenance review | SPDX identifiers in release modules; [review record](license_provenance.md) | Ready locally |
| Clear contribution policy | [CONTRIBUTING.md](../CONTRIBUTING.md) | Ready locally |
| Code of conduct | [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md), Contributor Covenant 2.1 | Ready locally |
| Public collaboration evidence | GitHub reported 0 issues, 0 pull requests and 1 contributor when checked on 2026-10-17 | Needs genuine public activity |
| OSGeo project page | [Draft page](osgeo_community_project.md) | Ready for project review and publication |

The first six items must be visible in the public repository before they can be
counted as application evidence. Local, unpushed files are preparation only.

## Recommended public sequence

1. Run the source and documentation checks after the SPDX and documentation
   changes.
2. Put the community documents, SPDX headers, provenance review, and OSGeo page
   draft into one focused, genuine pull request. This provides a real example
   of the project's public change process; it should not be described as
   external collaboration.
3. Update the GitHub repository description so that it describes both reading
   and writing, matching the 2.4.0 README and PyPI release.
4. Open a small number of substantive issues for actual unresolved work. Keep
   them technical and actionable; do not open placeholder issues merely to
   create a numerical collaboration record.
5. Review and publish the project page through the appropriate OSGeo process,
   then contact the Incubation Committee for review. Remove the draft-status
   note from the page only in the approved publishing workflow.

## Genuine issue candidates

### Validate Writer output in MapGIS 6.7

**Problem:** Reader–Writer–Reader tests establish internal consistency but do
not prove that MapGIS 6.7 accepts every written file.

**Requested evidence:** For representative `.wt`, `.wl`, and `.wp` outputs,
record the MapGIS version, open/save behaviour, geometry, Chinese and temporal
attributes, polygon fill behaviour, and any errors. Preserve failures as
reproduction cases rather than reporting only successful examples.

### Measure runtime and peak memory for the 400 MB polygon input

**Problem:** The existing performance benchmark covers the 36-layer corpus,
not the separate 400 MB polygon dataset.

**Requested evidence:** When the dataset is available, use the documented
benchmark protocol to report timing samples, absolute and incremental peak
memory, hardware, software versions, and any topology-repair effects. Do not
reuse the small-corpus measurements as an estimate for the large file.

### Document unsupported extended symbol-library records

**Problem:** Structural parsing must stop honestly when symbol records or
library versions are unsupported.

**Requested evidence:** Add redistributable fixtures or structural summaries
for unsupported records, document where decoding stops, and test that no
invented glyph geometry is returned. This issue should remain scoped to format
support, not geological semantic adjudication.

## Draft message to the Incubation Committee

**Subject:** OSGeo Community Project review request: mapgis2shp

Dear OSGeo Incubation Committee,

I would like to request guidance and review for mapgis2shp as an OSGeo
Community Project.

mapgis2shp (`pymapgis` on import) is an Apache-2.0 Python library and CLI for
reading, writing, and converting MapGIS 6.x/67 binary vector formats. It
provides GeoPandas interoperability, CRS inference, polygon-topology
reconstruction, graphic-parameter decoding, and structural parsers for MapGIS
symbol and line-style libraries. The current release is 2.4.0 on PyPI.

Project page: **insert the published project-page URL before sending**

Source: https://github.com/leecugb/mapgis2shp

PyPI: https://pypi.org/project/mapgis2shp/

The repository includes user and developer documentation, an Apache-2.0
licence, a contributing guide, a Contributor Covenant code of conduct, and a
licence/provenance review. We are also strengthening the project's public
collaboration record through substantive issues and pull requests rather than
placeholder activity.

I would appreciate the committee's review of the application materials and
guidance on any remaining gaps.

Best regards,

Shijie Li

1045105061@qq.com

## Public-action boundary

Publishing pages, opening issues or pull requests, changing repository metadata,
and contacting OSGeo are outward-facing actions. They require an explicit
project-owner decision and the appropriate GitHub/OSGeo authentication. Do not
share account passwords or tokens in application documents or issue text.
