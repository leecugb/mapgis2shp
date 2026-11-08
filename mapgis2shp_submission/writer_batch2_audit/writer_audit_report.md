# Writer SHP batch 2 audit

Cases: 11
Write errors: 0
Attribute matches: 11
Topological matches: 10
Exact coordinate matches: 2

| Case | Write error | Attributes | Topology | Exact coordinates | Source CRS | Native CRS | Our CRS |
|---|---|---|---|---|---|---|---|
| 01_minimal_triangle | none | True | True | False | EPSG:4326 | None | +proj=longlat +datum=WGS84 +no_defs +type=crs |
| 02_two_sizes | none | True | True | False | EPSG:4326 | None | +proj=longlat +datum=WGS84 +no_defs +type=crs |
| 03_three_holes | none | True | True | False | EPSG:4326 | None | +proj=longlat +datum=WGS84 +no_defs +type=crs |
| 04_multipart_with_holes | none | True | True | False | EPSG:4326 | None | +proj=longlat +datum=WGS84 +no_defs +type=crs |
| 05_touching_point | none | True | True | False | EPSG:4326 | None | +proj=longlat +datum=WGS84 +no_defs +type=crs |
| 06_shared_edge | none | True | True | False | EPSG:4326 | None | +proj=longlat +datum=WGS84 +no_defs +type=crs |
| 07_hole_and_island | none | True | True | False | EPSG:4326 | None | +proj=longlat +datum=WGS84 +no_defs +type=crs |
| 08_duplicate_vertices | none | True | True | False | EPSG:4326 | None | +proj=longlat +datum=WGS84 +no_defs +type=crs |
| 09_invalid_bowtie | none | True | False | False | EPSG:4326 | None | +proj=longlat +datum=WGS84 +no_defs +type=crs |
| 10_points | none | True | True | True | EPSG:4326 | None | +proj=longlat +datum=WGS84 +no_defs +type=crs |
| 11_multiline_and_duplicate | none | True | True | True | EPSG:4326 | None | +proj=longlat +datum=WGS84 +no_defs +type=crs |
