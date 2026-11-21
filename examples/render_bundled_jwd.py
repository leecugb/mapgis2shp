#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Render twelve user-supplied JWD layers with five matching SLIB files.

Original NGAC JWD vectors are not bundled. Obtain them through the official
channel and set PYMAPGIS_JWD, or use a source checkout that already contains a
legally obtained local fixture copy. The five generic SLIB libraries are bundled;
PYMAPGIS_SLIB can override them. Generated reports provide internal regression
evidence, not native MapGIS visual acceptance. Source data retain their original
terms.

The target CRS and map scale are explicit options. Without --target-crs, one
source-datum Gauss-Kruger zone is computed from the combined layer-bounds
longitude. The default ISO 32000 GeoPDF preserves the original-library raster
appearance and embeds the actual viewport and coordinate reference definition.
Full label collision avoidance and attitude-point dip attributes are enabled by
default; --legacy-label-layout and --native-attitude-annotations retain the
corresponding historical behaviours.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if importlib.util.find_spec("pymapgis") is None and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import matplotlib as mpl  # noqa: E402
from pyproj.exceptions import ProjError  # noqa: E402

from pymapgis import GraphicLibraries, GraphicRenderer, Reader  # noqa: E402
from pymapgis.render_projection import prepare_render_layers  # noqa: E402
from pymapgis.testing import jwd_path, slib_path  # noqa: E402

# Editable vector text: svg.fonttype='none' and pdf.fonttype=42.
mpl.rcParams["font.family"] = "sans-serif"
mpl.rcParams["font.sans-serif"] = ["Arial", "Microsoft YaHei", "SimSun", "DejaVu Sans"]
mpl.rcParams["svg.fonttype"] = "none"
mpl.rcParams["pdf.fonttype"] = 42
mpl.rcParams["ps.fonttype"] = 42
mpl.rcParams["savefig.dpi"] = 600


def regression_layers(root):
    """Load one copy of each vector, preferring original WP backups.

    A directory may contain both normalized ``.WP`` files and their original
    ``.WP~`` backups. The backup is the canonical JWD source in that case; loading
    both would duplicate polygons, labels and render counts.
    """
    candidates = list(Path(root).iterdir())
    backup_names = {path.name for path in candidates if path.suffix.lower() == ".wp~"}
    layers = []
    for path in sorted(candidates):
        suffix = path.suffix.lower()
        if suffix not in {".wl", ".wp", ".wt", ".wp~"}:
            continue
        if suffix == ".wp" and path.name + "~" in backup_names:
            continue
        if suffix == ".wp~":
            with Reader(str(path), read_graphic_params=True) as reader:
                layer = reader.geodataframe
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
        "source_features": sum(
            report.get("source_features", report["features"]) for report in reports
        ),
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


