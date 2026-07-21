"""Unit tests for pure helper functions (no I/O)."""

from __future__ import annotations

import datetime
import io
import struct

import pytest

from pymapgis.reader import (
    _decode_attribute_field,
    _decode_gbk,
    _Field,
    _PolygonTopologyBuilder,
    _raw_dms_to_degrees,
    _read_arc_index,
    _read_points,
    _read_struct,
    _read_topology_table,
)


class TestDecodeGbk:
    def test_valid_string(self) -> None:
        assert _decode_gbk("你好".encode("gbk")) == "你好"

    def test_trailing_null(self) -> None:
        assert _decode_gbk("abc\x00\x00".encode("gbk")) == "abc"

    def test_invalid_byte_fallback(self) -> None:
        # GBK cannot decode 0xff directly; fallback should truncate before it.
        buf = b"ab\xffcd"
        assert _decode_gbk(buf) == "ab"


class TestRawDmsToDegrees:
    def test_typical_central_meridian(self) -> None:
        # 730000.0 -> 73 deg 00 min 00 sec
        assert _raw_dms_to_degrees(730000.0) == pytest.approx(73.0)

    def test_with_minutes_seconds(self) -> None:
        # 731530.0 -> 73 deg 15 min 30 sec
        assert _raw_dms_to_degrees(731530.0) == pytest.approx(73.2583333333)

    def test_short_value_padded(self) -> None:
        # 73000.0 padded to 073000 -> 7 deg 30 min 00 sec
        assert _raw_dms_to_degrees(73000.0) == pytest.approx(7.5)

    def test_negative_western_longitude(self) -> None:
        # -731530.0 -> -(73 deg 15 min 30 sec); string approach mishandled signs.
        assert _raw_dms_to_degrees(-731530.0) == pytest.approx(-73.2583333333)

    def test_fractional_seconds_preserved(self) -> None:
        # 730030.5 -> 73 deg 00 min 30.5 sec; the old :.0f format dropped the .5.
        assert _raw_dms_to_degrees(730030.5) == pytest.approx(
            73.0 + 30.5 / 3600.0
        )


class TestReadStruct:
    def test_unpack(self) -> None:
        data = struct.pack("<i", 42) + struct.pack("<d", 3.14)
        f = io.BytesIO(data)
        a, b = _read_struct(f, "<id")
        assert a == 42
        assert b == pytest.approx(3.14)

    def test_short_read_raises(self) -> None:
        f = io.BytesIO(b"\x01\x02")
        with pytest.raises(Exception):
            _read_struct(f, "<i")


class TestField:
    def test_type_name(self) -> None:
        field = _Field("ID", 3, 0, 4, 0)
        assert field.type_name == "integer"

    def test_unknown_type_name(self) -> None:
        field = _Field("X", 99, 0, 4, 0)
        assert field.type_name == "unknown(99)"


class TestDecodeAttributeField:
    def test_integer(self) -> None:
        field = _Field("ID", 3, 0, 4, 0)
        record = (12345).to_bytes(4, "little")
        assert _decode_attribute_field(record, field) == 12345

    def test_string(self) -> None:
        field = _Field("NAME", 0, 0, 10, 0)
        record = b"hello\x00\x00\x00\x00\x00"
        assert _decode_attribute_field(record, field) == "hello"

    def test_date(self) -> None:
        field = _Field("D", 6, 0, 4, 0)
        record = (2024).to_bytes(2, "little") + bytes([7, 6])
        assert _decode_attribute_field(record, field) == datetime.date(2024, 7, 6)

    def test_date_zero_month_day_returns_none(self) -> None:
        # Missing dates are sometimes stored with month=0/day=0; tolerate them.
        field = _Field("D", 6, 0, 4, 0)
        record = (2024).to_bytes(2, "little") + bytes([0, 0])
        assert _decode_attribute_field(record, field) is None


