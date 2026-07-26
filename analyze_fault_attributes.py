#!/usr/bin/env python3
"""梳理 LDZOFBA003.WL 中断层的产状与属性，生成报告。"""

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


def main() -> int:
    path = ROOT / "LDZOFBA003.WL"
    if not path.exists():
        print(f"[error] {path} not found")
        return 1

    with Reader(path) as r:
        gdf = r.geodataframe.copy()
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    gdf_utm = gdf.to_crs(TARGET_CRS)

    # 几何属性
    gdf["length_m"] = gdf_utm.geometry.length
    gdf["length_km"] = gdf["length_m"] / 1000.0
    gdf["azimuth_deg"] = gdf_utm.geometry.apply(line_azimuth)
    # 走向取 0–180（线段方向相反等价）
    gdf["strike_deg"] = gdf["azimuth_deg"].apply(lambda a: a if a <= 180 else a - 180)

    # 字段重命名为可读名称（根据数值推断，待图例确认）
    rename = {
        "GZEAB": "fault_code",
        "KCDDEF": "numeric_attr",
        "GZEEB": "fault_type_code",
        "GZECE": "dip_angle",
        "GZEHG": "description",
        "GZAG": "confidence_code",
        "GZEEE": "activity_era_code",
        "GZELD": "occurrence_code",
    }
    for old, new in rename.items():
        if old in gdf.columns:
            gdf[new] = gdf[old]

    numeric_cols = ["length_m", "length_km", "azimuth_deg", "strike_deg"]
    if "numeric_attr" in gdf.columns:
        gdf["numeric_attr"] = pd.to_numeric(gdf["numeric_attr"], errors="coerce")
        numeric_cols.append("numeric_attr")
    if "dip_angle" in gdf.columns:
        gdf["dip_angle"] = pd.to_numeric(gdf["dip_angle"], errors="coerce")
        numeric_cols.append("dip_angle")

    # 输出完整属性表
    out_csv = ROOT / "fault_attributes.csv"
    out_cols = ["ID", "fault_code", "fault_type_code", "dip_angle", "numeric_attr",
                "length_m", "length_km", "azimuth_deg", "strike_deg",
                "confidence_code", "activity_era_code", "occurrence_code", "description"]
    out_cols = [c for c in out_cols if c in gdf.columns]
    gdf[out_cols].to_csv(out_csv, index=False, encoding="utf-8-sig")

    # Markdown 报告
    lines = [
        "# 库尔干幅断层属性梳理报告\n",
        f"- 来源图层：`LDZOFBA003.WL`\n",
        f"- 总断层数：{len(gdf)}\n",
        f"- 投影坐标系：{TARGET_CRS}（UTM Zone 43N）\n",
        "\n## 1. 字段含义推断\n",
        "| 字段 | 推断含义 | 说明 |\n",
        "|------|----------|------|\n",
        "| `GZEAB` | 断层编号/名称 | 如 `F9`、`F48`、`F50`，空白为未命名断层 |\n",
        "| `KCDDEF` | 断层迹线长度（km） | 对 `F9`/`F48`/`F50` 与几何分段总长度高度吻合 |\n",
        "| `GZEEB` | 断层类型代码 | `01`/`05`/`31`/`04`/`41`/`28`/`07`/`18`/`16` |\n",
        "| `GZECE` | 断面倾角 | 0°–80°，0 可能表示近水平/未知 |\n",
        "| `GZEHG` | 断层描述 | 中文描述，如切割地层、岩性、构造岩等 |\n",
        "| `GZAG` | 可靠程度代码 | `101` 为主，`103` 少量 |\n",
        "| `GZEEE` | 活动时代代码 | `101`/`102`/`103` |\n",
        "| `GZELD` | 产状/形态代码 | `101`/`109`/`103`/`104` |\n",
        "\n## 2. 类型代码统计\n",
    ]

    type_counts = gdf["fault_type_code"].astype(str).value_counts().sort_index()
    lines.append("| 断层类型代码 | 数量 |\n|--------------|------|\n")
    for code, count in type_counts.items():
        lines.append(f"| `{code}` | {count} |\n")

    lines.append("\n## 3. 断层类型代码与典型描述\n")
    lines.append("| 类型代码 | 数量 | 典型描述（出现最多） |\n|----------|------|----------------------|\n")
    for code, group in gdf.groupby("fault_type_code"):
        top_desc = group["description"].astype(str).value_counts().index[0]
        lines.append(f"| `{code}` | {len(group)} | {top_desc} |\n")

    lines.append("\n## 4. 断层编号统计\n")
    code_counts = gdf["fault_code"].astype(str).replace("", "未命名").value_counts()
    lines.append("| 断层编号 | 数量 | 总长度(km) | 平均倾角(°) |\n|----------|------|------------|-------------|\n")
    for code, group in gdf.groupby("fault_code"):
        display = code if code else "未命名"
        avg_dip = group["dip_angle"].mean() if "dip_angle" in group.columns else np.nan
        lines.append(f"| `{display}` | {len(group)} | {group['length_km'].sum():.2f} | {avg_dip:.1f} |\n")

    lines.append("\n## 5. 倾角统计\n")
    if "dip_angle" in gdf.columns:
        dips = gdf["dip_angle"].dropna()
        non_zero = dips[dips > 0]
        lines.append(f"- 有倾角记录数：{len(non_zero)} / {len(gdf)}\n")
        lines.append(f"- 倾角范围：{non_zero.min():.0f}° – {non_zero.max():.0f}°\n")
        lines.append(f"- 平均倾角：{non_zero.mean():.1f}°\n")
        lines.append(f"- 中位数倾角：{non_zero.median():.1f}°\n")

    lines.append("\n## 6. 断层走向统计\n")
    strikes = gdf["strike_deg"].dropna()
    lines.append(f"- 走向范围：{strikes.min():.1f}° – {strikes.max():.1f}°\n")
    lines.append(f"- 平均走向：{strikes.mean():.1f}°\n")
    lines.append(f"- 主要优势走向：{strikes.quantile(0.25):.0f}°–{strikes.quantile(0.75):.0f}°（四分位）\n")

    lines.append(f"\n## 7. 详细数据\n\n见 [`fault_attributes.csv`](fault_attributes.csv)。\n")

    out_md = ROOT / "fault_attributes_report.md"
    out_md.write_text("".join(lines), encoding="utf-8")

    print(f"Saved: {out_md}")
    print(f"Saved: {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
