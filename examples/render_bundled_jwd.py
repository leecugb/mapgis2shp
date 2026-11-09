#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Render the bundled twelve-layer JWD dataset with its five matching SLIB files.

The generated reports provide internal regression evidence, not native MapGIS
visual acceptance. The JWD and SLIB files retain their original data terms.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if importlib.util.find_spec("pymapgis") is None and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import matplotlib as mpl  # noqa: E402

from pymapgis import GraphicLibraries, GraphicRenderer, Reader  # noqa: E402
from pymapgis.testing import jwd_path, slib_path  # noqa: E402

# Editable vector text: svg.fonttype='none' and pdf.fonttype=42.
mpl.rcParams["font.family"] = "sans-serif"
mpl.rcParams["font.sans-serif"] = ["Arial", "Microsoft YaHei", "SimSun", "DejaVu Sans"]
mpl.rcParams["svg.fonttype"] = "none"
mpl.rcParams["pdf.fonttype"] = 42
mpl.rcParams["ps.fonttype"] = 42
mpl.rcParams["savefig.dpi"] = 600


def regression_layers(root):
    """Accept both the published WP-backup and normalized WP fixture layouts."""
    layers = []
    for path in sorted(Path(root).iterdir()):
        suffix = path.suffix.lower()
        if suffix not in {".wl", ".wp", ".wt", ".wp~"}:
            continue
        if suffix == ".wp~":
            layer = Reader(str(path), read_graphic_params=True).geodataframe
            layer.attrs["source"] = path.name
            layer.attrs["kind"] = "wp"
            layers.append(layer)
        else:
            layers.append(path)
    return layers


def summarise(reports):
    unknown_codes = sorted(
        {int(code) for report in reports for code in report.get("unknown_colors", {})}
    )
    unknown_fonts = sorted(
        {str(font) for report in reports for font in report.get("unknown_fonts", {})}
    )
    return {
        "layers": len(reports),
        "features": sum(report["features"] for report in reports),
        "drawn": sum(report["drawn"] for report in reports),
        "polygon_labels": sum(report.get("polygon_label", 0) for report in reports),
        "excluded_text": sum(report.get("excluded_text", 0) for report in reports),
        "unknown_colour_codes": unknown_codes,
        "unknown_colour_occurrences": sum(
            sum(report.get("unknown_colors", {}).values()) for report in reports
        ),
        "solid_fallbacks": sum(
            report.get("fallback", 0) + report.get("aux_fallback", 0)
            for report in reports
        ),
        "unknown_fills": sum(
            report.get("unknown_fill", 0) + report.get("aux_unknown_fill", 0)
            for report in reports
        ),
        "unresolved_symbols": sum(report.get("symbols_unresolved", 0) for report in reports),
        "empty_patterns": sum(
            report.get("empty_pattern", 0) + report.get("aux_empty_pattern", 0)
            for report in reports
        ),
        "cycle_limits": sum(
            report.get("cycle_limit", 0) + report.get("aux_cycle_limit", 0)
            for report in reports
        ),
        "unknown_fonts": unknown_fonts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("jwd_render"),
        help="Directory for jwd_map.png, jwd_map.pdf, jwd_map.svg and reports",
    )
    parser.add_argument("--dpi", type=int, default=600)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help="Optional directory of twelve JWD-compatible layers; defaults to bundled data",
    )
    parser.add_argument(
        "--target-crs",
        default=None,
        help="Optional output CRS such as EPSG:32643; default estimates UTM per layer",
    )
    parser.add_argument(
        "--source-crs",
        default=None,
        help="CRS to assign to layers with missing CRS metadata, such as EPSG:4326",
    )
    parser.add_argument(
        "--map-units-per-mm",
        type=float,
        default=None,
        help="Map-coordinate units per paper millimetre for layers without a CRS",
    )
    args = parser.parse_args()

    libraries = GraphicLibraries.from_directory(slib_path())
    renderer = GraphicRenderer(
        libraries,
        scale=250000,
        native_text_layout=True,
        polygon_labels=True,
        polygon_label_fontsize=5.0,
        polygon_label_scale=0.7,
        map_units_per_mm=args.map_units_per_mm,
        text_font_family=["Microsoft YaHei", "SimSun", "DejaVu Sans"],
        font_zh_map={1: "SimSun", 4: "SimHei"},
        font_en_map={0: "DejaVu Sans"},
    )
    input_dir = args.input_dir if args.input_dir is not None else jwd_path()
    raw_layers = regression_layers(input_dir)
    layers = []
    for layer in raw_layers:
        if hasattr(layer, "to_crs"):
            source_name = layer.attrs.get("source", "<GeoDataFrame>")
            kind = layer.attrs.get("kind")
        else:
            path = Path(layer)
            source_name = path.name
            kind = path.suffix.lower().lstrip(".")
            layer = GraphicRenderer.read_layer(path)
        layer.attrs["source"] = source_name
        layer.attrs["kind"] = kind
        if layer.crs is None and args.source_crs:
            layer = layer.set_crs(args.source_crs, allow_override=True)
        if layer.crs is not None:
            if len(layer) == 0:
                if args.target_crs:
                    layer = layer.set_crs(args.target_crs, allow_override=True)
            else:
                target_crs = args.target_crs or layer.estimate_utm_crs()
                if target_crs != layer.crs:
                    layer = layer.to_crs(target_crs)
        layers.append(layer)
    if args.map_units_per_mm is None and any(layer.crs is None for layer in layers):
        parser.error("Layers without CRS require --source-crs or --map-units-per-mm")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    png = args.output_dir / "jwd_map.png"
    pdf = args.output_dir / "jwd_map.pdf"
    svg = args.output_dir / "jwd_map.svg"
    result = renderer.render(layers, figsize=(12, 7.5), dpi=args.dpi)
    save_options = {"bbox_inches": "tight", "pad_inches": 0.02}
    result.figure.savefig(png, format="png", dpi=args.dpi, **save_options)
    result.figure.savefig(pdf, format="pdf", **save_options)
    result.figure.savefig(svg, format="svg", **save_options)
    svg.write_text(
        "\n".join(
            line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines()
        ) + "\n",
        encoding="utf-8",
    )
    result.figure.clear()

    summary = summarise(result.reports)
    public_reports = []
    for report in result.reports:
        public_report = dict(report)
        if "source" in public_report:
            public_report["source"] = Path(public_report["source"]).name
        public_reports.append(public_report)
    report_path = args.output_dir / "jwd_render_reports.json"
    report_path.write_text(
        json.dumps({"summary": summary, "layers": public_reports}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("OUTPUT_PNG", png)
    print("OUTPUT_PDF", pdf)
    print("OUTPUT_SVG", svg)
    print("OUTPUT_REPORTS", report_path)


if __name__ == "__main__":
    main()
