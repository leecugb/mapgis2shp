"""Tests for the pymapgis CLI."""

from __future__ import annotations

import struct
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import pytest

from pymapgis.cli import main


def _synthetic_subgraph() -> bytes:
    """Two indexed records + one tail-chained record + honest-stop sentinel."""
    def rec(t: int, pts: list) -> bytes:
        payload = b"".join(struct.pack("<2f", x, y) for x, y in pts)
        return struct.pack("<4H", t, 2 * len(pts), 0, len(pts)) + payload

    rec0 = rec(1, [(0.1, 0.2), (0.3, 0.4)])
    rec1 = rec(2, [(0.5, 0.5), (0.4, 0.4)])
    rec2 = rec(3, [(0.5, 0.5), (0.4, 0.4)])
    # 终止签名：(62, 6) + 6 个正常坐标点后接全零（无法出链 → 停）
    sentinel = (struct.pack("<2H", 62, 6)
                + struct.pack("<6f", 0.1, 0.2, 0.3, 0.4, 0.5, 0.5))
    return (struct.pack("<2I", 8, 8 + len(rec0))
            + rec0 + rec1 + rec2 + sentinel + b"\x00" * 32)


def _synthetic_linesty() -> bytes:
    """One 24-byte solid-pen style (color=6, width=0.5, yoff=0.0)."""
    subline = bytearray(24)
    struct.pack_into("<H", subline, 0, 1)          # n = 1 element
    struct.pack_into("<3H", subline, 2, 6, 2, 0)   # template (color=6, 2, 0)
    struct.pack_into("<f", subline, 16, 0.5)       # width
    struct.pack_into("<f", subline, 20, 0.0)       # y offset
    index_entry = struct.pack("<IH", 12, 1)        # record @12, 1 subline
    ptr = struct.pack("<IH", 18, 24)               # subline @18, 24B
    return struct.pack("<IH", 1, 0) + index_entry + ptr + bytes(subline)


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

    def test_graphic_params(self, sample_wt: Path, tmp_path: Path) -> None:
        output = tmp_path / "out.geojson"
        code = main([str(sample_wt), str(output), "--graphic-params"])
        assert code == 0
        gdf = gpd.read_file(output)
        assert "symbol_no" in gdf.columns or "point_type" in gdf.columns


class TestCliLib:
    """pymapgis lib subcommand against synthetic libraries."""

    def test_subgraph_summary(self, tmp_path: Path, capsys) -> None:
        lib = tmp_path / "Subgraph.lib"
        lib.write_bytes(_synthetic_subgraph())
        code = main(["lib", str(lib)])
        assert code == 0
        out = capsys.readouterr().out
        assert "2 indexed + 1 tail-chain = 3 symbols" in out

    def test_subgraph_symbol(self, tmp_path: Path, capsys) -> None:
        lib = tmp_path / "Subgraph.lib"
        lib.write_bytes(_synthetic_subgraph())
        code = main(["lib", str(lib), "--symbol", "2"])
        assert code == 0
        out = capsys.readouterr().out
        assert "type=3" in out and "points=2" in out

    def test_subgraph_out_of_range(self, tmp_path: Path) -> None:
        lib = tmp_path / "Subgraph.lib"
        lib.write_bytes(_synthetic_subgraph())
        assert main(["lib", str(lib), "--symbol", "99"]) == 1

    def test_linesty_style(self, tmp_path: Path, capsys) -> None:
        lib = tmp_path / "LINESTY.lib"
        lib.write_bytes(_synthetic_linesty())
        code = main(["lib", str(lib), "--style", "1"])
        assert code == 0
        out = capsys.readouterr().out
        assert "solid pen: color=6" in out

    def test_linesty_missing(self, tmp_path: Path) -> None:
        code = main(["lib", str(tmp_path / "missing.lib")])
        assert code == 1

    def test_lib_bad_kind(self, tmp_path: Path) -> None:
        lib = tmp_path / "Subgraph.lib"
        lib.write_bytes(_synthetic_subgraph())
        # --kind linesty on a subgraph file: count/slot decode fails or
        # yields no non-empty styles; must not crash.
        code = main(["lib", str(lib), "--kind", "linesty", "--style", "1"])
        assert code == 1


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
        try:
            result = subprocess.run(
                ["pymapgis", str(sample_wt), str(output)],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            pytest.skip("pymapgis command not installed in environment")
        # This requires the package to be installed; skip if the command is missing.
        if result.returncode != 0 and "pymapgis" in result.stderr:
            pytest.skip("pymapgis command not installed in environment")
        assert output.exists()
