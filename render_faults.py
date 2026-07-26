#!/usr/bin/env python3
"""按 DZ/T 0179 IR (dz_t_0179_rendering_rules.json#rules.faults) 绘制断裂构造。

类型代码地质含义待图例最终确认，确认后只需修改 IR 的 rules.faults。
符号几何来自 IR #symbols，通过 SymbolEngine 渲染参数化 path。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / "src"))
from pymapgis.rendering import load_ir
from pymapgis.rendering.symbol_engine import SymbolEngine, make_symbol_style


def _resolve_base_style(base_style_ir: dict, line_styles: Dict[str, dict]) -> Dict[str, Any]:
    """解析 base_style：如果含 ref，从 line_styles 获取并覆盖。"""
    result: Dict[str, Any] = {}
    ref = base_style_ir.get("ref")
    if ref and ref in line_styles:
        resolved = line_styles[ref].copy()
        # IR 用 width，matplotlib 用 linewidth
        if "width" in resolved:
            resolved["linewidth"] = resolved.pop("width")
        # 优先使用 IR 中的 linestyle 字符串；否则从 dasharray 推导
        linestyle = resolved.pop("linestyle", None)
        dasharray = resolved.pop("dasharray", None)
        if linestyle:
            resolved["linestyle"] = linestyle
        elif dasharray:
            resolved["linestyle"] = tuple(dasharray) if len(dasharray) else "-"
        else:
            resolved.setdefault("linestyle", "-")
        # 移除非 matplotlib 键
        resolved.pop("cap", None)
        resolved.pop("join", None)
        result.update(resolved)
    # 覆盖 alpha 等额外字段
    for k, v in base_style_ir.items():
        if k != "ref":
            result[k] = v
    result.setdefault("linestyle", "-")
    return result


def _tangent_and_normals(geom, d: float) -> Optional[Tuple]:
    """返回采样点、单位切向量、左右法向量。"""
    length = geom.length
    if length <= 0:
        return None
    pt = geom.interpolate(d)
    pt1 = geom.interpolate(max(0.0, d - 1.0))
    pt2 = geom.interpolate(min(length, d + 1.0))
    tx = pt2.x - pt1.x
    ty = pt2.y - pt1.y
    tlen = math.hypot(tx, ty)
    if tlen == 0:
        return None
    ux, uy = tx / tlen, ty / tlen
    return pt, (ux, uy), {"right": (uy, -ux), "left": (-uy, ux)}


def _sample_distances(length: float, spacing: float, short_threshold: float) -> List[float]:
    """沿断层线按间距采样；短线只在中点采一次。"""
    if length <= 0:
        return []
    if length <= short_threshold or spacing is None or spacing <= 0:
        return [length / 2.0]
    steps = max(1, int(length / spacing))
    if steps == 1:
        return [length / 2.0]
    return [i * length / steps for i in range(steps + 1)]


def _dip_label(ax, x: float, y: float, dip: float, ux: float, uy: float,
               offset: float, font_size: float, color: str = "black"):
    """沿断层线方向偏移注记倾角。"""
    if dip is None or np.isnan(dip) or dip <= 0:
        return
    text = str(int(round(min(dip, 90.0))))
    lx = x + ux * offset
    ly = y + uy * offset
    ax.text(lx, ly, text, fontsize=font_size, color=color, ha="center", va="center")


def _type_key_for_row(row, type_field) -> Optional[str]:
    if type_field is None:
        return "_all"
    if isinstance(type_field, list):
        vals = [str(row.get(f, "")).strip() for f in type_field]
        if not all(vals):
            return None
        return ",".join(vals)
    val = str(row.get(type_field, "")).strip()
    return val if val else None


def _resolve_style_key(type_key: Optional[str], type_map: Dict) -> Optional[str]:
    if type_key is None:
        return None
    if type_key in type_map:
        return type_key
    # 对 LYGREBA001 做容错：若不存在 "01,04" 等组合，尝试单独字段
    for k in type_map:
        if type_key in k.split(","):
            return k
    return None


# fault_rendering_styles.json 中的 symbol_type 到 IR symbol_id 的映射
SYMBOL_TYPE_TO_ID = {
    "normal": "normal_fault_tick",
    "neutral_tick": "neutral_tick",
    "reverse": "reverse_fault_tooth",
    "thrust": "thrust_fault_tooth",
    "strike_slip": "strike_slip_arrows",
    "active": "active_fault_arrows",
}


def _draw_symbol(ax, symbol_type: str, pt, tangent, normals, symbol_defaults: Dict,
                 style_base: Dict, side: Optional[str]):
    """使用 IR 参数化符号渲染单个采样点处的断层符号。"""
    if symbol_type in ("solid_unknown", "concealed", "interpreted", "dashed_dot", "arc_unknown", "none", "shear_zone_double_line"):
        return

    symbol_id = SYMBOL_TYPE_TO_ID.get(symbol_type)
    if symbol_id is None:
        return

    x0, y0 = float(pt.x), float(pt.y)
    ux, uy = tangent
    side_key = side if side in normals else "right"
    nx, ny = normals[side_key]

    sym_style = make_symbol_style(
        color=style_base["color"],
        linewidth=0.5,
        facecolor=style_base["color"] if symbol_type in ("reverse", "thrust") else "none",
        zorder=style_base.get("zorder", 3) + 1,
    )

    ir = load_ir()
    engine = SymbolEngine(ir.symbols)
    sym_def = ir.symbols.get(symbol_id, {})
    params = sym_def.get("params", {})
    if "tooth_len_m" in params:
        scale = symbol_defaults.get("tooth_len_m", 420.0)
    elif "tick_len_m" in params:
        scale = symbol_defaults.get("tick_len_m", 350.0)
    elif "arrow_len_m" in params:
        scale = symbol_defaults.get("tick_len_m", 350.0)
    else:
        scale = 300.0

    if symbol_type == "strike_slip":
        # 平推断层：两侧各一个半箭头
        for s in ("right", "left"):
            rx, ry = normals[s]
            engine.render_point_symbol(ax, symbol_id, x0, y0, (ux, uy), (rx, ry), scale, sym_style)
    else:
        engine.render_point_symbol(ax, symbol_id, x0, y0, (ux, uy), (nx, ny), scale, sym_style)


def draw_faults_with_styles(ax, line_layers: Dict[str, gpd.GeoDataFrame], root: Path):
    """根据 DZ/T 0179 IR (rules.faults) 绘制断裂线、符号与注记。"""
    ir = load_ir(root / "dz_t_0179_rendering_rules.json")
    styles = ir.rules.get("faults")
    if not styles:
        # 缺少 fault rules 时不绘制符号，避免误导
        return

    symbol_engine = SymbolEngine(ir.symbols, root=root)
    line_styles = ir.line_styles

    global_cfg = styles.get("global", {})
    dip_min = global_cfg.get("dip_angle_min", 0.1)

    for src_name, src_cfg in styles["sources"].items():
        gdf = line_layers.get(src_name)
        if gdf is None or gdf.empty:
            continue

        base_style_ir = src_cfg.get("base_style", {})
        base_style = _resolve_base_style(base_style_ir, line_styles)
        base_style.setdefault("zorder", 2)
        sym_defaults = src_cfg["symbol_defaults"]
        type_map = src_cfg["type_map"]
        type_field = src_cfg.get("type_field")
        dip_field = src_cfg.get("dip_field")

        # 1. 绘制基线
        gdf.plot(ax=ax, color=base_style["color"], linewidth=base_style["linewidth"],
                 linestyle=base_style["linestyle"], alpha=base_style.get("alpha", 1.0),
                 zorder=base_style["zorder"])

        # 2. 破碎带/剪切带类型绘制双线（DZ/T 0179 表22 为红色双线）
        offset = sym_defaults.get("tick_len_m", 250.0) * 0.6
        for _, row in gdf.iterrows():
            key = _type_key_for_row(row, type_field)
            mapped = _resolve_style_key(key, type_map)
            if mapped is None:
                continue
            sym_type = type_map[mapped].get("symbol_type")
            if sym_type == "shear_zone_double_line":
                double_style = {
                    "color": base_style["color"],
                    "linewidth": base_style["linewidth"] * 0.8,
                    "linestyle": "-",
                    "zorder": base_style["zorder"] + 0.5,
                }
                geom = row.geometry
                parts = list(geom.geoms) if geom.geom_type == "MultiLineString" else [geom]
                symbol_engine.render_line_offset(ax, parts, offset, double_style)

        # 3. 沿线采样绘制符号与倾角注记
        spacing = sym_defaults.get("sample_spacing_m")
        short_threshold = global_cfg.get("short_segment_threshold_m", 5000.0)

        for _, row in gdf.iterrows():
            key = _type_key_for_row(row, type_field)
            mapped = _resolve_style_key(key, type_map)
            if mapped is None:
                continue
            style_cfg = type_map[mapped]
            symbol_type = style_cfg.get("symbol_type", "none")
            if symbol_type == "none":
                continue

            side = style_cfg.get("default_side")
            label_dip = style_cfg.get("label_dip", False)

            dip = None
            if dip_field and dip_field in row:
                dip = pd.to_numeric(row[dip_field], errors="coerce")
                if pd.isna(dip) or dip <= dip_min:
                    dip = None

            geom = row.geometry
            parts = list(geom.geoms) if geom.geom_type == "MultiLineString" else [geom]
            for part in parts:
                length = part.length
                for d in _sample_distances(length, spacing, short_threshold):
                    res = _tangent_and_normals(part, d)
                    if res is None:
                        continue
                    pt, tangent, normals = res
                    _draw_symbol(ax, symbol_type, pt, tangent, normals, sym_defaults,
                                 base_style, side)
                    if label_dip and dip is not None:
                        ux, uy = tangent
                        # 注记放在符号末端再沿线偏移
                        offset = sym_defaults.get("dip_label_offset_m", 250.0)
                        _dip_label(
                            ax, float(pt.x), float(pt.y), float(dip),
                            ux, uy, offset,
                            sym_defaults.get("font_size", 3.0),
                            sym_defaults.get("font_color", "black"),
                        )

    # 4. 深部大断裂名称沿线标注（简单沿中点标注）
    deep_cfg = styles.get("sources", {}).get("LZLPGDJ002", {})
    deep_gdf = line_layers.get("LZLPGDJ002")
    if deep_gdf is not None and not deep_gdf.empty and "GZEAB" in deep_gdf.columns:
        font_size = deep_cfg.get("symbol_defaults", {}).get("font_size", 4.0)
        base_style_ir = deep_cfg.get("base_style", {})
        base_style = _resolve_base_style(base_style_ir, line_styles)
        color = base_style.get("color", "#c41e3a")
        for _, row in deep_gdf.iterrows():
            name = str(row.get("GZEAB", "")).strip()
            if not name:
                continue
            geom = row.geometry
            parts = list(geom.geoms) if geom.geom_type == "MultiLineString" else [geom]
            for part in parts:
                if part.length <= 0:
                    continue
                pt = part.interpolate(part.length / 2.0)
                ax.text(float(pt.x), float(pt.y), name, fontsize=font_size,
                        color=color, ha="center", va="center",
                        rotation=0, fontweight="bold")
