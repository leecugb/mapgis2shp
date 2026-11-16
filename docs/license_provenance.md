# License and Provenance Review

- **Project:** mapgis2shp (`pymapgis` import name)
- **Original review:** 2026-10-17 (2.4.0); header re-check 2026-10-18 (2.5.0)
- **Current distribution-boundary re-check:** 2026-11-16 (2.7.3)
- **Current release scope reviewed:** 2.7.3 source, wheel and sdist configuration

The 2.4.0/2.5.0 header review is retained as historical context. The current
2.7.3 package additionally contains the original-library renderer, GeoPDF
support, seven processed USGS test layers and five specifically authorized
generic SLIB fixtures. The third-party section below describes the current
boundary and supersedes the earlier statement that no graphic libraries were
bundled.

This document records the project team's licence and provenance review for
OSGeo Community Project preparation. It is a project-maintained review, not a
legal opinion or an OSGeo determination.

## Licence identification

- The repository licence is [Apache License 2.0](../LICENSE), an OSI-approved
  licence.
- `pyproject.toml` points to that licence file for the Python distribution.
- The source repository, distribution metadata, and contribution guide use the
  same licence identification.
- Contributors must preserve existing notices and provide provenance for any
  third-party material, as described in [CONTRIBUTING.md](../CONTRIBUTING.md).

## Release-file header review

The following first-party release modules now carry
`# SPDX-License-Identifier: Apache-2.0` at the file header:

- `src/pymapgis/__init__.py`
- `src/pymapgis/__main__.py`
- `src/pymapgis/_version.py`
- `src/pymapgis/reader.py`
- `src/pymapgis/writer.py`
- `src/pymapgis/cli.py`
- `src/pymapgis/slib.py`
- `src/pymapgis/linesty.py`
- `src/pymapgis/fillgrph.py`
- `src/pymapgis/colorlib.py`
- `src/pymapgis/pcolor.py`
- `src/pymapgis/graphic.py`
- `src/pymapgis/geopdf.py`
- `src/pymapgis/render_projection.py`
- `src/pymapgis/testing/__init__.py`
- `verify_pymapgis.py`

The SPDX line is placed after a shebang or encoding cookie where one is
present, and otherwise before the module docstring. No new copyright owner or
copyright assignment is introduced by this convention.

New release Python files should use the same convention. Markdown, JSON, TOML,
and other repository material remain covered by the repository licence unless
a different notice is explicitly required.

## Package-boundary review

The wheel and sdist configuration in `pyproject.toml` excludes the research
`rendering` and `semantics` modules and the map-specific
`linesty_adjudicated.py` data module. These are not part of the published
mapgis2shp package scope described in the README and OSGeo application
materials. Their presence in a source checkout does not expand the release
scope or permit release modules to depend on them.

The release dependency list is declared in `pyproject.toml`. Runtime
dependencies are resolved from their own distributions; they are not relicensed
as mapgis2shp code.

## Third-party material and data

Within the current 2.7.3 release-file scope:

- No vendor MapGIS source code is bundled.
- Five generic SLIB files (`Subgraph.lib`, `LINESTY.lib`, `Fillgrph.lib`,
  `Colorlib.lib` and `Pcolor.lib`) are bundled only in the documented test
  fixture locations. Their inclusion relies on the user's explicit packaging
  authorization recorded on 2026-11-13; no public-domain dedication or broader
  relicensing is inferred.
- Seven processed USGS Conejo Well test layers and the original public USGS
  E00/metadata fixtures are bundled with attribution and checksums. They are
  not original NGAC/JWD vectors or native NGAC exports.
- Original NGAC/JWD vectors, native NGAC exports, the separate 36-layer
  validation corpus and the 400 MB validation dataset are not redistributed.
- Optional integration tests skip when their external inputs are unavailable.
- References to other projects in documentation are citations or
  interoperability notes, not incorporated source code.

Contributors must not add restricted survey data, unapproved graphic
libraries, credentials, or third-party code with unclear redistribution
rights. Any additional bundled third-party component requires a source,
licence, attribution and archive-boundary review before merging.

## Maintenance

Update this review when release contents, bundled components, data fixtures,
or licensing terms change. Pull-request review should check both the file
header convention and the provenance statement rather than relying only on the
top-level `LICENSE` file.
