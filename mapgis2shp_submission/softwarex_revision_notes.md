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

# Nature-writing 复审优化（2026-11-10）

- 按 trust/audit bridge 重排 Motivation，先说明可检验、非厂商替代的实现原则，再交代版本历史。摘要历史 Reader 结果补入 99.9995% 平均属性等值率和 99.73% coverage IoU 两个锚点，并将可用性声明移到验证证据之后。
- 摘要、图 2 和验证表统一为五类零未解决项，即 colours、fills、fallbacks、symbols、fonts；不删除 5,732/1,362/7,094 这组必要账本。Impact 新增明确用户群，图 2 图注补出 Kurgan 图幅号。
- C2 同时保留 manifest 生成点 `f9ca6a66` 与最终验证及官方 LaTeX 构建点 `fe12768`，C3 明确脚本位于 `fe12768`。CI 表更新为全部成功的 `42634593828`。
- 删除当前版本未获七位作者确认时的批准句，保留标准 CRediT 角色。作者确认仍按外部签署流程处理，不用文字代替批准。
- 将外部 fixture 与再分发边界移到 Validation and reproducibility 下的独立小节，首次使用处解释 `A|B` 线型记号，区分 write-back 与 historical native-export 两类分析，并完成若干动词、长句和表意不清修正。
- 最终摘要 **200 词**，全文估算 **3,049 词**，满足官方 250/4,000 词限制。使用官方 elsarticle 3.4 编译后无未解析引用或 LaTeX 错误，首页摘要与通讯作者页脚不再重叠；排版日志仍有非零 overfull/underfull 警告。
- 本轮不关闭外部事项：七位作者实际确认、14 个原生色锚截图或日志、历史数据副本许可或清理仍分别按既有计划处理。

## 四闸门处置与外部 fixture 迁移（2026-11-09）

本节记录当前执行状态，不能据此声称四个闸门已全部关闭。

### 模板与编译

- 用户已明确授权运行 Tectonic 官方 GitHub `tectonic-typesetting/tectonic` 的 `tectonic@0.17.0` Windows release。下载 ZIP 为 21,060,223 字节，SHA-256 `f61ce51f0b0ade1015b7de7ef368541c5424e9756ecbd0d7af97d6d48030845f`。
- 用户提供的 `elsarticle.zip` 为真实 Elsevier 官方类包，SHA-256 `0b093093e84db49f99bcc9a7c3f69ed1fb61b0147c6d296427aff7963e7f50f6`。已从 DTX 的 class 区段确定性提取 `elsarticle.cls`，最终编译日志明确为 **Document Class: elsarticle 2024/04/04, 3.4**，并成功生成 PDF。
- 已按 LaTeX 提交说明生成并更新 `paper_softwarex_latex_source_20261109.zip`，包含 `paper_softwarex.tex`、官方 `elsarticle.cls`、两张图和构建说明，不含原始 JWD/SLIB 或临时文件。更新后 ZIP 为 3,966,772 字节，SHA-256 `26d16faf47b691a0ee261f7072e128b875ea0b8999960ec7af4b05d0f08f4fd6`。
- 首次编译发现 `authoryear` 与手工 bibliography 不兼容，已改为 `numbers` 并执行三轮编译。后续加入 T1 编码、6 处 `\textbar`、行号、`tabularx` 和简化 Quickstart，最终生成 17 页 PDF，交叉引用和参考文献可解析。
- 逐页渲染检查后，摘要已收回首页，表 1 不再越界，Quickstart 长导入路径已缩短，代码元数据表改为 footnotesize。编译日志仍有若干 overfull/underfull 警告，未将其写成零警告。
- 按 SoftwareX 口径估算约 **2,992 词、2 张图**。用户提供的 `D:\intro.pdf` 为真实 13 页官方指南，文件为 6,191,726 字节，SHA-256 `693870930050f13bac58fe8fe4d6c11990f297fe8fc08c045be7236ee1da9e51`。指南确认上限是 **4,000 词和 6 图**，不是此前二手检索的 3,000 词；摘要 194 词符合 250 词上限，关键词 6 个符合 1–7 个要求。已按首次出现顺序重排参考文献，改用标准 CRediT 角色，并在参考文献前加入实际 AI 使用声明。历史 Reader 性能段已删除。
- 官方 SoftwareX 专用模板仍未取得，现有编译只证明 `elsarticle` 可编译。`softwarex_template_request_draft.md` 已准备，需通过浏览器人机校验或编辑部回复取得真实模板后再核对。此闸门尚未完全关闭。

### NGAC 外部数据方案

