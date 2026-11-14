#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run an executable migration example on the seven bundled USGS-derived layers.

This demonstrates format interoperability and open analysis, not a new geological
interpretation or independent MapGIS native-application acceptance.
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

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402

from pymapgis import Reader  # noqa: E402
from pymapgis.testing import testdata_path  # noqa: E402

LAYER_NAMES = (
    "LDZOFBA002.WL",
    "LDZOFBA003.WL",
    "LDZOFBA016.WT",
    "LDZOFBB001.WP",
    "LDZOFBB002.WP",
    "LDZOFBB003.WP",
    "LDZOFBB004.WP",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Optionally write all seven layers as GeoPackage files to this directory",
    )
    args = parser.parse_args()

    layers = {}
    for name in LAYER_NAMES:
        reader = Reader(testdata_path(name), read_graphic_params=True)
        if reader.crs.to_epsg() != 32611 or reader.coordinate_scale_factor != 1.0:
            raise ValueError(f"Unexpected native spatial reference in {name}")
        layers[name] = reader.geodataframe

    lines = gpd.GeoDataFrame(
        pd.concat(
            [layers["LDZOFBA002.WL"], layers["LDZOFBA003.WL"]],
            ignore_index=True,
        ),
        crs="EPSG:32611",
    )
    polygons = gpd.GeoDataFrame(
        pd.concat(
            [layers[name] for name in LAYER_NAMES if name.endswith(".WP")],
            ignore_index=True,
        ),
        crs="EPSG:32611",
    )
    summary = {
        "source": "Bundled seven-layer USGS Conejo Well processed testdata",
        "native_crs": "EPSG:32611",
        "coordinate_scale_factor": 1.0,
        "source_cartographic_scale": 24000,
        "feature_counts": {name: len(layer) for name, layer in layers.items()},
        "attitude_and_lineation_count": int(len(layers["LDZOFBA016.WT"])),
        "line_length_by_type_km": {
            str(kind): round(float(group.geometry.length.sum() / 1000.0), 6)
            for kind, group in lines.groupby("FEAT_TYPE")
        },
        "polygon_area_by_unit_km2": {
            str(unit): round(float(group.geometry.area.sum() / 1_000_000.0), 6)
            for unit, group in polygons.groupby("QDUECC")
        },
    }

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for name, layer in layers.items():
            layer.to_file(args.output_dir / f"{Path(name).stem}.gpkg", driver="GPKG")
        summary["output_directory"] = str(args.output_dir.resolve())

    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
