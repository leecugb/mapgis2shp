#!/usr/bin/env python3
"""系统梳理每个 MapGIS 文件的内容类别。

输出：
- systematic_classification.md：每个文件的内容类别系统梳理
- systematic_classification.json：结构化数据
"""

from __future__ import annotations

import glob
import json
import re
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

warnings.filterwarnings("ignore")

import pandas as pd
from pymapgis import Reader


# 文件名前缀含义推断（基于常见 MapGIS 图幅数据命名习惯）
PREFIX_MEANING = {
    "LD": "地理/基础地理",
    "LF": "地理/框架数据",
    "LY": "流域/水系",
    "LZ": "地质/专题",
    "LH": "综合/专题",
}

# 字段前缀语义映射
FIELD_PREFIX_SEMANTICS = {
    "ID": ("系统", "内部标识符"),
    "FEATUREID": ("系统", "要素唯一标识"),
    "CHFCAC": ("系统", "图元编号/顺序码"),
    "CHFCCD": ("系统", "线分类码"),
    "CHFCCH": ("系统", "线型辅助码"),
    "CHFCCF": ("系统", "线型参数"),
    "CHFCEC": ("系统", "点分类码"),
    "CHFCED": ("系统", "点型参数"),
    "CODE": ("基础", "要素分类代码"),
    "GB": ("基础", "国标分类码"),
    "NAME": ("基础", "名称"),
    "TN": ("基础", "图名/题名"),
    "HYDC": ("水系", "水文数据码"),
    "长度": ("几何", "线长度"),
    "周长": ("几何", "面周长"),
    "面积": ("几何", "面面积"),
    "GZ": ("地质构造", "构造相关属性"),
    "DD": ("地层", "地层相关属性"),
    "YS": ("岩石岩性", "岩石岩性相关属性"),
    "MD": ("矿产", "矿产相关属性"),
    "KC": ("矿产勘查", "矿产勘查相关属性"),
    "KWB": ("矿产", "矿体/矿点相关"),
    "WT": ("水文地质", "水文地质相关属性"),
    "SWN": ("水文地质", "水文/水系相关"),
    "QDH": ("综合", "区调/核查相关"),
    "QDI": ("区调", "区域地质调查"),
    "QDUE": ("区调", "区域地质调查"),
    "QDFC": ("区调", "区域地质调查"),
    "HT": ("专题", "话题/专题标记"),
    "YG": ("遥感", "遥感相关"),
    "GCJF": ("空间基准", "空间基准框架"),
    "GG": ("地理", "地理信息相关"),
    "PKIGJ": ("图幅", "图幅信息"),
    "SYP": ("样品", "样品/标本"),
    "DSA": ("专题", "专题属性"),
    "HS": ("综合", "综合属性"),
}


def _get_field_prefix(field: str) -> str:
    """获取字段前缀（字母部分）。"""
    m = re.match(r"^([A-Za-z]+)", field)
    return m.group(1).upper() if m else field


def _classify_fields(fields: List[str]) -> Tuple[List[Tuple[str, str, str]], Set[str]]:
    """对每个字段进行分类，返回 (字段, 大类, 含义) 列表和主题集合。"""
    classified = []
    themes: Set[str] = set()
    for f in fields:
        prefix = _get_field_prefix(f)
        matched = False
        for key, (category, meaning) in FIELD_PREFIX_SEMANTICS.items():
            if prefix.startswith(key) or f.upper() == key or f == key:
                classified.append((f, category, meaning))
                if category not in ("系统", "几何", "基础"):
                    themes.add(category)
                matched = True
                break
        if not matched:
            classified.append((f, "其他", "未识别字段"))
    return classified, themes


def _analyze_filename(filename: str) -> Dict[str, Any]:
    """解析文件名结构。"""
    base = Path(filename).stem.upper()
    # 去掉可能的 ~ 后缀
    base = base.replace("~", "")
    # 提取前两位字母前缀
    prefix = base[:2] if len(base) >= 2 and base[:2].isalpha() else "未知"
    # 提取后续代码
    code = base[2:] if len(base) > 2 else ""

    return {
        "filename": filename,
        "base": base,
        "prefix": prefix,
        "prefix_meaning": PREFIX_MEANING.get(prefix, "未知专题"),
        "layer_code": code,
    }


def _gb_description(gb: str) -> str:
    """根据 GB 编码给出常见含义。"""
    gb_map = {
        "9": "地名/注记",
        "21010": "常年河/时令河",
        "21021": "河流",
        "73020": "湖泊/水库/坑塘",
    }
    return gb_map.get(str(gb).strip(), "未知")


