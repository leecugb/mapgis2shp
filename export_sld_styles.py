#!/usr/bin/env python3
"""将 DZ/T 0179 配色映射表导出为 GeoServer 可用的 OGC SLD 1.0 样式文件。

本脚本读取 geological_unit_color_mapping_final.json，按解析后的 color key 聚合生成
SLD Rule，使 GeoServer WMS 渲染的地质面颜色与 kurgan_strict_standard_map.png 保持一致。

输出：
- data/sld/kurgan_dzt0179_styles.sld

使用方式：
    python3 export_sld_styles.py

GeoServer 配套使用：
1. 先用 export_for_mapnik.py 生成 data/mapnik/geology_polygons.geojson（含 key 字段）。
2. 在 GeoServer 中发布 geology_polygons.geojson 为图层 kurgan_geology。
3. 上传 data/sld/kurgan_dzt0179_styles.sld 作为该图层的默认样式。
4. 确保数据属性中存在名为 key 的字段（可用 --property-name 修改）。
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).parent
DEFAULT_MAPPING = ROOT / "geological_unit_color_mapping_final.json"
DEFAULT_PALETTE = ROOT / "dz_t_0179_colors.json"
DEFAULT_OUT_DIR = ROOT / "data" / "sld"
DEFAULT_OUT_NAME = "kurgan_dzt0179_styles.sld"

# OGC SLD 1.0 命名空间
NS_SLD = "http://www.opengis.net/sld"
NS_OGC = "http://www.opengis.net/ogc"
NS_XLINK = "http://www.w3.org/1999/xlink"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"

ET.register_namespace("", NS_SLD)
ET.register_namespace("ogc", NS_OGC)
ET.register_namespace("xlink", NS_XLINK)
ET.register_namespace("xsi", NS_XSI)


def load_json(path: Path) -> dict | list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def aggregate_rules(mapping: List[dict]) -> OrderedDict[str, dict]:
    """按 key 聚合颜色规则，保留图层信息和要素数。

    同一 key 理论上只对应一种颜色；若出现多种颜色，按要素数取众数并告警。
    """
    groups: Dict[str, Dict[str, any]] = {}
    for record in mapping:
        key = str(record.get("key", "")).strip()
        color = str(record.get("color", "")).strip().lower()
        layer = str(record.get("layer", "")).strip()
        count = int(record.get("count", 0))

        if not key or key == "unknown" or not color:
            continue

        if key not in groups:
            groups[key] = {
                "key": key,
                "layers": set(),
                "codes": [],
                "colors": {},
                "total_count": 0,
            }

        g = groups[key]
        g["layers"].add(layer)
        g["codes"].append(str(record.get("code", "")))
        g["colors"][color] = g["colors"].get(color, 0) + count
        g["total_count"] += count

    # 按 key 排序，侵入岩 key 形如 acid_intermediate:T1 也按字母序排列
    sorted_keys = sorted(groups.keys())
    result: OrderedDict[str, dict] = OrderedDict()

    for key in sorted_keys:
        g = groups[key]
        # 取众数颜色
        best_color = max(g["colors"], key=g["colors"].get)
        other_colors = {c: n for c, n in g["colors"].items() if c != best_color}
        if other_colors:
            print(
                f"[warn] key '{key}' has multiple colors; using {best_color} "
                f"({g['colors'][best_color]} features), ignored: {other_colors}"
            )

        result[key] = {
            "key": key,
            "title": key,
            "fill": best_color,
            "layers": sorted(g["layers"]),
            "codes": g["codes"],
            "count": g["total_count"],
        }

    return result


def _sub(parent: ET.Element, tag: str, text: Optional[str] = None, **attribs) -> ET.Element:
    """便捷函数：创建子元素并设置文本和属性。"""
    child = ET.SubElement(parent, tag, attribs)
    if text is not None:
        child.text = text
    return child


def build_polygon_symbolizer(
    fill: str,
    stroke: str = "#555555",
    stroke_width: float = 0.15,
    fill_opacity: float = 1.0,
) -> ET.Element:
    """构建 PolygonSymbolizer 元素。"""
    sym = ET.Element(f"{{{NS_SLD}}}PolygonSymbolizer")

    fill_elem = _sub(sym, f"{{{NS_SLD}}}Fill")
    _sub(fill_elem, f"{{{NS_SLD}}}CssParameter", fill, name="fill")
    if fill_opacity != 1.0:
        _sub(fill_elem, f"{{{NS_SLD}}}CssParameter", str(fill_opacity), name="fill-opacity")

    stroke_elem = _sub(sym, f"{{{NS_SLD}}}Stroke")
    _sub(stroke_elem, f"{{{NS_SLD}}}CssParameter", stroke, name="stroke")
    _sub(stroke_elem, f"{{{NS_SLD}}}CssParameter", str(stroke_width), name="stroke-width")

    return sym


def build_rule(
    key: str,
    title: str,
    fill: str,
    property_name: str = "key",
    stroke: str = "#555555",
    stroke_width: float = 0.15,
) -> ET.Element:
    """构建一条按 key 过滤的 SLD Rule。"""
    rule = ET.Element(f"{{{NS_SLD}}}Rule")
    _sub(rule, f"{{{NS_SLD}}}Name", key)
    _sub(rule, f"{{{NS_SLD}}}Title", title)

    filter_elem = _sub(rule, f"{{{NS_OGC}}}Filter")
    prop_is_equal = _sub(filter_elem, f"{{{NS_OGC}}}PropertyIsEqualTo")
    _sub(prop_is_equal, f"{{{NS_OGC}}}PropertyName", property_name)
    _sub(prop_is_equal, f"{{{NS_OGC}}}Literal", key)

    rule.append(
        build_polygon_symbolizer(
            fill=fill,
            stroke=stroke,
            stroke_width=stroke_width,
        )
    )
    return rule


def build_default_rule(
    fill: str = "#c8c8c8",
    stroke: str = "#555555",
    stroke_width: float = 0.15,
) -> ET.Element:
    """构建默认回退 Rule（ElseFilter）。"""
    rule = ET.Element(f"{{{NS_SLD}}}Rule")
    _sub(rule, f"{{{NS_SLD}}}Name", "default")
    _sub(rule, f"{{{NS_SLD}}}Title", "未分类/默认")
    _sub(rule, f"{{{NS_SLD}}}ElseFilter")
    rule.append(
        build_polygon_symbolizer(
            fill=fill,
            stroke=stroke,
            stroke_width=stroke_width,
        )
    )
    return rule


def build_sld(
    rules: List[ET.Element],
    layer_name: str = "kurgan_geology",
    style_name: str = "kurgan_dzt0179",
    style_title: str = "库尔干幅 DZ/T 0179 标准色",
    default_fill: str = "#c8c8c8",
    stroke: str = "#555555",
    stroke_width: float = 0.15,
) -> ET.Element:
    """组装完整 SLD 文档。"""
    sld = ET.Element(
        f"{{{NS_SLD}}}StyledLayerDescriptor",
        {
            "version": "1.0.0",
            f"{{{NS_XSI}}}schemaLocation": f"{NS_SLD} {NS_SLD}/1.0.0/StyledLayerDescriptor.xsd",
        },
    )

    named_layer = _sub(sld, f"{{{NS_SLD}}}NamedLayer")
    _sub(named_layer, f"{{{NS_SLD}}}Name", layer_name)

    user_style = _sub(named_layer, f"{{{NS_SLD}}}UserStyle")
    _sub(user_style, f"{{{NS_SLD}}}Name", style_name)
    _sub(user_style, f"{{{NS_SLD}}}Title", style_title)

    feature_type_style = _sub(user_style, f"{{{NS_SLD}}}FeatureTypeStyle")
    _sub(feature_type_style, f"{{{NS_SLD}}}Name", "geology_polygons")

    for rule in rules:
        feature_type_style.append(rule)

    # 默认规则放在最后
    feature_type_style.append(
        build_default_rule(fill=default_fill, stroke=stroke, stroke_width=stroke_width)
    )

    return sld


def write_sld(sld: ET.Element, out_path: Path, pretty: bool = True) -> None:
    """将 SLD 元素写入文件，并添加 XML 声明。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(sld)

    # ET 本身不提供 pretty print，这里通过 indent 实现（Python 3.9+）
    try:
        ET.indent(tree, space="  ")
    except AttributeError:
        pass

    tree.write(out_path, encoding="utf-8", xml_declaration=True)
    print(f"Saved: {out_path}")


