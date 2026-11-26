# mapgis2shp 2.7.3 全面审计报告

日期：2026-11-25  
范围：当前工作树中的 `src/pymapgis`、CLI、验证脚本、示例、测试、发行配置，以及用户提供的 J43C001002 库尔干幅 NAS 数据。

## 1. 总体结论

本包在随包数据和用户提供的库尔干幅真实数据上表现稳定：读写、图形库解析、渲染、投影和 GeoPDF 主流程均通过验证。审计中未发现 `eval`/`exec`、pickle 反序列化、shell 注入、网络调用或恶意代码路径，也未发现需要立即阻断发布的高危安全问题。

本次审计共修复 6 类已复现问题，并补充 11 项回归测试（含此前验证脚本修复的 2 项）。当前最大的剩余风险不是已发现的代码缺陷，而是外部验收边界：原始 JWD 基准中 `LDZOFBA016.WT` 哈希不一致，NAS 中的 SHP 是后期处理版本，且仍缺少 MapGIS 原生应用打开、编辑、保存的独立验收。

## 2. 审计方法

- 源码结构、公共 API、CLI 入口和数据流审查
- Ruff 全树检查、源码编译检查、危险调用模式扫描
- Writer 边界输入动态复现：NaN/Inf 坐标、越界图形参数、保留字段元数据、NumPy 标量缺失值
- Reader 截断和随机字节变异：3 个合成 fixture，共 501 个用例
- 五类图形库截断和随机字节变异的资源耗尽检查：共 295 个用例
- 源码全量 pytest、隔离安装 wheel 全量 pytest、分支覆盖率
- 库尔干幅 36 个原生 WT/WL/WP 全量读取与本地往返
- wheel/sdist 重建、归档内容检查和 Twine 元数据检查

## 3. 已修复问题

| ID | 严重度 | 问题 | 影响与证据 | 修复 |
|---|---|---|---|---|
| A-01 | 中 | `verify_pymapgis.py` 在不同 CRS 下直接比较往返结果 | Writer 默认会把 UTM 转为 Gauss–Krüger；旧脚本仍比较原 CRS 坐标和面积，导致库尔干/测试数据全部误报失败 | 在源 CRS 中比较输出，见 [`verify_pymapgis.py`](../verify_pymapgis.py)；新增 [`test_verify_pymapgis.py`](../tests/test_verify_pymapgis.py) |
| A-02 | 中 | Writer 接受 NaN/Inf 坐标 | 可写出 bbox 为 NaN/Inf 的 `.wt`/`.wl` 文件；已用 Point 和 LineString 复现 | Writer 在标准化几何后拒绝非有限坐标，见 [`writer.py`](../src/pymapgis/writer.py) |
| A-03 | 中 | 图形参数校验不一致 | `layer=256` 等无符号参数会被静默取模，线宽等 float32 字段可写入 Inf | 增加 uint8/uint16/float32 参数校验，非法值抛出 `WriterError` |
| A-04 | 低 | 保留源字段元数据后，越界整数泄漏底层 `struct.error` | 将 int32 字段改为 `2**40` 后，旧代码抛出原始 struct 错误而不是公共 `WriterError` | 数值属性编码失败统一包装为 `WriterError` |
| A-05 | 低 | `_is_missing()` 未识别部分 NumPy 标量缺失值 | `np.float32("nan")` 在对象列中可能被写成字符串 `"nan"` | 改用 pandas 标量缺失判断 |
| A-06 | 中 | `ColorLib` 不校验文件签名 | 任意 24 字节文件都会被当成色表并返回错误 RGB | 要求 `C.U.G  Colorg` 签名，见 [`colorlib.py`](../src/pymapgis/colorlib.py) |

另修复一处示例导入格式问题，使全树 Ruff 通过。

新增回归测试集中在 [`test_audit_regressions_20261125.py`](../tests/test_audit_regressions_20261125.py) 和 [`test_verify_pymapgis.py`](../tests/test_verify_pymapgis.py)；变更摘要已写入 [`CHANGELOG.md`](CHANGELOG.md)。

## 4. 验证结果

