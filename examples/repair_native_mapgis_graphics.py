#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Repair display parameters in MapGIS-produced WT/WL/WP files in place.

The MapGIS SHP importer preserves DBF attributes but assigns default native
graphics.  This tool copies the native files and patches only the graphic
parameter records (and WT size boxes), leaving geometry, attribute tables,
polygon ring pointers and every unrelated byte unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.convert_usgs_conejo import LAYER_NAMES, TARGET_CRS, render_layers  # noqa: E402
from examples.export_usgs_shapefile import FIELD_ALIASES, GAUSS_KRUGER_CRS  # noqa: E402
from examples.render_bundled_jwd import summarise  # noqa: E402
from pymapgis import Reader  # noqa: E402

NATIVE_FILES = {
    "cwell_geo.WP": ("CWELL_GEO_WP.WP", "cwell_geo_wp.shp"),
    "cwell_geo.WL": ("CWELL_GEO_WL.WL", "cwell_geo_wl.shp"),
    "cwell_dk.WL": ("CWELL_DK_WL.WL", "cwell_dk_wl.shp"),
    "cwell_str.WT": ("CWELL_STR_WT.WT", "cwell_str_wt.shp"),
    "cwell_str_lab.WT": ("CWELL_STR_LAB_WT.WT", "cwell_str_lab_wt.shp"),
    "cwell_orn.WT": ("CWELL_ORN_WT.WT", "cwell_orn_wt.shp"),
    "cwell_ldr.WL": ("CWELL_LDR_WL.WL", "cwell_ldr_wl.shp"),
    "cwell_lab.WT": ("CWELL_LAB_WT.WT", "cwell_lab_wt.shp"),
}


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _header(data, index):
    table = struct.unpack_from("<i", data, 12)[0]
    return struct.unpack_from("<ii", data, table + index * 10)


def _value(row, name, default=0):
    value = row.get(FIELD_ALIASES.get(name, name), default)
    return default if value is None else value


def _int(row, name, default=0):
    value = _value(row, name, default)
    return default if not math.isfinite(float(value)) else int(value)


def _float(row, name, default=0.0):
    value = _value(row, name, default)
    return default if not math.isfinite(float(value)) else float(value)


def _aligned_source(native_path, shp_path):
    native = Reader(native_path, read_graphic_params=False).geodataframe
    source = gpd.read_file(shp_path, encoding="GBK", engine="pyogrio")
    native_ids = [int(value) for value in native["source_id"]]
    source_ids = [int(value) for value in source["source_id"]]
    if len(set(source_ids)) != len(source_ids) or set(native_ids) != set(source_ids):
        raise ValueError(f"source_id mismatch: {native_path.name} versus {shp_path.name}")
    if native_ids != source_ids:
        source = source.set_index("source_id").loc[native_ids].reset_index()
    for left, right in zip(native.geometry, source.geometry):
        if left.geom_type in {"Polygon", "MultiPolygon"}:
            equal = left.hausdorff_distance(right) < 1e-6
        else:
            equal = left.equals_exact(right, 1e-7)
        if not equal:
            raise ValueError(f"native/SHP geometry mismatch in {native_path.name}")
    return source.to_dict("records")


def _ranges(positions):
    if not positions:
        return []
    result = []
    start = previous = positions[0]
    for position in positions[1:]:
        if position != previous + 1:
            result.append([start, previous + 1])
            start = position
        previous = position
    result.append([start, previous + 1])
    return result


