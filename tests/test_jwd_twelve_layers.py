"""Reader and rendering regression for the original twelve JWD layers."""
import hashlib
import json
from pathlib import Path

import pytest

from examples.render_bundled_jwd import regression_layers, summarise
from pymapgis import GraphicLibraries, GraphicRenderer, Reader
from pymapgis.testing import slib_path

SOURCE = Path("mapgis2shp_submission/wheel_quickstart_release/pymapgis/testing/fixtures/jwd")
MANIFEST = Path("tests/fixtures/jwd_slib_manifest.json")


def test_original_jwd_twelve_reader_and_hashes():
    if not SOURCE.is_dir():
        pytest.skip("Original JWD fixture directory is unavailable")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    total = 0
    for name, info in manifest["vectors"].items():
        path = SOURCE / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == info["sha256"], name
        reader = Reader(path, read_graphic_params=True)
        frame = reader.geodataframe
        assert not frame.geometry.is_empty.any(), name
        assert frame.geometry.is_valid.all(), name
        assert frame.columns.is_unique, name
        total += len(frame)
    assert total == 7094


def test_original_jwd_twelve_slib_render(tmp_path):
    if not SOURCE.is_dir():
        pytest.skip("Original JWD fixture directory is unavailable")
    if not Path(r"D:/SLIB/SLIB").is_dir():
        pytest.skip("Original SLIB is unavailable")
    raw_layers = regression_layers(SOURCE)
    assert len(raw_layers) == 12
    renderer = GraphicRenderer(
        GraphicLibraries.from_directory(slib_path()),
        scale=250000,
        native_text_layout=True,
        polygon_labels=True,
        polygon_label_fontsize=5.0,
        polygon_label_scale=0.7,
        text_font_family=["Microsoft YaHei", "SimSun", "DejaVu Sans"],
        font_zh_map={1: "SimSun", 4: "SimHei"},
        font_en_map={0: "DejaVu Sans"},
    )
    layers = []
    for path in raw_layers:
        layer = GraphicRenderer.read_layer(path)
        layer.attrs["source"] = path.name
        layer.attrs["kind"] = path.suffix.lower().lstrip(".")
        layers.append(layer.to_crs("EPSG:32643"))
    result = renderer.render(layers, figsize=(12, 7.5), dpi=60)
    summary = summarise(result.reports)
    assert summary["layers"] == 12
    assert summary["features"] == 7094
    assert summary["unknown_colour_occurrences"] == 0
    assert summary["unknown_fills"] == 0
    assert summary["unresolved_symbols"] == 0
    assert summary["empty_patterns"] == 0
    assert summary["cycle_limits"] == 0
    assert summary["solid_fallbacks"] == 0
    assert summary["polygon_labels"] > 0
    fold = next(report for report in result.reports if report["source"].endswith("LDZOFBA005.WL"))
    assert fold["features"] == 4
    assert fold["drawn"] == 4
    attitudes = next(
        report for report in result.reports
        if report["source"].endswith("LDZOFBA016.WT")
    )
    assert attitudes["symbols"] == 305
    annotations = next(
        report for report in result.reports
        if report["source"].endswith("LDZOFBB099.WT")
    )
    assert annotations["text"] > 0
    assert annotations["symbols"] > 0
    result.figure.savefig(tmp_path / "jwd_map.png", dpi=60)
    assert (tmp_path / "jwd_map.png").is_file()
