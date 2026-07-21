# 库尔干幅（J43C001002）MapGIS 地质图渲染工作流

## 项目概述

使用 `pymapgis` 读取 MapGIS 6.x/67 矢量文件（`.wl`/`.wt`/`.wp`），投影到 WGS84 UTM Zone 43N（EPSG:32643）后，依据《DZ/T 0179 地质图用色标准》渲染地质图。

## 核心文件

| 文件 | 作用 |
|------|------|
| `dz_t_0179_colors.json` | DZ/T 0179 标准 RGB 色表（表2 正式地层、表3 跨时代、表6–13 侵入岩） |
| `render_strict_standard_map.py` | 严格按标准色渲染地质图，输出 `kurgan_strict_standard_map.png` |
| `render_thematic_maps.py` | 简化专题图渲染：输出地质-建造构造（LDZO）与水系（LDLY）两张专题图 |
| `render_combined_thematic_maps.py` | 将两张专题图合并为一张左右并排图 |
| `build_geological_unit_color_mapping.py` | 由 MapGIS 面图层生成地质单元配色映射表 |
| `verify_rendered_colors.py` | 建立配色映射表并核验渲染色一致性 |
| `verify_attitude_perpendicularity.py` | 核验产状走向与倾向输入字段垂直性 |
| `verify_rendered_attitudes.py` | 逐一核验渲染中产状符号走向线与短刺的垂直性及注记位置 |
| `analyze_fault_attributes.py` | 梳理断层属性并生成报告 |
| `analyze_attitude_types.py` | 梳理所有地层产状类型并生成报告 |
| `analyze_fault_attitude_types.py` | 梳理所有断裂产状类型并生成报告 |
| `build_fault_rendering_styles.py` | 生成断裂构造渲染样式配置 |
| `render_faults.py` | 按配置绘制断裂线、符号与注记 |
| `verify_fault_line_colors.py` | 白底单独渲染断层线并核对颜色 |
| `extract_fault_symbols_from_pdf.py` | 从 PDF 表22 提取断裂/构造线符号图片 |
| `analyze_fault_symbol_images.py` | 对表22 图片进行行分割与线型检测 |
| `parse_fault_symbols_from_pdf.py` | OCR 解析表22 符号名称并生成结构化对照表 |
| `reconstruct_geological_labels.py` | 从地质面图层重构完整地质单元代号标注点 |
| `.claude/skills/render-geology-map.md` | Claude Skill，可输入 `/render-geology-map` 一键渲染 |
| `geological_unit_color_mapping_final.{md,csv,json}` | 地质单元与配色映射表（最终版） |
| `color_verification_report.{md,json}` | 渲染色一致性核验报告 |
| `fault_color_verify.png` | 断裂线颜色白底核实图 |
| `fault_color_verify_report.md` | 断裂线颜色核实报告 |
| `geological_unit_codes_catalog.{md,json}` | 地质单元代号目录 |
| `geological_unit_rendering_scheme.md` | 地质单元代号渲染方案 |
| `geological_unit_labeling_scheme.md` | 地质单元代号标注方案（含 `#` 控制码与重构逻辑） |
| `geological_attitude_rendering_scheme.md` | 产状数据渲染方案（走向/倾向/倾角符号） |
| `geological_fault_rendering_scheme.md` | 断裂产状渲染方案 |
| `rendering_logic.md` | 整体渲染逻辑总览（图层顺序、配色、符号、整饰） |
| `thematic_rendering_scheme.md` | 专题图渲染方案（LDZO / LDLY） |
| `fault_type_geometry_summary.md` | 断裂类型与几何属性系统梳理 |
| `fault_rendering_styles.json` | 断裂构造渲染样式配置（机器可读） |
| `fault_rendering_styles_summary.md` | 断裂构造渲染样式总表 |
| `dz_t_0179_fault_symbols.{md,csv,json}` | DZ/T 0179 表22 断裂/构造线符号解析表 |
| `fault_symbol_extraction_report.{md,json}` | PDF 表22 图片/矢量提取报告 |
| `fault_symbol_image_analysis.{md,csv,json}` | 表22 图片行分割与线型检测结果 |
| `fault_attributes_report.md` | 断层属性梳理报告 |
| `fault_attributes.csv` | 断层属性详细表 |
| `attitude_types_report.md` | 地层产状类型梳理报告 |
| `attitude_types.csv` | 地层产状类型详细表 |
| `fault_attitude_types_report.md` | 断裂产状类型梳理报告 |
| `fault_attitude_types.csv` | 断裂产状类型详细表 |
| `geological_labels_reconstructed.{geojson,csv}` | 重构后的完整地质代号标注点 |

