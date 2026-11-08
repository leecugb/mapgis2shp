# SoftwareX 初稿说明与后续清单

## 主线与定位

- 主线：从封闭 MapGIS 二进制图件到可验证、可复现的开放制图栈。
- 故事类型：Trust / audit bridge，辅以 bottleneck-broken。
- 高潮：可运行的 bundled Quickstart、真实渲染输出与 reports 判读；历史 Reader 数字降为支撑证据。
- 目标期刊：SoftwareX。保留软件实现与复用价值，不沿用 ESI 对科学方法的过高叙述。

## 相比前期 ESI 稿件的主要更新

1. 版本基线为 mapgis2shp 2.7.1、发布提交 `823a5da`，并核实 `V2.7.1` Release 与 Zenodo DOI `10.5281/zenodo.24036158`。
2. 从 Reader 扩展为 Reader/Writer + 五类图形库解析 + 原生渲染。
3. 补充 Pcolor 32B 节点模型、LINESTY 双重 aux 语义和原线链长算法。
4. 将历史 36 层及 400 MB 原生导出验证明确标为历史 Reader 证据，并恢复 `d0d464d0` 的 `paper/validation/` 永久指针。
5. 加入当前 14 个颜色锚、25 个未知色号解决、37 条 38|2 的 782 个顶点零缺失。
6. 加入 12 层真实数据、5 个配套 SLIB、`pymapgis.testing`、wheel/sdist 数据包和 CI 证据。
7. 明确原生视觉验收、Fillgrph 非常规记录、透明输出、其他安装环境和 Writer 原生验收边界。
8. 数据来源改为公开发布的全国 1:25 万建造构造图空间数据库及其配套 SLIB，并注明非涉密资料与服务条款。
9. 新增可执行 `examples/render_bundled_jwd.py`，输出 PNG/PDF/SVG 与 `jwd_render_reports.json`，论文图 2 使用真实输出。
10. Availability 改为 C1–C9 元数据表，CITATION.cff 的版本、标题和 DOI 已同步。

## 第二轮复审与自动修复（2026-11-08）

- 一位独立复审完成，另外两位因 API 配额错误未能完成，未将其伪称为三份完整盲评。
- 针对发布版 Quickstart 阻断，采用向后兼容而非虚构新发布。`regression_layers()` 同时支持公开 V2.7.1 的 `.WP~` 与当前 `.WP`，并已实际从 PyPI 安装公开 2.7.1 运行成功。验证脚本为 `validate_published_quickstart.py`。
- 新增发布布局临时副本回归，不恢复 bundled `.WP~`；当前 fixture 仍全部使用标准 WP 文件名。
- 新增 `test_bundled_library_structural_census`，直接断言 Subgraph 7,360、LINESTY 859/984、Fillgrph 1,280/1,337、Colorlib 871 和 Pcolor 4,098。
- 完整测试数由 324 增至 326，targeted tests 由 8 增至 10。示例引导改为优先使用安装包，避免 wheel 验证被本地 `src` 覆盖。
- CI 表行明确为 pre-revision public release run；正文继续声明本轮没有新的远程 CI。
- Limitations 增加 dev-only GeoPandas `<1.2` 与 runtime `>=0.12` 的区别；README 新增 Unreleased 变更记录。
- C1–C3 不再要求通过发布新版才能运行中心示例。后续发布仍需同步新回归制品和旧 preferred-citation。

## 本轮测试与图件证据

