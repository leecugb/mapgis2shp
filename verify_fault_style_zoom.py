#!/usr/bin/env python3
"""放大渲染典型区域，专门核实 DZ/T 0179 表22 正断层（barbs）与逆/冲断层（三角齿）的几何样式。"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import render_strict_standard_map as rsm
from render_faults import draw_faults_with_styles, load_fault_styles

ROOT = Path(__file__).parent
TARGET_CRS = "EPSG:32643"
OUT_PNG = ROOT / "fault_style_zoom_verify.png"


def main() -> int:
    line_files = {
        "LDZOFBA003": dict(color="#e41a1c", linewidth=0.7, linestyle="-", label="实测断层"),
    }
    line_layers = rsm.load_layers(ROOT, list(line_files.keys()), target_crs=TARGET_CRS)
    gdf = line_layers.get("LDZOFBA003")
    if gdf is None or gdf.empty:
        print("[error] LDZOFBA003 not found")
        return 1

    # 只保留有 GZEEB 类型代码且为 05（正断层）或 31（逆/冲断层）的记录
    gdf = gdf[gdf["GZEEB"].isin(["05", "31"])].copy()
    if gdf.empty:
        print("[error] no 05/31 faults found")
        return 1

    # 选取记录较密集的区域作为示例
    bounds = gdf.total_bounds
    cx, cy = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
    width = (bounds[2] - bounds[0]) * 0.35
    height = (bounds[3] - bounds[1]) * 0.35
    zoom_bounds = (
        cx - width / 2, cy - height / 2,
        cx + width / 2, cy + height / 2,
    )

    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_aspect("equal")
    ax.set_xlim(zoom_bounds[0], zoom_bounds[2])
    ax.set_ylim(zoom_bounds[1], zoom_bounds[3])
    ax.set_facecolor("white")

    # 绘制基线（红色实线）
    styles = load_fault_styles(ROOT)
    base = styles["sources"]["LDZOFBA003"]["base_style"] if styles else {"color": "#e41a1c", "linewidth": 0.7}
    gdf.plot(ax=ax, color=base["color"], linewidth=base["linewidth"], linestyle="-")

    # 绘制符号
    draw_faults_with_styles(ax, {"LDZOFBA003": gdf}, ROOT)

    ax.set_title("DZ/T 0179 表22 正/逆断层几何样式核实（局部放大）", fontsize=12)
    plt.axis("off")
    plt.savefig(OUT_PNG, dpi=300, bbox_inches="tight", pad_inches=0.1)
    plt.close()
    print(f"Saved: {OUT_PNG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
