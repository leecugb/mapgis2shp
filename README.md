# mapgis2shp

[![PyPI version](https://img.shields.io/pypi/v/mapgis2shp.svg)](https://pypi.org/project/mapgis2shp/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.21487339-blue.svg)](https://doi.org/10.5281/zenodo.21487339)

Read MapGIS 6.x/67 vector files (`.wt`, `.wl`, `.wp`) into [GeoPandas](https://geopandas.org/) GeoDataFrames.

MapGIS is a widely used closed-source GIS platform in China, especially in geological surveying, engineering, and scientific research. `pymapgis` provides a lightweight, open-source reader for its native point, line, and polygon vector formats.

> **Relationship to prior work:** This package (`mapgis2shp`, import name `pymapgis`) is the matured, validated successor to the first author's earlier [`pymapgis`](https://github.com/leecugb/pymapgis) (2022) single-file reader — both developed by **Shijie Li** (leecugb). The present version adds coordinate-reference inference, vectorised parsing, polygon-topology reconstruction, and independent validation against the official MapGIS export.

## Features

- Read **point** (`.wt`), **line** (`.wl`), and **polygon** (`.wp`) files
- Decode GBK-encoded attribute fields and field names
- Decode point graphic parameters (text/symbol kind, subgraph number, glyph size, rotation angle)
- Decode line graphic parameters (style number, width in mm, pattern coefficients)
- Decode polygon graphic parameters (fill colour / pattern numbers from the head_9 section)
- Reconstruct polygon topology from arc records
- Preserve or repair invalid polygon geometries with `shapely.make_valid`
- Export to any format supported by GeoPandas / Fiona (Shapefile, GeoJSON, GeoPackage, etc.)
- Simple command-line interface for quick conversions

## Installation

```bash
pip install mapgis2shp
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

## Command-line usage

```bash
# Convert a polygon file to Shapefile
pymapgis input.wp output.shp

# Convert to GeoJSON
pymapgis input.wl output.geojson --driver GeoJSON

# Keep raw (possibly invalid) polygon geometries
pymapgis input.wp output.shp --no-make-valid
```

The same interface is available as `python -m pymapgis input.wp output.shp`.

## API

### `Reader(filepath, make_valid=True, read_point_params=False, read_graphic_params=False)`

Main entry point for reading a MapGIS file. With `read_point_params=True`
(point files only), the per-point graphic parameter area is decoded as well:
the columns `point_type` (0 = text, 1 = symbol), `symbol_no`, `height`,
`width`, `spacing` and `angle` (degrees, counter-clockwise from east) are
appended to the GeoDataFrame and exposed separately as `point_params`.
With `read_graphic_params=True`, graphic parameters are decoded for any
file type — point parameters for `.wt` (as above), line parameters for
`.wl` (`linetype`, `aux_linetype`, `width`, `x_coef`, `y_coef`, exposed as
`line_params`), and polygon parameters for `.wp` (`fill_color`, `pattern`,
`pattern_color` from the head_9 section, exposed as `polygon_params`).

**Attributes**

| Attribute | Type | Description |
|-----------|------|-------------|
| `shapeType` | `str` | `"POINT"`, `"LINE"`, or `"POLYGON"` |
| `crs` | `pyproj.CRS` or `None` | Detected coordinate reference system |
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

# Line files: style number, width in millimetres, pattern coefficients
with Reader("lines.wl", read_graphic_params=True) as r:
    print(r.geodataframe[["linetype", "width", "x_coef", "y_coef"]].head())

# Polygon files: fill colour / pattern numbers (head_9 section)
with Reader("polygons.wp", read_graphic_params=True) as r:
    print(r.geodataframe[["fill_color", "pattern", "pattern_color"]].head())
```

> **Warning — not self-contained.** Style, colour, symbol and pattern
> numbers are indices into the MapGIS system libraries (Slib, line-style
> library, pattern library) of the *originating* MapGIS installation; the
> glyph definitions are not stored in the data files. The same number may
> mean different things under a different or customised library. Field
> layouts were reverse-engineered and validated on the layers of map sheet
> J43C001002 — verify against your own data before relying on them.

## Supported formats

| Extension | Geometry type | Graphic parameters | Notes |
|-----------|---------------|--------------------|-------|
| `.wt` | Point | kind / symbol number / size / angle | 93-byte fixed record size |
| `.wl` | LineString | style number / width / coefficients | 57-byte arc index + coordinate block |
| `.wp` | Polygon/MultiPolygon | fill colour / pattern (head_9) | Arc index + topology table + coordinate block |

CRS detection supports the most common projections found in MapGIS 6.x files, including longitude/latitude, Gauss-Krüger (Transverse Mercator), Lambert Conformal Conic, and Albers Equal-Area. Because MapGIS stores only projection and ellipsoid **index numbers**, the complete CRS depends on external MapGIS index files (`ellip.dat`, etc.).

## Technical Documentation: MapGIS Vector File Format

> The following section is the technical specification of the MapGIS 6x/67 binary vector format (`.wt` / `.wl` / `.wp`). It is synchronized from `docs/MapGIS_Vector_Format.md` in this repository.

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
| Index section | 10 records of 10 bytes each, recording start offsets and sizes of sub-sections |
| Sub-sections | Coordinates / arcs / polygons / attributes, etc. |

The index-section start offset is at file bytes **12–15**, denoted as `data_start`. From `data_start` there are 10 consecutive index records:

```
head_1 : offset data_start + 0
head_2 : offset data_start + 10
...
head_10: offset data_start + 90
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

The central meridian and standard parallels are encoded as `DDDMMSS.sss` BCD-style doubles and must be converted to decimal degrees by splitting degrees, minutes, and seconds:

```
deg = s[:-4]
min = s[-4:-2]
sec = s[-2:]
decimal_degrees = deg + min/60 + sec/3600
```

For longitude/latitude (projection type 0), coordinate values are in decimal degrees. For projected coordinate systems, internal coordinates are usually in **millimeters**; after reading they are converted to meters by `scale = scale / 1000`.

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
| Reserved | 49–92 | 44 | - | Not fully decoded (class codes observed at offsets 75 and 83; not read) |

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
| Auxiliary style number | 24–25 | 2 | int16 | Auxiliary line-style index |
| Class code | 26–27 | 2 | int16 | Varies by layer category; exact meaning undetermined |
| Reserved | 28–29 | 2 | - | Unused |
| Line width | 30–33 | 4 | float32 | Width in millimetres |
| Reserved | 34 | 1 | - | Padding |
| X coefficient | 35–38 | 4 | float32 | Pattern X scale (unaligned) |
| Y coefficient | 39–42 | 4 | float32 | Pattern Y scale (unaligned) |
| Undecoded | 43–56 | 14 | - | Small per-class values; layout not yet pinned down |

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
| head_3 | 20 | Present in J43C001002; purpose undetermined |
| head_4 | 30 | Polygon topology data section start and size |
| head_9 | 80 | Polygon graphic-parameter section (see below) |
| head_10 | 90 | Attribute data section start and size |

#### Arc data section

Polygon files reuse the line arc-storage structure: **57 bytes** per arc index record, with the first 57-byte record empty. The fields have the same meaning as in `.wl` (anchor point count + coordinate offset).

#### Coordinate data section

Same as line files: each 16 bytes stores one double-precision XY pair. All arc coordinates are stored in this section.

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
| Class code | 1 | 1 | uint8 | Varies by geological unit; meaning undetermined |
| Reserved | 2–3 | 2 | - | Unused |
| Fill colour | 4–5 | 2 | int16 | Fill colour index (candidate) |
| Fill-pattern number | 6–7 | 2 | int16 | Pattern-library index; clusters by rock category (sedimentary ~3866–3931, intrusive 384–388, metamorphic 751–758) |
| Pattern colour | 8–9 | 2 | int16 | Pattern colour index (candidate) |
| Undecoded | 10–39 | 30 | - | Pattern sub-parameters for patterned units; layout not yet pinned down |

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

Each record is sliced according to the `storage offset` in the field descriptors. Field length is calculated as:

- Non-final field: `next_offset - current_offset`
- Final field: `record_length - current_offset`

String fields are read up to the first `\x00`. Date fields are year (int16) + month + day. Time fields are hour + minute + seconds (double, including microseconds).

### Known limitations

1. **Incomplete coordinate system**: The file only stores projection/ellipsoid index numbers. The full CRS depends on external `ellip.dat` and projection index tables. The current implementation embeds common ellipsoids (Beijing 54, Xi'an 80, WGS84, etc.) and projections (Gauss-Krüger, Albers, Lambert).
2. **Polygon topology tolerance**: Arc endpoints may have tiny deviations, and some source data may contain topological gaps or self-intersections. Geometry validity repair is recommended after reading.
3. **Encoding**: Field names and string attribute values use GBK. Illegal bytes are typically truncated at the first invalid byte.
4. **Scale**: In projected coordinate systems internal coordinates are often in millimeters and are converted to meters by `scale / 1000`; for longitude/latitude systems `scale` is usually 1.
5. **Graphic parameters are library-dependent**: symbol, line-style, colour and pattern numbers reference the MapGIS system libraries (Slib, line-style and pattern libraries) of the originating installation, which are not embedded in the file. They are only meaningful together with those libraries (and their versions); some field assignments are validated candidates rather than certainties (see the per-section notes).

## Changelog

### 2.2.1
- Packaging fix: `pymapgis.rendering` is under active development and is not yet ready for distribution (it is also undocumented and requires matplotlib, which is not a declared dependency). It is now excluded from the wheel and sdist; the published package again focuses on reading/conversion. The module remains in the source repository and will be published as a separate package or extra once it stabilises

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

## License

This project is licensed under the [Apache License 2.0](LICENSE).

## Acknowledgments

The original reverse-engineering of the MapGIS binary format was done by the author of the legacy `pymapgis.py` script. This package refactors and extends that work into an installable, tested library.
