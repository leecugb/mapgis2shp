# 库尔干幅地质单元代号渲染方案

## 1. 数据源

- **矢量数据**：MapGIS 6.x/67 格式 `.wl`（线）、`.wt`（点）、`.wp`（面）。
- **地质面图层**：`LDZOFBB001`、`LDZOFBB002`、`LDZOFBB003`、`LDZOFBB004`。
- **地层代号字段**：优先读取 `QDUECC`，其次 `QDUECD`。
- **配色标准**：`dz_t_0179_colors.json`（从 DZ/T 0179 PDF 提取并校核）。

## 2. 代号解析流程

对每条面要素的 `QDUECC`/`QDUECD` 字符串执行以下解析：

### 2.1 清洗

去掉箭头、上下标、小数点、连字符及希腊字母：

```text
→  ↓  ↑  ·  .  -  γ δ β υ η ν τ α ο φ ρ π μ ε
```

例如 `→D↓3→kz↑1` 规范化为 `D3kz1`。

### 2.2 判断是否侵入岩

若代号中包含希腊字母（`γδβυηνταοφρπμε`），则视为**侵入岩**，进入侵入岩配色分支；否则进入地层配色分支。

### 2.3 地层分支

按以下优先级匹配年代键：

1. **跨时代地层**（表3）：`C2P1→CP`、`EK`、`EN`、`NQ`、`KE`、`JK`、`TJ`、`PT`、`CP`、`DC`、`SD`、`OS`、`EO`、`ZE`、`NhZ`、`Ar3Pt1`。
2. **精确系/统**（表2）：`Qh`、`Qp`、`N1/2`、`E1/2/3`、`K1/2`、`J1/2/3`、`T1/2/3`、`P1/2/3`、`C1/2`、`D1/2/3`、`S1/2/3/4`、`Pt1/2/3`、`Ch`、`Nh`、`Z`、`Qb`、`Ar0/1/2/3`、`Hd`。
3. **单字母兜底**：若只出现时代字母（如 `ηγP` 中的 `P`），映射到代表性统：`P→P2`、`C→C2`、`D→D2` 等。

匹配到键后，从 `dz_t_0179_colors.json` 的 `period` 或 `cross_period` 中取色。

### 2.4 侵入岩分支

1. **岩性分类**（按希腊字母）：
   - `γ` 或 `η` → `acid_intermediate`（酸性—中酸性）
   - `ν` → `alkaline`（碱性）
   - `β` 或 `υ` → `basic`（基性）
   - `δ` 或 `τ` → `neutral`（中性）
2. **时代解析**：同地层分支，得到 `T1`、`C2`、`D1` 或更粗的 `Mz`/`Pz2`/`Pz1` 等。
3. **查色顺序**：
   - 先用精确年代键查对应侵入岩表；
   - 再用代表段（如 `S3-4→S3`）；
   - 再用“代”键（`Cz`/`Mz`/`Pz2`/`Pz1`/...）；
   - 最后用岩性大类兜底色 `rock_type_fallback`。

### 2.5 非地层图层

`LDZOFBB009`（断裂带）和 `LDZOFBB010`（构造岩浆岩带）无 `QDUECC/QDUECD` 字段，不填充面色，仅绘制边界线。

## 3. 渲染顺序

后绘制的图层会压盖先绘制的图层，因此顺序为：

1. `LDZOFBB004` — 变质基底（阿克苏岩群、赛图拉岩群等）
2. `LDZOFBB001` — 主要地层
3. `LDZOFBB002` — 补充地层
4. `LDZOFBB003` — 侵入岩（应绘于地层之上）
5. 构造线、水系、注记、图例等叠加要素
6. `LDZOFBB009` / `LDZOFBB010` — 仅边界

## 4. 绘制参数

- **地质面填充**：`alpha=1.0`，确保 PNG 颜色与配色表完全一致，不叠加白色背景产生色差。
- **边界线**：`edgecolor="#555555"`、`linewidth=0.15`，仅用于区分单元，不影响面色。
- **非地层边界**：
  - `LDZOFBB009`：`edgecolor="#d95f02"`、`linewidth=0.6`
  - `LDZOFBB010`：`edgecolor="#8c510a"`、`linewidth=0.5`、`linestyle="--"`

## 5. 输出产物

| 文件 | 说明 |
|------|------|
| `kurgan_strict_standard_map.png` | 最终渲染地质图 |
| `geological_unit_color_mapping_final.{md,csv,json}` | 地质单元—颜色映射表 |
| `color_verification_report.{md,json}` | 渲染色一致性核验报告 |

## 6. 核验

- **颜色分配一致性**：程序赋色与映射表比对，应为 100%。
- **像素级核验**：对可见多边形内部网格采样，比较采样 RGB 与预期 RGB（容差 ≤2），统计匹配率。

## 7. 一键调用

已封装为 Claude Skill：`/render-geology-map`，或在项目目录下执行：

```bash
python3 render_strict_standard_map.py
python3 verify_rendered_colors.py
```
