# 第四批 Writer 原生转换 SHP 用例

本批聚焦几何、属性、拓扑和原生默认参数，不以坐标系覆盖为目标。全部用例使用高斯-克吕格中央经线75°E、k=1、东偏500000m、单位米。

## 请转换

请使用 MapGIS 原生软件将本目录中的 SHP 转为对应 WT/WL/WP，保持原文件名，输出到 `mapgis_native/`。不要使用 pymapgis.Writer 生成对照文件。

同时请尽量提供：

1. MapGIS 版本和构建号；
2. 转换界面设置或截图，特别是投影、编码、空几何及默认图形参数；
3. 转换失败日志（空文件、空几何、退化环等不得静默跳过）；
4. 如方便，同时导出对应 WAT/WAL/WAP 明码文件。

## 用例

| 用例 | 要素数 | 审计重点 |
|---|---:|---|
| 01_POINT_BASIC | 2 | 基本点、中文名称和浮点属性 |
| 02_POINT_ATTR_NULL | 3 | 空值、int32极值、非有限浮点和控制符 |
| 03_POINT_MULTIPOINT | 2 | MultiPoint与单点混合 |
| 04_POINT_257 | 257 | 超过255条记录的属性与坐标对齐 |
| 05_LINE_BASIC | 2 | 基本折线与中文属性 |
| 06_LINE_MULTI_DUPLICATE | 2 | 连续重复点和MultiLineString |
| 07_LINE_EMPTY | 3 | 正常线、null和空线混合 |
| 08_LINE_10001_VERTICES | 1 | 一万零一个线顶点及大坐标段 |
| 09_POLY_BASIC | 2 | 最小三角形和矩形 |
| 10_POLY_HOLE_MULTIPART | 1 | 双孔、多部件和独立三角面 |
| 11_POLY_SHARED_ISLAND | 4 | 共边、孔洞与边界完全一致的独立岛 |
| 12_POLY_DUPLICATE_VERTICES | 1 | 连续及非连续重复环顶点 |
| 13_POLY_BOWTIE | 1 | 自交蝴蝶结无效面 |
| 14_POLY_DEGENERATE | 1 | 全部顶点相同的退化环 |
| 15_POLY_EMPTY | 3 | 正常面、null和空面混合 |
| 16_POLY_80_FIELDS | 3 | 80个附加字段及中文字段 |
| 17_POLY_LARGE_RING | 1 | 5001点外环和101点孔洞 |
| 18_POLY_DUPLICATE_ATTRIBUTES | 2 | 相同几何、不同属性及原生参数归属 |
| 19_POLY_LONG_TEXT | 1 | 长中文、控制码与属性宽度 |
| 20_EMPTY_FILE | 0 | 零要素文件及几何类型显式处理 |

空值、无效几何和不支持类型的预期行为不预设为成功；请保留 MapGIS 的实际成功、失败或跳过结果，以便与 Writer 的显式错误处理比较。
