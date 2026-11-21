"""Regression tests for direct USGS E00-to-Shapefile export."""
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

from examples.convert_usgs_conejo import LAYER_NAMES, load_layers
from examples.export_usgs_shapefile import (
    FIELD_ALIASES,
    _shapefile_frame,
    _shp_filename,
    export_shapefiles,
    verify_shapefiles,
)
from pymapgis.testing import usgs_conejo_path


def _source_dir():
    try:
        return usgs_conejo_path("source")
    except FileNotFoundError:
        return Path("work_usgs/e00/tempfiles")


SOURCE = _source_dir()


def test_shapefile_names_and_field_aliases():
    assert _shp_filename("cwell_geo.WP") == "cwell_geo_wp.shp"
    assert _shp_filename("cwell_geo.WL") == "cwell_geo_wl.shp"
    frame = gpd.GeoDataFrame(
        {name: [1] for name in FIELD_ALIASES}, geometry=[Point(0, 0)],
        crs="EPSG:32611",
    )
    converted = _shapefile_frame(frame, "EPSG:32611")
    assert set(converted.columns) == set(FIELD_ALIASES.values()) | {"geometry"}
    assert all(len(name) <= 10 for name in converted.columns)


def test_real_usgs_shapefile_roundtrip(tmp_path):
    if not SOURCE.is_dir():
        pytest.skip("USGS Conejo Well source archive is not downloaded")
    layers = load_layers(SOURCE)
    export_shapefiles(layers, tmp_path)
    checked = verify_shapefiles(layers, tmp_path)
    assert len(checked) == 2 * len(LAYER_NAMES)
    assert checked["utm11/cwell_geo.WP"] == 2498
    assert checked["gauss_kruger_117w/cwell_str_lab.WT"] == 23
    assert (tmp_path / "gauss_kruger_117w/cwell_geo_wp.shp").is_file()
    assert (tmp_path / "gauss_kruger_117w/cwell_geo_wl.shp").is_file()
