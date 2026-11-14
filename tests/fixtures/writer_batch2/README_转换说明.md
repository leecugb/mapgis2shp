# 第二批 MapGIS 官方转换说明

请将本目录 11 个 SHP 分别用 MapGIS 转换为 MapGIS 文件。本批重点验证最小环、24 位环索引偏移、孔洞与多部件、MultiLineString 和属性编码。

## 输出

- `01`–`09` → `.WP`；
- `10_points.shp` → `.WT`；
- `11_multiline_and_duplicate.shp` → `.WL`。

建议输出到本目录的新子目录 `mapgis_output/`，保留原文件名，不覆盖源 SHP。记录 MapGIS 版本、转换设置及任何异常提示。

## 用例

| 文件 | 要素数 | 外环 | 孔洞环 | 验证重点 |
|---|---:|---:|---:|---|
| 01_minimal_triangle | 1 | 1 | 0 | 最小有效三角形及最小偏移 |
| 02_two_sizes | 2 | 2 | 0 | 不同大小面及后续偏移 |
| 03_three_holes | 1 | 1 | 3 | 多孔洞和末孔洞零标记 |
| 04_multipart_with_holes | 1 | 2 | 2 | 同一 FID 的两个外环及各自孔洞 |
| 05_touching_point | 2 | 2 | 0 | 仅共一个顶点 |
| 06_shared_edge | 2 | 2 | 0 | 精确共享边 |
| 07_hole_and_island | 2 | 2 | 1 | 孔洞与独立岛 |
| 08_duplicate_vertices | 1 | 1 | 0 | 起点及闭合处连续重复点 |
| 09_invalid_bowtie | 1 | 1 | 0 | 故意自相交无效环 |
| 10_points | 3 | — | — | 中文名称、浮点值和可空日期 |
| 11_multiline_and_duplicate | 2 | — | — | MultiLineString 与重复点 |

## 属性

- 所有要素均有有效 FID；
- `NAME`、`CODE` 用于区分记录；
- `VALUE` 为浮点数；
- `DATE`：第 1 条为 2026-02-01，第 2 条为 2026-02-02，第 3 条为空。

## 返回时请提供

1. 官方 WT/WL/WP 文件；
2. 显示是否空白或有异常，以及实际要素数、孔洞是否正确；
3. 01、03、04、07 任一区的区参数截图，用于核对 field5/field6/field7 的 24 位环索引偏移；
4. 如可执行，另存副本供 Reader 对照。

`manifest.csv` 记录了几何数量、重复点和无效几何情况。
