#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Convert the public USGS Conejo Well ARC/INFO database to MapGIS.

Source: USGS Open-File Report 01-031. The source data are not synthetic and
retain the original USGS attribution and access disclaimer.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

import geopandas as gpd
import pyogrio
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from examples.e00_fast import read_coverage, read_info_tables  # noqa: E402
from examples.generate_synthetic_geology import _line_record, _point_record, _polygon_record  # noqa: E402
from examples.render_bundled_jwd import summarise  # noqa: E402
from examples.usgs_conejo_symbols import (  # noqa: E402
    LEFT_SLIP_PEN_WIDTH_MM,
    LEFT_SLIP_SIZE_MM,
    LEFT_SLIP_SYMBOL,
    fault_geometries,
    nearest_fault_angle,
)
from pymapgis import GraphicLibraries, GraphicRenderer, Writer  # noqa: E402
from pymapgis.testing import slib_path  # noqa: E402

SOURCE_URL = "https://pubs.usgs.gov/of/2001/of01-031/"
ACCESS_NOTE = (
    "USGS metadata: Access_Constraints=None; Metadata_Access_Constraints=none; "
    "Metadata_Use_Constraints=none. USGS provides the data as is, without warranty."
)
RESOLUTION_NOTE = (
    "Do not enlarge the DOQQ-based geologic data beyond 1:12,000 or the "
    "1:24,000 topographic base beyond its source resolution. Faults are not "
    "a substitute for site-specific fault-rupture hazard evaluations."
)
TARGET_CRS = "EPSG:32611"
LAYER_NAMES = (
    "cwell_geo.WP", "cwell_geo.WL", "cwell_dk.WL", "cwell_str.WT",
    "cwell_str_lab.WT", "cwell_orn.WT", "cwell_ldr.WL", "cwell_lab.WT",
)


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rgb(hex_value):
    value = hex_value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


UNIT_COLOR_HEX = {
    601: "#ffffd7", 602: "#ffffb2", 904: "#f29933", 689: "#ccff66",
    534: "#99ffff", 1226: "#ff7fe5", 1096: "#e5e5e5",
}
UNIT_COLOR_RGB = {number: _rgb(value) for number, value in UNIT_COLOR_HEX.items()}


def unit_color(label):
    """Assign a declared age-aware thematic colour, not the original USGS shade."""
    text = str(label or "").strip()
    if text.startswith(("Pr", "X", "Z")):
        return 1096
    if text.startswith("Q"):
        return 602
    if text.startswith("TJ"):
        return 534
    if text.startswith("Tr"):
        return 1226
    if text.startswith("T"):
        return 904
    if text.startswith("K"):
        return 689
    if text.startswith("J"):
        return 534
    if text.startswith("P"):
        return 1226
    return 601


def _read(source, coverage, layer):
    path = (Path(source) / coverage).resolve()
    records = read_coverage(str(path))[layer]
    # read_info only parses the header and avoids GDAL's slow full-coverage
    # geometry assembly.  The source geometries and INFO fields come directly
    # from the strict E00 reader above.
    crs = pyogrio.read_info(path, layer=layer)["crs"]
    frame = gpd.GeoDataFrame(records, geometry="geometry", crs=crs)
    return frame.to_crs(TARGET_CRS)


def _polygon_class(geometry):
    """Match MapGIS's native fresh 2×ring-count polygon class."""
    parts = [geometry] if geometry.geom_type == "Polygon" else list(geometry.geoms)
    return 2 * sum(1 + len(part.interiors) for part in parts)


def _offset_point(point, azimuth, distance_m):
    angle = math.radians(float(azimuth))
    return Point(
        point.x + math.sin(angle) * distance_m,
        point.y + math.cos(angle) * distance_m,
    )


