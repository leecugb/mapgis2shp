#!/usr/bin/env python3
"""梳理库尔干幅地质图的地质单元代号，生成代号目录及说明。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import geopandas as gpd
import pandas as pd

from pymapgis import Reader

ROOT = Path(__file__).parent
OUT_MD = ROOT / "geological_unit_codes_catalog.md"
OUT_JSON = ROOT / "geological_unit_codes_catalog.json"

LAYER_ORDER = ["LDZOFBB004", "LDZOFBB001", "LDZOFBB002", "LDZOFBB003"]

# 年代/岩性键到可读中文名称的映射
def period_name(key: str) -> str:
    names = {
        "Qh": "全新统",
        "Qp": "更新统",
        "QpQh": "更新统—全新统",
        "N1": "下新统（中新统）",
        "N2": "上新统",
        "E1": "古新统",
        "E2": "始新统",
        "E3": "渐新统",
        "K1": "下白垩统",
        "K2": "上白垩统",
        "J1": "下侏罗统",
        "J2": "中侏罗统",
        "J3": "上侏罗统",
        "T1": "下三叠统",
        "T2": "中三叠统",
        "T3": "上三叠统",
        "P1": "下二叠统",
        "P2": "上二叠统",
        "P3": "上二叠统",
        "C1": "下石炭统",
        "C2": "上石炭统",
        "CP": "石炭—二叠系",
        "D1": "下泥盆统",
        "D2": "中泥盆统",
        "D3": "上泥盆统",
        "S1": "下志留统",
        "S2": "中志留统",
        "S3": "上志留统",
        "S4": "顶志留统",
        "S3-4": "上—顶志留统",
        "Pt1": "下元古界",
        "Pt2": "中元古界",
        "Pt3": "上元古界",
        "Ch": "长城纪/造山纪",
        "Nh": "南华纪",
        "Z": "震旦纪",
        "Qb": "青白口纪",
        "Ar3": "新太古代",
        "Ar2": "中太古代",
        "Ar1": "古太古代",
        "Ar0": "始太古代",
        "Hd": "冥古宙",
        "EK": "白垩—古近系",
    }
    return names.get(key, key)


def rock_type_name(key: str) -> str:
    if "acid_intermediate" in key:
        return "酸性—中酸性侵入岩"
    if "neutral" in key:
        return "中性侵入岩"
    if "basic" in key:
        return "基性侵入岩"
    if "alkaline" in key:
        return "碱性侵入岩"
    if "ultrabasic" in key:
        return "超基性侵入岩"
    return "侵入岩"


def load_layer(name: str) -> gpd.GeoDataFrame:
    for ext in ("WP", "WL", "WT"):
        path = ROOT / f"{name}.{ext}"
        if path.exists():
            with Reader(path) as r:
                return r.geodataframe.copy()
    raise FileNotFoundError(f"No file found for {name}")


def main() -> int:
    records: List[Dict] = []
    for name in LAYER_ORDER:
        gdf = load_layer(name)
        if gdf.empty:
            continue
        code_col = None
        for c in ("QDUECC", "QDUECD"):
            if c in gdf.columns:
                code_col = c
                break
        if code_col is None:
            continue

        gdf = gdf.copy()
        gdf["__code__"] = gdf[code_col].astype(str).str.strip()
        gdf["__area__"] = gdf.geometry.area

        for code, group in gdf.groupby("__code__"):
            # 收集中文名称与岩性描述
            names = []
            if "QDUECD" in group.columns:
                names += group["QDUECD"].dropna().astype(str).str.strip().unique().tolist()
            if "GCJFLP" in group.columns:
                names += group["GCJFLP"].dropna().astype(str).str.strip().unique().tolist()
            names = [n for n in names if n]

            # 解析年代键（复用 render_strict_standard_map 的逻辑）
            import render_strict_standard_map as rsm
            _, parsed_key = rsm.get_color(code)

            records.append(
                {
                    "layer": name,
                    "code": code,
                    "parsed_key": parsed_key,
                    "period_name": period_name(parsed_key) if not rsm.has_greek(code) else "",
                    "rock_type": rock_type_name(parsed_key) if rsm.has_greek(code) else "",
                    "count": int(len(group)),
                    "total_area_deg2": float(group["__area__"].sum()),
                    "max_area_deg2": float(group["__area__"].max()),
                    "descriptions": list(dict.fromkeys(names)),
                }
            )

    # 按年代排序：自定义顺序
    era_order = [
        "Qh", "Qp", "QpQh", "N2", "N1", "EK", "K2", "K1",
        "J3", "J2", "J1", "T3", "T2", "T1", "P2", "P1", "CP",
        "C2", "C1", "D3", "D2", "D1", "S3-4", "S4", "S3", "S2", "S1",
        "Pt1", "Ch", "intrusive",
    ]

    def sort_key(r: Dict):
        key = r["parsed_key"]
        if key in era_order:
            return (era_order.index(key), r["layer"], r["code"])
        # 侵入岩放到最后
        for prefix in ["acid_intermediate", "neutral", "basic", "alkaline", "ultrabasic"]:
            if prefix in key:
                return (len(era_order), prefix, r["code"])
        return (len(era_order) + 1, r["code"])

    records.sort(key=sort_key)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    # Markdown
    lines = [
        "# 库尔干幅（J43C001002）地质单元代号目录\n",
        "本目录按年代地层与岩性整理项目中的地质单元代号。\n",
    ]

    current_era = None
    for r in records:
        era_label = r["period_name"] or r["rock_type"]
        if era_label != current_era:
            lines.append(f"## {era_label}\n")
            current_era = era_label
            lines.append("| 图层 | 原始代号 | 解析键 | 要素数 | 总面积(deg²) | 中文名称/岩性描述 |")
            lines.append("|------|----------|--------|--------|--------------|-------------------|")

        desc = "；".join(r["descriptions"][:3]) if r["descriptions"] else "-"
        lines.append(
            f"| {r['layer']} | `{r['code']}` | `{r['parsed_key']}` | {r['count']} | "
            f"{r['total_area_deg2']:.6f} | {desc} |"
        )

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Saved: {OUT_MD} ({len(records)} units)")
    print(f"Saved: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