def validate_sld(
    sld_path: Path,
    expected_rules: OrderedDict[str, dict],
    palette: dict,
) -> Tuple[bool, List[str]]:
    """验证生成的 SLD 文件。

    返回 (is_valid, messages)。
    """
    messages: List[str] = []
    try:
        tree = ET.parse(sld_path)
    except ET.ParseError as exc:
        messages.append(f"XML parse error: {exc}")
        return False, messages

    root = tree.getroot()
    if root.tag != f"{{{NS_SLD}}}StyledLayerDescriptor":
        messages.append(f"Root element is not sld:StyledLayerDescriptor: {root.tag}")
        return False, messages

    # 提取所有非默认 Rule 的 fill 和 key
    sld_colors: Dict[str, str] = {}
    has_default = False

    for rule in root.iter(f"{{{NS_SLD}}}Rule"):
        name_elem = rule.find(f"{{{NS_SLD}}}Name")
        if name_elem is None:
            continue
        name = name_elem.text or ""

        else_filter = rule.find(f"{{{NS_SLD}}}ElseFilter")
        if else_filter is not None:
            has_default = True
            continue

        # 提取 Literal（即 key）
        literal = rule.find(f".//{{{NS_OGC}}}Literal")
        if literal is None or not literal.text:
            continue
        key = literal.text.strip()

        # 提取 fill
        fill_param = rule.find(f".//{{{NS_SLD}}}CssParameter[@name='fill']")
        if fill_param is None or not fill_param.text:
            messages.append(f"Rule '{name}' missing fill color")
            continue
        sld_colors[key] = fill_param.text.strip().lower()

    # 与期望映射表比对
    for key, info in expected_rules.items():
        expected = info["fill"].lower()
        actual = sld_colors.get(key)
        if actual is None:
            messages.append(f"Missing Rule for key '{key}'")
        elif actual != expected:
            messages.append(f"Color mismatch for key '{key}': expected {expected}, got {actual}")

    # 检查是否有额外 Rule
    for key in sld_colors:
        if key not in expected_rules:
            messages.append(f"Unexpected Rule for key '{key}'")

    if not has_default:
        messages.append("Missing default ElseFilter rule")

    is_valid = not any(m.startswith(("XML", "Root", "Missing", "Color", "Unexpected")) for m in messages)
    return is_valid, messages


