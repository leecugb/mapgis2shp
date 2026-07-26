#!/usr/bin/env python3
"""使用 DZ/T 0179 标准色渲染库尔干幅地质图。"""

from __future__ import annotations

import json
import math
import re
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import geopandas as gpd
import matplotlib.font_manager as fm
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

from pymapgis import Reader
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent

# 中文字体
FONT_PATH = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
if FONT_PATH.exists():
    try:
        fm.fontManager.addfont(str(FONT_PATH))
    except Exception:
        pass
plt.rcParams["font.sans-serif"] = [
    "Noto Sans CJK SC", "Noto Sans CJK JP", "SimHei",
    "WenQuanYi Micro Hei", "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False

GREEK_LETTERS = "γδβυηνταοφρπμε"

# 加载标准色
with open(ROOT / "dz_t_0179_colors.json", encoding="utf-8") as f:
    _COLORS = json.load(f)

PERIOD_COLORS = {k: np.array(v) / 255.0 for k, v in _COLORS["period"].items()}
CROSS_COLORS = {k: np.array(v) / 255.0 for k, v in _COLORS["cross_period"].items()}
INTRUSIVE_COLORS = {
    k: np.array(v) / 255.0 for k, v in _COLORS["intrusive_acid_intermediate"].items()
}
FALLBACK_IGNEOUS = np.array(_COLORS["fallback"]["igneous_no_age"]) / 255.0
FALLBACK_UNKNOWN = np.array(_COLORS["fallback"]["unknown"]) / 255.0


def normalize_code(code: str) -> str:
    """去掉箭头、上下标、小数点、连字符和希腊字母。"""
    s = str(code).strip()
    for ch in "→↓↑·.":
        s = s.replace(ch, "")
    s = s.replace("-", "")
    for ch in GREEK_LETTERS:
        s = s.replace(ch, "")
    return s


def has_greek(code: str) -> bool:
    return any(ch in str(code) for ch in GREEK_LETTERS)


def code_to_period(code: str) -> Optional[str]:
    """从 QDUECC/QDUECD 代号中提取年代地层关键字。"""
    s = normalize_code(code)

    # 跨时代地层优先匹配
    cross_patterns = [
        ("C2P1", "CP"),
        ("EK", "EK"),
        ("EN", "EN"),
        ("NQ", "NQ"),
        ("KE", "KE"),
        ("JK", "JK"),
        ("TJ", "TJ"),
        ("PT", "PT"),
        ("CP", "CP"),
        ("DC", "DC"),
        ("SD", "SD"),
        ("OS", "OS"),
        ("EO", "EO"),
        ("ZE", "ZE"),
        ("NhZ", "NhZ"),
        ("Ar3Pt1", "Ar3Pt1"),
    ]
    for pat, key in cross_patterns:
        if pat in s:
            return key

    # 正式地层单位，按精度从高到低匹配
    period_patterns = [
        "Qh", "Qp",
        "N2", "N1",
        "E3", "E2", "E1",
        "K2", "K1",
        "J3", "J2", "J1",
        "T3", "T2", "T1",
        "P3", "P2", "P1",
        "C2", "C1",
        "D3", "D2", "D1",
        "S3-4", "S4", "S3", "S2", "S1",
        "Pt3", "Pt2", "Pt1",
        "Ch",
    ]
    for pat in period_patterns:
        if pat in s:
            return pat
    return None


def rgb_to_hex(rgb: np.ndarray) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255)
    )


def get_color(code: str) -> Tuple[np.ndarray, Optional[str]]:
    """返回 RGB 三元组（0-1）和匹配的色键。"""
    period = code_to_period(code)
    is_intrusive = has_greek(code)

    if is_intrusive:
        if period and period in INTRUSIVE_COLORS:
            return INTRUSIVE_COLORS[period], period
        return FALLBACK_IGNEOUS, None

    if period:
        if period in CROSS_COLORS:
            return CROSS_COLORS[period], period
        if period in PERIOD_COLORS:
            return PERIOD_COLORS[period], period

    return FALLBACK_UNKNOWN, None


