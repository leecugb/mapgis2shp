"""Regression tests for the independent synthetic geological-map generator."""
import os
from pathlib import Path

import pytest

from examples.generate_synthetic_geology import (
    LAYER_NAMES,
    generate_layers,
    read_layers,
    render_layers,
    write_layers,
)
from examples.render_bundled_jwd import summarise


def test_synthetic_layers_are_independent_and_typed():
    layers = generate_layers(seed=42)
    assert tuple(layers) == LAYER_NAMES
    assert len(layers) == 12
    assert all(layer.crs == "EPSG:32643" for layer in layers.values())
    assert all(layer.attrs["source"] == name for name, layer in layers.items())
    assert all(name.startswith("SIM_") for name in layers)
    expected_counts = {
        "SIM_LDZOFBB001.WP": 6,
        "SIM_LDZOFBB002.WP": 1,
        "SIM_LDZOFBB003.WP": 1,
        "SIM_LDZOFBB004.WP": 1,
        "SIM_LDLYAAE002.WP": 1,
        "SIM_LDZOFBA002.WL": 5,
        "SIM_LDZOFBA003.WL": 3,
        "SIM_LDZOFBA005.WL": 2,
        "SIM_LDZOFBA016.WT": 12,
        "SIM_LDZOFBB099.WT": 20,
    }
    for name, count in expected_counts.items():
        assert len(layers[name]) == count
    for name in ("SIM_LDZOFBB001.WP", "SIM_LDZOFBB002.WP", "SIM_LDZOFBB003.WP",
                 "SIM_LDZOFBB004.WP", "SIM_LDLYAAE002.WP"):
        assert layers[name]["QDUECC"].str.startswith("SIM-").all()
        assert not layers[name]["QDUECC"].str.contains("Qp|Qh|C1|D2").any()


def test_synthetic_native_roundtrip_and_render(tmp_path, monkeypatch):
    slib = os.environ.get("PYMAPGIS_SLIB")
    if not slib and Path(r"D:\SLIB\SLIB").is_dir():
        slib = r"D:\SLIB\SLIB"
    if not slib:
        pytest.skip("Set PYMAPGIS_SLIB to the five official graphic libraries")
    monkeypatch.setenv("PYMAPGIS_SLIB", slib)
    layers = generate_layers(seed=42)
    write_layers(layers, tmp_path / "vectors")
    native_layers = read_layers(tmp_path / "vectors")
    assert [layer.attrs["source"] for layer in native_layers] == list(LAYER_NAMES)
    assert [len(layer) for layer in native_layers] == [len(layer) for layer in layers.values()]

    result = render_layers(native_layers, tmp_path, dpi=60)
    summary = summarise(result.reports)
    assert summary["layers"] == 12
    assert summary["unknown_colour_occurrences"] == 0
    assert summary["unknown_fills"] == 0
    assert summary["unresolved_symbols"] == 0
    assert summary["unknown_fonts"] == []
    assert summary["empty_patterns"] == 0
    assert summary["cycle_limits"] == 0
    assert (tmp_path / "synthetic_geology.png").is_file()
    assert (tmp_path / "synthetic_geology.pdf").is_file()
    assert (tmp_path / "synthetic_geology.svg").is_file()
