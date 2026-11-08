# MapGIS regression fixtures

This directory contains small synthetic MapGIS binaries and an explicitly integrated real JWD/SLIB dataset. The synthetic files support basic tests without external data; the real dataset supports self-contained graphic-library rendering regression.

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

## Bundled JWD and SLIB integration dataset

The project owner explicitly supplied twelve real JWD vectors and five matching SLIB libraries for integration testing:

- `jwd/`: 5 WP, 5 WL and 2 WT files, 7,094 features, 7,092,289 bytes.
- `slib/`: `Subgraph.lib`, `LINESTY.lib`, `Fillgrph.lib`, `Colorlib.lib` and `Pcolor.lib`, 12,289,478 bytes.
- `jwd_slib_manifest.json`: provenance, roles, byte counts and SHA-256 for every file. Total dataset size: 19,381,767 bytes.

These files are bundled by explicit project-owner request for regression testing. They are **not** part of the synthetic-fixture Apache-2.0 dedication, and no additional licence or public-domain dedication is inferred. Both the source archive and wheel include them. Source tests use `tests/fixtures/`; wheel installations expose the same files as `pymapgis/testing/fixtures/`, with `pymapgis.testing.fixture_path()` resolving the correct location automatically.

Run the real integration tests without any absolute-path configuration:

```bash
python -m pytest -q tests/test_graphic_real_jwd.py
python -m pytest -q tests/test_pure.py -k "ColorLib or PcolorLib"
```

`PYMAPGIS_JWD` and `PYMAPGIS_SLIB` can override the fixture directories for another installation. `PYMAPGIS_COLORLIB` and `PYMAPGIS_PCOLOR` override individual colour libraries. An explicitly supplied invalid path, a missing bundled file or a checksum mismatch fails the test instead of silently skipping it.

The tests verify Reader and graphic-library behaviour, report invariants and PNG/PDF generation. They do not replace native MapGIS display, editing, save/reopen or visual acceptance.

## Native Writer SHP conversion batch

`writer_batch2/` contains eleven small synthetic SHP cases and their MapGIS-native WT/WL/WP conversion outputs, supplied for Writer auditing. The cases cover minimal rings, holes, multipart polygons, shared edges, duplicate vertices, an invalid bowtie, points with nullable dates and MultiLineString input. The MapGIS version and conversion settings were not provided and are not inferred. `writer_batch2_manifest.json` records provenance, byte counts and SHA-256 for all 68 files.

Run the native Writer regressions with:

```bash
python -m pytest -q tests/test_writer_native_batch2.py
```

The tests compare source semantics and native default point/line graphic parameters. They do not require the native conversion to preserve every source geometry decision: multipart lines are exploded by Writer, shared polygon boundaries may be represented differently, and the invalid bowtie is split into triangles by both paths.

## Third native Writer batch

`writer_batch3/` adds twelve SHP cases and their native MapGIS outputs for large 24-bit ring-index offsets, duplicate geometries, projected UTM input, long attributes, null geometry and degenerate rings. The MapGIS version and conversion settings are likewise not inferred. `writer_batch3_manifest.json` records all 74 files and their SHA-256 values.

```bash
python -m pytest -q tests/test_writer_native_batch3.py
```

UTM inputs are reprojected to Gauss-Kruger (k=1) before encoding because MapGIS 6x does not store the UTM zone scale factor. The tests reproject the written result back to EPSG:32643 and use an explicit 1e-5 m Hausdorff tolerance for projection round-trips. Null geometry must be rejected by default and is retained only through an explicit `on_empty="drop"` request; fully degenerate rings are rejected rather than silently written as empty polygons.

## Fixture licence

These entirely synthetic fixtures are distributed under the same Apache-2.0 licence as the repository. They contain no third-party survey data or proprietary MapGIS library content. A separate CC0 dedication may be considered by the maintainers in the future, but no additional permission is required for the current repository licence to apply.
