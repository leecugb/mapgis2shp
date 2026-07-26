# 产状数据渲染方案

## 1. 数据来源

| 文件 | 要素类型 | 记录数 | 作用 |
|------|----------|--------|------|
| `LDZOFBA016.WT` | 点 | 305 | 产状主数据（走向、倾向、倾角、产状类型） |
| `LDZOFBB099.WT` | 点 | 307（`CHFCEC == "产状"`） | 产状倾角数字注记，与 `LDZOFBA016` 空间匹配后作为注记文本 |

说明：

- `LDZOFBB099.WT` 中 `CHFCEC == "产状"` 的注记内容为纯数字（如 `46`、`70`、`30`），与 `LDZOFBA016.WT` 的 `GZBBAD` 字段对比，**301/305 个点的误差在 2° 以内**，因此可确认这些数字是产状的**倾角注记**。
- 这些数字注记点与产状点的平均距离约 **0.005°**（约 400–500 m），用于把注记文本匹配到最近的产状符号。

## 2. 字段解析

`LDZOFBA016.WT` 的字段含义（根据数值关系推断）：

| 字段 | 含义 | 单位 | 数值范围 | 说明 |
|------|------|------|----------|------|
| `GZBBGA` | 产状类型代码 | - | `202001`、`202005`、`202004`、`202011` | 类型编码，具体地质含义待图例确认 |
| `GZBBAB` | **走向** | ° | 1–175 | 产状线的方位角 |
| `GZBBAC` | **倾向** | ° | 0–359 | 与走向垂直，差值约 90° 或 270° |
| `GZBBAD` | **倾角** | ° | 9–87 | 岩层/面理的倾斜角度 |

验证：

- `GZBBAC - GZBBAB` 模 360 后，约 139 个点接近 90°，166 个点接近 270°，即二者基本正交。
- `GZBBAD` 的分布为 9°–87°，符合倾角范围。

完整类型梳理见 [`attitude_types_report.md`](attitude_types_report.md)，由 [`analyze_attitude_types.py`](analyze_attitude_types.py) 生成。

## 3. 产状类型代码分布

| 代码 | 数量 | 推测含义 | 渲染颜色 |
|------|------|----------|----------|
| `202001` | 239 | 层面产状（最常见） | 黑色 |
| `202005` | 63 | **变质岩产状**（片理 / 劈理 / 千枚理） | 红色 `#e41a1c`，走向线为双平行线 |
| `202004` | 2 | 线理 / 擦痕 | 蓝色 `#377eb8` |
| `202011` | 1 | 节理 / 裂隙 | 绿色 `#4daf4a` |

> **注意**：当前统一使用黑色；若后续需要按产状类型着色，可在 `draw_attitudes()` 的 `type_style` 中恢复不同颜色。

## 4. 投影方式

由于原始数据为经纬度坐标，直接在等比例经纬度画布上绘制方位角会导致投影变形（走向线与倾向短刺不垂直）。因此渲染器将数据统一投影到 **WGS84 UTM Zone 43N（EPSG:32643）**，该投影为正形投影，可保持局部角度不变。

涉及文件：

- [`render_strict_standard_map.py`](render_strict_standard_map.py)：`load_layers()` 读取每层后设置 EPSG:4326 并转 UTM。
- [`reconstruct_geological_labels.py`](reconstruct_geological_labels.py)：重构的完整代号标注点直接输出为 UTM。
- 图幅标题与坐标轴标注为 `东向 (m)` / `北向 (m)`。

## 5. 渲染逻辑

### 5.1 符号组成

每个产状点绘制三个要素：

1. **走向线**：一条以产状点为中心、沿走向方向延伸的短线；变质岩产状（`202005`）为双平行线。
2. **倾向短刺**：从走向线（变质岩为倾向侧的第一条平行线）向倾向方向伸出的一条更短的垂线，表示倾斜方向。
3. **倾角注记**：在倾向短刺末端沿走向方向偏移放置，**统一使用黑色**，避免遮盖短刺。

### 5.2 几何计算（UTM 坐标，单位：米）

```text
strike_rad = radians(strike)
dip_rad    = radians(dip_dir)

# 走向线半长、倾向短刺长、注记沿走向偏移
L = 650 m
l = 330 m
s = 270 m

sx = L * sin(strike_rad)    sy = L * cos(strike_rad)
dx = l * sin(dip_rad)       dy = l * cos(dip_rad)

# 走向线端点
x1 = x - sx,  y1 = y - sy
x2 = x + sx,  y2 = y + sy

# 倾向短刺端点
xt = x + dx,  yt = y + dy

# 倾角注记位置（沿走向偏移 s）
xl = x + dx + s * sin(strike_rad)
yl = y + dy + s * cos(strike_rad)
```

### 5.3 注记匹配

- 用 `scipy.spatial.cKDTree` 对 `LDZOFBB099` 中的“产状”数字注记建立索引。
- 对每个产状点查找最近注记点，若距离 **< 20 km**，则采用该注记文本；否则回退到 `GZBBAD` 的整数值。
- 匹配成功率：**301/305 ≈ 98.7%**。

## 6. 输出效果

渲染结果写入：

- `kurgan_strict_standard_map.png`

图中产状以带走向线、倾向短刺和倾角数字的标准符号显示，取代了原先统一的黑色三角。

## 7. 核验

运行：

```bash
python3 verify_rendered_attitudes.py
```

输出：

- `attitude_rendering_verification.md`
- `attitude_rendering_verification.csv`

最新核验结果：

| 指标 | 结果 |
|------|------|
| 总记录数 | 305 |
| 走向–短刺点积 | ±5.55e-16（浮点误差） |
| 走向–短刺夹角 | 90.000000° |
| 严格垂直记录 | **305 / 305** |
| 注记沿走向偏移 | 270.00 m |
| 注记沿倾向偏移 | 0.00 m |

## 8. 当前实现

实现函数：

- `draw_attitudes(ax, att, labels, ...)` in [`render_strict_standard_map.py`](render_strict_standard_map.py)

调用位置：

```python
att = load_layers(ROOT, ["LDZOFBA016"]).get("LDZOFBA016")
raw_labels_all = load_layers(ROOT, ["LDZOFBB099"]).get("LDZOFBB099")
draw_attitudes(ax, att, labels=raw_labels_all)
```

## 9. 后续可优化项

- 确认 `GZBBGA` 各代码的精确地质含义与图例颜色。
- 对不同类型的产状使用不同线型（如虚线、点划线）或符号。
- 当注记过于密集时，增加冲突检测或按比例尺动态调整符号大小。
- 若需要，可单独导出 `attitudes.geojson` / `attitudes.svg` 作为矢量出版图层。
