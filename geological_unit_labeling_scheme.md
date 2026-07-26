# 地质单元地质代号标注方案

## 1. 标注数据源

### 1.1 原始注记图层（碎片化）

- **图层**：`LDZOFBB099.WT`（点要素）
- **字段**：`CHFCED`，存储各地质单元的地质代号片段，例如：
  - `N#-1` + `a` → N₁a
  - `Qp#-3` + `#+pal` → Qp₃ᵖᵃˡ
  - `D#-3` + `kz` + `#+2` → D₃kz²
  - `E` + `K` → EK

该图层中的代号是**分散的多个注记对象**（一个完整代号被拆成前缀、下标、岩性、上标等独立点），直接绘制会得到一堆不完整的片段。因此优先使用下面重构后的完整代号。

### 1.2 推荐：重构后的完整代号

- **生成脚本**：[`reconstruct_geological_labels.py`](reconstruct_geological_labels.py)
- **输出文件**：
  - `geological_labels_reconstructed.geojson`
  - `geological_labels_reconstructed.csv`

重构逻辑：

1. 读取地质面图层 `LDZOFBB004` / `LDZOFBB001` / `LDZOFBB002` / `LDZOFBB003`；
2. 从 `QDUECC` / `QDUECD` 取得完整代号（如 `→N↓1→a`）；
3. 对相同代号进行融合（dissolve），再 explode 成独立连通地块；
4. 为每个连通地块计算 `representative_point()` 作为标注锚点。

这样每个标注点都携带完整的单元代号，避免了 `LDZOFBB099.WT` 中的碎片问题。

## 2. 标注内容

直接采用 `CHFCED` 字段原始字符串。该字段实际使用 **MapGIS 注记控制码 `#`** 来标注上下标，格式如下：

| 控制码 | 含义 | 示例 |
|--------|------|------|
| `#=` | 正常显示 | `#=kz` → kz |
| `#-` | 下标 | `N#-1` → N₁ |
| `#+` | 上标 | `#+pal` → ᵖᵃˡ |

例如：

- `N#-1` 渲染为 N₁
- `Qp#-3` 渲染为 Qp₃
- `C#-2#=P#-1` 渲染为 C₂P₁
- `#+pal` 渲染为 ᵖᵃˡ
- `#=kz` 渲染为 kz
- `γοC#-2` 渲染为 γοC₂（希腊字母保留原符号）

为兼容其他来源，渲染器同时保留对箭头规则的支持：

| 箭头 | 含义 | 示例 |
|------|------|------|
| `→` | 正常显示 | `→D`、`→kz` |
| `↓` | 下标 | `↓3` → D₃ |
| `↑` | 上标 | `↑1` → kz¹ |

### 特殊字符处理

`CHFCED` 中偶尔出现 `#`、`$`、`%`、`&`、`^`、`_`、`{`、`}`、`~` 等 mathtext 保留字符（如 `C#-1`），渲染前会进行转义，避免 mathtext 解析失败。

## 3. 标注位置

### 3.1 使用预置标注点

优先使用 `LDZOFBB099.WT` 中每个点的 `(x, y)` 作为标注锚点。

```python
labels = load_layers(ROOT, ["LDZOFBB099"]).get("LDZOFBB099")
if labels is not None and "CHFCED" in labels.columns:
    sub = labels[labels["CHFCED"].astype(str).str.strip().str.len() > 0]
```

### 3.2 自动补全（无预置标注时）

对于未被 `LDZOFBB099` 覆盖的地质单元，可取其多边形 `representative_point()` 或 `centroid` 作为标注位置，并确保该点落在多边形内部。

```python
pt = polygon.representative_point()
```

## 4. 标注样式

| 参数 | 取值 | 说明 |
|------|------|------|
| 字体 | Noto Sans CJK SC / DejaVu Sans | 支持中文、箭头、希腊字母 |
| 字号 | 4–6 pt | 1:250000 图幅宜小字，避免压盖 |
| 颜色 | `black` | 代号主体 |
| 描边/光晕 | `white`，线宽 2 px | 提高在彩色面上的可读性 |
| 对齐 | `ha="center"`，`va="center"` | 以锚点为中心 |
| 旋转 | 0°（水平） | 保持代号可读；特殊需要可沿构造线旋转 |

Matplotlib 实现示例：

