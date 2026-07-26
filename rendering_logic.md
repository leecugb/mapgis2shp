# 库尔干幅地质图渲染逻辑总览

## 1. 总体架构

渲染流程由三套核心文件驱动：

| 文件 | 职责 |
|------|------|
| `dz_t_0179_rendering_rules.json` | DZ/T 0179 标准的**中间表示（IR）**，含色板、线型、花纹、参数化符号、规则 |
| `render_strict_standard_map.py` | **主渲染器**：准备图层 → 调用 `draw_map_content()` → 添加整饰 → 输出 PNG |
| `render_faults.py` | **断裂渲染模块**：按 IR `rules.faults` 绘制三类断层线、符号、注记 |
| `render_mbtiles.py` | **瓦片渲染器**：复用 `PreparedLayers` 与 `draw_map_content()`，输出 Raster MBTiles |

所有图层读取后统一投影到 **WGS84 UTM Zone 43N（EPSG:32643）**，保证角度与长度在图面上保真。

## 2. 数据准备阶段（`load_and_prepare_layers`）

### 2.1 加载地质面层

按固定顺序加载并配色：

1. `LDZOFBB004` 变质基底
2. `LDZOFBB001` 主要地层
3. `LDZOFBB002` 补充地层
4. `LDZOFBB003` 侵入岩
5. `LDZOFBB009` / `LDZOFBB010` 非地层构造面（仅边界，不填充）

配色逻辑：

- 读取 `QDUECC` 或 `QDUECD` 字段中的地质代号。
- 调用 `_IR.resolve_unit_style(code)` 得到 IR 中定义的 `fill` 样式（含 RGB、可选花纹）。
- 将颜色存入 `__color__`，将色键存入 `__key__`，将花纹名存入 `__pattern__`。
- 最终合并为 `geology_all`。

### 2.2 加载推断/解译面边界

`LHCPGDAC05/08/11`、`LZLPGDJ004/006/009` 以紫色虚线绘制边界。

### 2.3 加载水系

- `LDLYAAE002`：浅蓝面 + 深蓝边
- `LDLYAAE001` / `LDLYAAA005`：深蓝线

### 2.4 加载构造线

构造线图层及默认样式：

| 图层 | 颜色 | 线宽 | 线型 | 图例 |
|------|------|------|------|------|
| `LDZOFBA002` | `#333333` | 0.3 | 实线 | 地质界线 |
| `LDZOFBA003` | `#e41a1c` | 0.7 | 实线 | 实测断层 |
| `LDZOFBA005` | `#4daf4a` | 1.0 | `--` | 褶皱轴 |
| `LHCPGDAC01` | `#ff7f00` | 0.6 | `-.` | 物探推断断裂 |
| `LYGREBA001` | `#984ea3` | 0.6 | `:` | 遥感解译线 |
| `LYGREBA004` | `#984ea3` | 0.6 | `-.` | 遥感环形构造 |
| `LZLPGDJ002` | `#e41a1c` | 1.2 | `--` | 深部大断裂 |
| `LHTQGTA001` | `#377eb8` | 0.8 | `-.` | 地球化学界线 |

### 2.5 加载产状点

- `LDZOFBA016`：走向/倾向/倾角。
- `LDZOFBB099` 中 `CHFCEC == "产状"` 的记录：作为倾角数字注记源。

### 2.6 加载地质代号注记

优先级：

1. `geological_labels_reconstructed.geojson` 的 `code` 字段（完整重构代号）。
2. 若不存在，回退到 `LDZOFBB099` 中 `CHFCEC == "代号"` 的 `CHFCED`。

### 2.7 加载水系注记

`LDLYAAI002` 的 `NAME` 字段。

## 3. 图面绘制阶段（`draw_map_content`）

绘制顺序（后绘制者压盖前者）：

```
1. 标准色地质面
2. 非地层构造面边界（LDZOFBB009/010）
3. 推断/解译面边界
4. 水系面/线
5. 构造线（除断层外）
6. 断层构造（draw_faults_with_styles）
7. 产状符号（draw_attitudes）
8. 地质代号注记
9. 水系注记
```

所有图层先通过 `_filter_by_bounds()` 按当前视口 + 边距裁剪，避免瓦片渲染时绘制范围外要素。

## 4. 断裂渲染逻辑（`render_faults.py`）

### 4.1 配置来源

从 `dz_t_0179_rendering_rules.json#rules.faults` 读取三类断层源：

| 源 | 文件 | 类型字段 | 倾角字段 | 数据性质 |
|----|------|----------|----------|----------|
| `LDZOFBA003` | `LDZOFBA003.WL` | `GZEEB` | `GZECE` | 实测断层 |
| `LYGREBA001` | `LYGREBA001.WL` | `GZEEBM,GZEGD` | `GZEEI` | 遥感/地质解译断层 |
| `LZLPGDJ002` | `LZLPGDJ002.WL` | — | `GZEEL` | 深部大断裂 |

### 4.2 每类断层绘制流程

对每一类断层源：