def analyze_file(path: str) -> Dict[str, Any]:
    """系统分析单个文件。"""
    filename = Path(path).name
    file_info = _analyze_filename(filename)
    result = {"file_info": file_info, "path": path}

    try:
        with Reader(path) as r:
            result["shape_type"] = r.shapeType
            result["feature_count"] = len(r)
            result["bbox"] = r.bbox.tolist() if r.bbox is not None else None
            result["crs"] = r.crs.to_wkt() if r.crs else None

            fields = [name for name, _, _ in r.fields]
            field_classified, themes = _classify_fields(fields)
            result["fields"] = [
                {"name": name, "category": cat, "meaning": meaning}
                for name, cat, meaning in field_classified
            ]

            # 字段类别统计
            cat_counter = Counter([cat for _, cat, _ in field_classified])
            result["field_category_distribution"] = dict(cat_counter)

            # 主题推断
            gdf = r.geodataframe
            sample_attrs = gdf.drop(columns="geometry", errors="ignore").head(3).to_dict(
                orient="records"
            )

            # 统计 GB 编码
            gb_dist = {}
            if "GB" in gdf.columns:
                gb_series = gdf["GB"].astype(str).str.strip()
                gb_dist = gb_series.value_counts().head(10).to_dict()

            # 推断内容类别（优先级：字段主题 > GB编码 > 文件名前缀 > 几何类型）
            categories = []

            # 1. 根据字段主题（最可靠）
            for theme in sorted(themes):
                if theme not in categories:
                    categories.append(theme)

            # 2. 根据 GB 编码
            if gb_dist:
                for gb in gb_dist:
                    desc = _gb_description(gb)
                    if desc and desc not in categories and desc != "未知":
                        categories.append(desc)

            # 3. 根据 NAME 样例判断地名注记
            if "NAME" in gdf.columns:
                names = gdf["NAME"].dropna().astype(str)
                names = names[names.str.strip() != ""]
                result["name_samples"] = names.head(8).tolist()
                if len(names) > 0 and names.str.len().mean() <= 2:
                    if "地名/注记" not in categories:
                        categories.append("地名/注记")
            else:
                result["name_samples"] = []

            # 4. 根据文件名前缀补充专题信息
            prefix = file_info["prefix"]
            layer_code = file_info["layer_code"]
            base = file_info["base"]

            # LH 系列细分
            if prefix == "LH":
                if "CPGDAC" in base:
                    # CPGDAC 系列：成矿地质背景专题
                    if base.endswith(("06", "09", "12")) and result["shape_type"] == "LINE":
                        categories.append("成矿背景辅助线")
                    elif base.endswith("01"):
                        categories.append("地质构造")
                    elif base.endswith(("05", "08")):
                        categories.append("水文地质")
                    elif base.endswith("11"):
                        categories.append("区调")
                    else:
                        categories.append("成矿地质背景")
                elif "TQGTA" in base:
                    categories.append("专题")

            # LY 系列补充
            if prefix == "LY" and "水系/流域" not in categories:
                categories.append("水系/流域")

            # LZ 系列补充
            if prefix == "LZ" and "地质专题" not in categories:
                categories.append("地质专题")

            # LF 系列：基础地理框架（图廓、格网、图例等）
            if prefix == "LF":
                if "基础地理框架" not in categories:
                    categories.append("基础地理框架")

            # LDZOFBB098/099：仅含系统符号参数，判为图例/符号
            if prefix == "LD" and "ZOFBB" in layer_code and layer_code.endswith(("098", "099")):
                if "图例/符号" not in categories:
                    categories.append("图例/符号")

            # 5. 根据图层码细分 LD 系列
            if prefix == "LD":
                if "LY" in layer_code:
                    if "水系/流域" not in categories:
                        categories.append("水系/流域")
                elif "ZO" in layer_code:
                    # ZO 系列为地质图专题
                    if result["shape_type"] == "POINT" and "GZBB" in str(fields):
                        categories.append("地质构造点")
                    elif any(f.startswith("GZ") for f in fields) and result["shape_type"] == "LINE":
                        categories.append("地质构造线")
                    elif any(f.startswith(("DD", "YS", "QD")) for f in fields):
                        if "岩石岩性" in themes and "地层" in themes:
                            categories.append("地层岩性面")
                        elif "地层" in themes:
                            categories.append("地层分区面")
                        elif "岩石岩性" in themes:
                            categories.append("岩性分布面")
                        else:
                            categories.append("地质构造面")
                    else:
                        categories.append("地质专题")

            # 6. 兜底
            if not categories:
                categories.append(result["shape_type"])

            result["categories"] = categories

            # 选择最具体的主类别（优先非通用、非几何类型）
            priority_order = [
                "水系/流域", "常年河/时令河", "河流", "湖泊/水库/坑塘",
                "地质构造", "地质构造线", "地质构造点", "地质构造面",
                "地层", "地层分区面", "岩性分布面", "地层岩性面",
                "岩石岩性", "矿产", "矿体/矿点相关", "矿产勘查",
                "水文地质", "区调", "区域地质调查",
                "成矿背景辅助线", "成矿地质背景",
                "专题", "遥感",
                "图例/符号", "测绘", "基础地理框架",
                "地名/注记",
            ]
            primary = "未分类"
            for candidate in priority_order:
                if candidate in categories:
                    primary = candidate
                    break
            if primary == "未分类" and categories:
                primary = categories[0]
            result["primary_category"] = primary

            result["gb_distribution"] = {str(k): int(v) for k, v in gb_dist.items()}
            result["attribute_samples"] = sample_attrs

    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


