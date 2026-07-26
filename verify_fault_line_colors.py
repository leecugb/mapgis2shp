#!/usr/bin/env python3
"""核实断裂线颜色：单独渲染三类断层线，验证其与 fault_rendering_styles.json 配置一致。

输出：
- fault_color_verify.png：白底上的三类断层线颜色样例
- fault_color_verify_report.md：颜色配置与采样核对报告
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

import render_strict_standard_map as rsm
from render_faults import draw_faults_with_styles

ROOT = Path(__file__).parent
TARGET_CRS = "EPSG:32643"

import sys
sys.path.insert(0, str(ROOT / "src"))
from pymapgis.rendering import load_ir


def render_faults_only(root: Path, out_path: Path):
    """在白底上单独绘制断层线，便于目视核对颜色。"""
    line_layers = rsm.load_layers(root, ["LDZOFBA003", "LYGREBA001", "LZLPGDJ002"], target_crs=TARGET_CRS)

    fig, ax = plt.subplots(figsize=(14, 13))
    ax.set_aspect("equal")
    ax.set_facecolor("white")

    # 先按 IR 的 rules.faults 绘制基础线
    ir = load_ir(root / "dz_t_0179_rendering_rules.json")
    fault_rules = ir.rules.get("faults", {})
    line_styles = ir.line_styles
    if fault_rules:
        for src_name, src_cfg in fault_rules.get("sources", {}).items():
            gdf = line_layers.get(src_name)
            if gdf is None or gdf.empty:
                continue
            base_ir = src_cfg.get("base_style", {})
            ref = base_ir.get("ref")
            if ref and ref in line_styles:
                resolved = line_styles[ref]
                color = resolved.get("color")
                linewidth = resolved.get("width")
                linestyle = resolved.get("linestyle", "-")
            else:
                color = base_ir.get("color", "#000000")
                linewidth = base_ir.get("linewidth", 0.5)
                linestyle = base_ir.get("linestyle", "-")
            gdf.plot(ax=ax, color=color, linewidth=linewidth,
                     linestyle=linestyle, alpha=base_ir.get("alpha", 1.0),
                     label=src_cfg.get("data_type", src_name))

    # 再叠加符号与注记
    draw_faults_with_styles(ax, line_layers, root)

    # 图例
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="lower right", fontsize=9)

    ax.set_title("断裂线颜色核实（白底）", fontsize=14)
    plt.savefig(out_path, dpi=200, bbox_inches="tight", pad_inches=0.2)
    plt.close()
    print(f"Saved: {out_path}")


def sample_line_color(img: Image.Image, rgb: List[int], tol: int = 8) -> Dict:
    """在图像中搜索与给定颜色相近的像素比例。"""
    arr = np.array(img.convert("RGB"))
    diff = np.abs(arr - np.array(rgb)).max(axis=2)
    mask = diff <= tol
    ratio = mask.sum() / mask.size
    return {
        "expected_rgb": rgb,
        "expected_hex": "#{:02x}{:02x}{:02x}".format(*rgb),
        "pixel_count": int(mask.sum()),
        "ratio_percent": round(ratio * 100, 4),
        "detected": ratio > 0.0001,
    }


def main() -> int:
    out_png = ROOT / "fault_color_verify.png"
    render_faults_only(ROOT, out_png)

    # 从 IR 读取预期颜色
    ir = load_ir(ROOT / "dz_t_0179_rendering_rules.json")
    fault_rules = ir.rules.get("faults", {})
    line_styles = ir.line_styles
    expected = {}
    for src_name, src_cfg in fault_rules.get("sources", {}).items():
        base_ir = src_cfg.get("base_style", {})
        ref = base_ir.get("ref")
        if ref and ref in line_styles:
            c = line_styles[ref]["color"]
        else:
            c = base_ir.get("color", "#000000")
        expected[src_name] = [int(c[i:i+2], 16) for i in (1, 3, 5)]

    img = Image.open(out_png)
    report_lines = [
        "# 断裂线颜色核实报告\n",
        "## 1. 配置颜色\n",
        "| 数据源 | 配置颜色 | RGB |",
        "|--------|----------|-----|",
    ]
    for src, rgb in expected.items():
        hex_c = "#{:02x}{:02x}{:02x}".format(*rgb)
        report_lines.append(f"| `{src}` | {hex_c} | {rgb} |")

    report_lines.extend(["\n## 2. 白底样图采样核对\n",
                          "| 数据源 | 预期 HEX | 像素数 | 占比(%) | 是否检出 |"])
    report_lines.append("|--------|----------|--------|---------|----------|")
    for src, rgb in expected.items():
        res = sample_line_color(img, rgb)
        report_lines.append(
            f"| `{src}` | {res['expected_hex']} | {res['pixel_count']} | "
            f"{res['ratio_percent']} | {'✅' if res['detected'] else '❌'} |"
        )

    report_lines.extend([
        "\n## 3. 说明\n",
        "- `fault_color_verify.png` 为白底上单独绘制的三类断层线，便于目视核对颜色；\n",
        "- 若某颜色未检出，请检查 IR `line_styles` 或 `rules.faults.sources.base_style` 配置。\n",
    ])

    report_md = ROOT / "fault_color_verify_report.md"
    report_md.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Saved: {report_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