1. **绘制基线**：按 `base_style`（颜色、线宽、线型、透明度）。
2. **绘制破碎带双线**：若 `symbol_type == "shear_zone_double_line"`，用 `SymbolEngine.render_line_offset()` 绘制平行双线。
3. **采样绘制符号**：
   - 沿断层线按 `sample_spacing_m` 采样。
   - 短线段（`length <= short_segment_threshold_m`）只在中点采样。
   - 在每个采样点计算单位切向量与左右法向量。
   - 根据 `symbol_type` 调用 `SymbolEngine.render_point_symbol()` 绘制标准符号：
     - `normal`：正断层齿
     - `reverse` / `thrust`：逆断层/冲断层三角齿
     - `strike_slip`：平推断层双半箭头
     - `active`：活动断层双箭头
     - `neutral_tick`：中性短垂线
     - `solid_unknown` / `concealed` / `arc_unknown`：仅基线，无符号
4. **倾角注记**：当 `label_dip=true` 且倾角字段 > `dip_angle_min` 时，在符号处沿线偏移标注倾角。
5. **深部断裂名称**：`LZLPGDJ002` 沿线中点标注断层名称。

### 4.3 倾向侧判定

优先级：

1. IR 中该类型配置的 `default_side`（`right` / `left`）。
2. 命名断层的特殊描述（如“断面倾向北东”），未来可解析为方位角后选择更近侧。
3. 性质不明类型不绘制指向性符号。

> 当前 `LDZOFBA003.WL` 的 `GZECD` 倾向字段全部为空，因此 `default_side=right` 为暂定可视化约定，已在图例中声明“倾向侧待确认”。

## 5. 产状渲染逻辑（`draw_attitudes`）

### 5.1 数据来源

- `LDZOFBA016.WT` 的 `GZBBAB`（走向）、`GZBBAC`（倾向）、`GZBBAD`（倾角）。
- 可选注记：最近 `LDZOFBB099` 中产状数字注记（距离 < 20 km）。

### 5.2 符号组成

1. **走向线**：沿 `GZBBAB` 方向、以点为中心向两侧延伸 650 m。
2. **倾向短刺**：沿 `GZBBAC` 方向伸出 330 m，与走向线严格垂直（UTM 正形投影保证）。
3. **倾角注记**：位于短刺末端，再沿走向偏移 270 m，黑色显示。

### 5.3 特殊类型

- `GZBBGA == "202005"`（变质岩产状）：绘制**双平行走向线**，倾向短刺连接到倾向侧第一条线。
- 其他类型统一使用黑色。

## 6. 代号注记格式化

`format_label()` 函数处理两种输入规则：

- **MapGIS `#` 控制码**：`#=` 正常、`#-` 下标、`#+` 上标。
- **箭头控制码**：`→` 正常、`↓` 下标、`↑` 上标。

希腊字母转换为 Matplotlib mathtext 命令（如 `γ` → `\gamma`），最终生成 `$...$` 字符串供 `ax.text()` 渲染。

## 7. 图幅整饰

主渲染器在 `draw_map_content()` 之后添加：

- 标题
- 坐标轴标签（东向 m / 北向 m）
- 20 km 比例尺（`add_scale_bar`）
- 指北针（`add_north_arrow`）
- 图例（构造线类型）

## 8. MBTiles 渲染（`render_mbtiles.py`）

1. 调用 `load_and_prepare_layers()` 准备图层（目标 CRS 改为 **EPSG:3857** Web Mercator）。
2. 按指定 zoom 范围（默认 6–12）和瓦片尺寸（默认 256×256）遍历瓦片。
3. 对每个瓦片：
   - 计算 Web Mercator 边界。
   - 创建临时 `Axes`。
   - 调用 `draw_map_content()`，不绘制标题/比例尺/指北针/图例。
   - 保存 PNG 到 SQLite MBTiles 的 `tiles` 表。
4. 写入 `metadata` 表（名称、格式、边界、zoom 范围等）。

## 9. 核验与验证脚本

| 脚本 | 核验内容 |
|------|----------|
| `verify_rendered_colors.py` | 像素级核验地质面色与映射表一致性 |
| `verify_rendered_attitudes.py` | 核验走向线与倾向短刺严格垂直、注记位置正确 |
| `verify_fault_line_colors.py` | 白底单独渲染断层线，核对颜色配置 |
| `verify_fault_style_synthetic.py` | 合成图检验断层符号几何正确性 |
| `verify_rendering_rules.py` | 核验 IR 规则覆盖度与一致性 |

## 10. 关键设计决策

1. **IR 驱动**：颜色、线型、花纹、符号尽量通过 `dz_t_0179_rendering_rules.json` 配置，代码只负责解释执行；国家标准调整时修改 JSON 即可。
2. **正形投影**：UTM Zone 43N 保证角度不变，使产状符号走向线与倾向短刺在图面上严格垂直。
3. **alpha=1.0**：地质面填充不透明，避免 PNG 输出与配色表产生色差。
4. **重构注记优先**：避免 `LDZOFBB099.WT` 中代号碎片化问题。
5. **断层类型优先于倾角**：倾角只作数值注记，符号类型由 `GZEEB`/`GZEEBM`/`GZEGD` 决定。

## 11. 后续可扩展点

- 将 `draw_attitudes()` 也迁移到 IR 驱动，支持按 `GZBBGA` 类型配置不同线型/颜色。
- 实现花纹填充（patterns）的图面渲染，目前 IR 已定义但可能未完全启用。
- 增加注记冲突检测，避免密集区域代号/倾角压盖。
- 图例确认后，更新 `rules.faults` 中暂定类型映射，并移除“倾向侧待确认”声明。
