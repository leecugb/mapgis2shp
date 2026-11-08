# pymapgis.Writer 第三批原生转换审计报告

## 范围

- 输入：12 组 SHP 与 MapGIS 原生转换文件，共 74 个文件、389,034 字节。
- 重点：24 位环索引高位字节、重复面、嵌套孔洞、UTM 投影、属性边界、空几何和退化环。
- 输出：独立目录 `writer_batch3_audit/`，未修改源目录。
- MapGIS 版本与转换设置未提供，不作推断。当前结果不替代 MapGIS 原生打开、编辑和另存验收。

## 最终验证

| 检查 | 结果 |
|---|---|
| 第三批原生用例 | 12 passed |
| 当前 wheel 的 JWD 与两批 Writer 回归 | 33 passed |
| 完整测试套件 | 366 passed, 0 skipped |
| Ruff | 全部通过 |
| Twine | wheel、sdist 均通过 |
| wheel 内容检查 | 184 entries，通过 |
| sdist 内容检查 | 219 entries，通过 |

`tests/fixtures/writer_batch3_manifest.json` 记录全部文件的来源、字节数和 SHA-256。

## 关键修复：UTM 坐标与元数据

初始 Writer 拒绝 `unsupported projection 'utm'`。仅增加 `utm → tmerc` 映射仍不足以保证正确性，因为 MapGIS 6x 不保存 UTM 的分带比例因子，直接把 UTM 坐标按 k=1 写出会改变实际地理位置。

当前处理逻辑为：

1. 从 UTM zone 计算中央经线，`zone 43 → 75°E`。
2. 将源坐标从 UTM 转换到 MapGIS 可表达的 Gauss-Kruger（k=1）坐标。
3. 使用同一中央经线和有效投影元数据写出。
4. 审计时再把输出回转到 EPSG:32643，以 1e-5 m Hausdorff 容差检查地理等价性。

UTM 用例现可通过。非投影用例仍使用严格拓扑比较，不共享该容差。

## 24 位环索引偏移

组合偏移按 `field5 + (field6 << 8) + (field7 << 16)` 计算。

| 用例 | Writer 组合偏移 | 原生组合偏移 | 结论 |
|---|---:|---:|---|
| 05_large_ring_over_64k | 81,634 | 81,634 | 高位字节一致，超过 65,535 |
| 06_large_then_small 第一面 | 80,098 | 80,098 | 一致 |
| 06_large_then_small 第二面 | 80,110 | 80,114 | 均超界；4 字节差异对应不同拓扑组织，不直接判错 |

所有输出的 `field5/6/7` 均通过非负和 24 位范围检查。具体偏移值仍建议用 MapGIS 区参数截图或原生打开进一步确认。

## 逐用例结论

| 用例 | 结果 |
|---|---|
| 01_reference_triangle | 最小参照环写入成功，属性与拓扑一致 |
| 02_identical_polygons | 两个完全相同的几何均保留，FID 1/2 未合并或去重 |
| 03_shared_edge_duplicate | 共边与重复点用例通过，两个面均保留 |
| 04_nested_hole_island | 孔洞和独立岛均保留，未重复计入岛面 |
| 05_large_ring_over_64k | 5001 点外环和 101 点孔洞均保留，24 位偏移与原生一致 |
| 06_large_then_small | 大小面均保留，后续指针同样超过 65,535 |
| 07_projected_utm | 修复后可写出；回转到 EPSG:32643 后地理等价 |
| 08_attribute_types | 长中文、空字符串、null、int32 极值、浮点和日期均与源 SHP 一致 |
| 09_null_geometry | 默认明确拒绝；`on_empty="drop"` 保留一个有效面及其属性 |
| 10_points | 中文属性、可空日期和坐标均保留，默认点样式一致 |
| 11_multiline | MultiLineString 展开后 3 条线及属性全部保留 |
| 12_degenerate_ring | 全同顶点环被明确拒绝，没有静默写出空面 |

08 的原生转换与源 SHP 存在浮点精度下降和空浮点值变 0 的现象，Writer 保留了源精度和 null。该差异未被当成 Writer 缺陷。

07 的原生 Reader 将共享边组织为 GeometryCollection，面积统计与源不同；Writer 保留源两个面的拓扑语义。

## 仍需原生验收

- 在 MapGIS 中打开 05、06 的 Writer 输出，核对 24 位环索引和区显示。
- 打开 07 的输出，确认高斯-克吕格坐标与中央经线设置符合预期。
- 核对 08 的长中文、空值和 int32 极值显示。
- 对 09、12 分别确认空几何和退化环的处理方式符合用户预期。
- 执行编辑和另存，再用 Reader 对另存结果做对照。

## 可复核文件

- 测试：`tests/test_writer_native_batch3.py`
- 数据：`tests/fixtures/writer_batch3/`
- 清单：`tests/fixtures/writer_batch3_manifest.json`
- 审计脚本：`mapgis2shp_submission/audit_writer_shp_batch2.py`
- 机器可读结果：`writer_batch3_audit/writer_audit_report.json`