- bundled JWD 中两个 `.WP~` 已按用户要求改为同名 `.WP`，目标文件此前不存在；两个字节数和 SHA-256 均未改变。测试目录只有这 2 个备份，未处理工作区其他历史文件。
- `tests/test_graphic_real_jwd.py` 与论文共用 `regression_layers()` 兼容路径。规范化 WP 直接传入，发布版 `.WP~` 由 Reader 预读为 GeoDataFrame。
- 38|2 测试现在显式断言 37 个要素、782 个源顶点、`max_deviation <= 1e-9`，保留逐顶点检查并允许平台浮点舍入误差。
- 新增 `drawn + excluded_text == 7094` 断言，支撑图注中的 5,732 + 1,362 = 7,094。
- 源码与当前 wheel 安装态各运行 10 个 targeted tests，均为 10 passed。另从 PyPI 下载公开发布的 2.7.1，在独立 target 目录中实际运行兼容 Quickstart，确认其原始 `.WP~` fixture 得到 7,094/5,732/1,362 且全部未解决项为零。
- 完整套件在 Python 3.12.7、GeoPandas 1.1.1、Matplotlib 3.11.2 下为 **326 passed, 0 skipped**；运行时需将虚拟环境 `Scripts` 放入 PATH，使 console-script 测试能发现 `pymapgis`。
- GeoPandas 1.2.0 下，可选旧模块 `pymapgis.rendering` 的像素对照出现底部边缘差异，最大通道差 255、变化比例 0.569%；公共 original-library JWD 回归在 1.2.0 下也通过。`dev` extra 暂时限制 `geopandas<1.2`，普通运行依赖未加该上限。
- 新构建 `dist_softwarex/`：wheel 40 项、sdist 73 项，`tests/inspect_dist.py` 全部通过。旧 `dist/` 未修改。
- 实图 reports：12 layers、7,094 features、5,732 drawn、713 polygon labels、1,362 excluded_text；未知色、未知填充、实线回退、未解决符号和未知字体均为 0。
- 图件源预检为 18 PASS、3 WARN、0 FAIL。WARN 为未输出 TIFF、DPI 静态规则未识别和图幅宽度；论文采用 PDF/SVG 矢量输出及 600 dpi PNG。
- PDF 字体审计发现 605 个原生注记文本为 3.5 pt，低于 Nature 风格常用的 5 pt 建议。未为通过检查而放大原生注记，论文 Limitations 已建议使用矢量图放大阅读。
- 碰撞审计尚未执行，因当前环境缺少 PyMuPDF，而安装该额外外部包需要用户明确授权。

## Writer 原生 SHP 转换审计（2026-11-08）

- 用户提供 11 组 SHP 与 MapGIS 原生转换结果，共 68 个文件、57,301 字节，已纳入 `tests/fixtures/writer_batch2/`；`writer_batch2_manifest.json` 记录来源和 SHA-256，MapGIS 版本及转换设置标为未提供。
- 新增 `tests/test_writer_native_batch2.py`，覆盖最小环、孔洞、多部件、共享边、重复点、无效 bowtie、可空日期和 MultiLineString。原生用例 11 passed。
- 修复独立 WT/WL 默认值：WT height/width=0.1 mm、color=6、pen_width=0.1 mm；WL width=0.05 mm、x/y_coef=1.0、aux_flag=1。显式参数仍优先。
- WP 的 class/fill_color 未按单批样本强行对齐，转换设置仍需更多证据。field5/6/7 做非负与 24 位范围检查，不替代原生打开验收。
- 当前 wheel 的 JWD 与原生 Writer 回归合计 21 passed；完整套件为 **352 passed, 0 skipped**。wheel 为 109 项，sdist 为 143 项，Ruff、Twine 和归档检查全部通过。
- 中文审计报告为 `writer_batch2_audit/writer_native_audit_zh.md`，机器可读结果为 `writer_audit_report.json`。原生打开、编辑和另存验收仍单独待做。

## Writer 第三批边界审计（2026-11-08）

