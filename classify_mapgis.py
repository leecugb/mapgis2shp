#!/usr/bin/env python3
"""梳理并分类 MapGIS 矢量文件内容。

输出：
- classification_report.md：分类汇总报告
- classification_report.json：结构化分类数据
"""

from __future__ import annotations

import glob
import json
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

warnings.filterwarnings("ignore")

import pandas as pd
from pymapgis import Reader


def _gb_category(gb_code: str) -> str:
    """根据常见 GB 编码前缀推断要素类别。"""
    if not gb_code or not str(gb_code).strip():
        return "未分类"
    gb = str(gb_code).strip()
    prefix_map = {
        "1": "水系",
        "2": "水系",
        "3": "居民地",
        "4": "交通",
        "5": "管线",
        "6": "境界与政区",
        "7": "地貌与土质",
        "8": "植被",
        "9": "地名/注记",
    }
    return prefix_map.get(gb[0], "其他")


def _field_prefixes(fields: List[str]) -> Set[str]:
    """提取字段名的字母前缀（2~4 位），用于专题识别。"""
    prefixes: Set[str] = set()
    for f in fields:
        s = ""
        for ch in f.upper():
            if ch.isalpha():
                s += ch
            else:
                break
        if 2 <= len(s) <= 6:
            prefixes.add(s)
    return prefixes


def _infer_theme(name: str, fields: List[str], sample_attrs: Dict[str, Any]) -> str:
    """综合文件名、字段和属性样例推断数据主题。"""
    name_u = name.upper()
    fld_set = {f.upper() for f in fields}
    prefixes = _field_prefixes(fields)

    # 根据文件名关键字
    if any(k in name_u for k in ["HYD", "LY", "水系", "河", "RIVER", "湖", "WATER"]):
        return "水系"
    if any(k in name_u for k in ["RES", "居民", "SETTLEMENT", "TOWN", "VILLAGE"]):
        return "居民地"
    if any(k in name_u for k in ["ROAD", "RAIL", "交通", "道路", "铁路", "BOU", "行政区", "境界", "BOUNDARY"]):
        return "交通/境界"
    if any(k in name_u for k in ["TER", "地貌", "TERRAIN", "DEM", "ELEV", "CONTOUR"]):
        return "地貌"
    if any(k in name_u for k in ["VEG", "植被", "FOREST", "WOOD", "PLANT"]):
        return "植被"
    if any(k in name_u for k in ["ANO", "注记", "LABEL", "POINT", "TXT"]):
        return "地名/注记"

    # 根据字段关键字（通用基础地理）
    if {"HYDC", "TN", "NAME"} & fld_set:
        return "水系"
    if {"GB"} & fld_set and sample_attrs:
        gb = str(sample_attrs.get("GB", "")).strip()
        cat = _gb_category(gb)
        if cat != "未分类":
            return cat

    # 根据 MapGIS 地质图常见字段前缀判断
    # 参考：DD=地层，YS=岩石，GZ=构造，MD=矿产，KC=矿产勘查，QDI/QDUE=区调，
    #      WT=水文地质，SWN=水文，CH=测绘，HT=话题/专题，PKIGJ=图幅信息
    geo_prefixes = {
        "GZ": "地质构造",
        "DD": "地层",
        "YS": "岩石/岩性",
        "QDI": "区调",
        "QDUE": "区调",
        "MD": "矿产",
        "KC": "矿产勘查",
        "KWB": "矿产",
        "WT": "水文地质",
        "SWN": "水文地质",
        "CH": "测绘",
        "HT": "专题",
        "YG": "遥感",
        "GCJF": "空间基准",
        "GGAA": "地理",
        "GGDD": "地理",
        "PKIGJ": "图幅信息",
    }
    matched_themes = []
    for prefix, theme in geo_prefixes.items():
        if any(p.startswith(prefix) for p in prefixes):
            matched_themes.append(theme)
    if matched_themes:
        # 如果同时匹配多个，取最具体的（前缀越长优先级越高）
        return matched_themes[0]

    # 点状要素且字段少，判为地名/注记
    if "NAME" in fld_set and len(fields) <= 7:
        return "地名/注记"

    return "未分类"


