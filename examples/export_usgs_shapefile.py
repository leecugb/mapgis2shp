#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Export the real USGS Conejo Well source data directly to Shapefile.

This path deliberately bypasses the native MapGIS Writer.  It provides a UTM
set and a MapGIS-friendly Gauss-Kruger k=1 set, with GBK DBF text and explicit
field aliases for the Shapefile ten-character field-name limit.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyproj

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.convert_usgs_conejo import LAYER_NAMES, TARGET_CRS, load_layers  # noqa: E402

GAUSS_KRUGER_CRS = pyproj.CRS.from_proj4(
    "+proj=tmerc +lat_0=0 +lon_0=-117 +k=1 +x_0=500000 +y_0=0 "
    "+datum=WGS84 +units=m +no_defs"
)
VARIANTS = {"utm11": TARGET_CRS, "gauss_kruger_117w": GAUSS_KRUGER_CRS}
FIELD_ALIASES = {
    "pattern_height": "PATTERN_H",
    "pattern_width": "PATTERN_W",
    "pattern_color": "PATTERN_C",
    "aux_linetype": "AUX_LTYPE",
    "transparent": "TRANSPAR",
    "L_DEFINITION": "L_DEF",
    "FEATURE_TYPE": "FEAT_TYPE",
    "annotation_flag": "ANNO_FLAG",
}


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _shp_filename(name):
    path = Path(name)
    return f"{path.stem}_{path.suffix.lower().lstrip('.')}.shp"


def _shapefile_frame(layer, target_crs):
    frame = layer.to_crs(target_crs) if layer.crs != target_crs else layer.copy()
    frame = frame.rename(columns=FIELD_ALIASES)
    names = [name for name in frame.columns if name != "geometry"]
    assert all(len(name) <= 10 for name in names), names
    assert len(names) == len(set(names)), names
    frame.attrs.update(layer.attrs)
    return frame


def export_shapefiles(layers, output_dir, encoding="GBK"):
    """Write both CRS variants and return the per-layer output paths."""
    output_dir = Path(output_dir)
    outputs = {}
    for variant, crs in VARIANTS.items():
        directory = output_dir / variant
        directory.mkdir(parents=True, exist_ok=True)
        for name in LAYER_NAMES:
            frame = _shapefile_frame(layers[name], crs)
            path = directory / _shp_filename(name)
            frame.to_file(path, driver="ESRI Shapefile", encoding=encoding, engine="pyogrio")
            outputs[f"{variant}/{name}"] = path
    return outputs


def verify_shapefiles(layers, output_dir, encoding="GBK"):
    """Read back every SHP and compare counts, geometry, CRS and attributes."""
    output_dir = Path(output_dir)
    checked = {}
    for variant, crs in VARIANTS.items():
        for name in LAYER_NAMES:
            path = output_dir / variant / _shp_filename(name)
            expected = _shapefile_frame(layers[name], crs)
            actual = gpd.read_file(path, encoding=encoding, engine="pyogrio")
            assert len(actual) == len(expected), (variant, name, len(actual), len(expected))
            assert pyproj.CRS(actual.crs).equals(pyproj.CRS(crs)), (variant, name, actual.crs)
            expected_fields = [name for name in expected.columns if name != "geometry"]
            actual_fields = [name for name in actual.columns if name != "geometry"]
            assert actual_fields == expected_fields, (variant, name)
            for column in expected.columns:
                if column == "geometry":
                    continue
                left = actual[column]
                right = expected[column]
                if (pd.api.types.is_string_dtype(left.dtype)
                        or pd.api.types.is_object_dtype(left.dtype)):
                    # DBF reads zero-length text as NULL; both represent the
                    # same empty source value. All non-empty text stays strict.
                    left = left.fillna("").astype(str)
                    right = right.fillna("").astype(str)
                pd.testing.assert_series_equal(
                    left, right, check_names=False,
                    check_dtype=False, check_exact=False, rtol=1e-7, atol=1e-7,
                )
            if variant == "utm11":
                comparisons = zip(actual.geometry, expected.geometry)
                assert all(a.equals_exact(b, 1e-7) for a, b in comparisons), (variant, name)
            else:
                restored = actual.to_crs(TARGET_CRS)
                comparisons = zip(restored.geometry, layers[name].geometry)
                assert all(a.hausdorff_distance(b) < 1e-4 for a, b in comparisons), (variant, name)
            for suffix in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
                assert path.with_suffix(suffix).is_file(), path.with_suffix(suffix)
            checked[f"{variant}/{name}"] = len(actual)
    return checked


