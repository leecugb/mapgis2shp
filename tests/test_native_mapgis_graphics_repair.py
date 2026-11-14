"""Regression test for repairing MapGIS-produced native graphic parameters."""
from pathlib import Path

import pytest

from examples.repair_native_mapgis_graphics import (
    LAYER_NAMES,
    NATIVE_FILES,
    read_repaired_layers,
    repair_file,
)
from pymapgis import Reader

SOURCE = Path(r"F:/1111/usgs_conejo_shp/usgs_conejo_shp/gauss_kruger_117w")


def test_mapgis_native_graphic_repair(tmp_path):
    if not SOURCE.is_dir():
        pytest.skip("MapGIS-produced Conejo Well files are not available")
    reports = {}
    for name in LAYER_NAMES:
        native_name, shp_name = NATIVE_FILES[name]
        report = repair_file(SOURCE / native_name, SOURCE / shp_name, tmp_path / native_name)
        reports[native_name] = report
        assert report["native_params_verified"] is True
        assert report["unrelated_bytes_unchanged"] is True
        assert report["changed_bytes"] > 0

    polygons = Reader(tmp_path / "CWELL_GEO_WP.WP", read_graphic_params=True).polygon_params
    assert polygons.iloc[0]["fill_color"] == 602
    assert polygons.iloc[0]["class"] == 3  # native anomaly is preserved
    assert polygons.iloc[1]["class"] == 2
    assert polygons["pattern_color"].eq(0).all()
    assert polygons["layer"].eq(0).all()
    labels = Reader(tmp_path / "CWELL_LAB_WT.WT", read_graphic_params=True).point_params
    assert (labels["point_type"] == 0).all()
    assert (labels["symbol_no"] == 0).all()
    attitudes = Reader(tmp_path / "CWELL_STR_LAB_WT.WT", read_graphic_params=True).point_params
    assert len(attitudes) == 23
    assert (attitudes["point_type"] == 0).all()
    assert attitudes.iloc[0]["height"] == 5
    lines = Reader(tmp_path / "CWELL_GEO_WL.WL", read_graphic_params=True).line_params
    assert (lines["color"] == 175).sum() == 664
    assert ((lines["width"] - 0.18).abs() < 1e-6).sum() == 664

    layers = read_repaired_layers(tmp_path, SOURCE)
    labels = layers["cwell_lab.WT"]
    assert len(labels) == 2498
    assert (labels["CHFCED"] == labels["LABL"]).all()
    assert not labels["CHFCED"].str.startswith(("<", "^")).any()
    assert labels["CHFCED"].str.len().max() == 13
    assert (labels["CHFCEC"] == "代号").all()
    attitude_labels = layers["cwell_str_lab.WT"]
    assert attitude_labels.iloc[0]["CHFCED"] == "51"
    assert attitude_labels.iloc[0]["CHFCEC"] == "产状"