def export_sld_styles(
    mapping_path: Path = DEFAULT_MAPPING,
    palette_path: Path = DEFAULT_PALETTE,
    out_dir: Path = DEFAULT_OUT_DIR,
    out_name: str = DEFAULT_OUT_NAME,
    property_name: str = "key",
    layer_name: str = "kurgan_geology",
    style_name: str = "kurgan_dzt0179",
    style_title: str = "库尔干幅 DZ/T 0179 标准色",
    stroke: str = "#555555",
    stroke_width: float = 0.15,
) -> int:
    """主入口：生成并验证 SLD 样式文件。"""
    if not mapping_path.exists():
        print(f"[error] Mapping file not found: {mapping_path}")
        print("Run: python3 build_geological_unit_color_mapping.py")
        return 1
    if not palette_path.exists():
        print(f"[error] Palette file not found: {palette_path}")
        return 1

    mapping = load_json(mapping_path)
    palette = load_json(palette_path)

    if not isinstance(mapping, list):
        print("[error] Mapping file must be a JSON array")
        return 1

    print(f"Loaded {len(mapping)} mapping records from {mapping_path}")

    rules_info = aggregate_rules(mapping)
    print(f"Aggregated into {len(rules_info)} unique color keys")

    rules = [
        build_rule(
            key=info["key"],
            title=info["title"],
            fill=info["fill"],
            property_name=property_name,
            stroke=stroke,
            stroke_width=stroke_width,
        )
        for info in rules_info.values()
    ]

    # 默认回退色：优先用 palette fallback.unknown，否则用灰色
    fallback_color = palette.get("fallback", {}).get("unknown", [200, 200, 200])
    default_fill = "#{:02x}{:02x}{:02x}".format(*fallback_color)

    sld = build_sld(
        rules=rules,
        layer_name=layer_name,
        style_name=style_name,
        style_title=style_title,
        default_fill=default_fill,
        stroke=stroke,
        stroke_width=stroke_width,
    )

    out_path = out_dir / out_name
    write_sld(sld, out_path)

    # 验证
    is_valid, messages = validate_sld(out_path, rules_info, palette)
    if messages:
        for msg in messages:
            print(f"  {'[ok]' if 'valid' in msg.lower() else '[warn]'} {msg}")

    if is_valid:
        print(f"\nValidation passed: {len(rules_info)} rules + 1 default rule")
        return 0
    else:
        print("\nValidation failed")
        return 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export DZ/T 0179 color mapping to GeoServer SLD 1.0 style"
    )
    parser.add_argument(
        "--mapping",
        type=Path,
        default=DEFAULT_MAPPING,
        help="Path to geological_unit_color_mapping_final.json",
    )
    parser.add_argument(
        "--palette",
        type=Path,
        default=DEFAULT_PALETTE,
        help="Path to dz_t_0179_colors.json",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Output directory for SLD file",
    )
    parser.add_argument(
        "--out-name",
        type=str,
        default=DEFAULT_OUT_NAME,
        help="Output SLD file name",
    )
    parser.add_argument(
        "--property-name",
        type=str,
        default="key",
        help="Attribute name used in SLD Filter (default: key)",
    )
    parser.add_argument(
        "--layer-name",
        type=str,
        default="kurgan_geology",
        help="NamedLayer name in SLD",
    )
    parser.add_argument(
        "--style-name",
        type=str,
        default="kurgan_dzt0179",
        help="UserStyle name in SLD",
    )
    parser.add_argument(
        "--style-title",
        type=str,
        default="库尔干幅 DZ/T 0179 标准色",
        help="UserStyle title in SLD",
    )
    parser.add_argument(
        "--stroke",
        type=str,
        default="#555555",
        help="Polygon boundary stroke color",
    )
    parser.add_argument(
        "--stroke-width",
        type=float,
        default=0.15,
        help="Polygon boundary stroke width",
    )

    args = parser.parse_args(argv)
    return export_sld_styles(
        mapping_path=args.mapping,
        palette_path=args.palette,
        out_dir=args.out_dir,
        out_name=args.out_name,
        property_name=args.property_name,
        layer_name=args.layer_name,
        style_name=args.style_name,
        style_title=args.style_title,
        stroke=args.stroke,
        stroke_width=args.stroke_width,
    )


if __name__ == "__main__":
    raise SystemExit(main())
