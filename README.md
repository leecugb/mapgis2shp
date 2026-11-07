# mapgis2shp

[![PyPI version](https://img.shields.io/pypi/v/mapgis2shp.svg)](https://pypi.org/project/mapgis2shp/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.21487339-blue.svg)](https://doi.org/10.5281/zenodo.21487339)

Read **and write** MapGIS 6.x/67 vector files (`.wt`, `.wl`, `.wp`) with [GeoPandas](https://geopandas.org/) GeoDataFrames.

MapGIS is a widely used closed-source GIS platform in China, especially in geological surveying, engineering, and scientific research. `pymapgis` provides a lightweight, open-source toolkit for reading, converting and writing its native point, line and polygon vector formats, parsing its graphic libraries, and rendering those vectors from the original libraries.

> **Relationship to prior work:** This package (`mapgis2shp`, import name `pymapgis`) is the matured, validated successor to the first author's earlier [`pymapgis`](https://github.com/leecugb/pymapgis) (2022) single-file reader — both developed by **Shijie Li** (leecugb). The present version adds coordinate-reference inference, vectorised parsing, polygon-topology reconstruction, and independent validation against the official MapGIS export.

## Scope and boundaries

`mapgis2shp` has three deliberately bounded responsibilities:

1. **Vector interoperability** — read MapGIS 6.x/67 `.wt`, `.wl` and `.wp`
   files, convert them through GeoDataFrames/OGR, and write native vectors back
   with attributes, geometry, CRS and graphic parameters.
2. **Graphic-library parsing** — decode `Subgraph.lib`, `LINESTY.lib`,
   `Fillgrph.lib`, `Colorlib.lib` and `Pcolor.lib` structures without replacing
   them with per-map thematic rules.
3. **Original-library rendering** — render WP/WL/WT geometry using those
   libraries, including fills and patterns, line rhythms, point symbols,
   colours and attribute-derived labels.

The following are **outside the core package boundary**:

- Geological interpretation or calibration, contact/fault semantic classification,
  and GeoSciML conversion
- DZ/T or unit-specific thematic recolouring presented as native MapGIS output
- A general-purpose replacement for MapGIS editing, layout or native visual
  acceptance workflows

Attribute-derived polygon labels are a display convenience, not a geological
semantic conversion. Explicit colour override hooks remain available only for
clearly labelled comparison/thematic work. Native MapGIS display, editing and
save/reopen acceptance is separate from internal regression testing.

## Features

- Read **point** (`.wt`), **line** (`.wl`), and **polygon** (`.wp`) files
- **Write** GeoDataFrames back to native `.wt` / `.wl` / `.wp` binaries
- **Byte-preserving round-trips**: files written from a Reader's GeoDataFrame
  reuse the source sections verbatim (arcs, metadata, label boxes, field
  widths) whenever the geometry is unchanged, preserving the source structure.
  Reader → Writer → Reader regression verifies this internally; native MapGIS
  open/edit/save acceptance is a separate verification step
- **Native-display-compatible writing**: written files carry the full 16-entry
  index table, the polygon label-box section (entry 11) and file footer
  (entry 12), the mm-to-degree display coefficients, and the header count
  sequence that MapGIS's renderer requires
- Decode GBK-encoded attribute fields and field names
- Decode point graphic parameters (text/symbol kind, subgraph number, glyph size, rotation angle, colour, layer, pen width / fonts)
- Decode line graphic parameters (style and auxiliary style numbers, line/auxiliary colour, width in mm, pattern coefficients, layer, transparent output)
- Decode polygon graphic parameters (class/layer, fill colour, pattern and pattern-colour numbers from the head_9 section)
- Parse the MapGIS 6.x graphic libraries themselves — `SubgraphLib` for
  `Subgraph.lib` point-symbol definitions (including chained records past
  the index table), `LinestyLib` for `LINESTY.lib` line-style definitions
  (sublines, element templates, dot/dash rhythm, pen tables), `ColorLib` for
  `Colorlib.lib` colour tables, `PcolorLib` for verified 32-byte `Pcolor.lib`
  colour nodes, and `FillgrphLib` for supported `Fillgrph.lib` fill-pattern
  records with explicit handling of unsupported structures
- Reconstruct polygon topology from arc records; preserve native sections on unchanged round-trips and encode freshly written polygons as independent closed rings with native ring-index pointers
- Preserve or repair invalid polygon geometries with `shapely.make_valid`
- Export to formats supported by GeoPandas/OGR (Shapefile, GeoJSON, GeoPackage, etc., via pyogrio or Fiona)
- Simple command-line interface for quick conversions in both directions

## Installation

```bash
pip install mapgis2shp
```

For original graphic-library rendering, install the optional Matplotlib dependency:

```bash
pip install "mapgis2shp[render]"
```

The Python package is imported as `pymapgis`:

```python
from pymapgis import Reader
```

## Quick start

```python
from pymapgis import Reader

with Reader("example.wp") as r:
    print(r)
    # Write to Shapefile
    r.geodataframe.to_file("example.shp")
    # Or access the GeoDataFrame directly
    print(r.geodataframe.head())
```

## Public interface at a glance

The curated top-level API is defined by `pymapgis.__all__`:

| Responsibility | Public interfaces |
|---|---|
| Read / convert | `Reader`, `Reader.geodataframe`, `Reader.to_file()` |
| Write native vectors | `Writer`, `write()`, `WriterError` |
| Load graphic libraries | `GraphicLibraries.from_directory()` |
| Subgraph symbols | `SubgraphLib`, `SubPath`, `Symbol`, `symbol_geometries()`, `fit_circle()` |
| Line styles | `LinestyLib`, `LineStyle`, `SubLine`, `Element`, `compose_feature_style()`, `classify_form()`, `census()` |
| Fill patterns | `FillgrphLib`, `FillPattern`, `FillStroke`, `pattern_geometry()` |
| Colours | `ColorLib`, `PcolorLib` |
| Render WP / WL / WT | `GraphicRenderer`, `GraphicRenderResult`, `render_graphic_map()` |
| Bundled test data | `pymapgis.testing.fixture_path()`, `jwd_path()`, `slib_path()` |

Legacy research helpers remain available from their implementation modules for
compatibility, but are not all promoted to the curated top-level API. In
particular, geological semantic tables and classification helpers are not public
package responsibilities.

## Command-line usage

```bash
# Convert a polygon file to Shapefile
pymapgis input.wp output.shp

# Convert to GeoJSON
pymapgis input.wl output.geojson --driver GeoJSON

# Keep raw (possibly invalid) polygon geometries
pymapgis input.wp output.shp --no-make-valid

# Convert a Shapefile (or GeoJSON/GeoPackage) back to MapGIS
pymapgis input.shp output.wp
pymapgis input.geojson output.wl --encoding GBK

# Also decode graphic parameters (style/colour numbers, width, symbol
# number, angle, ...) into extra attribute columns
pymapgis input.wp output.gpkg --graphic-params

# Inspect any of the five supported graphic-library types
pymapgis lib Subgraph.lib                     # symbol counts (indexed + tail chain)
pymapgis lib Subgraph.lib --symbol 1960       # decode one symbol's geometry
pymapgis lib LINESTY.lib                      # whole-library census
pymapgis lib LINESTY.lib --style 211 --aux 0  # decode one line style
pymapgis lib Fillgrph.lib --pattern 220       # decode one fill pattern
pymapgis lib Colorlib.lib --color 602         # Colorlib channels and RGB
pymapgis lib Pcolor.lib --color 602           # Pcolor 32-byte node and RGB

# An installation with a verified alternate channel model can select it
pymapgis lib Colorlib.lib --color 602 --channel-order YMCK
```

The direction is chosen from the **input** extension: `.wt`/`.wl`/`.wp` input reads MapGIS; any other input writes MapGIS. The same interface is available as `python -m pymapgis input.wp output.shp`.

## API

### `Reader(filepath, make_valid=True, read_point_params=False, read_graphic_params=False)`

Main entry point for reading a MapGIS file. With `read_point_params=True`
(point files only), the per-point graphic parameter area is decoded as well:
the columns `point_type` (0 = text, 1 = symbol), `symbol_no`, `height`,
`width`, `spacing` and `angle` (degrees, counter-clockwise from east), plus
the shared tail `color` and `layer` and the kind-dependent `pen_width`
(symbol points) / `font_zh`, `font_en`, `font_style` (text points), are
appended to the GeoDataFrame and exposed separately as `point_params`.
With `read_graphic_params=True`, graphic parameters are decoded for any
file type — point parameters for `.wt` (as above), line parameters for
`.wl` (`linetype`, `aux_linetype`, `aux_flag`, `color`, `width`, `x_coef`,
`y_coef`, `aux_color`, `layer`, `transparent`, exposed as `line_params`),
and polygon parameters for `.wp` (`class`, `fill_color`, `pattern`,
`pattern_height`, `pattern_width`, `pattern_color`, `layer`, and the three
bytes `field5`/`field6`/`field7` forming the 24-bit ring-index offset,
exposed as `polygon_params`). Pattern dimensions are decoded from the uint16
high halves of float32 values stored in the head_9 section.

**Parsing and alignment invariants**

- The reader consumes all 16 physical section-index entries for every vector
  type. Raw non-empty sections and the file tail are retained in
  `geodataframe.attrs["mapgis_section_passthrough"]`; source field descriptors
  and record widths are retained in `geodataframe.attrs["mapgis_field_meta"]`
  for Writer round-trips
- Polygon IDs are collected from the topology table, but only IDs with a
  corresponding attribute row are emitted. The same filtered ID sequence drives
  attributes, geometries and polygon graphic parameters, so orphan topology IDs
  are dropped consistently instead of causing a pandas length mismatch
- Attribute/geometry count disagreement raises `MapGISError`. A graphic-parameter
  count disagreement emits a warning and drops that parameter group rather than
  joining values to the wrong features
- Invalid headers, negative section offsets/sizes, degenerate one-point arcs and
  topology tables longer than the arc index raise `MapGISError`. Empty input
  produces an empty GeoDataFrame and a zero bounding box

**Attributes**

| Attribute | Type | Description |
|-----------|------|-------------|
| `shapeType` | `str` | `"POINT"`, `"LINE"`, or `"POLYGON"` |
| `crs` | `pyproj.CRS` or `str` | Detected coordinate reference system; empty string when no valid CRS can be inferred |
| `bbox` | `numpy.ndarray` | Bounding box `[minx, miny, maxx, maxy]` |
| `fields` | `list[tuple]` | Field metadata: `(name, type_name, length)` |
| `data` | `pandas.DataFrame` | Attribute table |
| `geom` | `list[shapely.geometry]` | Geometry objects |
| `point_params` | `pandas.DataFrame` | Point graphic parameters (`.wt`, opt-in) |
| `line_params` | `pandas.DataFrame` | Line graphic parameters (`.wl`, opt-in) |
| `polygon_params` | `pandas.DataFrame` | Polygon graphic parameters (`.wp`, opt-in) |
| `geodataframe` | `geopandas.GeoDataFrame` | Combined attributes and geometry |

**Methods**

- `to_file(filepath, **kwargs)` — forward to `GeoDataFrame.to_file`
- `len(reader)` — number of features
- `str(reader)` — summary (`"n features (type POINT)"`); `repr(reader)` shows the constructor arguments
- Context manager: `with Reader(...) as r:` (the file is fully parsed and closed in the constructor)

### Constants

- `POINT_TYPE_TEXT` (0) / `POINT_TYPE_SYMBOL` (1) — values of the `point_type` column for `.wt` graphic parameters
- `pymapgis.__version__` — package version string

### Exceptions

- `MapGISError` — base exception
- `InvalidFileError` — unsupported or unrecognized file
- `TopoError` — polygon topology reconstruction error
- `InvalidDirectoryError` — reserved for project/directory errors
- `WriterError` — a GeoDataFrame cannot be encoded as a MapGIS file

### `Writer(geodataframe, *, make_valid=False, on_empty="error", map_scale=1000.0, snap_tolerance=0.0, graphic_params=True, geometry_type=None)`

Encode a GeoDataFrame as a MapGIS binary file. One geometry type per file:
Point/MultiPoint for `.wt` (MultiPoint is exploded with a warning),
LineString/MultiLineString for `.wl` (exploded likewise), and
Polygon/MultiPolygon for `.wp` (a MultiPolygon stays one polygon feature,
matching the reader).

```python
from pymapgis import Writer, write

Writer(gdf).to_file("out.wp")   # or the shortcut: write(gdf, "out.wp")
```

- `make_valid` — disabled by default to preserve native rings, duplicate
  vertices, holes and ring counts. Set it to `True` to repair invalid polygons
  explicitly before arc decomposition; repair may change the resulting rings
- `on_empty` — `"error"` (default) rejects empty/null geometries with their
  row positions; `"drop"` discards them with a warning only when explicitly
  requested
- `map_scale` — map-scale denominator for projected CRS (coordinates are
  stored as `value * 1000 / map_scale`); ignored for longitude/latitude data
- `snap_tolerance` — coordinate quantisation step applied before topology
  validation and ring encoding (0 = exact coordinates, no snapping)
- `graphic_params` — when the frame carries the reader's graphic-parameter
  columns (`point_type`/`symbol_no`/..., `linetype`/...,
  `fill_color`/`pattern`/`pattern_height`/`pattern_width`/...), write them
  into the native parameter areas instead of the ordinary attribute table.
  A recognised key column activates a parameter group and missing columns
  receive native defaults. Polygon `field5`/`field6`/`field7` are computed
  ring-index offsets, not editable style defaults
- `geometry_type` — explicit `"POINT"`/`"LINE"`/`"POLYGON"` for empty frames

Freshly written WP files encode every exterior and interior ring as an
independent closed arc, preserve consecutive duplicate vertices, and write
native polygon/ring/arc indices into the coordinate section. Each polygon's
24-bit ring-index offset is calculated during the same encoding pass so the
arc index, coordinate section and head_9 pointers stay consistent.

Attributes are encoded with MapGIS field types inferred from pandas dtypes
(GBK strings, dates, times, numbers); unsupported columns raise `WriterError`.
A GeoDataFrame produced by `Reader` also carries source section bytes and field
metadata in `gdf.attrs`. When its geometry is unchanged, `Writer` reuses those
sections byte-for-byte—including the original shared-arc layout and pointer
table—so tested round-trips preserve native record widths, metadata blocks,
polygon label boxes and file footers.

**Write-side limitations**

- `.wt` label text stored in auxiliary annotation sections is not produced;
  written `.wt` files carry geometry, attributes, and symbol points only
- Shapefile's 10-character field-name limit truncates long parameter columns
  (e.g. `pattern_color` → `pattern_col`) when passing through `.shp`, which
  disables the matching parameter group on write; GeoJSON/GeoPackage or a
  direct GeoDataFrame hand-off is unaffected
- Longitude/latitude, Transverse Mercator, Albers, and Lambert CRS are
  written; other projections raise `WriterError`
- CGCS2000 has no MapGIS ellipsoid code and is written as WGS84 with a
  warning (they agree to better than 0.1 mm)
- Freshly authored polygon files (data that did not come from a `Reader`)
  use the native structural conventions (16-entry index, label-box and
  footer sections, closed-ring arcs), but arbitrary new data still needs
  native-application acceptance. Round-tripped files preserve source structure
  and are checked by internal Reader → Writer → Reader regression

## Reading graphic parameters

Beyond geometry and attributes, MapGIS files carry per-feature **graphic
parameters** (how MapGIS draws the feature). Decoding is opt-in:

```python
from pymapgis import Reader, POINT_TYPE_SYMBOL

# Point files: annotation vs. subgraph symbol, symbol number, glyph size,
# rotation angle
with Reader("points.wt", read_graphic_params=True) as r:
    symbols = r.geodataframe[r.geodataframe.point_type == POINT_TYPE_SYMBOL]
    print(symbols[["symbol_no", "height", "width", "angle"]].head())

# Line files: style and auxiliary style numbers, colour index, width in
# millimetres, pattern coefficients
with Reader("lines.wl", read_graphic_params=True) as r:
    print(r.geodataframe[["linetype", "aux_linetype", "color",
                          "width", "x_coef", "y_coef"]].head())

# Polygon files: class/layer, fill colour, pattern number and dimensions,
# pattern colour, and the 24-bit ring-index pointer bytes
with Reader("polygons.wp", read_graphic_params=True) as r:
    print(r.geodataframe[["class", "fill_color", "pattern",
                          "pattern_height", "pattern_width", "pattern_color"]].head())
```

> **Warning — not self-contained.** Style, colour, symbol and pattern
> numbers are indices into the MapGIS system libraries (Slib, line-style
> library, pattern library) of the *originating* MapGIS installation; the
> glyph definitions are not stored in the data files. The same number may
> mean different things under a different or customised library. Field
> layouts were reverse-engineered and validated on the layers of map sheet
> J43C001002 — verify against your own data before relying on them.

## Parsing the graphic libraries

The library files referenced by the graphic parameters can be parsed
directly (the same parsers back the `pymapgis lib` subcommand):

```python
from pymapgis import (
    FillgrphLib, LinestyLib, SubgraphLib, PcolorLib,
    classify_form, compose_feature_style, pattern_geometry,
)

# Subgraph.lib: point-symbol geometry (mm coordinates, subpaths, fitted circles)
lib = SubgraphLib("Subgraph.lib")
print(lib.n_indexed, "indexed +", lib.n_tail, "tail-chain symbols")
sym = lib.decode(1960)          # None when out of range
for sp in sym.subpaths:
    print(len(sp.points), "points", sp.circle)   # circle = (cx, cy, r) fit

# LINESTY.lib: line styles (1-based, as stored in .wl linetype fields)
styles = LinestyLib("LINESTY.lib")
style = styles.decode(211)
print(classify_form(style))                        # form label + evidence
main, aux = compose_feature_style(styles, 211, 0)  # aux is None when it selects a main-record variant

# Fillgrph.lib: pattern records and data-driven geometry
patterns = FillgrphLib("Fillgrph.lib")
print(pattern_geometry(patterns, 220))

# Pcolor.lib: colour N is in 32-byte node N + 3, channels at node +28
pcolors = PcolorLib("Pcolor.lib")
print(pcolors.rgb(602))  # (255, 255, 178) in the verified JWD library
```

Line-style style numbers and symbol numbers are *library-local*: they
resolve only against the same (or a byte-identical) library that produced
the data.

For LINESTY, the renderer uses a hybrid path: previously verified `(linetype,
aux)` variants first resolve through `feature_rhythm()`, preserving their
validated period, phase and subline selection. Other records use
`LineStyle.rhythm()` when the library contains a direct rhythm, or the selected
subline's `SubLine.parameter_geometry()` otherwise. The structural path consumes
element templates and f32 payloads without consulting style numbers or
adjudication tables. Alternative non-solid sublines are not merged; multiple
solid pens remain genuine overlays. Explicit fill/dot units are honoured; an
unproven dot fill is `None` and is reported as `unknown_fill` instead of being
inferred from radius. A verified but unresolved variant stays unresolved rather
than being replaced by generic geometry. Raised-line variants such as `48|0`
use the library's actual segment intervals rather than screen-space dash
constants; source vertices are preserved on curved base lines, and `x_coef` /
`y_coef` scale longitudinal rhythm and transverse offset respectively.
Coincident solid dots in the verified 16/17 records are merged by their visible
union, retaining the largest radius without overplotting redundant references.
Zero-offset rhythm strokes, including the 38|2 solid baseline, are clipped
along the original source chainage and retain every interior source vertex;
they are never replaced by straight chords between period endpoints.
Constant-offset parallel strokes likewise follow complete offset curves, with
rhythm phase measured on the original line rather than the offset curve.
`compose_feature_style()` distinguishes an in-range aux subline variant from an
out-of-range independent auxiliary record (with the verified style-2 equivalent
family as an exception). Only an independent auxiliary record is overlaid, so
`16|1` remains a dot-only variant while `1|2` retains its separate dashed record.
The older `payload_geometry()` remains available for compatibility and auxiliary
evidence. `symbol_geometries()` likewise exports Subgraph element groups and
their `fill_kind` alongside paths, circles and arcs.

`ColorLib(path, channel_order="KCMY")` uses the JWD reference mapping by
default. `channel_order="YMCK"` is available for installations whose truth
anchors prove that model; it is never selected automatically. `PcolorLib`
reads colour number N from 32-byte node N + 3, with channel bytes at node
offset 28. All-zero KCMY is valid white, not an empty slot. For WP fills,
`GraphicRenderer(..., fill_library="auto")` uses Pcolor when available and
Colorlib otherwise; `"pcolor"` requires that library and `"color"` preserves
the legacy comparison path. All other colour roles continue to use Colorlib.

## Rendering with the original graphic libraries

`pymapgis.graphic` renders `.wp`, `.wl` and `.wt` layers directly from
`Fillgrph.lib`, `LINESTY.lib`, `Subgraph.lib` and `Colorlib.lib`. It preserves
polygon holes, stamps line-style elements along the original coordinates
without extending line endpoints, instantiates subgraph geometry and fills,
and renders WT text annotations.

```python
from pymapgis import GraphicLibraries, GraphicRenderer

libraries = GraphicLibraries.from_directory("/path/to/SLIB")
renderer = GraphicRenderer(
    libraries,
    scale=250000,
    # Native WT layout: per-character advance = width + spacing.
    native_text_layout=True,
    # Geosciml4china-style labels from polygon attributes (default):
    polygon_labels=True,
    polygon_label_fields=("QDUECC_eff", "QDUECC", "QDUECD"),
    polygon_label_fontsize=4.5,
    # Fragmented WT unit-code annotations are excluded by default:
    exclude_text_categories={"代号"},
    text_category_scales={"产状": 0.45, "断层产状": 0.45},
    text_font_family=["Noto Sans CJK JP", "SimSun", "DejaVu Sans"],
    # Optional native font-number mappings (installation-local):
    font_zh_map={1: "SimSun", 4: "SimHei"},
    font_en_map={0: "DejaVu Sans"},
    font_style_map={0: {"style": "normal"}},
)
result = renderer.render(
    ["area.wp", "boundaries.wl", "points.wt"],  # automatically WP → WL → WT
    "map.png",                                 # .png and .pdf are supported
    figsize=(12, 10),
    dpi=300,
)
print(result.reports)  # drawn features, fallbacks, unresolved colours, ...
```

By default, complete geological-unit labels come from polygon attributes and
are drawn at each geometry's `representative_point()` with Mathtext, 4.5 pt
type and a translucent background, following the geosciml4china pipeline.
Fragmented WT annotations whose `CHFCEC` is `代号` are reported as
`excluded_text` instead of being duplicated. `polygon_label` counts the new
labels. Set `polygon_labels=False` and `exclude_text_categories=()` to restore
the legacy WT-only annotation path.

The one-shot equivalent is:

```python
from pymapgis import render_graphic_map

result = render_graphic_map(
    ["area.wp", "boundaries.wl", "points.wt"],
    "/path/to/SLIB",
    "map.pdf",
    scale=250000,
)
```

For an existing Matplotlib workflow, use `renderer.draw_layers(ax, layers)` or
`renderer.draw_layer(ax, gdf, kind="wl")`. File paths and pre-read
GeoDataFrames can be mixed. The latter must have been read with
`read_graphic_params=True` (and `read_point_params=True` for WT).

The paper-mm/map-unit conversion is inferred from the CRS. For local data
without a CRS, pass `map_units_per_mm` explicitly. For original graphic-library
rendering, WP fills use Pcolor in `auto` mode when available, while pattern,
line, auxiliary and point colours always resolve through Colorlib. Only
out-of-range colour numbers use `fallback_color`; no family-interpolated or
unit-specific colours are enabled by default. `color_overrides` and
`unit_color_overrides` are restricted to explicitly labelled thematic or
comparison renders and must not be used to present a map as native MapGIS
output. Unresolved feature colours and line-style solid fallbacks are counted
in each layer's report.
See [the colour-evidence and role rules](docs/color_parsing_logic.md) for the
JWD truth-anchor history and current verification results.

The renderer is format-level and is not a guarantee of pixel-identical MapGIS
output. Its current display-parameter boundaries are explicit:

- Polygon `class=0` features are skipped and counted as `excluded_class`
- Positive WT `pen_width` values override `symbol_line_width_pt`; zero/missing
  values retain that display default
- With `native_text_layout=True` (default), character advance is exactly
  `width + spacing`, including negative compression values. Script size and
  baseline remain typographic approximations. Set it to `False` for whole-label
  Mathtext layout
- Polygon unit labels default to `QDUECC_eff`, `QDUECC` or `QDUECD`, anchored at
  `representative_point()` with 4.5 pt Mathtext and a translucent background;
  Greek labels use Times New Roman. WT `代号` annotations are excluded by
  default; the two paths can be switched independently through
  `polygon_labels` and `exclude_text_categories`
- Native font numbers are installation-local. Supply `font_zh_map`,
  `font_en_map` and optionally `font_style_map`; unmapped numbers are counted
  in `unknown_fonts` rather than silently treated as resolved
- The aux field has verified dual semantics. An in-range value selects a main-
  record subline variant; an out-of-range value is decoded and drawn as an
  independent auxiliary record. The style-2 equivalent-dash family is the
  explicit exception. Thus `16|1`, `38|2` and `65|4` do not acquire an extra
  auxiliary line, while `1|2` retains one. Native visual confirmation is still
  required for aux combinations not covered by these verified rules
- Out-of-range colour numbers use `fallback_color`; these substitutions,
  unknown fill states and unresolved symbols/styles are reported rather than
  hidden

## Supported formats

| Extension | Geometry type | Graphic parameters | Notes |
|-----------|---------------|--------------------|-------|
| `.wt` | Point | kind / symbol / size / angle / colour / pen width / text fonts | 93-byte fixed record size |
| `.wl` | LineString | style + auxiliary fields / colour / width / coefficients / layer / transparency | 57-byte arc index + coordinate block |
| `.wp` | Polygon/MultiPolygon | class / fill / pattern + dimensions / layer / 24-bit ring pointer | Arc index + topology + coordinate and ring-index blocks |

CRS detection supports the most common projections found in MapGIS 6.x files, including longitude/latitude, Gauss-Krüger (Transverse Mercator), Lambert Conformal Conic, and Albers Equal-Area. Because MapGIS stores only projection and ellipsoid **index numbers**, the complete CRS depends on external MapGIS index files (`ellip.dat`, etc.).

## Technical Documentation: MapGIS Vector File Format

> The following section describes the MapGIS 6x/67 binary vector format (`.wt` / `.wl` / `.wp`) as implemented by the current `Reader` and `Writer`. Historical reverse-engineering notes and supporting evidence remain under `docs/`.

MapGIS vector files are a closed-source binary vector data format developed by MapGIS (Zhongdi Digital). They are widely used in geological surveying, engineering investigation, and scientific research in China. The format itself **does not carry a complete coordinate-system description**; projection and ellipsoid parameters must be interpreted using the index tables in the MapGIS installation environment (e.g., `mapgis67\program\ellip.dat`).

**Conventions**

- All offsets are **0-based** from the beginning of the file.
- `int16` / `int32` / `uint8` / `double` are all **little-endian**.
- String fields are encoded as **GBK** unless otherwise noted.

### Overall file structure

The three file types share the same top-level organization:

| Region | Description |
|--------|-------------|
| File header | 8-byte magic + 4-byte file ID + 4-byte index-section start offset |
| Index section | 16 records of 10 bytes each, recording start offsets and sizes of sub-sections |
| Sub-sections | Coordinates / arcs / polygons / attributes, etc. |

The index-section start offset is at file bytes **12–15**, denoted as `data_start`. From `data_start` there are 16 consecutive index records (the first ten hold the regular data sections; entries 11 and 12 hold the polygon label-box section and file footer, which MapGIS’s renderer requires):

```
head_1  : offset data_start + 0
head_2  : offset data_start + 10
...
head_10 : offset data_start + 90
head_11 : offset data_start + 100   (polygon label boxes, 32 + 32n bytes)
head_12 : offset data_start + 120   (polygon file footer, 4 + 4n bytes)
head_13..16 : empty
```

Each index record begins with 8 bytes `(start, volume)` representing the start offset and size (in bytes) of the corresponding sub-section.

The magic numbers and file IDs are:

| File type | Magic | File ID | Description |
|-----------|-------|---------|-------------|
| Point `.wt` | `WMAP`D22` | 1 | Point features |
| Line `.wl` | `WMAP`D21` | 0 | Line features |
| Polygon `.wp` | `WMAP`D23` | 2 | Polygon features |

### Coordinate reference system parsing

The CRS parameters are stored at the same fixed offsets in all three file types:

| Content | Offset | Bytes | Type | Description |
|---------|--------|-------|------|-------------|
| Projection type | 109 | 1 | uint8 | Projection-type index |
| Ellipsoid type | 110 | 1 | uint8 | Ellipsoid index |
| Scale | 143 | 8 | double | Scale denominator |

> The projection-type index and ellipsoid index correspond to index tables in the MapGIS installation directory and `ellip.dat`, respectively. Therefore, the full CRS interpretation depends on the external MapGIS software environment.

#### Common ellipsoids

| Index | Datum | PROJ4 definition |
|-------|-------|------------------|
| 1 | Beijing 54 | `+ellps=krass +towgs84=15.8,-154.4,-82.3,0,0,0,0 +units=m +no_defs` |
| 2 | Xi'an 80 | `+a=6378140 +b=6356755.288157528` |
| 7 | WGS84 | `+datum=WGS84` |
| 16 | Krassovsky | `+ellps=krass` |

#### Projection parameters

For Gauss-Krüger (projection index 5), Lambert (3), Albers (2), and similar projections, additional parameters are stored as follows. The offsets 175/183/191 correspond to the starting latitude, first standard parallel, and second standard parallel described in the original technical article:

| Content | Offset | Bytes | Type | Description |
|---------|--------|-------|------|-------------|
| Central meridian | 151 | 8 | double | Format `DDDMMSS.sss` |
| Starting latitude | 175 | 8 | double | Standard parallel 0 |
| First standard parallel | 183 | 8 | double | Standard parallel 1 |
| Second standard parallel | 191 | 8 | double | Standard parallel 2 |
| False easting | 199 | 8 | double | False Easting |
| False northing | 207 | 8 | double | False Northing |

The central meridian and standard parallels are encoded as `DDDMMSS.sss` doubles. The reader decodes them arithmetically, preserving fractional seconds and negative western longitudes without string rounding or zero-padding:

```
sign = -1 if raw < 0 else 1
ms = abs(raw) % 10000
degrees = (abs(raw) - ms) / 10000
minutes = int(ms // 100)
seconds = ms - minutes * 100
decimal_degrees = sign * (degrees + minutes/60 + seconds/3600)
```

For longitude/latitude (projection type 0), coordinates are decimal degrees and the header scale is ignored because native files may store zero there. For supported projected CRS types, internal coordinates are converted to map units with `scale / 1000`. A non-finite or non-positive projected scale, or invalid projection parameters, yields an empty CRS rather than collapsing or poisoning the geometry.

### Point files (`.wt`)

#### File header and index section

| Content | Offset | Bytes | Type | Description |
|---------|--------|-------|------|-------------|
| File header magic | 0–7 | 8 | string | `WMAP`D22` |
| File ID | 8–11 | 4 | int32 | Fixed value 1 |
| Index section start | 12–15 | 4 | int32 | `data_start` |

Index-section meaning:

| head | Offset (relative to `data_start`) | Meaning |
|------|-----------------------------------|---------|
| head_1 | 0 | Coordinate data section start and size |
| head_2 | 10 | Unused |
| head_3 | 20 | Attribute data section start and size |

#### Coordinate data section

The coordinate data section stores one point per **93 bytes**. The first 93-byte record is empty, so the actual point count is:

```
point_count = coord_volume / 93 - 1
```

Single point record structure:

| Content | Offset within record | Bytes | Type | Description |
|---------|----------------------|-------|------|-------------|
| Label | 0 | 1 | uint8 | Point label |
| Reserved | 1–6 | 6 | - | Unused |
| X coordinate | 7–14 | 8 | double | X value |
| Y coordinate | 15–22 | 8 | double | Y value |
| Graphic parameters | 23–92 | 70 | - | Point graphic parameters (see below) |

#### Point graphic parameters (bytes 23–92)

> Reverse-engineered in September 2026 and validated on the annotation layers
> of map sheet J43C001002. The byte at offset 31 selects the point kind; the
> remaining fields are interpreted according to that kind. Sizes are in
> millimetres and the angle in degrees (counter-clockwise from east, matching
> the `atan2(dy, dx)` line-tangent convention — verified by fault symbols
> whose rotation is parallel (mod 180°) to their parent fault's strike).

| Content | Offset within record | Bytes | Type | Description |
|---------|----------------------|-------|------|-------------|
| Reserved | 23–30 | 8 | - | Unused (always zero) |
| Point kind | 31 | 1 | uint8 | 0 = text annotation, 1 = subgraph symbol |
| Reserved | 32 | 1 | - | Unused |
| Subgraph number | 33–34 | 2 | int16 | Symbol points: symbol-library number; 0 for text |
| Text height | 33–36 | 4 | float32 | Text points: character height in mm (overlaps the subgraph number; interpret by kind) |
| Height | 37–40 | 4 | float32 | Symbol points: glyph height (mm); text points: character width (mm) |
| Width | 41–44 | 4 | float32 | Symbol points: glyph width (mm); text points: character spacing (mm) |
| Rotation angle | 45–48 | 4 | float32 | Symbol / text rotation angle in degrees |
| Kind-dependent pen/font fields | 49–53 | 5 | Symbol points: float32 pen width at 49–52 (mm). Text points: `font_zh` at 49, `font_en` at 51, `font_style` at 53 |
| Colour | 75 | 1 | uint8 | Native Colorlib index shared by symbol and text points |
| Layer | 83 | 1 | uint8 | Native layer number shared by both point kinds |
| Other / reserved | 54–74, 76–82, 84–92 | — | - | Not fully decoded; auxiliary colour, text arrangement and transparent-output offsets remain unpinned |

> **These parameters are not self-contained.** The subgraph number is an
> index into the MapGIS system symbol library (Slib) of the originating
> MapGIS installation; the glyph definitions are not stored in the file.
> Under a different or customised library the same number may map to a
> different glyph, and what a rotation of zero means depends on the glyph
> design. Interpret the values only in the context of the symbol library
> (and library version) that produced the data.

### Line files (`.wl`)

#### File header and index section

| Content | Offset | Bytes | Type | Description |
|---------|--------|-------|------|-------------|
| File header magic | 0–7 | 8 | string | `WMAP`D21` |
| File ID | 8–11 | 4 | int32 | Fixed value 0 |
| Index section start | 12–15 | 4 | int32 | `data_start` |

Index-section meaning:

| head | Offset (relative to `data_start`) | Meaning |
|------|-----------------------------------|---------|
| head_1 | 0 | Line data section start and size |
| head_2 | 10 | Coordinate data section start and size |
| head_3 | 20 | Attribute data section start and size |

#### Line data section

The line data section stores one line index record per **57 bytes**. The first 57-byte record is empty, so the actual line count is:

```
line_count = line_volume / 57 - 1
```

Single line index structure:

| Content | Offset within record | Bytes | Type | Description |
|---------|----------------------|-------|------|-------------|
| Reserved | 0–9 | 10 | - | Unused |
| Anchor point count | 10–13 | 4 | int32 | Number of coordinate points in this line |
| Anchor coordinate offset | 14–17 | 4 | int32 | Offset relative to coordinate-section start |
| Graphic parameters | 18–56 | 39 | - | Line graphic parameters (see below) |

#### Line graphic parameters (bytes 18–56)

> Reverse-engineered in September 2026 and validated on all 18 line layers of
> map sheet J43C001002 (widths are geologically plausible for every layer,
> 0.05–4 mm; style numbers cluster by line category).

| Content | Offset within record | Bytes | Type | Description |
|---------|----------------------|-------|------|-------------|
| Reserved | 18–21 | 4 | - | Unused |
| Line-style number | 22–23 | 2 | int16 | Index into the MapGIS line-style library (1 = plain solid) |
| Auxiliary line-style number | 24 | 1 | uint8 | Exposed as `aux_linetype`; not combined with the following flag byte |
| Auxiliary flag | 25 | 1 | uint8 | Exposed as `aux_flag`; 0 is the normal case, 1 marks special/residual records |
| Line colour | 26–27 | 2 | int16 | Colorlib index (1-based) |
| Reserved | 28–29 | 2 | - | Unused |
| Line width | 30–33 | 4 | float32 | Width in millimetres |
| Reserved | 34 | 1 | - | Padding |
| X coefficient | 35–38 | 4 | float32 | Pattern X scale (unaligned) |
| Y coefficient | 39–42 | 4 | float32 | Pattern Y scale (unaligned) |
| Auxiliary colour | 43–44 | 2 | int16 | Colorlib index; 0 = none |
| Reserved | 45–46 | 2 | - | Not currently decoded |
| Layer | 47 | 1 | uint8 | Native layer number |
| Transparent output | 48 | 1 | uint8 | 0 = no, 1 = transparent output |
| Reserved | 49–56 | 8 | - | Not currently decoded |

> Line-style and colour numbers reference the external MapGIS line-style
> library and are not self-contained (same dependency as point parameters).

#### Additional sections

Beyond the documented sections (lines / coordinates / attributes), `.wl`
files in J43C001002 carry further per-line sections in the header index:
head_4 (24 bytes per line), head_7 (32 bytes per line) and head_8 (4 bytes
per line). Their content shows no correlation with display parameters and
their purpose is undetermined (possibly topology/annotation linkages).

#### Coordinate data section

The coordinate data section stores anchor points sequentially. Each XY pair occupies **16 bytes** (2 × double). Reading uses the anchor point count and coordinate offset from the line index.

### Polygon files (`.wp`)

#### File header and index section

| Content | Offset | Bytes | Type | Description |
|---------|--------|-------|------|-------------|
| File header magic | 0–7 | 8 | string | `WMAP`D23` |
| File ID | 8–11 | 4 | int32 | Fixed value 2 |
| Index section start | 12–15 | 4 | int32 | `data_start` |

Index-section meaning:

| head | Offset (relative to `data_start`) | Meaning |
|------|-----------------------------------|---------|
| head_1 | 0 | Arc data section start and size |
| head_2 | 10 | Coordinate data section start and size |
| head_3 | 20 | Metadata block (Windows FILETIME + source-path area) |
| head_4 | 30 | Polygon topology data section start and size |
| head_9 | 80 | Polygon graphic-parameter section (see below) |
| head_10 | 90 | Attribute data section start and size |

#### Arc data section

Polygon files reuse the line arc-storage structure: **57 bytes** per arc index record, with the first 57-byte record empty. The fields have the same meaning as in `.wl` (anchor point count + coordinate offset).

#### Coordinate data section

Arc coordinates use the same 16-byte double-precision XY pairs as line files, but the WP coordinate section also contains variable-length **polygon/ring/arc index records** between coordinate blocks. Arc byte offsets therefore always refer to the combined coordinate-and-index stream, not to an array of coordinates alone.

For freshly written files, the Writer emits each polygon's ring-index record after the first arc of the following polygon, and emits the final polygon's record after the final arc. The record lead is derived from raw arc point counts and hole/zero markers. Each record's byte offset is returned to the head_9 encoder and stored in `field5`/`field6`/`field7`, keeping the coordinate section, arc index and ring pointers synchronized.

#### Polygon topology data section

The topology data section stores one record per **24 bytes**. The first 24-byte record is empty, so the actual topology record count is:

```
topo_count = poly_volume / 24 - 1
```

The first 16 bytes of each record contain 4 little-endian int32 values. The parser mainly uses columns 2 and 3 (0-indexed), i.e., record bytes 8–15:

| Content | Offset within record | Bytes | Type | Description |
|---------|----------------------|-------|------|-------------|
| Left polygon ID | 8–11 | 4 | int32 | Polygon ID on the left side of the arc |
| Right polygon ID | 12–15 | 4 | int32 | Polygon ID on the right side of the arc |
| Reserved | 16–23 | 8 | - | Unused |

> Polygon IDs are 1-based. To reconstruct a polygon, select all arcs whose left or right polygon ID equals the target ID. If the left ID matches, the arc coordinates are usually reversed so that the polygon boundary is consistently on the same side of the arc. The arcs are then chained by matching endpoints into closed rings, and rings are classified as shells or holes to build `Polygon` / `MultiPolygon` geometries.

#### Polygon graphic-parameter section (head_9)

> Reverse-engineered in September 2026 and validated on all 13 polygon layers
> of map sheet J43C001002: the section holds exactly one record per polygon,
> and its fields are 100% consistent within each geological unit.

The section stores one record per **40 bytes**, the first record is empty,
and record *i* (0-based after the empty record) belongs to polygon ID *i + 1*:

| Content | Offset within record | Bytes | Type | Description |
|---------|----------------------|-------|------|-------------|
| Kind byte | 0 | 1 | uint8 | Observed value 1 |
| Class code | 1 | 1 | uint8 | Native display class; 0 suppresses the native fill |
| Reserved | 2–4 | 3 | - | Unused |
| Ring-index offset | 5–7 | 3 | uint8 × 3 | 24-bit little-endian byte offset of the polygon's ring-index record in the coordinate section; `field5` low, `field6` middle, `field7` high |
| Reserved | 8 | 1 | - | Unused |
| Fill colour | 9–10 | 2 | uint16 | Colorlib index; values above the standard library range require installation-specific colour evidence |
| Reserved | 11–12 | 2 | - | Unused / observed zero |
| Fill-pattern number | 13–14 | 2 | uint16 | Fillgrph.lib pattern index |
| Reserved | 15–16 | 2 | - | Unused |
| Pattern height | 17–18 | 2 | uint16 | High 16 bits of a float32; reconstructed as `uint16_value << 16` and viewed as float32, in mm |
| Reserved | 19–20 | 2 | - | Unused |
| Pattern width | 21–22 | 2 | uint16 | Same high-half float32 representation as pattern height, in mm |
| Pattern colour | 23 | 1 | uint8 | Colorlib index used for the pattern |
| Reserved | 24–29 | 6 | - | Unused |
| Layer | 30 | 1 | uint8 | Native layer number |
| Reserved | 31–39 | 9 | - | Unused |

For freshly written WP files, `field5`/`field6`/`field7` are calculated from the generated coordinate layout and must not be replaced with colour or arbitrary display values. For unchanged source-derived round-trips, the original pointer table is preserved with the original arc layout.

> Colour and pattern numbers reference the external MapGIS colour/pattern
> libraries and are not self-contained (same dependency as point parameters).

#### Polygon reconstruction key points

1. **Select arcs**: For target polygon ID `pid`, select arcs where `left_id == pid` or `right_id == pid`.
2. **Orient arcs**: If `left_id == pid`, reverse the arc coordinates so the polygon boundary stays on the consistent side.
3. **Form rings**: Use a greedy nearest-endpoint merge to chain arcs into closed rings. Endpoint coordinates may differ by ~1e-6 due to floating-point precision.
4. **Hole detection**: Use point-in-polygon containment between rings to distinguish outer shells and inner holes.
5. **Validity repair**: Because arc merging can produce self-intersecting rings, `shapely.make_valid()` or similar repair is recommended after reconstruction.

### Attribute data section (common to all file types)

Point, line, and polygon files share the same attribute table structure.

#### Attribute table header

| Content | Offset within attribute section | Bytes | Type | Description |
|---------|---------------------------------|-------|------|-------------|
| Reserved | 0–321 | 322 | - | Date, work directory, and other metadata |
| Field count | 322–323 | 2 | int16 | `field_count` |
| Record count | 324–327 | 4 | int32 | `record_count` |
| Record length | 328–329 | 2 | int16 | `record_length` |
| Reserved | 330–347 | 18 | - | Unused |
| Field descriptors | 348 onwards | 39 × field_count | - | 39 bytes per field |

> The original technical article states that field descriptors start at "the 349th byte"; this is a 1-based description. This document uses 0-based offsets, so the start is **348**.

#### Field descriptor

Each field descriptor is fixed **39 bytes**:

| Content | Offset within descriptor | Bytes | Type | Description |
|---------|--------------------------|-------|------|-------------|
| Field name | 0–19 | 20 | string | GBK encoded, terminated by `\x00` |
| Field type | 20 | 1 | uint8 | 0–7 |
| Storage offset | 21–24 | 4 | int32 | Start offset of the field within each record |
| Reserved / display width | 25–38 | 14 | - | Includes display width, decimal places, etc. |

Field type mapping:

| Type value | Meaning | Python type |
|------------|---------|-------------|
| 0 | string | `str` |
| 1 | byte | `int` |
| 2 | short integer | `int` |
| 3 | integer | `int` |
| 4 | float | `float` |
| 5 | double | `float` |
| 6 | date | `datetime.date` |
| 7 | time | `datetime.time` |

#### Record data

Immediately after the field descriptors there are `record_count × record_length` bytes of data. **The first record is empty**; the actual valid record count is `record_count - 1`.

Each record is sliced at the field descriptor's `storage offset`. String fields use their declared byte length and are decoded as GBK up to a null terminator or invalid byte. Numeric fields use the fixed size implied by their type code rather than the display width. Date fields contain year (int16), month and day; time fields contain hour, minute and seconds (double, including fractional seconds).

Unknown field-type descriptors are skipped without shifting the retained raw descriptors used by the Writer. Truncated numeric values and invalid or non-finite date/time values decode as `None`; a non-positive attribute `record_length` raises `MapGISError` instead of leaking a low-level parsing exception.

### Known limitations

1. **Incomplete coordinate system**: The file only stores projection/ellipsoid index numbers. The full CRS depends on external `ellip.dat` and projection index tables. The current implementation embeds common ellipsoids (Beijing 54, Xi'an 80, WGS84, etc.) and projections (Gauss-Krüger, Albers, Lambert).
2. **Polygon topology tolerance**: Arc endpoints may have tiny deviations, and some source data may contain topological gaps or self-intersections. Geometry validity repair is recommended after reading.
3. **Encoding**: Field names and string attribute values use GBK. Illegal bytes are typically truncated at the first invalid byte.
4. **Scale and invalid CRS fields**: Geographic files ignore the header scale because native zero/uninitialised values are valid. Supported projected CRS types use `scale / 1000`; a non-finite or non-positive projected scale and invalid projection parameters produce an empty CRS rather than usable-looking but corrupted coordinates.
5. **Graphic parameters are library-dependent**: symbol, line-style, colour and pattern numbers reference the MapGIS system libraries (Slib, line-style and pattern libraries) of the originating installation, which are not embedded in the file. They are only meaningful together with those libraries (and their versions); some field assignments are validated candidates rather than certainties (see the per-section notes).

## Changelog

### 2.7.1 (2026-11-07)

- Document original-library rendering in the package introduction and project metadata; clarify the complete vector / graphic-library / rendering scope
- Fix CI Ruff checks, pin Python 3.9 to Ubuntu 24.04, update checkout/setup-python actions and make nested `pytest.approx()` tests compatible with current pytest

### 2.7.0 (2026-11-07)

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

### 2.6.0
- **Writer**: encode GeoDataFrames back to native MapGIS `.wt` / `.wl` / `.wp` binaries — attribute table (GBK strings, dates, times, typed numerics), graphic parameters (with mapgis → shp → mapgis fidelity when the reader's parameter columns are present), CRS (longitude/latitude, Transverse Mercator, Albers, Lambert), and regenerated polygon topology (shared boundaries stored as single arcs with left/right polygon IDs). New public API: `Writer`, `write()`, and `WriterError`
- CLI converts in both directions based on the input extension (`.shp`, `.geojson`, `.gpkg`, ... → `.wt`/`.wl`/`.wp`); new `--encoding` option
- New runtime dependency: `pyogrio>=0.8` (reading shapefiles is now a runtime feature)
- `verify_pymapgis.py --roundtrip`: Reader → Writer → Reader regression over all local MapGIS files (not recorded in the baseline)
- New graphic-library parsers: `ColorLib` (Colorlib.lib CMYK → RGB) and `FillgrphLib` (fill-pattern records; unsupported structures return `None` rather than inferred geometry)
- Fix the coincident hole–island polygon regression (area over-count when a hole boundary exactly coincides with an independent island polygon); covered by `test_coincident_hole_and_island` and the public fixtures
- Public synthetic MapGIS fixtures (`tests/fixtures/mapgis/`, with generator, provenance manifest and SHA-256 checksums), clean-checkout test fallbacks, executable example (`examples/geological_workflow.py`), CI workflow (`.github/workflows/test-and-build.yml`) and release-archive inspection (`tests/inspect_dist.py`)
- Release notes for 2.3.0–2.5.0 remain to be backfilled into this changelog

### 2.2.1
- Packaging fix: `pymapgis.rendering` is under active development and is not yet ready for distribution (it is also undocumented and requires matplotlib, which is not a declared runtime dependency). It is excluded from the wheel and sdist; the published package again focuses on reading/conversion. Optional development copies are not required by the core package and may remain outside the tracked repository. A separate package or extra can be considered once the module stabilises

### 2.2.0
- `read_graphic_params=True`: decode line graphic parameters (`.wl`: `linetype`, `aux_linetype`, `width`, `x_coef`, `y_coef`) and polygon graphic parameters (`.wp` head_9 section: `fill_color`, `pattern`, `pattern_color`), exposed as `line_params` / `polygon_params` and joined into the GeoDataFrame
- Format documentation: line graphic-parameter area (bytes 18–56), polygon head_9 section, additional `.wl` index sections

### 2.1.0
- `read_point_params=True`: decode point graphic parameters (`.wt`: `point_type`, `symbol_no`, `height`, `width`, `spacing`, `angle`), exposed as `point_params` and joined into the GeoDataFrame
- New constants `POINT_TYPE_TEXT` / `POINT_TYPE_SYMBOL`
- Format documentation: point graphic-parameter area (bytes 23–92)

### 2.0.x
- Matured reader: CRS inference, vectorised parsing, polygon-topology reconstruction, GBK attribute decoding, CLI

## Development

Clone the repository and install in editable mode with dev dependencies:

```bash
git clone https://github.com/leecugb/mapgis2shp.git
cd mapgis2shp
pip install -e ".[dev]"
```

Run the test suite:

```bash
pytest
```

Run the smoke-test regression against all local MapGIS files:

```bash
python verify_pymapgis.py
```

### Synthetic and real test fixtures with executable example

Small synthetic MapGIS binaries are included under `tests/fixtures/mapgis/` so
that a fresh checkout can test actual `.wt`, `.wl`, and `.wp` input without
restricted survey data. Run their dedicated tests with:

```bash
python -m pytest -q tests/test_public_fixtures.py
```

The generic Reader, Writer, and CLI tests fall back to these public fixtures
when local real-data files are unavailable. See `tests/fixtures/README.md` for
provenance, regeneration, and the Apache-2.0 fixture licence. These
Writer-generated fixtures support internal regression only;
they are not official MapGIS exports or independent native-export validation.

An executable geological-data migration example is provided in
`examples/geological_workflow.py`. It reads the public binaries, reprojects the
layers to EPSG:32643, and reports attribute-grouped lengths and areas:

```bash
PYTHONPATH=src python3 examples/geological_workflow.py
```

The twelve-layer JWD vectors and all five matching SLIB libraries are also
bundled under `tests/fixtures/jwd/` and `tests/fixtures/slib/`. The real
rendering and colour-parser tests use them by default, with no absolute paths
or environment variables required:

```bash
python -m pytest -q tests/test_graphic_real_jwd.py
python -m pytest -q tests/test_pure.py -k "ColorLib or PcolorLib"
```

`PYMAPGIS_JWD` and `PYMAPGIS_SLIB` remain optional external-directory overrides;
`PYMAPGIS_COLORLIB` and `PYMAPGIS_PCOLOR` override individual colour libraries.
`tests/fixtures/jwd_slib_manifest.json` records provenance and SHA-256 for every
file. The real and synthetic fixtures are included in both the source archive
and wheel. `pymapgis.testing` provides a single source/install-independent path
API:

```python
from pymapgis.testing import fixture_path, jwd_path, slib_path

print(jwd_path())                       # directory containing the twelve vectors
print(slib_path("Pcolor.lib"))          # installed or source Pcolor.lib
print(fixture_path("mapgis"))           # synthetic WT/WL/WP directory
```

They verify library decoding, PNG/PDF generation, geometry and report
invariants; they are not a substitute for MapGIS native-application visual,
editing or save/reopen acceptance. See `tests/fixtures/README.md` for the
separate real-data provenance and licensing note.

The workflow in `.github/workflows/test-and-build.yml` is configured to run
lint, tests with the bundled synthetic and real fixtures, and the public
example on Linux, Windows, and macOS. Its build job additionally checks wheel and source-archive
contents with `tests/inspect_dist.py` and retains the artifacts for review.
The optional Matplotlib extra is required only for rendering tests.

## Further documentation

- [MapGIS file-structure knowledge archive](docs/mapgis_file_structure_knowledge.md) —
  header fields, section layouts, display gates, and the evidence appendix
  from the native-format reverse-engineering sessions
- [Colour parsing logic and truth anchors](docs/color_parsing_logic.md) —
  Colorlib channels, verified 32-byte Pcolor nodes, WP fill-versus-feature
  colour roles and JWD dialog anchors
- [Plaintext-pair audit report](docs/plaintext_pairs_audit.md) —
  field-by-field cross-validation against the official `.wat`/`.wal`/`.wap` exports

## Contributing

Contributions are welcome. Read the [contributing guide](CONTRIBUTING.md) for
project scope, development setup, format-evidence rules, tests, and the
pull-request checklist. Public issues and pull requests are used to maintain an
auditable collaboration and decision record.

OSGeo Community Project preparation materials include the
[project-page draft](docs/osgeo_community_project.md),
[application checklist](docs/osgeo_application_checklist.md), and
[licence and provenance review](docs/license_provenance.md).

Participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md), adapted
from the [Contributor Covenant](https://www.contributor-covenant.org/).
Contributors to mapgis2shp are expected to act respectfully toward others.

## License

This project is licensed under the [Apache License 2.0](LICENSE).

## Acknowledgments

The original reverse-engineering of the MapGIS binary format was done by the author of the legacy `pymapgis.py` script. This package refactors and extends that work into an installable, tested library.
