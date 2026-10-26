# Public MapGIS regression fixtures

This directory contains small synthetic MapGIS binaries and the code used to generate them. They allow a fresh source checkout to exercise actual `.wt`, `.wl`, and `.wp` input files without downloading restricted geological-survey data.

## Contents

| File | Contents |
|---|---|
| `mapgis/synthetic_points.wt` | Three attitude-station points with Chinese attributes, a nullable date, WGS 84 coordinates, and symbol graphic parameters |
| `mapgis/synthetic_lines.wl` | Three geological/hydrological lines with type attributes and line graphic parameters |
| `mapgis/synthetic_polygons.wp` | Two adjacent polygons with a shared boundary, one polygon with a hole, and a separate island whose boundary exactly coincides with that hole, plus unit attributes and polygon graphic parameters |
| `fixture_manifest.json` | Provenance, generator version/source description, feature counts, bounding boxes, CRS, fields, and SHA-256 checksums |
| `build_mapgis_fixtures.py` | Deterministic semantic source for the geometries and attributes |

## Provenance and validation boundary

The binaries are generated with `pymapgis.Writer` from synthetic geometries defined in `build_mapgis_fixtures.py`. They contain no confidential survey data and no proprietary MapGIS graphic-library files.

They are **public regression fixtures**, not official MapGIS exports. Reader-Writer-Reader checks on these files establish internal consistency only. They are not independent native-export validation, native MapGIS application acceptance, or evidence of vendor-identical rendering.

The historical 36-layer and 400 MB validation datasets remain separate and are not redistributed here.

## Run the public tests

From the repository root after installing the development dependencies:

```bash
python -m pytest -q tests/test_public_fixtures.py
```

The generic Reader, Writer, and CLI fixtures in `tests/conftest.py` prefer locally available real `*.WT`, `*.WL`, and `*.WP` files. When those files are absent, they fall back to these public binaries instead of skipping all binary-file tests.

## Regenerate

```bash
PYTHONPATH=src python3 tests/fixtures/build_mapgis_fixtures.py
python -m pytest -q tests/test_public_fixtures.py
```

Regeneration rewrites the three binaries and their manifest. Header timestamps or other native metadata can change binary checksums even when the semantic content is unchanged. Review semantic differences and the updated checksums together.

## Optional proprietary Colorlib test

`Colorlib.lib` is not bundled. The two ColorLib tests skip unless a readable library is explicitly supplied:

```bash
PYMAPGIS_COLORLIB=/path/to/Colorlib.lib python -m pytest -q tests/test_pure.py -k ColorLib
```

An explicitly supplied path that is invalid should be treated as a failed test, not silently skipped.

## Fixture licence

These entirely synthetic fixtures are distributed under the same Apache-2.0 licence as the repository. They contain no third-party survey data or proprietary MapGIS library content. A separate CC0 dedication may be considered by the maintainers in the future, but no additional permission is required for the current repository licence to apply.
