# JWD / SLIB 数据来源与引用说明

## 当前使用原则

自 **2026-11-08** 起，本项目停止生成新的 JWD 坐标扰动、虚拟地层单元或其他衍生仿真版本。后续测试、示例和论文图件以**开放版原始 JWD 矢量及配套 SLIB 图形库**为准，并加强来源引用。

历史仿真目录仅作为过程记录保留，不作为当前推荐数据、回归母本或发布依据。基本 Reader/Writer 单元测试夹具与上述 JWD 衍生仿真不同，仍按其各自 manifest 使用。

## 原始数据集

- **名称**：《中国陆域1∶25万分幅建造构造图空间数据库》（V1）
- **英文名称**：Spatial database of serial suite-tectonic map-sheets of mainland China (1:250,000) (V1)
- **生产者**：中国地质调查局发展研究中心
- **分发者**：全国地质资料馆（National Geological Archives of China）
- **发布日期**：2018-09-10
- **数据集 DOI**：<https://doi.org/10.23650/data.A.2018.NGA131703.K1.1.1.V1>
- **数据服务系统**：<http://dcc.cgs.gov.cn>
- **本测试使用范围**：库尔干幅 **J43C001002** 的12个 WT/WL/WP 图层及同一数据包配套 SLIB，不是完整图幅。

数据集包含729个1∶25万分幅，采用 MapGIS 6.7 格式。原始数据使用北京54坐标系和1956年黄海高程基准，后续科研使用时需另行评估坐标及高程基准转换。

## 配套 SLIB

测试使用以下5个与原始数据包配套的图形库：

- `Subgraph.lib`
- `LINESTY.lib`
- `Fillgrph.lib`
- `Colorlib.lib`
- `Pcolor.lib`

SLIB 是原始图形解释和渲染回归的一部分，不能用其他 MapGIS 安装目录中的异名库替代。JWD 与 SLIB 的文件级字节数和 SHA-256 见 `tests/fixtures/jwd_slib_manifest.json`。

自 **2026-11-13** 起，用户明确提供 `D:/SLIB/SLIB` 作为**通用图形库**随包分发。该目录只包含符号、线型、填充图案和颜色定义，不包含地质空间对象、坐标、图幅或地质单元。相同的五个库文件现内置在 `tests/fixtures/slib/` 和 wheel 的 `pymapgis/testing/fixtures/slib/`，清单见该目录 `manifest.json`；`PYMAPGIS_SLIB` 仍可用于覆盖为另一套明确指定的本地库。

## 推荐引用

### 中文

左群强、叶天竺、冯艳丽、葛佐、王杨刚，2018. 中国陆域1∶25万分幅建造构造图空间数据库（V1）[数据集]. 中国地质调查局发展研究中心［生产者］，2006；全国地质资料馆［分发者］，2018-09-10. DOI: 10.23650/data.A.2018.NGA131703.K1.1.1.V1. 本研究使用其中库尔干幅（J43C001002）部分图层及配套 SLIB，仅用于软件测试与验证.

左群强、叶天竺、冯艳丽、葛佐、王杨刚，2018. 中国陆域1∶25万分幅建造构造图空间数据库[J]. 中国地质, 45(S1): 1–26. DOI: 10.12029/gc2018Z101.

### English

Zuo, Q., Ye, T., Feng, Y., Ge, Z., and Wang, Y. (2018). *Spatial database of serial suite-tectonic map-sheets of mainland China (1:250,000)* (V1) [Data set]. Development and Research Center of China Geological Survey [producer], 2006; National Geological Archives of China [distributor], 2018-09-10. https://doi.org/10.23650/data.A.2018.NGA131703.K1.1.1.V1. This work uses selected layers from sheet J43C001002 and the accompanying SLIB solely for software testing and validation.

Zuo, Q., Ye, T., Feng, Y., Ge, Z., and Wang, Y. (2018). Spatial database of serial suite-tectonic map-sheets of mainland China (1:250,000). *Geology in China*, 45(S1), 1–26. https://doi.org/10.12029/gc2018Z101

