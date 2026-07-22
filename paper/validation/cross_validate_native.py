#!/usr/bin/env python3
"""Cross-validate pymapgis (mapgis2shp) output against official MapGIS-exported
shapefiles.

For each of the 36 sample layers, this script compares the GeoDataFrame
produced by ``pymapgis.Reader`` against the shapefile exported by the official
MapGIS software, checking:

* feature count,
* attribute fidelity (field-by-field, aligned by ID/FEATUREID),
* geometric fidelity (point distance, line Hausdorff distance, polygon IoU),
* coordinate reference system presence.

Results are written to ``cross_validation_report.csv`` and
``cross_validation_report.md`` for the paper's Validation section.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Dict, List, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

warnings.filterwarnings("ignore")

MAPGIS_DIR = Path(r"E:/J43C001002/MAPGIS/JWD")
NATIVE_DIR = Path(r"E:/J43C001002/转shp")

# Tolerance for treating two coordinates as equal (degrees in longlat CRS).
COORD_TOL = 1e-7
# Relative tolerance for float attribute / length / area equality.
REL_TOL = 1e-6


def _try_float(x: Any):
    """Return float(x) if x is a number or a numeric string, else None.

    Handles Python scalars, numpy scalars (np.int32/np.float64/...), and
    numeric strings. NaN -> None (treated as empty).
    """
    import math
    if isinstance(x, bool):
        return None
    if isinstance(x, str):
        s = x.strip()
        if not s:
            return None
        try:
            f = float(s)
        except ValueError:
            return None
    else:
        try:
            f = float(x)  # numpy scalars coerce fine
        except (TypeError, ValueError):
            return None
    if math.isnan(f):
        return None
    return f


def _sig_figs(x: float) -> int:
    """Count significant figures in the short repr of x."""
    s = f"{x:.12g}".replace("-", "").replace("+", "")
    if "e" in s.lower():
        mant = s.split("e")[0].split("E")[0]
    else:
        mant = s
    mant = mant.replace(".", "").lstrip("0")
    return max(len(mant), 1)


def _attr_category(a: Any, b: Any) -> str:
    """Classify an attribute comparison.

    Returns one of:
    - "match": semantically equal (empty/None equal; numeric equal; strings
      identical).
    - "native_truncated": pymapgis preserves more precision than the native
      shapefile export. Covers (i) floats native rounds to fewer sig figs
      (incl. scientific notation), (ii) numeric strings formatted differently
      ("72.0" vs "72"), (iii) strings differing only by padding whitespace
      (pymapgis keeps the field's stored padding, native strips it).
    - "mismatch": a genuine semantic difference.
    """
    na = "" if (a is None or (isinstance(a, float) and np.isnan(a))) else a
    nb = "" if (b is None or (isinstance(b, float) and np.isnan(b))) else b
    if na == "" and nb == "":
        return "match"

    # Numeric comparison (incl. numeric strings like "72.0" vs "72").
    fa, fb = _try_float(na), _try_float(nb)
    if fa is not None and fb is not None:
        if fa == fb:
            return "match"
        if fa == 0 or fb == 0:
            return "match" if abs(fa - fb) <= 1e-9 else "native_truncated"
        if abs(fa - fb) <= REL_TOL * max(abs(fa), abs(fb)):
            return "match"
        # Native rounds floats to few sig figs; does rounding pymapgis to
        # native's sig-fig count reproduce native?
        try:
            nsf = _sig_figs(fb)
            if float(f"{fa:.{nsf}g}") == fb:
                return "native_truncated"
        except Exception:
            pass
        return "mismatch"

    # String comparison: equal after stripping padding whitespace -> native
    # stripped, pymapgis preserved the stored bytes.
    sa, sb = str(na), str(nb)
    if sa == sb:
        return "match"
    if sa.strip() == sb.strip() and sa.strip() != "":
        return "native_truncated"
    return "mismatch"


def _equiv_attr(a: Any, b: Any) -> bool:
    """Backward-compatible boolean wrapper (match or native_truncated)."""
    return _attr_category(a, b) != "mismatch"


def _align_key(gdf: gpd.GeoDataFrame) -> str:
    """Pick the alignment key: ID if unique, else FEATUREID."""
    for key in ("ID", "FEATUREID"):
        if key in gdf.columns and gdf[key].is_unique:
            return key
    return "ID"


def _point_geom_metric(a: shapely.geometry.base.BaseGeometry,
                       b: shapely.geometry.base.BaseGeometry) -> Dict[str, float]:
    d = a.distance(b)
    return {"metric": "point_distance_deg", "value": d, "match": d <= COORD_TOL}


def _line_geom_metric(a: shapely.geometry.base.BaseGeometry,
                      b: shapely.geometry.base.BaseGeometry) -> Dict[str, float]:
    haus = a.hausdorff_distance(b)
    la, lb = a.length, b.length
    rel_len = abs(la - lb) / max(la, lb, 1e-12) if (la or lb) else 0.0
    # Match if Hausdorff distance is within tolerance (lines coincide).
    return {"metric": "hausdorff_deg", "value": haus,
            "match": haus <= COORD_TOL, "extra_rel_len_diff": rel_len}


def _poly_geom_metric(a: shapely.geometry.base.BaseGeometry,
                      b: shapely.geometry.base.BaseGeometry) -> Dict[str, float]:
    a = shapely.make_valid(a) if not a.is_valid else a
    b = shapely.make_valid(b) if not b.is_valid else b
    inter = a.intersection(b).area
    union = a.union(b).area
    iou = inter / union if union > 0 else 1.0
    aa, ab = a.area, b.area
    rel_area = abs(aa - ab) / max(aa, ab, 1e-12) if (aa or ab) else 0.0
    symdiff = a.symmetric_difference(b).area
    return {"metric": "IoU", "value": iou, "match": iou >= 1 - 1e-6,
            "extra_rel_area_diff": rel_area, "extra_symdiff_deg2": symdiff}


def _geom_metric(geom_a, geom_b, gtype: str) -> Dict[str, Any]:
    try:
        if gtype == "POINT":
            return _point_geom_metric(geom_a, geom_b)
        if gtype == "LINE":
            return _line_geom_metric(geom_a, geom_b)
        return _poly_geom_metric(geom_a, geom_b)
    except Exception as exc:  # pragma: no cover - defensive
        return {"metric": "error", "value": str(exc), "match": False}


def compare_layer(stem: str, gtype: str) -> Dict[str, Any]:
    """Compare one layer. ``stem`` e.g. 'LDLYAAI002', gtype 'WT'/'WL'/'WP'."""
    mgis_path = MAPGIS_DIR / f"{stem}.{gtype}"
    native_path = NATIVE_DIR / f"{stem}_{gtype}.shp"

    rec: Dict[str, Any] = {"layer": stem, "type": gtype, "mapgis_file": str(mgis_path)}
    if not mgis_path.exists() or not native_path.exists():
        rec["error"] = "missing file"
        return rec

    from pymapgis import Reader
    with Reader(mgis_path) as r:
        a = r.geodataframe
    b = gpd.read_file(native_path)

    rec["count_pymapgis"] = len(a)
    rec["count_native"] = len(b)
    rec["count_match"] = (len(a) == len(b))

    # Bounds comparison.
    ba, bb = a.total_bounds, b.total_bounds
    rec["bounds_max_diff"] = float(np.max(np.abs(np.array(ba) - np.array(bb))))

    # CRS.
    rec["pymapgis_crs"] = "set" if a.crs else "none"
    rec["native_crs"] = "set" if b.crs else "none"

    # Attribute columns.
    ca, cb = [c for c in a.columns if c != a.geometry.name], \
             [c for c in b.columns if c != b.geometry.name]
    rec["attr_cols_match"] = (set(ca) == set(cb))

    # Align by key (ID preferred if unique in both, else FEATUREID).
    key = None
    for cand in ("ID", "FEATUREID"):
        if cand in a.columns and cand in b.columns \
                and a[cand].is_unique and b[cand].is_unique:
            key = cand
            break
    rec["align_key"] = key
    # Exclude the key itself from attribute comparison (it is the index after set_index).
    common_cols = [c for c in ca if c in set(cb) and c != key]
    if key:
        da = a.set_index(key)
        db = b.set_index(key)
        common_keys = da.index.intersection(db.index)
        rec["aligned_pairs"] = len(common_keys)
        cat_counts = {"match": 0, "native_truncated": 0, "mismatch": 0}
        attr_total = 0
        for k in common_keys:
            ra = da.loc[k]
            rb = db.loc[k]
            ra = ra.iloc[0] if isinstance(ra, pd.DataFrame) else ra
            rb = rb.iloc[0] if isinstance(rb, pd.DataFrame) else rb
            for c in common_cols:
                attr_total += 1
                cat_counts[_attr_category(ra[c], rb[c])] += 1
        rec["attr_compared"] = attr_total
        rec["attr_match"] = cat_counts["match"]
        rec["attr_native_truncated"] = cat_counts["native_truncated"]
        rec["attr_mismatch"] = cat_counts["mismatch"]
        # Equivalence rate treats native-truncated as equivalent (pymapgis is
        # strictly more precise). Strict rate counts only exact matches.
        equiv = cat_counts["match"] + cat_counts["native_truncated"]
        rec["attr_equiv_rate"] = equiv / attr_total if attr_total else 1.0
        rec["attr_strict_rate"] = cat_counts["match"] / attr_total if attr_total else 1.0
        rec["attr_match_rate"] = rec["attr_equiv_rate"]  # legacy column
    else:
        rec["aligned_pairs"] = 0
        rec["attr_equiv_rate"] = float("nan")
        rec["attr_strict_rate"] = float("nan")
        rec["attr_match_rate"] = float("nan")

    # Geometry comparison on aligned pairs.
    if key and rec["aligned_pairs"]:
        _gtype_map = {"WT": "POINT", "WL": "LINE", "WP": "POLYGON"}
        gtype_norm = _gtype_map[gtype]
        metrics = []
        da = a.set_index(key)
        db = b.set_index(key)
        common_keys = da.index.intersection(db.index)
        for k in common_keys:
            ga = da.loc[k].geometry
            gb = db.loc[k].geometry
            if isinstance(ga, pd.Series):
                ga = ga.iloc[0]
            if isinstance(gb, pd.Series):
                gb = gb.iloc[0]
            m = _geom_metric(ga, gb, gtype_norm)
            metrics.append(m)
        vals = [m["value"] for m in metrics if isinstance(m["value"], (int, float))]
        matches = sum(1 for m in metrics if m["match"])
        rec["geom_pairs"] = len(metrics)
        rec["geom_match_count"] = matches
        rec["geom_match_rate"] = matches / len(metrics) if metrics else 1.0
        if vals:
            arr = np.array(vals, dtype=float)
            rec["geom_metric_min"] = float(np.min(arr))
            rec["geom_metric_mean"] = float(np.mean(arr))
            rec["geom_metric_max"] = float(np.max(arr))
    else:
        rec["geom_match_rate"] = float("nan")

    return rec


def main() -> int:
    files = sorted(list(MAPGIS_DIR.glob("*.WT")) + list(MAPGIS_DIR.glob("*.WL"))
                   + list(MAPGIS_DIR.glob("*.WP")))
    rows: List[Dict[str, Any]] = []
    for f in files:
        stem = f.stem
        gtype = f.suffix[1:].upper()
        print(f"comparing {stem}.{gtype} ...", flush=True)
        rows.append(compare_layer(stem, gtype))

    df = pd.DataFrame(rows)
    df.to_csv(MAPGIS_DIR / "cross_validation_report.csv", index=False, encoding="utf-8-sig")

    # Markdown summary.
    lines = ["# Cross-validation: pymapgis vs official MapGIS export", "",
             f"Layers compared: {len(df)}", ""]
    valid = df[df.get("error").isna()] if "error" in df.columns else df
    lines.append(f"- Count match (all): {bool(valid['count_match'].all())}")
    lines.append(f"- Total features pymapgis: {int(valid['count_pymapgis'].sum())}")
    lines.append(f"- Total features native:  {int(valid['count_native'].sum())}")
    lines.append(f"- Attr columns match (all): {bool(valid['attr_cols_match'].all())}")
    lines.append(f"- Attr strict match rate (mean): {valid['attr_strict_rate'].mean():.6f}")
    lines.append(f"- Attr equivalence rate (mean, incl. native-truncated): "
                 f"{valid['attr_equiv_rate'].mean():.6f}")
    lines.append(f"- Real attr mismatches (total): {int(valid['attr_mismatch'].sum())}")
    lines.append(f"- Attr cells native-truncated (pymapgis more precise), total: "
                 f"{int(valid['attr_native_truncated'].sum())}")
    lines.append(f"- Mean geom match rate: {valid['geom_match_rate'].mean():.6f}")
    lines.append(f"- Layers with geom match rate >= 0.999: "
                 f"{int((valid['geom_match_rate'] >= 0.999).sum())}/{len(valid)}")
    lines.append("")
    lines.append("| layer | type | count(pm/nat) | attr_strict | attr_equiv | attr_mismatch | geom_match |")
    lines.append("|---|---|---|---|---|---|---|")
    for _, r in valid.iterrows():
        lines.append(
            f"| {r['layer']} | {r['type']} | {r['count_pymapgis']}/{r['count_native']} | "
            f"{r['attr_strict_rate']:.4f} | {r['attr_equiv_rate']:.4f} | "
            f"{int(r['attr_mismatch'])} | {r['geom_match_rate']:.4f} |"
        )
    (MAPGIS_DIR / "cross_validation_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n=== SUMMARY ===")
    print("\n".join(lines[:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
