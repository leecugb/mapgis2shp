# Changelog

## Unreleased

- Preserve WT/WL feature order, line grouping and exact edited coordinates when deciding whether source sections can be passed through; malformed native section ranges now fail before oversized reads
- Reject CLI input/output aliases that would overwrite the source file; validate Writer scale, duplicate columns and int16 graphic parameters, and write finite empty-file extents
- Compute symbol export bounds from drawable paths, circles and arcs; restrict raster GeoPDF input to finite, non-degenerate north-up GeoTransforms
- Synchronize citation, example, OSGeo and provenance documentation; add contribution and conduct guides and mark non-bundled historical evidence explicitly
- Reorganize the README around installation, conversion, writing, rendering and limitations; preserve detailed format and release material in dedicated documents, and add the executable `examples/render_testdata.py` workflow

## 2.7.3 (2026-11-14)

- Fix AEA/LCC first-standard-parallel overwrites, preserve appended attribute values with physical storage-length accounting and expanded records, and replace fuzzy polygon passthrough fingerprints with exact normalized-WKB comparison
- Add `tests/test_writer_regressions_20261114.py` with five targeted regression cases, covering non-25° conic parallels, native attribute append and small polygon edits; verify the complete Writer batch2/3/4 native comparison suites
- Declare PyMuPDF and lxml in the development extra, add `pytest.importorskip` guards for optional GDAL and geosciml4china dependencies, remove the hard-coded semantic-extension path, and set pytest `pythonpath` for direct invocation
- Bundle the Writer integrity fixes in a public 2.7.3 release and distinguish that release from the earlier 2.7.2 artifact

## 2.7.2 (2026-11-14)

- Bundle seven processed USGS Conejo Well test layers (8,512 features) and the independently authorized five generic SLIB libraries; keep original NGAC/JWD vectors and native NGAC exports external, reject them in current release trees and archives, and detect renamed forbidden content by SHA-256
- Add strict-scale fully vector GeoPDF output, `Writer(..., preserve_utm=True)`, projection-scale parsing at byte 232 and explicit Reader `coordinate_scale_factor`; distinguish native storage scaling from the source map's cartographic scale
- Replace application examples with self-contained `testdata_path()` / `slib_path()` workflows, add the actual rendered geological map to the README, and update `examples/geological_workflow.py` for the seven bundled layers
- Add release-boundary tests, strict wheel/sdist content inspection, and current full-suite validation

- Align fresh WT/WL/WP output with MapGIS SHP import: compute attribute-prefix descriptor offsets/counts and descriptor flags, add native ID/length/area fields, use native text/numeric declarations, write WT 65536 flags and coordinate-scaled boxes/extents, apply fresh polygon ring-count classes and cyclic fill colours, zero fresh legacy header stamps, and prevent geometry passthrough from discarding explicit style edits
- Add external SHP→MapGIS reference tests covering binary coordinate sections, native auxiliary records, attribute descriptors, default graphics and style-preserving mode

- Use original open-edition JWD/SLIB for current regression and examples, stop new JWD-derived synthetic variants, and strengthen dataset, companion-article and SLIB attribution in `DATA_ATTRIBUTION.md`
- Add the fourth domestic Gauss-Kruger Writer batch (20 SHP cases and 18 native MapGIS outputs); preserve multipart geometry, valid topology, metric fields and null semantics while matching native point/line defaults, and reject native topology/empty-geometry defects instead of inheriting them
- Add twelve third-batch Writer cases for large 24-bit ring-index offsets, projected UTM input, long attributes, null geometry and degenerate rings; reproject UTM to Gauss-Kruger (k=1) with the correct central meridian instead of writing UTM coordinates with incorrect metadata
- Add eleven native SHP-to-MapGIS Writer cases with provenance manifests and source/wheel fixture access; align default WT point size 0.1 mm, colour 6 and pen width 0.1 mm, and default WL width 0.05 mm, X/Y coefficients 1.0 and `aux_flag=1` with the supplied native conversion reference
- Normalize the two bundled WP backup filenames to `.WP`, and add a compatibility loader that still handles the published V2.7.1 `.WP~` layout through `Reader`
- Add `examples/render_bundled_jwd.py` with PNG/PDF/SVG output and sanitized JSON reports, and run it in CI
- Assert all 782 38|2 source vertices and `max_deviation <= 1e-9`, pin `drawn + excluded_text == 7094`, cover the published WP-backup layout, and add direct Subgraph/LINESTY/Fillgrph/Colorlib/Pcolor structural-census assertions
- Select `geopandas<1.2` only in the `dev` reference environment because GeoPandas 1.2 changes edge pixels in the optional legacy rendering reference path; ordinary runtime requirements are unchanged
- Synchronize the citation title and 2.7.1 Zenodo DOI, and clarify the SoftwareX validation artifacts and native-acceptance boundary

