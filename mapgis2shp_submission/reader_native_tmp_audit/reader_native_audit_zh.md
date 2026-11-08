# mapgis2shp Reader 原生转换对照审计报告

## 1. 审计范围与结论

审计输入为 **F:\tmp\** 中的 MapGIS 二进制文件、MapGIS 软件生成的明码文件（`.wat/.wal/.wap`）及对应 SHP。

结论：**未发现需要修改 Reader 的缺陷，本轮不修改生产代码。**

- 36个 MapGIS 二进制文件均由 Reader 成功读取，解析异常为0，原生几何无效数为0。
- 5组完整的二进制、明码和 SHP 对照中，明码坐标、弧段拓扑、原生线型及 SHP 属性均未发现 Reader 错误。
- Polygon/MultiPolygon 类型与部件数差异属于原生导出组织差异，不能据此要求 Reader 改成 SHP 的表现形式。
- `LDZOFBB004.SHP` 的一个空几何属于 SHP 导出信息丢失，Reader 能恢复有效面。
- 4处 WAT 文本差异中，二进制属性与 SHP 一致，差异只存在于 MapGIS 明码导出结果中，不是 Reader 解码错误。

## 2. 逐组结果

| 对照组 | 原生规模 | 明码几何/拓扑 | 原生图形参数 | SHP 属性 | 需要说明的差异 |
|---|---:|---|---|---|---|
| LDLYAAI002 | 242点 | 0差异 | 0差异 | 0 / 1,694 | 16列文本点格式核验通过 |
| LDZOFBA002 | 2,222线 | 0差异 | 0差异 | 0 / 13,332 | 坐标、长度、线型及属性一致 |
| LDZOFBB001 | 608面、2,036弧段 | 0差异 | 0差异 | 0 / 9,728 | 586个表示差异；SHP 有87个无效面 |
| LDZOFBB004 | 49面、315弧段 | 0差异 | 0差异 | 0 / 1,127 | 48个表示差异；SHP 有1个空几何和14个非空自交面 |
| LDZOFBB099 | 2,024点 | 坐标0差异 | 除4处文本外为0 | 0 / 10,120 | 13列子图点与16列文本点分别核验 |

坐标比较容差为 `5.1×10⁻⁷`，用于容纳明码六位小数及 SHP/DBF 数值显示精度。属性比较将空字符串和空值统一处理，不将原生转换中的空值语义差异误判为 Reader 错误。

## 3. Polygon 表示差异不是几何丢失

`LDZOFBB001` 中，Reader 输出以 MultiPolygon 为主，而 SHP 多数输出 Polygon；`LDZOFBB004` 也存在同类差异。

关键证据：

- 两组 SHP 对照的几何 Hausdorff 距离均未超过阈值，绝大多数为0。
- Reader 的几何有效性检查均为0个无效面。
- `LDZOFBB001.SHP` 有87个无效面，其中73个为自交、14个为嵌套壳。
- `LDZOFBB004.SHP` 另有14个非空自交面。

这表明 MapGIS SHP 导出时的面部件合并方式会改变类型和部件组织，并可能产生自交。若仅为了让 Reader 类型与 SHP 一致而强行合并多边形，反而可能破坏几何有效性。因此不建议修改 Reader 的多边形重建逻辑。

## 4. SHP 空几何记录

`LDZOFBB004.SHP` 的第48行（从0计数）几何为空：

- `ID=833`
- `CHFCAC=000049`
- 单元为赛图拉岩群（`ChSt`）
- Reader 能恢复一个有效 Polygon，面积约为 `3.583744×10⁻⁵`（原坐标单位平方）

因此该空几何是原生 SHP 导出信息丢失，不是 Reader 漏读。

## 5. 四处 WAT 文本差异的字节证据

差异均位于 `LDZOFBB099.WT` 的 `CHFCED` 字段：

| 行号（从0计数） | 二进制属性字节及解码 | SHP | MapGIS 明码 WAT | 判定 |
|---:|---|---|---|---|
| 988 | `44` → `D` | `D` | `D#-1` | 二进制与 SHP 一致，WAT 不同 |
| 989 | `a6c9` → `ι` | `ι` | `O` | 二进制与 SHP 一致，WAT 不同 |
| 991 | `44` → `D` | `D` | `D#-1` | 二进制与 SHP 一致，WAT 不同 |
| 992 | `a6c9` → `ι` | `ι` | `O` | 二进制与 SHP 一致，WAT 不同 |

Reader 按原字段字节正确解码，SHP 也保留了相同值。不能用这4行 WAT 文本反推 Reader 应返回 `D#-1` 或 `O`。

## 6. WAP 弧段及尾部记录

`LDZOFBB001.wap` 的2,036个弧段和 `LDZOFBB004.wap` 的315个弧段均与 Reader 的原生弧段一致，左右面拓扑和线型也一致。

两份 WAP 在声明的弧段序列之后还包含节点或其他记录：

- `LDZOFBB001.wap`：24,683行尾部记录；
- `LDZOFBB004.wap`：2,056行尾部记录。

这些记录不属于声明的弧段序列，不是 Reader 构建面要素所缺失的弧段，不应计为 Reader 漏读。

## 7. 坐标系边界

5组 SHP 均未附带 `.prj`，因此 SHP 的 CRS 为 `None`，不能用 SHP 侧文件证明坐标系。Reader 从 MapGIS 二进制头识别为经纬度坐标及相应椭球参数；坐标值与明码、SHP 一致。

本审计没有把“坐标数值一致”误写为“SHP 已验证 CRS”。

## 8. 建议

1. 不修改 Reader 生产代码。
2. 不以 SHP 的 Polygon/MultiPolygon 类型或部件数作为唯一真值，应同时检查几何覆盖和有效性。
3. 将 `LDZOFBB004.SHP` 第48行登记为原生 SHP 导出空几何案例，而非 Reader 缺陷。
4. 将4处 WAT 文本差异登记为 MapGIS 明码与二进制/SHP 不一致案例。
5. 如需进一步验收，应增加 MapGIS 原生软件中的显示、编辑和另存对照，而不是仅凭内部回归推断原生视觉一致性。

## 9. 可复现材料

- 审计脚本：`mapgis2shp_submission/audit_reader_native_tmp.py`
- 机器可读结果：`mapgis2shp_submission/reader_native_tmp_audit/reader_native_audit.json`
- 本报告：`mapgis2shp_submission/reader_native_tmp_audit/reader_native_audit_zh.md`

审计脚本已通过 Ruff 检查。输入数据仍保留在原目录，未新增到发行包。
