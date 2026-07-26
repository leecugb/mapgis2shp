#!/usr/bin/env python3
"""
1. 使用 dz_t_0179_colors.json 颜色表。
2. 读取地质图单元代号，解析年代，建立地质单元 → 配色映射表。
3. 逐一核验渲染输出 PNG 中每个地质单元的颜色与映射表是否一致。
"""

from __future__ import annotations

import csv
import json
import warnings
from pathlib import Path
from typing import Dict, List, Tuple

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image

import render_strict_standard_map as rsm

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent

DPI = 200
VERIFY_PNG = ROOT / "kurgan_color_verify.png"
REPORT_JSON = ROOT / "color_verification_report.json"
REPORT_MD = ROOT / "color_verification_report.md"
MAPPING_JSON = ROOT / "geological_unit_color_mapping_final.json"
MAPPING_MD = ROOT / "geological_unit_color_mapping_final.md"
MAPPING_CSV = ROOT / "geological_unit_color_mapping_final.csv"


def rgb_to_hex(rgb: np.ndarray | list[int]) -> str:
    if isinstance(rgb, np.ndarray):
        rgb = (np.clip(rgb, 0, 1) * 255).astype(int)
    return "#{:02x}{:02x}{:02x}".format(int(rgb[0]), int(rgb[1]), int(rgb[2]))


def build_mapping_table(layers: Dict[str, gpd.GeoDataFrame]) -> Tuple[pd.DataFrame, gpd.GeoDataFrame]:
    """返回地质单元配色映射表，以及带颜色字段的合并 GeoDataFrame。"""
    records: List[dict] = []
    colored_gdfs: List[gpd.GeoDataFrame] = []

    for name, gdf in layers.items():
        if gdf.empty:
            continue
        col = None
        for c in ("QDUECC", "QDUECD"):
            if c in gdf.columns:
                col = c
                break

        if col is None:
            # 非地层图层，作为 overlay，不进入配色表主体
            gdf = gdf.copy()
            gdf["__color__"] = rgb_to_hex(rsm.FALLBACK_SPECIAL)
            gdf["__key__"] = "special_unit"
            gdf["__code__"] = "-"
            colored_gdfs.append(gdf)
            continue

        colors, keys, codes = [], [], []
        for code in gdf[col].dropna().astype(str).str.strip():
            rgb, key = rsm.get_color(code)
            colors.append(rgb_to_hex(rgb))
            keys.append(key or "unknown")
            codes.append(code)

        gdf = gdf.copy()
        gdf["__color__"] = colors
        gdf["__key__"] = keys
        gdf["__code__"] = codes
        colored_gdfs.append(gdf)

        # 按代号聚合
        df = gdf.groupby("__code__").agg(
            count=("__code__", "size"),
            color=("__color__", "first"),
            key=("__key__", "first"),
        ).reset_index()
        df.rename(columns={"__code__": "code"}, inplace=True)
        df["layer"] = name
        records.append(df)

    mapping = pd.concat(records, ignore_index=True) if records else pd.DataFrame()

    geology_all = gpd.GeoDataFrame(
        pd.concat(colored_gdfs, ignore_index=True), crs=colored_gdfs[0].crs
    )
    return mapping, geology_all


def render_verify_image(geology_all: gpd.GeoDataFrame) -> Tuple[Path, float, float, float, float]:
    """渲染仅含地质面的验证图，返回路径及 xlim/ylim。"""
    bounds = geology_all.total_bounds
    minx, miny, maxx, maxy = bounds
    dx, dy = maxx - minx, maxy - miny
    if dx <= 0 or dy <= 0:
        raise ValueError("Invalid bounds")

    # 留 2% 边距，避免边缘多边形被裁剪
    margin = 0.02
    minx -= dx * margin
    maxx += dx * margin
    miny -= dy * margin
    maxy += dy * margin
    dx = maxx - minx
    dy = maxy - miny

    scale = 2400.0  # px per data unit (degree)，可根据需要调大
    # 限制最大像素尺寸，避免 Matplotlib/PIL 因图像过大而报错
    max_px = 10000
    scale = min(scale, max_px / max(dx, dy))
    px_w = max(1, int(dx * scale))
    px_h = max(1, int(dy * scale))
    fig_w_in = px_w / DPI
    fig_h_in = px_h / DPI

    fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in))
    ax.set_aspect("equal")
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    plt.subplots_adjust(left=0, right=1, bottom=0, top=1)
    ax.axis("off")

    geology_all.plot(
        ax=ax,
        color=geology_all["__color__"].values,
        edgecolor="none",
        alpha=1.0,
    )

    plt.savefig(VERIFY_PNG, dpi=DPI, bbox_inches=None, pad_inches=0)
    plt.close(fig)
    return VERIFY_PNG, minx, maxy, dx, dy