class TestPolygonTopologyBuilder:
    def test_merge_two_arcs_into_ring(self) -> None:
        arcs = [
            [(0.0, 0.0), (1.0, 0.0)],
            [(1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)],
        ]
        rings = _PolygonTopologyBuilder._merge_arcs_into_rings(arcs)
        assert len(rings) == 1
        # Shared endpoint appears twice at the joint.
        assert len(rings[0]) == 6

    def test_single_closed_arc(self) -> None:
        arcs = [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)]]
        rings = _PolygonTopologyBuilder._merge_arcs_into_rings(arcs)
        assert len(rings) == 1
        assert len(rings[0]) == 4

    def test_build_multipolygon_shell_and_hole(self) -> None:
        shell = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
        hole = [(2.0, 2.0), (2.0, 8.0), (8.0, 8.0), (8.0, 2.0), (2.0, 2.0)]
        mp = _PolygonTopologyBuilder._build_multipolygon([shell, hole])
        assert mp.geom_type == "MultiPolygon"
        assert len(mp.geoms) == 1
        assert len(mp.geoms[0].interiors) == 1

    def test_build_multipolygon_nested_holes(self) -> None:
        # Outer shell, one hole, and an island inside that hole.
        shell = [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0), (0.0, 0.0)]
        hole = [(5.0, 5.0), (15.0, 5.0), (15.0, 15.0), (5.0, 15.0), (5.0, 5.0)]
        island = [(8.0, 8.0), (12.0, 8.0), (12.0, 12.0), (8.0, 12.0), (8.0, 8.0)]
        mp = _PolygonTopologyBuilder._build_multipolygon([shell, hole, island])
        assert mp.is_valid
        assert mp.area > 0

    def test_build_multipolygon_empty(self) -> None:
        mp = _PolygonTopologyBuilder._build_multipolygon([])
        assert mp.is_empty


class TestVectorizedReaders:
    """Unit tests for the vectorized binary parsing helpers."""

    def test_read_points(self) -> None:
        # One empty 93-byte record + one point with x=1.5, y=2.5.
        empty = b"\x00" * 93
        record = bytearray(93)
        record[7:15] = struct.pack("<d", 1.5)
        record[15:23] = struct.pack("<d", 2.5)
        buf = empty + bytes(record)

        f = io.BytesIO(buf)
        points = _read_points(f, 0, len(buf), scale=1.0)
        assert len(points) == 1
        assert points[0].x == pytest.approx(1.5)
        assert points[0].y == pytest.approx(2.5)

    def test_read_points_scaled(self) -> None:
        empty = b"\x00" * 93
        record = bytearray(93)
        record[7:15] = struct.pack("<d", 10.0)
        record[15:23] = struct.pack("<d", 20.0)
        buf = empty + bytes(record)

        f = io.BytesIO(buf)
        points = _read_points(f, 0, len(buf), scale=0.001)
        assert points[0].x == pytest.approx(0.01)
        assert points[0].y == pytest.approx(0.02)

    def test_read_arc_index(self) -> None:
        # One empty 57-byte record + two arc index records.
        empty = b"\x00" * 57
        rec1 = bytearray(57)
        rec1[10:14] = struct.pack("<i", 4)   # point_count
        rec1[14:18] = struct.pack("<i", 0)   # point_offset
        rec2 = bytearray(57)
        rec2[10:14] = struct.pack("<i", 3)
        rec2[14:18] = struct.pack("<i", 64)  # bytes offset
        buf = empty + bytes(rec1) + bytes(rec2)

        f = io.BytesIO(buf)
        index = _read_arc_index(f, 0, len(buf), 57)
        assert index == [(4, 0), (3, 64)]

    def test_read_topology_table(self) -> None:
        # One empty 24-byte record + two topology records.
        empty = b"\x00" * 24
        rec1 = struct.pack("<4i", 0, 0, 1, 2) + b"\x00" * 8
        rec2 = struct.pack("<4i", 0, 0, 3, 4) + b"\x00" * 8
        buf = empty + rec1 + rec2

        f = io.BytesIO(buf)
        topo = _read_topology_table(f, 0, len(buf))
        assert topo.shape == (2, 4)
        assert topo[0, 2] == 1
        assert topo[0, 3] == 2
        assert topo[1, 2] == 3
        assert topo[1, 3] == 4
