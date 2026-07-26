#!/usr/bin/env python3
"""合成测试图：在白底上绘制标准正断层（barbs）与逆/冲断层（三角齿）几何样式，
与 DZ/T 0179 表22 图例直接对照。
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon

ROOT = Path(__file__).parent
OUT_PNG = ROOT / "fault_style_synthetic_test.png"

RED = "#e41a1c"


def draw_fault_line(ax, x0, y0, angle_deg, length, symbol_type: str, side: str = "right",
                    spacing: float = 1200.0, tick_len: float = 500.0, tooth_len: float = 600.0):
    """绘制一段带符号的断层线。"""
    angle = math.radians(angle_deg)
    ux, uy = math.sin(angle), math.cos(angle)

    # 右/左法向量
    if side == "right":
        nx, ny = uy, -ux
    else:
        nx, ny = -uy, ux

    x1 = x0 + length * ux / 2
    y1 = y0 + length * uy / 2
    x2 = x0 - length * ux / 2
    y2 = y0 - length * uy / 2
    ax.plot([x2, x1], [y2, y1], color=RED, linewidth=1.0, solid_capstyle="butt")

    n = max(1, int(length / spacing))
    for i in range(n + 1):
        t = i / n
        px = x2 + t * (x1 - x2)
        py = y2 + t * (y1 - y2)

        if symbol_type == "normal":
            ax.plot([px, px + tick_len * nx], [py, py + tick_len * ny],
                    color=RED, linewidth=1.0, solid_capstyle="butt")
        elif symbol_type == "reverse":
            half_base = tooth_len * 0.35
            bx1 = px - half_base * ux
            by1 = py - half_base * uy
            bx2 = px + half_base * ux
            by2 = py + half_base * uy
            tx = px + tooth_len * nx
            ty = py + tooth_len * ny
            poly = Polygon([(bx1, by1), (bx2, by2), (tx, ty)],
                           closed=True, facecolor=RED, edgecolor=RED, linewidth=0.5)
            ax.add_patch(poly)


def main() -> int:
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_aspect("equal")
    ax.set_xlim(-500, 6500)
    ax.set_ylim(-500, 3500)
    ax.set_facecolor("white")

    # 正断层：barbs 指向下降盘（右侧）
    draw_fault_line(ax, 1500, 2500, 20, 4000, "normal", side="right",
                    spacing=900, tick_len=550)
    ax.text(1500, 3200, "正断层（实测）：实线 + 垂直短齿（barbs）",
            fontsize=12, ha="center", va="center", color="black", fontweight="bold")

    # 逆/冲断层：三角齿指向上盘（右侧）
    draw_fault_line(ax, 4500, 2500, 20, 4000, "reverse", side="right",
                    spacing=900, tooth_len=650)
    ax.text(4500, 3200, "逆/冲断层（实测）：实线 +  filled 三角齿",
            fontsize=12, ha="center", va="center", color="black", fontweight="bold")

    # 与表22 文字对应
    ax.text(3250, 500,
            "对照：DZ/T 0179 表22\n"
            "· 实测正断层/逆断层：实线 + 齿/三角齿\n"
            "· 实测冲断层：实线 + 三角齿",
            fontsize=11, ha="center", va="center", color="darkgreen",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="white", edgecolor="darkgreen", alpha=0.9))

    ax.axis("off")
    plt.savefig(OUT_PNG, dpi=300, bbox_inches="tight", pad_inches=0.2)
    plt.close()
    print(f"Saved: {OUT_PNG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