def _positive_float(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("value must be positive and finite")
    return number


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("jwd_render"),
        help="Directory for preview PNG/SVG, strict-scale GeoPDF and reports",
    )
    parser.add_argument("--dpi", type=int, default=600)
    parser.add_argument(
        "--figsize",
        type=_positive_float,
        nargs=2,
        default=(12.0, 7.5),
        metavar=("WIDTH_IN", "HEIGHT_IN"),
        help="Initial figure size used for layout before exact-scale GeoPDF sizing (default: 12 7.5)",
    )
    parser.add_argument(
        "--axes-rect",
        type=float,
        nargs=4,
        default=None,
        metavar=("LEFT", "BOTTOM", "WIDTH", "HEIGHT"),
        help="Optional normalized Axes rectangle, for example 0.03 0.03 0.94 0.94",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help="Optional directory of twelve JWD layers; defaults to PYMAPGIS_JWD",
    )
    parser.add_argument(
        "--slib-dir",
        type=Path,
        default=None,
        help="Optional directory of five matching SLIB files; defaults to PYMAPGIS_SLIB",
    )
    parser.add_argument(
        "--target-crs",
        default=None,
        help=(
            "Output CRS (EPSG or PROJ). Default: one source-datum 6-degree "
            "Gauss-Kruger zone from the mean longitude of all layers"
        ),
    )
    parser.add_argument(
        "--zone-width",
        type=int,
        choices=(3, 6),
        default=6,
        help="Gauss-Kruger zone width used only when --target-crs is absent (default: 6)",
    )
    parser.add_argument(
        "--scale",
        type=_positive_float,
        default=250000,
        help="Map scale denominator used for paper sizing (default: 250000)",
    )
    parser.add_argument(
        "--attribute-dip-labels",
        action="store_true",
        help="Derive dip labels from each attitude point's dip/GZBBAD attribute (default)",
    )
    parser.add_argument(
        "--native-attitude-annotations",
        action="store_true",
        help="Keep independent native dip annotations instead of deriving them from attitude points",
    )
    parser.add_argument(
        "--legacy-label-layout",
        action="store_true",
        help="Disable integrated label collision avoidance and preserve the historical baseline",
    )
    parser.add_argument(
        "--polygon-label-fontsize",
        type=_positive_float,
        default=5.0,
        help="Base polygon-label size in points before polygon_label_scale (default: 5.0)",
    )
    parser.add_argument(
        "--polygon-label-max-offset-pt",
        type=_positive_float,
        default=48.0,
        help="Maximum in-polygon label offset in points (default: 48.0)",
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
    parser.add_argument(
        "--no-geopdf",
        action="store_true",
        help="Skip strict-scale GeoPDF; PNG/SVG previews will have no scale-certified PDF",
    )
    args = parser.parse_args()
    if args.attribute_dip_labels and args.native_attitude_annotations:
        parser.error("--attribute-dip-labels and --native-attitude-annotations are mutually exclusive")
    if args.axes_rect is not None:
        rect = [float(v) for v in args.axes_rect]
        if (any(not math.isfinite(v) for v in rect)
                or rect[0] < 0 or rect[1] < 0 or rect[2] <= 0 or rect[3] <= 0
                or rect[0] + rect[2] > 1 or rect[1] + rect[3] > 1):
            parser.error("--axes-rect must be LEFT BOTTOM WIDTH HEIGHT within the figure")
    use_attribute_dips = args.attribute_dip_labels or (
        not args.native_attitude_annotations and not args.legacy_label_layout
    )
    full_label_avoidance = not args.legacy_label_layout

    try:
        slib_dir = args.slib_dir if args.slib_dir is not None else slib_path()
        libraries = GraphicLibraries.from_directory(slib_dir)
        input_dir = args.input_dir if args.input_dir is not None else jwd_path()
        raw_layers = regression_layers(input_dir)
    except FileNotFoundError as exc:
        parser.exit(2, f"error: {exc}\n")

    renderer = GraphicRenderer(
        libraries,
        scale=args.scale,
        vector_patterns=True,
        native_text_layout=True,
        polygon_labels=True,
        polygon_label_fontsize=args.polygon_label_fontsize,
        polygon_label_scale=0.7,
        polygon_label_avoid_collisions=full_label_avoidance,
        polygon_label_randomize=full_label_avoidance,
        polygon_label_seed=42 if full_label_avoidance else None,
        polygon_label_buffer_pt=2.0,
        polygon_label_max_offset_pt=args.polygon_label_max_offset_pt,
        map_units_per_mm=args.map_units_per_mm,
        text_font_family=["Microsoft YaHei", "SimSun", "DejaVu Sans"],
        font_zh_map={1: "SimSun", 4: "SimHei"},
        font_en_map={0: "DejaVu Sans"},
        exclude_text_categories=("代号", "产状") if use_attribute_dips else ("代号",),
        attitude_dip_labels=use_attribute_dips,
        attitude_dip_label_direction="symbol",
        attitude_dip_tick_mm=2.0,
        attitude_dip_label_buffer_pt=0.5,
        attitude_symbol_scale=1.0,
    )
    layers = []
    source_manifest = []
    for layer in raw_layers:
        if hasattr(layer, "to_crs"):
            source_name = layer.attrs.get("source", "<GeoDataFrame>")
            kind = layer.attrs.get("kind")
            source_path = input_dir / source_name
            if not source_path.exists():
                source_path = None
        else:
            path = Path(layer)
            source_path = path
            source_name = path.name
            kind = path.suffix.lower().lstrip(".")
            layer = GraphicRenderer.read_layer(path)
        layer.attrs["source"] = source_name
        layer.attrs["kind"] = kind
        layers.append(layer)
        source_crs = getattr(layer, "crs", None)
        manifest_item = {
            "file": source_name,
            "features": int(len(layer)),
            "native_crs": str(source_crs) if source_crs is not None else None,
            "native_epsg": source_crs.to_epsg() if source_crs is not None else None,
        }
        if source_path is not None:
            raw = source_path.read_bytes()
            manifest_item.update({
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "native_map_scale_at_byte_143": (
                    struct.unpack_from("<d", raw, 143)[0] if len(raw) >= 151 else None
                ),
                "projection_scale_at_byte_232": (
                    struct.unpack_from("<d", raw, 232)[0] if len(raw) >= 240 else None
                ),
            })
        source_manifest.append(manifest_item)
    try:
        layers, target_crs, projection_report = prepare_render_layers(
            layers,
            target_crs=args.target_crs,
            source_crs=args.source_crs,
            zone_width=args.zone_width,
            map_units_per_mm=args.map_units_per_mm,
        )
    except (ValueError, ProjError) as exc:
        parser.error(str(exc))
    if target_crs is None and not args.no_geopdf:
        parser.error("GeoPDF requires source CRS metadata; use --source-crs or --no-geopdf")
    if (target_crs is not None and not args.no_geopdf
            and getattr(target_crs, "is_geographic", False)):
        parser.error("GeoPDF requires a projected target CRS; --target-crs is geographic")
    projection_report["scale_denominator"] = args.scale
    projection_report["dpi"] = args.dpi
    projection_report["initial_figsize_inches"] = list(args.figsize)
    projection_report["axes_rect"] = list(args.axes_rect) if args.axes_rect else None
    projection_report["output_policy"] = {
        "preview_formats": ["png", "svg"],
        "formal_pdf": "strict_scale_geopdf",
        "ordinary_pdf": False,
    }
    projection_report["label_layout"] = {
        "mode": "full" if full_label_avoidance else "legacy",
        "attitude_dip_source": "attribute" if use_attribute_dips else "native_annotations",
        "dip_labels_predrawn_before_polygons": full_label_avoidance and use_attribute_dips,
        "native_annotations_registered_first": full_label_avoidance,
        "polygon_label_randomize": renderer.polygon_label_randomize,
        "polygon_label_seed": renderer.polygon_label_seed,
        "polygon_label_buffer_pt": renderer.polygon_label_buffer_pt,
        "polygon_label_max_offset_pt": renderer.polygon_label_max_offset_pt,
        "polygon_label_fontsize_pt": renderer.polygon_label_fontsize,
        "attitude_dip_label_buffer_pt": renderer.attitude_dip_label_buffer_pt,
        "attitude_dip_tick_mm": renderer.attitude_dip_tick_mm,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    png = args.output_dir / "jwd_map.png"
    svg = args.output_dir / "jwd_map.svg"
    result = renderer.render(
        layers, figsize=tuple(args.figsize), dpi=args.dpi, axes_rect=args.axes_rect,
    )
    # PNG/SVG are previews only. Do not emit an ordinary tight-bbox PDF:
    # its physical page does not implement the requested map scale.
    save_options = {"bbox_inches": "tight", "pad_inches": 0.02}
    result.figure.savefig(png, format="png", dpi=args.dpi, **save_options)
    result.figure.savefig(svg, format="svg", **save_options)
    svg.write_text(
        "\n".join(
            line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines()
        ) + "\n",
        encoding="utf-8",
    )
    geopdf_info = None
    actual_scale_x = actual_scale_y = None
    if not args.no_geopdf:
        from pymapgis.geopdf import inspect_geopdf, write_vector_geopdf

        geopdf_path = args.output_dir / "jwd_map_geopdf.pdf"
        geopdf_info = write_vector_geopdf(
            geopdf_path,
            result.figure,
            result.axes,
            target_crs,
            scale_denominator=args.scale,
            title="Kurgan sheet J43C001002 - original-library vector rendering",
        )
        geopdf_info["readback"] = inspect_geopdf(geopdf_path)
        transform = geopdf_info["page_transform"]
        actual_scale_x = (
            abs(transform[1]) * geopdf_info["page_width_pt"]
            * geopdf_info["metres_per_unit"]
            / (geopdf_info["page_width_mm"] / 1000.0)
        )
        actual_scale_y = (
            abs(transform[5]) * geopdf_info["page_height_pt"]
            * geopdf_info["metres_per_unit"]
            / (geopdf_info["page_height_mm"] / 1000.0)
        )
        if (not math.isclose(actual_scale_x, args.scale, rel_tol=1e-9, abs_tol=1e-6)
                or not math.isclose(actual_scale_y, args.scale, rel_tol=1e-9, abs_tol=1e-6)):
            parser.exit(3, f"GeoPDF scale mismatch: X={actual_scale_x}, Y={actual_scale_y}, expected={args.scale}\n")
        readback = geopdf_info["readback"]
        if readback["image_count"] or readback["image_xobject_count"]:
            parser.exit(3, "GeoPDF contains raster image objects; vector-only delivery is required\n")
        geopdf_info["actual_scale_x"] = actual_scale_x
        geopdf_info["actual_scale_y"] = actual_scale_y
    # Audit after the GeoPDF sizing: write_vector_geopdf rescales the figure to
    # the strict paper scale, so only this geometry is the shipped deliverable.
    collision_audit = renderer.inspect_text_collisions(result.axes)
    (args.output_dir / "jwd_text_collisions.json").write_text(
        json.dumps(collision_audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    result.figure.clear()

    summary = summarise(result.reports)
    summary.update({
        "attitude_dip_labels": sum(
            item.get("attitude_dip_label", 0) for item in result.reports
        ),
        "attitude_dip_label_offsets": sum(
            item.get("attitude_dip_label_offset", 0) for item in result.reports
        ),
        "attitude_dip_label_collisions": sum(
            item.get("attitude_dip_label_collision", 0) for item in result.reports
        ),
        "native_text_collisions": sum(
            item.get("native_text_collision", 0) for item in result.reports
        ),
        "polygon_label_offsets": sum(
            item.get("label_offset", 0) for item in result.reports
        ),
        "polygon_label_collisions_skipped": sum(
            item.get("label_skipped_collision", 0) for item in result.reports
        ),
        "text_overlap_count": collision_audit["overlap_count"],
        "geopdf_actual_scale_x": actual_scale_x,
        "geopdf_actual_scale_y": actual_scale_y,
        "geopdf_image_objects": (
            geopdf_info["readback"]["image_xobject_count"] if geopdf_info else None
        ),
        "geopdf_vector_drawings": (
            geopdf_info["readback"]["drawing_count"] if geopdf_info else None
        ),
        "geopdf_text_characters": (
            geopdf_info["readback"]["text_character_count"] if geopdf_info else None
        ),
    })
    public_reports = []
    for report in result.reports:
        public_report = dict(report)
        if "source" in public_report:
            public_report["source"] = Path(public_report["source"]).name
        public_reports.append(public_report)
    report_path = args.output_dir / "jwd_render_reports.json"
    report_path.write_text(
        json.dumps(
            {
                "summary": summary,
                "sources": source_manifest,
                "rendering": {
                    **projection_report,
                    "geopdf": geopdf_info,
                    "text_collision_audit": {
                        key: collision_audit[key]
                        for key in ("checked_text_artists", "buffer_pt", "overlap_count")
                    },
                },
                "layers": public_reports,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("OUTPUT_PNG", png)
    print("OUTPUT_SVG", svg)
    if geopdf_info is not None:
        print("OUTPUT_GEOPDF", geopdf_info["output"])
    print("OUTPUT_REPORTS", report_path)
    print("OUTPUT_TEXT_COLLISIONS", args.output_dir / "jwd_text_collisions.json")


if __name__ == "__main__":
    main()