## 2.7.1 (2026-11-07)

- Document original-library rendering in the package introduction and project metadata; clarify the complete vector / graphic-library / rendering scope
- Fix CI Ruff checks, pin Python 3.9 to Ubuntu 24.04, update checkout/setup-python actions and make nested `pytest.approx()` tests compatible with current pytest

## 2.7.0 (2026-11-07)

- Add the original graphic-library rendering API: `GraphicLibraries`, `GraphicRenderer`, `GraphicRenderResult` and `render_graphic_map`, with WP/WL/WT rendering, PNG/PDF output, per-layer reports and the optional `render` Matplotlib extra
- Honour WP `class=0`, positive WT `pen_width`, native `width + spacing` text advances (including compression), annotation scripts and optional native font-number maps; add the bundled twelve-layer real JWD rendering regression
- Correct Matplotlib display-pixel to typographic-point conversion for WL widths and marker sizes so output geometry does not change with DPI
- Extend Subgraph decoding with element groups, parameter-driven fill handling and explicit-angle circles/arcs; export those elements through `symbol_geometries()` and preserve unresolved structures as explicit non-results
- Use a hybrid LINESTY path: verified `(linetype, aux)` variants resolve through `feature_rhythm()`, while other records use direct library rhythm or `SubLine.parameter_geometry()` with selected subline variants; retain all-solid pen overlays, preserve unresolved verified variants as non-results and report unknown fill states explicitly
- Render 48-family raised lines from library segment intervals with source-vertex preservation and X/Y coefficient scaling instead of fixed screen-space dashes; merge coincident solid-dot references in verified 16/17 families without changing their visible geometry
- Resolve aux duality as main-record subline selection versus independent auxiliary-record overlay, including the style-2 exception; preserve origin vertical ticks without duplicating closed-line end seams
- Follow the geosciml4china polygon-label scheme by default: draw complete unit codes at polygon representative points with Mathtext, translucent backgrounds and Greek font selection; exclude fragmented WT `代号` annotations and retain an explicit legacy compatibility switch
- Preserve every original source vertex when clipping zero-offset rhythm strokes, including the 38|2 solid baseline; verify all 37 real 38|2 features and all 782 source vertices with zero omissions
- Render constant-offset parallel strokes along complete offset curves with source-chainage phase control, and keep `(linetype, aux)` rhythm cache keys type-correct
- Export `FillgrphLib`, `FillPattern`, `FillStroke` and `pattern_geometry` at package level; compute Fillgrph record boundaries once and use O(n) f32-bitwise coordinate deduplication while preserving every real-library geometry hash
- Decode verified 32-byte Pcolor colour nodes (`N + 3`, channels at +28), including valid all-zero white nodes; use Pcolor for WP fills in `auto` mode while retaining Colorlib for other roles, resolving all 25 previously unresolved JWD colour codes without manual overrides
- Bundle the twelve JWD vectors and five matching SLIB libraries as checksummed integration fixtures under `tests/fixtures/`; include them in both sdist and wheel and expose source/install-independent access through `pymapgis.testing.fixture_path()`
- Clarify the vector/graphic-library/rendering scope, curate `pymapgis.__all__`, remove geological semantics from CLI output, and extend `pymapgis lib` to Fillgrph, Colorlib and Pcolor record inspection
- Harden Reader CRS inference, malformed-section handling, temporal/numeric missing values, and attribute/geometry/graphic-parameter alignment; non-finite DMS and conic-projection parameters now follow the same empty-CRS fallback instead of leaking `ValueError`
- Change Writer defaults to preserve native rings (`make_valid=False`), add explicit `on_empty` handling, encode fresh polygons as independent closed rings, and generate native ring indices plus 24-bit head_9 pointers; unchanged source geometry continues to use raw-section passthrough
- Synchronize the public format documentation with the current WT/WL/WP layouts and document the remaining native-rendering verification boundaries