## 图件与报告署名建议

使用原始 JWD/SLIB 生成图件、测试报告或论文插图时，建议在图注或数据可用性声明中写明：

> 数据来源于《中国陆域1∶25万分幅建造构造图空间数据库》（V1）库尔干幅（J43C001002）部分图层及其配套 SLIB，由全国地质资料馆分发，DOI: 10.23650/data.A.2018.NGA131703.K1.1.1.V1。仅用于软件测试与验证。

软件自身的 Apache-2.0 许可证不覆盖原始 JWD 或 SLIB。引用软件与引用数据集应分别进行，不能只引用软件而省略数据来源。

## 使用与再分发边界

“公开版”“非涉密”和“仅作测试”说明数据获取属性及本项目用途，但**不自动等同于公共领域授权或允许任意再分发**。全国地质资料馆服务条款及条目级下载约定仍然适用于**原始 JWD 矢量**。通用 SLIB 的内置则依据用户于 2026-11-13 提供的明确打包授权，并保留来源说明。

- 不把裁切、改名、坐标变换或仅用于测试解释为许可豁免。
- 不以 Apache-2.0、CC0 或其他软件许可证重新许可原始 JWD/SLIB。
- 如期刊、归档或公开发布需要明确的再分发授权，应取得条目级条款或全国地质资料馆的书面确认。
- 无法确认原始 JWD 矢量的再分发条件时，使用者应通过数据服务系统自行获取，并用 `PYMAPGIS_JWD` 指向本地目录运行测试。通用 SLIB 已内置，亦可用 `PYMAPGIS_SLIB` 显式覆盖。

本引用说明用于加强来源透明性，不构成对授权状态的替代判断。

## USGS Conejo Well 转换示例

`examples/convert_usgs_conejo.py` 使用真实的美国地质调查局数据，而非 JWD
衍生仿真：

- Powell, Robert E., and Cossette, Pamela M. (digital cartography), 2001.
  *Geologic map and digital database of the Conejo Well 7.5 minute quadrangle,
  Riverside County, California*, Version 1.0. U.S. Geological Survey Open-File
  Report 01-031. <https://pubs.usgs.gov/of/2001/of01-031/>
- 原始发布形式为 ARC/INFO E00 coverage、PDF 图件和元数据。示例直接读取
  ARC/PAL/LAB/IFO，保留转换图层的源属性，并在输出目录记录输入 SHA-256。
- 元数据声明 `Access_Constraints: None`，同时保留 USGS 的“按现状”免责、
  数据修订权及空间分辨率限制。DOQQ 地质数据不得通过放大冒充超过
  1:12,000 的场地级资料；1:24,000 地形底图和断层评价限制同样适用。
- 自 **2026-11-10** 起，原始 E00、元数据和 `usgs_conejo` 下的六个原生转换 MapGIS 文件作为 USGS 转换器的历史对照纳入 `tests/fixtures/usgs_conejo/`。自 **2026-11-13** 起，另将用户基于 public-domain USGS 数据加工的 **7 个测试文件**纳入 `tests/fixtures/testdata/` 及 wheel。后者按中国陆域1∶25万分幅建造构造图空间数据库的属性结构组织，并使用 SLIB 样式编码，保留用户更新的颜色与 Fillgrph 参数。用户已明确确认这 7 个文件**无知识产权风险并具备随包分发条件**。原生六层不作为 clean 标准测试包的必需内容，也不与加工后的七层混称为同一显示版本。
- 转换图的时代配色和 MapGIS 点符号是明确声明的转换样式，不冒充 USGS 原图
  色或逐符号等效复刻。完整原始代号、shade 字段和符号编号予以保留。
  `PLABL` 的 `<` 与 `^` 是 GeoAge 字体控制字符；普通文本显示使用完整
  `LABL`，避免把 Proterozoic `Pr` 或 Triassic `Tr` 错显为控制字符。