def write_documentation(layers, output_dir, encoding="GBK"):
    output_dir = Path(output_dir)
    with (output_dir / "field_mapping.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["layer", "original_field", "shp_field"])
        for name in LAYER_NAMES:
            for column in layers[name].columns:
                if column != "geometry":
                    writer.writerow([name, column, FIELD_ALIASES.get(column, column)])

    files = sorted(path for path in output_dir.rglob("*") if path.is_file())
    manifest = {
        "source": "USGS Open-File Report 01-031",
        "source_url": "https://pubs.usgs.gov/of/2001/of01-031/",
        "conversion_path": (
            "USGS E00 -> GeoDataFrame -> ESRI Shapefile; "
            "native MapGIS Writer bypassed"
        ),
        "dbf_encoding": encoding,
        "field_aliases": FIELD_ALIASES,
        "crs_variants": {
            "utm11": "EPSG:32611 (WGS84 UTM zone 11N)",
            "gauss_kruger_117w": GAUSS_KRUGER_CRS.to_wkt(),
        },
        "layers": {name: len(layer) for name, layer in layers.items()},
        "files": {
            str(path.relative_to(output_dir)): _sha256(path)
            for path in files if path.suffix.lower() in {".shp", ".dbf", ".prj", ".cpg", ".shx"}
        },
        "graphic_parameter_note": (
            "SHP retains graphic parameters as attributes. MapGIS import must "
            "explicitly apply fill_color, linetype, color, width, symbol_no, "
            "height, width, angle and point_type; SHP has no SLIB display rules."
        ),
    }
    (output_dir / "shapefile_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    readme = """# USGS Conejo Well Shapefile 数据包

## 用途

本包直接从 USGS E00 生成 SHP，**没有经过有兼容性疑问的 MapGIS Writer**。
用于在其他电脑的 MapGIS 软件中重新导入并生成原生 WT/WL/WP。

## 坐标版本

- `gauss_kruger_117w/`：推荐用于 MapGIS。WGS84，横轴墨卡托，
  中央经线 −117°，k=1，假东 500000 m，假北 0 m，单位米。
- `utm11/`：WGS84 UTM Zone 11N，EPSG:32611。

MapGIS 6.x 不保存 UTM 的 0.9996 比例因子，因此优先使用 Gauss–Krüger
版本，或在导入时手工输入上述投影参数。

## 图层

- `cwell_geo_wp.shp`：地质面。
- `cwell_geo_wl.shp`：地质界线、断层和图廓。
- `cwell_dk_wl.shp`：岩脉线。
- `cwell_str_wt.shp`：产状符号点。
- `cwell_str_lab_wt.shp`：倾角/倾伏角注记点。
- `cwell_orn_wt.shp`：辅助点。
- `cwell_ldr_wl.shp`：引线。
- `cwell_lab_wt.shp`：地质代号注记点。

每个坐标目录均包含上述八个 SHP；原始图层对应关系见
`shapefile_manifest.json` 的 `layers`。

## 编码与字段

- DBF 使用 **GBK**，`.cpg` 一并提供。
- Shapefile 字段名上限为 10 字符，完整对照见 `field_mapping.csv`。
- `PATTERN_H/PATTERN_W/PATTERN_C` 分别对应 pattern_height/width/color。
- `AUX_LTYPE` 对应 aux_linetype，`TRANSPAR` 对应 transparent。
- `L_DEF` 对应 L_DEFINITION，`FEAT_TYPE` 对应 FEATURE_TYPE。
- `ANNO_FLAG` 对应 annotation_flag，用于区分代号和产状注记类别。

## MapGIS 导入时必须检查

SHP 不保存 MapGIS/SLIB 显示规则，只把图形参数保留为字段。导入后请按字段
重新指定，不要期待 SHP 自动恢复配色与符号：

1. WP：`fill_color`、`pattern`、`PATTERN_H/PATTERN_W/PATTERN_C`。
2. WL：`linetype`、`color`、`width`、`AUX_LTYPE`、系数和透明字段。
3. WT 子图点：`point_type=1`，使用 `symbol_no`、`height`、`width`、`angle`。
4. WT 注记点：`point_type=0`，文本在 `CHFCED`，类别在 `CHFCEC`。
   `cwell_lab` 是地质代号；`cwell_str_lab` 是倾角/倾伏角，不能当作普通子图点。
5. 原始 USGS 字段 `SHDPS/SHDFIL/L_SYMB/P_SYMB` 仍保留，但它们不是
   MapGIS SLIB 编号，不要直接混用。

导入后先保存，再关闭并重新打开原生文件，检查全部图层、代号、产状数字、
孔洞和投影。产状子图 1245/1281 仍是暂定映射；左行辅助点已按最近断层
切线展开为成对 SLIB 239 半箭头，仍需对照 USGS 原图目视复核。

## 来源与限制

USGS Open-File Report 01-031，Powell 与 Cossette，2001，Version 1.0：
https://pubs.usgs.gov/of/2001/of01-031/

保留 USGS 来源、元数据、分辨率及免责声明。转换和专题配色不代表 USGS
对转换结果背书。本包不包含 D:/SLIB/SLIB 图形库。
"""
    (output_dir / "README_SHP.md").write_text(readme, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("work_usgs/e00/tempfiles"))
    parser.add_argument("--output-dir", type=Path, default=Path("output/usgs_conejo/shp"))
    parser.add_argument("--encoding", default="GBK")
    args = parser.parse_args()

    layers = load_layers(args.source)
    export_shapefiles(layers, args.output_dir, encoding=args.encoding)
    checked = verify_shapefiles(layers, args.output_dir, encoding=args.encoding)
    write_documentation(layers, args.output_dir, encoding=args.encoding)
    print(json.dumps({"output_dir": str(args.output_dir), "verified": checked},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
