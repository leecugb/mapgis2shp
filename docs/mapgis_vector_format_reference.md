# MapGIS vector format reference

> This is the current implementation-oriented reference for the MapGIS 6x/67 binary layouts used by `Reader` and `Writer`. Historical reverse-engineering notes and their superseded candidates are retained separately.

MapGIS vector files are a closed-source binary vector data format developed by MapGIS (Zhongdi Digital). They are widely used in geological surveying, engineering investigation, and scientific research in China. The format itself **does not carry a complete coordinate-system description**; projection and ellipsoid parameters must be interpreted using the index tables in the MapGIS installation environment (e.g., `mapgis67\program\ellip.dat`).

**Conventions**

- All offsets are **0-based** from the beginning of the file.
- `int16` / `int32` / `uint8` / `double` are all **little-endian**.
- String fields are encoded as **GBK** unless otherwise noted.

## Overall file structure

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

## Coordinate reference system parsing

The CRS parameters are stored at the same fixed offsets in all three file types:

| Content | Offset | Bytes | Type | Description |
|---------|--------|-------|------|-------------|
| Projection type | 109 | 1 | uint8 | Projection-type index |
| Ellipsoid type | 110 | 1 | uint8 | Ellipsoid index |
| Scale | 143 | 8 | double | Scale denominator |
| Transverse Mercator projection scale | 232 | 8 | double | `k=1` for Gauss-Krüger; `k=0.9996` for UTM |

> The projection-type index and ellipsoid index correspond to index tables in the MapGIS installation directory and `ellip.dat`, respectively. Therefore, the full CRS interpretation depends on the external MapGIS software environment.

### Common ellipsoids

| Index | Datum | PROJ4 definition |
|-------|-------|------------------|
| 1 | Beijing 54 | `+ellps=krass +towgs84=15.8,-154.4,-82.3,0,0,0,0 +units=m +no_defs` |
| 2 | Xi'an 80 | `+a=6378140 +b=6356755.288157528` |
| 7 | WGS84 | `+datum=WGS84` |
| 16 | Krassovsky | `+ellps=krass` |

### Projection parameters

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

For longitude/latitude (projection type 0), coordinates are decimal degrees and the header scale is ignored because native files may store zero there. For supported projected CRS types, internal coordinates are converted to map units with `scale / 1000`. A non-finite or non-positive projected scale, or invalid projection parameters, yields an empty CRS rather than collapsing or poisoning the geometry. The resulting multiplier is exposed as `Reader.coordinate_scale_factor` and `geodataframe.attrs['mapgis_coordinate_scale_factor']`.

For Transverse Mercator, offset 232 stores the projection scale `k`, independently of the geometry multiplier. A header with central meridian −117°, WGS84 ellipsoid, `k=0.9996`, and header scale 1000 therefore reads as an EPSG:32611-equivalent CRS with `coordinate_scale_factor == 1.0` and unchanged metre coordinates.

## Point files (`.wt`)

### File header and index section

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

### Coordinate data section

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

### Point graphic parameters (bytes 23–92)

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

## Line files (`.wl`)

### File header and index section

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

### Line data section

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

### Line graphic parameters (bytes 18–56)

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

### Additional sections

Beyond the documented sections (lines / coordinates / attributes), `.wl`
files in J43C001002 carry further per-line sections in the header index:
head_4 (24 bytes per line), head_7 (32 bytes per line) and head_8 (4 bytes
per line). Their content shows no correlation with display parameters and
their purpose is undetermined (possibly topology/annotation linkages).

### Coordinate data section

The coordinate data section stores anchor points sequentially. Each XY pair occupies **16 bytes** (2 × double). Reading uses the anchor point count and coordinate offset from the line index.

## Polygon files (`.wp`)

### File header and index section

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

### Arc data section

Polygon files reuse the line arc-storage structure: **57 bytes** per arc index record, with the first 57-byte record empty. The fields have the same meaning as in `.wl` (anchor point count + coordinate offset).

### Coordinate data section

