#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build a mixed MapGIS WT containing attitude symbols and text annotations."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.convert_usgs_conejo import load_layers  # noqa: E402
from examples.export_usgs_shapefile import GAUSS_KRUGER_CRS  # noqa: E402
from pymapgis import Reader, Writer  # noqa: E402


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_mixed(output_dir, source_dir="work_usgs/e00/tempfiles"):
    output_dir = Path(output_dir)
    vector_dir = output_dir / "vectors"
    vector_dir.mkdir(parents=True, exist_ok=True)
    layers = load_layers(source_dir)
    symbols = layers["cwell_str.WT"]
    annotations = layers["cwell_str_lab.WT"]
    mixed = gpd.GeoDataFrame(
        pd.concat([symbols, annotations], ignore_index=True),
        geometry="geometry",
        crs=symbols.crs,
    )
    path = vector_dir / "cwell_str_mixed.WT"
    Writer(mixed.to_crs(GAUSS_KRUGER_CRS), make_valid=True, map_scale=24000).to_file(path)

    reader = Reader(path, read_graphic_params=True)
    params = reader.point_params
    assert len(reader) == 46
    assert params["point_type"].tolist() == [1] * 23 + [0] * 23
    assert params["symbol_no"].iloc[:23].tolist() == symbols["symbol_no"].tolist()
    assert params["symbol_no"].iloc[23:].eq(0).all()
    assert reader.geodataframe["CHFCED"].iloc[23:].tolist() == annotations["CHFCED"].tolist()

    optimized = ROOT / "output/writer_usgs_audit/optimized/vectors"
    for name in (
        "cwell_geo.WP", "cwell_geo.WL", "cwell_dk.WL",
        "cwell_orn.WT", "cwell_ldr.WL", "cwell_lab.WT",
    ):
        target = vector_dir / name
        target.write_bytes((optimized / name).read_bytes())

    manifest = {
        "mixed_file": str(path),
        "records": 46,
        "symbol_records": 23,
        "text_records": 23,
        "point_type_sequence": "1×23 + 0×23",
        "sha256": _sha256(path),
        "note": (
            "One WT file with separate symbol and annotation records; not one "
            "record carrying both roles. Other layers are copied from the "
            "same optimized Writer build."
        ),
    }
    (output_dir / "mixed_attitude_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path, reader


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("work_usgs/e00/tempfiles"))
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path("output/usgs_conejo/mixed_attitude"),
    )
    args = parser.parse_args()
    path, reader = build_mixed(args.output_dir, args.source)
    print(json.dumps({
        "output": str(path), "records": len(reader),
        "point_types": reader.point_params["point_type"].value_counts().to_dict(),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