def load_layers(source):
    """Read the five source coverages and their native attributes."""
    source = Path(source)
    layers = {}
    line_relations = read_info_tables(source / "lines.rel.e00")["LINES.REL"]
    line_definitions = {row["L-TAG"]: row["L-EXP"] for row in line_relations}

    polygon = _read(source, "cwell_geo.e00", "PAL")
    records = []
    for row in polygon.to_dict("records"):
        record = _polygon_record(
            row["geometry"],
            row["LABL"],
            unit_color(row["LABL"]),
        )
        record.update({
            "class": _polygon_class(row["geometry"]),
            "pattern_color": 0,
            "layer": 0,
            "LABL": row["LABL"],
            "PLABL": row["PLABL"],
            "SHDPS": row["SHDPS"],
            "SHDFIL": row["SHDFIL"],
            "NAME": row["NAME"],
            "source_id": int(row["CWELL_GEO-ID"]),
        })
        records.append(record)
    layers["cwell_geo.WP"] = _frame(records, "cwell_geo.WP", "wp")

    contact = _read(source, "cwell_geo.e00", "ARC")
    records = []
    for row in contact.to_dict("records"):
        tag = str(row["L-TAG"])
        definition = line_definitions[tag]
        is_fault = tag.startswith("F")
        is_dashed = any(token in definition for token in (
            "inferred", "questionable", "may not meet map accuracy standard",
        ))
        records.append(_line_record(
            row["geometry"],
            style=2 if is_dashed else 1,
            color=175 if is_fault else 1,
            width=0.18 if is_fault else 0.08,
            L_TAG=tag,
            L_SYMB=row["L-SYMB"],
            L_DEFINITION=definition,
            FEATURE_TYPE="fault" if is_fault else (
                "map boundary" if tag == "CL1" else "geological contact"
            ),
            source_id=int(row["CWELL_GEO-ID"]),
        ))
    layers["cwell_geo.WL"] = _frame(records, "cwell_geo.WL", "wl")

    dikes = _read(source, "cwell_dk.e00", "ARC")
    records = []
    for row in dikes.to_dict("records"):
        records.append(_line_record(
            row["geometry"],
            style=1,
            color=175,
            width=0.16,
            LTYPE=row["LTYPE"],
            LABL=row["LABL"],
            L_SYMB=row["L-SYMB"],
            NAME=row["NAME"],
            source_id=int(row["CWELL_DK-ID"]),
        ))
    layers["cwell_dk.WL"] = _frame(records, "cwell_dk.WL", "wl")

    structure = _read(source, "cwell_str.e00", "LAB")
    records = []
    annotations = []
    for row in structure.to_dict("records"):
        strike = float(row["P-STRIKE"])
        dip = float(row["P-DIP"])
        dipdir = float(row["P-DIPDIR"])
        plunge = float(row["P-PLUNGE"])
        bearing = float(row["P-BEARING"])
        planar = strike != 0 or dip != 0
        if planar and dipdir < 0:
            dipdir = (strike + 90) % 360
        value = dip if planar else plunge
        record = _point_record(
            row["geometry"],
            symbol=1245 if planar else 1281,
            height=5 if planar else 4,
            width=5 if planar else 4,
            angle=strike if planar else bearing,
            category="产状" if planar else "线理",
            text=str(int(value)) if value.is_integer() else str(value),
            P_TAG=row["P-TAG"],
            P_SYMB=row["P-SYMB"],
            P_STRIKE=strike,
            P_DIP=dip,
            P_DIPDIR=dipdir,
            P_PLUNGE=plunge,
            P_BEARING=bearing,
            P_SOURCE=row["P-SOURCE"],
            PTTYPE=row["PTTYPE"],
            source_id=int(row["CWELL_STR-ID"]),
        )
        if planar:
            record.update({"GZBBAB": strike, "GZBBAC": dipdir, "GZBBAD": dip})
        annotation = record.copy()
        annotation.update({
            "point_type": 0,
            "symbol_no": 0,
            "height": 6.0,
            "width": 6.0,
            "angle": 0.0,
            "annotation_flag": 65538,
            "geometry": _offset_point(
                row["geometry"], dipdir if planar else bearing, 5.0 * 24000 / 1000
            ),
        })
        annotations.append(annotation)
        # MapGIS subgraph records do not emit CHFCED in the renderer.  Keep
        # the numeric value only in the separate point-type-0 annotation layer.
        record["CHFCED"] = ""
        records.append(record)
    layers["cwell_str.WT"] = _frame(records, "cwell_str.WT", "wt")
    layers["cwell_str_lab.WT"] = _frame(annotations, "cwell_str_lab.WT", "wt")

    ornament = _read(source, "cwell_orn.e00", "LAB")
    records = []
    faults = fault_geometries(layers["cwell_geo.WL"])
    for row in ornament.to_dict("records"):
        angle = nearest_fault_angle(row["geometry"], faults)
        # USGS P-SYMB 192 is one left-slip marker composed of two opposing
        # half-arrows. Store both SLIB 239 glyphs explicitly so MapGIS native
        # display and GraphicRenderer produce the same pair.
        for offset in (0.0, 180.0):
            records.append(_point_record(
                row["geometry"],
                symbol=LEFT_SLIP_SYMBOL,
                height=LEFT_SLIP_SIZE_MM,
                width=LEFT_SLIP_SIZE_MM,
                angle=angle + offset,
                color=1,
                pen_width=LEFT_SLIP_PEN_WIDTH_MM,
                category="断层辅助点",
                annotation_flag=65540,
                P_TAG=row["P-TAG"],
                P_SYMB=row["P-SYMB"],
                PTTYPE=row["PTTYPE"],
                source_id=int(row["CWELL_ORN-ID"]),
            ))
    layers["cwell_orn.WT"] = _frame(records, "cwell_orn.WT", "wt")

    leaders = _read(source, "cwell_ldr.e00", "ARC")
    records = []
    for row in leaders.to_dict("records"):
        records.append(_line_record(
            row["geometry"], style=1, width=0.05,
            L_SYMB=row["L-SYMB"], source_id=int(row["CWELL_LDR-ID"]),
        ))
    layers["cwell_ldr.WL"] = _frame(records, "cwell_ldr.WL", "wl")

    labels = _read(source, "cwell_geo.e00", "LAB")
    records = []
    for row in labels.to_dict("records"):
        records.append(_point_record(
            row["geometry"],
            height=3.0,
            width=3.0,
            angle=0,
            category="代号",
            annotation_flag=65537,
            text=str(row["LABL"]),
            LABL=row["LABL"],
            PLABL=row["PLABL"],
            SHDPS=row["SHDPS"],
            SHDFIL=row["SHDFIL"],
            NAME=row["NAME"],
            source_id=int(row["CWELL_GEO-ID"]),
        ))
    layers["cwell_lab.WT"] = _frame(records, "cwell_lab.WT", "wt")
    return layers


