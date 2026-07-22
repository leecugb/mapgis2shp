#!/usr/bin/env python3
"""Figure 1 — byte-level layout of the MapGIS 6.x/67 vector formats.

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
INK = "#1a1a1a"          # near-black ink
SUB = "#6b6b6b"           # secondary text / offsets
ACCENT = "#2c6fbb"        # primary accent (structure / coordinates)
ACCENT_SOFT = "#dce8f4"   # light fill for coordinate sections
AMBER = "#c98a2b"         # attribute sections (warm, colour-blind safe)
AMBER_SOFT = "#f3e6cf"
GRAY = "#9a9a9a"          # common header
GRAY_SOFT = "#e6e6e6"
TOPO = "#5aa070"          # topology (green-ish accent)
TOPO_SOFT = "#dcefe0"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "pdf.fonttype": 42,        # editable TrueType in PDF
    "ps.fonttype": 42,
    "svg.fonttype": "none",    # editable text in SVG
    "font.size": 7,
    "axes.linewidth": 0.6,
    "text.color": INK,
    "axes.edgecolor": INK,
})


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------
def block(ax, x, y, w, h, fc, ec=INK, lw=0.8):
    """Square-cornered technical block."""
    ax.add_patch(Rectangle((x, y), w, h, facecolor=fc, edgecolor=ec,
                           linewidth=lw, zorder=2))


def label(ax, x, y, text, fs=6.5, weight="normal", color=INK, ha="center",
          va="center", style="normal"):
    ax.text(x, y, text, fontsize=fs, fontweight=weight, color=color, ha=ha,
            va=va, style=style, zorder=3)


def offset_tag(ax, x, y, text, fs=5.6, color=SUB):
    """Byte-offset annotation in secondary grey."""
    ax.text(x, y, text, fontsize=fs, color=color, ha="center", va="center",
            family="DejaVu Sans Mono", zorder=3)


def brace_arrow(ax, x0, y0, x1, y1):
    """Thin connector arrow."""
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>",
                                 mutation_scale=7, lw=0.7, color=SUB,
                                 zorder=1))


def panel_label(ax, x, y, letter):
    ax.text(x, y, letter, fontsize=9, fontweight="bold", color=INK,
            ha="left", va="bottom")


# ---------------------------------------------------------------------------
# Figure 1
# ---------------------------------------------------------------------------
def figure1(png_path: str, pdf_path: str) -> None:
    # 183 mm wide double-column; height tuned for two panels
    fig, (ax_h, ax_f) = plt.subplots(
        2, 1, figsize=(7.2, 4.7),
        gridspec_kw={"height_ratios": [1.0, 1.7], "hspace": 0.14},
    )
    for ax in (ax_h, ax_f):
        ax.set_axis_off()

    # =====================================================================
    # Panel a — common file header
    # =====================================================================
    ax_h.set_xlim(0, 100)
    ax_h.set_ylim(0, 100)
    panel_label(ax_h, 0, 96, "a")
    ax_h.text(4, 96, "Common file header  (shared by .wt / .wl / .wp)",
              fontsize=7.5, fontweight="bold", color=INK, ha="left", va="bottom")

    # header strip baseline
    y0 = 38
    h = 30
    # blocks: magic | file id | data_start | index area | CRS
    # x-positions (schematic, not to scale)
    bx = [4, 20, 33, 46, 70]
    bw = [16, 13, 13, 24, 26]
    cols = [GRAY_SOFT, GRAY_SOFT, GRAY_SOFT, GRAY_SOFT, ACCENT_SOFT]
    for x, w, c in zip(bx, bw, cols):
        block(ax_h, x, y0, w, h, fc=c)

    # block titles + offsets
    label(ax_h, bx[0] + bw[0] / 2, y0 + h - 7, "magic", fs=6.6, weight="bold")
    label(ax_h, bx[0] + bw[0] / 2, y0 + h - 15, "WMAP·D2x", fs=5.8)
    label(ax_h, bx[0] + bw[0] / 2, y0 + h - 22, "8 B", fs=5.6, color=SUB)
    offset_tag(ax_h, bx[0] + bw[0] / 2, y0 - 6, "0–7")

    label(ax_h, bx[1] + bw[1] / 2, y0 + h - 7, "file id", fs=6.6, weight="bold")
    label(ax_h, bx[1] + bw[1] / 2, y0 + h - 15, "int32", fs=5.8)
    label(ax_h, bx[1] + bw[1] / 2, y0 + h - 22, "4 B", fs=5.6, color=SUB)
    offset_tag(ax_h, bx[1] + bw[1] / 2, y0 - 6, "8–11")

    label(ax_h, bx[2] + bw[2] / 2, y0 + h - 7, "data_start", fs=6.6, weight="bold")
    label(ax_h, bx[2] + bw[2] / 2, y0 + h - 15, "int32", fs=5.8)
    label(ax_h, bx[2] + bw[2] / 2, y0 + h - 22, "4 B", fs=5.6, color=SUB)
    offset_tag(ax_h, bx[2] + bw[2] / 2, y0 - 6, "12–15")

    label(ax_h, bx[3] + bw[3] / 2, y0 + h - 7, "index area", fs=6.6, weight="bold")
    label(ax_h, bx[3] + bw[3] / 2, y0 + h - 15, "10 × 10 B", fs=5.8)
    label(ax_h, bx[3] + bw[3] / 2, y0 + h - 22, "(start, volume)", fs=5.4, color=SUB)
    offset_tag(ax_h, bx[3] + bw[3] / 2, y0 - 6, "16–115")

    label(ax_h, bx[4] + bw[4] / 2, y0 + h - 6, "CRS bytes", fs=6.6, weight="bold", color=ACCENT)
    label(ax_h, bx[4] + bw[4] / 2, y0 + h - 13, "proj@109  ellip@110", fs=5.4)
    label(ax_h, bx[4] + bw[4] / 2, y0 + h - 19, "scale@143", fs=5.4)
    label(ax_h, bx[4] + bw[4] / 2, y0 + h - 25, "cent. meridian@151", fs=5.2)
    offset_tag(ax_h, bx[4] + bw[4] / 2, y0 - 6, "DDDMMSS.sss")

    # tick line under offsets
    ax_h.plot([4, 96], [y0 - 0.5, y0 - 0.5], color=INK, lw=0.5, zorder=1)

    # legend chips (header)
    chip_y = 14
    block(ax_h, 4, chip_y, 3.2, 4.5, fc=GRAY_SOFT); label(ax_h, 9, chip_y + 2.2, "header / index", fs=5.8, ha="left")
    block(ax_h, 30, chip_y, 3.2, 4.5, fc=ACCENT_SOFT); label(ax_h, 35, chip_y + 2.2, "coordinates / CRS", fs=5.8, ha="left")
    block(ax_h, 58, chip_y, 3.2, 4.5, fc=AMBER_SOFT, ec=AMBER); label(ax_h, 63, chip_y + 2.2, "attributes (GBK)", fs=5.8, ha="left")
    block(ax_h, 80, chip_y, 3.2, 4.5, fc=TOPO_SOFT, ec=TOPO); label(ax_h, 85, chip_y + 2.2, "topology", fs=5.8, ha="left")

    # =====================================================================
    # Panel b — per-format sections
    # =====================================================================
    ax_f.set_xlim(0, 100)
    ax_f.set_ylim(0, 100)
    panel_label(ax_f, 0, 98, "b")
    ax_f.text(4, 98, "Type-specific record sections after the header",
              fontsize=7.5, fontweight="bold", color=INK, ha="left", va="bottom")

    rows = [
        # (label, magic, y_top, segments)
        # segments: (width, fill, edge, title_lines, size_tag, offset_tag)
        (".wt  point", "D22", 84, [
            (12, GRAY_SOFT, INK, ["header"], "shared", ""),
            (40, ACCENT_SOFT, ACCENT, ["coordinate section", "93 B / record", "X double @7–14", "Y double @15–22"], "first record empty", ""),
            (36, AMBER_SOFT, AMBER, ["attribute section (head_3)", "GBK strings", "int / float / double / date"], "", ""),
        ]),
        (".wl  line", "D21", 56, [
            (12, GRAY_SOFT, INK, ["header"], "shared", ""),
            (26, ACCENT_SOFT, ACCENT, ["line index", "57 B / record", "point_count @10–13", "point_offset @14–17"], "", ""),
            (22, "#eef4fa", ACCENT, ["coordinate section", "16 B / XY", "2 × double"], "", ""),
            (28, AMBER_SOFT, AMBER, ["attribute section", "(head_3)"], "", ""),
        ]),
        (".wp  polygon", "D23", 28, [
            (12, GRAY_SOFT, INK, ["header"], "shared", ""),
            (20, TOPO_SOFT, TOPO, ["arc index", "57 B / record"], "", ""),
            (20, "#eef4fa", ACCENT, ["coordinate", "section", "16 B / XY"], "", ""),
            (18, TOPO_SOFT, TOPO, ["topology", "24 B / record", "left @8–11", "right @12–15"], "", ""),
            (22, AMBER_SOFT, AMBER, ["attribute", "section", "(head_10)"], "", ""),
        ]),
    ]

    left_margin = 4
    total_w = 92
    row_h = 20

    for label_txt, magic, y_top, segs in rows:
        # row label
        ax_f.text(left_margin, y_top + 2, label_txt, fontsize=7.2, fontweight="bold",
                  color=ACCENT, ha="left", va="bottom")
        ax_f.text(left_margin + 17, y_top + 2, f"magic {magic}", fontsize=5.8,
                  color=SUB, ha="left", va="bottom", style="italic")

        # scale segment widths to total_w
        scale = total_w / sum(s[0] for s in segs)
        x = left_margin
        y = y_top - row_h
        for w, fc, ec, lines, size_tag, _ in segs:
            bw = w * scale
            block(ax_f, x, y, bw, row_h, fc=fc, ec=ec)
            # multi-line title centered
            n = len(lines)
            for i, ln in enumerate(lines):
                ly = y + row_h - 4.5 - i * 4.0
                fs = 6.0 if i == 0 else 5.4
                wt = "bold" if i == 0 else "normal"
                col = INK if i == 0 else SUB
                label(ax_f, x + bw / 2, ly, ln, fs=fs, weight=wt, color=col)
            if size_tag:
                label(ax_f, x + bw / 2, y + 1.8, size_tag, fs=5.0, color=SUB, style="italic")
            x += bw

    # footer note
    ax_f.text(left_margin, 2.5,
              "All integers little-endian; strings encoded GBK.  "
              "Magic byte codes: D22 = point (.wt), D21 = line (.wl), D23 = polygon (.wp).  "
              "Schematic; section widths not to scale.",
              fontsize=5.8, color=SUB, ha="left", va="bottom", style="italic")

    fig.subplots_adjust(left=0.02, right=0.98, top=0.97, bottom=0.03)
    fig.savefig(png_path, dpi=300, bbox_inches="tight", pad_inches=0.03)
    fig.savefig(pdf_path, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


if __name__ == "__main__":
    png = "figure1_format_layout_nature.png"
    pdf = "figure1_format_layout_nature.pdf"
    figure1(png, pdf)
    print("wrote", png, pdf)
