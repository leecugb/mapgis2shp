# 第三批 MapGIS 官方转换说明

请将本目录 12 个 SHP 分别用 MapGIS 转换为 MapGIS 文件。本批重点验证 24 位环索引偏移的高位字节、投影坐标、属性边界和异常输入。

## 输出

- `01`–`09`、`12` → `.WP`；
- `10_points.shp` → `.WT`；
- `11_multiline.shp` → `.WL`。

建议输出到本目录的新子目录 `mapgis_output/`，保留原文件名，不覆盖源 SHP。记录 MapGIS 版本、转换设置及任何异常提示。

## 用例

| 文件 | 验证重点 |
|---|---|
| 01_reference_triangle | 最小参照环 |
| 02_identical_polygons | 两个完全相同但 FID 不同的面 |
| 03_shared_edge_duplicate | 共边含连续重复点 |
| 04_nested_hole_island | 孔洞与独立岛 |
| 05_large_ring_over_64k | 5001 点外环＋101 点孔洞，环索引偏移超过 65535 |
| 06_large_then_small | 大面之后的小面，后续指针也超过 65535 |
| 07_projected_utm | EPSG:32643 投影坐标与共边 |
| 08_attribute_types | 长中文、空字符串、null、int32 极值、浮点和日期 |
| 09_null_geometry | 一个有效面＋一个空几何，转换可能拒绝 |
| 10_points | 中文属性与可空日期 |
| 11_multiline | MultiLineString 与重复点 |
| 12_degenerate_ring | 全部顶点相同，故意负例 |

## 属性

- `FID` 均有效；
- `DATE`：2026-03-01、2026-03-02、空值循环；
- 08 另含 `LONG_NAME`、`TEXT_NULL`、`INT32`、`FLOAT64`、`NOTE`，用于检查字段宽度、中文和极值。

## 返回时请提供

1. 官方 WT/WL/WP 文件；
2. 显示是否空白或异常，以及实际要素数、孔洞是否正确；
3. 05、06 的区参数截图，用于验证 field5/6/7 的 24 位偏移及高位字节；
4. 08 的属性表截图，用于检查长中文、空值和数值；
5. 对 09、12 若转换失败，请保留错误信息，不要删除负例。

`manifest.csv` 记录了几何数量、重复点、无效几何、空几何和 CRS。
