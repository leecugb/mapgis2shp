#!/usr/bin/env python3
"""生成花纹瓦片校验图（checkerboard）并与原始 PDF 表页对比。

对每个已验证的 pattern：
1. 绘制一个底色方块（用其对应的 DZ/T 0179 标准色）。
2. 在其上叠加 pattern 花纹。
3. 把原始 PDF 裁剪出的花纹瓦片并排显示。

输出：data/pattern_swatches/checkerboard.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from pymapgis.rendering import load_ir
from pymapgis.rendering.pattern_engine import PatternEngine
from shapely.geometry import Polygon

IR_PATH = ROOT / "dz_t_0179_rendering_rules.json"
OUTPUT = ROOT / "data" / "pattern_swatches" / "checkerboard.png"


def hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))


def main() -> int:
    ir = load_ir(IR_PATH)
    patterns = {
        k: v for k, v in ir.patterns.items()
        if v.get("verified") not in ("no", "")
    }
    if not patterns:
        print("No verified patterns found.")
        return 0

    n = len(patterns)
    cols = 4
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3, rows * 3))
    if rows == 1:
        axes = np.array([axes]).reshape(1, -1)
    axes = axes.flatten()

    engine = PatternEngine(ir.patterns, root=ROOT)

    for idx, (pattern_id, pattern) in enumerate(sorted(patterns.items())):
        ax = axes[idx]
        name = pattern.get("name", pattern_id)
        ptype = pattern.get("type", "image")

        # 示例多边形：正方形
        square = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])

        # 底色：尝试用 source pdf_page 推断，否则用浅灰
        base_color = (0.95, 0.95, 0.9)
        source_table = str(pattern.get("source", {}).get("table", ""))
        if "表5" in source_table:
            base_color = (1.0, 1.0, 0.8)  # Quaternary yellowish

        # 绘制底色
        ax.fill(*square.exterior.xy, color=base_color, edgecolor="black", linewidth=1)
        # 叠加花纹
        engine.render(ax, [square], pattern_id, base_color=base_color, alpha=1.0, zorder=2)

        ax.set_title(f"{name}\n{pattern_id}", fontsize=8)
        ax.set_aspect("equal")
        ax.axis("off")

        # 右侧显示原始瓦片缩略图
        tile_path = ROOT / pattern.get("tile_file", "")
        if tile_path.exists():
            inset_ax = ax.inset_axes([0.65, 0.65, 0.3, 0.3])
            tile = Image.open(tile_path)
            inset_ax.imshow(np.array(tile))
            inset_ax.axis("off")
            inset_ax.set_title("tile", fontsize=6, pad=2)

    # 隐藏多余子图
    for idx in range(n, len(axes)):
        axes[idx].axis("off")

    plt.tight_layout()
    fig.savefig(OUTPUT, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Checkerboard saved to: {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
