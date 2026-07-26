#!/usr/bin/env python3
"""梳理库尔干幅地质单元代号与 DZ/T 0179 标准色的最终映射表。

输出：
- geological_unit_color_mapping_final.json
- geological_unit_color_mapping_final.csv
- geological_unit_color_mapping_final.md

逻辑：
1. 读取所有含地质代号的MapGIS面图层（LDZOFBB004/001/002/003）。
2. 复用 render_strict_standard_map.py 的 get_color() 解析规则，为每个唯一
   代号分配标准色。
3. 统计每个代号的要素数与总面积，按年代地层/岩性大类排序。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import geopandas as gpd
import numpy as np

from pymapgis import Reader

import render_strict_standard_map as rsm

ROOT = Path(__file__).parent

LAYER_ORDER = ["LDZOFBB004", "LDZOFBB001", "LDZOFBB002", "LDZOFBB003"]

OUT_JSON = ROOT / "geological_unit_color_mapping_final.json"
OUT_CSV = ROOT / "geological_unit_color_mapping_final.csv"
OUT_MD = ROOT / "geological_unit_color_mapping_final.md"

ERA_ORDER = [
    "Qh", "Qp", "QpQh", "N2", "N1", "EK", "K2", "K1",
    "J3", "J2", "J1", "T3", "T2", "T1", "P2", "P1", "CP",
    "C2", "C1", "D3", "D2", "D1", "S3-4", "S4", "S3", "S2", "S1",
    "Pt3", "Pt2", "Pt1", "Ch", "Nh", "Z", "Qb", "Ar3", "Ar2", "Ar1", "Ar0", "Hd",
]

ROCK_TYPE_ORDER = [
    "acid_intermediate", "neutral", "basic", "ultrabasic", "alkaline",
]


def load_layer(name: str) -> Optional[gpd.GeoDataFrame]:
    for ext in ("WP", "WL", "WT"):
        path = ROOT / f"{name}.{ext}"
        if path.exists():
            with Reader(path) as r:
                return r.geodataframe.copy()
    return None


def sort_key(record: Dict) -> Tuple:
    key = record["key"]

    # 侵入岩：按 rock_type:era 形式
    if ":" in key:
        rock, era = key.split(":", 1)
        rock_idx = ROCK_TYPE_ORDER.index(rock) if rock in ROCK_TYPE_ORDER else len(ROCK_TYPE_ORDER)
        era_idx = ERA_ORDER.index(era) if era in ERA_ORDER else len(ERA_ORDER)
        return (len(ERA_ORDER), rock_idx, era_idx, record["layer"], record["code"])

    # 年代地层
    if key in ERA_ORDER:
        return (ERA_ORDER.index(key), 0, 0, record["layer"], record["code"])

    return (len(ERA_ORDER) + 1, 0, 0, record["layer"], record["code"])


def main() -> int:
    records: List[Dict] = []
    for layer_name in LAYER_ORDER:
        gdf = load_layer(layer_name)
        if gdf is None or gdf.empty:
            print(f"[skip] {layer_name}: empty or missing")
            continue

        code_col = None
        for c in ("QDUECC", "QDUECD"):
            if c in gdf.columns:
                code_col = c
                break
        if code_col is None:
            print(f"[skip] {layer_name}: no code column")
            continue

        gdf = gdf.copy()
        gdf["__code__"] = gdf[code_col].astype(str).str.strip()

        # 面积（原始坐标系下，与 catalog_geological_units.py 保持一致）
        gdf["__area__"] = gdf.geometry.area

        for code, group in gdf.groupby("__code__"):
            rgb, key = rsm.get_color(code)
            hex_color = rsm.rgb_to_hex(rgb)
            records.append(
                {
                    "layer": layer_name,
                    "code": code,
                    "key": key or "unknown",
                    "R": int(round(rgb[0] * 255)),
                    "G": int(round(rgb[1] * 255)),
                    "B": int(round(rgb[2] * 255)),
                    "color": hex_color,
                    "count": int(len(group)),
                    "total_area_deg2": float(group["__area__"].sum()),
                    "max_area_deg2": float(group["__area__"].max()),
                }
            )

    records.sort(key=sort_key)

    # JSON
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"Saved: {OUT_JSON} ({len(records)} units)")

    # CSV
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["layer", "code", "key", "R", "G", "B", "HEX", "count"],
        )
        writer.writeheader()
        for r in records:
            writer.writerow(
                {
                    "layer": r["layer"],
                    "code": r["code"],
                    "key": r["key"],
                    "R": r["R"],
                    "G": r["G"],
                    "B": r["B"],
                    "HEX": r["color"],
                    "count": r["count"],
                }
            )
    print(f"Saved: {OUT_CSV}")

    # Markdown
    lines = [
        "# 库尔干幅地质单元及 DZ/T 0179 配色映射表（最终版）\n",
        "| 图层 | 原始代号 | 解析键 | R | G | B | HEX | 要素数 |",
        "|------|----------|--------|---|---|---|-----|--------|",
    ]
    for r in records:
        lines.append(
            f"| {r['layer']} | `{r['code']}` | {r['key']} | "
            f"{r['R']} | {r['G']} | {r['B']} | {r['color']} | {r['count']} |"
        )

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Saved: {OUT_MD}")

    # 打印未知/兜底色统计
    unknown = [r for r in records if r["key"] == "unknown"]
    fallback = [r for r in records if "fallback" in r["key"]]
    if unknown:
        print(f"\n[warn] {len(unknown)} units with unknown color:")
        for r in unknown:
            print(f"  - {r['layer']} `{r['code']}`")
    if fallback:
        print(f"\n[info] {len(fallback)} units using fallback color:")
        for r in fallback:
            print(f"  - {r['layer']} `{r['code']}` -> {r['key']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
