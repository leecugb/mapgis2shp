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

## Reader/Writer 原生审计、发行包与图件定稿（2026-11-09）

本节为当前状态，取代下文各阶段快照中的测试数、归档数和图件审计状态。

- Reader 审计使用 `F:\tmp` 的 36 个 MapGIS 二进制、原生明码与 SHP。36 个二进制均可读取；5 组原生 SHP 对照未发现需要修改 Reader 的缺陷。SHP 的自交面、空几何和部件组织差异没有被误判为 Reader 错误；`LDZOFBB004` 第 48 个空 SHP 面可由原生 WP 恢复。4 处 WAT 文本异常与二进制及 SHP 对照后确认不是 Reader 解码错误。可复现脚本和中文报告为 `audit_reader_native_tmp.py`、`reader_native_tmp_audit/`。
- `tests/fixtures/reader_native/` 含 16 个文件并配套 SHA-256 manifest；新增 `test_reader_native_exports.py` 8 项测试，覆盖点线几何、共享属性、CRS 边界、面有效性和缺失面恢复。
- Writer 第四批含 20 个 SHP 用例、18 个 MapGIS 原生转换结果及目录内 manifest，共 120 个文件。`test_writer_native_batch4.py` 28 项测试通过。原生 09 的错误面合并、07 的跨文件几何复用、06 的多部件丢失，以及量算错误、NaN/Inf/null 转 0 和 CRS 缺失均作为反例，不作为 Writer 应继承的行为。
- 新增 `test_writer_fixture_manifests.py` 5 项测试（含 batch2/3 参数化两项），逐文件核验 Writer batch2/3/4 和 Reader native 的字节数及 SHA-256；batch2/3 的文本条目同时保留原始 `bytes`/`sha256` 与 LF 规范化 `lf_bytes`/`lf_sha256`，避免 Git 换行策略造成跨平台误判，二进制仍严格按原始字节核验。batch4 还交叉核验根级与目录内 manifest 字节一致并锁定 120 个目录项，Reader native 锁定恰好 16 个目录项，防止额外文件随 force-include 混入。batch2/3/4 显式断言用例集合非空，避免空目录造成静默通过。
- wheel 内只将软件示例放在 `pymapgis/testing/examples/`，不占用通用顶层 `examples/` 命名空间。按用户要求，论文与 `mapgis2shp_submission/` 审计材料不进入 wheel 或 sdist；`validate_published_quickstart.py` 仅保留在仓库和稿件材料中，归档检查会拒绝任何投稿目录内容。
- 当前目标渲染、Reader 和 Writer 回归共 76 项，已在最终 wheel 安装态复跑为 **76 passed**（84.97 s）；同一 76 项也包含在源码完整套件中。完整套件在 Python 3.12.7、GeoPandas 1.1.3、Matplotlib 3.9.2 下复跑为 **420 passed, 1 environment-dependent skip**（52.76 s）。当前构建 wheel **323 项**、sdist **360 项**，均通过 `tests/inspect_dist.py`。
- `examples/render_bundled_jwd.py` 已加入 wheel/sdist；`validate_published_quickstart.py` 不进入发行包。最终 wheel 在独立 target 中实际安装并运行示例，得到 12 layers、7,094 features、5,732 drawn、713 polygon labels、1,362 excluded_text；未知色、未知填充、实线回退、未解决符号、空 pattern、循环上限和未知字体均为 0。
- 论文已从普通 `article` 迁移为 `elsarticle` frontmatter 和 SoftwareX 结构，包含 C1–C9、Illustrative examples、Impact 与 Conclusions。当前没有可用 LaTeX 编译器，因此只完成源码结构迁移，未声称编译通过；未将 404、AccessDenied 或 Cloudflare 页面当作官方模板。
- 架构图改为三列处理路径和 2×2 证据区，修正证据框越界、页脚碰撞及 Pcolor 文本触框。独立图件复核后，图内进一步改为明确 `420 passed · 1 environment-dependent skip`、`Public-release CI`，并将 57 个 explicit non-results 明确归于 Fillgrph。最终导出 PDF/PNG/SVG/TIFF，画布宽 182.9 mm，栅格 600 dpi，SVG 保留可编辑文本。
- 架构图最终源预检 **21 PASS, 0 WARN, 0 FAIL**；PDF 文本审计最小 6.8 pt；渲染碰撞审计 **0 FAIL, 0 WARN**；SVG 审计可执行且无 FAIL，仅保留标题大于 7 pt 的样式 WARN。最终 PNG 已逐区视觉检查。
- JWD 输出新增紧边界裁切，PNG 从 7200×4500 变为 4032×3489，去除大面积空白但不改变地图内容、原始注记位置或渲染 reports；论文内有效显示尺寸因此提高。
- 最终裁剪版 JWD 碰撞审计已完成并保存 JSON 与文本日志：**1,249 FAIL、1,059 WARN**，主要为原生注记与线划相交。该结果明确为 `FIX BEFORE DELIVERY`，没有声称通过；诊断 overlay 不作为交付图件。论文 Limitations 已明确保留 label–line-work overlaps。
- GitHub Actions 运行 `42503245112` 已复核：Windows/Python 3.13、macOS/Python 3.13 和 Ubuntu/Python 3.13 通过，Ubuntu/Python 3.9 因 `test_multi_part_offset_curves_are_supported` 错把 GEOS 版本相关的偏移返回类型当成固定行为而失败，构建任务因此被跳过。测试已改为显式构造两段 MultiLineString，保留多部件切片、部件数和总长断言，不增加跳过。
- 推送 `75c8fb8` 后的运行 `42569772303` 进一步暴露跨平台换行问题：四个环境均为 409 passed、10 skipped、2 failed，失败仅来自 batch2/3 `manifest.csv` 的 CRLF/LF 字节差异。manifest 已增加 LF 规范化字段且保留原始哈希，修复后的新远程 CI 仍待核验。
- 当前 JWD PDF 文本审计检出 1,597 个低于 5 pt 的文本运行，最小约 1.70079 pt。该图保留原始注记尺度，不通过放大字体或删注记伪装合规；论文继续要求用矢量 PDF/SVG 放大阅读，并将其列为图件限制。JWD 源预检为 18 PASS、3 WARN、0 FAIL，WARN 是未导出 TIFF、静态规则未识别栅格 DPI 和 304.8 mm 整图宽度。

