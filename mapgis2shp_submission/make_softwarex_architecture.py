"""Build the SoftwareX architecture figure for mapgis2shp 2.7.1."""

import re
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

mpl.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'DejaVu Sans'],
    'svg.fonttype': 'none',
    'pdf.fonttype': 42,
})

OUT = Path(__file__).resolve().parent
INK = '#0b0b0b'
SECONDARY = '#52514e'
MUTED = '#898781'
SURFACE = '#fcfcfb'
NEUTRAL_FILL = '#f0efec'
NEUTRAL_EDGE = '#c3c2b7'
BLUE = '#2a78d6'
BLUE_FILL = '#eaf2fc'
ORANGE = '#eb6834'
ORANGE_FILL = '#fdf0ea'
AQUA = '#1baf7a'
AQUA_FILL = '#e9f8f2'


def box(ax, x, y, w, h, title, lines, edge, fill, title_size=10, body_size=8):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle='round,pad=0.025,rounding_size=0.06',
        linewidth=1.2,
        edgecolor=edge,
        facecolor=fill,
        zorder=2,
    )
    ax.add_patch(patch)
    ax.text(
        x + 0.16, y + h - 0.24, title,
        ha='left', va='top', fontsize=title_size, fontweight='bold', color=INK, zorder=3,
    )
    if lines:
        ax.text(
            x + 0.16, y + h - 0.66, '\n'.join(lines),
            ha='left', va='top', fontsize=body_size, color=SECONDARY,
            linespacing=1.4, zorder=3,
        )


def arrow(ax, start, end, color, rad=0.0, style='-', lw=1.25):
    patch = FancyArrowPatch(
        start, end,
        arrowstyle='-|>', mutation_scale=11, linewidth=lw, linestyle=style,
        color=color, connectionstyle=f'arc3,rad={rad}', shrinkA=1.5, shrinkB=1.5,
        zorder=1,
    )
    ax.add_patch(patch)


def main():
    plt.rcParams.update({'font.size': 8, 'savefig.facecolor': SURFACE})
    fig = plt.figure(figsize=(7.2, 4.6), facecolor=SURFACE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    ax.text(0.25, 7.78, 'a', fontsize=14, fontweight='bold', color=INK, va='top')
    ax.text(0.58, 7.78, 'Processing paths', fontsize=14, fontweight='bold', color=INK, va='top')

    box(ax, 0.35, 5.65, 3.3, 1.55, 'MapGIS 6.x/67 vectors', [
        '.wt point · .wl line · .wp polygon',
        'Geometry · attributes · parameters',
        'CRS and topology sections',
    ], NEUTRAL_EDGE, NEUTRAL_FILL)
    box(ax, 4.35, 5.65, 3.3, 1.55, 'Reader / Writer', [
        'Binary sections ↔ GeoDataFrame',
        'CRS inference · topology rebuild',
        'Native write-back · section reuse',
    ], BLUE, BLUE_FILL)
    box(ax, 8.35, 5.65, 3.3, 1.55, 'Open vectors & access', [
        'GeoPandas · OGR formats',
        'PyPI · GitHub · pymapgis.testing',
        'Source and wheel examples',
    ], BLUE, BLUE_FILL)

    box(ax, 0.35, 3.55, 3.3, 1.65, 'Accompanying SLIB', [
        'Subgraph.lib · LINESTY.lib',
        'Fillgrph.lib · Colorlib.lib · Pcolor.lib',
        'Original cartographic definitions',
    ], NEUTRAL_EDGE, NEUTRAL_FILL)
    box(ax, 4.35, 3.55, 3.3, 1.65, 'Five library parsers', [
        'Symbols · fills · Colorlib channels',
        'Pcolor 32-byte nodes',
        '57 Fillgrph explicit non-results',
    ], ORANGE, ORANGE_FILL)
    box(ax, 8.35, 3.55, 3.3, 1.65, 'Original-library renderer', [
        'WP fills · WL chainage strokes',
        'WT symbols and annotations',
        'Polygon labels · PNG · PDF · SVG',
    ], ORANGE, ORANGE_FILL)

    arrow(ax, (3.65, 6.42), (4.15, 6.42), BLUE)
    arrow(ax, (7.65, 6.42), (8.15, 6.42), BLUE)
    arrow(ax, (3.65, 4.38), (4.15, 4.38), ORANGE)
    arrow(ax, (7.65, 4.38), (8.15, 4.38), ORANGE)
    arrow(ax, (5.95, 5.60), (5.95, 5.24), BLUE, style=(0, (3, 2)), lw=1.0)
    ax.text(6.05, 5.39, 'geometry + graphic parameters', fontsize=7.0, color=MUTED, va='center')

    ax.text(0.25, 3.02, 'b', fontsize=14, fontweight='bold', color=INK, va='top')
    ax.text(
        0.58, 3.02, 'Evidence, validation and reproduction',
        fontsize=14, fontweight='bold', color=INK, va='top',
    )

    box(ax, 0.35, 1.45, 5.3, 1.2, 'Dialogue reference anchors', [
        '14 exact matches', '25 unknown codes resolved',
    ], AQUA, AQUA_FILL, title_size=9.4, body_size=8.2)
    box(ax, 6.35, 1.45, 5.3, 1.2, 'Line coordinate fidelity', [
        '37 features · 782 vertices', '0 omitted · max |Δ| ≤ 1e-9',
    ], AQUA, AQUA_FILL, title_size=9.4, body_size=8.2)
    box(ax, 0.35, 0.10, 5.3, 1.2, 'Real regression fixtures', [
        '12 JWD layers + 5 SLIB', 'SHA-256 manifest',
    ], AQUA, AQUA_FILL, title_size=9.4, body_size=8.2)
    box(ax, 6.35, 0.10, 5.3, 1.2, 'Release verification', [
        '423 passed · 1 environment-dependent skip',
        'Public-release CI · local archive inspection',
    ], AQUA, AQUA_FILL, title_size=9.4, body_size=8.2)

    ax.text(
        11.65, 7.78,
        'Native MapGIS visual acceptance pending.',
        fontsize=6.8, color=MUTED, ha='right', va='top',
    )

    fig.savefig(OUT / 'softwarex_architecture.pdf', dpi=600, bbox_inches='tight', pad_inches=0.0)
    fig.savefig(OUT / 'softwarex_architecture.png', dpi=600, bbox_inches='tight', pad_inches=0.0)
    fig.savefig(OUT / 'softwarex_architecture.svg', dpi=600, bbox_inches='tight', pad_inches=0.0)
    fig.savefig(OUT / 'softwarex_architecture.tiff', dpi=600, bbox_inches='tight', pad_inches=0.0)
    plt.close(fig)

    # The SVG doctype is unnecessary for standalone submission files and prevents
    # secure XML parsers from auditing the editable schematic.
    svg_path = OUT / 'softwarex_architecture.svg'
    svg = svg_path.read_text(encoding='utf-8')
    svg = re.sub(r'<!DOCTYPE\s+svg[^>]*>\s*', '', svg, count=1, flags=re.IGNORECASE)

    def declare_font_size(match):
        tag = match.group(0)
        font = re.search(r'\bfont:\s*(?:\d+\s+)?([\d.]+)px', tag)
        return tag if font is None else f'{tag[:-1]} font-size="{font.group(1)}px">'

    svg = re.sub(r'<text\b[^>]*>', declare_font_size, svg)
    svg = '\n'.join(line.rstrip() for line in svg.splitlines()) + '\n'
    svg_path.write_text(svg, encoding='utf-8')


if __name__ == '__main__':
    main()
