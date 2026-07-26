#!/usr/bin/env python3
"""详细解析 MapGIS 矢量文件内容。

输出：
- parsed_content.json：每个文件的头信息、字段定义、前 N 条要素的属性和几何坐标
- parsed_content.txt：人类可读的文本摘要
"""

from __future__ import annotations

import glob
import json
import warnings
from pathlib import Path
from typing import Any, Dict, List

warnings.filterwarnings("ignore")

import numpy as np
from shapely.geometry import mapping

from pymapgis import Reader


def _coords_summary(geom: Any, max_points: int = 10) -> Dict[str, Any]:
    """将 shapely 几何对象转为可序列化的坐标摘要。"""
    if geom is None or geom.is_empty:
        return {"type": "Empty", "coords": None}

    geom_type = geom.geom_type
    coords = mapping(geom)

    if geom_type == "Point":
        return {"type": geom_type, "coords": list(geom.coords)[0]}

    if geom_type == "LineString":
        pts = list(geom.coords)
        return {
            "type": geom_type,
            "total_points": len(pts),
            "coords": pts[:max_points],
            "truncated": len(pts) > max_points,
        }

    if geom_type in ("Polygon", "MultiPolygon"):
        # 对复杂面仅返回坐标摘要
        return {
            "type": geom_type,
            "wkt": geom.wkt[:500],
            "wkt_truncated": len(geom.wkt) > 500,
        }

    return {"type": geom_type, "wkt": geom.wkt[:500]}


def parse_file(path: str, max_features: int = 5) -> Dict[str, Any]:
    """读取单个 MapGIS 文件并返回详细内容。"""
    result: Dict[str, Any] = {"path": path}
    try:
        with Reader(path) as r:
            result["shape_type"] = r.shapeType
            result["feature_count"] = len(r)
            result["crs_wkt"] = r.crs.to_wkt() if r.crs else None
            result["bbox"] = r.bbox.tolist() if r.bbox is not None else None
            result["fields"] = [
                {"name": name, "type": type_name, "length": length}
                for name, type_name, length in r.fields
            ]

            features: List[Dict[str, Any]] = []
            gdf = r.geodataframe
            for idx, row in gdf.head(max_features).iterrows():
                attrs = row.drop("geometry", errors="ignore").to_dict()
                # 处理 numpy 类型与日期类型，确保可 JSON 序列化
                clean_attrs: Dict[str, Any] = {}
                for k, v in attrs.items():
                    if isinstance(v, (np.integer, np.floating)):
                        clean_attrs[k] = v.item()
                    elif isinstance(v, np.bool_):
                        clean_attrs[k] = bool(v)
                    elif hasattr(v, "isoformat"):
                        clean_attrs[k] = v.isoformat()
                    else:
                        clean_attrs[k] = v

                geom = row["geometry"]
                features.append({
                    "index": int(idx),
                    "attributes": clean_attrs,
                    "geometry": _coords_summary(geom),
                })
            result["features"] = features
            result["sample_limit"] = max_features

    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def build_text_report(report: List[Dict[str, Any]]) -> str:
    """将解析结果转为可读文本。"""
    lines: List[str] = ["# MapGIS 矢量文件详细内容解析", ""]

    for item in report:
        lines.append(f"## {item['path']}")
        if "error" in item:
            lines.append(f"错误：{item['error']}")
            lines.append("")
            continue

        lines.append(f"类型：{item['shape_type']}")
        lines.append(f"要素数：{item['feature_count']}")
        lines.append(f"边界框：{item['bbox']}")
        lines.append("字段定义：")
        for f in item["fields"]:
            lines.append(f"  - {f['name']} ({f['type']}, 长度 {f['length']})")
        lines.append("")
        lines.append(f"前 {item['sample_limit']} 条要素详情：")

        for feat in item["features"]:
            lines.append(f"### 记录 #{feat['index']}")
            lines.append("属性：")
            for k, v in feat["attributes"].items():
                lines.append(f"  {k}: {v}")
            geom = feat["geometry"]
            lines.append("几何：")
            lines.append(f"  类型：{geom['type']}")
            if geom.get("coords") is not None:
                lines.append(f"  坐标：{geom['coords']}")
                if geom.get("truncated"):
                    lines.append("  （坐标已截断，仅显示前若干节点）")
            if geom.get("total_points") is not None:
                lines.append(f"  总节点数：{geom['total_points']}")
            if geom.get("wkt"):
                lines.append(f"  WKT：{geom['wkt']}")
                if geom.get("wkt_truncated"):
                    lines.append("  （WKT 已截断）")
            lines.append("")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    files = sorted(glob.glob("*.WT") + glob.glob("*.WL") + glob.glob("*.WP"))
    if not files:
        print("当前目录未找到 *.WT / *.WL / *.WP 文件。")
        return 0

    print(f"正在详细解析 {len(files)} 个文件...")
    report: List[Dict[str, Any]] = [parse_file(f, max_features=5) for f in files]

    json_path = "parsed_content.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"JSON 详细内容已保存：{json_path}")

    txt_path = "parsed_content.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(build_text_report(report))
    print(f"文本详细内容已保存：{txt_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