def _patch_wt(data, records, report):
    start, volume = _header(data, 0)
    box_start, box_volume = _header(data, 3)
    count = len(records)
    assert volume == (count + 1) * 93, (volume, count)
    assert box_volume == (count + 1) * 32, (box_volume, count)
    report["allowed"].extend([(start, start + volume), (box_start, box_start + box_volume)])
    for i, row in enumerate(records):
        offset = start + (i + 1) * 93
        point_type = _int(row, "point_type", 1)
        height = _float(row, "height", 0.1)
        width = _float(row, "width", 0.1)
        data[offset + 31] = point_type
        if point_type == 1:
            struct.pack_into("<h", data, offset + 33, _int(row, "symbol_no", 1))
            struct.pack_into("<f", data, offset + 37, height)
            struct.pack_into("<f", data, offset + 41, width)
            struct.pack_into("<f", data, offset + 49, _float(row, "pen_width", 0.1))
        else:
            struct.pack_into("<f", data, offset + 33, height)
            struct.pack_into("<f", data, offset + 37, width)
            struct.pack_into("<f", data, offset + 41, _float(row, "spacing"))
            data[offset + 49] = _int(row, "font_zh", 1) & 0xFF
            data[offset + 51] = _int(row, "font_en") & 0xFF
            data[offset + 53] = _int(row, "font_style") & 0xFF
        struct.pack_into("<f", data, offset + 45, _float(row, "angle"))
        data[offset + 75] = _int(row, "color", 6) & 0xFF
        data[offset + 83] = _int(row, "layer") & 0xFF
        x, y = struct.unpack_from("<dd", data, offset + 7)
        struct.pack_into(
            "<4d", data, box_start + (i + 1) * 32,
            x - width, y - height, x + width, y + height,
        )


def _patch_wl(data, records, report):
    start, volume = _header(data, 0)
    assert volume == (len(records) + 1) * 57, (volume, len(records))
    report["allowed"].append((start, start + volume))
    for i, row in enumerate(records):
        offset = start + (i + 1) * 57
        struct.pack_into("<h", data, offset + 22, _int(row, "linetype", 1))
        data[offset + 24] = _int(row, "aux_linetype") & 0xFF
        data[offset + 25] = _int(row, "aux_flag", 1) & 0xFF
        struct.pack_into("<h", data, offset + 26, _int(row, "color", 1))
        struct.pack_into("<f", data, offset + 30, _float(row, "width", 0.05))
        struct.pack_into("<f", data, offset + 35, _float(row, "x_coef", 1.0))
        struct.pack_into("<f", data, offset + 39, _float(row, "y_coef", 1.0))
        struct.pack_into("<h", data, offset + 43, _int(row, "aux_color"))
        data[offset + 47] = _int(row, "layer") & 0xFF
        data[offset + 48] = _int(row, "transparent") & 0xFF


def _patch_wp(data, records, report):
    start, volume = _header(data, 8)
    assert volume == (len(records) + 1) * 40, (volume, len(records))
    report["allowed"].append((start, start + volume))
    for i, row in enumerate(records):
        offset = start + (i + 1) * 40
        # Preserve MapGIS's native class, pattern_color and layer.  Changing
        # them to 1 suppressed/mis-rendered native fills in user acceptance.
        struct.pack_into("<H", data, offset + 9, _int(row, "fill_color"))
        struct.pack_into("<H", data, offset + 13, _int(row, "pattern"))
        for name, byte_offset in (("pattern_height", 17), ("pattern_width", 21)):
            high = struct.unpack("<I", struct.pack("<f", _float(row, name)))[0] >> 16
            struct.pack_into("<H", data, offset + byte_offset, high)
        # field5/6/7 at offsets 5/6/7 are native ring pointers: do not touch.


def _verify_params(path, records, kind):
    reader = Reader(path, read_graphic_params=True)
    params = getattr(
        reader, {"wt": "point_params", "wl": "line_params", "wp": "polygon_params"}[kind]
    )
    assert len(params) == len(records)
    for i, row in enumerate(records):
        actual = params.iloc[i]
        if kind == "wl":
            names = ("linetype", "aux_linetype", "aux_flag", "color", "width",
                     "x_coef", "y_coef", "aux_color", "layer", "transparent")
        elif kind == "wp":
            names = ("fill_color", "pattern", "pattern_height", "pattern_width")
        else:
            names = ["point_type", "symbol_no", "height", "width", "angle", "color", "layer"]
            if _int(row, "point_type", 1) == 1:
                names.append("pen_width")
            else:
                names.extend(("spacing", "font_zh", "font_en", "font_style"))
        for name in names:
            expected = _float(row, name)
            value = float(actual[name])
            assert math.isclose(value, expected, rel_tol=1e-6, abs_tol=1e-6), (
                path.name, i, name, value, expected
            )