| 验证项 | 结果 |
|---|---|
| Ruff 全树检查 | 通过 |
| 源码编译检查 | 通过 |
| 顶层公共 API | 33 个 `__all__` 导出全部可解析 |
| 源码全量测试 | **546 passed，32 skipped** |
| 隔离安装 wheel 全量测试 | **543 passed，35 skipped** |
| 启用分支统计的覆盖率 | **83%**；Reader 91%，Writer 91%，Graphic 86%，LINESTY 61% |
| Writer 定向回归 | 158 passed |
| 渲染/图形审计回归 | 99 passed |
| 颜色库与 CLI 定向回归 | 8 passed |
| Reader 损坏输入检查 | 501 个截断/变异用例，无意外异常类型 |
| 图形库资源耗尽检查 | 295 个截断/变异用例，无 MemoryError/RecursionError |
| 库尔干幅全目录 | 36 个 WT/WL/WP、16,874 个要素；修复后 **36/36 往返通过** |
| 十二层真实渲染 | 13/15 通过；仅 2 项失败，均为同一个 `LDZOFBA016.WT` 哈希差异 |
| 严格矢量 GeoPDF | 通过；实际比例 X/Y 均约 250,000，无栅格图像对象 |
| wheel/sdist 构建 | 通过；wheel 319 项、sdist 402 项 |
| Twine 元数据检查 | 当前环境失败：packaging 25.0 不识别 `Metadata-Version: 2.5` |

十二层渲染输出保存在本地验证目录 `outputs/J43C001002/`。这些文件是本地验证产物，不属于发行包内容；如需再分发，仍需遵守原始 JWD/SLIB 数据条款。

## 5. NAS 数据核对结论

- 五个共享 SLIB 文件大小和 SHA-256 全部匹配项目清单。
- 十二个基准 JWD 矢量中 11 个匹配；`LDZOFBA016.WT` 大小相同但 SHA-256 不同。
- 该 WT 可正常读取、渲染和往返，因此当前差异应视为基准版本问题，而不是 Reader/Writer 故障。
- NAS `SHP` 目录中的多数文件与原始 MapGIS 导出清单不一致，并带有 `.prj`（EPSG:4214）；对应 7 项旧断言失败均由处理后数据特征解释，未判定为 Reader 回归。

## 6. 剩余风险与建议

| 优先级 | 风险 | 建议 |
|---|---|---|
| 高 | 原始 JWD 基准不完整：`LDZOFBA016.WT` 与清单哈希不一致 | 从官方渠道重新获取原始文件，或确认当前 NAS 文件才是正确版本后，单独建立新基准；不要直接覆盖旧清单 |
| 高 | 缺少 MapGIS 原生应用验收 | 保留“内部测试通过”和“原生打开/编辑/保存通过”两类结论，不互相替代 |
| 中 | LINESTY 覆盖率 61%，复杂线型和异常分支仍是主要盲区 | 优先补 `(linetype, aux)` 变体、坏指针、截断记录、周期边界和真实库结构断言 |
| 中 | NAS SHP 与原始导出不是同一版本 | 若需支持处理后 SHP，另建 manifest 和测试组，不要放宽原始导出测试 |
| 中 | 最低依赖版本组合未实际验证 | 增加 minimum-dependency CI；当前仅验证了较新的依赖组合 |
| 低 | 渲染器缓存按单图案限制资源，但没有跨图案累计字节上限 | 对不可信大批量数据渲染时增加全局 tile/cache 字节预算 |
| 低 | 部分图形库损坏输入仍可能抛出底层 struct/ValueError | 统一包装为明确的库解析异常；ColorLib 签名问题已先修复 |
| 低 | GeoPDF 在异常路径下未显式关闭 document | 用 `try/finally` 或上下文管理器消除极端错误路径的资源泄漏 |
| 低 | `integration` marker 与外部数据测试覆盖不完全一致 | 统一外部数据测试标记和跳过原因，便于 CI 分层 |
| 低 | `repr(reader)` 未包含所有构造参数，与 README 描述略有出入 | 更新 README 或扩充 repr |
| 发布 | 当前 Twine/packaging 组合不支持 Metadata 2.5 | 发布前用支持 Metadata 2.5 的新工具链复核，或调整构建/发布工具约束 |

## 7. 本次修改文件

- [`src/pymapgis/writer.py`](../src/pymapgis/writer.py)
- [`src/pymapgis/colorlib.py`](../src/pymapgis/colorlib.py)
- [`verify_pymapgis.py`](../verify_pymapgis.py)
- [`examples/convert_usgs_conejo.py`](../examples/convert_usgs_conejo.py)
- [`tests/test_verify_pymapgis.py`](../tests/test_verify_pymapgis.py)
- [`tests/test_audit_regressions_20261125.py`](../tests/test_audit_regressions_20261125.py)
- [`docs/CHANGELOG.md`](CHANGELOG.md)
- 本报告：[`docs/package_audit_20261125.md`](package_audit_20261125.md)

## 8. 最终判断

在当前可验证范围内，包可以判定为**功能稳定、测试证据充分、无已知阻断性代码缺陷**。发布或对外声称“原生兼容”前，应先解决原始 JWD 基准版本问题，并补充 MapGIS 原生应用验收；LINESTY 复杂分支和最低依赖矩阵是下一阶段最值得投入的测试工作。