```python
ax.text(
    x, y, str(label).strip(),
    fontsize=4,
    color="black",
    ha="center", va="center",
    path_effects=[pe.withStroke(linewidth=2, foreground="white")],
)
```

## 5. 密度控制与冲突避免

1. **阈值过滤**：代号长度 ≤1 或为空的点不标注。
2. **数量上限**：若总点数过多（如 >600），按空间均匀采样或随机采样，避免图面拥挤。
3. **碰撞检测**（可选）：
   - 计算每个标注的边界框（Bbox）；
   - 迭代放置，若与已放置框重叠则跳过；
   - 对未放置的重要单元，改用最近未占用位置或连接引线。

## 6. 特殊符号渲染

### 箭头与上下标

使用 Matplotlib 的 **mathtext** 引擎，将原始代号自动转换为 TeX 格式。

当前 `CHFCED` 字段使用 `#` 控制码，渲染器按以下规则转换：

- `#=` 后内容按正常大小写入；
- `#-` 后内容用下标 `_{...}`；
- `#+` 后内容用上标 `^{...}`；
- 连续拉丁字母/数字放入 `\mathrm{}`；
- 希腊字母转换为对应 TeX 命令（如 `γ→\gamma`，`δ→\delta`）。

转换示例：

```text
N#-1              ->  $\mathrm{N}_{\mathrm{1}}$
Qp#-3             ->  $\mathrm{Qp}_{\mathrm{3}}$
C#-2#=P#-1        ->  $\mathrm{C}_{\mathrm{2}}\mathrm{P}_{\mathrm{1}}$
#+pal             ->  $^{\mathrm{pal}}$
#=kz              ->  $\mathrm{kz}$
γοC#-2            ->  $\gamma o \mathrm{C}_{\mathrm{2}}$
```

如果将来字段改用箭头风格，渲染器也支持：

```text
→D↓3→kz↑1    ->  $\mathrm{D}_{\mathrm{3}}\mathrm{kz}^{\mathrm{1}}$
→Qp↓3↑pal    ->  $\mathrm{Qp}_{\mathrm{3}}^{\mathrm{pal}}$
→γοC↓2       ->  $\gamma o \mathrm{C}_{\mathrm{2}}$
```

### 字体

- 中文字体：Noto Sans CJK SC
- 数学/希腊字母：matplotlib 内置数学字体（随 mathtext 自动选择）

### 特殊字符

`#`、`$`、`%`、`&`、`^`、`_`、`{`、`}`、`~` 等 mathtext 保留字符会被自动转义，防止解析错误。

## 7. 与地质面颜色的协调

- 在亮色单元（如 `Qh` #ffffbf、`K1` #8cff33）上使用黑字白边效果良好。
- 在深色/饱和单元（如 `γοC↓2` #f25585、`οφD↓1` #f23049）上同样适用，因为白边可隔离背景。

## 8. 输出产物

标注结果随地质图一起输出到：

- `kurgan_strict_standard_map.png`

可单独导出注记图层为：

- `geological_labels.geojson` / `geological_labels.svg`（矢量出版用）

## 9. 当前实现

1. **重构完整代号**：[`reconstruct_geological_labels.py`](reconstruct_geological_labels.py) 从地质面图层生成 `geological_labels_reconstructed.geojson`，每个标注点携带完整代号。
2. **`render_strict_standard_map.py`** 优先读取重构后的标注文件：
   - `parse_label_hash()`：按 `#=` / `#-` / `#+` 把 MapGIS 注记拆分为 normal/sub/sup 段；
   - `parse_label_arrows()`：兼容 `→/↓/↑` 箭头写法；
   - `_tokenize_label_segment()`：把连续拉丁/数字放入 `\mathrm{}`，希腊字母转为 TeX 命令；
   - `format_label()`：生成 mathtext 字符串，并自动转义 `#`、`$` 等特殊字符；
   - 调用 `ax.text(..., path_effects=[...])` 绘制黑字白边标注。
3. 若重构文件不存在，则回退到 `LDZOFBB099.WT` 原始碎片。

核心代码：

```python
display_label = format_label(str(label).strip())
ax.text(
    x, y, display_label, fontsize=4, color="black",
    ha="center", va="center",
    path_effects=[pe.withStroke(linewidth=2, foreground="white")],
)
```

渲染结果见 `kurgan_strict_standard_map.png`。
