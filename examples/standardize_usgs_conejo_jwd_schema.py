#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Rename three USGS layers and align their core attributes with JWD schemas."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pymapgis import GraphicRenderer, Reader, Writer  # noqa: E402

TARGETS = {
    "CWELL_GEO_WP.WP": "LDZOFBB001.WP",
    "CWELL_GEO_WL.WL": "LDZOFBA002.WL",
    "CWELL_STR_WT.WT": "LDZOFBA016.WT",
}
PREFIXES = {
    "CWELL_GEO_WP.WP": "OFBB001C1A",
    "CWELL_GEO_WL.WL": "OFBA002C1A",
    "CWELL_STR_WT.WT": "OFBA016C1A",
}
CORE_FIELDS = {
    "CWELL_GEO_WP.WP": [
        "ID", "周长", "面积", "FEATUREID", "CHFCAC", "QDUECD", "QDUECC",
    ],
    "CWELL_GEO_WL.WL": [
        "ID", "长度", "FEATUREID", "CHFCAC", "GZBD", "PKIGJ",
    ],
    "CWELL_STR_WT.WT": [
        "ID", "FEATUREID", "CHFCAC", "GZBBGA", "GZBBAC", "GZBBAD", "GZBBAB",
    ],
}
ATTITUDE_CODES = {
    "metamorphosed bedding": "202001",
    "foliation": "202011",
    "cleavage": "202008",
    # JWD LDZOFBA016 has no lineation code. Keep these two source records
    # explicit instead of inventing a planar-attitude classification.
    "stretched pebble": "",
    "minor fold axis, dextral rotation": "",
}


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _geometry_hash(frame):
    digest = hashlib.sha256()
    for geometry in frame.geometry:
        digest.update(geometry.wkb)
    return digest.hexdigest()


def _text(value):
    if value is None:
        return ""
    return str(value).strip()


def _number_text(value, decimals=0):
    if value is None:
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(number):
        return ""
    if decimals:
        return f"{number:.{decimals}f}"
    return str(int(number)) if number.is_integer() else str(number)


def _with_identifiers(frame, prefix):
    result = frame.copy()
    count = len(result)
    result["ID"] = np.arange(1, count + 1, dtype=np.int32)
    result["FEATUREID"] = [
        f"{prefix}01031CW{index:09d}" for index in range(1, count + 1)
    ]
    result["CHFCAC"] = [f"{index:06d}" for index in range(1, count + 1)]
    if not result["FEATUREID"].str.len().eq(26).all():
        raise AssertionError("FEATUREID does not follow the 26-character JWD layout")
    return result


def _boundary_code(row):
    feature_type = _text(row.get("FEAT_TYPE"))
    definition = _text(row.get("L_DEF")).lower()
    if feature_type == "fault":
        return "10"
    if feature_type == "map boundary":
        return ""
    if "igneous contact" in definition:
        return "11"
    if "inferred" in definition or "questionable" in definition:
        return "16"
    # Do not infer Quaternary/unconformity subclasses without evidence from
    # the adjacent polygons. Certain non-igneous contacts stay generic 01.
    return "01"


def _ordered(frame, core):
    columns = [name for name in core if name in frame.columns]
    columns.extend(
        name for name in frame.columns
        if name not in columns and name != "geometry"
    )
    columns.append("geometry")
    return frame[columns].copy()


def prepare(source_name, frame):
    frame = _with_identifiers(frame, PREFIXES[source_name])
    if source_name == "CWELL_GEO_WP.WP":
        # JWD: QDUECC=unit code, QDUECD=unit name. USGS names remain English;
        # no JWD-specific # control codes or Chinese names are fabricated.
        frame["QDUECC"] = frame["LABL"].map(_text)
        frame["QDUECD"] = frame["NAME"].map(_text)
    elif source_name == "CWELL_GEO_WL.WL":
        frame["GZBD"] = [
            _boundary_code(row) for row in frame.to_dict("records")
        ]
        frame["PKIGJ"] = (
            "1:24000 Conejo Well 7.5-minute quadrangle (USGS OFR 01-031)"
        )
    else:
        types = [_text(value) for value in frame["PTTYPE"]]
        frame["GZBBGA"] = [ATTITUDE_CODES.get(value, "") for value in types]
        strike = []
        dip_direction = []
        dip = []
        for row in frame.to_dict("records"):
            if _text(row.get("CHFCEC")) == "产状":
                strike.append(_number_text(row.get("P_STRIKE"), decimals=6))
                dip_direction.append(_number_text(row.get("P_DIPDIR")))
                dip.append(_number_text(row.get("P_DIP")))
            else:
                # Preserve lineation trend/plunge in the direction/value fields;
                # strike and GZBBGA remain empty because JWD has no lineation code.
                strike.append("")
                dip_direction.append(_number_text(row.get("P_BEARING")))
                dip.append(_number_text(row.get("P_PLUNGE")))
        frame["GZBBAB"] = strike
        frame["GZBBAC"] = dip_direction
        frame["GZBBAD"] = dip
    result = _ordered(frame, CORE_FIELDS[source_name])
    # Attribute names/types are intentionally rebuilt. Reusing the source
    # descriptors would keep GZBBAB/GZBBAC/GZBBAD numeric and reject JWD-style
    # empty strings; raw source sections also carry the old attribute schema.
    result.attrs = frame.attrs.copy()
    result.attrs.pop("mapgis_field_meta", None)
    result.attrs.pop("mapgis_section_passthrough", None)
    return result