def analyze_file(path: str) -> Dict[str, Any]:
    """读取单个文件并返回分类信息。"""
    result = {"path": path}
    try:
        with Reader(path) as r:
            result["shape_type"] = r.shapeType
            result["feature_count"] = len(r)
            result["fields"] = [name for name, _, _ in r.fields]
            result["field_types"] = {name: t for name, t, _ in r.fields}

            gdf = r.geodataframe
            sample = gdf.drop(columns="geometry", errors="ignore").head(3).to_dict(
                orient="records"
            )
            result["attribute_samples"] = sample

            # 统计 GB 编码分布
            if "GB" in gdf.columns:
                gb_counts = gdf["GB"].value_counts().head(10).to_dict()
                result["gb_distribution"] = {str(k): int(v) for k, v in gb_counts.items()}
            else:
                result["gb_distribution"] = {}

            # 统计 NAME 样例
            if "NAME" in gdf.columns:
                names = gdf["NAME"].dropna().astype(str)
                names = names[names.str.strip() != ""]
                result["name_samples"] = names.head(10).tolist()
            else:
                result["name_samples"] = []

            result["theme"] = _infer_theme(path, result["fields"], sample[0] if sample else {})

    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def build_classification_report(items: List[Dict[str, Any]]) -> str:
    """生成 Markdown 分类报告。"""
    lines: List[str] = ["# MapGIS 矢量文件内容分类梳理", ""]

    # 1. 按几何类型统计
    geom_groups: Dict[str, List[str]] = defaultdict(list)
    for item in items:
        if "error" not in item:
            geom_groups[item["shape_type"]].append(item["path"])

    lines.extend(["## 一、按几何类型分类", ""])
    for geom_type, files in sorted(geom_groups.items()):
        lines.append(f"### {geom_type}（{len(files)} 个文件）")
        for f in files:
            lines.append(f"- {f}")
        lines.append("")

    # 2. 按主题分类
    theme_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in items:
        if "error" not in item:
            theme_groups[item["theme"]].append(item)

    lines.extend(["## 二、按数据主题分类", ""])
    for theme, group in sorted(theme_groups.items(), key=lambda x: -len(x[1])):
        lines.append(f"### {theme}（{len(group)} 个文件）")
        for item in group:
            lines.append(
                f"- **{item['path']}** | {item['shape_type']} | "
                f"要素数 {item['feature_count']} | 字段 {', '.join(item['fields'])}"
            )
        lines.append("")

    # 3. 字段共性分析
    all_fields: Set[str] = set()
    field_files: Dict[str, List[str]] = defaultdict(list)
    for item in items:
        if "error" in item:
            continue
        for f in item["fields"]:
            all_fields.add(f)
            field_files[f].append(item["path"])

    lines.extend(["## 三、字段共性分析", ""])
    lines.append(f"所有文件共出现 {len(all_fields)} 个不同字段名。")
    lines.append("")
    lines.append("### 通用字段（出现在 ≥50% 文件中）")
    threshold = len(items) * 0.5
    common_fields = {f: fs for f, fs in field_files.items() if len(fs) >= threshold}
    for f, fs in sorted(common_fields.items(), key=lambda x: -len(x[1])):
        lines.append(f"- `{f}`：出现在 {len(fs)} 个文件中")
    lines.append("")

    lines.append("### 专用字段（仅出现在 1 个文件中）")
    unique_fields = {f: fs for f, fs in field_files.items() if len(fs) == 1}
    for f, fs in sorted(unique_fields.items()):
        lines.append(f"- `{f}`：{fs[0]}")
    lines.append("")

    # 4. 每个文件详情卡片
    lines.extend(["## 四、文件详情卡片", ""])
    for item in items:
        if "error" in item:
            lines.append(f"### {item['path']} — 解析失败")
            lines.append(f"错误：{item['error']}")
            lines.append("")
            continue

        lines.append(f"### {item['path']}")
        lines.append(f"- 主题：{item['theme']}")
        lines.append(f"- 几何类型：{item['shape_type']}")
        lines.append(f"- 要素数：{item['feature_count']}")
        lines.append(f"- 字段：{', '.join(item['fields'])}")
        if item.get("gb_distribution"):
            lines.append("- GB 编码分布：")
            for gb, cnt in item["gb_distribution"].items():
                lines.append(f"  - `{gb}`：{cnt} 条")
        if item.get("name_samples"):
            samples = "、".join(item["name_samples"][:8])
            lines.append(f"- NAME 样例：{samples}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    files = sorted(glob.glob("*.WT") + glob.glob("*.WL") + glob.glob("*.WP"))
    if not files:
        print("当前目录未找到 *.WT / *.WL / *.WP 文件。")
        return 0

    print(f"正在分类梳理 {len(files)} 个文件...")
    items = [analyze_file(f) for f in files]

    json_path = "classification_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"分类 JSON 已保存：{json_path}")

    md_path = "classification_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_classification_report(items))
    print(f"分类报告已保存：{md_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
