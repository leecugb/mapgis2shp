# Writer SHP batch 2 audit

Cases: 12
Write errors: 2
Attribute matches: 10
Topological matches: 10
Exact coordinate matches: 2

| Case | Write error | Attributes | Topology | Exact coordinates | Source CRS | Native CRS | Our CRS |
|---|---|---|---|---|---|---|---|
| 01_reference_triangle | none | True | True | False | EPSG:4326 | None | +proj=longlat +datum=WGS84 +no_defs +type=crs |
| 02_identical_polygons | none | True | True | False | EPSG:4326 | None | +proj=longlat +datum=WGS84 +no_defs +type=crs |
| 03_shared_edge_duplicate | none | True | True | False | EPSG:4326 | None | +proj=longlat +datum=WGS84 +no_defs +type=crs |
| 04_nested_hole_island | none | True | True | False | EPSG:4326 | None | +proj=longlat +datum=WGS84 +no_defs +type=crs |
| 05_large_ring_over_64k | none | True | True | False | EPSG:4326 | None | +proj=longlat +datum=WGS84 +no_defs +type=crs |
| 06_large_then_small | none | True | True | False | EPSG:4326 | None | +proj=longlat +datum=WGS84 +no_defs +type=crs |
| 07_projected_utm | none | True | True | False | EPSG:32643 | None | +proj=tmerc +lat_0=0 +lon_0=75.0 +k=1 +x_0=500000 +y_0=0 +datum=WGS84 +units=m +no_defs +type=crs |
| 08_attribute_types | none | True | True | False | EPSG:4326 | None | +proj=longlat +datum=WGS84 +no_defs +type=crs |
| 09_null_geometry | WriterError: found 1 empty/null geometries at row positions [1]; pass on_empty='drop' to discard them explicitly | None | None | None | EPSG:4326 | None | None |
| 10_points | none | True | True | True | EPSG:4326 | None | +proj=longlat +datum=WGS84 +no_defs +type=crs |
| 11_multiline | none | True | True | True | EPSG:4326 | None | +proj=longlat +datum=WGS84 +no_defs +type=crs |
| 12_degenerate_ring | WriterError: polygon topology cannot be encoded safely: polygon 1: ring collapsed to fewer than three distinct vertices after snapping | None | None | None | EPSG:4326 | None | None |