def _frame(records, source, kind):
    layer = gpd.GeoDataFrame(records, crs=TARGET_CRS)
    layer.attrs["source"] = source
    layer.attrs["kind"] = kind
    return layer


def write_layers(layers, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, layer in layers.items():
        Writer(layer, make_valid=True, map_scale=24000).to_file(output_dir / name)


def read_layers(output_dir):
    layers = {}
    for name in LAYER_NAMES:
        path = Path(output_dir) / name
        layer = GraphicRenderer.read_layer(path)
        # Writer encodes UTM input as Gauss-Kruger k=1 because MapGIS 6x has
        # no UTM scale-factor field. Restore UTM after the native round-trip
        # so rendering and source comparisons use one declared CRS.
        if layer.crs not in (None, ""):
            layer = layer.to_crs(TARGET_CRS)
        layer.attrs["source"] = name
        layer.attrs["kind"] = path.suffix.lower().lstrip(".")
        layers[name] = layer
    return layers


def select_overview_labels(polygons, labels, max_labels=650):
    """Select legible overview labels without changing the native WT layer.

    The largest polygon of every unit is selected first, followed by the
    largest remaining polygons.  This guarantees unit coverage while avoiding
    thousands of unreadable annotations on small slivers.
    """
    areas = dict(zip(polygons["source_id"], polygons.geometry.area))
    ranked = labels.copy()
    ranked["_polygon_area"] = ranked["source_id"].map(areas)
    if ranked["_polygon_area"].isna().any():
        raise ValueError("Every label must join to its source polygon")
    ranked = ranked.sort_values("_polygon_area", ascending=False)
    representative = ranked.groupby("LABL", sort=False).head(1)
    selected = representative
    if len(selected) < min(max_labels, len(ranked)):
        remainder = ranked.loc[~ranked.index.isin(selected.index)]
        selected = ranked.loc[
            list(selected.index)
            + list(remainder.head(min(max_labels, len(ranked)) - len(selected)).index)
        ]
    result = labels.loc[selected.index].copy()
    result["height"] = 1.4
    result["width"] = 1.4
    result.attrs.update(labels.attrs)
    return result


def _draw_overview_labels(result, labels):
    """Draw whole unit codes with font-accurate, screen-space collision checks."""
    fig, ax = result.figure, result.axes
    fig.canvas.draw()
    canvas_renderer = fig.canvas.get_renderer()
    inverse = ax.transData.inverted()
    accepted = []
    accepted_units = set()
    forced = 0
    ratio = fig.dpi / 160
    offsets = (
        (0, 0), (0, 8), (0, -8), (10, 0), (-10, 0),
        (12, 8), (-12, 8), (12, -8), (-12, -8),
        (0, 16), (0, -16), (18, 0), (-18, 0),
        (20, 12), (-20, 12), (20, -12), (-20, -12),
        (0, 26), (0, -26), (28, 0), (-28, 0),
        (30, 20), (-30, 20), (30, -20), (-30, -20),
    )

    def overlap_area(a, b):
        width = max(0, min(a.x1, b.x1) - max(a.x0, b.x0))
        height = max(0, min(a.y1, b.y1) - max(a.y0, b.y0))
        return width * height

    for row in labels.to_dict("records"):
        required = row["LABL"] not in accepted_units
        point = row["geometry"]
        base = ax.transData.transform((point.x, point.y))
        artist = None
        best = None
        for dx, dy in offsets:
            x, y = inverse.transform(base + (dx * ratio, dy * ratio))
            if artist is None:
                artist = ax.text(
                    x, y, str(row["CHFCED"]),
                    fontsize=float(row["height"]) * 72 / 25.4,
                    fontfamily="DejaVu Sans", color="#111111",
                    ha="left", va="baseline", parse_math=False, zorder=30,
                )
            else:
                artist.set_position((x, y))
            bbox = artist.get_window_extent(renderer=canvas_renderer).expanded(1.04, 1.15)
            outside = (
                max(0, ax.bbox.x0 - bbox.x0) + max(0, bbox.x1 - ax.bbox.x1)
                + max(0, ax.bbox.y0 - bbox.y0) + max(0, bbox.y1 - ax.bbox.y1)
            )
            overlap = sum(overlap_area(bbox, other) for other in accepted)
            score = overlap + outside * 1000
            if best is None or score < best[0]:
                best = (score, (x, y), bbox, overlap, outside)
            if score == 0:
                break
        _score, (x, y), bbox, overlap, outside = best
        if overlap or outside:
            if not required:
                artist.remove()
                continue
            forced += 1
        artist.set_position((x, y))
        artist.set_bbox({
            "boxstyle": "round,pad=0.08", "facecolor": "white",
            "edgecolor": "none", "alpha": 0.76,
        })
        accepted.append(bbox)
        accepted_units.add(row["LABL"])
    return len(accepted), forced


def render_layers(layers, output_dir, dpi=160):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    renderer = GraphicRenderer(
        GraphicLibraries.from_directory(slib_path()),
        scale=24000,
        color_overrides=UNIT_COLOR_RGB,
        native_text_layout=False,
        polygon_labels=False,
        exclude_text_categories=("代号",),
        text_category_scales={"线理": 0.3},
        text_font_family=["Microsoft YaHei", "SimSun", "DejaVu Sans"],
        font_zh_map={1: "SimSun", 4: "SimHei"},
        font_en_map={0: "DejaVu Sans"},
    )
    ordered = [layers[name] for name in LAYER_NAMES]
    result = renderer.render(ordered, output_dir / "cwell_map.png", figsize=(12, 9), dpi=dpi)
    candidates = select_overview_labels(
        layers["cwell_geo.WP"], layers["cwell_lab.WT"]
    )
    label_count, forced = _draw_overview_labels(result, candidates)
    label_report = next(
        report for report in result.reports if report["source"] == "cwell_lab.WT"
    )
    label_report["excluded_text"] = len(layers["cwell_lab.WT"]) - label_count
    label_report["text"] = label_count
    label_report["drawn"] = label_count
    label_report["label_collisions"] = forced
    result.overview_label_count = label_count
    result.overview_label_collisions = forced
    fig, ax = result.figure, result.axes
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    handles = [
        Patch(facecolor=UNIT_COLOR_HEX[602], label="Quaternary (Q*)"),
        Patch(facecolor=UNIT_COLOR_HEX[904], label="Tertiary (T*, TK*)"),
        Patch(facecolor=UNIT_COLOR_HEX[689], label="Cretaceous (K*)"),
        Patch(facecolor=UNIT_COLOR_HEX[534], label="Jurassic / Triassic-Jurassic"),
        Patch(facecolor=UNIT_COLOR_HEX[1226], label="Triassic / Permian"),
        Patch(facecolor=UNIT_COLOR_HEX[1096], label="Proterozoic (Pr*)"),
        Patch(facecolor=UNIT_COLOR_HEX[601], label="Other / mixed age"),
        Line2D([0], [0], color="black", lw=0.8, label="Contact, located"),
        Line2D([0], [0], color="black", lw=0.8, ls="--", label="Contact, approximate/inferred"),
        Line2D([0], [0], color="red", lw=1.2, label="Fault (dash = inferred)"),
        Line2D([0], [0], color="red", lw=1.8, label="Dike"),
    ]
    fig.legend(handles=handles, loc="center left", bbox_to_anchor=(0.79, 0.5),
               title="Age-based thematic colours", fontsize=8, title_fontsize=9,
               frameon=True, framealpha=0.9)
    fig.text(0.5, 0.96, "USGS CONEJO WELL 7.5-MINUTE QUADRANGLE", ha="center", va="top",
             fontsize=15, fontweight="bold")
    fig.text(0.5, 0.925, "USGS OFR 01-031 | Native MapGIS conversion | not synthetic",
             ha="center", va="top", fontsize=9, color="#555555")
    fig.subplots_adjust(left=0.03, right=0.76, top=0.88, bottom=0.06)
    xmin, ymin, xmax, ymax = result.bounds
    ax.plot([xmin + 100, xmin + 1100], [ymin + 100, ymin + 100], color="black", lw=2)
    ax.text(xmin + 600, ymin + 220, "1 km", ha="center", fontsize=8)
    ax.text(xmax - 150, ymax - 150, "N\n↑", ha="center", va="center", fontsize=13)
    fig.savefig(output_dir / "cwell_map.png", dpi=dpi)
    fig.savefig(output_dir / "cwell_map.pdf", format="pdf")
    fig.savefig(output_dir / "cwell_map.svg", format="svg")
    fig.clear()
    return result


def write_metadata(output_dir, layers, reports, source_dir):
    output_dir = Path(output_dir)
    source_dir = Path(source_dir)
    with (output_dir / "cwell_units.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "LABL", "PLABL", "NAME", "thematic_fill_color", "thematic_rgb",
            "SHDPS", "SHDFIL",
        ])
        seen = set()
        for row in layers["cwell_geo.WP"].itertuples():
            if row.LABL in seen:
                continue
            seen.add(row.LABL)
            color = unit_color(row.LABL)
            writer.writerow([
                row.LABL, row.PLABL, row.NAME, color, UNIT_COLOR_HEX[color],
                row.SHDPS, row.SHDFIL,
            ])

    input_names = (
        "cwell_geo.e00", "cwell_dk.e00", "cwell_str.e00", "cwell_orn.e00",
        "cwell_ldr.e00", "lines.rel.e00",
    )
    archive = ROOT / "work_usgs/cwell.tar.gz"
    map_pdf = ROOT / "work_usgs/cwell_map.pdf"
    summary = summarise(reports)
    overview_candidates = select_overview_labels(
        layers["cwell_geo.WP"], layers["cwell_lab.WT"]
    )
    label_report = next(
        report for report in reports if report["source"] == "cwell_lab.WT"
    )
    overview_label_count = label_report.get("drawn", 0)
    overview_label_collisions = label_report.get("label_collisions", 0)
    manifest = {
        "source": {
            "title": "Geologic Map and Digital Database of the Conejo Well 7.5 minute Quadrangle",
            "report": "USGS Open-File Report 01-031",
            "url": SOURCE_URL,
            "access": ACCESS_NOTE,
            "resolution_and_use": RESOLUTION_NOTE,
            "archive_sha256": _sha256(archive) if archive.is_file() else None,
            "map_pdf_sha256": _sha256(map_pdf) if map_pdf.is_file() else None,
            "input_sha256": {
                name: _sha256(source_dir / name) for name in input_names
            },
        },
        "source_crs": "NAD27 / Polyconic (original PRJ section)",
        "target_crs": TARGET_CRS,
        "mapgis_storage_crs": (
            "WGS84 Gauss-Kruger, central meridian -117, k=1; Writer converts "
            "UTM because MapGIS 6x cannot encode the UTM scale factor"
        ),
        "render_scale": 24000,
        "render_pipeline": {
            "renderer": "mapgis2shp / pymapgis.GraphicRenderer",
            "native_mapgis_roundtrip": True,
            "slib_directory": str(slib_path()),
            "library_sha256": {
                name: _sha256(Path(slib_path()) / name)
                for name in (
                    "Subgraph.lib", "LINESTY.lib", "Fillgrph.lib",
                    "Colorlib.lib", "Pcolor.lib",
                )
            },
        },
        "reader": "Strict direct ARC/PAL/LAB/IFO E00 parser; no geometry simplification",
        "layers": {name: len(layer) for name, layer in layers.items()},
        "geologic_unit_count": layers["cwell_geo.WP"]["LABL"].nunique(),
        "source_label_count": len(layers["cwell_lab.WT"]),
        "overview_label_count": overview_label_count,
        "overview_label_unit_coverage": (
            overview_candidates["LABL"].nunique() if overview_label_count else 0
        ),
        "overview_label_collisions": overview_label_collisions,
        "attitude_annotation_count": len(layers["cwell_str_lab.WT"]),
        "planar_attitudes": int((layers["cwell_str.WT"]["CHFCEC"] == "产状").sum()),
        "linear_attitudes": int((layers["cwell_str.WT"]["CHFCEC"] == "线理").sum()),
        "thematic_colors": UNIT_COLOR_HEX,
        "summary": summary,
        "note": (
            "Native USGS data, not synthetic. Original converted-layer attributes "
            "and USGS disclaimers are retained. Fill colours are declared "
            "age-based thematic colours, not recovered USGS plot shades."
        ),
    }
    (output_dir / "conversion_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    document_dir = output_dir / "source_documents"
    document_dir.mkdir(parents=True, exist_ok=True)
    documents = {
        source_dir / "cwell_met.txt": "cwell_met.txt",
        source_dir / "cwell_readme.txt": "cwell_readme.txt",
        map_pdf: "cwell_map.pdf",
        ROOT / "work_usgs/cwell_dmu.pdf": "cwell_dmu.pdf",
    }
    for source, name in documents.items():
        if source.is_file():
            shutil.copy2(source, document_dir / name)

    layer_rows = "\n".join(
        f"| `{name}` | {len(layer)} |" for name, layer in layers.items()
    )
    notes = f"""# USGS Conejo Well → MapGIS 转换说明

## 数据来源

- USGS Open-File Report **01-031**，Conejo Well 7.5 分钟图幅。
- 发布页：{SOURCE_URL}
- 本成果使用真实 USGS ARC/INFO 矢量，**不是仿真地质图**。
- 原图、说明书、元数据和 readme 保存在 `source_documents/`；
  原始文件 SHA-256 见 `conversion_manifest.json`。

## 原生 MapGIS 图层

| 文件 | 要素数 |
|---|---:|
{layer_rows}

地质面保留 `LABL/PLABL/SHDPS/SHDFIL/NAME`，界线保留 `L-TAG/L-SYMB`
及 USGS 字典释义，构造点保留走向、倾角、倾向、倾伏角和方位等字段。
共 {manifest['geologic_unit_count']} 种单元代号，完整表见 `cwell_units.csv`。

## 转换与渲染

1. 直接解析未压缩 E00 的 ARC、PAL、LAB 和 IFO 固定宽度记录；不抽稀几何。
2. 从 NAD27 Polyconic 投影到 **EPSG:32611 (WGS84 UTM 11N)**。
3. 用 `pymapgis.Writer` 写出 MapGIS 6.x WT/WL/WP，再重新读取二进制成果。
   MapGIS 6.x 无法存储 UTM 的 0.9996 比例因子，因此 Writer 在文件内使用
   中央经线 −117°、k=1 的 WGS84 Gauss–Krüger；回读后恢复 EPSG:32611
   再渲染和比较，避免把 UTM 坐标误标为 k=1 或重复投影。
4. 用原图形库渲染 PNG、PDF、SVG，显示比例尺为 **1:24,000**。
   本机使用 `D:/SLIB/SLIB` 的 `Subgraph.lib`、`LINESTY.lib`、`Fillgrph.lib`、
   `Colorlib.lib`、`Pcolor.lib`，由 `mapgis2shp.GraphicRenderer` 解析渲染；
   不是从 E00 内存数据绕过 MapGIS 直接出图。代号仅在渲染结果上做字体
   边界框布局，不改变矢量几何或图形库配色。

平面产状 {manifest['planar_attitudes']} 个，线理 {manifest['linear_attitudes']} 个；
二者分别使用 `P-DIP/P-STRIKE/P-DIPDIR` 与 `P-PLUNGE/P-BEARING`，
没有把线理误作 0° 平面产状。符号位于 `cwell_str.WT`，全部
{manifest['attitude_annotation_count']} 个倾角/倾伏角数字位于独立的
`cwell_str_lab.WT`，按倾向或线理方位偏移，避免被符号记录吞掉或压住符号。

## 样式边界

- 填充色是明确声明的**按时代分类 MapGIS 专题色**，不是从 USGS PDF
  反推的原图色；原始 shade 字段未丢失。
- 单元注记由原始 LAB 点及其 PAT 属性生成；显示文本使用完整标准代号
  `LABL`。`PLABL` 中代表 GeoAge 字体的 `<`（Proterozoic）和 `^`（Triassic）
  控制字符只作为原属性保留，不再误当普通显示文本；TX7 未另建独立图层。
  原生 WT 完整保留 {manifest['source_label_count']} 个注记；总览图按真实字体
  边界框和防碰撞结果绘制 {manifest['overview_label_count']} 个代号，并保证
  {manifest['overview_label_unit_coverage']} 类单元全部至少出现一次。透明白底
  用于隔开地质界线，未显示的注记仍在 `vectors/cwell_lab.WT` 中。
- RPL 区域复合拓扑未作为额外叠加面输出，避免重复覆盖基本地质面。
- MapGIS 点符号为转换示意映射，USGS 原 `P-SYMB` 保留，未声称逐符号等效。

## 使用限制

{RESOLUTION_NOTE}

{ACCESS_NOTE}

## 自动核验

```json
{json.dumps(summary, ensure_ascii=False, indent=2)}
```
"""
    (output_dir / "CONVERSION_NOTES.md").write_text(notes, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("work_usgs/e00/tempfiles"))
    parser.add_argument("--output-dir", type=Path, default=Path("output/usgs_conejo"))
    parser.add_argument("--dpi", type=int, default=160)
    args = parser.parse_args()

    layers = load_layers(args.source)
    write_layers(layers, args.output_dir / "vectors")
    native_layers = read_layers(args.output_dir / "vectors")
    result = render_layers(native_layers, args.output_dir, dpi=args.dpi)
    write_metadata(args.output_dir, layers, result.reports, args.source)
    print(json.dumps({"output_dir": str(args.output_dir),
                      "summary": summarise(result.reports)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