Arc coordinates use the same 16-byte double-precision XY pairs as line files, but the WP coordinate section also contains variable-length **polygon/ring/arc index records** between coordinate blocks. Arc byte offsets therefore always refer to the combined coordinate-and-index stream, not to an array of coordinates alone.

For freshly written files, the Writer emits each polygon's ring-index record after the first arc of the following polygon, and emits the final polygon's record after the final arc. The record lead is derived from raw arc point counts and hole/zero markers. Each record's byte offset is returned to the head_9 encoder and stored in `field5`/`field6`/`field7`, keeping the coordinate section, arc index and ring pointers synchronized.

### Polygon topology data section

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

### Polygon graphic-parameter section (head_9)

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

### Polygon reconstruction key points

1. **Select arcs**: For target polygon ID `pid`, select arcs where `left_id == pid` or `right_id == pid`.
2. **Orient arcs**: If `left_id == pid`, reverse the arc coordinates so the polygon boundary stays on the consistent side.
3. **Form rings**: Use a greedy nearest-endpoint merge to chain arcs into closed rings. Endpoint coordinates may differ by ~1e-6 due to floating-point precision.
4. **Hole detection**: Use point-in-polygon containment between rings to distinguish outer shells and inner holes.
5. **Validity repair**: Because arc merging can produce self-intersecting rings, `shapely.make_valid()` or similar repair is recommended after reconstruction.

## Attribute data section (common to all file types)

Point, line, and polygon files share the same attribute table structure.

### Attribute table header

| Content | Offset within attribute section | Bytes | Type | Description |
|---------|---------------------------------|-------|------|-------------|
| Reserved | 0–321 | 322 | - | Date, work directory, and other metadata |
| Field count | 322–323 | 2 | int16 | `field_count` |
| Record count | 324–327 | 4 | int32 | `record_count` |
| Record length | 328–329 | 2 | int16 | `record_length` |
| Reserved | 330–347 | 18 | - | Unused |
| Field descriptors | 348 onwards | 39 × field_count | - | 39 bytes per field |

> The original technical article states that field descriptors start at "the 349th byte"; this is a 1-based description. This document uses 0-based offsets, so the start is **348**.

### Field descriptor

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

### Record data

Immediately after the field descriptors there are `record_count × record_length` bytes of data. **The first record is empty**; the actual valid record count is `record_count - 1`.

Each record is sliced at the field descriptor's `storage offset`. String fields use their declared byte length and are decoded as GBK up to a null terminator or invalid byte. Numeric fields use the fixed size implied by their type code rather than the display width. Date fields contain year (int16), month and day; time fields contain hour, minute and seconds (double, including fractional seconds).

Unknown field-type descriptors are skipped without shifting the retained raw descriptors used by the Writer. Truncated numeric values and invalid or non-finite date/time values decode as `None`; a non-positive attribute `record_length` raises `MapGISError` instead of leaking a low-level parsing exception.

## Known limitations

1. **Incomplete coordinate system**: The file only stores projection/ellipsoid index numbers. The full CRS depends on external `ellip.dat` and projection index tables. The current implementation embeds common ellipsoids (Beijing 54, Xi'an 80, WGS84, etc.) and projections (Gauss-Krüger, Albers, Lambert).
2. **Polygon topology tolerance**: Arc endpoints may have tiny deviations, and some source data may contain topological gaps or self-intersections. Geometry validity repair is recommended after reading.
3. **Encoding**: Field names and string attribute values use GBK. Illegal bytes are typically truncated at the first invalid byte.
4. **Scale and invalid CRS fields**: Geographic files ignore the header scale because native zero/uninitialised values are valid. Supported projected CRS types use `scale / 1000`; a non-finite or non-positive projected scale and invalid projection parameters produce an empty CRS rather than usable-looking but corrupted coordinates.
5. **Graphic parameters are library-dependent**: symbol, line-style, colour and pattern numbers reference the MapGIS system libraries (Slib, line-style and pattern libraries) of the originating installation, which are not embedded in the file. They are only meaningful together with those libraries (and their versions); some field assignments are validated candidates rather than certainties (see the per-section notes).