def build_systematic_report(items: List[Dict[str, Any]]) -> str:
    """生成系统梳理报告。"""
    lines: List[str] = ["# MapGIS 文件内容系统梳理", ""]

    # 总体统计
    total = len(items)
    success = sum(1 for i in items if "error" not in i)
    lines.append(f"共分析 **{total}** 个文件，成功 **{success}** 个。")
    lines.append("")

    # 按主类别分组
    cat_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in items:
        if "error" not in item:
            cat_groups[item["primary_category"]].append(item)

    lines.extend(["## 一、按主类别分组", ""])
    for cat, group in sorted(cat_groups.items(), key=lambda x: -len(x[1])):
        lines.append(f"### {cat}（{len(group)} 个文件）")
        for item in group:
            info = item["file_info"]
            lines.append(
                f"- **{info['filename']}** "
                f"(`{info['base']}` / {item['shape_type']} / {item['feature_count']} 要素)"
            )
        lines.append("")

    # 文件名前缀分组
    prefix_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in items:
        if "error" not in item:
            prefix_groups[item["file_info"]["prefix"]].append(item)

    lines.extend(["## 二、按文件名前缀分组", ""])
    for prefix, group in sorted(prefix_groups.items()):
        meaning = PREFIX_MEANING.get(prefix, "未知")
        lines.append(f"### {prefix} — {meaning}（{len(group)} 个文件）")
        for item in group:
            info = item["file_info"]
            lines.append(
                f"- {info['filename']} → 图层码 `{info['layer_code']}` | "
                f"{item['shape_type']} | {item['primary_category']}"
            )
        lines.append("")

    # 每个文件的系统梳理卡片
    lines.extend(["## 三、每个文件详细梳理", ""])
    for item in items:
        if "error" in item:
            lines.append(f"### {item['path']} — 解析失败")
            lines.append(f"- 错误：{item['error']}")
            lines.append("")
            continue

        info = item["file_info"]
        lines.append(f"### {info['filename']}")
        lines.append(f"- **文件名解析**：前缀 `{info['prefix']}`（{info['prefix_meaning']}），图层码 `{info['layer_code']}`")
        lines.append(f"- **几何类型**：{item['shape_type']}")
        lines.append(f"- **要素数量**：{item['feature_count']}")
        lines.append(f"- **主类别**：{item['primary_category']}")
        lines.append(f"- **内容标签**：{', '.join(item['categories'])}")
        lines.append(f"- **边界框**：{item['bbox']}")

        lines.append("- **字段类别分布**：")
        for cat, count in sorted(item["field_category_distribution"].items(), key=lambda x: -x[1]):
            lines.append(f"  - {cat}：{count} 个字段")

        lines.append("- **字段明细**：")
        for field in item["fields"]:
            lines.append(f"  - `{field['name']}` → {field['category']} | {field['meaning']}")

        if item.get("gb_distribution"):
            lines.append("- **GB 编码分布**：")
            for gb, cnt in item["gb_distribution"].items():
                desc = _gb_description(gb)
                lines.append(f"  - `{gb}`：{cnt} 条（{desc}）")

        if item.get("name_samples"):
            samples = "、".join(str(n) for n in item["name_samples"])
            lines.append(f"- **NAME 样例**：{samples}")

        if item.get("attribute_samples"):
            lines.append("- **属性样例**：")
            for idx, attrs in enumerate(item["attribute_samples"], 1):
                lines.append(f"  记录 {idx}：{attrs}")

        lines.append("")

    return "\n".join(lines)


def main() -> int:
    files = sorted(glob.glob("*.WT") + glob.glob("*.WL") + glob.glob("*.WP"))
    if not files:
        print("当前目录未找到 *.WT / *.WL / *.WP 文件。")
        return 0

    print(f"正在系统梳理 {len(files)} 个文件的类别...")
    items = [analyze_file(f) for f in files]

    json_path = "systematic_classification.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"结构化数据已保存：{json_path}")

    md_path = "systematic_classification.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_systematic_report(items))
    print(f"系统梳理报告已保存：{md_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
