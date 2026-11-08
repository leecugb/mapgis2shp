"""Audit pymapgis.Writer against SHP and native MapGIS conversions."""
from __future__ import annotations

import argparse
import json
import warnings
from collections import Counter
from pathlib import Path

import geopandas as gpd
import pandas as pd

from pymapgis import Reader, write

ATTRIBUTE_COLUMNS = (
    "FID", "NAME", "CODE", "VALUE", "DATE", "LONG_NAME", "TEXT_NULL",
    "INT32", "FLOAT64", "NOTE",
)


def scalar(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def records(gdf):
    result = []
    for _, row in gdf.iterrows():
        result.append({name: scalar(row[name]) for name in ATTRIBUTE_COLUMNS if name in row})
    return result


def geometry_signature(gdf):
    return {
        "count": len(gdf),
        "types": dict(Counter(gdf.geom_type)),
        "valid": sum(geom is not None and geom.is_valid for geom in gdf.geometry),
        "area_sum": float(gdf.geometry.area.sum()),
        "length_sum": float(gdf.geometry.length.sum()),
        "crs": str(gdf.crs) if gdf.crs is not None else None,
    }


def geometry_comparison(expected, actual, tolerance=0.0):
    exact = len(expected) == len(actual)
    topological = exact
    exact_coordinates = exact
    if exact:
        for left, right in zip(expected.geometry, actual.geometry):
            if left is None or right is None:
                topological = topological and left is right
                exact_coordinates = exact_coordinates and left is right
                continue
            try:
                if tolerance:
                    topological = topological and left.hausdorff_distance(right) <= tolerance
                else:
                    topological = topological and bool(left.equals(right))
                exact_coordinates = exact_coordinates and bool(left.equals_exact(right, 1e-9))
            except Exception:
                topological = False
                exact_coordinates = False
    return {
        "topological_match": topological,
        "exact_coordinate_match": exact_coordinates,
        "expected_count": len(expected),
        "actual_count": len(actual),
        "hausdorff_tolerance": tolerance,
    }


def wkts(gdf):
    return [geom.wkt if geom is not None else None for geom in gdf.geometry]


def standard_values(gdf):
    names = (
        "class", "fill_color", "pattern", "pattern_height", "pattern_width",
        "pattern_color", "layer", "field5", "field6", "field7", "point_type",
        "symbol_no", "height", "width", "spacing", "angle", "color", "pen_width",
        "linetype", "aux_linetype", "aux_flag", "x_coef", "y_coef", "aux_color",
        "transparent",
    )
    result = []
    for _, row in gdf.iterrows():
        values = {name: scalar(row[name]) for name in names if name in row}
        has_ring_offset = all(
            name in values and values[name] is not None
            for name in ("field5", "field6", "field7")
        )
        if has_ring_offset:
            values["ring_index_offset"] = (
                values["field5"] + (values["field6"] << 8) + (values["field7"] << 16)
            )
        result.append(values)
    return result


def expected_source(gdf):
    if (gdf.geom_type == "MultiLineString").any():
        return gdf.explode(index_parts=False)
    return gdf


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for shp in sorted(args.input_dir.glob("*.shp")):
            ext = (
                ".WT" if shp.stem.startswith("10_")
                else ".WL" if shp.stem.startswith("11_") else ".WP"
            )
            native_path = args.input_dir / (shp.stem.upper() + ext)
            output_path = args.output_dir / (shp.stem + ext.lower())
            source = gpd.read_file(shp)
            native = Reader(
                str(native_path), read_graphic_params=True, read_point_params=True
            ).geodataframe
            result = {
                "case": shp.stem,
                "source_file": shp.name,
                "native_file": native_path.name,
                "output_file": output_path.name,
                "source": geometry_signature(source),
                "native": geometry_signature(native),
            }
            try:
                write(source, output_path)
                ours = Reader(
                    str(output_path), read_graphic_params=True, read_point_params=True
                ).geodataframe
                expected = expected_source(source)
                comparison_ours = ours
                crs_tolerance = 0.0
                if (
                    source.crs is not None
                    and ours.crs is not None
                    and source.crs.to_proj4() != ours.crs.to_proj4()
                ):
                    comparison_ours = ours.to_crs(source.crs)
                    crs_tolerance = 1e-5
                result.update(
                    {
                        "write_error": None,
                        "ours": geometry_signature(ours),
                        "expected_source": geometry_signature(expected),
                        "source_native_attributes_match": records(source) == records(native),
                        "source_ours_attributes_match": records(expected) == records(ours),
                        "source_native_geometry": geometry_comparison(
                            expected_source(source), native
                        ),
                        "source_ours_geometry": geometry_comparison(
                            expected, comparison_ours, tolerance=crs_tolerance
                        ),
                        "native_standard_values": standard_values(native),
                        "ours_standard_values": standard_values(ours),
                        "native_wkt": wkts(native),
                        "ours_wkt": wkts(ours),
                        "ours_source_crs_wkt": wkts(comparison_ours),
                        "expected_wkt": wkts(expected),
                        "source_wkt": wkts(source),
                    }
                )
            except Exception as exc:
                result.update(
                    {
                        "write_error": f"{type(exc).__name__}: {exc}",
                        "native_standard_values": standard_values(native),
                        "native_wkt": wkts(native),
                        "source_wkt": wkts(source),
                    }
                )
            empty_mask = source.geometry.isna() | source.geometry.is_empty
            if empty_mask.any():
                drop_path = args.output_dir / (shp.stem + "_drop" + ext.lower())
                try:
                    write(source, drop_path, on_empty="drop")
                    dropped = Reader(
                        str(drop_path), read_graphic_params=True, read_point_params=True
                    ).geodataframe
                    expected_drop = expected_source(source.loc[~empty_mask])
                    result["on_empty_drop"] = {
                        "output_file": drop_path.name,
                        "ours": geometry_signature(dropped),
                        "attributes_match": records(expected_drop) == records(dropped),
                        "geometry": geometry_comparison(expected_drop, dropped),
                        "wkt": wkts(dropped),
                    }
                except Exception as exc:
                    result["on_empty_drop"] = {"error": f"{type(exc).__name__}: {exc}"}
            results.append(result)
            print(
                result["case"],
                "WRITE_ERROR=" + str(result["write_error"]),
                "ATTR=" + str(result.get("source_ours_attributes_match")),
                "GEOM=" + str(result.get("source_ours_geometry")),
            )

    report = {
        "input_directory": str(args.input_dir),
        "output_directory": str(args.output_dir),
        "case_count": len(results),
        "write_errors": sum(result["write_error"] is not None for result in results),
        "attribute_matches": sum(
            result.get("source_ours_attributes_match") is True for result in results
        ),
        "topological_matches": sum(
            result.get("source_ours_geometry", {}).get("topological_match") is True
            for result in results
        ),
        "exact_coordinate_matches": sum(
            result.get("source_ours_geometry", {}).get("exact_coordinate_match") is True
            for result in results
        ),
        "results": results,
    }
    (args.output_dir / "writer_audit_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# Writer SHP batch 2 audit",
        "",
        f"Cases: {len(results)}",
        f"Write errors: {report['write_errors']}",
        f"Attribute matches: {report['attribute_matches']}",
        f"Topological matches: {report['topological_matches']}",
        f"Exact coordinate matches: {report['exact_coordinate_matches']}",
        "",
        "| Case | Write error | Attributes | Topology | Exact coordinates | "
        "Source CRS | Native CRS | Our CRS |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        geometry = result.get("source_ours_geometry", {})
        lines.append(
            "| {case} | {error} | {attrs} | {topo} | {exact} | "
            "{src_crs} | {native_crs} | {our_crs} |".format(
                case=result["case"],
                error=result["write_error"] or "none",
                attrs=result.get("source_ours_attributes_match"),
                topo=geometry.get("topological_match"),
                exact=geometry.get("exact_coordinate_match"),
                src_crs=result["source"]["crs"],
                native_crs=result["native"]["crs"],
                our_crs=result.get("ours", {}).get("crs"),
            )
        )
    (args.output_dir / "writer_audit_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print("REPORT", args.output_dir / "writer_audit_report.json")


if __name__ == "__main__":
    main()
