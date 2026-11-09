# SPDX-License-Identifier: Apache-2.0
"""Public access to installed and source fixture datasets."""
import json
from pathlib import Path

import pytest

from pymapgis.testing import fixture_path, jwd_path, slib_path


def test_fixture_access_api_and_dataset_inventory():
    assert fixture_path("fixture_manifest.json").is_file()
    assert fixture_path("jwd_slib_manifest.json").is_file()
    assert fixture_path("writer_batch2_manifest.json").is_file()
    assert fixture_path("writer_batch3_manifest.json").is_file()
    assert fixture_path("writer_batch4_manifest.json").is_file()
    assert fixture_path("reader_native_manifest.json").is_file()
    attribution = fixture_path("DATA_ATTRIBUTION.md")
    assert attribution.is_file()
    source_attribution = Path(__file__).parents[1] / "DATA_ATTRIBUTION.md"
    assert attribution.read_bytes() == source_attribution.read_bytes()
    assert len(list(fixture_path("writer_batch2").glob("*.shp"))) == 11
    assert len(list(fixture_path("writer_batch3").glob("*.shp"))) == 12
    assert len(list(fixture_path("writer_batch4").glob("*.shp"))) == 20
    assert (fixture_path("mapgis") / "synthetic_points.wt").is_file()
    assert (fixture_path("mapgis") / "synthetic_lines.wl").is_file()
    assert (fixture_path("mapgis") / "synthetic_polygons.wp").is_file()


def test_external_jwd_slib_paths(monkeypatch, tmp_path):
    jwd = tmp_path / "jwd"
    slib = tmp_path / "slib"
    jwd.mkdir()
    slib.mkdir()
    (slib / "Pcolor.lib").touch()
    monkeypatch.setenv("PYMAPGIS_JWD", str(jwd))
    monkeypatch.setenv("PYMAPGIS_SLIB", str(slib))
    assert jwd_path() == jwd
    assert slib_path("Pcolor.lib") == slib / "Pcolor.lib"


def test_missing_ngac_data_has_actionable_guidance(monkeypatch):
    monkeypatch.delenv("PYMAPGIS_JWD", raising=False)
    monkeypatch.delenv("PYMAPGIS_SLIB", raising=False)
    with pytest.raises(FileNotFoundError, match="not bundled.*PYMAPGIS_JWD"):
        jwd_path()
    with pytest.raises(FileNotFoundError, match="not bundled.*PYMAPGIS_SLIB"):
        slib_path()


def test_ngac_manifest_registries():
    manifest = json.loads(fixture_path("jwd_slib_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["vectors"]) == 12
    assert len(manifest["libraries"]) == 5
    assert manifest["validation"]["feature_count"] == 7094
    assert manifest["totals"]["bytes"] == 19381767
    assert manifest["totals"]["bytes"] == (
        manifest["totals"]["vector_bytes"] + manifest["totals"]["library_bytes"]
    )
    assert "not bundled" in manifest["current_distribution"]
    for item in (*manifest["vectors"].values(), *manifest["libraries"].values()):
        assert item["bytes"] > 0
        assert len(item["sha256"]) == 64

    reader = json.loads(fixture_path("reader_native_manifest.json").read_text(encoding="utf-8"))
    assert len(reader["files"]) == 16
    assert len({item["file"] for item in reader["files"]}) == 16
    assert reader["source"]["sheet"] == "J43C001002"
    assert reader["source"]["doi"] == "10.23650/data.A.2018.NGA131703.K1.1.1.V1"
    assert "not bundled" in reader["current_distribution"]