def repair_file(native_path, shp_path, output_path):
    native_path, output_path = Path(native_path), Path(output_path)
    records = _aligned_source(native_path, shp_path)
    kind = native_path.suffix.lower().lstrip(".")
    original = native_path.read_bytes()
    data = bytearray(original)
    report = {"allowed": []}
    {"wt": _patch_wt, "wl": _patch_wl, "wp": _patch_wp}[kind](data, records, report)
    changed = [i for i, (left, right) in enumerate(zip(original, data)) if left != right]
    assert changed, f"no graphic parameters changed: {native_path.name}"
    assert all(any(a <= i < b for a, b in report["allowed"]) for i in changed)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    _verify_params(output_path, records, kind)
    return {
        "file": output_path.name,
        "features": len(records),
        "original_sha256": hashlib.sha256(original).hexdigest(),
        "repaired_sha256": _sha256(output_path),
        "changed_bytes": len(changed),
        "changed_ranges": _ranges(changed),
        "unrelated_bytes_unchanged": True,
        "native_params_verified": True,
    }


def read_repaired_layers(vector_dir, source_dir, source_crs=GAUSS_KRUGER_CRS):
    layers = {}
    for name in LAYER_NAMES:
        native_name, shp_name = NATIVE_FILES[name]
        path = Path(vector_dir) / native_name
        native = Reader(path, read_graphic_params=False).geodataframe
        # MapGIS's fixed-width attribute records pad text to 80 bytes and may
        # change the encoding of Chinese category fields.  Use the aligned SHP
        # text for display, while retaining the native geometry byte-for-byte.
        records = _aligned_source(path, Path(source_dir) / shp_name)
        frame = gpd.GeoDataFrame(
            records, geometry=native.geometry.to_numpy(), crs=source_crs
        )
        reader = Reader(path, read_graphic_params=True)
        params = getattr(
            reader,
            {
                "wt": "point_params", "wl": "line_params", "wp": "polygon_params"
            }[path.suffix.lower()[1:]],
        )
        for column in params.columns:
            if column not in {"field5", "field6", "field7"}:
                frame[column] = params[column].to_numpy()
        frame = frame.to_crs(TARGET_CRS)
        frame.attrs["source"] = name
        frame.attrs["kind"] = path.suffix.lower().lstrip(".")
        layers[name] = frame
    return layers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path("output/usgs_conejo/native_mapgis_repaired"),
    )
    parser.add_argument("--render", action="store_true")
    parser.add_argument(
        "--source-crs", choices=("utm11", "gauss_kruger_117w"),
        default="gauss_kruger_117w",
    )
    args = parser.parse_args()

    reports = []
    for name in LAYER_NAMES:
        native_name, shp_name = NATIVE_FILES[name]
        reports.append(repair_file(
            args.input_dir / native_name,
            args.input_dir / shp_name,
            args.output_dir / "vectors" / native_name,
        ))
    manifest = {
        "method": "Copy MapGIS-produced native files; patch graphic parameters only",
        "input_dir": str(args.input_dir),
        "geometry_and_attributes_rewritten": False,
        "native_crs_note": (
            "Reader did not detect a valid native CRS. Rendering assigns the "
            f"source SHP CRS explicitly: {args.source_crs}."
        ),
        "display_text_source": "Aligned source SHP text; native geometry and graphics",
        "reports": reports,
    }
    if args.render:
        layers = read_repaired_layers(
            args.output_dir / "vectors", args.input_dir,
            source_crs=TARGET_CRS if args.source_crs == "utm11" else GAUSS_KRUGER_CRS,
        )
        result = render_layers(layers, args.output_dir, dpi=160)
        manifest["render_summary"] = summarise(result.reports)
        manifest["overview_labels"] = result.overview_label_count
    (args.output_dir / "repair_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