## 2.6.0
- **Writer**: encode GeoDataFrames back to native MapGIS `.wt` / `.wl` / `.wp` binaries — attribute table (GBK strings, dates, times, typed numerics), graphic parameters (with mapgis → shp → mapgis fidelity when the reader's parameter columns are present), CRS (longitude/latitude, Transverse Mercator, Albers, Lambert), and regenerated polygon topology (shared boundaries stored as single arcs with left/right polygon IDs). New public API: `Writer`, `write()`, and `WriterError`
- CLI converts in both directions based on the input extension (`.shp`, `.geojson`, `.gpkg`, ... → `.wt`/`.wl`/`.wp`); new `--encoding` option
- New runtime dependency: `pyogrio>=0.8` (reading shapefiles is now a runtime feature)
- `verify_pymapgis.py --roundtrip`: Reader → Writer → Reader regression over all local MapGIS files (not recorded in the baseline)
- New graphic-library parsers: `ColorLib` (Colorlib.lib CMYK → RGB) and `FillgrphLib` (fill-pattern records; unsupported structures return `None` rather than inferred geometry)
- Fix the coincident hole–island polygon regression (area over-count when a hole boundary exactly coincides with an independent island polygon); covered by `test_coincident_hole_and_island` and the public fixtures
- Public synthetic MapGIS fixtures (`tests/fixtures/mapgis/`, with generator, provenance manifest and SHA-256 checksums), clean-checkout test fallbacks, executable example (`examples/geological_workflow.py`), CI workflow (`.github/workflows/test-and-build.yml`) and release-archive inspection (`tests/inspect_dist.py`)
- Release notes for 2.3.0–2.5.0 remain to be backfilled into this changelog

## 2.2.1
- Packaging fix: `pymapgis.rendering` is under active development and is not yet ready for distribution (it is also undocumented and requires matplotlib, which is not a declared runtime dependency). It is excluded from the wheel and sdist; the published package again focuses on reading/conversion. Optional development copies are not required by the core package and may remain outside the tracked repository. A separate package or extra can be considered once the module stabilises

## 2.2.0
- `read_graphic_params=True`: decode line graphic parameters (`.wl`: `linetype`, `aux_linetype`, `width`, `x_coef`, `y_coef`) and polygon graphic parameters (`.wp` head_9 section: `fill_color`, `pattern`, `pattern_color`), exposed as `line_params` / `polygon_params` and joined into the GeoDataFrame
- Format documentation: line graphic-parameter area (bytes 18–56), polygon head_9 section, additional `.wl` index sections

## 2.1.0
- `read_point_params=True`: decode point graphic parameters (`.wt`: `point_type`, `symbol_no`, `height`, `width`, `spacing`, `angle`), exposed as `point_params` and joined into the GeoDataFrame
- New constants `POINT_TYPE_TEXT` / `POINT_TYPE_SYMBOL`
- Format documentation: point graphic-parameter area (bytes 23–92)

## 2.0.x
- Matured reader: CRS inference, vectorised parsing, polygon-topology reconstruction, GBK attribute decoding, CLI
