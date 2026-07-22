#!/usr/bin/env python3
"""Native cross-validation of mapgis2shp against an official MapGIS export.

Compares a MapGIS ``.wt/.wl/.wp`` file read by ``pymapgis.Reader`` against a
reference dataset exported by the official MapGIS software (shapefile/GeoJSON).
Handles the common case where the official export has a different feature
partition (e.g. adjacent polygons dissolved) by comparing coverage
equivalence via geometry unions rather than 1:1 feature equality.

Usage::

    python cross_validate.py <mapgis_file> <reference_file> [--skip-union]

Metrics reported:
  * bounding box, CRS, feature count, geometry-type mix, invalid count
  * field-schema overlap
  * total area (equal-area projection) and area ratio
  * symmetric-difference area of the two coverage unions (the decisive
    equivalence test) -- skipped with --skip-union for very large inputs
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Any, Dict

warnings.filterwarnings("ignore")

import geopandas as gpd
import numpy as np
import pyproj
import shapely

# Allow running from the repo root before the package is installed.
_SRC = Path(__file__).parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from pymapgis import Reader  # noqa: E402


def _geodesic_area_km2(geoms: gpd.GeoSeries, geod: pyproj.Geod) -> float:
    """Sum absolute geodesic area (km^2) over arbitrary geometries.

    Uses the ellipsoidal Geod so no reprojection is needed -- critical for
    large inputs where ``to_crs`` would exhaust memory. GeometryCollections
    (produced by ``make_valid``) are decomposed to their polygon parts.
    """
    total = 0.0
    for g in geoms:
        if g is None or g.is_empty:
            continue
        if g.geom_type == "GeometryCollection":
            parts = [p for p in g.geoms if p.geom_type in ("Polygon", "MultiPolygon")]
        else:
            parts = [g]
        for part in parts:
            try:
                area, _ = geod.geometry_area_perimeter(part)
                total += abs(area)
            except Exception:
                pass
    return total / 1e6


def _load_mapgis(path: str) -> gpd.GeoDataFrame:
    with Reader(path) as r:
        return r.geodataframe


def _load_reference(path: str) -> gpd.GeoDataFrame:
    return gpd.read_file(path)


def _ensure_crs(gdf: gpd.GeoDataFrame, fallback: str) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        gdf = gdf.set_crs(fallback)
    return gdf


def _summary(gdf: gpd.GeoDataFrame, label: str) -> Dict[str, Any]:
    bounds = gdf.total_bounds
    return {
        "label": label,
        "feature_count": len(gdf),
        "crs": str(gdf.crs),
        "geom_types": gdf.geom_type.value_counts().to_dict(),
        "invalid": int((~gdf.is_valid).sum()),
        "bbox": [round(float(v), 6) for v in bounds],
        "fields": [c for c in gdf.columns if c != gdf.geometry.name],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mapgis_file")
    ap.add_argument("reference_file")
    ap.add_argument("--skip-union", action="store_true",
                    help="skip the symmetric-difference union test (large files)")
    ap.add_argument("--json", metavar="PATH", help="write report as JSON to PATH")
    args = ap.parse_args()

    print(f"Reading mapgis2shp : {args.mapgis_file}")
    mg = _load_mapgis(args.mapgis_file)
    print(f"Reading reference  : {args.reference_file}")
    rf = _load_reference(args.reference_file)

    # Both datasets share longlat degree coordinates; assign the mapgis2shp
    # inferred CRS to the reference if the official export dropped its .prj.
    inferred_crs = mg.crs if mg.crs is not None else "EPSG:4326"
    mg = _ensure_crs(mg, inferred_crs)
    rf = _ensure_crs(rf, inferred_crs)

    rep: Dict[str, Any] = {}
    rep["mapgis2shp"] = _summary(mg, "mapgis2shp")
    rep["reference"] = _summary(rf, "official MapGIS export")

    # Bounding box agreement.
    bb_mg = np.array(mg.total_bounds)
    bb_rf = np.array(rf.total_bounds)
    rep["bbox_abs_diff"] = [round(float(v), 9) for v in np.abs(bb_mg - bb_rf)]
    rep["bbox_match"] = bool(np.allclose(bb_mg, bb_rf, atol=1e-6))

    # Field-schema overlap.
    f_mg = set(rep["mapgis2shp"]["fields"])
    f_rf = set(rep["reference"]["fields"])
    rep["fields_common"] = sorted(f_mg & f_rf)
    rep["fields_only_mapgis"] = sorted(f_mg - f_rf)
    rep["fields_only_reference"] = sorted(f_rf - f_mg)

    # Geodesic total areas on the native ellipsoid (no reprojection).
    geod = pyproj.Geod(ellps="krass")  # Krassovsky / Beijing-54 ellipsoid
    area_mg = _geodesic_area_km2(mg.geometry, geod)
    area_rf = _geodesic_area_km2(rf.geometry, geod)
    rep["total_area_km2"] = {"mapgis2shp": round(area_mg, 3),
                             "reference": round(area_rf, 3)}
    rep["area_abs_diff_km2"] = round(abs(area_mg - area_rf), 3)
    rep["area_rel_diff_pct"] = (round(abs(area_mg - area_rf) / max(area_rf, 1e-9) * 100, 6)
                                if area_rf else None)

    # Coverage equivalence via union symmetric difference (decisive test).
    # Performed in native longlat space; areas via Geod on the result.
    if not args.skip_union:
        print("Computing coverage unions (may take a while on large inputs)...")
        try:
            union_mg = shapely.union_all(np.asarray(mg.geometry))
            union_rf = shapely.union_all(np.asarray(rf.geometry))
            sym = union_mg.symmetric_difference(union_rf)
            inter = union_mg.intersection(union_rf)
            sym_area = _geodesic_area_km2(gpd.GeoSeries([sym]), geod)
            inter_area = _geodesic_area_km2(gpd.GeoSeries([inter]), geod)
            rep["union_symdiff_km2"] = round(sym_area, 6)
            rep["union_intersection_km2"] = round(inter_area, 6)
            rep["coverage_iou"] = round(inter_area / (inter_area + sym_area + 1e-12), 8)
        except Exception as exc:
            rep["union_error"] = f"{type(exc).__name__}: {exc}"

    # Pretty print.
    print("\n" + "=" * 60)
    for k, v in rep.items():
        if isinstance(v, dict):
            print(f"\n[{k}]")
            for kk, vv in v.items():
                print(f"  {kk}: {vv}")
        elif isinstance(v, list):
            print(f"{k}: {v}")
        else:
            print(f"{k}: {v}")

    if args.json:
        Path(args.json).write_text(json.dumps(rep, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        print(f"\nReport written to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
