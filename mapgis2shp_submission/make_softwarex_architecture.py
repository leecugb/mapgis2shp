"""Build the SoftwareX architecture figure for mapgis2shp 2.7.1."""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


OUT = Path(__file__).resolve().parent

INK = "#0b0b0b"
SECONDARY = "#52514e"
MUTED = "#898781"
SURFACE = "#fcfcfb"
NEUTRAL_FILL = "#f0efec"
NEUTRAL_EDGE = "#c3c2b7"
BLUE = "#2a78d6"
BLUE_FILL = "#eaf2fc"
ORANGE = "#eb6834"
ORANGE_FILL = "#fdf0ea"
AQUA = "#1baf7a"
AQUA_FILL = "#e9f8f2"


def box(ax, x, y, w, h, title, lines, edge, fill, title_size=11.2, body_size=9.0):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.025,rounding_size=0.06",
        linewidth=1.35,
        edgecolor=edge,
        facecolor=fill,
        zorder=2,
    )
    ax.add_patch(patch)
    ax.text(
        x + 0.16,
        y + h - 0.27,
        title,
        ha="left",
        va="top",
        fontsize=title_size,
        fontweight="bold",
        color=INK,
        zorder=3,
    )
    if lines:
        ax.text(
            x + 0.16,
            y + h - 0.69,
            "\n".join(lines),
            ha="left",
            va="top",
            fontsize=body_size,
            color=SECONDARY,
            linespacing=1.45,
            zorder=3,
        )
    return patch


def arrow(ax, start, end, color, rad=0.0, style="-", lw=1.45):
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=12,
        linewidth=lw,
        linestyle=style,
        color=color,
        connectionstyle=f"arc3,rad={rad}",
        shrinkA=1.5,
        shrinkB=1.5,
        zorder=1,
    )
    ax.add_patch(patch)
    return patch


def main():
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9.5,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.facecolor": SURFACE,
        }
    )
    fig = plt.figure(figsize=(14, 7.8), facecolor=SURFACE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 7.8)
    ax.axis("off")

    ax.text(0.25, 7.53, "a", fontsize=14, fontweight="bold", color=INK, va="top")
    ax.text(
        0.58,
        7.53,
        "Processing paths",
        fontsize=14,
        fontweight="bold",
        color=INK,
        va="top",
    )

    # Inputs: neutral because they are source material, not a data series.
    box(
        ax,
        0.4,
        4.65,
        2.65,
        1.75,
        "MapGIS 6.x/67 vectors",
        [".wt point · .wl line · .wp polygon", "Geometry · attributes · parameters", "CRS and topology sections"],
        NEUTRAL_EDGE,
        NEUTRAL_FILL,
    )
    box(
        ax,
        0.4,
        2.05,
        2.65,
        2.0,
        "Accompanying SLIB",
        ["Subgraph.lib · LINESTY.lib", "Fillgrph.lib · Colorlib.lib", "Pcolor.lib", "Original cartographic definitions"],
        NEUTRAL_EDGE,
        NEUTRAL_FILL,
    )

    # Vector interoperability path.
    box(
        ax,
        3.85,
        4.65,
        2.85,
        1.75,
        "Reader / Writer",
        ["Binary sections ↔ GeoDataFrame", "CRS inference · topology rebuild", "Native write-back · section reuse"],
        BLUE,
        BLUE_FILL,
    )
    box(
        ax,
        7.55,
        4.65,
        2.85,
        1.75,
        "Open vector interoperability",
        ["GeoPandas · OGR formats", "Shapefile · GeoJSON · GeoPackage", "Analysis · migration · archiving"],
        BLUE,
        BLUE_FILL,
    )

    # Original-library path.
    box(
        ax,
        3.85,
        2.05,
        2.85,
        2.0,
        "Five library parsers",
        ["Symbols · subline variants · fills", "Colorlib KCMY/YMCK channels", "Pcolor 32-byte nodes", "Explicit unresolved records"],
        ORANGE,
        ORANGE_FILL,
    )
    box(
        ax,
        7.55,
        2.05,
        2.85,
        2.0,
        "Original-library renderer",
        ["WP fills · WL chainage strokes", "WT symbols and annotations", "Polygon-attribute labels", "PNG · PDF · SVG"],
        ORANGE,
        ORANGE_FILL,
    )

    # Public access spans both paths.
    access = FancyBboxPatch(
        (11.25, 2.05),
        2.35,
        4.35,
        boxstyle="round,pad=0.025,rounding_size=0.06",
        linewidth=1.35,
        edgecolor=NEUTRAL_EDGE,
        facecolor="#f9f9f7",
        zorder=2,
    )
    ax.add_patch(access)
    ax.text(11.42, 6.12, "Public access", fontsize=11.2, fontweight="bold", color=INK, va="top")
    ax.text(
        11.42,
        5.62,
        "Python API\nReader · Writer\nGraphicLibraries\nGraphicRenderer\n\nCommand line\nconvert · lib inspect\n\nDistribution\nPyPI · GitHub\npymapgis.testing\nwheel + sdist fixtures",
        fontsize=9.0,
        color=SECONDARY,
        linespacing=1.38,
        va="top",
        ha="left",
    )

    arrow(ax, (3.05, 5.525), (3.85, 5.525), BLUE)
    arrow(ax, (6.70, 5.525), (7.55, 5.525), BLUE)
    arrow(ax, (10.40, 5.525), (11.25, 5.525), BLUE)
    arrow(ax, (3.05, 3.05), (3.85, 3.05), ORANGE)
    arrow(ax, (6.70, 3.05), (7.55, 3.05), ORANGE)
    arrow(ax, (10.40, 3.05), (11.25, 3.05), ORANGE)
    arrow(ax, (5.70, 4.65), (8.20, 4.05), BLUE, rad=0.18, style=(0, (3, 2)), lw=1.25)
    ax.text(
        6.72,
        4.38,
        "geometry + graphic parameters",
        fontsize=8.5,
        color=SECONDARY,
        ha="center",
        va="center",
        bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 0.8},
        zorder=4,
    )

    ax.text(0.25, 1.67, "b", fontsize=14, fontweight="bold", color=INK, va="top")
    ax.text(
        0.58,
        1.67,
        "Evidence, validation and reproduction",
        fontsize=14,
        fontweight="bold",
        color=INK,
        va="top",
    )

    evidence = [
        (0.4, 2.65, "Native colour anchors", ["14 exact matches", "25 unknown codes resolved"]),
        (3.85, 2.85, "Line coordinate fidelity", ["37 features · 782 vertices", "0 omitted · maximum deviation 0"]),
        (7.55, 2.85, "Real regression fixtures", ["12 JWD layers + 5 SLIB", "SHA-256 manifest"]),
        (11.25, 2.35, "Release verification", ["324-test local regression", "CI matrix · wheel + sdist inspection"]),
    ]
    for x, w, title, lines in evidence:
        box(ax, x, 0.25, w, 1.05, title, lines, AQUA, AQUA_FILL, title_size=10.2, body_size=8.6)

    # A quiet footer separates internal regression from vendor acceptance.
    ax.text(
        13.6,
        0.06,
        "Structural checks, internal regression and native MapGIS visual acceptance are reported separately.",
        fontsize=8.0,
        color=MUTED,
        ha="right",
        va="bottom",
    )

    for suffix in ("pdf", "png"):
        fig.savefig(OUT / f"softwarex_architecture.{suffix}", dpi=300, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)


if __name__ == "__main__":
    main()
