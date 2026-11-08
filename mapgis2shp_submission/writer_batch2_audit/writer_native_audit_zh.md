# pymapgis.Writer 原生 SHP 转换批次审计报告

## 范围与证据边界

- 输入：用户提供的 11 组 SHP 及 MapGIS 原生转换文件，共 68 个文件、57,301 字节。
- 输出：独立目录 `writer_batch2_audit/`，未修改源目录。
- 对照：SHP 源数据、MapGIS 原生转换结果、`pymapgis.Writer` 输出及其 Reader 回读结果。
- MapGIS 版本与转换设置未提供，本报告不作推断。
- 当前证据不等同于 Writer 输出已在 MapGIS 中完成原生打开、编辑和另存验收。

## 最终验证结果

| 检查 | 结果 |
|---|---|
| 原生 Writer 用例 | 11 passed |
| wheel 安装态原生用例与 fixture 访问 | 12 passed |
| 完整测试套件 | 352 passed, 0 skipped |
| Ruff | 全部通过 |
| Twine | wheel、sdist 均通过 |
| wheel 内容检查 | 109 entries，通过 |
| sdist 内容检查 | 143 entries，通过 |

`tests/fixtures/writer_batch2_manifest.json` 记录来源、字节数和 SHA-256。MapGIS 版本与转换设置标为未提供。

## 已修复的默认图形参数

原生转换批次证明，独立 WT/WL 路径的默认值与 WP 面弧段路径不一致，且与原生 SHP 转换默认值不一致。已作如下修复：

| 参数 | 修复前 Writer 默认值 | 原生参考与修复后 |
|---|---:|---:|
| WT height / width | 1.0 mm | 0.1 mm |
| WT color | 1 | 6 |
| WT pen_width | 0.05 mm | 0.1 mm |
| WL width | 0.1 mm | 0.05 mm |
| WL x_coef / y_coef | 5.0 | 1.0 |
| WL aux_flag | 0 | 1 |

显式传入的图形参数仍优先于默认值。WP 面弧段路径原本已使用 0.05 mm、1.0 和 `aux_flag=1`，未作修改。

## 逐用例结果

| 用例 | 属性与坐标/拓扑结果 | 原生参考差异及说明 |
|---|---|---|
| 01_minimal_triangle | 通过；最小三角形及环索引写入成功 | Writer 与原生几何一致 |
| 02_two_sizes | 属性与拓扑一致 | 原生 Reader 将部分共享弧组织为 MultiPolygon，Writer 保留源面语义 |
| 03_three_holes | 一个外环和三个孔洞均保留，拓扑一致 | 孔洞环方向/链序与原生不同，不构成面积或拓扑错误 |
| 04_multipart_with_holes | 两个外环及各自孔洞均保留，仍属同一 FID | 原生与 Writer 的孔洞环方向/链序不同 |
| 05_touching_point | 属性与拓扑一致 | 原生 Reader 将部分共享顶点组织为多部件，Writer 保留源面语义 |
| 06_shared_edge | 两个共享边面均保留，拓扑一致 | 原生 Reader 将共享边作为 LineString 留在 GeometryCollection 中；Writer 保留两个源面 |
| 07_hole_and_island | 孔洞与独立岛均保留，未重复计入岛面 | 原生 Reader 将岛面同时组织进第一个多部件和独立记录；Writer 与源语义一致 |
| 08_duplicate_vertices | 连续重复点及闭合重复点均保留 | 共 7 个坐标点，与原生一致 |
| 09_invalid_bowtie | 与原生一致，拆分为两个三角形 | 源 bowtie 为无效几何，因此不与源几何作有效拓扑相等断言 |
| 10_points | 3 个点、浮点值、中文名称和空日期均保留；坐标完全一致 | 默认符号尺寸、颜色和笔宽已对齐 |
| 11_multiline_and_duplicate | MultiLineString 展开后 3 条线的坐标和属性全部保留 | 原生文件经当前 Reader 读出 2 条；差异需用 MapGIS 原生视图进一步区分转换行为与 Reader 重建行为 |

多边形 `equals_exact` 未作为通过条件，因为原生弧链可能改变环起点、方向和部件组织。除故意无效的 bowtie 外，其余用例均通过 Shapely 拓扑等价检查。

## 尚未判定为错误的事项

1. **WP class 与 fill_color 默认值不同。** 原生转换产生多种 class 和 fill_color，Writer 使用通用默认值。由于转换设置未知，未擅自按单批样本修改这些字段。
2. **原生文件 CRS 未被 Reader 识别。** 源 SHP 为 EPSG:4326，Writer 输出可回读为 WGS 84 经纬度；原生参考文件当前为 `crs=None`。该差异不被当作 Writer 缺陷。
3. **24 位环索引字段。** 所有 Writer 输出的 `field5/field6/field7` 均通过非负和 24 位范围检查。不同拓扑组织下的具体偏移值不强行要求与原生相同，仍需区参数截图或 MapGIS 原生打开进一步核验。
4. **MultiLineString 的记录数。** Writer 按公开设计展开并复制属性，当前 3 条结果不是数据丢失；原生参考只有 2 条，不能据此认定 Writer 错误。

## 后续原生验收建议

- 在 MapGIS 中打开 `writer_batch2_audit/` 内的 Writer 输出，重点检查 01、03、04、07、09 的区显示与区参数。
- 核对 11 的三条线是否全部可见，以及原生参考文件实际包含几条线。
- 在 MapGIS 中执行编辑和另存，再用 Reader 对另存文件做对照。
- 若需统一 WP 的 class/fill_color 默认值，应先记录 MapGIS 转换版本、设置和更多样本，不以本批单一设置替代通用规则。

## 可复核文件

- 测试：`tests/test_writer_native_batch2.py`
- 数据：`tests/fixtures/writer_batch2/`
- 清单：`tests/fixtures/writer_batch2_manifest.json`
- 审计脚本：`mapgis2shp_submission/audit_writer_shp_batch2.py`
- 机器可读结果：`writer_batch2_audit/writer_audit_report.json`
