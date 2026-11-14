"""Reader and rendering regression using only the six original testdata files."""
import json
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import box

from examples.audit_six_usgs_layers import EXPECTED, read_six_layers, render_six_layers
from examples.render_bundled_jwd import summarise
from examples.usgs_conejo_symbols import expand_left_slip_ornaments
from pymapgis import GraphicLibraries, GraphicRenderer, Reader
from pymapgis.testing import slib_path, usgs_conejo_path

pytestmark = pytest.mark.skipif(
    not (usgs_conejo_path() / "native").is_dir(),
    reason="optional native USGS comparison files are not included in this clean distribution",
)


def test_six_native_files_reader_and_manifest():
    layers, reports = read_six_layers()
    assert len(layers) == 6
    assert all(layer.columns.is_unique for layer in layers)
    assert sum(len(layer) for layer in layers) == 8804
    assert {report["file"]: report["features"] for report in reports} == EXPECTED
    assert all(report["empty_geometries"] == 0 for report in reports)
    assert all(report["invalid_geometries"] == 0 for report in reports)
    assert all(report["render_crs"] == "EPSG:32611" for report in reports)
    manifest = json.loads(usgs_conejo_path("manifest.json").read_text(encoding="utf-8"))
    for report in reports:
        assert manifest["native_files"][report["file"]]["sha256"] == report["sha256"]
    polygon = next(layer for layer in layers if layer.attrs["source"] == "CWELL_GEO_WP.WP")
    assert polygon["LABL"].nunique() == 56
    assert polygon["QDUECC"].equals(polygon["LABL"])
    assert polygon["QDUECD"].equals(polygon["LABL"])

    by_source = {layer.attrs["source"]: layer for layer in layers}
    ornaments = expand_left_slip_ornaments(
        by_source["CWELL_ORN_WT.WT"], by_source["CWELL_GEO_WL.WL"]
    )
    assert len(ornaments) == 4
    assert ornaments["source_id"].tolist() == [1, 1, 2, 2]
    assert ornaments["symbol_no"].eq(239).all()
    assert ornaments["height"].eq(3.0).all()
    assert ornaments["width"].eq(3.0).all()
    assert ornaments["angle"].iloc[1] - ornaments["angle"].iloc[0] == pytest.approx(180)
    assert ornaments["angle"].iloc[3] - ornaments["angle"].iloc[2] == pytest.approx(180)
    assert max(ornaments.attrs["nearest_fault_distances_m"]) < 0.01


def test_six_native_files_original_library_render(tmp_path):
    if not Path(r"D:/SLIB/SLIB").is_dir() and not os.environ.get("PYMAPGIS_SLIB"):
        pytest.skip("The five original SLIB libraries are unavailable")
    layers, _ = read_six_layers()
    result = render_six_layers(layers, tmp_path, dpi=60, formats=("png", "pdf", "svg"))
    summary = summarise(result.reports)
    assert summary["layers"] == 6
    assert summary["source_features"] == 8804
    assert summary["features"] == 8806
    assert summary["drawn"] == 8806
    ornaments = next(
        report for report in result.reports if report["source"] == "CWELL_ORN_WT.WT"
    )
    assert ornaments["source_features"] == 2
    assert ornaments["features"] == 4
    assert ornaments["drawn"] == 4
    assert ornaments["symbols"] == 4
    assert max(ornaments["nearest_fault_distances_m"]) < 0.01
    assert summary["unknown_colour_occurrences"] == 0
    assert summary["solid_fallbacks"] == 0
    assert summary["unknown_fills"] == 0
    assert summary["unresolved_symbols"] == 0
    assert summary["empty_patterns"] == 0
    assert summary["cycle_limits"] == 0
    assert summary["polygon_labels"] == 0
    for suffix in ("png", "pdf", "svg"):
        assert (tmp_path / f"cwell_six_map.{suffix}").is_file()


