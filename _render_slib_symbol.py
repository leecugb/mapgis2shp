"""渲染 Subgraph.lib 指定符号号为 PNG（矢量描边，等比例 mm 坐标）。

用法：python _render_slib_symbol.py [符号号] [输出.png]
默认：子图 21 → _symbol_21.png
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Arc as MplArc, Circle as MplCircle

from pymapgis.slib import SubgraphLib, symbol_geometries

LIB = r"D:/SLIB/Subgraph.lib"


def main(no: int, out: str, view=None) -> None:
    lib = SubgraphLib(LIB)
    geo = symbol_geometries(lib, no)
    if "error" in geo:
        raise SystemExit(f"decode failed: {geo['error']}")

    fig, ax = plt.subplots(figsize=(4.2, 4.2))
    ax.set_aspect("equal")

    # 参考系：0.1mm 浅网格 + 原点十字
    for g in range(-5, 6):
        ax.axvline(g / 10, color="#dddddd", lw=0.4, zorder=0)
        ax.axhline(g / 10, color="#dddddd", lw=0.4, zorder=0)
    ax.plot([-0.15, 0.15], [0, 0], color="#bbbbbb", lw=0.6, zorder=1)
    ax.plot([0, 0], [-0.15, 0.15], color="#bbbbbb", lw=0.6, zorder=1)

    # 几何绘制策略（2026-10-18 图面裁定）：
    #   三点参数组（圆/弧）——存储点是参数而非几何，必须按参数画；
    #   密集弧整圆——补丁（v 时代裁定通过）；
    #   密集部分弧——忠实描存储点（拟合补丁对 partial arc 有
    #   0.07–0.13mm 弦偏差，#23 sp0-3 实证，不得替代原数据）。
    for sp in geo["subpaths"]:
        n = len(sp["points"])
        if sp["arc"] and n == 3:
            cx, cy, r, a0, a1 = sp["arc"]
            ax.add_patch(MplArc((cx, cy), 2 * r, 2 * r, angle=0,
                                theta1=a0, theta2=a1,
                                ec="black", lw=1.0, zorder=2))
        elif sp["circle"] and n == 3:
            cx, cy, r = sp["circle"]
            ax.add_patch(MplCircle((cx, cy), r, fill=False,
                                   ec="black", lw=1.0, zorder=2))
        elif sp["circle"]:
            cx, cy, r = sp["circle"]
            ax.add_patch(MplCircle((cx, cy), r, fill=False,
                                   ec="black", lw=1.0, zorder=2))
        else:
            xs = [p[0] for p in sp["points"]]
            ys = [p[1] for p in sp["points"]]
            ax.plot(xs, ys, color="black", lw=1.0, zorder=2,
                    marker=None, solid_capstyle="round")

    ax.set_title(f"Subgraph #{no} (type={geo['type']}, {len(geo['subpaths'])} subpaths)")
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    ax.margins(0.15)
    if view is not None:
        x0, y0, x1, y1 = view
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    print(f"saved: {out}")
    print(f"no={geo['no']} type={geo['type']} bbox={geo['bbox']} "
          f"circles={geo['circles']}")
    for i, sp in enumerate(geo["subpaths"]):
        print(f"  sp{i}: closed={sp['closed']} npts={len(sp['points'])}")


if __name__ == "__main__":
    no = int(sys.argv[1]) if len(sys.argv) > 1 else 21
    out = sys.argv[2] if len(sys.argv) > 2 else f"_symbol_{no}.png"
    view = None
    if len(sys.argv) > 3:
        view = tuple(float(v) for v in sys.argv[3].split(","))
    main(no, out, view)
