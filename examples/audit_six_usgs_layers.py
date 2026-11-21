#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run Reader and original-library rendering tests on six native USGS files."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.render_bundled_jwd import summarise  # noqa: E402
from examples.usgs_conejo_symbols import expand_left_slip_ornaments  # noqa: E402
from pymapgis import GraphicLibraries, GraphicRenderer, Reader  # noqa: E402
from pymapgis.testing import slib_path, usgs_conejo_path  # noqa: E402

EXPECTED = {
    "CWELL_GEO_WP.WP": 2498,
    "CWELL_GEO_WL.WL": 5991,
    "CWELL_DK_WL.WL": 253,
    "CWELL_STR_WT.WT": 23,
    "CWELL_ORN_WT.WT": 2,
    "CWELL_LDR_WL.WL": 37,
}
TARGET_CRS = "EPSG:32611"


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_six_layers(root=None):
    root = Path(root) if root else usgs_conejo_path("native")
    layers = []
    reports = []
    for name, expected in EXPECTED.items():
        path = root / name
        reader = Reader(path, read_graphic_params=True)
        frame = GraphicRenderer.read_layer(path)
        assert len(frame) == expected, (name, len(frame), expected)
        assert frame.columns.is_unique, f"duplicate graphic columns: {name}"
        assert not frame.geometry.is_empty.any(), name
        assert not frame.geometry.isna().any(), name
        assert frame.geometry.is_valid.all(), name
        if name == "CWELL_GEO_WP.WP":
            for field in ("LABL", "QDUECC", "QDUECD", "CHFCAC", "PLABL", "NAME"):
                assert field in frame.columns, field
            assert frame["LABL"].nunique() == 56
        # MapGIS's SHP importer may leave CRS empty. Assign the source UTM CRS
        # only when the native header has no usable CRS; repaired files retain
        # their own parsed spatial reference without changing any coordinates.
        if frame.crs in (None, ""):
            frame = frame.set_crs(TARGET_CRS, allow_override=True)
        elif reader.crs.to_epsg() != 32611:
            raise ValueError(f"Unexpected native CRS in {name}: {reader.crs}")
        frame.attrs["source"] = name
        frame.attrs["kind"] = path.suffix.lower().lstrip(".")
        layers.append(frame)
        reports.append({
            "file": name,
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "features": len(frame),
            "geometry_types": frame.geometry.geom_type.value_counts().to_dict(),
            "empty_geometries": int(frame.geometry.is_empty.sum()),
            "invalid_geometries": int((~frame.geometry.is_valid).sum()),
            "attribute_columns": list(reader.data.columns),
            "bounds": list(frame.total_bounds),
            "native_crs": str(reader.crs),
            "native_epsg": reader.crs.to_epsg() if reader.crs not in (None, "") else None,
            "native_coordinate_scale_factor": reader.coordinate_scale_factor,
            "render_crs": TARGET_CRS,
        })
    return layers, reports


def render_six_layers(layers, output_dir, dpi=160, formats=("png", "pdf", "svg"), label_field=None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if label_field not in (None, "LABL", "QDUECC", "QDUECD", "CHFCAC"):
        raise ValueError(f"Unsupported label field: {label_field}")

    # The original six-file fixture contains the provisional USGS ORN mapping
    # (one SLIB 1281 double-tick per source point). Build the corrected native
    # representation in memory: two opposing SLIB 239 half-arrows per source
    # point, aligned to the nearest fault. Reader hashes and source counts stay
    # unchanged; the render report distinguishes source and graphic records.
    by_source = {layer.attrs["source"]: layer for layer in layers}
    prepared_layers = []
    for layer in layers:
        if layer.attrs["source"] == "CWELL_ORN_WT.WT":
            layer = expand_left_slip_ornaments(
                layer, by_source["CWELL_GEO_WL.WL"]
            )
        prepared_layers.append(layer)

    renderer = GraphicRenderer(
        GraphicLibraries.from_directory(slib_path()),
        scale=24000,
        polygon_labels=label_field is not None,
        polygon_label_avoid_collisions=label_field is not None,
        polygon_label_randomize=label_field is not None,
        polygon_label_seed=42,
        polygon_label_buffer_pt=2.0,
        polygon_label_max_offset_pt=24.0,
        polygon_label_fields=(label_field,) if label_field else ("QDUECC", "QDUECD"),
        unit_code_fields=(label_field,) if label_field else ("QDUECC", "QDUECD"),
        native_text_layout=False,
        exclude_text_categories=(),
    )
    result = renderer.render(
        prepared_layers, output_dir / "cwell_six_map.png", figsize=(12, 9), dpi=dpi
    )
    metadata_by_source = {
        layer.attrs["source"]: layer.attrs for layer in prepared_layers
    }
    for report in result.reports:
        metadata = metadata_by_source[report["source"]]
        if "source_feature_count" in metadata:
            report["source_features"] = metadata["source_feature_count"]
            report["nearest_fault_distances_m"] = metadata[
                "nearest_fault_distances_m"
            ]
    fig = result.figure
    for fmt in formats:
        fig.savefig(output_dir / f"cwell_six_map.{fmt}", format=fmt, dpi=dpi)
    fig.clear()
    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=None)
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path("output/usgs_conejo/six_file_tests"),
    )
    parser.add_argument("--dpi", type=int, default=160)
    parser.add_argument(
        "--label-field",
        choices=("LABL", "QDUECC", "QDUECD", "CHFCAC"),
        default=None,
        help="Optional polygon-label field; omit for vector-only output",
    )
    args = parser.parse_args()

    layers, reader_reports = read_six_layers(args.input_dir)
    result = render_six_layers(layers, args.output_dir, dpi=args.dpi, label_field=args.label_field)
    summary = summarise(result.reports)
    (args.output_dir / "reader_report.json").write_text(
        json.dumps(reader_reports, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / "render_report.json").write_text(
        json.dumps({"summary": summary, "layers": result.reports,
                    "label_field": args.label_field}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.output_dir / "README.md").write_text(
        "# 六文件 Reader 与渲染测试\n\n"
        "仅使用 testdata 原始六层，无 lab 文件、无人工配色覆盖。\n\n"
        "Reader 使用 `read_graphic_params=True`；渲染使用 `D:/SLIB/SLIB`。\n"
        "原始 SHP 导入文件若没有有效 CRS，渲染前显式赋予 EPSG:32611；"
        "UTM 修补版直接使用 Reader 解析的原生 CRS，坐标不变。\n"
        "WP 的 LABL/QDUECC/QDUECD/CHFCAC 等地质代号字段已核验，共 56 类。\n"
        "ORN 原始临时映射为 2 个 1281 双短线；修正输出按最近断层切线展开为 "
        "4 个 SLIB 239 半箭头（两个左行符号各一对），source_id 保持不变。\n"
        "summary.source_features=8804 为源要素数，features/drawn=8806 为修正后的图形记录数。\n\n"
        f"```json\n{json.dumps(summary, ensure_ascii=False, indent=2)}\n```\n",
        encoding="utf-8",
    )
    print(json.dumps({"reader_layers": len(reader_reports), "render_summary": summary},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