def convert_one(source: Path, destination: Path):
    frame = GraphicRenderer.read_layer(source)
    if frame.crs in (None, "") or frame.crs.to_epsg() != 32611:
        raise ValueError(f"Expected repaired EPSG:32611 input: {source}")
    source_geometry_hash = _geometry_hash(frame)
    prepared = prepare(source.name, frame)
    Writer(
        prepared,
        make_valid=False,
        map_scale=1000,
        preserve_utm=True,
    ).to_file(destination)

    repaired = Reader(destination, read_graphic_params=True)
    target_frame = repaired.geodataframe
    if repaired.crs.to_epsg() != 32611 or repaired.coordinate_scale_factor != 1.0:
        raise AssertionError(f"CRS round-trip failed: {destination.name}")
    if len(target_frame) != len(frame):
        raise AssertionError(f"Feature count changed: {destination.name}")
    hausdorff = [
        left.hausdorff_distance(right)
        for left, right in zip(frame.geometry, target_frame.geometry)
    ]
    if max(hausdorff, default=0.0) > 1e-5:
        raise AssertionError(f"Geometry changed beyond 1e-5 m: {destination.name}")
    missing_core = [name for name in CORE_FIELDS[source.name] if name not in repaired.data]
    if missing_core:
        raise AssertionError(f"Missing JWD core fields: {missing_core}")
    report = {
        "source_file": source.name,
        "target_file": destination.name,
        "features": len(frame),
        "source_sha256": _sha256(source),
        "target_sha256": _sha256(destination),
        "source_geometry_sha256": source_geometry_hash,
        "target_geometry_sha256": _geometry_hash(target_frame),
        "max_hausdorff_m": max(hausdorff, default=0.0),
        "bounds": list(target_frame.total_bounds),
        "reader_epsg": repaired.crs.to_epsg(),
        "coordinate_scale_factor": repaired.coordinate_scale_factor,
        "attribute_fields": list(repaired.data.columns),
        "jwd_core_fields": CORE_FIELDS[source.name],
    }
    if "GZBD" in repaired.data:
        report["GZBD_counts"] = repaired.data["GZBD"].value_counts().to_dict()
    if "GZBBGA" in repaired.data:
        report["GZBBGA_counts"] = repaired.data["GZBBGA"].value_counts().to_dict()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("testdata"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/usgs_conejo/six_file_tests/jwd_schema"),
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reports = [
        convert_one(args.input_dir / source, args.output_dir / target)
        for source, target in TARGETS.items()
    ]
    report = {
        "method": (
            "JWD-style file names and core attributes, with original USGS fields retained; "
            "Writer preserve_utm=True and map_scale=1000"
        ),
        "feature_id_note": (
            "26-character IDs use USGS OFR 01-031 and CW, not the JWD J43C001002 sheet code"
        ),
        "polygon_name_note": (
            "LDZOFBB001.WP is a JWD-style layer name only; all 56 mixed USGS units remain"
        ),
        "native_mapgis_acceptance": "Pending testing in MapGIS on the acceptance computer",
        "files": reports,
    }
    (args.output_dir / "jwd_schema_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "output_dir": str(args.output_dir),
        "files": [
            {
                "source": item["source_file"],
                "target": item["target_file"],
                "features": item["features"],
                "epsg": item["reader_epsg"],
                "coordinate_scale_factor": item["coordinate_scale_factor"],
                "max_hausdorff_m": item["max_hausdorff_m"],
            }
            for item in reports
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