def test_raw_reader_duplicate_columns_use_native_graphics(tmp_path):
    if not Path(r"D:/SLIB/SLIB").is_dir() and not os.environ.get("PYMAPGIS_SLIB"):
        pytest.skip("The five original SLIB libraries are unavailable")
    raw = Reader(
        usgs_conejo_path("native/CWELL_GEO_WP.WP"), read_graphic_params=True
    ).geodataframe
    expected = Reader(
        usgs_conejo_path("native/CWELL_GEO_WP.WP"), read_graphic_params=True
    ).polygon_params.iloc[0]
    assert not raw.columns.is_unique
    renderer = GraphicRenderer(
        GraphicLibraries.from_directory(slib_path()), scale=24000,
        polygon_labels=False, map_units_per_mm=24.0,
    )
    prepared = renderer._coerce_layer(raw)
    assert prepared.gdf.columns.is_unique
    assert prepared.gdf["fill_color"].iloc[0] == expected["fill_color"]
    assert prepared.gdf["class"].iloc[0] == expected["class"]
    assert prepared.gdf["layer"].iloc[0] == expected["layer"]
    result = renderer.render([raw], tmp_path / "raw.png", figsize=(5, 4), dpi=50)
    assert result.reports[0]["drawn"] == 2498
    assert result.reports[0]["unknown_colors"] == {}


def test_six_polygon_label_field_labl(tmp_path):
    if not Path(r"D:/SLIB/SLIB").is_dir() and not os.environ.get("PYMAPGIS_SLIB"):
        pytest.skip("The five original SLIB libraries are unavailable")
    layers, _ = read_six_layers()
    result = render_six_layers(
        layers, tmp_path, dpi=60, formats=("svg",), label_field="LABL"
    )
    summary = summarise(result.reports)
    assert 0 < summary["polygon_labels"] <= 2498
    svg = (tmp_path / "cwell_six_map.svg").read_text(encoding="utf-8")
    assert "Qyas2,3" in svg


def test_polygon_label_collision_buffer_skips_overlapping_label(tmp_path):
    if not Path(r"D:/SLIB/SLIB").is_dir() and not os.environ.get("PYMAPGIS_SLIB"):
        pytest.skip("The five original SLIB libraries are unavailable")
    polygons = gpd.GeoDataFrame(
        {"LABL": ["A", "B"], "fill_color": [602, 602], "class": [2, 2]},
        geometry=[box(0, 0, 100, 100), box(0, 0, 100, 100)],
        crs="EPSG:32611",
    )
    polygons.attrs["source"] = "overlap.wp"
    polygons.attrs["kind"] = "wp"
    renderer = GraphicRenderer(
        GraphicLibraries.from_directory(slib_path()),
        scale=24000,
        map_units_per_mm=24.0,
        polygon_labels=True,
        polygon_label_fields=("LABL",),
        polygon_label_avoid_collisions=True,
        polygon_label_buffer_pt=100.0,
        polygon_label_max_offset_pt=4.0,
    )
    result = renderer.render([polygons], tmp_path / "overlap.png", figsize=(4, 4), dpi=60)
    assert result.reports[0]["polygon_label"] == 1
    assert result.reports[0]["label_skipped_collision"] == 1


def test_polygon_label_randomized_visibility_is_seeded(tmp_path):
    if not Path(r"D:/SLIB/SLIB").is_dir() and not os.environ.get("PYMAPGIS_SLIB"):
        pytest.skip("The five original SLIB libraries are unavailable")
    labels = list("ABCDEFGHIJ")
    polygons = gpd.GeoDataFrame(
        {"LABL": labels, "fill_color": [602] * 10, "class": [2] * 10},
        geometry=[box(0, 0, 100, 100)] * 10,
        crs="EPSG:32611",
    )
    polygons.attrs["source"] = "random.wp"
    polygons.attrs["kind"] = "wp"
    seed = 42
    renderer = GraphicRenderer(
        GraphicLibraries.from_directory(slib_path()),
        scale=24000,
        map_units_per_mm=24.0,
        polygon_labels=True,
        polygon_label_fields=("LABL",),
        polygon_label_avoid_collisions=True,
        polygon_label_randomize=True,
        polygon_label_seed=seed,
        polygon_label_buffer_pt=100.0,
        polygon_label_max_offset_pt=4.0,
    )
    result = renderer.render([polygons], tmp_path / "random.png", figsize=(4, 4), dpi=60)
    expected = labels[np.random.default_rng(seed).permutation(len(labels))[0]]
    assert [text.get_text() for text in result.axes.texts] == [expected]
    assert result.reports[0]["polygon_label"] == 1
    assert result.reports[0]["label_skipped_collision"] == 9
