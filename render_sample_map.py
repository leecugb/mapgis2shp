#!/usr/bin/env python3
"""使用 pymapgis + matplotlib 渲染库尔干幅地质图示例 PNG。"""

from __future__ import annotations

import math
import warnings
from pathlib import Path
from typing import Dict, Optional

import geopandas as gpd
import matplotlib.font_manager as fm
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

from pymapgis import Reader

warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent

# 优先使用 Noto Sans CJK SC；如未索引则手动添加字体文件
FONT_PATH = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
if FONT_PATH.exists():
    try:
        fm.fontManager.addfont(str(FONT_PATH))
    except Exception:
        pass

plt.rcParams["font.sans-serif"] = [
    "Noto Sans CJK SC",
    "Noto Sans CJK JP",
    "SimHei",
    "WenQuanYi Micro Hei",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False


def load_layers(root: Path) -> Dict[str, gpd.GeoDataFrame]:
    """加载当前目录下所有 MapGIS 矢量文件。"""
    layers: Dict[str, gpd.GeoDataFrame] = {}
    files = []
    for ext in ("WT", "WL", "WP"):
        files.extend(sorted(root.glob(f"*.{ext}")))
    for f in files:
        name = f.stem
        try:
            with Reader(f) as r:
                layers[name] = r.geodataframe.copy()
        except Exception as exc:
            print(f"[skip] {f}: {exc}")
    return layers


def add_scale_bar(ax, xy, length_km: int = 20, color: str = "black"):
    """在 ax 左下角添加公里比例尺。"""
    lat = xy[1]
    km_per_deg_lon = 111.32 * math.cos(math.radians(lat))
    deg = length_km / km_per_deg_lon
    x0, y0 = xy
    ax.plot([x0, x0 + deg], [y0, y0], color=color, linewidth=2.5, solid_capstyle="butt")
    ax.plot([x0, x0], [y0 - 0.015, y0 + 0.015], color=color, linewidth=1.5)
    ax.plot([x0 + deg, x0 + deg], [y0 - 0.015, y0 + 0.015], color=color, linewidth=1.5)
    ax.text(
        x0 + deg / 2,
        y0 + 0.025,
        f"{length_km} km",
        ha="center",
        va="bottom",
        fontsize=8,
        color=color,
    )


def add_north_arrow(ax, xy, size: float = 0.18):
    """在 ax 右上角添加指北针。"""
    x, y = xy
    ax.annotate(
        "N",
        xy=(x, y + size * 0.7),
        xytext=(x, y - size * 0.3),
        arrowprops=dict(arrowstyle="-|>", color="black", lw=2),
        fontsize=12,
        ha="center",
        va="bottom",
        color="black",
        fontweight="bold",
    )


def plot_layer(gdf: Optional[gpd.GeoDataFrame], ax, **kwargs) -> bool:
    if gdf is None or gdf.empty:
        return False
    gdf.plot(ax=ax, **kwargs)
    return True


def main() -> int:
    print("Loading MapGIS files...")
    layers = load_layers(ROOT)
    print(f"Loaded {len(layers)} layers")

    fig, ax = plt.subplots(figsize=(14, 13))
    ax.set_aspect("equal")

    # 自动计算图幅范围
    bounds = np.array([gdf.total_bounds for gdf in layers.values() if not gdf.empty])
    if bounds.size:
        minx, miny = bounds[:, 0].min(), bounds[:, 1].min()
        maxx, maxy = bounds[:, 2].max(), bounds[:, 3].max()
        dx, dy = maxx - minx, maxy - miny
        ax.set_xlim(minx - dx * 0.02, maxx + dx * 0.02)
        ax.set_ylim(miny - dy * 0.02, maxy + dy * 0.02)

    # ------------------------------------------------------------------
    # 1. 地质面色（地层、岩体、断裂带、构造岩浆岩带）
    # ------------------------------------------------------------------
    geology_files = [
        ("LDZOFBB001", "QDUECC", "tab20"),   # 岩石地层单位
        ("LDZOFBB002", "QDUECC", "tab20b"),  # 火山岩/特殊地层
        ("LDZOFBB003", "QDUECC", "Set3"),    # 岩脉/火山岩
        ("LDZOFBB004", "QDUECC", "Pastel1"), # 变质岩/岩群
        ("LDZOFBB009", "DDDEO", "Dark2"),    # 断裂构造带
        ("LDZOFBB010", "DDCDLV", "Paired"),  # 构造岩浆岩带
    ]
    for name, col, cmap in geology_files:
        gdf = layers.get(name)
        if not plot_layer(gdf, ax):
            continue
        if col in gdf.columns:
            # 重绘以带颜色（先绘一遍是为了处理空几何的兼容性）
            gdf.plot(
                ax=ax,
                column=col,
                cmap=cmap,
                edgecolor="#555555",
                linewidth=0.15,
                alpha=0.85,
                legend=False,
            )
        else:
            gdf.plot(ax=ax, color="#e0e0e0", edgecolor="#555555", linewidth=0.15, alpha=0.85)

    # ------------------------------------------------------------------
    # 2. 物探/深部推断面（只画边界，不填色）
    # ------------------------------------------------------------------
    inferred_files = [
        "LHCPGDAC05",
        "LHCPGDAC08",
        "LHCPGDAC11",
        "LZLPGDJ004",
        "LZLPGDJ006",
        "LZLPGDJ009",
    ]
    for name in inferred_files:
        plot_layer(
            layers.get(name),
            ax,
            facecolor="none",
            edgecolor="#7b3294",
            linewidth=1.0,
            linestyle="--",
            alpha=0.75,
        )

    # ------------------------------------------------------------------
    # 3. 水系
    # ------------------------------------------------------------------
    plot_layer(
        layers.get("LDLYAAE002"),
        ax,
        color="#a6cee3",
        edgecolor="#1f78b4",
        linewidth=0.25,
        alpha=0.85,
    )

    # ------------------------------------------------------------------
    # 4. 主要线状要素
    # ------------------------------------------------------------------
    line_styles = {
        "LDZOFBA002": dict(color="#333333", linewidth=0.3, label="地质界线"),
        "LDZOFBA003": dict(color="#e41a1c", linewidth=0.7, label="断层"),
        "LDZOFBA005": dict(color="#4daf4a", linewidth=1.0, linestyle="--", label="褶皱轴"),
        "LDLYAAE001": dict(color="#1f78b4", linewidth=0.5, label="河流"),
        "LDLYAAA005": dict(color="#1f78b4", linewidth=0.3, linestyle=":", label="水系线"),
        "LHCPGDAC01": dict(color="#ff7f00", linewidth=0.6, linestyle="-.", label="物探推断断裂"),
        "LYGREBA001": dict(color="#984ea3", linewidth=0.6, linestyle=":", label="遥感解译线"),
        "LYGREBA004": dict(color="#984ea3", linewidth=0.6, linestyle="-.", label="遥感环形构造"),
        "LZLPGDJ002": dict(color="#e41a1c", linewidth=1.2, linestyle="--", label="深部大断裂"),
        "LHTQGTA001": dict(color="#377eb8", linewidth=0.8, linestyle="-.", label="地球化学界线"),
    }
    for name, style in line_styles.items():
        plot_layer(layers.get(name), ax, **style)

    # 辅助线（花纹线、引线、图廓线等）
    for name in (
        "LFZYBCT002",
        "LDZOFBB098",
        "LFZYBAA002",
        "LFZYBAB002",
        "LHCPGDAC06",
        "LHCPGDAC09",
        "LHCPGDAC12",
    ):
        plot_layer(layers.get(name), ax, color="#999999", linewidth=0.2, alpha=0.5)

    # ------------------------------------------------------------------
    # 5. 点状符号
    # ------------------------------------------------------------------
    # 产状点
    plot_layer(layers.get("LDZOFBA016"), ax, marker="^", color="black", markersize=6, alpha=0.7)

    # 构造花纹点（数量太大，抽稀显示）
    gdf = layers.get("LFZYBCT001")
    if gdf is not None and not gdf.empty:
        sub = gdf.sample(min(400, len(gdf)), random_state=42)
        sub.plot(ax=ax, marker=".", color="#444444", markersize=2, alpha=0.5)

    # ------------------------------------------------------------------
    # 6. 注记
    # ------------------------------------------------------------------
    # 地质代号注记
    gdf = layers.get("LDZOFBB099")
    if gdf is not None and not gdf.empty and "CHFCED" in gdf.columns:
        sub = gdf[gdf["CHFCED"].astype(str).str.strip().str.len() > 0]
        if len(sub) > 600:
            sub = sub.sample(600, random_state=1)
        for x, y, label in zip(sub.geometry.x, sub.geometry.y, sub["CHFCED"]):
            ax.text(
                x,
                y,
                str(label).strip(),
                fontsize=4,
                color="black",
                ha="center",
                va="center",
                path_effects=[pe.withStroke(linewidth=2, foreground="white")],
            )

    # 水系名称注记
    gdf = layers.get("LDLYAAI002")
    if gdf is not None and not gdf.empty and "NAME" in gdf.columns:
        sub = gdf[gdf["NAME"].astype(str).str.strip().str.len() > 0]
        for x, y, label in zip(sub.geometry.x, sub.geometry.y, sub["NAME"]):
            ax.text(
                x,
                y,
                str(label).strip(),
                fontsize=5,
                color="#1f78b4",
                ha="center",
                va="center",
                style="italic",
                path_effects=[pe.withStroke(linewidth=2, foreground="white")],
            )

    # ------------------------------------------------------------------
    # 7. 图幅整饰
    # ------------------------------------------------------------------
    ax.set_title("1:250000 库尔干幅（J43C001002）地质图示例", fontsize=15, pad=12)
    ax.set_xlabel("经度", fontsize=10)
    ax.set_ylabel("纬度", fontsize=10)

    xlim = ax.get_xlim()
    ylim = ax.get_ylim()

    # 比例尺
    add_scale_bar(
        ax,
        (xlim[0] + (xlim[1] - xlim[0]) * 0.05, ylim[0] + (ylim[1] - ylim[0]) * 0.05),
        length_km=20,
    )
    # 指北针
    add_north_arrow(
        ax,
        (xlim[1] - (xlim[1] - xlim[0]) * 0.08, ylim[1] - (ylim[1] - ylim[0]) * 0.08),
    )

    # 图例
    legend_elems = [
        Line2D([0], [0], color="#e41a1c", lw=1.5, label="断层"),
        Line2D([0], [0], color="#4daf4a", lw=1.5, linestyle="--", label="褶皱轴"),
        Line2D([0], [0], color="#333333", lw=1, label="地质界线"),
        Line2D([0], [0], color="#1f78b4", lw=1, label="河流/水系"),
        Line2D([0], [0], color="#ff7f00", lw=1, linestyle="-.", label="物探推断断裂"),
        Line2D([0], [0], color="#984ea3", lw=1, linestyle="-.", label="遥感解译构造"),
        Line2D([0], [0], color="#7b3294", lw=1, linestyle="--", label="推断地质体面边界"),
    ]
    ax.legend(handles=legend_elems, loc="lower right", fontsize=8, framealpha=0.92)

    out_path = ROOT / "kurgan_sample_map.png"
    plt.savefig(out_path, dpi=200, bbox_inches="tight", pad_inches=0.2)
    print(f"Saved: {out_path}")
    plt.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
