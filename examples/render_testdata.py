#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Render the seven bundled USGS layers and a strict-scale vector GeoPDF.

The PNG and SVG are previews. The GeoPDF is checked for its requested physical
scale, ISO 32000 georeferencing and absence of raster image objects. This is an
internal software-rendering example, not an original USGS or NGAC plot.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import matplotlib as mpl  # noqa: E402

mpl.use("Agg")
mpl.rcParams["svg.fonttype"] = "none"
mpl.rcParams["pdf.fonttype"] = 42

from pymapgis import GraphicLibraries, GraphicRenderer  # noqa: E402
from pymapgis.geopdf import inspect_geopdf, write_vector_geopdf  # noqa: E402
from pymapgis.testing import slib_path, testdata_path  # noqa: E402


def _json_default(value):
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/testdata_render"),
        help="Directory for previews, GeoPDF and JSON reports",
    )
    parser.add_argument("--dpi", type=int, default=300, help="Preview/layout DPI")
    args = parser.parse_args()
    if args.dpi <= 0:
        parser.error("--dpi must be positive")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    layers = []
    for path in sorted(testdata_path().iterdir()):
        if path.suffix.lower() not in {".wt", ".wl", ".wp"}:
            continue
        layer = GraphicRenderer.read_layer(path)
        layer.attrs["source"] = path.name
        layer.attrs["kind"] = path.suffix.lower().lstrip(".")
        layers.append(layer)
    if len(layers) != 7 or sum(len(layer) for layer in layers) != 8512:
        raise RuntimeError("The bundled seven-layer USGS fixture is incomplete")

    renderer = GraphicRenderer(
        GraphicLibraries.from_directory(slib_path()),
        scale=24000,
        vector_patterns=True,
        native_text_layout=True,
        polygon_labels=True,
        polygon_label_fields=("QDUECC", "QDUECD"),
        polygon_label_fontsize=5.0,
        polygon_label_scale=0.7,
        polygon_label_avoid_collisions=True,
        polygon_label_randomize=True,
        polygon_label_seed=42,
        polygon_label_buffer_pt=2.0,
        polygon_label_max_offset_pt=48.0,
        attitude_dip_labels=True,
        attitude_dip_label_direction="symbol",
        attitude_dip_tick_mm=2.0,
        attitude_dip_label_buffer_pt=0.5,
        exclude_text_categories=("代号", "产状"),
        text_font_family=["Microsoft YaHei", "SimSun", "DejaVu Sans"],
        font_zh_map={1: "SimSun", 4: "SimHei"},
        font_en_map={0: "DejaVu Sans"},
    )
    result = renderer.render(
        layers,
        figsize=(7.5, 9.5),
        dpi=args.dpi,
        axes_rect=(0.02, 0.02, 0.96, 0.96),
    )
    result.figure.savefig(args.output_dir / "testdata_map.png", dpi=args.dpi)
    result.figure.savefig(args.output_dir / "testdata_map.svg")

    geopdf_path = args.output_dir / "testdata_geopdf_1_24000.pdf"
    info = write_vector_geopdf(
        geopdf_path,
        result.figure,
        result.axes,
        "EPSG:32611",
        scale_denominator=24000,
        title="USGS Conejo Well 7.5-minute quadrangle - 1:24000 vector GeoPDF",
    )
    readback = inspect_geopdf(geopdf_path)
    transform = info["page_transform"]
    scale_x = (
        abs(transform[1]) * info["page_width_pt"] * info["metres_per_unit"]
        / (info["page_width_mm"] / 1000.0)
    )
    scale_y = (
        abs(transform[5]) * info["page_height_pt"] * info["metres_per_unit"]
        / (info["page_height_mm"] / 1000.0)
    )
    if not all(
        math.isclose(value, 24000, rel_tol=1e-9, abs_tol=1e-6)
        for value in (scale_x, scale_y)
    ):
        raise RuntimeError(f"GeoPDF scale mismatch: X={scale_x}, Y={scale_y}")
    if readback["image_count"] or readback["image_xobject_count"]:
        raise RuntimeError("The formal GeoPDF contains raster image objects")

    collisions = renderer.inspect_text_collisions(result.axes)
    reports = []
    for report in result.reports:
        item = dict(report)
        if "source" in item:
            item["source"] = Path(item["source"]).name
        reports.append(item)
    summary = {
        "layers": len(reports),
        "source_features": sum(len(layer) for layer in layers),
        "drawn": sum(report["drawn"] for report in reports),
        "geopdf_actual_scale_x": scale_x,
        "geopdf_actual_scale_y": scale_y,
        "geopdf_image_objects": readback["image_xobject_count"],
        "geopdf_vector_drawings": readback["drawing_count"],
        "geopdf_text_characters": readback["text_character_count"],
        "text_overlap_count": collisions["overlap_count"],
    }
    for name, payload in (
        ("render_summary.json", summary),
        ("layer_reports.json", reports),
        ("text_collisions.json", collisions),
    ):
        (args.output_dir / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
            encoding="utf-8",
        )
    result.figure.clear()
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