## 第二轮复审与自动修复（2026-11-08）

- 一位独立复审完成，另外两位因 API 配额错误未能完成，未将其伪称为三份完整盲评。
- 针对发布版 Quickstart 阻断，采用向后兼容而非虚构新发布。`regression_layers()` 同时支持公开 V2.7.1 的 `.WP~` 与当前 `.WP`，并已实际从 PyPI 安装公开 2.7.1 运行成功。验证脚本为 `validate_published_quickstart.py`。
- 新增发布布局临时副本回归，不恢复 bundled `.WP~`；当前 fixture 仍全部使用标准 WP 文件名。
- 新增 `test_bundled_library_structural_census`，直接断言 Subgraph 7,360、LINESTY 859/984、Fillgrph 1,280/1,337、Colorlib 871 和 Pcolor 4,098。
- 完整测试数由 324 增至 326，targeted tests 由 8 增至 10。示例引导改为优先使用安装包，避免 wheel 验证被本地 `src` 覆盖。
- CI 表行明确为 pre-revision public release run；正文继续声明本轮没有新的远程 CI。
- Limitations 增加 dev-only GeoPandas `<1.2` 与 runtime `>=0.12` 的区别；README 新增 Unreleased 变更记录。
- C1–C3 不再要求通过发布新版才能运行中心示例。后续发布仍需同步新回归制品和旧 preferred-citation。

## 第二轮复审时的测试与图件证据（2026-11-08，阶段快照）

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
- 当时的 PDF 字体审计发现 605 个原生注记文本为 3.5 pt；当前最终 PDF 的重新审计结果见上节，旧数字不再代表最终文件。
- 当时碰撞审计尚未执行；2026-11-09 已安装 PyMuPDF 并补做，最终结果见上节。

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
- [x] 源码结构已迁移到 `elsarticle` / SoftwareX frontmatter；尚未声称完成编译或取得在线官方指南全文。
- [x] 将图 1 占位框替换为正式的软件架构图（`softwarex_architecture.pdf/.png`）。
- [x] 加入真实开源渲染输出图与 reports 判读（图 2 `jwd_map.pdf/.png/.svg`）。
- [ ] 如有条件，加入 MapGIS 原生输出与开源渲染的代表性对照图及差异分析。
- [ ] 复核全国地质资料馆条目级下载和再分发条款，必要时附书面确认。
- [ ] 确认数据与 SLIB 的许可说明不被误解为 Apache-2.0 或公共领域授权。
- [ ] 补充原生颜色锚的 MapGIS 版本、采集路径、截图或日志，以及英文证据摘要。
- [x] 历史性能数字明确标为 Reader 基准；脚本与 JSON/CSV 随稿件材料提供。
- [ ] 全体作者确认作者贡献、基金、致谢及版本描述。
- [x] 核实并引用现有 2.7.1 的 Zenodo 版本 DOI。
- [ ] 后续 Release/Zenodo 应纳入 WP 文件名规范化、新示例、Reader/Writer 原生审计 fixture、加强断言和当前 323/360 项归档内容，并同步 C1–C3。公开 V2.7.1 的中心 Quickstart 已通过兼容路径验证，不再依赖该发布动作才能复现；但发布件自身的旧 preferred-citation 与新回归制品仍待同步。
- [ ] 推送后运行更新后的 CI；论文只声称既有公开 Release 工作流成功，未虚构本轮远程运行。
- [x] 已安装 PyMuPDF 并完成碰撞审计。架构图通过；JWD 原生密集注记存在未清除的碰撞，已作为限制保留，不标记为通过生产版式验收。

## 文件

- 初稿：`paper_softwarex.tex`
- 前期 ESI 稿：`paper.tex`（保留，不覆盖）
- 架构图：`softwarex_architecture.pdf/.png/.svg`（另在本地导出 600 dpi TIFF）
- 实图：`jwd_map.pdf/.png/.svg`
- 实图报告：`jwd_render_reports.json`
- 图件审计：`softwarex_architecture.source-audit.json`、`.text-audit.json`、`.svg-audit.json`、`.collision-audit.json`，以及 `jwd_map.source-audit.json`、`.text-audit.json`、`.svg-structure-audit.json`、`.collision-audit.json`；文本与终端日志保留在本地审计工作区
- 公共示例：`../examples/render_bundled_jwd.py`
