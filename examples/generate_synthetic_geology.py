#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate an independent synthetic geological map and native MapGIS layers.

The data are deterministic test fixtures, not geological interpretations of JWD
or of any real area. Layer schemas and graphic parameters follow the project's
MapGIS examples, while all geometries and SIM-* identifiers are synthetic.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString, Point, Polygon

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from examples.render_bundled_jwd import summarise  # noqa: E402
from pymapgis import GraphicLibraries, GraphicRenderer, Writer  # noqa: E402
from pymapgis.testing import slib_path  # noqa: E402

CRS = "EPSG:32643"
ORIGIN_X = 500000.0
ORIGIN_Y = 4400000.0
WIDTH = 12000.0
HEIGHT = 9000.0
LAYER_NAMES = (
    "SIM_LDLYAAE002.WP",
    "SIM_LDZOFBB001.WP",
    "SIM_LDZOFBB002.WP",
    "SIM_LDZOFBB003.WP",
    "SIM_LDZOFBB004.WP",
    "SIM_LDLYAAE001.WL",
    "SIM_LDZOFBA002.WL",
    "SIM_LDZOFBA003.WL",
    "SIM_LDZOFBA005.WL",
    "SIM_LDZOFBB098.WL",
    "SIM_LDZOFBA016.WT",
    "SIM_LDZOFBB099.WT",
)
def _rgb(hex_value):
    value = hex_value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


SYNTHETIC_COLORS = {
    602: _rgb("#2a78d6"),
    498: _rgb("#eb6834"),
    533: _rgb("#1baf7a"),
    689: _rgb("#eda100"),
    904: _rgb("#e87ba4"),
    1226: _rgb("#008300"),
    1243: _rgb("#6250d6"),
    534: _rgb("#e34948"),
    1096: _rgb("#52514e"),
    9: _rgb("#cde2fb"),
}


def _xy(x, y):
    return ORIGIN_X + x, ORIGIN_Y + y


def _line(points):
    return LineString([_xy(x, y) for x, y in points])


def _ellipse(cx, cy, rx, ry, angle_deg, count=96):
    angle = math.radians(angle_deg)
    ca, sa = math.cos(angle), math.sin(angle)
    points = []
    for i in range(count):
        t = 2 * math.pi * i / count
        x, y = rx * math.cos(t), ry * math.sin(t)
        points.append(_xy(cx + x * ca - y * sa, cy + x * sa + y * ca))
    return Polygon(points)


def _frame(records, source, kind):
    layer = gpd.GeoDataFrame(records, crs=CRS)
    layer.attrs["source"] = source
    layer.attrs["kind"] = kind
    return layer


def _line_record(geom, style=1, aux=0, color=1, width=0.1, xc=1.0, yc=1.0, **attrs):
    record = {
        "linetype": style,
        "aux_linetype": aux,
        "aux_flag": 0,
        "color": color,
        "width": width,
        "x_coef": xc,
        "y_coef": yc,
        "aux_color": 0,
        "layer": 1,
        "transparent": 0,
        "geometry": geom,
    }
    record.update(attrs)
    return record


def _point_record(geom, symbol=0, height=2.0, width=2.0, angle=0.0,
                  color=1, category="注记", text="", **attrs):
    record = {
        "point_type": 1 if symbol else 0,
        "symbol_no": symbol,
        "height": height,
        "width": width,
        "spacing": 0.0,
        "angle": angle,
        "color": color,
        "layer": 1,
        "pen_width": 0.1,
        "font_zh": 1,
        "font_en": 0,
        "font_style": 0,
        "CHFCEC": category,
        "CHFCED": text,
        "geometry": geom,
    }
    record.update(attrs)
    return record


def _polygon_record(geom, code, fill, pattern=0, pattern_color=1,
                    pattern_height=0.0, pattern_width=0.0):
    return {
        "class": 1,
        "fill_color": fill,
        "pattern": pattern,
        "pattern_height": pattern_height,
        "pattern_width": pattern_width,
        "pattern_color": pattern_color,
        "layer": 1,
        "QDUECC": code,
        "QDUECD": code,
        "CHFCAC": code,
        "geometry": geom,
    }


