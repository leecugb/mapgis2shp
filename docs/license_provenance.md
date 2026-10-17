# License and Provenance Review

- **Project:** mapgis2shp (`pymapgis` import name)
- **Review date:** 2026-10-17
- **Release scope reviewed:** 2.4.0 source and distribution configuration

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

Within the release-file scope reviewed:

- No vendor MapGIS source code is bundled.
- No proprietary MapGIS symbol, style, colour, or pattern library is bundled.
- The 36 geological-survey validation layers and the 400 MB validation dataset
  are not redistributed with the package.
- Real-data integration tests skip when their input files are unavailable.
- No additional bundled third-party source component was identified during
  this review. References to other projects in documentation are citations or
  interoperability notes, not incorporated source code.

Contributors must not add restricted survey data, proprietary graphic
libraries, credentials, or third-party code with unclear redistribution
rights. Any future bundled third-party component requires a source, licence,
and attribution review before merging.

## Maintenance

Update this review when release contents, bundled components, data fixtures,
or licensing terms change. Pull-request review should check both the file
header convention and the provenance statement rather than relying only on the
top-level `LICENSE` file.
