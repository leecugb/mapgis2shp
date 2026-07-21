"""Tests for the pymapgis CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import pytest

from pymapgis.cli import main


class TestCliMain:
    def test_convert_point(self, sample_wt: Path, tmp_path: Path) -> None:
        output = tmp_path / "out.geojson"
        code = main([str(sample_wt), str(output)])
        assert code == 0
        assert output.exists()
        gdf = gpd.read_file(output)
        assert len(gdf) > 0

    def test_convert_polygon(self, sample_wp: Path, tmp_path: Path) -> None:
        output = tmp_path / "out.shp"
        code = main([str(sample_wp), str(output)])
        assert code == 0
        assert output.exists()
        gdf = gpd.read_file(output)
        assert len(gdf) > 0

    def test_missing_input(self, tmp_path: Path) -> None:
        output = tmp_path / "out.shp"
        code = main([str(tmp_path / "missing.wp"), str(output)])
        assert code == 1

    def test_invalid_file(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.wp"
        bad.write_text("not mapgis")
        output = tmp_path / "out.shp"
        code = main([str(bad), str(output)])
        assert code == 1

    def test_no_make_valid(self, sample_wp: Path, tmp_path: Path) -> None:
        output = tmp_path / "out.geojson"
        code = main([str(sample_wp), str(output), "--no-make-valid"])
        assert code == 0
        assert output.exists()


class TestCliEntryPoint:
    def test_module_execution(self, sample_wt: Path, tmp_path: Path) -> None:
        output = tmp_path / "out.geojson"
        result = subprocess.run(
            [sys.executable, "-m", "pymapgis", str(sample_wt), str(output)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert output.exists()

    def test_console_script(self, sample_wt: Path, tmp_path: Path) -> None:
        output = tmp_path / "out.geojson"
        result = subprocess.run(
            ["pymapgis", str(sample_wt), str(output)],
            capture_output=True,
            text=True,
        )
        # This requires the package to be installed; skip if the command is missing.
        if result.returncode != 0 and "pymapgis" in result.stderr:
            pytest.skip("pymapgis command not installed in environment")
        assert output.exists()