- 用户选择“改为用户自备数据”。原始 12 个 JWD、5 个 SLIB 和 16 个 `reader_native` 文件已移至仓库外 `E:\AFH0.3米数据\JWD_external_fixtures`，不再进入当前 Git 工作树或后续 wheel/sdist。
- `PYMAPGIS_JWD`、`PYMAPGIS_SLIB` 和 `PYMAPGIS_READER_NATIVE` 支持外部路径。缺省为 **394 passed, 13 skipped**，外部数据齐全为 **423 passed, 1 skipped**；缺失可选数据给出明确获取提示，显式错误路径和校验失败仍硬失败。
- 当前 wheel **291 项**、sdist **329 项**，`tests/inspect_dist.py` 已改为拒绝任何原始 JWD/SLIB/reader_native 数据。安装后的无数据 wheel 使用外部 fixture 完成 Quickstart，目标回归为 **79 passed**。
- `ngac_distribution_remediation_plan.md` 区分停止新增分发和历史副本处置。Git 历史、PyPI 2.7.1 和 Zenodo 的既有副本仍需书面许可或单独的历史清理，未执行强制改写、下架或平台联系。新增分发边界已建立，完整历史合规闸门仍未关闭。

### 作者确认

- 用户选择保持 SoftwareX 现稿作者顺序。`author_confirmation_package.md` 已列明七位作者、CRediT、基金、利益冲突、致谢、AI 声明和当前版本批准方式。
- 该文件不是七位作者的批准。只有最终候选稿哈希填写完成且七位作者实际签字或邮件确认后，才能更新当前版本批准声明并勾选闸门。此闸门仍需外部确认。

### 颜色锚溯源

- 用户选择重新采集。`color_anchor_capture_package.md` 已包含 14 个锚、库路径和 SHA-256、4 个锚的 2026-10-22 记录、14 锚于 2026-10-23 入仓以及 2026-11-07 内部复核。
- MapGIS 6.7 目前只有间接版本证据，精确构建号、采集环境、采集人和 14 张截图或等效原生日志仍需实际补采。内部 JSON 不能替代原生截图。此闸门仍需外部证据。

## Reader/Writer 原生审计、发行包与图件定稿（迁移前快照）

本节为外部 fixture 迁移前阶段快照，当前测试数、归档数和合规状态见上节。

- Reader 审计使用 `F:\tmp` 的 36 个 MapGIS 二进制、原生明码与 SHP。36 个二进制均可读取；5 组原生 SHP 对照未发现需要修改 Reader 的缺陷。SHP 的自交面、空几何和部件组织差异没有被误判为 Reader 错误；`LDZOFBB004` 第 48 个空 SHP 面可由原生 WP 恢复。4 处 WAT 文本异常与二进制及 SHP 对照后确认不是 Reader 解码错误。可复现脚本和中文报告为 `audit_reader_native_tmp.py`、`reader_native_tmp_audit/`。
- `tests/fixtures/reader_native/` 含 16 个文件并配套 SHA-256 manifest；新增 `test_reader_native_exports.py` 8 项测试，覆盖点线几何、共享属性、CRS 边界、面有效性和缺失面恢复。
- Writer 第四批含 20 个 SHP 用例、18 个 MapGIS 原生转换结果及目录内 manifest，共 120 个文件。`test_writer_native_batch4.py` 28 项测试通过。原生 09 的错误面合并、07 的跨文件几何复用、06 的多部件丢失，以及量算错误、NaN/Inf/null 转 0 和 CRS 缺失均作为反例，不作为 Writer 应继承的行为。
- 新增 `test_writer_fixture_manifests.py` 5 项测试（含 batch2/3 参数化两项），逐文件核验 Writer batch2/3/4 和 Reader native 的字节数及 SHA-256；batch2/3 的文本条目同时保留原始 `bytes`/`sha256` 与 LF 规范化 `lf_bytes`/`lf_sha256`，避免 Git 换行策略造成跨平台误判，二进制仍严格按原始字节核验。batch4 还交叉核验根级与目录内 manifest 字节一致并锁定 120 个目录项，Reader native 锁定恰好 16 个目录项，防止额外文件随 force-include 混入。batch2/3/4 显式断言用例集合非空，避免空目录造成静默通过。
- wheel 内只将软件示例放在 `pymapgis/testing/examples/`，不占用通用顶层 `examples/` 命名空间。按用户要求，论文与 `mapgis2shp_submission/` 审计材料不进入 wheel 或 sdist；`validate_published_quickstart.py` 仅保留在仓库和稿件材料中，归档检查会拒绝任何投稿目录内容。
- 当前目标渲染、Reader 和 Writer 回归共 76 项，已在最终 wheel 安装态复跑为 **76 passed**（84.97 s）；同一 76 项也包含在源码完整套件中。完整套件在 Python 3.12.7、GeoPandas 1.1.3、Matplotlib 3.9.2 下复跑为 **420 passed, 1 environment-dependent skip**（52.76 s）。当前构建 wheel **323 项**、sdist **360 项**，均通过 `tests/inspect_dist.py`。
- `examples/render_bundled_jwd.py` 已加入 wheel/sdist；`validate_published_quickstart.py` 不进入发行包。最终 wheel 在独立 target 中实际安装并运行示例，得到 12 layers、7,094 features、5,732 drawn、713 polygon labels、1,362 excluded_text；未知色、未知填充、实线回退、未解决符号、空 pattern、循环上限和未知字体均为 0。
- 论文已从普通 `article` 迁移为 `elsarticle` frontmatter 和 SoftwareX 结构，包含 C1–C9、Illustrative examples、Impact 与 Conclusions。迁移前没有可用编译器；当前已使用获授权的 Tectonic 完成编译和逐页检查，详见上节。官方 SoftwareX 专用模板仍需取得，未将 404、AccessDenied 或 Cloudflare 页面当作官方模板。
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

