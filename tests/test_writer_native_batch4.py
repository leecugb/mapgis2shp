"""Batch-4 native Writer evidence without inheriting native conversion defects."""
from __future__ import annotations

import math

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest

from pymapgis import Reader, Writer, WriterError
from pymapgis.testing import fixture_path

FIXTURE_ROOT = fixture_path("writer_batch4")
CASES = sorted(FIXTURE_ROOT.glob("*.shp"))
GRAPHIC_FIELDS = {
    "class", "fill_color", "pattern", "pattern_height", "pattern_width",
    "pattern_color", "layer", "field5", "field6", "field7", "linetype",
    "aux_linetype", "aux_flag", "color", "width", "x_coef", "y_coef",
    "aux_color", "transparent", "point_type", "symbol_no", "height",
    "spacing", "angle", "pen_width", "font_zh", "font_en", "font_style",
    "面积", "周长", "长度",
}


def kind(shp):
    if shp.stem.startswith(("01", "02", "03", "04")):
        return "POINT", ".WT"
    if shp.stem.startswith(("05", "06", "07", "08")):
        return "LINE", ".WL"
    return "POLYGON", ".WP"


def output_path(shp, tmp_path):
    geometry_type, suffix = kind(shp)
    return tmp_path / (shp.stem + suffix.lower()), geometry_type


def read_output(path):
    return Reader(str(path), read_graphic_params=True, read_point_params=True).geodataframe


def scalar_equal(left, right):
    try:
        if pd.isna(left):
            left = None
        if pd.isna(right):
            right = None
    except (TypeError, ValueError):
        pass
    if isinstance(left, str):
        left = left.strip() or None
    if isinstance(right, str):
        right = right.strip() or None
    if left is None or right is None:
        return left is right
    if isinstance(left, (int, float, np.number)) and isinstance(right, (int, float, np.number)):
        return math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-9)
    return left == right


def assert_attributes(source, actual, ignore_fields=()):
    ignored = set(ignore_fields)
    for index, row in source.iterrows():
        for field in source.columns:
            if field in ignored or field in GRAPHIC_FIELDS or field == "geometry":
                continue
            assert scalar_equal(row[field], actual.iloc[index][field]), (
                index, field, row[field], actual.iloc[index][field]
            )


def write_and_read(source, output, geometry_type):
    Writer(source, geometry_type=geometry_type).to_file(output)
    return read_output(output)


@pytest.mark.parametrize("shp", CASES, ids=lambda path: path.stem)
def test_batch4_writer_source_fidelity(shp, tmp_path):
    output, geometry_type = output_path(shp, tmp_path)
    source = gpd.read_file(shp, encoding="GBK")
    if shp.stem in {"07_LINE_EMPTY", "15_POLY_EMPTY"}:
        with pytest.raises(WriterError, match="empty/null geometries"):
            Writer(source, geometry_type=geometry_type).to_file(output)
        mask = source.geometry.isna() | source.geometry.is_empty
        source = source.loc[~mask].reset_index(drop=True)
        ours = write_and_read(source, output, geometry_type)
    elif shp.stem == "14_POLY_DEGENERATE":
        with pytest.raises(WriterError, match="fewer than three distinct vertices"):
            Writer(source, geometry_type=geometry_type).to_file(output)
        return
    elif shp.stem == "20_EMPTY_FILE":
        ours = write_and_read(source, output, geometry_type)
        assert len(ours) == 0
        return
    else:
        ours = write_and_read(source, output, geometry_type)

    expected = source
    if shp.stem == "03_POINT_MULTIPOINT":
        with pytest.warns(UserWarning, match="MultiPoint exploded"):
            output.unlink()
            ours = write_and_read(source, output, geometry_type)
        expected = source.explode(index_parts=False)
    elif shp.stem == "06_LINE_MULTI_DUPLICATE":
        expected = source.explode(index_parts=False)
        assert len(ours) == 3

    assert len(ours) == len(expected)
    if shp.stem == "03_POINT_MULTIPOINT":
        assert ours.ID.tolist() == [1, 1, 2]
        assert_attributes(expected, ours, ignore_fields={"ID"})
    else:
        assert_attributes(expected, ours)
    if shp.stem == "13_POLY_BOWTIE":
        native = read_output(FIXTURE_ROOT / "13_POLY_BOWTIE.WP")
        assert [geom.wkt for geom in ours.geometry] == [geom.wkt for geom in native.geometry]
    else:
        for expected_geom, actual_geom in zip(expected.geometry, ours.geometry):
            assert expected_geom.equals(actual_geom)


def test_batch4_native_default_point_and_line_styles(tmp_path):
    for name in ("01_POINT_BASIC", "02_POINT_ATTR_NULL", "04_POINT_257"):
        source = gpd.read_file(FIXTURE_ROOT / f"{name}.shp", encoding="GBK")
        ours = write_and_read(source, tmp_path / f"{name}.wt", "POINT")
        native = read_output(FIXTURE_ROOT / f"{name}.WT")
        for field in ("point_type", "symbol_no", "height", "width", "color", "pen_width"):
            assert ours[field].tolist() == native[field].tolist()
    for name in ("05_LINE_BASIC", "08_LINE_10001_VERTICES"):
        source = gpd.read_file(FIXTURE_ROOT / f"{name}.shp", encoding="GBK")
        ours = write_and_read(source, tmp_path / f"{name}.wl", "LINE")
        native = read_output(FIXTURE_ROOT / f"{name}.WL")
        for field in ("linetype", "aux_linetype", "aux_flag", "color", "width", "x_coef", "y_coef"):
            assert ours[field].tolist() == native[field].tolist()