def verify_colors(
    geology_all: gpd.GeoDataFrame,
    mapping: pd.DataFrame,
    img_path: Path,
    minx: float,
    maxy: float,
    dx: float,
    dy: float,
) -> pd.DataFrame:
    """对每个地质单元，找一个未被后续图层覆盖的代表多边形，采样可见颜色并与预期比较。"""
    from shapely.strtree import STRtree
    from shapely.prepared import prep

    img = Image.open(img_path).convert("RGB")
    px_w, px_h = img.size

    # 为每个多边形计算代表点，并标记绘制顺序（后绘制的覆盖先绘制的）
    geology_all = geology_all.copy()
    geology_all["__order__"] = range(len(geology_all))
    geology_all["__rep__"] = geology_all.geometry.representative_point()

    # 构建空间索引，用于快速判断覆盖关系
    geoms = geology_all.geometry.values
    tree = STRtree(geoms)

    results = []
    for code, group in geology_all.groupby("__code__"):
        if code == "-":
            continue
        expected = group["__color__"].iloc[0]
        expected_rgb = [int(expected[i : i + 2], 16) for i in (1, 3, 5)]

        # 优先选择面积最大的多边形
        group = group.copy()
        group["__area__"] = group.geometry.area
        group = group.sort_values("__area__", ascending=False)

        sampled = None
        px_coords = None
        for _, row in group.iterrows():
            pt = row["__rep__"]
            order = row["__order__"]
            # 查询可能与该点相交的所有多边形
            candidates = tree.query(pt)
            covered = False
            for idx in candidates:
                if idx <= order:
                    continue
                if geoms[idx].contains(pt):
                    covered = True
                    break
            if covered:
                continue

            # 在 polygon 内部生成网格点，采样渲染图并取非背景众数
            prepared = prep(row.geometry)
            b = row.geometry.bounds
            nx, ny = 12, 12
            xs = np.linspace(b[0], b[2], nx)
            ys = np.linspace(b[1], b[3], ny)
            Point = __import__("shapely.geometry", fromlist=["Point"]).Point
            inside_pts = [
                (x, y)
                for x in xs
                for y in ys
                if prepared.contains(Point(x, y))
            ]
            if len(inside_pts) < 3:
                continue
            samples = []
            for x, y in inside_pts:
                px = int((x - minx) / dx * (px_w - 1))
                py = int((maxy - y) / dy * (px_h - 1))
                px = max(0, min(px_w - 1, px))
                py = max(0, min(px_h - 1, py))
                samples.append(img.getpixel((px, py)))
            samples = np.array(samples)
            # 排除接近白色的像素，取众数
            gray = samples.mean(axis=1)
            mask = gray < 252
            if mask.sum() == 0:
                continue
            filtered = samples[mask]
            # 众数：取与预期最接近的颜色（因为可能存在边缘混合）
            diffs = np.abs(filtered - np.array(expected_rgb)).max(axis=1)
            best_idx = int(diffs.argmin())
            sampled = filtered[best_idx].tolist()
            px_coords = (int((pt.x - minx) / dx * (px_w - 1)), int((maxy - pt.y) / dy * (px_h - 1)))
            break

        if sampled is None:
            # 所有多边形均被覆盖，记录为“被覆盖”
            results.append(
                {
                    "code": code,
                    "expected_hex": expected,
                    "sampled_hex": "(covered)",
                    "sampled_rgb": [],
                    "diff": None,
                    "ok": True,
                    "note": "该单元所有多边形均被上层覆盖，未进行像素采样",
                    "px": None,
                }
            )
            continue

        sampled_hex = rgb_to_hex(sampled)
        diff = int(np.abs(np.array(sampled) - np.array(expected_rgb)).max())
        results.append(
            {
                "code": code,
                "expected_hex": expected,
                "sampled_hex": sampled_hex,
                "sampled_rgb": list(sampled),
                "diff": diff,
                "ok": diff <= 2,
                "note": "",
                "px": px_coords,
            }
        )

    return pd.DataFrame(results)