def load_layers(root: Path, names: List[str]) -> Dict[str, gpd.GeoDataFrame]:
    layers: Dict[str, gpd.GeoDataFrame] = {}
    for name in names:
        path = None
        for ext in ("WP", "WL", "WT"):
            candidate = root / f"{name}.{ext}"
            if candidate.exists():
                path = candidate
                break
        if path is None:
            print(f"[skip] {name} not found")
            continue
        try:
            with Reader(path) as r:
                layers[name] = r.geodataframe.copy()
        except Exception as exc:
            print(f"[skip] {path}: {exc}")
    return layers


def add_scale_bar(ax, xy, length_km: int = 20, color: str = "black"):
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


def main() -> int:
    # 需要按标准色填充的地质面图层
    geology_layers = [
        "LDZOFBB001", "LDZOFBB002", "LDZOFBB003",
        "LDZOFBB004", "LDZOFBB009", "LDZOFBB010",
    ]

    print("Loading geology polygon layers...")
    layers = load_layers(ROOT, geology_layers)

    # 为每个面要素分配标准色
    colored_gdfs: List[gpd.GeoDataFrame] = []
    color_stats: Dict[str, int] = {}
    for name, gdf in layers.items():
        if gdf.empty:
            continue
        col = None
        for c in ("QDUECC", "QDUECD", "DDDEO", "DDCDLV"):
            if c in gdf.columns:
                col = c
                break
        if col is None:
            print(f"[warn] {name}: no code column found")
            continue

        colors = []
        keys = []
        for code in gdf[col].astype(str).str.strip():
            rgb, key = get_color(code)
            colors.append(rgb_to_hex(rgb))
            keys.append(key)
            color_stats[key] = color_stats.get(key, 0) + 1

        gdf = gdf.copy()
        gdf["__color__"] = colors
        gdf["__period__"] = keys
        colored_gdfs.append(gdf)

    if not colored_gdfs:
        print("No geology layers loaded.")
        return 1

    geology_all = gpd.GeoDataFrame(
        pd.concat(colored_gdfs, ignore_index=True), crs=colored_gdfs[0].crs
    )

    print("Color assignment summary:")
    for key, count in sorted(color_stats.items(), key=lambda x: -x[1]):
        print(f"  {key}: {count}")

    fig, ax = plt.subplots(figsize=(14, 13))
    ax.set_aspect("equal")

    bounds = np.array([gdf.total_bounds for gdf in layers.values() if not gdf.empty])
    minx, miny = bounds[:, 0].min(), bounds[:, 1].min()
    maxx, maxy = bounds[:, 2].max(), bounds[:, 3].max()
    dx, dy = maxx - minx, maxy - miny
    ax.set_xlim(minx - dx * 0.02, maxx + dx * 0.02)
    ax.set_ylim(miny - dy * 0.02, maxy + dy * 0.02)

    # 1. 标准色地质面
    geology_all.plot(
        ax=ax,
        color=geology_all["__color__"].values,
        edgecolor="#555555",
        linewidth=0.15,
        alpha=0.9,
    )

    # 2. 推断/解译面边界
    inferred = ["LHCPGDAC05", "LHCPGDAC08", "LHCPGDAC11", "LZLPGDJ004", "LZLPGDJ006", "LZLPGDJ009"]
    for name in inferred:
        gdf = load_layers(ROOT, [name]).get(name)
        if gdf is not None and not gdf.empty:
            gdf.plot(ax=ax, facecolor="none", edgecolor="#7b3294", linewidth=1.0, linestyle="--", alpha=0.75)

    # 3. 水系
    water_files = ["LDLYAAE002", "LDLYAAE001", "LDLYAAA005"]
    water_layers = load_layers(ROOT, water_files)
    if "LDLYAAE002" in water_layers:
        water_layers["LDLYAAE002"].plot(
            ax=ax, color="#a6cee3", edgecolor="#1f78b4", linewidth=0.25, alpha=0.85
        )
    for name in ("LDLYAAE001", "LDLYAAA005"):
        if name in water_layers:
            water_layers[name].plot(ax=ax, color="#1f78b4", linewidth=0.4)

    # 4. 构造线
    line_files = {
        "LDZOFBA002": dict(color="#333333", linewidth=0.3, label="地质界线"),
        "LDZOFBA003": dict(color="#e41a1c", linewidth=0.7, label="断层"),
        "LDZOFBA005": dict(color="#4daf4a", linewidth=1.0, linestyle="--", label="褶皱轴"),
        "LHCPGDAC01": dict(color="#ff7f00", linewidth=0.6, linestyle="-.", label="物探推断断裂"),
        "LYGREBA001": dict(color="#984ea3", linewidth=0.6, linestyle=":", label="遥感解译线"),
        "LYGREBA004": dict(color="#984ea3", linewidth=0.6, linestyle="-.", label="遥感环形构造"),
        "LZLPGDJ002": dict(color="#e41a1c", linewidth=1.2, linestyle="--", label="深部大断裂"),
        "LHTQGTA001": dict(color="#377eb8", linewidth=0.8, linestyle="-.", label="地球化学界线"),
    }
    line_layers = load_layers(ROOT, list(line_files.keys()))
    for name, style in line_files.items():
        gdf = line_layers.get(name)
        if gdf is not None and not gdf.empty:
            gdf.plot(ax=ax, **style)

    # 5. 产状点
    att = load_layers(ROOT, ["LDZOFBA016"]).get("LDZOFBA016")
    if att is not None and not att.empty:
        att.plot(ax=ax, marker="^", color="black", markersize=6, alpha=0.7)

    # 6. 注记
    labels = load_layers(ROOT, ["LDZOFBB099"]).get("LDZOFBB099")
    if labels is not None and not labels.empty and "CHFCED" in labels.columns:
        sub = labels[labels["CHFCED"].astype(str).str.strip().str.len() > 0]
        if len(sub) > 600:
            sub = sub.sample(600, random_state=1)
        for x, y, label in zip(sub.geometry.x, sub.geometry.y, sub["CHFCED"]):
            ax.text(
                x, y, str(label).strip(), fontsize=4, color="black",
                ha="center", va="center",
                path_effects=[pe.withStroke(linewidth=2, foreground="white")],
            )

    water_labels = load_layers(ROOT, ["LDLYAAI002"]).get("LDLYAAI002")
    if water_labels is not None and not water_labels.empty and "NAME" in water_labels.columns:
        sub = water_labels[water_labels["NAME"].astype(str).str.strip().str.len() > 0]
        for x, y, label in zip(sub.geometry.x, sub.geometry.y, sub["NAME"]):
            ax.text(
                x, y, str(label).strip(), fontsize=5, color="#1f78b4",
                ha="center", va="center", style="italic",
                path_effects=[pe.withStroke(linewidth=2, foreground="white")],
            )

    # 7. 图幅整饰
    ax.set_title("1:250000 库尔干幅（J43C001002）标准色地质图", fontsize=15, pad=12)
    ax.set_xlabel("经度", fontsize=10)
    ax.set_ylabel("纬度", fontsize=10)

    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    add_scale_bar(
        ax,
        (xlim[0] + (xlim[1] - xlim[0]) * 0.05, ylim[0] + (ylim[1] - ylim[0]) * 0.05),
        length_km=20,
    )
    add_north_arrow(
        ax,
        (xlim[1] - (xlim[1] - xlim[0]) * 0.08, ylim[1] - (ylim[1] - ylim[0]) * 0.08),
    )

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

    out_path = ROOT / "kurgan_standard_color_map.png"
    plt.savefig(out_path, dpi=200, bbox_inches="tight", pad_inches=0.2)
    print(f"Saved: {out_path}")
    plt.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
