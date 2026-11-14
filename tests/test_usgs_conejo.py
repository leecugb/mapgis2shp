"""Regression tests for the real USGS Conejo Well MapGIS conversion."""
import os
import struct
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pytest
from shapely.geometry import Point, Polygon

from examples.convert_usgs_conejo import (
    LAYER_NAMES,
    _draw_overview_labels,
    _polygon_class,
    load_layers,
    read_layers,
    render_layers,
    select_overview_labels,
    unit_color,
    write_layers,
)
from examples.render_bundled_jwd import summarise
from pymapgis import GraphicRenderResult
from pymapgis.testing import usgs_conejo_path

pytestmark = pytest.mark.skipif(
    not (usgs_conejo_path() / "native").is_dir(),
    reason="optional native USGS comparison files are not included in this clean distribution",
)


def _source_dir():
    try:
        return usgs_conejo_path("source")
    except FileNotFoundError:
        return Path("work_usgs/e00/tempfiles")


SOURCE = _source_dir()


def test_usgs_access_metadata():
    metadata = (SOURCE.parent / "metadata/cwell_met.txt").read_text(encoding="utf-8")
    assert "Access_Constraints: None" in metadata
    assert "Metadata_Access_Constraints: none" in metadata
    assert "Metadata_Use_Constraints: none" in metadata
    assert unit_color("Qa") == 602
    assert unit_color("Pr") == 1096
    assert unit_color("TJh?") == 534
    assert unit_color("TrPmc") == 1226


def test_overview_label_layout_separates_complete_codes():
    polygons = gpd.GeoDataFrame(
        {"source_id": [1, 2], "LABL": ["Prjgg", "TrPmc"]},
        geometry=[
            Polygon([(0, 0), (100, 0), (100, 100), (0, 100)]),
            Polygon([(0, 0), (90, 0), (90, 90), (0, 90)]),
        ],
        crs="EPSG:32611",
    )
    labels = gpd.GeoDataFrame(
        {
            "source_id": [1, 2], "LABL": ["Prjgg", "TrPmc"],
            "CHFCED": ["Prjgg", "TrPmc"], "height": [2.0, 2.0],
        },
        geometry=[Point(50, 50), Point(50, 50)], crs="EPSG:32611",
    )
    candidates = select_overview_labels(polygons, labels)
    fig, ax = plt.subplots(figsize=(4, 4), dpi=80)
    try:
        ax.set(xlim=(0, 100), ylim=(0, 100))
        ax.set_aspect("equal")
        result = GraphicRenderResult(fig, ax, [], (0, 0, 100, 100))
        count, forced = _draw_overview_labels(result, candidates)
        assert count == 2
        assert forced == 0
        assert {text.get_text() for text in ax.texts} == {"Prjgg", "TrPmc"}
        assert len({text.get_position() for text in ax.texts}) == 2
    finally:
        plt.close(fig)


def test_fast_e00_geometry_and_info_tables():
    if not SOURCE.is_dir():
        pytest.skip("USGS Conejo Well source archive is not downloaded")
    from examples.e00_fast import read_coverage, read_info_tables

    coverage = read_coverage(str((SOURCE / "cwell_geo.e00").resolve()))
    assert {name: len(rows) for name, rows in coverage.items()} == {
        "ARC": 5991, "PAL": 2498, "LAB": 2498,
    }
    first = coverage["PAL"][0]
    assert first["ArcIds"] == [98, -97]
    assert first["LABL"] == "Qyas2,3"
    assert first["CWELL_GEO-ID"] == 1
    assert first["geometry"].area == pytest.approx(153.59204483032227)
    assert all(row["geometry"].is_valid for row in coverage["PAL"])
    assert coverage["ARC"][0]["L-TAG"] == "CL1"
    definitions = read_info_tables(SOURCE / "lines.rel.e00")["LINES.REL"]
    by_tag = {row["L-TAG"]: row["L-EXP"] for row in definitions}
    assert ".high-angle fault" in by_tag["F1"]
    assert ".sedimentary contact" in by_tag["C30"]


