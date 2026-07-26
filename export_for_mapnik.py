#!/usr/bin/env python3
"""为 Mapnik 渲染导出矢量图层 GeoJSON。

运行后会生成 data/mapnik/ 目录，包含 Mapnik 样式文件引用的全部数据源：
- geology_polygons.geojson      带 fill 色的地质面
- overlay_polygons.geojson      断裂带/构造岩浆岩带边界（面）
- inferred_boundaries.geojson   推断/解译面边界
- water_polygons.geojson        水系面
- water_lines.geojson           水系线
- structural_lines.geojson      构造线（含 layer 字段区分样式）
- attitudes.geojson             产状点
- unit_labels.geojson           地质代号注记
- water_labels.geojson          水系注记

坐标系：EPSG:3857（Web Mercator），与 MBTiles/Mapnik 默认切片网格一致。
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import geopandas as gpd
import pandas as pd

from render_strict_standard_map import load_and_prepare_layers

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent
OUT_DIR = ROOT / "data" / "mapnik"
TARGET_CRS = "EPSG:3857"


def _sanitize_for_mapnik(text: str) -> str:
    """移除 Mapnik 不易直接渲染的箭头与部分希腊字母，保留可读文本。

    注意：这会导致上下标、希腊字母地质符号丢失；生产环境建议用 SVG/Shield
    或客户端渲染替代。
    """
    s = str(text).strip()
    # 去掉箭头控制符
    s = re.sub(r"[→↓↑]", "", s)
    # 将 # 控制码替换为空格
    s = s.replace("#", " ")
    # 简单替换常见希腊字母为拉丁近似（可选）
    greek_map = {
        "γ": "g", "δ": "d", "β": "b", "υ": "u", "η": "e", "ν": "v",
        "τ": "t", "α": "a", "ο": "o", "φ": "ph", "ρ": "r", "π": "p",
        "μ": "m", "ε": "e", "ψ": "ps", "χ": "ch", "ι": "i",
    }
    for ch, rep in greek_map.items():
        s = s.replace(ch, rep)
    return s.strip("-.")


def export_for_mapnik() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading layers in {TARGET_CRS}...")
    prepared = load_and_prepare_layers(ROOT, TARGET_CRS)

    # 1. 地质面（带 fill 颜色）
    polys = prepared.geology_all.copy()
    if "__color__" in polys.columns:
        polys = polys.rename(columns={"__color__": "fill"})
    if "__key__" in polys.columns:
        polys = polys.rename(columns={"__key__": "key"})
    polys.to_file(OUT_DIR / "geology_polygons.geojson", driver="GeoJSON", encoding="utf-8")
    print(f"  geology_polygons: {len(polys)} features")

    # 2. 非地层构造面（仅边界）
    overlay_parts = []
    for name, gdf in prepared.overlay_gdfs:
        gdf = gdf.copy()
        gdf["layer"] = name
        overlay_parts.append(gdf[["layer", "geometry"]])
    if overlay_parts:
        gpd.GeoDataFrame(pd.concat(overlay_parts, ignore_index=True), crs=TARGET_CRS).to_file(
            OUT_DIR / "overlay_polygons.geojson", driver="GeoJSON", encoding="utf-8"
        )
        print(f"  overlay_polygons: {len(overlay_parts)} features")

    # 3. 推断/解译面边界
    if prepared.inferred_gdfs:
        inferred = gpd.GeoDataFrame(
            pd.concat([gdf[["geometry"]] for gdf in prepared.inferred_gdfs], ignore_index=True),
            crs=TARGET_CRS,
        )
        inferred.to_file(OUT_DIR / "inferred_boundaries.geojson", driver="GeoJSON", encoding="utf-8")
        print(f"  inferred_boundaries: {len(inferred)} features")

    # 4. 水系
    water_polys = []
    water_lines = []
    if "LDLYAAE002" in prepared.water and not prepared.water["LDLYAAE002"].empty:
        gdf = prepared.water["LDLYAAE002"].copy()
        gdf["layer"] = "LDLYAAE002"
        water_polys.append(gdf[["layer", "geometry"]])
    for name in ("LDLYAAE001", "LDLYAAA005"):
        if name in prepared.water and not prepared.water[name].empty:
            gdf = prepared.water[name].copy()
            gdf["layer"] = name
            water_lines.append(gdf[["layer", "geometry"]])
    if water_polys:
        gpd.GeoDataFrame(pd.concat(water_polys, ignore_index=True), crs=TARGET_CRS).to_file(
            OUT_DIR / "water_polygons.geojson", driver="GeoJSON", encoding="utf-8"
        )
        print(f"  water_polygons: {len(water_polys)} features")
    if water_lines:
        gpd.GeoDataFrame(pd.concat(water_lines, ignore_index=True), crs=TARGET_CRS).to_file(
            OUT_DIR / "water_lines.geojson", driver="GeoJSON", encoding="utf-8"
        )
        print(f"  water_lines: {len(water_lines)} features")

    # 5. 构造线
    line_parts = []
    for name, gdf in prepared.line_layers.items():
        gdf = gdf.copy()
        gdf["layer"] = name
        line_parts.append(gdf[["layer", "geometry"]])
    if line_parts:
        lines = gpd.GeoDataFrame(pd.concat(line_parts, ignore_index=True), crs=TARGET_CRS)
        lines.to_file(OUT_DIR / "structural_lines.geojson", driver="GeoJSON", encoding="utf-8")
        print(f"  structural_lines: {len(lines)} features")

    # 6. 产状点
    if prepared.attitudes is not None and not prepared.attitudes.empty:
        att = prepared.attitudes.copy()
        for col in ("GZBBAB", "GZBBAC", "GZBBAD", "GZBBGA"):
            if col not in att.columns:
                att[col] = None
        att = att[["GZBBAB", "GZBBAC", "GZBBAD", "GZBBGA", "geometry"]]
        att.to_file(OUT_DIR / "attitudes.geojson", driver="GeoJSON", encoding="utf-8")
        print(f"  attitudes: {len(att)} features")

    # 7. 地质代号注记
    if prepared.unit_labels is not None and not prepared.unit_labels.empty:
        labels = prepared.unit_labels.copy()
        col = prepared.unit_label_col
        labels["label"] = labels[col].astype(str).str.strip().apply(_sanitize_for_mapnik)
        labels[["label", "geometry"]].to_file(
            OUT_DIR / "unit_labels.geojson", driver="GeoJSON", encoding="utf-8"
        )
        print(f"  unit_labels: {len(labels)} features")

    # 8. 水系注记
    if prepared.water_labels is not None and not prepared.water_labels.empty and "NAME" in prepared.water_labels.columns:
        wl = prepared.water_labels.copy()
        wl["label"] = wl["NAME"].astype(str).str.strip()
        wl[["label", "geometry"]].to_file(
            OUT_DIR / "water_labels.geojson", driver="GeoJSON", encoding="utf-8"
        )
        print(f"  water_labels: {len(wl)} features")

    print(f"\nExported to {OUT_DIR}")


if __name__ == "__main__":
    raise SystemExit(export_for_mapnik())
