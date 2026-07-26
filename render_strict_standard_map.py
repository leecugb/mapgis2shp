#!/usr/bin/env python3
"""严格按照 DZ/T 0179 标准色渲染库尔干幅地质图。"""

from __future__ import annotations

import json
import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import geopandas as gpd
import matplotlib.font_manager as fm
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from scipy.spatial import cKDTree

from pymapgis import Reader
from pymapgis.rendering import load_ir, rgb_to_hex
from render_faults import draw_faults_with_styles

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent

# 输出坐标系：WGS84 UTM Zone 43N（覆盖 72°E–78°E，1:250000 库尔干幅位于该带）
TARGET_CRS = "EPSG:32643"

# 中文字体
FONT_PATH = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
if FONT_PATH.exists():
    try:
        fm.fontManager.addfont(str(FONT_PATH))
    except Exception:
        pass
plt.rcParams["font.sans-serif"] = [
    "Noto Sans CJK SC", "Noto Sans CJK JP", "SimHei",
    "WenQuanYi Micro Hei", "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False

GREEK = "γδβυηνταοφρπμεψχι"

# 地质代号箭头：→ 正常显示，↓ 下标，↑ 上标
GREEK_TO_TEX: Dict[str, str] = {
    "γ": r"\gamma",
    "δ": r"\delta",
    "β": r"\beta",
    "υ": r"\upsilon",
    "η": r"\eta",
    "ν": r"\nu",
    "τ": r"\tau",
    "α": r"\alpha",
    "ο": "o",
    "φ": r"\phi",
    "ρ": r"\rho",
    "π": r"\pi",
    "μ": r"\mu",
    "ε": r"\epsilon",
    "ψ": r"\psi",
    "χ": r"\chi",
    "ι": r"\iota",
}


def parse_label_hash(text: str) -> List[Tuple[str, str]]:
    """解析 MapGIS 注记字段中的 # 控制码：#- 下标、#+ 上标、#= 正常。"""
    s = str(text).strip()
    segments: List[Tuple[str, str]] = []
    mode = "normal"
    buf = ""
    i = 0
    mode_map = {"-": "sub", "+": "sup", "=": "normal"}
    while i < len(s):
        if s[i] == "#" and i + 1 < len(s):
            if buf:
                segments.append((mode, buf))
                buf = ""
            mode = mode_map.get(s[i + 1], "normal")
            i += 2
        else:
            buf += s[i]
            i += 1
    if buf:
        segments.append((mode, buf))
    return [(m, c) for m, c in segments if c]


def parse_label_arrows(text: str) -> List[Tuple[str, str]]:
    """把地质代号按箭头拆分为 (mode, content) 段。mode: normal/sub/sup。"""
    s = str(text).strip()
    segments: List[Tuple[str, str]] = []
    mode = "normal"
    buf = ""
    i = 0
    if s and s[0] in "→↓↑":
        mode = {"→": "normal", "↓": "sub", "↑": "sup"}[s[0]]
        i = 1
    while i < len(s):
        ch = s[i]
        if ch in "→↓↑":
            if buf:
                segments.append((mode, buf))
                buf = ""
            mode = {"→": "normal", "↓": "sub", "↑": "sup"}[ch]
        else:
            buf += ch
        i += 1
    if buf:
        segments.append((mode, buf))
    return segments


def _escape_for_math(text: str) -> str:
    """转义 mathtext 中的特殊字符。"""
    return (
        text.replace("\\", "\\\\")
        .replace("#", "\\#")
        .replace("_", "\\_")
        .replace("%", "\\%")
        .replace("&", "\\&")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("~", "\\~")
        .replace("^", "\\^")
        .replace("$", "\\$")
    )


def _tokenize_label_segment(text: str) -> str:
    r"""将一段中的希腊字母转为 TeX 命令，连续拉丁/数字放入 \mathrm{}。"""
    tokens: List[str] = []
    latin_buf = ""
    for c in text:
        if c in GREEK_TO_TEX:
            if latin_buf:
                tokens.append(r"\mathrm{" + _escape_for_math(latin_buf) + "}")
                latin_buf = ""
            tokens.append(GREEK_TO_TEX[c])
        else:
            latin_buf += c
    if latin_buf:
        tokens.append(r"\mathrm{" + _escape_for_math(latin_buf) + "}")
    return " ".join(tokens)


def format_label(text: str) -> str:
    """把原始地质代号（含箭头或 # 控制码、希腊字母）转成 Matplotlib mathtext 字符串。"""
    s = str(text).strip()
    if "#" in s:
        segments = parse_label_hash(s)
    else:
        segments = parse_label_arrows(s)
    parts = []
    for mode, content in segments:
        t = _tokenize_label_segment(content)
        if not t:
            continue
        if mode == "normal":
            parts.append(t)
        elif mode == "sub":
            parts.append(r"_{" + t + "}")
        elif mode == "sup":
            parts.append(r"^{" + t + "}")
    return "$" + "".join(parts) + "$"


# 加载 DZ/T 0179 渲染规则中间表示（IR）。Phase 1 先用其色板解析地质单元颜色，
# 后续 Phase 逐步把线型、图案、符号规则也迁移到 IR。
_IR = load_ir()
get_color = _IR.resolve_unit_color


def load_layers(root: Path, names: List[str], target_crs: Optional[str] = None) -> Dict[str, gpd.GeoDataFrame]:
    layers: Dict[str, gpd.GeoDataFrame] = {}
    if target_crs is None:
        target_crs = TARGET_CRS
    for name in names:
        path = None
        for ext in ("WP", "WL", "WT"):
            candidate = root / f"{name}.{ext}"
            if candidate.exists():
                path = candidate
                break
        if path is None:
            continue
        try:
            with Reader(path) as r:
                gdf = r.geodataframe.copy()
            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:4326")
            gdf = gdf.to_crs(target_crs)
            layers[name] = gdf
        except Exception as exc:
            print(f"[skip] {path}: {exc}")
    return layers


def add_scale_bar(ax, xy, length_km: int = 20, color: str = "black"):
    """绘制比例尺。坐标单位为度时使用旧逻辑，单位为米（UTM/Web Mercator）时直接按米绘制。"""
    x0, y0 = xy
    # 根据坐标数量级判断是否已投影为米（UTM 下 x、y 通常 > 1e5）
    if abs(x0) > 10000 or abs(y0) > 10000:
        length_m = length_km * 1000
        tick_m = length_m * 0.08
        ax.plot([x0, x0 + length_m], [y0, y0], color=color, linewidth=2.5, solid_capstyle="butt")
        ax.plot([x0, x0], [y0 - tick_m, y0 + tick_m], color=color, linewidth=1.5)
        ax.plot([x0 + length_m, x0 + length_m], [y0 - tick_m, y0 + tick_m], color=color, linewidth=1.5)
        ax.text(
            x0 + length_m / 2, y0 + tick_m * 1.2, f"{length_km} km",
            ha="center", va="bottom", fontsize=8, color=color,
        )
    else:
        lat = y0
        km_per_deg_lon = 111.32 * math.cos(math.radians(lat))
        deg = length_km / km_per_deg_lon
        ax.plot([x0, x0 + deg], [y0, y0], color=color, linewidth=2.5, solid_capstyle="butt")
        ax.plot([x0, x0], [y0 - 0.015, y0 + 0.015], color=color, linewidth=1.5)
        ax.plot([x0 + deg, x0 + deg], [y0 - 0.015, y0 + 0.015], color=color, linewidth=1.5)
        ax.text(
            x0 + deg / 2, y0 + 0.025, f"{length_km} km",
            ha="center", va="bottom", fontsize=8, color=color,
        )


def add_north_arrow(ax, xy, size: float = 0.18):
    x, y = xy
    ax.annotate(
        "N", xy=(x, y + size * 0.7), xytext=(x, y - size * 0.3),
        arrowprops=dict(arrowstyle="-|>", color="black", lw=2),
        fontsize=12, ha="center", va="bottom", color="black", fontweight="bold",
    )


def draw_fault_attitudes(ax, faults: gpd.GeoDataFrame, sample_spacing_m: float = 6000.0):
    """在断层线上按间距绘制断面倾角短线与数字注记。

    说明：LDZOFBA003.WL 未提供倾向方向，短线统一画在断层线前进方向的右侧，
    仅作可视化参考，不代表真实倾向。
    """
    if faults is None or faults.empty:
        return

    for _, row in faults.iterrows():
        geom = row.geometry
        dip = pd.to_numeric(row.get("GZECE"), errors="coerce")
        if pd.isna(dip) or dip <= 0:
            continue

        # 统一把 MultiLineString 拆成单段
        parts = list(geom.geoms) if geom.geom_type == "MultiLineString" else [geom]
        for part in parts:
            length = part.length
            if length <= 0:
                continue
            # 采样间距不小于线段长度时只取中点
            steps = max(1, int(length / sample_spacing_m))
            for i in range(steps + 1):
                d = min(i * length / steps, length)
                pt = part.interpolate(d)
                # 切线方向
                pt1 = part.interpolate(max(0, d - 1))
                pt2 = part.interpolate(min(length, d + 1))
                tx = pt2.x - pt1.x
                ty = pt2.y - pt1.y
                tlen = math.hypot(tx, ty)
                if tlen == 0:
                    continue
                ux, uy = tx / tlen, ty / tlen
                # 右侧法向量（垂直于切线）
                nx, ny = uy, -ux
                tick_len = max(120.0, 300.0 * dip / 90.0)
                x0, y0 = pt.x, pt.y
                x1, y1 = x0 + tick_len * nx, y0 + tick_len * ny
                ax.plot([x0, x1], [y0, y1], color="black", linewidth=0.5)
                # 倾角数字放在短线末端并沿断层线适当偏移
                shift = 180.0
                lx = x1 + shift * ux
                ly = y1 + shift * uy
                ax.text(
                    lx, ly, str(int(round(dip))),
                    fontsize=3.2, color="black",
                    ha="center", va="center",
                )


def draw_attitudes(
    ax,
    att: gpd.GeoDataFrame,
    labels: Optional[gpd.GeoDataFrame] = None,
    strike_len_m: float = 650.0,
    tick_len_m: float = 330.0,
    strike_label_shift_m: float = 270.0,
):
    """绘制产状符号：走向线 + 倾向短刺 + 倾角注记。

    坐标系应为正形投影（如 UTM/Web Mercator），因此可按方位角和米制长度直接绘制，
    走向线与倾向短刺自然严格垂直。

    字段约定（来自 LDZOFBA016.WT）：
    - GZBBAB：走向（°）
    - GZBBAC：倾向（°），与走向相差 90° 或 270°
    - GZBBAD：倾角（°）
    - GZBBGA：产状类型代码（如 202001 层面产状）
    """
    if att is None or att.empty:
        return

    df = att.copy()
    for col in ("GZBBAC", "GZBBAD", "GZBBAB"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            df[col] = np.nan

    df["x"] = df.geometry.x
    df["y"] = df.geometry.y

    # 可选的产状类型样式（颜色待根据图例标准确认）
    type_style = {
        "202001": dict(color="black", linewidth=0.6),   # 层面产状（最常见）
        "202005": dict(color="black", linewidth=0.6), # 变质岩产状（片理/劈理/千枚理）
        "202004": dict(color="#377eb8", linewidth=0.6), # 待确认：线理/擦痕？
        "202011": dict(color="#4daf4a", linewidth=0.6), # 待确认：节理/裂隙？
    }

    # 建立产状注记点索引，用于把 LDZOFBB099 中的数字注记匹配到产状点
    label_tree = None
    label_coords = None
    label_texts = None
    if labels is not None and not labels.empty and "CHFCED" in labels.columns:
        lab = labels[labels["CHFCED"].astype(str).str.strip().str.len() > 0].copy()
        if "CHFCEC" in lab.columns:
            lab = lab[lab["CHFCEC"].astype(str).str.strip() == "产状"]
        if len(lab):
            lab["lx"] = lab.geometry.x
            lab["ly"] = lab.geometry.y
            label_coords = lab[["lx", "ly"]].values
            label_texts = lab["CHFCED"].astype(str).str.strip().values
            label_tree = cKDTree(label_coords)

    for _, row in df.iterrows():
        if pd.isna(row["GZBBAB"]) or pd.isna(row["GZBBAC"]):
            continue
        x, y = float(row["x"]), float(row["y"])
        strike = float(row["GZBBAB"])
        dip_dir = float(row["GZBBAC"])
        dip = int(round(float(row["GZBBAD"]))) if not pd.isna(row["GZBBAD"]) else ""

        strike_rad = math.radians(strike)
        dip_rad = math.radians(dip_dir)

        # 正形投影下直接按方位角和米制长度绘制
        sx, sy = strike_len_m * math.sin(strike_rad), strike_len_m * math.cos(strike_rad)
        dx, dy = tick_len_m * math.sin(dip_rad), tick_len_m * math.cos(dip_rad)

        style = type_style.get(str(row.get("GZBBGA", "")), dict(color="black", linewidth=0.6))

        # 走向线
        code = str(row.get("GZBBGA", ""))
        if code == "202005":
            # 变质岩产状（片理/劈理/千枚理）用双平行线表示
            offset_m = 90.0
            px = -sy / strike_len_m * offset_m
            py = sx / strike_len_m * offset_m
            # 选择位于倾向一侧的那条平行线作为“第一条”，短线连接到它
            if dx * px + dy * py >= 0:
                ox, oy = px, py
            else:
                ox, oy = -px, -py
            # 第一条平行线（倾向侧）
            ax.plot(
                [x - sx + ox, x + sx + ox],
                [y - sy + oy, y + sy + oy],
                **style,
            )
            # 第二条平行线
            ax.plot(
                [x - sx - ox, x + sx - ox],
                [y - sy - oy, y + sy - oy],
                **style,
            )
            # 倾向短刺从第一条平行线中点向倾向方向伸出
            tick_x0, tick_y0 = x + ox, y + oy
        else:
            ax.plot(
                [x - sx, x + sx],
                [y - sy, y + sy],
                **style,
            )
            tick_x0, tick_y0 = x, y
        # 倾向短刺
        ax.plot(
            [tick_x0, tick_x0 + dx],
            [tick_y0, tick_y0 + dy],
            **style,
        )

        # 倾角注记：优先匹配最近的“产状”数字注记，否则使用 GZBBAD
        label_text = str(dip) if dip != "" else ""
        if label_tree is not None:
            dist, idx = label_tree.query([[x, y]], k=1)
            if dist[0] < 20000:  # 20 km 内匹配
                label_text = str(label_texts[idx[0]])

        if label_text:
            # 倾角注记放在真实倾向短刺末端，沿走向方向偏移，黑色显示
            shift_x = strike_label_shift_m * math.sin(strike_rad)
            shift_y = strike_label_shift_m * math.cos(strike_rad)
            lx = tick_x0 + dx + shift_x
            ly = tick_y0 + dy + shift_y
            ax.text(
                lx, ly,
                label_text,
                fontsize=3.5,
                color="black",
                ha="center",
                va="center",
            )


@dataclass
class PreparedLayers:
    """保存已加载、配色、重投影后的全部图层，供 PNG 或 MBTiles 渲染复用。"""
    geology_all: gpd.GeoDataFrame
    overlay_gdfs: List[Tuple[str, gpd.GeoDataFrame]]
    inferred_gdfs: List[gpd.GeoDataFrame]
    water: Dict[str, gpd.GeoDataFrame]
    line_layers: Dict[str, gpd.GeoDataFrame]
    faults: Optional[gpd.GeoDataFrame]
    attitudes: Optional[gpd.GeoDataFrame]
    attitude_labels: Optional[gpd.GeoDataFrame]
    unit_labels: Optional[gpd.GeoDataFrame]
    unit_label_col: Optional[str]
    water_labels: Optional[gpd.GeoDataFrame]


def _load_reconstructed_labels(root: Path, target_crs: str) -> Optional[gpd.GeoDataFrame]:
    """读取重构的完整地质代号标注点；若不存在或读取失败则返回 None。"""
    path = root / "geological_labels_reconstructed.geojson"
    if not path.exists():
        return None
    try:
        gdf = gpd.read_file(path)
        if gdf.empty or "code" not in gdf.columns:
            return None
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        return gdf.to_crs(target_crs)
    except Exception as exc:
        print(f"[warn] failed to load reconstructed labels: {exc}")
        return None


def load_and_prepare_layers(root: Path, target_crs: str) -> PreparedLayers:
    """一次性加载所有图层、完成配色与重投影，返回 PreparedLayers。"""
    geology_layers = [
        "LDZOFBB004",   # 变质基底（阿克苏岩群）先绘
        "LDZOFBB001",   # 主要地层面
        "LDZOFBB002",   # 补充地层面
        "LDZOFBB003",   # 侵入岩绘在最上层
        "LDZOFBB009",   # 断裂带/构造面（仅边界）
        "LDZOFBB010",   # 构造岩浆岩带（仅边界）
    ]

    print("Loading geology polygon layers...")
    layers = load_layers(root, geology_layers, target_crs=target_crs)

    colored_gdfs: List[gpd.GeoDataFrame] = []
    overlay_gdfs: List[Tuple[str, gpd.GeoDataFrame]] = []
    color_stats: Dict[str, int] = {}
    for name, gdf in layers.items():
        if gdf.empty:
            continue
        col = None
        for c in ("QDUECC", "QDUECD"):
            if c in gdf.columns:
                col = c
                break

        if col is None:
            # 非地层代号图层（断裂带、构造岩浆岩带）不填充，仅保留边界
            overlay_gdfs.append((name, gdf.copy()))
            continue

        colors, keys, patterns = [], [], []
        for code in gdf[col].dropna().astype(str).str.strip():
            style = _IR.resolve_unit_style(code)
            rgb = np.array(style["fill"]["rgb"]) / 255.0
            key = style["fill"].get("key") or "unknown"
            pattern = style["fill"].get("pattern")
            colors.append(rgb_to_hex(rgb))
            keys.append(key)
            patterns.append(pattern)
            color_stats[key] = color_stats.get(key, 0) + 1

        gdf = gdf.copy()
        gdf["__color__"] = colors
        gdf["__key__"] = keys
        gdf["__pattern__"] = patterns
        colored_gdfs.append(gdf)

    if not colored_gdfs:
        raise ValueError("No geology polygon layers loaded.")

    geology_all = gpd.GeoDataFrame(
        pd.concat(colored_gdfs, ignore_index=True), crs=colored_gdfs[0].crs
    )

    print("\nColor assignment summary:")
    for key, count in sorted(color_stats.items(), key=lambda x: -x[1]):
        print(f"  {key}: {count}")

    # 推断/解译面边界
    inferred_names = ["LHCPGDAC05", "LHCPGDAC08", "LHCPGDAC11", "LZLPGDJ004", "LZLPGDJ006", "LZLPGDJ009"]
    inferred_gdfs: List[gpd.GeoDataFrame] = []
    for name in inferred_names:
        gdf = load_layers(root, [name], target_crs=target_crs).get(name)
        if gdf is not None and not gdf.empty:
            inferred_gdfs.append(gdf)

    # 水系
    water = load_layers(root, ["LDLYAAE002", "LDLYAAE001", "LDLYAAA005"], target_crs=target_crs)

    # 构造线
    line_files = {
        "LDZOFBA002": dict(color="#333333", linewidth=0.3, label="地质界线"),
        "LDZOFBA003": dict(color="#e41a1c", linewidth=0.7, label="断层"),
        "LDZOFBA005": dict(color="#4daf4a", linewidth=1.0, linestyle="--", label="褶皱轴"),
        "LHCPGDAC01": dict(color="#ff7f00", linewidth=0.6, linestyle="-.", label="物探推断断裂"),
        "LYGREBA001": dict(color="#984ea3", linewidth=0.6, linestyle=":", label="遥感解译线"),
        "LYGREBA004": dict(color="#984ea3", linewidth=0.6, linestyle="-.", label="遥感环形构造"),
        "LZLPGDJ002": dict(color="#e41a1c", linewidth=1.2, linestyle="--", label="深部大断裂"),
        "LHTQGTA001": dict(color="#377eb8", linewidth=0.8, linestyle="-.", label="地球化学界线"),
    }
    line_layers = load_layers(root, list(line_files.keys()), target_crs=target_crs)
    # 给每个线图层附加样式，便于后续统一绘制
    for name, style in line_files.items():
        if name in line_layers:
            line_layers[name].attrs["_style"] = style

    faults = line_layers.get("LDZOFBA003")

    # 产状点与产状注记
    attitudes = load_layers(root, ["LDZOFBA016"], target_crs=target_crs).get("LDZOFBA016")
    raw_labels_all = load_layers(root, ["LDZOFBB099"], target_crs=target_crs).get("LDZOFBB099")
    attitude_labels = None
    if raw_labels_all is not None and not raw_labels_all.empty and "CHFCED" in raw_labels_all.columns:
        attitude_labels = raw_labels_all[
            raw_labels_all["CHFCED"].astype(str).str.strip().str.len() > 0
        ].copy()
        if "CHFCEC" in attitude_labels.columns:
            attitude_labels = attitude_labels[
                attitude_labels["CHFCEC"].astype(str).str.strip() == "产状"
            ]

    # 地质代号注记（优先重构，否则 LDZOFBB099 的“代号”类别）
    unit_labels = _load_reconstructed_labels(root, target_crs)
    unit_label_col = "code"
    if unit_labels is None:
        unit_labels = raw_labels_all
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

    # 水系注记
    water_labels = load_layers(root, ["LDLYAAI002"], target_crs=target_crs).get("LDLYAAI002")

    return PreparedLayers(
        geology_all=geology_all,
        overlay_gdfs=overlay_gdfs,
        inferred_gdfs=inferred_gdfs,
        water=water,
        line_layers=line_layers,
        faults=faults,
        attitudes=attitudes,
        attitude_labels=attitude_labels,
        unit_labels=unit_labels,
        unit_label_col=unit_label_col,
        water_labels=water_labels,
    )


def _filter_by_bounds(gdf: Optional[gpd.GeoDataFrame], bounds: Tuple[float, float, float, float], margin: float = 0.0) -> Optional[gpd.GeoDataFrame]:
    """使用空间索引按 bounds + margin 快速过滤 GeoDataFrame。"""
    if gdf is None or gdf.empty:
        return gdf
    minx, miny, maxx, maxy = bounds
    try:
        return gdf.cx[minx - margin : maxx + margin, miny - margin : maxy + margin]
    except Exception:
        return gdf


def draw_map_content(
    ax,
    prepared: PreparedLayers,
    bounds: Optional[Tuple[float, float, float, float]] = None,
    margin_m: float = 2000.0,
    draw_unit_labels: bool = True,
    unit_label_sample_limit: Optional[int] = 600,
):
    """在指定 bounds 内绘制地图内容（不含标题、比例尺、指北针、图例等整饰）。

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        目标画布。
    prepared : PreparedLayers
        已通过 load_and_prepare_layers 准备好的图层。
    bounds : tuple[float, float, float, float] | None
        (minx, miny, maxx, maxy)。None 时使用 geology_all 的总边界并留 2% 边距。
    margin_m : float
        瓦片边缘缓冲距离，用于避免产状符号/注记被裁切。
    draw_unit_labels : bool
        是否绘制地质代号注记。
    unit_label_sample_limit : int | None
        使用原始 LDZOFBB099 注记时的采样上限；重构注记不受此限制。
    """
    ax.set_aspect("equal")

    if bounds is None:
        total = prepared.geology_all.total_bounds
        minx, miny, maxx, maxy = total
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

    # 标准色地质面
    geology_all = _filter_by_bounds(prepared.geology_all, bounds, margin_m)
    if geology_all is not None and not geology_all.empty:
        geology_all.plot(
            ax=ax,
            color=geology_all["__color__"].values,
            edgecolor="#555555",
            linewidth=0.15,
            alpha=1.0,
        )

    # 非地层构造面带/构造岩浆岩带：只绘边界
    overlay_styles = {
        "LDZOFBB009": dict(edgecolor="#d95f02", linewidth=0.6, linestyle="-"),
        "LDZOFBB010": dict(edgecolor="#8c510a", linewidth=0.5, linestyle="--"),
    }
    for name, ogdf in prepared.overlay_gdfs:
        ogdf = _filter_by_bounds(ogdf, bounds, margin_m)
        if ogdf is None or ogdf.empty:
            continue
        style = overlay_styles.get(name, dict(edgecolor="#555555", linewidth=0.3))
        ogdf.plot(ax=ax, facecolor="none", **style)

    # 推断/解译面边界
    for gdf in prepared.inferred_gdfs:
        gdf = _filter_by_bounds(gdf, bounds, margin_m)
        if gdf is None or gdf.empty:
            continue
        gdf.plot(ax=ax, facecolor="none", edgecolor="#7b3294", linewidth=1.0, linestyle="--", alpha=0.75)

    # 水系
    if "LDLYAAE002" in prepared.water:
        gdf = _filter_by_bounds(prepared.water["LDLYAAE002"], bounds, margin_m)
        if gdf is not None and not gdf.empty:
            gdf.plot(ax=ax, color="#a6cee3", edgecolor="#1f78b4", linewidth=0.25, alpha=0.85)
    for name in ("LDLYAAE001", "LDLYAAA005"):
        if name in prepared.water:
            gdf = _filter_by_bounds(prepared.water[name], bounds, margin_m)
            if gdf is not None and not gdf.empty:
                gdf.plot(ax=ax, color="#1f78b4", linewidth=0.4)

    # 构造线（断层线由 draw_faults_with_styles 单独绘制，避免双重绘制）
    fault_sources = {"LDZOFBA003", "LYGREBA001", "LZLPGDJ002"}
    for name, gdf in prepared.line_layers.items():
        if name in fault_sources:
            continue
        gdf = _filter_by_bounds(gdf, bounds, margin_m)
        if gdf is None or gdf.empty:
            continue
        style = gdf.attrs.get("_style", dict(color="#555555", linewidth=0.3))
        gdf.plot(ax=ax, **style)

    # 断层构造：按 fault_rendering_styles.json 绘制线型、符号与注记
    draw_faults_with_styles(ax, prepared.line_layers, ROOT)

    # 产状符号
    att = _filter_by_bounds(prepared.attitudes, bounds, margin_m)
    att_labels = _filter_by_bounds(prepared.attitude_labels, bounds, margin_m)
    draw_attitudes(ax, att, labels=att_labels)

    # 地质代号注记
    if draw_unit_labels and prepared.unit_labels is not None and prepared.unit_label_col is not None:
        sub = _filter_by_bounds(prepared.unit_labels, bounds, margin_m)
        if sub is not None and not sub.empty:
            if prepared.unit_label_col == "CHFCED" and unit_label_sample_limit and len(sub) > unit_label_sample_limit:
                sub = sub.sample(unit_label_sample_limit, random_state=1)
            for x, y, label in zip(sub.geometry.x, sub.geometry.y, sub[prepared.unit_label_col]):
                try:
                    display_label = format_label(str(label).strip())
                except Exception:
                    display_label = str(label).strip()
                ax.text(
                    x, y, display_label, fontsize=4, color="black",
                    ha="center", va="center",
                    path_effects=[pe.withStroke(linewidth=2, foreground="white")],
                )

    # 水系注记
    if prepared.water_labels is not None and not prepared.water_labels.empty and "NAME" in prepared.water_labels.columns:
        sub = _filter_by_bounds(prepared.water_labels, bounds, margin_m)
        if sub is not None and not sub.empty:
            sub = sub[sub["NAME"].astype(str).str.strip().str.len() > 0]
            for x, y, label in zip(sub.geometry.x, sub.geometry.y, sub["NAME"]):
                ax.text(
                    x, y, str(label).strip(), fontsize=5, color="#1f78b4",
                    ha="center", va="center", style="italic",
                    path_effects=[pe.withStroke(linewidth=2, foreground="white")],
                )


def main() -> int:
    prepared = load_and_prepare_layers(ROOT, TARGET_CRS)

    fig, ax = plt.subplots(figsize=(14, 13))
    draw_map_content(ax, prepared, bounds=None, draw_unit_labels=True)

    # 图幅整饰
    ax.set_title("1:250000 库尔干幅（J43C001002）DZ/T 0179 标准色地质图（UTM Zone 43N）", fontsize=15, pad=12)
    ax.set_xlabel("东向 (m)", fontsize=10)
    ax.set_ylabel("北向 (m)", fontsize=10)

    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    add_scale_bar(
        ax,
        (xlim[0] + (xlim[1] - xlim[0]) * 0.05, ylim[0] + (ylim[1] - ylim[0]) * 0.05),
        length_km=20,
    )
    add_north_arrow(
        ax,
        (xlim[1] - (xlim[1] - xlim[0]) * 0.08, ylim[1] - (ylim[1] - ylim[0]) * 0.08),
    )

    legend_elems = [
        Line2D([0], [0], color="#e41a1c", lw=0.7, linestyle="-", label="实测断层"),
        Line2D([0], [0], color="#e41a1c", lw=0.6, linestyle="-.", label="遥感解译断层"),
        Line2D([0], [0], color="#e41a1c", lw=1.5, linestyle="--", label="深部大断裂"),
        Line2D([0], [0], color="#4daf4a", lw=1.5, linestyle="--", label="褶皱轴"),
        Line2D([0], [0], color="#333333", lw=1, label="地质界线"),
        Line2D([0], [0], color="#1f78b4", lw=1, label="河流/水系"),
        Line2D([0], [0], color="#ff7f00", lw=1, linestyle="-.", label="物探推断断裂"),
        Line2D([0], [0], color="#984ea3", lw=1, linestyle=":", label="遥感解译线"),
        Line2D([0], [0], color="#7b3294", lw=1, linestyle="--", label="推断地质体面边界"),
        Line2D([0], [0], color="#8c510a", lw=1, linestyle="--", label="构造岩浆岩带边界"),
        Line2D([0], [0], color="#d95f02", lw=1, label="断裂带（面）边界"),
    ]
    ax.legend(handles=legend_elems, loc="lower right", fontsize=8, framealpha=0.92)

    out_path = ROOT / "kurgan_strict_standard_map.png"
    plt.savefig(out_path, dpi=200, bbox_inches="tight", pad_inches=0.2)
    print(f"\nSaved: {out_path}")
    plt.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
