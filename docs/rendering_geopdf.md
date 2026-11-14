# Gauss–Krüger rendering and vector ISO 32000 GeoPDF

`examples/render_bundled_jwd.py` resolves projection **after** the MapGIS Reader has loaded the layers. Reader itself never reprojects coordinates.

## Target CRS and scale

- `--target-crs EPSG:32643` (or a PROJ string) always takes precedence.
- Without `--target-crs`, the pipeline computes one target from the union of all non-empty layer bounds:
  - the mean longitude is the centre of the combined geographic bounds;
  - the default is a 6-degree Gauss–Krüger zone (`--zone-width 6`; `3` is optional);
  - all layers are reprojected to that one CRS, avoiding mixed-CRS rendering failures;
  - the source ellipsoid and `towgs84` parameters are preserved in the generated CRS.
- `--scale 250000` is the map-scale denominator used for paper sizing. It is independent of the projection scale factor (`k=1` for Gauss–Krüger and `k=0.9996` for UTM). **The vector PDF Axes and page are calculated from this denominator**, so the delivered page scale is exact rather than merely a renderer setting.
- If source CRS is missing, provide `--source-crs`. Alternatively, `--map-units-per-mm` permits unprojected rendering only when no target CRS is requested and `--no-geopdf` is set.
- Mixed source datums, invalid bounds, antimeridian ambiguity, spans over 9 degrees, and polar-domain inputs require an explicit target CRS.

For the twelve JWD layers, the default is central meridian **75°E**, 6-degree zoning, source Beijing-54 datum parameters, and **1:250,000**.

## Label layout

The standard entry point defaults to integrated collision avoidance and attitude-point dip attributes:

- Native WT annotations are registered as fixed obstacles first. Derived dip labels are placed next, followed by WP/WL labels, so drawing order establishes one shared collision domain without changing the report order or visual z-order.
- `exclude_text_categories` filters native **text annotations only**. Attitude Subgraph points are retained even when their native text twins are excluded.
- `dip`/`GZBBAD` generates horizontal 3.5 pt dip labels. Independent native dip annotations are excluded to prevent duplicates. Use `--native-attitude-annotations` to retain the independent annotations instead. The fallback dip tick is defined as 2.0 paper mm, independent of output DPI.
- Polygon labels use randomized candidate placement with seed 42, a 2 pt buffer and a 48 pt maximum in-polygon offset. Dip labels use a 0.5 pt buffer and right-normal offsets. Unresolved dip labels are never silently deleted; they are counted in `attitude_dip_label_collision`.
- `--polygon-label-fontsize` and `--polygon-label-max-offset-pt` expose the layout parameters for data-specific adapters. `--figsize` and `--axes-rect` control the initial layout canvas, which is important for portrait sheets and dense labels.
- The requested `--dpi` is used when the Figure is created, not only when it is saved. It affects text measurement and candidate layout but not the exact GeoPDF scale. Physical style parameters and final layout results are therefore reported separately.
- Polygon labels that cannot fit inside their own polygon are counted in `label_skipped_collision`. Successful moves are counted in `label_offset`.
- `jwd_text_collisions.json` records a final audit of every visible text artist. `native_text_collision` identifies pre-existing native-annotation collisions separately from managed polygon/dip layout failures.
- Use `--legacy-label-layout` for the historical non-avoidance baseline. When this option is used alone, native dip annotations are retained. `--attribute-dip-labels` can be combined with it to request only the attribute-dip change.

## Outputs

The example writes preview-only `jwd_map.png` and `jwd_map.svg`, plus `jwd_render_reports.json`. It deliberately does **not** write an ordinary tight-bbox `jwd_map.pdf`, because that page format does not implement a certified physical map scale. The formal PDF product is `jwd_map_geopdf.pdf`, a fully vector **ISO 32000 GeoPDF**.

JWD enables `GraphicRenderer(vector_patterns=True)`. Fillgrph tiles are emitted as vector `LineCollection` and `PolyCollection` artists with polygon-and-hole clipping. The vector writer rejects any raster image XObject instead of silently delivering a hybrid PDF. No `jwd_map_geopdf_source.png` is produced.

The GeoPDF page contains:

- a page `/VP` viewport;
- `/Measure /GEO`;
- four geographic control points (`/GPTS`) and normalized local points (`/LPTS`);
- a WKT2 `/GCS` coordinate definition. WKT2 `BOUNDCRS` retains numeric `towgs84` parameters when present;
- vector paths and text, with no raster image objects.

PNG and SVG outputs are previews and must not be described as scale-certified prints. Their DPI does not control the vector GeoPDF page geometry.

## Exact vector page scale

For a projected CRS with metric axis conversion, the required Axes dimensions are:

```text
axes_width_mm  = abs(xmax - xmin) * metres_per_unit / scale_denominator * 1000
axes_height_mm = abs(ymax - ymin) * metres_per_unit / scale_denominator * 1000
```

`write_vector_geopdf()` resizes the figure iteratively until the actual Axes has those physical dimensions, preserving its margins and equal-aspect adjustment. It then computes a north-up transform from **PDF points** (bottom-left origin) to projected map coordinates. The four page corners are transformed to geographic latitude/longitude for `/GPTS`.

A geographic CRS is rejected for exact paper-scale output because degrees cannot be converted to a paper scale without a latitude-dependent approximation. The earlier raster writer `write_geopdf()` remains available for compatibility, but JWD uses `write_vector_geopdf()` exclusively.

Use `--no-geopdf` to skip strict-scale vector GeoPDF generation; the remaining PNG/SVG files are previews only, with no scale-certified formal PDF. The `render` extra installs PyMuPDF (with a Python-3.9-compatible version bound); the import is delayed so `--no-geopdf` still works with older rendering-only installations.

## Verification

`inspect_geopdf()` reads the viewport and coordinate dictionaries back from the final file. It also reports page images, all image XObjects, vector drawing count and text character count.

The standard CLI independently computes X/Y scale denominators from the page transform and full page dimensions, then aborts if either differs from the requested scale or if any raster image object is found. `jwd_render_reports.json` includes a `sources` manifest with each input's feature count, native CRS, SHA-256 and native header scale values. When `.WP` and `.WP~` versions of the same layer coexist, the original `.WP~` backup is loaded once and the normalized `.WP` is not duplicated.

The JWD integration test requires:
- zero page images and zero image XObjects;
- at least one vector drawing and non-empty text;
- central meridian 75°E and scale factor 1 in the WKT read by GDAL `osr`;
- the original `towgs84` values;
- control-point coverage of the source data bounds;
- independent X/Y scale calculations both returning 250000.

For vector output, scale is checked from the page transform and full page dimensions:

```text
actual_x_scale = abs(page_transform[1]) * page_width_pt * metres_per_unit / (page_width_mm / 1000)
actual_y_scale = abs(page_transform[5]) * page_height_pt * metres_per_unit / (page_height_mm / 1000)
```

The current GDAL 3.11 runtime has no PDF driver, so `gdalinfo` cannot validate the file in this environment. Validation is therefore performed with PyMuPDF readback and GDAL `osr` WKT parsing. When a GDAL build with the PDF driver is available, additionally run:

```bash
gdalinfo jwd_map_geopdf.pdf
```