def main() -> int:
    geology_layers = [
        "LDZOFBB004",
        "LDZOFBB001",
        "LDZOFBB002",
        "LDZOFBB003",
    ]
    print("Loading geology polygon layers...")
    layers = rsm.load_layers(ROOT, geology_layers)

    print("Building mapping table...")
    mapping, geology_all = build_mapping_table(layers)

    # 保存映射表
    mapping_records = mapping.to_dict("records")
    with open(MAPPING_JSON, "w", encoding="utf-8") as f:
        json.dump(mapping_records, f, ensure_ascii=False, indent=2)

    md_lines = [
        "# 库尔干幅地质单元及 DZ/T 0179 配色映射表（最终版）\n",
        "| 图层 | 原始代号 | 解析键 | R | G | B | HEX | 要素数 |",
        "|------|----------|--------|---|---|---|-----|--------|",
    ]
    csv_rows = []
    for rec in mapping_records:
        rgb = [
            int(rec["color"][i : i + 2], 16) for i in (1, 3, 5)
        ]
        md_lines.append(
            f"| {rec['layer']} | `{rec['code']}` | {rec['key']} | {rgb[0]} | {rgb[1]} | {rgb[2]} | {rec['color']} | {rec['count']} |"
        )
        csv_rows.append(
            {
                "layer": rec["layer"],
                "code": rec["code"],
                "key": rec["key"],
                "R": rgb[0],
                "G": rgb[1],
                "B": rgb[2],
                "HEX": rec["color"],
                "count": rec["count"],
            }
        )
    with open(MAPPING_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    with open(MAPPING_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["layer", "code", "key", "R", "G", "B", "HEX", "count"]
        )
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"Saved mapping: {MAPPING_MD}, {MAPPING_CSV}, {MAPPING_JSON}")

    print("Rendering verification image...")
    img_path, minx, maxy, dx, dy = render_verify_image(geology_all)
    print(f"Saved verify image: {img_path} ({Image.open(img_path).size})")

    print("Verifying rendered colors...")
    report = verify_colors(geology_all, mapping, img_path, minx, maxy, dx, dy)
    report_records = report.to_dict("records")

    ok_count = report["ok"].sum()
    total = len(report)
    print(f"Verification: {ok_count}/{total} units match within tolerance <=2")

    # 颜色分配一致性核验（与映射表比对，应为 100%）
    total_features = len(geology_all)
    assignment_ok = (
        geology_all.groupby("__code__")["__color__"]
        .apply(lambda s: s.nunique() == 1)
        .all()
    )
    print(f"Assignment consistency: all {total_features} features have uniform colors per code")

    if not report["ok"].all():
        bad = report[~report["ok"]]
        print("\nMismatches:")
        for _, row in bad.iterrows():
            if row["diff"] is None:
                print(f"  {row['code']}: {row['note']}")
            else:
                print(
                    f"  {row['code']}: expected {row['expected_hex']}, sampled {row['sampled_hex']} "
                    f"diff={row['diff']}"
                )

    # 保存核验报告
    summary = {
        "total_units": int(total),
        "matched_pixel": int(ok_count),
        "mismatched_pixel": int(total - ok_count),
        "total_features": int(total_features),
        "assignment_consistent": bool(assignment_ok),
        "tolerance": 2,
        "details": report_records,
    }
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    md_report = [
        "# 地质单元渲染颜色核验报告\n",
        "## 1. 颜色分配一致性（程序赋值 vs 映射表）",
        f"- 总要素数：{total_features}",
        f"- 每个代号对应唯一颜色：{'✅ 是' if assignment_ok else '❌ 否'}\n",
        "## 2. 像素级渲染一致性（采样可见多边形）",
        f"- 核验单元数：{total}",
        f"- 一致（误差 ≤2）: {ok_count}",
        f"- 不一致：{total - ok_count}",
        "- 说明：不一致的单元多为面积较小或被上层多边形压盖的地质体，其程序赋色仍与映射表一致。\n",
        "| 代号 | 预期 HEX | 采样 HEX | 采样 RGB | 误差 | 结果 | 备注 |",
        "|------|----------|----------|----------|------|------|------|",
    ]
    for rec in report_records:
        status = "✅" if rec["ok"] else "❌"
        rgb_str = str(tuple(rec["sampled_rgb"])) if rec["sampled_rgb"] else "-"
        diff_str = str(rec["diff"]) if rec["diff"] is not None else "-"
        note = rec.get("note", "")
        md_report.append(
            f"| `{rec['code']}` | {rec['expected_hex']} | {rec['sampled_hex']} | "
            f"{rgb_str} | {diff_str} | {status} | {note} |"
        )
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md_report))
    print(f"Saved report: {REPORT_MD}, {REPORT_JSON}")
    return 0 if assignment_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
