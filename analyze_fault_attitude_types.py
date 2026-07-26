#!/usr/bin/env python3
"""梳理所有断裂产状类型：断层线、解译断层、深部断裂，生成报告。"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from pymapgis import Reader

ROOT = Path(__file__).parent
TARGET_CRS = "EPSG:32643"


def line_azimuth(geom) -> float:
    """返回线段整体走向方位角（°，0–360，从北顺时针）。"""
    coords = list(geom.coords)
    x1, y1 = coords[0]
    x2, y2 = coords[-1]
    dx = x2 - x1
    dy = y2 - y1
    az = np.degrees(np.arctan2(dx, dy))
    if az < 0:
        az += 360
    return az


def analyze_ldzofba003() -> pd.DataFrame:
    """分析实测断层线 LDZOFBA003.WL。"""
    path = ROOT / "LDZOFBA003.WL"
    if not path.exists():
        return pd.DataFrame()

    with Reader(path) as r:
        gdf = r.geodataframe.copy()
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    gdf_utm = gdf.to_crs(TARGET_CRS)

    gdf["length_m"] = gdf_utm.geometry.length
    gdf["length_km"] = gdf["length_m"] / 1000.0
    gdf["azimuth_deg"] = gdf_utm.geometry.apply(line_azimuth)
    gdf["strike_deg"] = gdf["azimuth_deg"].apply(lambda a: a if a <= 180 else a - 180)

    for col in ("KCDDEF", "GZECE"):
        if col in gdf.columns:
            gdf[col] = pd.to_numeric(gdf[col], errors="coerce")

    return gdf


def analyze_lygreba001() -> pd.DataFrame:
    """分析解译/遥感断层线 LYGREBA001.WL。"""
    path = ROOT / "LYGREBA001.WL"
    if not path.exists():
        return pd.DataFrame()

    with Reader(path) as r:
        gdf = r.geodataframe.copy()
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    gdf_utm = gdf.to_crs(TARGET_CRS)

    gdf["length_m"] = gdf_utm.geometry.length
    gdf["length_km"] = gdf["length_m"] / 1000.0
    gdf["azimuth_deg"] = gdf_utm.geometry.apply(line_azimuth)
    gdf["strike_deg"] = gdf["azimuth_deg"].apply(lambda a: a if a <= 180 else a - 180)

    for col in ("GZEEI",):
        if col in gdf.columns:
            gdf[col] = pd.to_numeric(gdf[col], errors="coerce")

    return gdf


def analyze_lzlpgdj002() -> pd.DataFrame:
    """分析深部断裂 LZLPGDJ002.WL。"""
    path = ROOT / "LZLPGDJ002.WL"
    if not path.exists():
        return pd.DataFrame()

    with Reader(path) as r:
        gdf = r.geodataframe.copy()
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    gdf_utm = gdf.to_crs(TARGET_CRS)

    gdf["length_m"] = gdf_utm.geometry.length
    gdf["length_km"] = gdf["length_m"] / 1000.0
    gdf["azimuth_deg"] = gdf_utm.geometry.apply(line_azimuth)
    gdf["strike_deg"] = gdf["azimuth_deg"].apply(lambda a: a if a <= 180 else a - 180)

    for col in ("KCDDEF", "GZEEL"):
        if col in gdf.columns:
            gdf[col] = pd.to_numeric(gdf[col], errors="coerce")

    return gdf


def summarize_descriptions(series: pd.Series, top_n: int = 3) -> str:
    """返回出现最频繁的非空描述。"""
    s = series.astype(str).replace("", np.nan).dropna()
    if s.empty:
        return "无"
    top = s.value_counts().head(top_n)
    return "； ".join(f"{v}（{c}次）" for v, c in top.items())


def main() -> int:
    lines = [
        "# 断裂产状类型梳理报告\n",
        "本报告汇总图幅内所有与断裂产状相关的数据，纠正此前将 `LDZOFBA003.WL` 简单当作唯一断裂产状来源的做法。\n",
        "\n## 数据来源总览\n",
        "| 文件 | 类型 | 记录数 | 数据性质 | 关键字段 |\n",
        "|------|------|--------|----------|----------|\n",
    ]

    gdf_map = {}

    # 1. LDZOFBA003.WL 实测断层
    gdf_map["LDZOFBA003"] = g003 = analyze_ldzofba003()
    lines.append(
        f"| `LDZOFBA003.WL` | 线 | {len(g003)} | 实测/填图断层迹线 | "
        f"`GZEAB` 断层编号、`GZEEB` 类型代码、`GZECE` 断面倾角、`GZEHG` 描述 |\n"
    )

    # 2. LYGREBA001.WL 解译断层
    gdf_map["LYGREBA001"] = g001 = analyze_lygreba001()
    lines.append(
        f"| `LYGREBA001.WL` | 线 | {len(g001)} | 遥感/地质解译断层 | "
        f"`GZEAB` 断层名、`GZEEBM`/`GZEGD` 类型代码、`GZEEI` 倾角、`GZEAD` 描述 |\n"
    )

    # 3. LZLPGDJ002.WL 深部断裂
    gdf_map["LZLPGDJ002"] = g002 = analyze_lzlpgdj002()
    lines.append(
        f"| `LZLPGDJ002.WL` | 线 | {len(g002)} | 深部/物探推断大断裂 | "
        f"`GZEAB` 断层名、`GZECC` 走向文字、`GZEEL` 倾角 |\n"
    )

    lines.append("\n")

    # 1. LDZOFBA003 类型统计
    lines.append("## 1. LDZOFBA003.WL 实测断层类型（`GZEEB`）\n")
    lines.append("| 代码 | 数量 | 占比 | 典型描述 | 有倾角记录数 | 平均倾角(°) | 平均走向(°) |\n")
    lines.append("|------|------|------|----------|--------------|-------------|-------------|\n")
    for code, group in g003.groupby("GZEEB"):
        count = len(group)
        pct = count / len(g003) * 100
        desc = summarize_descriptions(group["GZEHG"], top_n=1)
        dip_col = pd.to_numeric(group["GZECE"], errors="coerce")
        has_dip = (dip_col > 0).sum()
        avg_dip = dip_col[dip_col > 0].mean() if has_dip else np.nan
        avg_dip_str = f"{avg_dip:.1f}" if not np.isnan(avg_dip) else "-"
        avg_strike = group["strike_deg"].mean()
        lines.append(
            f"| `{code}` | {count} | {pct:.1f}% | {desc} | {has_dip} | "
            f"{avg_dip_str} | {avg_strike:.1f} |\n"
        )

    # 2. LYGREBA001 类型统计
    lines.append("\n## 2. LYGREBA001.WL 解译断层类型\n")
    lines.append("### 2.1 `GZEEBM` 与 `GZEGD` 对应关系\n")
    lines.append("| GZEEBM | GZEGD | 数量 | 典型遥感特征 | 有倾角记录数 | 平均 GZEEI |\n")
    lines.append("|--------|-------|------|--------------|--------------|------------|\n")
    for (ebm, egd), group in g001.groupby(["GZEEBM", "GZEGD"]):
        count = len(group)
        rs = summarize_descriptions(group["YGGBDG"], top_n=1)
        dip_col = pd.to_numeric(group["GZEEI"], errors="coerce")
        has_dip = (dip_col > 0).sum()
        avg_dip = dip_col[dip_col > 0].mean() if has_dip else np.nan
        avg_dip_str = f"{avg_dip:.1f}" if not np.isnan(avg_dip) else "-"
        lines.append(
            f"| `{ebm}` | `{egd}` | {count} | {rs} | {has_dip} | "
            f"{avg_dip_str} |\n"
        )

    lines.append("\n### 2.2 `GZEEJ` 代码分布\n")
    lines.append("| GZEEJ | 数量 | 对应 GZEEBM | 对应 GZEGD |\n")
    lines.append("|-------|------|-------------|------------|\n")
    for code, group in g001.groupby("GZEEJ"):
        ebm_counts = group["GZEEBM"].value_counts().to_dict()
        egd_counts = group["GZEGD"].value_counts().to_dict()
        ebm_str = ", ".join(f"{k}({v})" for k, v in ebm_counts.items())
        egd_str = ", ".join(f"{k}({v})" for k, v in egd_counts.items())
        lines.append(f"| `{code}` | {len(group)} | {ebm_str} | {egd_str} |\n")

    lines.append("\n### 2.3 命名断层统计\n")
    named = g001[g001["GZEAB"].astype(str).str.strip() != ""]
    lines.append("| 断层名称 | 记录数 | GZEEBM | GZEGD | 描述 |\n")
    lines.append("|----------|--------|--------|-------|------|\n")
    for name, group in named.groupby("GZEAB"):
        ebm = ", ".join(group["GZEEBM"].unique())
        egd = ", ".join(group["GZEGD"].unique())
        desc = summarize_descriptions(group["GZEAD"], top_n=1)
        lines.append(f"| {name} | {len(group)} | {ebm} | {egd} | {desc} |\n")

    # 3. LZLPGDJ002 深部断裂
    lines.append("\n## 3. LZLPGDJ002.WL 深部断裂\n")
    lines.append("| 断层名称 | 走向文字 | 长度(km) | 走向(°) | GZEEL |\n")
    lines.append("|----------|----------|----------|---------|-------|\n")
    for _, row in g002.iterrows():
        lines.append(
            f"| {row['GZEAB']} | {row['GZECC']} | {row['length_km']:.2f} | "
            f"{row['strike_deg']:.1f} | {row['GZEEL']} |\n"
        )

    # 4. 整体对比
    lines.append("\n## 4. 各数据源走向对比\n")
    for name, gdf in gdf_map.items():
        if gdf.empty:
            continue
        strikes = gdf["strike_deg"].dropna()
        lines.append(f"- `{name}.WL`：走向范围 {strikes.min():.1f}°–{strikes.max():.1f}°，平均 {strikes.mean():.1f}°\n")

    # 5. 渲染建议
    lines.append("\n## 5. 对断裂产状渲染的修正建议\n")
    lines.append("此前方案仅依据 `LDZOFBA003.WL` 的 `GZECE` 在断层线右侧画短垂线，存在以下问题：\n")
    lines.append("1. **未区分断层类型**：`GZEEB`/`GZEEBM`/`GZEGD` 才是断层类型代码，应据此绘制正断层、逆断层、走滑断层等标准符号。\n")
    lines.append("2. **倾向侧不能默认右侧**：倾角符号应置于断层真实倾向侧，而非沿迹线前进方向的右侧。\n")
    lines.append("3. **数据来源不唯一**：除 `LDZOFBA003.WL` 实测断层外，还有 `LYGREBA001.WL` 解译断层和 `LZLPGDJ002.WL` 深部断裂，应分别渲染。\n")
    lines.append("4. **缺倾向字段**：`LDZOFBA003.WL` 的 `GZECD` 全部为空，`LYGREBA001.WL` 亦无明确倾向字段，需由图例或地质描述推断，或仅绘制类型符号而不标倾角。\n")

    # 保存报告
    out_md = ROOT / "fault_attitude_types_report.md"
    out_md.write_text("".join(lines), encoding="utf-8")

    # 保存合并 CSV
    combined = []
    for name, gdf in gdf_map.items():
        if gdf.empty:
            continue
        df = gdf.copy()
        df["source_file"] = name + ".WL"
        # 统一类型字段
        if "GZEEB" in df.columns:
            df["type_code"] = df["GZEEB"]
        elif "GZEEBM" in df.columns:
            df["type_code"] = df["GZEEBM"]
        else:
            df["type_code"] = ""
        combined.append(df)

    if combined:
        out_csv = ROOT / "fault_attitude_types.csv"
        pd.concat(combined, ignore_index=True).to_csv(out_csv, index=False, encoding="utf-8-sig")
        print(f"Saved: {out_csv}")

    print(f"Saved: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
