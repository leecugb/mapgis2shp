#!/usr/bin/env python3
"""Generate publication figures for the mapgis2shp paper.

Fig 1: byte-layout diagram of the .wt/.wl/.wp binary formats.
Fig 2: reader architecture / data-flow diagram.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# Restrained, publication-friendly palette.
INK = "#1a1a1a"
ACCENT = "#2c6fbb"
SOFT = "#e8eef6"
WARM = "#f4ece0"
LINE_C = "#9bbcd9"
POLY_C = "#c9a96e"
HEADER_C = "#d9d9d9"
CRS_C = "#f0d9e8"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.edgecolor": INK,
    "text.color": INK,
})


def _box(ax, x, y, w, h, text, fc=SOFT, ec=INK, fs=8, lw=1.0, weight="normal"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fc, ec=ec, lw=lw))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, fontweight=weight, wrap=True)


def _arrow(ax, x0, y0, x1, y1, text=""):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1),
                                 arrowstyle="-|>", mutation_scale=11,
                                 lw=1.2, color=INK))
    if text:
        ax.text((x0 + x1) / 2, (y0 + y1) / 2 + 0.12, text, ha="center", va="bottom",
                fontsize=7, style="italic", color=INK)


# ---------------------------------------------------------------------------
# Figure 1 — byte layout
# ---------------------------------------------------------------------------
def figure1(path: str) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 5.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    ax.set_title("Figure 1.  Byte-level layout of the MapGIS 6.x/67 vector formats",
                 fontsize=11, fontweight="bold", loc="left", pad=8)

    # --- Common header band ----------------------------------------------
    ax.text(2, 95, "Common file header", fontsize=9, fontweight="bold")
    _box(ax, 2, 88, 14, 5, "magic\nWMAP◇D2x\n(0–7)", fc=HEADER_C, fs=7)
    _box(ax, 16, 88, 10, 5, "file id\nint32\n(8–11)", fc=HEADER_C, fs=7)
    _box(ax, 26, 88, 12, 5, "data_start\nint32\n(12–15)", fc=HEADER_C, fs=7)
    _box(ax, 38, 88, 30, 5, "index area: 10 entries × 10 B  (start, volume)",
         fc=HEADER_C, fs=7)
    _box(ax, 68, 88, 30, 5, "CRS bytes: proj@109  ellip@110  scale@143\n"
                            "central meridian@151 (DDDMMSS.sss)", fc=CRS_C, fs=6.5)

    # --- Point .wt -------------------------------------------------------
    y = 70
    ax.text(2, y + 11, ".wt  (point)", fontsize=9, fontweight="bold", color=ACCENT)
    _box(ax, 2, y + 4, 45, 5, "header", fc=HEADER_C, fs=7)
    _box(ax, 47, y + 4, 51, 5, "coordinate section  —  93 B per point record\n"
        "X: double @7–14    Y: double @15–22    (first record empty)",
        fc=SOFT, fs=7)
    _box(ax, 2, y - 2, 96, 5, "attribute section  (head_3)  —  GBK strings, int/float/double/date fields",
         fc=WARM, fs=7)

    # --- Line .wl --------------------------------------------------------
    y = 46
    ax.text(2, y + 11, ".wl  (line)", fontsize=9, fontweight="bold", color=ACCENT)
    _box(ax, 2, y + 4, 45, 5, "header", fc=HEADER_C, fs=7)
    _box(ax, 47, y + 4, 25, 5, "line index\n57 B per record\npoint_count@10–13\npoint_offset@14–17",
         fc=LINE_C, fs=6.5)
    _box(ax, 72, y + 4, 26, 5, "coordinate section\n16 B per XY pair (2× double)",
         fc=SOFT, fs=6.5)
    _box(ax, 2, y - 2, 96, 5, "attribute section  (head_3)", fc=WARM, fs=7)

    # --- Polygon .wp -----------------------------------------------------
    y = 22
    ax.text(2, y + 11, ".wp  (polygon)", fontsize=9, fontweight="bold", color=ACCENT)
    _box(ax, 2, y + 4, 45, 5, "header", fc=HEADER_C, fs=7)
    _box(ax, 47, y + 4, 18, 5, "arc index\n57 B/record", fc=POLY_C, fs=6.5)
    _box(ax, 65, y + 4, 18, 5, "coordinate\nsection 16 B/XY", fc=SOFT, fs=6.5)
    _box(ax, 83, y + 4, 15, 5, "topology\n24 B/record\nleft@8–11\nright@12–15",
         fc=POLY_C, fs=6.2)
    _box(ax, 2, y - 2, 96, 5, "attribute section  (head_10)", fc=WARM, fs=7)

    ax.text(2, 6, "All integers little-endian; strings GBK.  Magic bytes: "
                  "D22 = point, D21 = line, D23 = polygon.",
            fontsize=7, style="italic", color="#555555")
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 2 — architecture / data flow
# ---------------------------------------------------------------------------
def figure2(path: str) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    ax.set_title("Figure 2.  mapgis2shp reader architecture and data flow",
                 fontsize=11, fontweight="bold", loc="left", pad=8)

    # Input
    _box(ax, 2, 60, 16, 14, "MapGIS 6.x/67\n.wt / .wl / .wp\n(closed binary)",
         fc=HEADER_C, fs=8, weight="bold")
    _arrow(ax, 18, 67, 26, 67)

    # Binary I/O + record model
    _box(ax, 26, 60, 20, 14, "Binary I/O\n+ record model\n(NumPy structured\ndtypes)",
         fc=SOFT, fs=7.5)
    _arrow(ax, 46, 67, 54, 67)

    # CRS inference (above)
    _box(ax, 26, 80, 20, 10, "CRS inference\n(proj/ellip index →\nPROJ string)",
         fc=CRS_C, fs=7.5)
    _arrow(ax, 36, 80, 36, 74)

    # Topology reconstruction (below)
    _box(ax, 26, 44, 20, 12, "Polygon topology\narc–node → rings →\nshells/holes + make_valid",
         fc=POLY_C, fs=7.5)
    _arrow(ax, 36, 56, 36, 60)

    # Geometry objects
    _box(ax, 54, 60, 18, 14, "Shapely\ngeometries\n(Point / Line /\nPolygon)",
         fc=SOFT, fs=7.5)
    _arrow(ax, 72, 67, 80, 67)

    # Output
    _box(ax, 80, 60, 18, 14, "GeoDataFrame\n/ shapefile\n/ GeoJSON",
         fc=WARM, fs=8, weight="bold")

    # CLI / API
    _box(ax, 54, 44, 44, 10, "Reader API  •  CLI:  pymapgis input.wp output.shp",
         fc="#eef0f2", fs=7.5)

    # Validation harness (bottom)
    _box(ax, 2, 20, 44, 16, "Reproducible validation harness\n"
        "• 36-layer 1:1 cross-check vs official MapGIS\n"
        "  (geometry 100%, attributes 99.9995%)\n"
        "• 400 MB coverage-equivalence test (IoU 99.73%)",
         fc="#eaf3ea", fs=7.3)
    _arrow(ax, 36, 36, 36, 44)

    # Baseline
    _box(ax, 54, 20, 44, 16, "Regression baseline\n"
        "pymapgis_baseline.json  (count / bbox / CRS /\n"
        "geom_types / validity  for 36 layers)\n"
        "pytest unit + integration suite",
         fc="#eaf3ea", fs=7.3)
    _arrow(ax, 76, 36, 76, 44)

    ax.text(2, 6, "Open-source (Apache-2.0), Python ≥ 3.9, deps: geopandas / numpy / pandas / pyproj / shapely.",
            fontsize=7, style="italic", color="#555555")
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    out = "figure1_format_layout.png"
    figure1(out)
    print("wrote", out)
    out2 = "figure2_architecture.png"
    figure2(out2)
    print("wrote", out2)
