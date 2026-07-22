#!/usr/bin/env python3
"""Figure 2 — mapgis2shp reader architecture and data flow.

Nature/journal-style technical schematic. Double-column width (~183 mm).
Renders PNG (300 dpi) and PDF (editable TrueType text).
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch

# ---------------------------------------------------------------------------
# Journal style
# ---------------------------------------------------------------------------
INK = "#1a1a1a"
SUB = "#6b6b6b"
ACCENT = "#2c6fbb"        # primary accent (main pipeline)
ACCENT_SOFT = "#dce8f4"
AMBER = "#c98a2b"         # output / products
AMBER_SOFT = "#f3e6cf"
CRS_C = "#7d5ba6"         # CRS inference (muted violet, colour-blind safe)
CRS_SOFT = "#e7ddf0"
TOPO = "#5aa070"          # topology (green)
TOPO_SOFT = "#dcefe0"
VALID_C = "#4a7c8c"       # validation (teal-grey)
VALID_SOFT = "#dfeaec"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
    "font.size": 7,
    "axes.linewidth": 0.6,
    "text.color": INK,
    "axes.edgecolor": INK,
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def block(ax, x, y, w, h, fc, ec=INK, lw=0.8, radius=0.0):
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
    ax.text(x, y, letter, fontsize=9, fontweight="bold", color=INK,
            ha="left", va="bottom")


# ---------------------------------------------------------------------------
# Figure 2
# ---------------------------------------------------------------------------
def figure2(png_path: str, pdf_path: str) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_axis_off()

    panel_label(ax, 0, 97, "a")
    ax.text(4, 97, "Reader architecture: closed MapGIS binary → open geospatial output",
            fontsize=7.8, fontweight="bold", color=INK, ha="left", va="bottom")

    # =====================================================================
    # Main pipeline (horizontal, centre band y ~ 62–78)
    # =====================================================================
    pipe_y = 60
    pipe_h = 16

    # 1. Input
    block(ax, 3, pipe_y, 15, pipe_h, fc="#e9e9e9", ec=INK)
    label(ax, 10.5, pipe_y + pipe_h - 4, "MapGIS 6.x/67", fs=6.6, weight="bold")
    label(ax, 10.5, pipe_y + pipe_h - 9, ".wt  .wl  .wp", fs=6.4, color=ACCENT)
    label(ax, 10.5, pipe_y + 3, "closed binary", fs=5.6, color=SUB, style="italic")

    # 2. Binary I/O + record model
    block(ax, 23, pipe_y, 17, pipe_h, fc=ACCENT_SOFT, ec=ACCENT)
    label(ax, 31.5, pipe_y + pipe_h - 4, "Binary I/O +", fs=6.4, weight="bold")
    label(ax, 31.5, pipe_y + pipe_h - 8.5, "record model", fs=6.4, weight="bold")
    label(ax, 31.5, pipe_y + pipe_h - 13, "NumPy structured dtypes", fs=5.4, color=SUB)
    label(ax, 31.5, pipe_y + 3, "little-endian · GBK", fs=5.2, color=SUB, style="italic")

    # 3. Shapely geometries
    block(ax, 44, pipe_y, 16, pipe_h, fc=ACCENT_SOFT, ec=ACCENT)
    label(ax, 52, pipe_y + pipe_h - 4, "Shapely", fs=6.6, weight="bold")
    label(ax, 52, pipe_y + pipe_h - 9, "geometries", fs=6.4)
    label(ax, 52, pipe_y + pipe_h - 13.5, "Point / Line / Polygon", fs=5.4, color=SUB)

    # 4. Output
    block(ax, 64, pipe_y, 17, pipe_h, fc=AMBER_SOFT, ec=AMBER)
    label(ax, 72.5, pipe_y + pipe_h - 4, "Open output", fs=6.6, weight="bold", color=AMBER)
    label(ax, 72.5, pipe_y + pipe_h - 9, "GeoDataFrame", fs=6.0)
    label(ax, 72.5, pipe_y + pipe_h - 13.5, "shapefile / GeoJSON", fs=5.6, color=SUB)

    # pipeline arrows
    arrow(ax, 18, pipe_y + pipe_h / 2, 23, pipe_y + pipe_h / 2)
    arrow(ax, 40, pipe_y + pipe_h / 2, 44, pipe_y + pipe_h / 2)
    arrow(ax, 60, pipe_y + pipe_h / 2, 64, pipe_y + pipe_h / 2)

    # forward-consumes label on the long middle arrow
    label(ax, 42, pipe_y + pipe_h + 1.5, "parse", fs=5.2, color=SUB, style="italic")
    label(ax, 62, pipe_y + pipe_h + 1.5, "build", fs=5.2, color=SUB, style="italic")

    # =====================================================================
    # Bypass: CRS inference (above record model)
    # =====================================================================
    crs_y = 84
    crs_h = 12
    block(ax, 23, crs_y, 17, crs_h, fc=CRS_SOFT, ec=CRS_C)
    label(ax, 31.5, crs_y + crs_h - 3.5, "CRS inference", fs=6.4, weight="bold", color=CRS_C)
    label(ax, 31.5, crs_y + crs_h - 7.5, "proj / ellip index", fs=5.6)
    label(ax, 31.5, crs_y + crs_h - 11, "→ PROJ string", fs=5.6, color=SUB)
    # dashed feed-down into record model / output CRS
    arrow(ax, 31.5, crs_y, 31.5, pipe_y + pipe_h, color=CRS_C, lw=0.8, ls=(0, (3, 2)))
    label(ax, 33.2, (crs_y + pipe_y + pipe_h) / 2, "CRS", fs=5.0, color=CRS_C, ha="left", style="italic")
    # CRS also informs the output projection
    arrow(ax, 40, crs_y + crs_h / 2, 64, crs_y + crs_h / 2, color=CRS_C, lw=0.8, ls=(0, (3, 2)))
    arrow(ax, 64, crs_y + crs_h / 2, 72.5, pipe_y + pipe_h, color=CRS_C, lw=0.8, ls=(0, (3, 2)))

    # =====================================================================
    # Bypass: polygon topology reconstruction (below geometry stage)
    # =====================================================================
    topo_y = 40
    topo_h = 14
    block(ax, 44, topo_y, 16, topo_h, fc=TOPO_SOFT, ec=TOPO)
    label(ax, 52, topo_y + topo_h - 3.5, "Topology rebuild", fs=6.2, weight="bold", color=TOPO)
    label(ax, 52, topo_y + topo_h - 7.5, "arcs → rings →", fs=5.6)
    label(ax, 52, topo_y + topo_h - 11, "shells / holes", fs=5.6)
    label(ax, 52, topo_y + 1.8, "+ make_valid", fs=5.2, color=SUB, style="italic")
    # feed-up into Shapely geometry stage (polygons)
    arrow(ax, 52, topo_y + topo_h, 52, pipe_y, color=TOPO, lw=0.9, ls=(0, (3, 2)))
    label(ax, 53.4, (topo_y + topo_h + pipe_y) / 2, "polygons", fs=5.0, color=TOPO, ha="left", style="italic")

    # =====================================================================
    # Reader API + CLI bar (under main pipeline)
    # =====================================================================
    api_y = 38
    block(ax, 3, 30, 78, 6.5, fc="#f4f4f4", ec=SUB, lw=0.6)
    label(ax, 42, 33.2, "Reader API  ·  CLI:   pymapgis  input.wp  output.shp",
          fs=6.6, weight="bold")
    label(ax, 42, 30 + 1.6, "programmatic + command-line access to the pipeline above",
          fs=5.2, color=SUB, style="italic")

    # =====================================================================
    # Validation band (bottom)
    # =====================================================================
    panel_label(ax, 0, 27.5, "b")
    ax.text(4, 27.5, "Reproducible verification & regression",
            fontsize=7.4, fontweight="bold", color=INK, ha="left", va="bottom")

    val_y = 12
    val_h = 13
    # validation harness
    block(ax, 3, val_y, 38, val_h, fc=VALID_SOFT, ec=VALID_C)
    label(ax, 22, val_y + val_h - 3.5, "Cross-validation harness", fs=6.4, weight="bold", color=VALID_C)
    label(ax, 22, val_y + val_h - 7.5, "36-layer 1:1 check vs official MapGIS", fs=5.6)
    label(ax, 22, val_y + val_h - 11, "geometry 100%  ·  attributes 99.9995%", fs=5.6, color=SUB)
    label(ax, 22, val_y + 1.8, "400 MB coverage equivalence  ·  IoU 99.73%", fs=5.4, color=SUB, style="italic")

    # regression baseline
    block(ax, 43, val_y, 38, val_h, fc=VALID_SOFT, ec=VALID_C)
    label(ax, 62, val_y + val_h - 3.5, "Regression baseline", fs=6.4, weight="bold", color=VALID_C)
    label(ax, 62, val_y + val_h - 7.5, "pymapgis_baseline.json", fs=5.6)
    label(ax, 62, val_y + val_h - 11, "count / bbox / CRS / types / validity", fs=5.4, color=SUB)
    label(ax, 62, val_y + 1.8, "pytest unit + integration suite", fs=5.4, color=SUB, style="italic")

    # verification feeds up (dashed) into pipeline
    arrow(ax, 22, val_y + val_h, 22, 30, color=VALID_C, lw=0.7, ls=(0, (2, 2)))
    arrow(ax, 62, val_y + val_h, 62, 30, color=VALID_C, lw=0.7, ls=(0, (2, 2)))
    label(ax, 81, (val_y + val_h + 30) / 2, "verify", fs=5.0, color=VALID_C, ha="left", style="italic")

    # =====================================================================
    # Footer meta
    # =====================================================================
    ax.text(3, 5.5,
            "Open source (Apache-2.0)  ·  Python ≥ 3.9  ·  "
            "deps: geopandas · numpy · pandas · pyproj · shapely",
            fontsize=5.8, color=SUB, ha="left", va="bottom", style="italic")

    fig.subplots_adjust(left=0.02, right=0.98, top=0.97, bottom=0.02)
    fig.savefig(png_path, dpi=300, bbox_inches="tight", pad_inches=0.03)
    fig.savefig(pdf_path, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


if __name__ == "__main__":
    png = "figure2_architecture_nature.png"
    pdf = "figure2_architecture_nature.pdf"
    figure2(png, pdf)
    print("wrote", png, pdf)
