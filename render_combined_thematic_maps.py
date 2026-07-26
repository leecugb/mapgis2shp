#!/usr/bin/env python3
"""将 LDZO 地质-建造构造专题图与 LDLY 水系专题图合并为一张图。"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent / "src"))

import render_strict_standard_map as rssm
from render_thematic_maps import (
    draw_theme_content,
    prepare_ldly_theme,
    prepare_ldzo_theme,
    _add_decorations,
)

ROOT = Path(__file__).parent
TARGET_CRS = rssm.TARGET_CRS


def main() -> int:
    print("Preparing LDZO theme...")
    ldzo = prepare_ldzo_theme(ROOT, TARGET_CRS)
    print("Preparing LDLY theme...")
    ldly = prepare_ldly_theme(ROOT, TARGET_CRS)

    # 合并边界，使两张子图使用同一地理范围，便于对比
    minx = min(ldzo.bounds[0], ldly.bounds[0])
    miny = min(ldzo.bounds[1], ldly.bounds[1])
    maxx = max(ldzo.bounds[2], ldly.bounds[2])
    maxy = max(ldzo.bounds[3], ldly.bounds[3])
    common_bounds = (minx, miny, maxx, maxy)
    ldzo.bounds = common_bounds
    ldly.bounds = common_bounds

    fig, axes = plt.subplots(1, 2, figsize=(22, 11))

    # 左侧：LDZO 地质-建造构造
    ax1 = axes[0]
    draw_theme_content(ax1, ldzo, "地质-建造构造专题（LDZO）")
    ldzo_legend = [
        rssm.Line2D([0], [0], color="#e41a1c", lw=0.7, linestyle="-", label="断层"),
        rssm.Line2D([0], [0], color="#333333", lw=1, label="地质界线"),
        rssm.Line2D([0], [0], color="#4daf4a", lw=1.5, linestyle="--", label="褶皱轴"),
    ]
    _add_decorations(ax1, ldzo, ldzo_legend)

    # 右侧：LDLY 水系
    ax2 = axes[1]
    draw_theme_content(ax2, ldly, "水系专题（LDLY）")
    ldly_legend = [
        rssm.Line2D([0], [0], color="#1f78b4", lw=1, label="河流/水系线"),
    ]
    _add_decorations(ax2, ldly, ldly_legend)

    fig.suptitle(
        "1:250000 库尔干幅（J43C001002）专题图",
        fontsize=16,
        y=0.98,
    )

    out_path = ROOT / "kurgan_thematic_combined.png"
    plt.savefig(out_path, dpi=200, bbox_inches="tight", pad_inches=0.25)
    print(f"Saved: {out_path}")
    plt.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
