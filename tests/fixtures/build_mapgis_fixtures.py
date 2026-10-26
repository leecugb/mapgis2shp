#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build small synthetic MapGIS fixtures for public regression tests.

The fixtures are generated from geometries defined below. They are not official
MapGIS exports and must not be cited as independent native-export validation.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point, Polygon, box

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pymapgis import Reader, Writer, __version__  # noqa: E402

OUT = Path(__file__).resolve().parent / "mapgis"


def _point_frame() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "ID": pd.array([1, 2, 3], dtype="int32"),
            "NAME": ["产状点A", "产状点B", "产状点C"],
            "STRIKE": [45.0, 90.0, 120.0],
            "DIP_DIR": [135.0, 180.0, 210.0],
            "DIP": [30.0, 45.0, 60.0],
            "SURVEY_DATE": pd.to_datetime(["2026-01-01", "2026-01-02", None]),
            "point_type": [1, 1, 1],
            "symbol_no": [1281, 1281, 1281],
            "height": [2.0, 2.0, 2.0],
            "width": [2.0, 2.0, 2.0],
            "spacing": [np.nan, np.nan, np.nan],
            "angle": [45.0, 90.0, 120.0],
            "color": [6, 6, 6],
            "layer": [1, 1, 1],
            "pen_width": [0.05, 0.05, 0.05],
        },
        geometry=[Point(73.50, 39.50), Point(73.65, 39.55), Point(74.00, 39.70)],
        crs="EPSG:4326",
    )


def _line_frame() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "ID": pd.array([1, 2, 3], dtype="int32"),
            "NAME": ["合成界线", "合成断层", "合成河流"],
            "TYPE": ["boundary", "fault", "river"],
            "linetype": [1, 2, 1],
            "aux_linetype": [0, 0, 0],
            "color": [1, 2, 3],
            "width": [0.2, 0.4, 0.2],
            "x_coef": [1.0, 1.0, 1.0],
            "y_coef": [1.0, 1.0, 1.0],
            "aux_color": [0, 0, 0],
            "layer": [1, 1, 1],
            "transparent": [0, 0, 0],
        },
        geometry=[
            LineString([(73.40, 39.45), (73.70, 39.50), (73.75, 39.55)]),
            LineString([(73.55, 39.40), (73.70, 39.55), (73.85, 39.65)]),
            LineString([(73.60, 39.70), (73.80, 39.75), (74.00, 39.80)]),
        ],
        crs="EPSG:4326",
    )


def _polygon_frame() -> gpd.GeoDataFrame:
    with_hole = Polygon(
        [(74.10, 39.40), (74.40, 39.40), (74.40, 39.70), (74.10, 39.70), (74.10, 39.40)],
        [[(74.20, 39.50), (74.30, 39.50), (74.30, 39.60),
          (74.20, 39.60), (74.20, 39.50)]],
    )
    return gpd.GeoDataFrame(
        {
            "ID": pd.array([1, 2, 3, 4], dtype="int32"),
            "UNIT": ["C1", "C2", "Q", "Q"],
            "NAME": ["合成单元A", "合成单元B", "合成第四系", "合成岛面"],
            "fill_color": [70, 35, 9, 9],
            "pattern": [0, 0, 0, 0],
            "pattern_height": [3.0, 3.0, 3.0, 3.0],
            "pattern_width": [3.0, 3.0, 3.0, 3.0],
            "pattern_color": [0, 0, 0, 0],
            "layer": [1, 1, 1, 1],
        },
        geometry=[
            box(73.40, 39.40, 73.70, 39.70),
            box(73.70, 39.40, 74.00, 39.70),
            with_hole,
            box(74.20, 39.50, 74.30, 39.60),
        ],
        crs="EPSG:4326",
    )


def _manifest_entry(path: Path) -> dict:
    with Reader(path, read_graphic_params=True) as reader:
        frame = reader.geodataframe
        return {
            "geometry_family": reader.shapeType,
            "feature_count": len(reader),
            "bbox": reader.bbox.tolist(),
            "geometry_types": sorted(frame.geom_type.unique().tolist()),
            "crs": reader.crs.to_wkt() if reader.crs else None,
            "attribute_fields": [field[0] for field in reader.fields],
            "graphic_parameter_columns": sorted(
                set(frame.columns)
                - set(reader.data.columns)
                - {"geometry"}
            ),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }


def _source_description() -> str:
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable"
    return result.stdout.strip()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frames = {
        "synthetic_points.wt": _point_frame(),
        "synthetic_lines.wl": _line_frame(),
        "synthetic_polygons.wp": _polygon_frame(),
    }
    for filename, frame in frames.items():
        Writer(frame).to_file(OUT / filename)

    manifest = {
        "schema_version": 1,
        "generator": "tests/fixtures/build_mapgis_fixtures.py",
        "generator_software_version": __version__,
        "generator_source_description": _source_description(),
        "provenance": (
            "Synthetic geometries generated with pymapgis Writer. These are public "
            "regression fixtures, not official MapGIS exports and not independent "
            "native-export validation."
        ),
        "files": {
            filename: _manifest_entry(OUT / filename)
            for filename in sorted(frames)
        },
    }
    manifest_path = OUT.parent / "fixture_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(frames)} fixtures to {OUT}")
    print(f"Wrote manifest to {manifest_path}")


if __name__ == "__main__":
    main()