- 第三批 12 组 SHP 与原生转换结果共 74 个文件、389,034 字节，已纳入 `tests/fixtures/writer_batch3/` 和独立 manifest。
- 新增 `tests/test_writer_native_batch3.py`，覆盖 24 位组合偏移、重复面、UTM、长中文、空值、空几何和退化环，12 passed。
- 修复 UTM 支持：不再仅做 `utm → tmerc` 名称映射，而是先转换为 MapGIS 可表达的 Gauss-Kruger（k=1）坐标并写入正确中央经线。审计回转 EPSG:32643 后使用 1e-5 m Hausdorff 容差。
- 05 的组合偏移为 81,634，与原生一致；06 两个面均超过 65,535，偏移差异与拓扑组织分开解释。
- 空几何默认拒绝，`on_empty="drop"` 保留有效面；全同顶点退化环明确拒绝，未生成空面。
- 08 的长中文、null、int32 极值、浮点和日期均与源 SHP 一致。原生转换存在浮点精度下降和空浮点值变 0，未据此要求 Writer 降级。
- 当前 wheel 的 JWD 与两批 Writer 回归合计 33 passed；完整套件 **366 passed, 0 skipped**。wheel 184 项，sdist 219 项，Ruff、Twine 和归档检查全部通过。
- 中文报告为 `writer_batch3_audit/writer_native_audit_zh.md`。UTM 投影显示、环索引及异常输入的原生打开、编辑和另存验收仍待做。
- CI 失败复核发现远端上传改变了 `LDLYAAE002.WP` 与 `LDZOFBB003.WP` 的原生 pattern 参数。经用户确认，已从原始提交恢复两份文件，保留原始 12 层回归语义；manifest 哈希和 pattern=165 均已恢复。38|2 容差统一为 `<=1e-9`，不把平台浮点舍入误写为绝对零。

## Reader/Writer 综合回归（2026-11-08）

- `verify_pymapgis.py` 的 36 个真实文件全部读取成功，invalid geometry 为 0。
- `verify_pymapgis.py --roundtrip` 的 36 个 Reader → Writer → Reader 往返全部成功，面文件 `area_rel_diff=0.00e+00`。
- 原生拓扑抽查确认 Reader 按左右面 ID 重建多部件几何。`02_two_sizes` 的第二条弧同时属于面 1 和面 2，因此 Reader 的多部件结果不是无依据复制，未修改这部分实现。
- 中文字段名 `面积`、`周长` 的原始 GBK 描述符与解码结果一致，控制台显示乱码不构成 Reader 解码缺陷。
- UTM 写出语义已在 README 明确：先转换为 Gauss-Kruger（k=1）和正确中央经线，比较时再回转原 UTM CRS。CI 已在 Windows、Ubuntu、macOS 和发行构建中全部通过。

## 投稿前待办

- [ ] 用 LaTeX 编译并检查版式（本机尚未安装 pdflatex）。
- [ ] 迁移到 SoftwareX 官方 Word/LaTeX 模板；当前仍为普通 `article`，但已补 C1–C9 表。
- [x] 将图 1 占位框替换为正式的软件架构图（`softwarex_architecture.pdf/.png`）。
- [x] 加入真实开源渲染输出图与 reports 判读（图 2 `jwd_map.pdf/.png/.svg`）。
- [ ] 如有条件，加入 MapGIS 原生输出与开源渲染的代表性对照图及差异分析。
- [ ] 复核全国地质资料馆条目级下载和再分发条款，必要时附书面确认。
- [ ] 确认数据与 SLIB 的许可说明不被误解为 Apache-2.0 或公共领域授权。
- [ ] 补充原生颜色锚的 MapGIS 版本、采集路径、截图或日志，以及英文证据摘要。
- [x] 历史性能数字明确标为 Reader 基准；脚本与 JSON/CSV 随稿件材料提供。
- [ ] 全体作者确认作者贡献、基金、致谢及版本描述。
- [x] 核实并引用现有 2.7.1 的 Zenodo 版本 DOI。
- [ ] 后续 Release/Zenodo 应纳入 WP 文件名规范化、新示例、加强断言和 sdist 第 73 项，并同步 C1–C3。公开 V2.7.1 的中心 Quickstart 已通过兼容路径验证，不再依赖该发布动作才能复现；但发布件自身的旧 preferred-citation 与新回归制品仍待同步。
- [ ] 推送后运行更新后的 CI；论文只声称既有公开 Release 工作流成功，未虚构本轮远程运行。
- [ ] 如需完成 collision QA，先获得安装 PyMuPDF 的明确授权，再运行碰撞审计并处理或解释警告。

## 文件

- 初稿：`paper_softwarex.tex`
- 前期 ESI 稿：`paper.tex`（保留，不覆盖）
- 架构图：`softwarex_architecture.pdf/.png`
- 实图：`jwd_map.pdf/.png/.svg`
- 实图报告：`jwd_render_reports.json`
- 公共示例：`../examples/render_bundled_jwd.py`