def _curve(level, phase=0.0):
    xs = np.linspace(0, WIDTH, 49)
    return [(x, level + 0.1 * x + 150 * math.sin(x / 850 + phase)) for x in xs]


def generate_layers(seed=42):
    """Return twelve independent synthetic GeoDataFrames in render order."""
    layers = {}
    phase_offset = float(seed) * 0.01
    boundary = Polygon([_xy(0, 0), _xy(WIDTH, 0), _xy(WIDTH, HEIGHT), _xy(0, HEIGHT)])
    levels = [0, 1500, 3000, 4500, 6000, 7500, 9000]
    codes = ["SIM-A", "SIM-B", "SIM-C", "SIM-D", "SIM-E", "SIM-F"]
    fills = [602, 498, 533, 689, 904, 1226]
    polygons = []
    for i, (code, fill) in enumerate(zip(codes, fills)):
        lower = _curve(levels[i], phase=i * 0.35 + phase_offset)
        upper = _curve(levels[i + 1], phase=i * 0.35 + phase_offset)
        geometry = Polygon(
            [_xy(x, y) for x, y in lower + list(reversed(upper))]
        ).intersection(boundary)
        pattern = 0
        polygons.append(_polygon_record(
            geometry, code, fill, pattern=pattern,
            pattern_color=1, pattern_height=3.0, pattern_width=3.0,
        ))
    layers["SIM_LDZOFBB001.WP"] = _frame(polygons, "SIM_LDZOFBB001.WP", "wp")
    layers["SIM_LDZOFBB002.WP"] = _frame([
        _polygon_record(_ellipse(2800, 6100, 1000, 650, -20), "SIM-V", 534)
    ], "SIM_LDZOFBB002.WP", "wp")
    layers["SIM_LDZOFBB003.WP"] = _frame([
        _polygon_record(_ellipse(7900, 4800, 1200, 800, 25), "SIM-G", 1243)
    ], "SIM_LDZOFBB003.WP", "wp")
    layers["SIM_LDZOFBB004.WP"] = _frame([
        _polygon_record(_ellipse(1900, 3000, 1400, 700, 35), "SIM-M", 1096)
    ], "SIM_LDZOFBB004.WP", "wp")
    layers["SIM_LDLYAAE002.WP"] = _frame([
        _polygon_record(_ellipse(2600, 1050, 1700, 450, -10), "SIM-WATER", 9,
                        pattern=725, pattern_color=2,
                        pattern_height=3.0, pattern_width=3.0)
    ], "SIM_LDLYAAE002.WP", "wp")

    boundaries = []
    for i, level in enumerate(levels[1:-1], start=1):
        boundaries.append(_line_record(
            _line(_curve(level, phase=i * 0.35 + phase_offset)), style=1, width=0.1,
            CHFCAC=f"B{i:05d}",
        ))
    layers["SIM_LDZOFBA002.WL"] = _frame(boundaries, "SIM_LDZOFBA002.WL", "wl")

    fault_geometries = [
        _line([(500, 100), (3000, 2200), (6200, 4700), (9200, 7400), (11600, 8900)]),
        _line([(300, 8300), (3300, 6500), (6900, 4200), (11100, 1700)]),
        _line([(3000, 100), (4500, 3000), (6100, 6100), (7600, 8900)]),
    ]
    faults = []
    for i, geometry in enumerate(fault_geometries, start=1):
        faults.append(_line_record(
            geometry, style=2, width=0.08, yc=0.1, GZEEB=f"0{i}",
            GZEAB=f"SimFault-{i}", GZECE=[45, 60, 70][i - 1],
            CHFCAC=f"F{i:05d}",
        ))
    layers["SIM_LDZOFBA003.WL"] = _frame(faults, "SIM_LDZOFBA003.WL", "wl")

    folds = [
        _line_record(_line([(200, 2200), (2500, 3100), (5200, 3600), (8200, 4200), (11600, 5100)]),
                     style=65, aux=0, width=0.1, xc=30, yc=1, CHFCAC="FOLD01"),
        _line_record(_line([(500, 7000), (3000, 5900), (5900, 5300), (8800, 4600), (11500, 3900)]),
                     style=65, aux=4, width=0.1, xc=25, yc=1, CHFCAC="FOLD02"),
    ]
    layers["SIM_LDZOFBA005.WL"] = _frame(folds, "SIM_LDZOFBA005.WL", "wl")
    annotation_lines = [
        _line_record(_line([(5400, 3800), (5700, 4000)]), style=1, width=0.05),
        _line_record(_line([(7600, 4900), (7900, 5100)]), style=1, width=0.05),
    ]
    layers["SIM_LDZOFBB098.WL"] = _frame(annotation_lines, "SIM_LDZOFBB098.WL", "wl")

    rivers = []
    for i in range(3):
        geometry = _line([
            (0, 900 + i * 500), (1800, 1200 + i * 450), (3700, 1600 + i * 400),
            (5500, 2200 + i * 350), (7600, 2800 + i * 300),
            (9700, 3300 + i * 250), (12000, 3900 + i * 200),
        ])
        rivers.append(_line_record(geometry, style=1, color=2, width=0.15,
                                   CHFCAC=f"R{i + 1:05d}"))
    layers["SIM_LDLYAAE001.WL"] = _frame(rivers, "SIM_LDLYAAE001.WL", "wl")

    attitude_records = []
    dip_records = []
    samples = [
        (1400, 1900, 30, 35), (2300, 2800, 45, 42), (3300, 3700, 60, 50),
        (4300, 2600, 75, 46), (5400, 4600, 90, 60), (6500, 3500, 105, 55),
        (7400, 5600, 120, 65), (8500, 4300, 135, 58), (9600, 6000, 150, 62),
        (10600, 5000, 165, 70), (4800, 6800, 15, 38), (9200, 7400, 170, 75),
    ]
    for i, (x, y, angle, dip) in enumerate(samples, start=1):
        symbol = 1245 if i % 2 else 1249
        attitude_records.append(_point_record(
            Point(*_xy(x, y)), symbol=symbol, height=5, width=5, angle=angle,
            category="产状", text=str(dip), CHFCAC=f"A{i:05d}",
        ))
        dip_records.append(_point_record(
            Point(*_xy(x + 120, y + 80)), height=2, width=2,
            category="产状", text=str(dip), CHFCAC=f"AT{i:05d}",
        ))
    layers["SIM_LDZOFBA016.WT"] = _frame(attitude_records, "SIM_LDZOFBA016.WT", "wt")

    for i, geometry in enumerate(fault_geometries):
        center = geometry.interpolate(0.52, normalized=True)
        dip = [45, 60, 70][i]
        dip_records.append(_point_record(
            center, symbol=1894, height=2.25, width=1.5, angle=[45, 70, 110][i],
            category="断层辅助点", CHFCAC=f"FA{i + 1:05d}",
        ))
        dip_records.append(_point_record(
            Point(center.x + 140, center.y + 100), height=2, width=2,
            category="断层辅助点", text=str(dip), CHFCAC=f"FD{i + 1:05d}",
        ))
    first = fault_geometries[0]
    for i, fraction in enumerate((0.45, 0.60), start=1):
        point = first.interpolate(fraction, normalized=True)
        dip_records.append(_point_record(
            point, symbol=1281, height=1, width=1, angle=45,
            category="断层辅助点", CHFCAC=f"FP{i:05d}",
        ))
    layers["SIM_LDZOFBB099.WT"] = _frame(dip_records, "SIM_LDZOFBB099.WT", "wt")

    layers = {name: layers[name] for name in LAYER_NAMES}
    if tuple(layers) != LAYER_NAMES:
        raise AssertionError("Unexpected synthetic layer order")
    return layers


