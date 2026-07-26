#!/usr/bin/env python3
"""简化渲染：分别输出地质-建造构造专题（LDZO）和水系专题（LDLY）两张图。"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# 本地 src 目录提供 pymapgis.rendering（IR、符号引擎等）
sys.path.insert(0, str(Path(__file__).parent / "src"))
from pymapgis import Reader

# 从主渲染器复用准备逻辑
import render_strict_standard_map as rssm

warnings_ignored = False

ROOT = Path(__file__).parent
TARGET_CRS = rssm.TARGET_CRS


def _load_single_layer(root: Path, name: str, target_crs: str) -> Optional[gpd.GeoDataFrame]:
    """加载单个 MapGIS 图层并投影。"""
    for ext in ("WP", "WL", "WT"):
        candidate = root / f"{name}.{ext}"
        if candidate.exists():
            try:
                with Reader(candidate) as r:
                    gdf = r.geodataframe.copy()
                if gdf.crs is None:
                    gdf = gdf.set_crs("EPSG:4326")
                return gdf.to_crs(target_crs)
            except Exception as exc:
                print(f"[skip] {candidate}: {exc}")
    return None


def _resolve_unit_colors(gdf: gpd.GeoDataFrame, code_col: str) -> gpd.GeoDataFrame:
    """为地质面图层解析填充颜色。"""
    colors, keys = [], []
    for code in gdf[code_col].dropna().astype(str).str.strip():
        style = rssm._IR.resolve_unit_style(code)
        rgb = np.array(style["fill"]["rgb"]) / 255.0
        key = style["fill"].get("key") or "unknown"
        colors.append(rssm.rgb_to_hex(rgb))
        keys.append(key)
    gdf = gdf.copy()
    gdf["__color__"] = colors
    gdf["__key__"] = keys
    return gdf


@dataclass
class ThemeLayers:
    """专题图图层集合。"""
    geology: Optional[gpd.GeoDataFrame]
    overlays: List[Tuple[str, gpd.GeoDataFrame]]
    lines: Dict[str, gpd.GeoDataFrame]
    attitudes: Optional[gpd.GeoDataFrame]
    attitude_labels: Optional[gpd.GeoDataFrame]
    unit_labels: Optional[gpd.GeoDataFrame]
    unit_label_col: Optional[str]
    water_labels: Optional[gpd.GeoDataFrame]
    bounds: Tuple[float, float, float, float]


def _total_bounds(*gdfs: Optional[gpd.GeoDataFrame]) -> Tuple[float, float, float, float]:
    """合并多个 GeoDataFrame 的总边界。"""
    valid = [g for g in gdfs if g is not None and not g.empty]
    if not valid:
        return (0.0, 0.0, 1.0, 1.0)
    bounds = np.array([g.total_bounds for g in valid])
    return (
        float(bounds[:, 0].min()),
        float(bounds[:, 1].min()),
        float(bounds[:, 2].max()),
        float(bounds[:, 3].max()),
    )


def prepare_ldzo_theme(root: Path, target_crs: str) -> ThemeLayers:
    """准备地质-建造构造专题（LDZO）图层。"""
    # 地质面：变质基底 → 主要地层 → 补充地层 → 侵入岩 → 构造面/岩浆岩带边界
    geo_names = ["LDZOFBB004", "LDZOFBB001", "LDZOFBB002", "LDZOFBB003", "LDZOFBB009", "LDZOFBB010"]
    colored_gdfs: List[gpd.GeoDataFrame] = []
    overlays: List[Tuple[str, gpd.GeoDataFrame]] = []

    for name in geo_names:
        gdf = _load_single_layer(root, name, target_crs)
        if gdf is None or gdf.empty:
            continue
        code_col = None
        for c in ("QDUECC", "QDUECD"):
            if c in gdf.columns:
                code_col = c
                break
        if code_col is None:
            overlays.append((name, gdf))
        else:
            colored_gdfs.append(_resolve_unit_colors(gdf, code_col))

    geology = None
    if colored_gdfs:
        geology = gpd.GeoDataFrame(pd.concat(colored_gdfs, ignore_index=True), crs=colored_gdfs[0].crs)

    # 构造线
    line_styles = {
        "LDZOFBA002": dict(color="#333333", linewidth=0.3, label="地质界线"),
        "LDZOFBA003": dict(color="#e41a1c", linewidth=0.7, label="断层"),
        "LDZOFBA005": dict(color="#4daf4a", linewidth=1.0, linestyle="--", label="褶皱轴"),
    }
    lines: Dict[str, gpd.GeoDataFrame] = {}
    for name, style in line_styles.items():
        gdf = _load_single_layer(root, name, target_crs)
        if gdf is not None and not gdf.empty:
            gdf.attrs["_style"] = style
            lines[name] = gdf

    # 产状点与注记
    attitudes = _load_single_layer(root, "LDZOFBA016", target_crs)
    raw_labels = _load_single_layer(root, "LDZOFBB099", target_crs)
    attitude_labels = None
    if raw_labels is not None and not raw_labels.empty and "CHFCED" in raw_labels.columns:
        attitude_labels = raw_labels[
            raw_labels["CHFCED"].astype(str).str.strip().str.len() > 0
        ].copy()
        if "CHFCEC" in attitude_labels.columns:
            attitude_labels = attitude_labels[
                attitude_labels["CHFCEC"].astype(str).str.strip() == "产状"
            ]

    # 地质代号注记（优先重构）
    unit_labels = rssm._load_reconstructed_labels(root, target_crs)
    unit_label_col = "code"
    if unit_labels is None:
        unit_labels = raw_labels
        if unit_labels is not None and not unit_labels.empty and "CHFCED" in unit_labels.columns:
            unit_labels = unit_labels[
                unit_labels["CHFCED"].astype(str).str.strip().str.len() > 0
            ].copy()
            if "CHFCEC" in unit_labels.columns:
                unit_labels = unit_labels[
                    unit_labels["CHFCEC"].astype(str).str.strip() == "代号"
                ]
            unit_label_col = "CHFCED"
        else:
            unit_label_col = None

    bounds = _total_bounds(geology, *lines.values(), attitudes)

    return ThemeLayers(
        geology=geology,
        overlays=overlays,
        lines=lines,
        attitudes=attitudes,
        attitude_labels=attitude_labels,
        unit_labels=unit_labels,
        unit_label_col=unit_label_col,
        water_labels=None,
        bounds=bounds,
    )


def prepare_ldly_theme(root: Path, target_crs: str) -> ThemeLayers:
    """准备水系专题（LDLY）图层。"""
    # 水系面
    water_area = _load_single_layer(root, "LDLYAAE002", target_crs)

    # 水系线
    line_styles = {
        "LDLYAAE001": dict(color="#1f78b4", linewidth=0.6, label="河流/水系线"),
        "LDLYAAA005": dict(color="#1f78b4", linewidth=0.4, label="水系边界"),
    }
    lines: Dict[str, gpd.GeoDataFrame] = {}
    for name, style in line_styles.items():
        gdf = _load_single_layer(root, name, target_crs)
        if gdf is not None and not gdf.empty:
            gdf.attrs["_style"] = style
            lines[name] = gdf

    # 水系注记
    water_labels = _load_single_layer(root, "LDLYAAI002", target_crs)

    bounds = _total_bounds(water_area, *lines.values(), water_labels)

    return ThemeLayers(
        geology=water_area,
        overlays=[],
        lines=lines,
        attitudes=None,
        attitude_labels=None,
        unit_labels=None,
        unit_label_col=None,
        water_labels=water_labels,
        bounds=bounds,
    )


def _filter_by_bounds(gdf: Optional[gpd.GeoDataFrame], bounds: Tuple[float, float, float, float],
                      margin: float = 0.0) -> Optional[gpd.GeoDataFrame]:
    if gdf is None or gdf.empty:
        return gdf
    minx, miny, maxx, maxy = bounds
    try:
        return gdf.cx[minx - margin : maxx + margin, miny - margin : maxy + margin]
    except Exception:
        return gdf


def draw_theme_content(ax, theme: ThemeLayers, title: str, margin_m: float = 2000.0):
    """绘制专题图内容。"""
    ax.set_aspect("equal")

    minx, miny, maxx, maxy = theme.bounds
    dx, dy = maxx - minx, maxy - miny
    bounds = (
        minx - dx * 0.02,
        miny - dy * 0.02,
        maxx + dx * 0.02,
        maxy + dy * 0.02,
    )
    minx, miny, maxx, maxy = bounds
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)

    # 1. 面状图层
    if theme.geology is not None and not theme.geology.empty:
        geo = _filter_by_bounds(theme.geology, bounds, margin_m)
        if not geo.empty:
            if "__color__" in geo.columns:
                # 地质面
                geo.plot(
                    ax=ax,
                    color=geo["__color__"].values,
                    edgecolor="#555555",
                    linewidth=0.15,
                    alpha=1.0,
                )
            else:
                # 水系面
                geo.plot(ax=ax, color="#a6cee3", edgecolor="#1f78b4", linewidth=0.25, alpha=0.85)

    # 2. 覆盖层边界
    for name, ogdf in theme.overlays:
        ogdf = _filter_by_bounds(ogdf, bounds, margin_m)
        if ogdf is None or ogdf.empty:
            continue
        if name == "LDZOFBB009":
            ogdf.plot(ax=ax, facecolor="none", edgecolor="#d95f02", linewidth=0.6, linestyle="-")
        elif name == "LDZOFBB010":
            ogdf.plot(ax=ax, facecolor="none", edgecolor="#8c510a", linewidth=0.5, linestyle="--")

    # 3. 线状图层
    for name, gdf in theme.lines.items():
        gdf = _filter_by_bounds(gdf, bounds, margin_m)
        if gdf is None or gdf.empty:
            continue
        style = gdf.attrs.get("_style", dict(color="#555555", linewidth=0.3))
        gdf.plot(ax=ax, **style)

    # 4. 断层符号（仅 LDZO 专题且存在 LDZOFBA003）
    if "LDZOFBA003" in theme.lines:
        rssm.draw_faults_with_styles(ax, theme.lines, ROOT)

    # 5. 产状符号（仅 LDZO）
    if theme.attitudes is not None:
        att = _filter_by_bounds(theme.attitudes, bounds, margin_m)
        att_labels = _filter_by_bounds(theme.attitude_labels, bounds, margin_m)
        rssm.draw_attitudes(ax, att, labels=att_labels)

    # 6. 地质代号注记（仅 LDZO）
    if theme.unit_labels is not None and theme.unit_label_col is not None:
        sub = _filter_by_bounds(theme.unit_labels, bounds, margin_m)
        if sub is not None and not sub.empty:
            for x, y, label in zip(sub.geometry.x, sub.geometry.y, sub[theme.unit_label_col]):
                try:
                    display_label = rssm.format_label(str(label).strip())
                except Exception:
                    display_label = str(label).strip()
                ax.text(
                    x, y, display_label, fontsize=4, color="black",
                    ha="center", va="center",
                    path_effects=[rssm.pe.withStroke(linewidth=2, foreground="white")],
                )

    # 7. 水系注记（仅 LDLY）
    if theme.water_labels is not None and not theme.water_labels.empty and "NAME" in theme.water_labels.columns:
        sub = _filter_by_bounds(theme.water_labels, bounds, margin_m)
        if sub is not None and not sub.empty:
            sub = sub[sub["NAME"].astype(str).str.strip().str.len() > 0]
            for x, y, label in zip(sub.geometry.x, sub.geometry.y, sub["NAME"]):
                ax.text(
                    x, y, str(label).strip(), fontsize=5, color="#1f78b4",
                    ha="center", va="center", style="italic",
                    path_effects=[rssm.pe.withStroke(linewidth=2, foreground="white")],
                )

    ax.set_title(title, fontsize=14, pad=12)
    ax.set_xlabel("东向 (m)", fontsize=10)
    ax.set_ylabel("北向 (m)", fontsize=10)


def _add_decorations(ax, theme: ThemeLayers, legend_elems):
    """添加比例尺、指北针、图例。"""
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    rssm.add_scale_bar(
        ax,
        (xlim[0] + (xlim[1] - xlim[0]) * 0.05, ylim[0] + (ylim[1] - ylim[0]) * 0.05),
        length_km=20,
    )
    rssm.add_north_arrow(
        ax,
        (xlim[1] - (xlim[1] - xlim[0]) * 0.08, ylim[1] - (ylim[1] - ylim[0]) * 0.08),
    )
    if legend_elems:
        ax.legend(handles=legend_elems, loc="lower right", fontsize=8, framealpha=0.92)


def main() -> int:
    # 地质-建造构造专题
    print("Preparing LDZO theme...")
    ldzo = prepare_ldzo_theme(ROOT, TARGET_CRS)
    fig, ax = plt.subplots(figsize=(14, 13))
    draw_theme_content(ax, ldzo, "1:250000 库尔干幅 地质-建造构造专题图（LDZO）")
    ldzo_legend = [
        rssm.Line2D([0], [0], color="#e41a1c", lw=0.7, linestyle="-", label="断层"),
        rssm.Line2D([0], [0], color="#333333", lw=1, label="地质界线"),
        rssm.Line2D([0], [0], color="#4daf4a", lw=1.5, linestyle="--", label="褶皱轴"),
    ]
    _add_decorations(ax, ldzo, ldzo_legend)
    out_ldzo = ROOT / "kurgan_thematic_ldzo.png"
    plt.savefig(out_ldzo, dpi=200, bbox_inches="tight", pad_inches=0.2)
    print(f"Saved: {out_ldzo}")
    plt.close()

    # 水系专题
    print("Preparing LDLY theme...")
    ldly = prepare_ldly_theme(ROOT, TARGET_CRS)
    fig, ax = plt.subplots(figsize=(14, 13))
    draw_theme_content(ax, ldly, "1:250000 库尔干幅 水系专题图（LDLY）")
    ldly_legend = [
        rssm.Line2D([0], [0], color="#1f78b4", lw=1, label="河流/水系线"),
    ]
    _add_decorations(ax, ldly, ldly_legend)
    out_ldly = ROOT / "kurgan_thematic_ldly.png"
    plt.savefig(out_ldly, dpi=200, bbox_inches="tight", pad_inches=0.2)
    print(f"Saved: {out_ldly}")
    plt.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
