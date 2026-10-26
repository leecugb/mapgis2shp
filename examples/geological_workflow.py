#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run a reproducible geological-data migration example on public fixtures.

This example demonstrates format interoperability and open analysis, not a new
geological interpretation or an independent MapGIS native-export validation.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pymapgis import Reader  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "mapgis"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Optionally write the three open GeoPackage outputs to this directory",
    )
    args = parser.parse_args()

    with Reader(FIXTURES / "synthetic_points.wt", read_graphic_params=True) as reader:
        points = reader.geodataframe
    with Reader(FIXTURES / "synthetic_lines.wl", read_graphic_params=True) as reader:
        lines = reader.geodataframe
    with Reader(FIXTURES / "synthetic_polygons.wp", read_graphic_params=True) as reader:
        polygons = reader.geodataframe

    points_utm = points.to_crs("EPSG:32643")
    lines_utm = lines.to_crs("EPSG:32643")
    polygons_utm = polygons.to_crs("EPSG:32643")
    summary = {
        "crs_after_migration": "EPSG:32643",
        "attitude_count": int(len(points)),
        "line_length_by_type_km": {
            str(kind): round(float(group.length.sum() / 1000.0), 6)
            for kind, group in lines_utm.groupby("TYPE")
        },
        "polygon_area_by_unit_km2": {
            str(unit): round(float(group.area.sum() / 1_000_000.0), 6)
            for unit, group in polygons_utm.groupby("UNIT")
        },
    }

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        points_utm.to_file(args.output_dir / "synthetic_points.gpkg", driver="GPKG")
        lines_utm.to_file(args.output_dir / "synthetic_lines.gpkg", driver="GPKG")
        polygons_utm.to_file(args.output_dir / "synthetic_polygons.gpkg", driver="GPKG")
        summary["output_directory"] = str(args.output_dir.resolve())

    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
