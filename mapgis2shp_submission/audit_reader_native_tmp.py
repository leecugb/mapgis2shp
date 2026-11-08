"""Audit pymapgis Reader against native MapGIS text and SHP exports in F:/tmp."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import struct
from collections import Counter
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.validation import explain_validity

from pymapgis import Reader
from pymapgis.reader import _read_polygon_arcs, _read_topology_table

ROOT = Path("F:/tmp")
OUT = Path(__file__).resolve().parent / "reader_native_tmp_audit"
GROUPS = {
    "LDLYAAI002": "WT",
    "LDZOFBA002": "WL",
    "LDZOFBB001": "WP",
    "LDZOFBB004": "WP",
    "LDZOFBB099": "WT",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_default(value):
    if isinstance(value, np.generic):
        return value.item()
    return str(value)


def scalar(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        value = value.item()
    return value


def parts(geom):
    if geom is None:
        return 0
    return len(geom.geoms) if geom.geom_type.startswith("Multi") else 1


def text_rows(path):
    lines = path.read_text(encoding="gbk").splitlines()
    return lines[0], int(lines[1]), [line for line in lines[2:] if line.strip()]


def parse_wat(path):
    magic, count, lines = text_rows(path)
    if magic != "WMAP9022":
        raise ValueError(f"Unexpected WAT magic {magic}")
    records = []
    for line in lines:
        values = next(csv.reader([line]))
        if len(values) == 13:
            records.append({
                "xy": (float(values[0]), float(values[1])),
                "id": int(values[2]),
                "point_type": int(values[3]),
                "symbol_no": int(values[4]),
                "text": "",
                "height": float(values[5]),
                "width": float(values[6]),
                "spacing": float("nan"),
                "angle": float(values[7]),
                "font_zh": float("nan"),
                "font_en": float("nan"),
                "font_style": float("nan"),
                "pen_width": float(values[10]),
                "color": int(float(values[9])),
                "layer": int(float(values[11])),
                "transparent": int(float(values[12])),
            })
            continue
        records.append({
            "xy": (float(values[0]), float(values[1])),
            "id": int(values[2]),
            "point_type": int(float(values[3])),
            "symbol_no": 0,
            "text": values[4],
            "height": float(values[5]),
            "width": float(values[6]),
            "spacing": float(values[7]),
            "angle": float(values[8]),
            "font_zh": int(float(values[9])),
            "font_en": int(float(values[10])),
            "font_style": int(float(values[11])),
            "pen_width": float(values[12]),
            "color": int(float(values[13])),
            "layer": int(float(values[14])),
            "transparent": int(float(values[15])),
        })
    if len(records) != count:
        raise ValueError(f"WAT count mismatch: {len(records)} != {count}")
    return records


def parse_style(values):
    return {
        "linetype": int(values[0]),
        "aux_linetype": int(values[1]),
        "color": int(values[2]),
        "width": float(values[3]),
        "x_coef": float(values[4]),
        "y_coef": float(values[5]),
        "aux_color": int(values[6]),
        "layer": int(values[7]),
        "transparent": int(values[8]),
    }


def parse_wal(path):
    magic, count, lines = text_rows(path)
    if magic != "WMAP9021":
        raise ValueError(f"Unexpected WAL magic {magic}")
    records = []
    cursor = 0
    while cursor < len(lines):
        style = parse_style(next(csv.reader([lines[cursor]])))
        point_count = int(lines[cursor + 1])
        coordinates = [
            tuple(map(float, lines[cursor + 2 + i].split(",")))
            for i in range(point_count)
        ]
        tail = lines[cursor + 2 + point_count].split(",")
        records.append({
            **style,
            "xy": coordinates,
            "id": int(tail[0]),
            "metric": float(tail[1]),
        })
        cursor += point_count + 3
    if len(records) + 1 != count:
        raise ValueError(f"WAL count mismatch: {len(records) + 1} != {count}")
    return records


def parse_wap(path):
    magic, count, lines = text_rows(path)
    if magic != "WMAP9023":
        raise ValueError(f"Unexpected WAP magic {magic}")
    records = []
    cursor = 0
    while cursor < len(lines) and len(records) < count:
        try:
            style = parse_style(next(csv.reader([lines[cursor]])))
        except (IndexError, ValueError) as exc:
            raise ValueError({
                "wap_record": len(records),
                "cursor": cursor,
                "context": lines[cursor:cursor + 6],
            }) from exc
        nodes = tuple(map(int, lines[cursor + 1].split(",")))
        sides = tuple(map(int, lines[cursor + 2].split(",")))
        point_count = int(lines[cursor + 3])
        coordinates = [
            tuple(map(float, lines[cursor + 4 + i].split(",")))
            for i in range(point_count)
        ]
        tail = lines[cursor + 4 + point_count].split(",")
        records.append({
            **style,
            "nodes": nodes,
            "sides": sides,
            "xy": coordinates,
            "id": int(tail[0]),
            "metric": float(tail[1]),
        })
        cursor += point_count + 5
    if len(records) != count:
        raise ValueError(f"WAP count mismatch: {len(records)} != {count}")
    return records, lines[cursor:]


def xy_deviation(left, right):
    if len(left) != len(right):
        return {"count_mismatch": [len(left), len(right)]}
    if not left:
        return {"max": 0.0}
    array = np.abs(np.asarray(left) - np.asarray(right))
    return {"max": float(array.max()), "mean": float(array.mean())}


def close_number(left, right, tolerance=5.1e-7):
    try:
        if pd.isna(left) and pd.isna(right):
            return True
    except (TypeError, ValueError):
        pass
    if left is None or right is None:
        return left == right
    if isinstance(left, (float, int, np.number)) and isinstance(right, (float, int, np.number)):
        return math.isclose(float(left), float(right), rel_tol=1e-8, abs_tol=tolerance)
    return left == right


def raw_attribute_bytes(path, field_name, record_index):
    data = path.read_bytes()
    attr_start = struct.unpack_from("<i", data, 657 + 2 * 10)[0]
    field_count, _, record_length = struct.unpack_from("<hih", data, attr_start + 322)
    for index in range(field_count):
        raw_name, _, offset, length, _ = struct.unpack_from(
            "<20sBi2xh4xh4x", data, attr_start + 348 + index * 39
        )
        name = raw_name.split(b"\x00", 1)[0].decode("gbk")
        if name == field_name:
            start = (
                attr_start + 348 + field_count * 39
                + (record_index + 1) * record_length + offset
            )
            return data[start:start + length]
    raise KeyError(field_name)


def audit_wat(name):
    native_path = ROOT / f"{name}.WT"
    frame = Reader(str(native_path), read_graphic_params=True, read_point_params=True).geodataframe
    plain = parse_wat(ROOT / f"{name}.wat")
    shape = gpd.read_file(ROOT / f"{name}.SHP", encoding="GBK")
    geometry_errors = []
    style_errors = []
    for index, record in enumerate(plain):
        row = frame.iloc[index]
        deviation = xy_deviation([record["xy"]], [(row.geometry.x, row.geometry.y)])
        if deviation["max"] > 5.1e-7:
            geometry_errors.append({"row": index, **deviation})
        if record["id"] != row["ID"]:
            style_errors.append({
                "row": index, "field": "ID",
                "native": row["ID"], "plain": record["id"],
            })
        text_field = "CHFCED" if "CHFCED" in frame.columns else "NAME"
        if record["text"] != str(row[text_field]):
            style_errors.append({
                "row": index, "field": text_field,
                "native": row[text_field], "plain": record["text"],
            })
        for field in (
            "point_type", "symbol_no", "height", "width", "spacing", "angle", "font_zh",
            "font_en", "pen_width", "font_style", "color", "layer",
        ):
            expected = record[field]
            actual = row[field]
            if field == "pen_width" and pd.isna(actual) and expected == 0:
                continue
            if not close_number(actual, expected):
                style_errors.append({
                    "row": index, "field": field,
                    "native": actual, "plain": expected,
                })
    byte_evidence = []
    for error in style_errors:
        if error["field"] not in {"CHFCED", "NAME"}:
            continue
        index = error["row"]
        raw = raw_attribute_bytes(native_path, error["field"], index)
        byte_evidence.append({
            **error,
            "native_field_hex": raw.hex(),
            "shp_value": scalar(shape.iloc[index][error["field"]]),
            "interpretation": "binary and SHP agree; native WAT text differs",
        })
    shp_deviations = [
        index for index, (left, right) in enumerate(zip(frame.geometry, shape.geometry))
        if left.hausdorff_distance(right) > 5.1e-7
    ]
    attributes = compare_attributes(frame, shape)
    return {
        "native_features": len(frame),
        "plain_features": len(plain),
        "shp_features": len(shape),
        "plain_geometry_errors": geometry_errors[:30],
        "plain_style_errors": style_errors[:50],
        "text_byte_evidence": byte_evidence,
        "shp_geometry_errors": shp_deviations[:30],
        "shp_attribute_comparison": attributes,
        "shp_crs": str(shape.crs),
    }


def audit_wal(name):
    native_path = ROOT / f"{name}.WL"
    frame = Reader(str(native_path), read_graphic_params=True).geodataframe
    plain = parse_wal(ROOT / f"{name}.wal")
    shape = gpd.read_file(ROOT / f"{name}.SHP", encoding="GBK")
    geometry_errors = []
    style_errors = []
    for index, record in enumerate(plain):
        row = frame.iloc[index]
        deviation = xy_deviation(record["xy"], list(row.geometry.coords))
        if deviation.get("count_mismatch") or deviation["max"] > 5.1e-7:
            geometry_errors.append({"row": index, **deviation})
        if record["id"] != row["ID"]:
            style_errors.append({
                "row": index, "field": "ID",
                "native": row["ID"], "plain": record["id"],
            })
        if not close_number(row["长度"], record["metric"]):
            style_errors.append({
                "row": index, "field": "长度", "native": row["长度"], "plain": record["metric"]
            })
        for field in (
            "linetype", "aux_linetype", "color", "width", "x_coef", "y_coef",
            "aux_color", "layer", "transparent",
        ):
            if not close_number(row[field], record[field]):
                style_errors.append({
                    "row": index, "field": field,
                    "native": row[field], "plain": record[field],
                })
    shp_deviations = [
        index for index, (left, right) in enumerate(zip(frame.geometry, shape.geometry))
        if left.hausdorff_distance(right) > 5.1e-7
    ]
    attributes = compare_attributes(frame, shape)
    return {
        "native_features": len(frame),
        "plain_features": len(plain),
        "shp_features": len(shape),
        "plain_geometry_errors": geometry_errors[:30],
        "plain_style_errors": style_errors[:50],
        "shp_geometry_errors": shp_deviations[:30],
        "shp_attribute_comparison": attributes,
        "shp_crs": str(shape.crs),
    }


def raw_polygons(path):
    data = path.read_bytes()
    entries = [struct.unpack_from("<ii", data, 657 + i * 10) for i in range(16)]
    with path.open("rb") as stream:
        arcs = _read_polygon_arcs(
            stream, *entries[0], *entries[1], 1.0
        )
        topology = _read_topology_table(stream, *entries[3])
    return arcs, topology


def raw_line_style(data, index_start, index):
    start = index_start + (index + 1) * 57
    return {
        "linetype": struct.unpack_from("<h", data, start + 22)[0],
        "aux_linetype": data[start + 24],
        "color": struct.unpack_from("<h", data, start + 26)[0],
        "width": struct.unpack_from("<f", data, start + 30)[0],
        "x_coef": struct.unpack_from("<f", data, start + 35)[0],
        "y_coef": struct.unpack_from("<f", data, start + 39)[0],
        "aux_color": struct.unpack_from("<h", data, start + 43)[0],
        "layer": data[start + 47],
        "transparent": data[start + 48],
    }


def audit_wap(name):
    native_path = ROOT / f"{name}.WP"
    frame = Reader(str(native_path), read_graphic_params=True).geodataframe
    arcs, topology = raw_polygons(native_path)
    plain, trailing = parse_wap(ROOT / f"{name}.wap")
    native_bytes = native_path.read_bytes()
    index_start = struct.unpack_from("<i", native_bytes, 657)[0]
    shape = gpd.read_file(ROOT / f"{name}.SHP", encoding="GBK")
    geometry_errors = []
    style_errors = []
    topology_errors = []
    for index, record in enumerate(plain):
        deviation = xy_deviation(record["xy"], list(arcs[index].coords))
        if deviation.get("count_mismatch") or deviation["max"] > 5.1e-7:
            geometry_errors.append({"arc": index, **deviation})
        if tuple(map(int, topology[index, 2:4])) != record["sides"]:
            topology_errors.append({
                "arc": index,
                "native": list(map(int, topology[index, 2:4])),
                "plain": list(record["sides"]),
            })
        raw_style = raw_line_style(native_bytes, index_start, index)
        for field in (
            "linetype", "aux_linetype", "color", "width", "x_coef", "y_coef",
            "aux_color", "layer", "transparent",
        ):
            if not close_number(raw_style[field], record[field]):
                style_errors.append({
                    "arc": index,
                    "field": field,
                    "native": raw_style[field],
                    "plain": record[field],
                })
    shp_geometry = compare_shp_geometry(frame, shape)
    attributes = compare_attributes(frame, shape)
    return {
        "native_polygons": len(frame),
        "native_arcs": len(arcs),
        "plain_arcs": len(plain),
        "plain_trailing_lines": len(trailing),
        "plain_trailing_examples": trailing[:12],
        "shp_features": len(shape),
        "plain_arc_geometry_errors": geometry_errors[:30],
        "plain_topology_errors": topology_errors[:30],
        "plain_style_errors": style_errors[:30],
        "shp_geometry_comparison": shp_geometry,
        "shp_attribute_comparison": attributes,
        "shp_crs": str(shape.crs),
    }


def compare_shp_geometry(native, shape):
    missing = []
    deviations = []
    representation_differences = []
    for index, (left, right) in enumerate(zip(native.geometry, shape.geometry)):
        if right is None or right.is_empty:
            missing.append(index)
            continue
        distance = left.hausdorff_distance(right)
        if distance > 5.1e-7:
            deviations.append({"row": index, "hausdorff": distance})
        if parts(left) != parts(right) or left.geom_type != right.geom_type:
            representation_differences.append({
                "row": index,
                "native_type": left.geom_type,
                "shp_type": right.geom_type,
                "native_parts": parts(left),
                "shp_parts": parts(right),
                "hausdorff": distance,
            })
    return {
        "shp_empty_geometries": missing,
        "empty_geometry_examples": [
            {
                "row": index,
                "native_type": native.geometry.iloc[index].geom_type,
                "native_area": native.geometry.iloc[index].area,
                "native_valid": native.geometry.iloc[index].is_valid,
            }
            for index in missing[:10]
        ],
        "geometry_deviations": deviations[:30],
        "representation_differences": len(representation_differences),
        "representation_examples": representation_differences[:20],
        "native_invalid": int((~native.geometry.is_valid).sum()),
        "shp_invalid": int((~shape.geometry.is_valid).sum()),
        "shp_invalid_reason_categories": dict(Counter(
            explain_validity(geometry).split("[", 1)[0]
            for geometry in shape.geometry
            if geometry is not None and not geometry.is_valid
        )),
    }


def compare_attributes(native, shape):
    mismatches = []
    compared = 0
    shared = [name for name in native.columns if name in shape.columns and name != "geometry"]
    for index, (left, right) in enumerate(zip(native.iterrows(), shape.iterrows())):
        for field in shared:
            a = scalar(left[1][field])
            b = scalar(right[1][field])
            compared += 1
            if a == "":
                a = None
            if b == "":
                b = None
            if isinstance(a, str) or isinstance(b, str):
                a = a.strip() if isinstance(a, str) else a
                b = b.strip() if isinstance(b, str) else b
            if not close_number(a, b, tolerance=5.1e-7):
                mismatches.append({"row": index, "field": field, "native": a, "shp": b})
    return {
        "shared_fields": shared,
        "compared_values": compared,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:50],
    }


def inventory():
    rows = []
    for path in sorted(ROOT.iterdir()):
        if path.suffix.lower() not in {".wt", ".wl", ".wp"}:
            continue
        row = {"file": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}
        try:
            reader = Reader(str(path), read_graphic_params=True, read_point_params=True)
            frame = reader.geodataframe
            row.update({
                "kind": reader.shapeType,
                "features": len(frame),
                "invalid": int((~frame.geometry.is_valid).sum()),
                "crs": str(frame.crs),
            })
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "source": str(ROOT),
        "inventory": inventory(),
        "groups": {},
    }
    for name, kind in GROUPS.items():
        if kind == "WT":
            result = audit_wat(name)
        elif kind == "WL":
            result = audit_wal(name)
        else:
            result = audit_wap(name)
        report["groups"][name] = result
        print(name, json.dumps(result, ensure_ascii=False, default=json_default)[:1800])
    report["native_read_errors"] = [row for row in report["inventory"] if "error" in row]
    (OUT / "reader_native_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8"
    )
    print("OUTPUT", OUT / "reader_native_audit.json")


if __name__ == "__main__":
    main()