def test_batch4_large_ring_offset_matches_native(tmp_path):
    source = gpd.read_file(FIXTURE_ROOT / "17_POLY_LARGE_RING.shp", encoding="GBK")
    ours = write_and_read(source, tmp_path / "large.wp", "POLYGON")
    native = read_output(FIXTURE_ROOT / "17_POLY_LARGE_RING.WP")

    def offset(frame):
        return (
            int(frame.field5.iloc[0])
            + (int(frame.field6.iloc[0]) << 8)
            + (int(frame.field7.iloc[0]) << 16)
        )

    assert offset(ours) == offset(native) == 81650


def test_batch4_native_09_topology_defect_not_reused(tmp_path):
    source = gpd.read_file(FIXTURE_ROOT / "09_POLY_BASIC.shp", encoding="GBK")
    ours = write_and_read(source, tmp_path / "basic.wp", "POLYGON")
    native = read_output(FIXTURE_ROOT / "09_POLY_BASIC.WP")
    assert ours.geometry.iloc[0].equals(source.geometry.iloc[0])
    assert ours.geometry.iloc[1].equals(source.geometry.iloc[1])
    assert native.geometry.iloc[0].geom_type == "MultiPolygon"
    assert native.geometry.iloc[0].area == 15000
    assert ours.geometry.iloc[0].area == 5000


def test_batch4_native_07_empty_lines_contain_foreign_geometry(tmp_path):
    source = gpd.read_file(FIXTURE_ROOT / "07_LINE_EMPTY.shp", encoding="GBK")
    native = read_output(FIXTURE_ROOT / "07_LINE_EMPTY.WL")
    previous = gpd.read_file(FIXTURE_ROOT / "06_LINE_MULTI_DUPLICATE.shp", encoding="GBK")
    assert native.geometry.iloc[1].equals(previous.geometry.iloc[1].geoms[0])
    assert native.geometry.iloc[2].equals(previous.geometry.iloc[1].geoms[1])
    with pytest.raises(WriterError, match="empty/null geometries"):
        Writer(source, geometry_type="LINE").to_file(tmp_path / "empty.wl")
    Writer(source, on_empty="drop", geometry_type="LINE").to_file(tmp_path / "empty.wl")
    ours = read_output(tmp_path / "empty.wl")
    assert len(ours) == 1
    assert ours.geometry.iloc[0].equals(source.geometry.iloc[0])


def test_batch4_native_06_drops_multiline_part(tmp_path):
    source = gpd.read_file(FIXTURE_ROOT / "06_LINE_MULTI_DUPLICATE.shp", encoding="GBK")
    ours = write_and_read(source, tmp_path / "multi.wl", "LINE")
    native = read_output(FIXTURE_ROOT / "06_LINE_MULTI_DUPLICATE.WL")
    assert len(native) == 2
    assert len(ours) == 3
    assert ours.geometry.iloc[2].equals(source.geometry.iloc[1].geoms[1])


def test_batch4_nonfinite_and_null_values_not_coerced_to_zero(tmp_path):
    source = gpd.read_file(FIXTURE_ROOT / "02_POINT_ATTR_NULL.shp", encoding="GBK")
    ours = write_and_read(source, tmp_path / "attrs.wt", "POINT")
    native = read_output(FIXTURE_ROOT / "02_POINT_ATTR_NULL.WT")
    assert native.FLOAT64.tolist() == [0, 0, 0]
    assert np.isnan(ours.FLOAT64.iloc[0])
    assert ours.FLOAT64.iloc[1] == np.inf
    assert ours.FLOAT64.iloc[2] == -np.inf

    source16 = gpd.read_file(FIXTURE_ROOT / "16_POLY_80_FIELDS.shp", encoding="GBK")
    ours16 = write_and_read(source16, tmp_path / "fields.wp", "POLYGON")
    native16 = read_output(FIXTURE_ROOT / "16_POLY_80_FIELDS.WP")
    assert pd.isna(ours16.FIELD_01.iloc[2])
    assert native16.FIELD_01.iloc[2] == 0


def test_batch4_metrics_follow_actual_geometry_not_native_errors(tmp_path):
    names = (
        "09_POLY_BASIC", "10_POLY_HOLE_MULTIPART",
        "11_POLY_SHARED_ISLAND", "18_POLY_DUPLICATE_ATTRIBUTES",
    )
    for name in names:
        source = gpd.read_file(FIXTURE_ROOT / f"{name}.shp", encoding="GBK")
        ours = write_and_read(source, tmp_path / f"{name}.wp", "POLYGON")
        for row in ours.itertuples():
            assert math.isclose(row.面积, row.geometry.area, rel_tol=1e-9, abs_tol=1e-9)
            assert math.isclose(row.周长, row.geometry.length, rel_tol=1e-9, abs_tol=1e-9)


def test_batch4_writer_preserves_gauss_kruger_crs(tmp_path):
    source = gpd.read_file(FIXTURE_ROOT / "01_POINT_BASIC.shp", encoding="GBK")
    ours = write_and_read(source, tmp_path / "crs.wt", "POINT")
    native = read_output(FIXTURE_ROOT / "01_POINT_BASIC.WT")
    assert ours.crs is not None
    assert "+proj=tmerc" in ours.crs.to_proj4()
    assert "+lon_0=75" in ours.crs.to_proj4()
    assert native.crs in (None, "")
