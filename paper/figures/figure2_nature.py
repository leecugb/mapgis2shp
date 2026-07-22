#!/usr/bin/env python3
"""Figure 2 — mapgis2shp reader architecture and data flow.

Overlap-free layout: clear vertical bands, <=2 lines per box, bypasses
separated from the main pipeline. PNG (300 dpi) + editable PDF.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch

INK = "#1a1a1a"
SUB = "#6b6b6b"
ACCENT = "#2c6fbb"
ACCENT_SOFT = "#dce8f4"
AMBER = "#c98a2b"
AMBER_SOFT = "#f3e6cf"
CRS_C = "#7d5ba6"
CRS_SOFT = "#e7ddf0"
TOPO = "#5aa070"
TOPO_SOFT = "#dcefe0"
VALID_C = "#4a7c8c"
VALID_SOFT = "#dfeaec"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
    "font.size": 7, "axes.linewidth": 0.6, "text.color": INK,
})


def block(ax, x, y, w, h, fc, ec=INK, lw=0.8):
    ax.add_patch(Rectangle((x, y), w, h, facecolor=fc, edgecolor=ec,
                           linewidth=lw, zorder=2))


def label(ax, x, y, text, fs=6.6, weight="normal", color=INK, ha="center",
          va="center", style="normal"):
    ax.text(x, y, text, fontsize=fs, fontweight=weight, color=color, ha=ha,
            va=va, style=style, zorder=3)


def arrow(ax, x0, y0, x1, y1, color=INK, lw=1.0, style="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style,
                                 mutation_scale=9, lw=lw, color=color,
                                 linestyle=ls, zorder=1,
                                 shrinkA=0, shrinkB=0))


def panel_label(ax, x, y, letter):
    ax.text(x, y, letter, fontsize=10, fontweight="bold", color=INK,
            ha="left", va="bottom")


def figure2(png_path: str, pdf_path: str) -> None:
    fig, ax = plt.subplots(figsize=(7.4, 5.3))
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.set_axis_off()

    # ===== Panel a — architecture =====================================
    panel_label(ax, 0, 97, "a")
    label(ax, 4, 97, "Reader architecture: closed MapGIS binary $\\rightarrow$ open geospatial output",
          fs=8, weight="bold", ha="left", va="bottom")

    # bands (well separated):
    # CRS bypass      y = 83–93
    # main pipeline   y = 63–77
    # topology bypass y = 43–57
    # API bar         y = 34–40
    pipe_y, pipe_h = 63, 14

    # --- main pipeline (4 boxes) ---
    boxes = [
        (3, 14, "#e9e9e9", INK, "MapGIS 6.x/67", ".wt  .wl  .wp  (closed)"),
        (22, 16, ACCENT_SOFT, ACCENT, "Binary I/O + record model", "NumPy structured dtypes"),
        (43, 15, ACCENT_SOFT, ACCENT, "Shapely geometries", "Point / Line / Polygon"),
        (63, 17, AMBER_SOFT, AMBER, "Open output", "GeoDataFrame / shapefile / GeoJSON"),
    ]
    for (x, w, fc, ec, t1, t2) in boxes:
        block(ax, x, pipe_y, w, pipe_h, fc=fc, ec=ec)
        label(ax, x + w / 2, pipe_y + pipe_h - 4, t1, fs=6.6, weight="bold",
              color=(AMBER if ec == AMBER else INK))
        label(ax, x + w / 2, pipe_y + 4, t2, fs=5.6, color=SUB)
    # pipeline arrows
    arrow(ax, 17, pipe_y + pipe_h / 2, 22, pipe_y + pipe_h / 2)
    arrow(ax, 38, pipe_y + pipe_h / 2, 43, pipe_y + pipe_h / 2)
    arrow(ax, 58, pipe_y + pipe_h / 2, 63, pipe_y + pipe_h / 2)
    label(ax, 19.5, pipe_y + pipe_h + 1.5, "parse", fs=5.2, color=SUB, style="italic")
    label(ax, 50.5, pipe_y + pipe_h + 1.5, "build", fs=5.2, color=SUB, style="italic")

    # --- CRS bypass (above pipeline) ---
    crs_y, crs_h = 83, 10
    block(ax, 22, crs_y, 16, crs_h, fc=CRS_SOFT, ec=CRS_C)
    label(ax, 30, crs_y + crs_h - 3.5, "CRS inference", fs=6.4, weight="bold", color=CRS_C)
    label(ax, 30, crs_y + 2.5, "proj/ellip index $\\rightarrow$ PROJ", fs=5.4, color=SUB)
    arrow(ax, 30, crs_y, 30, pipe_y + pipe_h, color=CRS_C, lw=0.8, ls=(0, (3, 2)))
    label(ax, 31.4, (crs_y + pipe_y + pipe_h) / 2, "CRS", fs=5.0, color=CRS_C, ha="left", style="italic")

    # --- topology bypass (below pipeline) ---
    topo_y, topo_h = 43, 14
    block(ax, 43, topo_y, 15, topo_h, fc=TOPO_SOFT, ec=TOPO)
    label(ax, 50.5, topo_y + topo_h - 3.5, "Topology rebuild", fs=6.2, weight="bold", color=TOPO)
    label(ax, 50.5, topo_y + 3.5, "arcs $\\rightarrow$ rings", fs=5.6)
    label(ax, 50.5, topo_y + 1.2, "+ make_valid", fs=5.2, color=SUB, style="italic")
    arrow(ax, 50.5, topo_y + topo_h, 50.5, pipe_y, color=TOPO, lw=0.9, ls=(0, (3, 2)))
    label(ax, 51.8, (topo_y + topo_h + pipe_y) / 2, "polygons", fs=5.0, color=TOPO, ha="left", style="italic")

    # --- API / CLI bar ---
    block(ax, 3, 34, 77, 6, fc="#f4f4f4", ec=SUB, lw=0.6)
    label(ax, 41.5, 37, "Reader API  ·  CLI:   pymapgis  input.wp  output.shp",
          fs=6.6, weight="bold")

    # ===== Panel b — verification =====================================
    panel_label(ax, 0, 29, "b")
    label(ax, 4, 29, "Reproducible verification & regression",
          fs=8, weight="bold", ha="left", va="bottom")

    val_y, val_h = 11, 14
    block(ax, 3, val_y, 38, val_h, fc=VALID_SOFT, ec=VALID_C)
    label(ax, 22, val_y + val_h - 3.5, "Cross-validation harness", fs=6.4, weight="bold", color=VALID_C)
    label(ax, 22, val_y + val_h - 8, "36-layer 1:1 vs official MapGIS 6.7", fs=5.6)
    label(ax, 22, val_y + 3, "geometry 100%  ·  attributes 99.9995%", fs=5.4, color=SUB)
    label(ax, 22, val_y + 0.8, "400 MB  ·  IoU 99.73%", fs=5.4, color=SUB, style="italic")

    block(ax, 43, val_y, 38, val_h, fc=VALID_SOFT, ec=VALID_C)
    label(ax, 62, val_y + val_h - 3.5, "Regression baseline", fs=6.4, weight="bold", color=VALID_C)
    label(ax, 62, val_y + val_h - 8, "pymapgis_baseline.json", fs=5.6)
    label(ax, 62, val_y + 3, "count / bbox / CRS / types / validity", fs=5.4, color=SUB)
    label(ax, 62, val_y + 0.8, "pytest unit + integration suite", fs=5.4, color=SUB, style="italic")

    # verify arrows up into API bar
    arrow(ax, 22, val_y + val_h, 22, 34, color=VALID_C, lw=0.7, ls=(0, (2, 2)))
    arrow(ax, 62, val_y + val_h, 62, 34, color=VALID_C, lw=0.7, ls=(0, (2, 2)))
    label(ax, 82, (val_y + val_h + 34) / 2, "verify", fs=5.0, color=VALID_C, ha="left", style="italic")

    # footer
    label(ax, 3, 4.5,
          "Open source (Apache-2.0)  ·  Python $\\geq$ 3.9  ·  "
          "deps: geopandas · numpy · pandas · pyproj · shapely",
          fs=5.8, color=SUB, ha="left", va="bottom", style="italic")

    fig.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
    fig.savefig(png_path, dpi=300, bbox_inches="tight", pad_inches=0.03)
    fig.savefig(pdf_path, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


if __name__ == "__main__":
    figure2("figure2_architecture_nature.png", "figure2_architecture_nature.pdf")
    print("wrote figure2")