## 快速开始

一键渲染与核验：

```bash
/render-geology-map
```

或分步执行：

```bash
python3 reconstruct_geological_labels.py        # 重构完整地质代号标注点
python3 build_geological_unit_color_mapping.py  # 生成地质单元配色映射表
python3 build_fault_rendering_styles.py         # 生成断裂构造渲染样式配置
python3 render_strict_standard_map.py           # 渲染地质图
python3 verify_rendered_colors.py               # 核验颜色一致性
```

## 关键设置

- **投影坐标系**：所有图层读取后设为 EPSG:4326，并统一投影到 **WGS84 UTM Zone 43N（EPSG:32643）**。UTM 为正形投影，可保证产状符号的走向线与倾向短刺严格垂直。
- **透明度**：地质面填充 `alpha=1.0`，避免 PNG 颜色偏离配色表。
- **非地层图层**：`LDZOFBB009`/`010` 不填充米色，仅绘制边界，防止覆盖地质面色。
- **地质代号标注**：`LDZOFBB099.WT` 中的代号是碎片化注记对象（如 `N#-1` 与 `a` 分离），渲染器优先使用 `reconstruct_geological_labels.py` 生成的完整标注点。
- **产状符号**：`LDZOFBA016.WT` 存储走向/倾向/倾角，`LDZOFBB099.WT` 的 `CHFCEC == "产状"` 提供倾角数字注记；渲染为走向线 + 倾向短刺 + 倾角注记。
- **断裂构造**：`LDZOFBA003.WL`（实测）、`LYGREBA001.WL`（解译）、`LZLPGDJ002.WL`（深部）三类断层按 `fault_rendering_styles.json` 分层、分型绘制符号与倾角注记；类型代码地质含义待图例最终确认，当前为临时映射。
- **专题图**：运行 `python3 render_thematic_maps.py` 可分别输出 `kurgan_thematic_ldzo.png`（地质-建造构造）与 `kurgan_thematic_ldly.png`（水系）；运行 `python3 render_combined_thematic_maps.py` 可输出合并版 `kurgan_thematic_combined.png`。

## 注意事项

- 若 `dz_t_0179_colors.json` 不存在，先运行 `read_dz_t_0179_pdf.py` 与 `build_color_mapping_table.py` 从 PDF 建立色表。
- “阶一级”颜色提取见 `extract_stage_level_colors.py`，因 OCR 限制需人工校核。
- 产状符号严格按 `GZBBAB`（走向）和 `GZBBAC`（倾向）绘制；UTM 正形投影 + 等比例显示确保二者在图面上严格垂直。
- 运行 `python3 verify_rendered_attitudes.py` 可逐一核验产状符号的垂直性与注记位置。
- 运行 `python3 analyze_fault_attributes.py` 可生成断层属性梳理报告。
- 运行 `python3 analyze_attitude_types.py` 可生成地层产状类型梳理报告。
- 运行 `python3 analyze_fault_attitude_types.py` 可生成断裂产状类型梳理报告；当前断裂产状渲染方案已据此修正，待图例确认类型代码含义后实施。
- 运行 `python3 verify_fault_line_colors.py` 可白底单独渲染断层线并核对颜色配置。
- 运行 `python3 build_fault_rendering_styles.py` 可重新生成 `fault_rendering_styles.json` 与渲染样式总表。
- 运行 `python3 extract_fault_symbols_from_pdf.py` + `parse_fault_symbols_from_pdf.py` 可从 DZ/T 0179 PDF 表22 提取断裂/构造线符号并生成 `dz_t_0179_fault_symbols.md`。
- 运行 `python3 render_strict_standard_map.py` 时，`render_faults.py` 会按 `fault_rendering_styles.json` 绘制断裂线、符号与注记。
- 运行 `python3 render_thematic_maps.py` 可输出两张简化专题图（LDZO / LDLY），复用主渲染器逻辑，但仅加载对应前缀图层。
- 运行 `python3 render_combined_thematic_maps.py` 可将两张专题图左右合并为一张图，便于对比查看。
