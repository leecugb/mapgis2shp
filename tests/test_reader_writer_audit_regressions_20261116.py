"""Regressions for the 2026-11-16 Reader/Writer audit findings."""
import io
import math
import struct
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Point

from pymapgis import MapGISError, Reader, Writer, WriterError
from pymapgis.reader import _read_attribute_records

FIXTURES = Path(__file__).parents[1] / "tests" / "fixtures" / "mapgis"


def _raw_section(path, index):
    data = Path(path).read_bytes()
    table = struct.unpack_from("<i", data, 12)[0]
    start, volume = struct.unpack_from("<2i", data, table + index * 10)
    return data[start : start + volume]


def test_wt_reordering_cannot_pair_new_attributes_with_old_geometry(tmp_path):
    source = Reader(FIXTURES / "synthetic_points.wt")
    frame = source.geodataframe.iloc[::-1].reset_index(drop=True)
    output = tmp_path / "reordered.wt"

    Writer(frame).to_file(output)
    result = Reader(output)

    assert result.data["ID"].tolist() == frame["ID"].tolist()
    for expected, actual in zip(frame.geometry, result.geom):
        assert expected.equals_exact(actual, 0.0)


def test_wl_reordering_preserves_line_order_and_grouping(tmp_path):
    source = Reader(FIXTURES / "synthetic_lines.wl")
    frame = source.geodataframe.iloc[::-1].reset_index(drop=True)
    output = tmp_path / "reordered.wl"

    Writer(frame).to_file(output)
    result = Reader(output)

    assert result.data["ID"].tolist() == frame["ID"].tolist()
    for expected, actual in zip(frame.geometry, result.geom):
        assert expected.equals_exact(actual, 0.0)


def test_wt_small_edit_is_not_rounded_into_source_passthrough(tmp_path):
    source = Reader(FIXTURES / "synthetic_points.wt")
    frame = source.geodataframe.copy()
    old = frame.geometry.iloc[0]
    moved = Point(old.x + 0.0000004, old.y)
    frame.loc[frame.index[0], "geometry"] = moved
    output = tmp_path / "small_edit.wt"

    Writer(frame).to_file(output)

    assert Reader(output).geom[0].x == moved.x


def test_wl_small_edit_is_not_rounded_into_source_passthrough(tmp_path):
    source = Reader(FIXTURES / "synthetic_lines.wl")
    frame = source.geodataframe.copy()
    coordinates = list(frame.geometry.iloc[0].coords)
    coordinates[0] = (coordinates[0][0] + 0.0000004, coordinates[0][1])
    edited = LineString(coordinates)
    frame.loc[frame.index[0], "geometry"] = edited
    output = tmp_path / "small_edit.wl"

    Writer(frame).to_file(output)

    assert edited.equals_exact(Reader(output).geom[0], 0.0)


@pytest.mark.parametrize(
    ("filename", "output_name", "sections"),
    [
        ("synthetic_points.wt", "unchanged.wt", (0,)),
        ("synthetic_lines.wl", "unchanged.wl", (0, 1)),
    ],
)
def test_unchanged_wt_wl_still_pass_through_source_geometry(
    tmp_path, filename, output_name, sections
):
    source = Reader(FIXTURES / filename)
    output = tmp_path / output_name

    Writer(source.geodataframe).to_file(output)

    for section in sections:
        assert _raw_section(output, section) == _raw_section(FIXTURES / filename, section)


def test_wt_attribute_only_edit_keeps_geometry_passthrough(tmp_path):
    source = Reader(FIXTURES / "synthetic_points.wt")
    frame = source.geodataframe.copy()
    frame.loc[0, "ID"] = 999
    output = tmp_path / "attribute_edit.wt"

    Writer(frame).to_file(output)

    assert _raw_section(output, 0) == _raw_section(FIXTURES / "synthetic_points.wt", 0)
    assert Reader(output).data["ID"].tolist() == frame["ID"].tolist()


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), "invalid"])
def test_writer_rejects_invalid_map_scale(value):
    frame = gpd.GeoDataFrame(geometry=[Point(0, 0)])
    with pytest.raises(WriterError, match="map_scale"):
        Writer(frame, map_scale=value)


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), "invalid"])
def test_writer_rejects_invalid_snap_tolerance(value):
    frame = gpd.GeoDataFrame(geometry=[Point(0, 0)])
    with pytest.raises(WriterError, match="snap_tolerance"):
        Writer(frame, snap_tolerance=value)


def test_writer_rejects_duplicate_columns_clearly():
    attributes = pd.DataFrame([[1, 2]], columns=["duplicate", "duplicate"])
    frame = gpd.GeoDataFrame(attributes, geometry=[Point(0, 0)])
    with pytest.raises(WriterError, match="duplicate column names"):
        Writer(frame)


def test_wt_symbol_number_int16_overflow_is_a_writer_error(tmp_path):
    frame = Reader(
        FIXTURES / "synthetic_points.wt", read_graphic_params=True
    ).geodataframe.copy()
    frame["symbol_no"] = 40000
    with pytest.raises(WriterError, match="symbol_no"):
        Writer(frame).to_file(tmp_path / "overflow.wt")


@pytest.mark.parametrize("column", ["linetype", "color", "aux_color"])
def test_wl_int16_graphic_overflow_is_a_writer_error(tmp_path, column):
    frame = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (1, 1)])])
    frame["linetype"] = 1
    frame[column] = 40000
    with pytest.raises(WriterError, match=column):
        Writer(frame).to_file(tmp_path / "overflow.wl")


@pytest.mark.parametrize(
    ("geometry_type", "suffix"),
    [("POINT", "wt"), ("LINE", "wl"), ("POLYGON", "wp")],
)
def test_empty_writer_output_has_finite_zero_extents(tmp_path, geometry_type, suffix):
    frame = gpd.GeoDataFrame(
        geometry=gpd.GeoSeries([], dtype="geometry"), crs="EPSG:4326"
    )
    output = tmp_path / f"empty.{suffix}"

    Writer(frame, geometry_type=geometry_type).to_file(output)

    extents = struct.unpack_from("<4d", output.read_bytes(), 304)
    assert all(math.isfinite(value) for value in extents)
    assert extents == (0.0, 0.0, 0.0, 0.0)
    assert len(Reader(output)) == 0


def test_reader_rejects_declared_section_past_eof_before_large_read(tmp_path):
    data = bytearray(b"WMAP`D22" + struct.pack("<ii", 1, 16))
    data += struct.pack("<2i", 176, 64 * 1024 * 1024) + b"\xff\xff"
    data += b"".join(
        struct.pack("<2i", 0, 0) + b"\xff\xff" for _ in range(15)
    )
    data += b"\x00" * 1024
    path = tmp_path / "oversized.wt"
    path.write_bytes(data)

    with pytest.raises(MapGISError, match="extends past end of file"):
        Reader(path)


def test_zero_attribute_byte_cap_never_materialises_forged_record_count():
    frame = _read_attribute_records(
        io.BytesIO(b""), 1000, 65535, [], max_bytes=0
    )
    assert len(frame) == 0
