"""Regression tests for the 2026-11-25 package audit findings."""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, Point, Polygon

from pymapgis import ColorLib, Reader, Writer, WriterError


@pytest.mark.parametrize(
    ("geometry", "suffix"),
    [
        (Point(np.nan, 1.0), ".wt"),
        (LineString([(0.0, 0.0), (np.inf, 1.0)]), ".wl"),
        (Polygon([(0.0, 0.0), (np.inf, 0.0), (0.0, 1.0), (0.0, 0.0)]), ".wp"),
    ],
)
def test_writer_rejects_nonfinite_coordinates(tmp_path, geometry, suffix):
    frame = gpd.GeoDataFrame(geometry=[geometry], crs="EPSG:4326")
    with pytest.raises(WriterError, match="non-finite coordinates"):
        Writer(frame).to_file(tmp_path / f"bad{suffix}")


def test_preserved_int32_metadata_out_of_range_raises_writer_error(tmp_path):
    source = gpd.GeoDataFrame(
        {"code": pd.array([1, 2], dtype="int32")},
        geometry=[Point(0, 0), Point(1, 1)],
        crs="EPSG:4326",
    )
    source_path = tmp_path / "source.wt"
    Writer(source).to_file(source_path)
    edited = Reader(source_path).geodataframe
    edited.loc[0, "code"] = 2**40

    with pytest.raises(WriterError, match="cannot encode"):
        Writer(edited).to_file(tmp_path / "edited.wt")


def test_numpy_float32_nan_is_written_as_missing_string(tmp_path):
    frame = gpd.GeoDataFrame(
        {"value": pd.Series([np.float32("nan")], dtype=object)},
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )
    output = tmp_path / "missing.wt"
    Writer(frame).to_file(output)
    assert Reader(output).data.iloc[0]["value"] == ""


def test_point_layer_out_of_range_raises_writer_error(tmp_path):
    frame = gpd.GeoDataFrame(
        {"point_type": [1], "layer": [256]},
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )
    with pytest.raises(WriterError, match="layer must be an integer in 0..255"):
        Writer(frame).to_file(tmp_path / "point.wt")


def test_line_width_must_be_finite(tmp_path):
    frame = gpd.GeoDataFrame(
        {"linetype": [1], "width": [np.inf]},
        geometry=[LineString([(0, 0), (1, 1)])],
        crs="EPSG:4326",
    )
    with pytest.raises(WriterError, match="width must be finite"):
        Writer(frame).to_file(tmp_path / "line.wl")


def test_polygon_fill_color_out_of_range_raises_writer_error(tmp_path):
    polygon = Polygon([(0, 0), (1, 0), (0, 1), (0, 0)])
    frame = gpd.GeoDataFrame(
        {"fill_color": [65536]},
        geometry=[polygon],
        crs="EPSG:4326",
    )
    with pytest.raises(WriterError, match="fill_color must be an integer in 0..65535"):
        Writer(frame).to_file(tmp_path / "polygon.wp")


def test_colorlib_rejects_wrong_signature(tmp_path):
    path = tmp_path / "Colorlib.lib"
    path.write_bytes(b"X" * 32)
    with pytest.raises(ValueError, match="Colorg signature"):
        ColorLib(str(path))