def test_usgs_native_conversion_and_render(tmp_path, monkeypatch):
    if not SOURCE.is_dir():
        pytest.skip("USGS Conejo Well source archive is not downloaded")
    slib = os.environ.get("PYMAPGIS_SLIB")
    if not slib and Path(r"D:\SLIB\SLIB").is_dir():
        slib = r"D:\SLIB\SLIB"
    if not slib:
        pytest.skip("Set PYMAPGIS_SLIB to the five official graphic libraries")
    monkeypatch.setenv("PYMAPGIS_SLIB", slib)
    layers = load_layers(SOURCE)
    assert tuple(layers) == LAYER_NAMES
    assert all(layer.crs == "EPSG:32611" for layer in layers.values())
    assert len(layers["cwell_geo.WP"]) == 2498
    assert layers["cwell_geo.WP"]["class"].to_numpy().tolist() == [
        _polygon_class(geometry) for geometry in layers["cwell_geo.WP"].geometry
    ]
    assert layers["cwell_geo.WP"]["pattern_color"].eq(0).all()
    assert layers["cwell_geo.WP"]["layer"].eq(0).all()
    assert len(layers["cwell_geo.WL"]) == 5991
    assert len(layers["cwell_str.WT"]) == 23
    assert len(layers["cwell_str_lab.WT"]) == 23
    ornaments = layers["cwell_orn.WT"]
    assert len(ornaments) == 4
    assert ornaments["source_id"].tolist() == [1, 1, 2, 2]
    assert ornaments["symbol_no"].eq(239).all()
    assert ornaments["angle"].iloc[1] - ornaments["angle"].iloc[0] == pytest.approx(180)
    assert ornaments["angle"].iloc[3] - ornaments["angle"].iloc[2] == pytest.approx(180)
    assert layers["cwell_geo.WP"]["LABL"].nunique() == 56
    assert layers["cwell_geo.WP"]["LABL"].notna().all()
    assert (layers["cwell_geo.WL"]["FEATURE_TYPE"] == "fault").sum() == 664
    attitudes = layers["cwell_str.WT"]
    planar = attitudes[attitudes["CHFCEC"] == "产状"]
    linear = attitudes[attitudes["CHFCEC"] == "线理"]
    assert len(planar) == 21
    assert len(linear) == 2
    cleavage = planar[planar["PTTYPE"] == "cleavage"].iloc[0]
    assert cleavage["GZBBAB"] == 75
    assert cleavage["GZBBAD"] == 51
    assert cleavage["CHFCED"] == ""
    annotations = layers["cwell_str_lab.WT"]
    assert (annotations["point_type"] == 0).all()
    assert (annotations["height"] == 6).all()
    assert (annotations["width"] == 6).all()
    assert annotations.iloc[0]["CHFCED"] == "51"
    assert annotations.iloc[0]["GZBBAD"] == 51
    assert not annotations.iloc[0].geometry.equals(attitudes.iloc[0].geometry)
    assert set(linear["P_PLUNGE"]) == {15, 20}
    assert (layers["cwell_lab.WT"]["CHFCED"] == layers["cwell_lab.WT"]["LABL"]).all()
    assert not layers["cwell_lab.WT"]["CHFCED"].str.startswith(("<", "^")).any()
    overview = select_overview_labels(
        layers["cwell_geo.WP"], layers["cwell_lab.WT"]
    )
    assert len(overview) == 650
    assert overview["LABL"].nunique() == 56
    assert (overview["height"] == 1.4).all()
    assert len(layers["cwell_lab.WT"]) == 2498
    assert layers["cwell_lab.WT"]["height"].eq(3).all()
    assert layers["cwell_lab.WT"]["width"].eq(3).all()

    write_layers(layers, tmp_path / "vectors")
    raw = (tmp_path / "vectors/cwell_str_lab.WT").read_bytes()
    assert struct.unpack_from("<d", raw, 143)[0] == 24000
    data_start = struct.unpack_from("<i", raw, 12)[0]
    flag_start, _ = struct.unpack_from("<2i", raw, data_start + 40)
    assert struct.unpack_from("<i", raw, flag_start + 4)[0] == 65538
    label_raw = (tmp_path / "vectors/cwell_lab.WT").read_bytes()
    label_start, _ = struct.unpack_from("<2i", label_raw, data_start + 40)
    assert struct.unpack_from("<i", label_raw, label_start + 4)[0] == 65537
    native = read_layers(tmp_path / "vectors")
    assert [len(layer) for layer in native.values()] == [
        len(layer) for layer in layers.values()
    ]
    assert native["cwell_str.WT"].iloc[0]["GZBBAD"] == 51
    assert native["cwell_str_lab.WT"].iloc[0]["CHFCED"] == "51"
    assert native["cwell_str_lab.WT"].iloc[0]["point_type"] == 0
    assert (native["cwell_lab.WT"]["CHFCED"] == native["cwell_lab.WT"]["LABL"]).all()
    assert all(layer.crs == "EPSG:32611" for layer in native.values())
    assert layers["cwell_geo.WP"].geometry.iloc[0].hausdorff_distance(
        native["cwell_geo.WP"].geometry.iloc[0]
    ) < 1e-4
    assert layers["cwell_geo.WL"].geometry.iloc[0].hausdorff_distance(
        native["cwell_geo.WL"].geometry.iloc[0]
    ) < 1e-4
    result = render_layers(native, tmp_path, dpi=60)
    summary = summarise(result.reports)
    assert summary["layers"] == len(LAYER_NAMES)
    assert summary["features"] == 11327
    assert result.overview_label_count > 0
    code_report = next(
        report for report in result.reports if report["source"] == "cwell_lab.WT"
    )
    assert code_report["drawn"] == result.overview_label_count
    attitude_report = next(
        report for report in result.reports
        if report["source"] == "cwell_str_lab.WT"
    )
    assert attitude_report["text"] == 23
    assert summary["drawn"] == 8829 + result.overview_label_count
    assert summary["excluded_text"] == 2498 - result.overview_label_count
    assert summary["unknown_colour_occurrences"] == 0
    assert summary["unknown_fills"] == 0
    assert summary["unresolved_symbols"] == 0
    assert summary["empty_patterns"] == 0
    assert summary["cycle_limits"] == 0
    assert (tmp_path / "cwell_map.png").is_file()
    assert (tmp_path / "cwell_map.pdf").is_file()
    assert (tmp_path / "cwell_map.svg").is_file()
    svg = (tmp_path / "cwell_map.svg").read_text(encoding="utf-8")
    assert "Prjgg" in svg
    assert "TrPmc" in svg
    assert "&lt;jgg" not in svg
    assert "^Pmc" not in svg
    assert ">51</text>" in svg
