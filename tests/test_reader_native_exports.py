"""Reader robustness against native SHP export representations from open JWD data."""

from __future__ import annotations

import math
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest

from pymapgis import Reader
from pymapgis.testing import fixture_path, jwd_path


def _reader_native_root():
    configured = os.environ.get("PYMAPGIS_READER_NATIVE")
    if configured:
        return Path(configured)
    try:
        return fixture_path("reader_native")
    except FileNotFoundError as exc:
        pytest.skip(
            f"Optional native SHP integration is unavailable: {exc}. "
            "Set PYMAPGIS_READER_NATIVE after obtaining the original exports.",
            allow_module_level=True,
        )


ROOT = _reader_native_root()
POINT_AND_LINE = ("LDLYAAI002", "LDZOFBA002", "LDZOFBB099")
POLYGONS = ("LDZOFBB001", "LDZOFBB004")


def read_jwd(name):
    candidate = ROOT / name
    path = candidate if candidate.exists() else jwd_path(name)
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
        return math.isclose(float(left), float(right), rel_tol=1e-7, abs_tol=5.1e-7)
    return left == right


def assert_shared_attributes(native, exported):
    for field in [
        name for name in native.columns if name in exported.columns and name != "geometry"
    ]:
        for index, (left, right) in enumerate(zip(native[field], exported[field])):
            assert scalar_equal(left, right), (field, index, left, right)


@pytest.mark.parametrize("name", POINT_AND_LINE)
def test_reader_point_and_line_match_native_shp(name):
    extension = ".WT" if name in {"LDLYAAI002", "LDZOFBB099"} else ".WL"
    native = read_jwd(name + extension)
    exported = gpd.read_file(ROOT / f"{name}.SHP", encoding="GBK")
    assert len(native) == len(exported)
    for left, right in zip(native.geometry, exported.geometry):
        assert left.equals(right)
    assert_shared_attributes(native, exported)
    assert exported.crs is None


@pytest.mark.parametrize("name", POLYGONS)
def test_reader_polygon_coverage_and_attributes_remain_valid(name):
    native = read_jwd(name + ".WP")
    exported = gpd.read_file(ROOT / f"{name}.SHP", encoding="GBK")
    assert len(native) == len(exported)
    assert int((~native.geometry.is_valid).sum()) == 0
    for left, right in zip(native.geometry, exported.geometry):
        if right is None or right.is_empty:
            continue
        assert left.hausdorff_distance(right) <= 5.1e-7
    assert_shared_attributes(native, exported)
    assert exported.crs is None


def test_reader_does_not_inherit_shp_invalid_polygon_merges():
    native = read_jwd("LDZOFBB001.WP")
    exported = gpd.read_file(ROOT / "LDZOFBB001.SHP", encoding="GBK")
    assert int((~native.geometry.is_valid).sum()) == 0
    assert int((~exported.geometry.is_valid).sum()) == 87
    assert native.geometry.iloc[0].geom_type == "MultiPolygon"
    assert exported.geometry.iloc[0].geom_type == "Polygon"


def test_reader_recovers_polygon_missing_from_shp():
    native = read_jwd("LDZOFBB004.WP")
    exported = gpd.read_file(ROOT / "LDZOFBB004.SHP", encoding="GBK")
    assert exported.geometry.iloc[48] is None
    assert native.geometry.iloc[48].is_valid
    assert native.geometry.iloc[48].area > 0


def test_reader_attribute_values_match_shp_not_wat_text_anomalies():
    native = read_jwd("LDZOFBB099.WT")
    exported = gpd.read_file(ROOT / "LDZOFBB099.SHP", encoding="GBK")
    for index, expected in ((988, "D"), (989, "ι"), (991, "D"), (992, "ι")):
        assert native.CHFCED.iloc[index] == expected
        assert exported.CHFCED.iloc[index] == expected