def write_layers(layers, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, layer in layers.items():
        Writer(layer).to_file(output_dir / name)


def read_layers(output_dir):
    layers = []
    for name in LAYER_NAMES:
        path = Path(output_dir) / name
        layer = GraphicRenderer.read_layer(path)
        layer.attrs["source"] = name
        layer.attrs["kind"] = path.suffix.lower().lstrip(".")
        layers.append(layer)
    return layers


def render_layers(layers, output_dir, dpi=160):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    renderer = GraphicRenderer(
        GraphicLibraries.from_directory(slib_path()),
        scale=250000,
        native_text_layout=True,
        polygon_labels=True,
        polygon_label_fontsize=5.0,
        polygon_label_scale=0.7,
        text_font_family=["Microsoft YaHei", "SimSun", "DejaVu Sans"],
        font_zh_map={1: "SimSun", 4: "SimHei"},
        font_en_map={0: "DejaVu Sans"},
        color_overrides=SYNTHETIC_COLORS,
    )
    result = renderer.render(layers, output_dir / "synthetic_geology.png",
                             figsize=(12, 9), dpi=dpi)
    fig, ax = result.figure, result.axes
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    handles = []
    for code, fill in zip(["SIM-A", "SIM-B", "SIM-C", "SIM-D", "SIM-E", "SIM-F"],
                          [602, 498, 533, 689, 904, 1226]):
        rgb = SYNTHETIC_COLORS[fill]
        handles.append(Patch(facecolor=rgb, edgecolor="none", label=code))
    handles.extend([
        Patch(facecolor=SYNTHETIC_COLORS[1243], label="SIM-G"),
        Patch(facecolor=SYNTHETIC_COLORS[534], label="SIM-V"),
        Patch(facecolor=SYNTHETIC_COLORS[1096], label="SIM-M"),
        Patch(facecolor=SYNTHETIC_COLORS[9], label="SIM-WATER"),
        Line2D([0], [0], color="black", lw=1, label="Geological boundary"),
        Line2D([0], [0], color="black", lw=1, ls="--", label="Fault"),
        Line2D([0], [0], color=(0, 1, 1), lw=1.5, label="River"),
    ])
    fig.legend(handles=handles, loc="center left", bbox_to_anchor=(0.79, 0.5),
               title="SIMULATED UNITS", fontsize=8, title_fontsize=9,
               frameon=True, framealpha=0.9)
    fig.text(0.5, 0.96, "SIMULATED GEOLOGICAL MAP", ha="center", va="top",
             fontsize=16, fontweight="bold")
    fig.text(0.5, 0.925, "Synthetic test data only - no real geological interpretation",
             ha="center", va="top", fontsize=9, color="#555555")
    fig.subplots_adjust(left=0.03, right=0.76, top=0.88, bottom=0.06)
    xmin, ymin, xmax, ymax = result.bounds
    ax.plot([xmin + 400, xmin + 2400], [ymin + 350, ymin + 350], color="black", lw=2)
    ax.text(xmin + 1400, ymin + 500, "2 km", ha="center", fontsize=8)
    ax.text(xmax - 500, ymax - 500, "N\n↑", ha="center", va="center", fontsize=13)
    fig.savefig(output_dir / "synthetic_geology.png", dpi=dpi)
    fig.savefig(output_dir / "synthetic_geology.pdf", format="pdf")
    fig.savefig(output_dir / "synthetic_geology.svg", format="svg")
    fig.clear()
    return result


def write_metadata(output_dir, layers, reports, seed):
    output_dir = Path(output_dir)
    with (output_dir / "synthetic_units.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["code", "fill_color", "description"])
        for name in ("SIM_LDZOFBB001.WP", "SIM_LDZOFBB002.WP", "SIM_LDZOFBB003.WP",
                     "SIM_LDZOFBB004.WP", "SIM_LDLYAAE002.WP"):
            for row in layers[name].itertuples():
                writer.writerow([row.QDUECC, row.fill_color, "Synthetic test unit"])
    manifest = {
        "title": "Synthetic geological map - not measured data",
        "seed": seed,
        "crs": CRS,
        "origin": [ORIGIN_X, ORIGIN_Y],
        "layer_count": len(layers),
        "feature_counts": {name: len(layer) for name, layer in layers.items()},
        "summary": summarise(reports),
        "notice": (
            "All geometries and SIM-* identifiers are synthetic; "
            "no real JWD feature is reused."
        ),
    }
    (output_dir / "synthetic_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("output/synthetic_geology"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dpi", type=int, default=160)
    args = parser.parse_args()

    layers = generate_layers(seed=args.seed)
    vectors = args.output_dir / "vectors"
    write_layers(layers, vectors)
    native_layers = read_layers(vectors)
    result = render_layers(native_layers, args.output_dir, dpi=args.dpi)
    write_metadata(args.output_dir, layers, result.reports, args.seed)
    summary = summarise(result.reports)
    print(json.dumps({"output_dir": str(args.output_dir), "vectors": str(vectors),
                      "summary": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
