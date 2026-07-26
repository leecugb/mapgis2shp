# 专题图渲染方案：地质-建造构造（LDZO）与水系（LDLY）

## 1. 设计目标

将原本综合在一张图上的内容拆分为两张专题图：

- **LDZO 专题图**：仅使用 `LDZO*` 前缀文件，聚焦地质面、构造线、产状与地质代号。
- **LDLY 专题图**：仅使用 `LDLY*` 前缀文件，聚焦水系面、水系线与水系注记。

这样可分别突出地质构造信息与水系信息，避免图面要素互相压盖，也便于按专题出版或制图。

## 2. 数据分层

### 2.1 LDZO 地质-建造构造专题

| 图层 | 类型 | 渲染方式 |
|------|------|----------|
| `LDZOFBB004` | 面 | 变质基底，按 DZ/T 0179 标准色填充 |
| `LDZOFBB001` | 面 | 主要地层，按标准色填充 |
| `LDZOFBB002` | 面 | 补充地层，按标准色填充 |
| `LDZOFBB003` | 面 | 侵入岩，按标准色填充 |
| `LDZOFBB009` | 面 | 断裂带边界，仅边界不填充 |
| `LDZOFBB010` | 面 | 构造岩浆岩带边界，仅边界不填充 |
| `LDZOFBA002` | 线 | 地质界线，深灰色实线 |
| `LDZOFBA003` | 线 | 实测断层，红色实线 + `render_faults.py` 符号 |
| `LDZOFBA005` | 线 | 褶皱轴，绿色虚线 |
| `LDZOFBA016` | 点 | 产状符号（走向线 + 倾向短刺 + 倾角注记） |
| `LDZOFBB099` / `geological_labels_reconstructed.geojson` | 点 | 地质代号注记 |

### 2.2 LDLY 水系专题

| 图层 | 类型 | 渲染方式 |
|------|------|----------|
| `LDLYAAE002` | 面 | 水域，浅蓝填充 + 深蓝边界 |
| `LDLYAAE001` | 线 | 河流/水系线，深蓝线 |
| `LDLYAAA005` | 线 | 水系边界/岸线，深蓝细线 |
| `LDLYAAI002` | 点 | 水系名称注记，蓝色斜体 |

## 3. 渲染脚本

### 3.1 分别输出两张专题图

[`render_thematic_maps.py`](render_thematic_maps.py)

执行：

```bash
python3 render_thematic_maps.py
```

输出：

- `kurgan_thematic_ldzo.png`
- `kurgan_thematic_ldly.png`

### 3.2 合并为一张图

[`render_combined_thematic_maps.py`](render_combined_thematic_maps.py)

执行：

```bash
python3 render_combined_thematic_maps.py
```

输出：

- `kurgan_thematic_combined.png`：左右并排显示 LDZO 与 LDLY 两张专题图，使用统一地理边界。

## 4. 实现要点

### 4.1 复用主渲染器逻辑

`render_thematic_maps.py` 导入 [`render_strict_standard_map.py`](render_strict_standard_map.py) 中的函数：

- `load_ir()` 驱动的 `_IR.resolve_unit_style()` 用于地质面配色。
- `format_label()` 用于格式化地质代号注记。
- `draw_attitudes()` 用于绘制产状符号。
- `draw_faults_with_styles()` 用于按 IR 绘制断层符号。
- `add_scale_bar()` / `add_north_arrow()` 用于图幅整饰。

### 4.2 各自独立的图层准备

- `prepare_ldzo_theme()`：只加载 `LDZO*` 文件，按主渲染器相同顺序配色。
- `prepare_ldly_theme()`：只加载 `LDLY*` 文件，水系面直接固定颜色，水系线按预设样式。

### 4.3 统一的专题绘制函数

`draw_theme_content()` 根据传入的 `ThemeLayers` 绘制：

1. 面状图层（地质面或水系面）
2. 覆盖层边界（仅 LDZO）
3. 线状图层
4. 断层符号（仅 LDZO，当存在 `LDZOFBA003` 时）
5. 产状符号（仅 LDZO）
6. 地质代号注记（仅 LDZO）
7. 水系注记（仅 LDLY）

### 4.4 边界计算

每个专题图根据各自图层计算总边界，不强制使用全图幅边界，因此两张图的视口范围可能略有不同。

## 5. 输出示例

| 文件 | 大小 | 内容 |
|------|------|------|
| `kurgan_thematic_ldzo.png` | ~2.3 MB | 地质面、断层、褶皱轴、产状、地质代号 |
| `kurgan_thematic_ldly.png` | ~1.0 MB | 水域、河流、水系名称 |
| `kurgan_thematic_combined.png` | ~2.3 MB | 左右并排的 LDZO + LDLY 专题图 |

## 6. 与综合图的关系

- [`render_strict_standard_map.py`](render_strict_standard_map.py) 继续输出全要素综合图 `kurgan_strict_standard_map.png`。
- [`render_thematic_maps.py`](render_thematic_maps.py) 输出两张简化专题图，互不覆盖。
- 若国家标准或图例调整，只需修改 `dz_t_0179_rendering_rules.json` 与 `render_strict_standard_map.py`，专题图会自动继承（通过导入复用）。

## 7. 后续可优化项

- 为 LDZO 专题增加图例条目，区分不同断层类型符号。
- 为 LDLY 专题增加水域面积分级或河流等级分级。
- 增加 MBTiles 专题瓦片输出。
- 增加专题图之间的一致性检查（如坐标系、比例尺、图幅范围）。
