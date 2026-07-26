#!/usr/bin/env python3
"""使用 pymapgis 批量分析当前目录下的 MapGIS 矢量文件（*.wl/*.wt/*.wp）。

输出：
- analysis_report.json：结构化汇总
- analysis_report.md：Markdown 表格报告
"""

from __future__ import annotations

import glob
import json
import warnings
from pathlib import Path
from typing import Any, Dict, List

warnings.filterwarnings("ignore")

import numpy as np

from pymapgis import Reader


def summarize_file(path: str) -> Dict[str, Any]:
    """读取单个 MapGIS 文件并返回内容摘要。"""
    result: Dict[str, Any] = {"path": path}
    try:
        with Reader(path) as r:
            result["shape_type"] = r.shapeType
            result["feature_count"] = len(r)
            result["fields"] = [
                {"name": name, "type": type_name, "length": length}
                for name, type_name, length in r.fields
            ]
            result["crs"] = r.crs.to_wkt() if r.crs else None
            result["bbox"] = r.bbox.tolist() if r.bbox is not None else None

            gdf = r.geodataframe
            geom_counts = gdf.geom_type.value_counts().to_dict()
            result["geometry_types"] = {str(k): int(v) for k, v in geom_counts.items()}
            result["invalid_count"] = int((~gdf.is_valid).sum())

            # 属性表样例（前 3 行），避免 JSON 序列化问题
            sample = gdf.drop(columns="geometry", errors="ignore").head(3)
            result["attribute_sample"] = sample.to_dict(orient="records")

            # 对点/线/面分别做简单几何统计
            if r.shapeType == "POINT":
                result["geometry_summary"] = "Point features"
            elif r.shapeType == "LINE":
                lengths = gdf.length
                result["geometry_summary"] = {
                    "total_length": float(lengths.sum()),
                    "mean_length": float(lengths.mean()),
                    "min_length": float(lengths.min()),
                    "max_length": float(lengths.max()),
                }
            elif r.shapeType == "POLYGON":
                areas = gdf.area
                result["geometry_summary"] = {
                    "total_area": float(areas.sum()),
                    "mean_area": float(areas.mean()),
                    "min_area": float(areas.min()),
                    "max_area": float(areas.max()),
                }
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def build_markdown(report: List[Dict[str, Any]]) -> str:
    """将 JSON 报告转为 Markdown 表格。"""
    lines: List[str] = [
        "# MapGIS 矢量文件内容分析",
        "",
        "| 文件 | 类型 | 要素数 | 几何类型 | 属性字段数 | 无效几何 | 边界框 |",
        "|------|------|--------|----------|------------|----------|--------|",
    ]
    for item in report:
        if "error" in item:
            lines.append(
                f"| {item['path']} | ERROR | - | - | - | - | {item['error']} |"
            )
            continue

        geom_str = "; ".join(
            f"{k}({v})" for k, v in item["geometry_types"].items()
        )
        bbox = item["bbox"]
        bbox_str = f"[{bbox[0]:.4f}, {bbox[1]:.4f}, {bbox[2]:.4f}, {bbox[3]:.4f}]" if bbox else "-"
        lines.append(
            f"| {item['path']} | {item['shape_type']} | {item['feature_count']} | "
            f"{geom_str} | {len(item['fields'])} | {item['invalid_count']} | {bbox_str} |"
        )

    lines.extend([
        "",
        "## 坐标系信息",
        "",
        "所有文件均使用 MapGIS 内置的投影/椭球索引解析；以下为检测到的 CRS 摘要。",
        "",
    ])

    crs_groups: Dict[str, List[str]] = {}
    for item in report:
        if "error" in item or not item.get("crs"):
            continue
        # 用 WKT 前半部分作为分组键
        crs_key = item["crs"].split("\n")[0][:120]
        crs_groups.setdefault(crs_key, []).append(item["path"])

    for crs_key, files in crs_groups.items():
        lines.append(f"- **{crs_key}...**（{len(files)} 个文件）")
        for f in files:
            lines.append(f"  - {f}")

    lines.extend(["", "## 字段示例", ""])
    for item in report[:5]:
        if "error" in item:
            continue
        lines.append(f"### {item['path']}")
        lines.append(f"- 字段：{', '.join(f['name'] for f in item['fields'])}")
        lines.append("- 前 3 行属性样例：")
        lines.append("```json")
        lines.append(json.dumps(item["attribute_sample"], ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    files = sorted(glob.glob("*.WT") + glob.glob("*.WL") + glob.glob("*.WP"))
    if not files:
        print("当前目录未找到 *.WT / *.WL / *.WP 文件。")
        return 0

    print(f"正在分析 {len(files)} 个文件...")
    report: List[Dict[str, Any]] = [summarize_file(f) for f in files]

    json_path = "analysis_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"JSON 报告已保存：{json_path}")

    md_path = "analysis_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_markdown(report))
    print(f"Markdown 报告已保存：{md_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
