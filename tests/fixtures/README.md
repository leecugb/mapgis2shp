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

## Optional user-supplied JWD and SLIB integration data

The original JWD vectors and five matching SLIB libraries are **not bundled** in the current Git tree, wheel or source archive. They must be obtained through the official National Geological Archives of China channel and supplied locally. The redistribution surface is covered by the acquisition terms, so public access, non-classified status and test-only use are not treated as redistribution permission.

- `jwd_slib_manifest.json` remains as the provenance and SHA-256 registry for the original 12 vectors and five libraries, totalling 19,381,767 bytes.
- Set `PYMAPGIS_JWD` to the directory containing the original 12 vectors and `PYMAPGIS_SLIB` to the directory containing the five original libraries.
- `PYMAPGIS_COLORLIB` and `PYMAPGIS_PCOLOR` can override individual colour libraries. `PYMAPGIS_READER_NATIVE` points to the optional native SHP export directory.
- Missing external data produces an explicit optional-integration skip with acquisition guidance. An explicitly supplied invalid path or a checksum mismatch still fails the test instead of silently skipping it.
- Archive inspection rejects any actual JWD, SLIB or `reader_native` data file. Synthetic fixtures and the independent Writer SHP batches remain required and are checked strictly.

The authoritative source is the public V1 *Spatial database of serial suite-tectonic map-sheets of mainland China (1:250,000)*, sheet **J43C001002**, produced by the Development and Research Center of China Geological Survey and distributed by the National Geological Archives of China. Dataset DOI: **10.23650/data.A.2018.NGA131703.K1.1.1.V1**; companion article DOI: **10.12029/gc2018Z101**. See [DATA_ATTRIBUTION.md](../../DATA_ATTRIBUTION.md) for citations, acquisition guidance and the usage boundary. No coordinate-warped or virtual-geological-unit derivatives are used.

Run the real integration tests after configuring the external data:

```bash
python -m pytest -q tests/test_graphic_real_jwd.py
python -m pytest -q tests/test_pure.py -k "ColorLib or PcolorLib"
```

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

For writer batch2/3, each manifest retains the originally supplied `bytes` and `sha256`. Text files also carry `lf_bytes` and `lf_sha256`, computed after CRLF/CR to LF normalization, so Git checkout line-ending policy does not cause cross-platform false failures. Binary SHP components and native WT/WL/WP files are always checked against their original raw byte counts and SHA-256 values.

## Optional native SHP Reader robustness fixtures

Native SHP exports from the same J43C001002 source dataset are also **not bundled**. `reader_native_manifest.json` remains as the DOI, hash and native-export-caveat registry. Set `PYMAPGIS_READER_NATIVE` to a legally obtained local export directory to enable these tests. SHP files have no `.prj`, so tests do not infer CRS from SHP.

`tests/test_reader_native_exports.py` verifies point/line attributes and geometry, polygon coverage and Reader validity, recovery of the polygon missing from SHP, and the four attribute values that differ from WAT text. It deliberately does not inherit SHP self-intersections or WAT/binary inconsistencies. Missing external exports produce an explicit optional-integration skip.

## Fourth native Writer batch

`writer_batch4/` contains twenty domestic Gauss-Kruger SHP cases and eighteen MapGIS-native outputs supplied for Writer auditing. All cases use a 75°E central meridian, k=1 and metre units. The cases cover MultiPoint, MultiLineString, 257 point records, empty/null geometry, 10,001 line vertices, duplicate rings, a bowtie, a degenerate ring, 80 attribute fields, a 5,001-vertex exterior ring, duplicate geometry and a zero-feature file. `03_POINT_MULTIPOINT` and `20_EMPTY_FILE` have no native output and are recorded explicitly in `writer_batch4_manifest.json`.

The native outputs are comparison evidence, not a desired-behaviour specification. In particular, native case 09 merges and duplicates geometry, case 07 fills empty records with lines from the previous conversion, case 06 loses the second MultiLineString part, and several native metric fields disagree with native geometry. Writer regressions therefore assert source fidelity, valid topology, correct metric fields and null semantics rather than copying those defects. Native point/line default styles and the large-ring 24-bit offset of 81,650 are matched explicitly.

```bash
python -m pytest -q tests/test_writer_native_batch4.py
```

The fourth batch currently has 28 passing regressions. Source and wheel fixture layouts both include the root manifest and all SHP/native files. MapGIS version and conversion settings were not provided and are not inferred.

## Fixture licence

These entirely synthetic fixtures are distributed under the same Apache-2.0 licence as the repository. They contain no third-party survey data or proprietary MapGIS library content. A separate CC0 dedication may be considered by the maintainers in the future, but no additional permission is required for the current repository licence to apply.
