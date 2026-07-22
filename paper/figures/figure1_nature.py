#!/usr/bin/env python3
"""Figure 1 — byte-level layout of the MapGIS 6.x/67 vector formats.

Cleaner, overlap-free layout: one short label per block, details in caption.
Renders PNG (300 dpi) and PDF (editable TrueType text).
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

# Journal style
INK = "#1a1a1a"
SUB = "#6b6b6b"
ACCENT = "#2c6fbb"
ACCENT_SOFT = "#dce8f4"
AMBER = "#c98a2b"
AMBER_SOFT = "#f3e6cf"
GRAY_SOFT = "#e6e6e6"
TOPO = "#5aa070"
TOPO_SOFT = "#dcefe0"
COORD_SOFT = "#eef4fa"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
    "font.size": 7, "axes.linewidth": 0.6, "text.color": INK,
})


def block(ax, x, y, w, h, fc, ec=INK, lw=0.8):
    ax.add_patch(Rectangle((x, y), w, h, facecolor=fc, edgecolor=ec,
                           linewidth=lw, zorder=2))


def txt(ax, x, y, s, fs=6.5, weight="normal", color=INK, ha="center",
        va="center", style="normal"):
    ax.text(x, y, s, fontsize=fs, fontweight=weight, color=color, ha=ha,
            va=va, style=style, zorder=3)


def panel_label(ax, x, y, letter):
    ax.text(x, y, letter, fontsize=10, fontweight="bold", color=INK,
            ha="left", va="bottom")


def figure1(png_path: str, pdf_path: str) -> None:
    fig, (ax_h, ax_f) = plt.subplots(
        2, 1, figsize=(7.4, 4.6),
        gridspec_kw={"height_ratios": [1.0, 1.9], "hspace": 0.18},
    )
    for ax in (ax_h, ax_f):
        ax.set_axis_off()

    # ===== Panel a — common header =====================================
    ax_h.set_xlim(0, 100); ax_h.set_ylim(0, 100)
    panel_label(ax_h, 0, 95, "a")
    txt(ax_h, 4, 95, "Common file header  (shared by .wt / .wl / .wp)",
        fs=8, weight="bold", ha="left", va="bottom")

    y0, h = 30, 34
    # 5 boxes spanning x=4..96 (width 92), generous widths
    items = [
        ("magic", "WMAP·D2x", "0–7", GRAY_SOFT),
        ("file id", "int32", "8–11", GRAY_SOFT),
        ("data_start", "int32", "12–15", GRAY_SOFT),
        ("index area", "10 × 10 B", "16–115", GRAY_SOFT),
        ("CRS bytes", "109 / 110 / 143 / 151", "header", ACCENT_SOFT),
    ]
    n = len(items)
    gap = 1.2
    bw = (92 - gap * (n - 1)) / n
    x = 4
    for (title, mid, off, fc) in items:
        block(ax_h, x, y0, bw, h, fc=fc)
        txt(ax_h, x + bw / 2, y0 + h - 8, title, fs=7, weight="bold")
        txt(ax_h, x + bw / 2, y0 + h / 2 - 1, mid, fs=6.0, color=SUB)
        txt(ax_h, x + bw / 2, y0 + 5, off, fs=5.8, color=SUB,
            style="italic")
        x += bw + gap
    ax_h.plot([4, 96], [y0 - 1.2, y0 - 1.2], color=INK, lw=0.5, zorder=1)

    # legend
    chip_y = 10
    chips = [(GRAY_SOFT, INK, "header / index"),
             (ACCENT_SOFT, ACCENT, "coordinates / CRS"),
             (AMBER_SOFT, AMBER, "attributes (GBK)"),
             (TOPO_SOFT, TOPO, "topology")]
    cx = 4
    for fc, ec, name in chips:
        block(ax_h, cx, chip_y, 3.2, 4.5, fc=fc, ec=ec)
        txt(ax_h, cx + 5, chip_y + 2.2, name, fs=6.0, ha="left")
        cx += 5 + len(name) * 1.7 + 4

    # ===== Panel b — per-format sections ===============================
    ax_f.set_xlim(0, 100); ax_f.set_ylim(0, 100)
    panel_label(ax_f, 0, 98, "b")
    txt(ax_f, 4, 98, "Type-specific record sections after the header",
        fs=8, weight="bold", ha="left", va="bottom")

    # Each row: list of (relative_width, fill, edge, [lines])
    rows = [
        (".wt  point  (D22)", 82, [
            (10, GRAY_SOFT, INK, ["header"]),
            (46, ACCENT_SOFT, ACCENT, ["coordinate section", "93 B / record"]),
            (36, AMBER_SOFT, AMBER, ["attribute section", "(head_3)"]),
        ]),
        (".wl  line  (D21)", 58, [
            (10, GRAY_SOFT, INK, ["header"]),
            (28, ACCENT_SOFT, ACCENT, ["line index", "57 B / record"]),
            (24, COORD_SOFT, ACCENT, ["coordinate", "section", "16 B / XY"]),
            (30, AMBER_SOFT, AMBER, ["attribute", "section", "(head_3)"]),
        ]),
        (".wp  polygon  (D23)", 34, [
            (10, GRAY_SOFT, INK, ["header"]),
            (20, TOPO_SOFT, TOPO, ["arc index", "57 B / record"]),
            (20, COORD_SOFT, ACCENT, ["coordinate", "section", "16 B / XY"]),
            (20, TOPO_SOFT, TOPO, ["topology", "24 B / record"]),
            (22, AMBER_SOFT, AMBER, ["attribute", "section", "(head_10)"]),
        ]),
    ]

    left_margin = 4
    total_w = 92
    row_h = 18
    for label_txt, y_top, segs in rows:
        # row label, well clear of the blocks (blocks start at x=4, label above)
        txt(ax_f, left_margin, y_top + 2.5, label_txt, fs=7.5, weight="bold",
            color=ACCENT, ha="left", va="bottom")
        scale = total_w / sum(s[0] for s in segs)
        x = left_margin
        y = y_top - row_h
        for (w, fc, ec, lines) in segs:
            bw = w * scale
            block(ax_f, x, y, bw, row_h, fc=fc, ec=ec)
            nlines = len(lines)
            # vertical centering of the lines stack
            top = y + row_h - 4.5
            step = 4.2
            start = top - (nlines - 1) * step / 2 if nlines > 1 else y + row_h / 2
            # actually place from top
            for i, ln in enumerate(lines):
                ly = top - i * step
                fs = 6.2 if i == 0 else 5.6
                wt = "bold" if i == 0 else "normal"
                col = INK if i == 0 else SUB
                txt(ax_f, x + bw / 2, ly, ln, fs=fs, weight=wt, color=col)
            x += bw

    txt(ax_f, left_margin, 2.5,
        "All integers little-endian; strings GBK.  Section widths schematic, not to scale.  "
        "Per-field offsets: point X/Y double @7–14/15–22; line point_count @10–13, "
        "point_offset @14–17; polygon topology left/right @8–11/12–15.  CRS central "
        "meridian @151 as DDDMMSS.sss.",
        fs=5.6, color=SUB, ha="left", va="bottom", style="italic")

    fig.subplots_adjust(left=0.02, right=0.98, top=0.97, bottom=0.03)
    fig.savefig(png_path, dpi=300, bbox_inches="tight", pad_inches=0.03)
    fig.savefig(pdf_path, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


if __name__ == "__main__":
    figure1("figure1_format_layout_nature.png", "figure1_format_layout_nature.pdf")
    print("wrote figure1")
