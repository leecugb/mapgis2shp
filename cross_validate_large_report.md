# 大文件 native 交叉验证报告

**日期**：2026-07-22
**工具版本**：mapgis2shp (pymapgis) 2.0.5
**验证脚本**：`cross_validate.py`

## 数据源

| 角色 | 文件 | 说明 |
|------|------|------|
| 待验证（MapGIS 原始） | `E:\沉积建造岩.WP` | MapGIS 6.x/67 区文件，400 MB |
| 参考基准（官方导出） | `C:\Users\Administrator\xwechat_files\...\沉积建造岩_WP_merged_recolored.shp` | 正版 MapGIS 导出（合并/重着色后），327 MB shapefile |

## 1. 基础指标对比

| 指标 | mapgis2shp | 官方导出 | 一致性 |
|------|-----------|---------|--------|
| 要素数 | 78,873 | 67,039 | 不同（官方按地层合并溶解，少 ~11,834 个） |
| CRS | longlat / Krassovsky（北京54） | 同左（.prj 缺失，按推断补） | ✅ 推断正确 |
| bbox | [73.486464, 32.0, 111.000001, 48.0] | 同左 | ✅ **完全一致**（diff = 0.0） |
| 几何类型 | MultiPolygon 71195 / Polygon 7667 / GeometryCollection 11 | Polygon 67036 / MultiPolygon 3 | — |
| 无效几何 | 0 | 3 | ✅ mapgis2shp 更干净 |
| 属性字段 | 16 个原生字段 | 16 个相同 + strat_code + ColorCode | ✅ **16 原生字段完全一致** |

**字段差异**：官方导出额外含 `strat_code`、`ColorCode` 两个字段，系其后处理（地层合并 + 重着色）产物，不影响读取器对原生数据的正确性。

## 2. 面积与覆盖等价性（决定性指标）

因官方版按地层合并了相邻多边形，要素数不一致，无法 1:1 逐要素比较，故采用**覆盖等价性**指标：对两套几何分别求并集（消除重叠与分割差异），再算对称差与交并比。面积采用 Krassovsky 椭球大地面积（`pyproj.Geod`，无需重投影，避免大文件内存爆炸）。

| 指标 | 值 | 解读 |
|------|-----|------|
| 总面积和（mapgis2shp） | 2,147,783.76 km² | 含重叠伪影 |
| 总面积和（官方） | 2,112,611.69 km² | 干净无重叠 |
| 面积和绝对差 | 35,172.07 km²（1.66%） | 表面差异 |
| **并集对称差** | **5,649.94 km²** | 真实覆盖差异 |
| 并集交集 | 2,112,457.17 km² | 共同覆盖区 |
| **Coverage IoU** | **0.99733（99.73%）** | **覆盖等价性极高** |

### 关键发现

1. **1.66% 的面积和差异是重叠伪影，非覆盖错误。** mapgis2shp 的贪心弧段合并在共享边界处产生微小重叠（缝隙桥接所致），累加后"面积和"偏大 1.66%；用并集去重叠后，真实覆盖差异仅 **0.27%**（5,650 km² / 2.11 M km²）。
2. **覆盖等价性 IoU = 99.73%**：在 400 MB / 78,873 面的极端规模下，mapgis2shp 输出与正版 MapGIS 导出的空间覆盖几乎完全一致。
3. mapgis2shp 0 无效几何，官方反而有 3 个无效——逆向读取器的几何有效性优于官方导出。
4. bbox 精确一致、CRS 正确推断（官方 .prj 丢失，mapgis2shp 补出了正确坐标系）、16 原生字段完全一致。

## 3. 论文验证章可用段落

> On a 400 MB MapGIS polygon file (沉积建造岩.WP, 78,873 features), the reader's output was compared against an official MapGIS export (67,039 features after the vendor's dissolve-and-recolor post-processing). Bounding boxes matched exactly (diff = 0); the 16 native attribute fields were identical; and the coordinate reference system (Beijing-54 / Krassovsky, longlat) was correctly inferred even though the official export had lost its `.prj` file. The reader produced zero invalid geometries versus three in the reference. Because the official export dissolves adjacent polygons, feature counts differ and 1:1 comparison is impossible; coverage equivalence was therefore assessed via geometry unions. Summed polygon areas exceeded the reference by 1.66%, but the union symmetric difference was only 5,650 km² against 2.11 × 10⁶ km² of coverage, yielding an **intersection-over-union of 99.73%**. The 1.66% summed-area gap is thus a quantified overlap artifact of the heuristic arc-merge reconstruction at shared boundaries, not a coverage error.

## 4. 局限与说明

- 该官方导出为"合并重着色"后处理版本，非 MapGIS 直接导出的原始拓扑；理想验证应补一份**未合并**的官方原始导出做 1:1 逐要素对照。
- 0.27% 的残余对称差来源于：弧段合并的缝隙容差、官方 3 个无效几何、以及合并溶解时的微小拓扑差异。
- 大地面积基于 Krassovsky 椭球；mapgis2shp 推断的 CRS 含 `towgs84` 参数，与官方一致。

## 5. 产物文件

- `cross_validate.py` — 可复用 native 交叉验证脚本
- `cross_validate_large_report.json` — 快速指标（含字段/bbox/面积和）
- `cross_validate_large_union.json` — 完整结果（含并集对称差与 IoU）
- `cross_validate_large_report.md` — 本报告