- [x] 使用获授权的 Tectonic 与官方 elsarticle 3.4 编译并逐页检查版式，生成 PDF 和 LaTeX 源文件 ZIP（仍保留非零排版警告）。
- [ ] 使用 SoftwareX 官方专用模板复核结构、行号和最终版式；真实模板尚未取得。
- [x] 源码结构已迁移到 `elsarticle` / SoftwareX frontmatter，不能据此替代官方专用模板合规。
- [x] 将图 1 占位框替换为正式的软件架构图（`softwarex_architecture.pdf/.png`）。
- [x] 加入真实开源渲染输出图与 reports 判读（图 2 `jwd_map.pdf/.png/.svg`）。
- [ ] 如有条件，加入 MapGIS 原生输出与开源渲染的代表性对照图及差异分析。
- [x] 当前及后续发行包停止附带原始 JWD/SLIB/reader_native，改用外部 fixture 和哈希校验。
- [ ] 处理 Git 历史、PyPI 与 Zenodo 既有副本的条目级许可或历史清理；必要时附 NGAC 书面确认。
- [ ] 确认数据与 SLIB 的许可说明不被误解为 Apache-2.0 或公共领域授权。
- [ ] 补充原生颜色锚的 MapGIS 版本、采集路径、截图或日志，以及英文证据摘要。
- [x] 历史性能数字明确标为 Reader 基准；脚本与 JSON/CSV 随稿件材料提供。
- [ ] 全体作者确认作者贡献、基金、致谢及版本描述。
- [x] 核实并引用现有 2.7.1 的 Zenodo 版本 DOI。
- [ ] 后续 Release/Zenodo 应纳入 WP 文件名规范化、新示例、外部 fixture 获取说明、Reader/Writer 原生审计 manifest、加强断言和当前 291/329 项无原始数据归档，并同步 C1–C3。公开 V2.7.1 的中心 Quickstart 已通过兼容路径验证；当前 wheel 也已在配置外部数据后验证。发布件自身的旧 preferred-citation、历史数据副本与新回归制品仍待处理。
- [x] 既有提交 `575e80d` 的运行 `42574990251` 已全部成功，包括四测试环境、归档检查和 Twine。
- [x] 最新运行 `42634593828`（提交 `fe12768`）已全部成功，包括四测试环境、无原始数据归档检查和 Twine；无外部数据的 runner 明确可选跳过真实 JWD 渲染，不将其写成已完成真实渲染。
- [x] 已安装 PyMuPDF 并完成碰撞审计。架构图通过；JWD 原生密集注记存在未清除的碰撞，已作为限制保留，不标记为通过生产版式验收。

## 文件

- 初稿：`paper_softwarex.tex`
- 前期 ESI 稿：`paper.tex`（保留，不覆盖）
- 架构图：`softwarex_architecture.pdf/.png/.svg`（另在本地导出 600 dpi TIFF）
- 实图：`jwd_map.pdf/.png/.svg`
- 实图报告：`jwd_render_reports.json`
- 图件审计：`softwarex_architecture.source-audit.json`、`.text-audit.json`、`.svg-audit.json`、`.collision-audit.json`，以及 `jwd_map.source-audit.json`、`.text-audit.json`、`.svg-structure-audit.json`、`.collision-audit.json`；文本与终端日志保留在本地审计工作区
- 公共示例：`../examples/render_bundled_jwd.py`
- 编译稿：`compiled_20261109/paper_softwarex.pdf`
- LaTeX 源文件包：`paper_softwarex_latex_source_20261109.zip`
- 四闸门材料：`softwarex_template_request_draft.md`、`ngac_redistribution_request_draft.md`、`ngac_distribution_remediation_plan.md`、`author_confirmation_package.md`、`color_anchor_capture_package.md`
