"""Unit tests for pure helper functions (no I/O)."""

from __future__ import annotations

import datetime
import importlib.util
import io
import math
import os
import struct
from pathlib import Path

import numpy as np
import pytest

from pymapgis.reader import (
    MapGISError,
    _decode_attribute_field,
    _decode_gbk,
    _Field,
    _PolygonTopologyBuilder,
    _raw_dms_to_degrees,
    _read_arc_index,
    _read_attribute_records,
    _read_crs,
    _read_header_entries,
    _read_line_params,
    _read_lines,
    _read_point_params,
    _read_points,
    _read_polygon_params,
    _read_struct,
    _read_topology_table,
)
from pymapgis.slib import Element, SubgraphLib, parse_elements, symbol_geometries


def _has_optional_adjudicated_tables() -> bool:
    return importlib.util.find_spec("pymapgis.linesty_adjudicated") is not None


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

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_nonfinite_returns_nan(self, value: float) -> None:
        # CRS callers reject NaN in their normal finite-parameter checks;
        # converting it to minutes must not leak ValueError first.
        assert math.isnan(_raw_dms_to_degrees(value))


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

    def test_time_nan_seconds_returns_none(self) -> None:
        # 2026-10-30 审计回归：NaN/Inf 秒值回退 None，不得泄漏 int(NaN) 的
        # 原生 ValueError/OverflowError（与日期分支的容忍语义一致）。
        field = _Field("T", 7, 0, 10, 0)
        record = bytes([3, 4]) + struct.pack("<d", float("nan")) + b"\x00" * 8
        assert _decode_attribute_field(record, field) is None

    def test_time_inf_seconds_returns_none(self) -> None:
        field = _Field("T", 7, 0, 10, 0)
        record = bytes([3, 4]) + struct.pack("<d", float("inf")) + b"\x00" * 8
        assert _decode_attribute_field(record, field) is None

    def test_numeric_short_chunk_returns_none(self) -> None:
        # 描述符把数值字段声明到记录末尾之外：截断切片回退 None，
        # 不得泄漏 struct.error("unpack requires a buffer of 4 bytes")。
        field = _Field("X", 3, 90, 4, 0)
        assert _decode_attribute_field(b"\x01" * 20, field) is None


class TestCrsRobustness:
    """2026-10-30 审计回归：地理文件 scale=0/NaN 不得丢 CRS——
    LDZOFBA016.WT / LHCPGDAC05.WP 头部 scale=0 曾令 crs="" 与基线不符；
    截断/NaN 头部回退 ("", 1.0)，不得泄漏 TypeError/ValueError/CRSError。"""

    @staticmethod
    def _header(projection: int = 0, ellipsoid: int = 1, scale: float = 1.0,
                central: float = None, projection_scale: float = 1.0) -> io.BytesIO:
        buf = bytearray(240)
        buf[109] = projection
        buf[110] = ellipsoid
        struct.pack_into("<d", buf, 143, scale)
        struct.pack_into("<d", buf, 232, projection_scale)
        if central is not None:
            struct.pack_into("<d", buf, 151, central)
        return io.BytesIO(bytes(buf))

    def test_geographic_zero_scale_keeps_crs(self) -> None:
        crs, scale = _read_crs(self._header(scale=0.0))
        assert crs != "" and scale == 1.0

    def test_geographic_nan_scale_keeps_crs(self) -> None:
        crs, scale = _read_crs(self._header(scale=float("nan")))
        assert crs != "" and scale == 1.0

    def test_projected_zero_scale_returns_empty(self) -> None:
        crs, scale = _read_crs(
            self._header(projection=5, ellipsoid=16, scale=0.0, central=730000.0)
        )
        assert crs == "" and scale == 1.0

    def test_projected_nan_central_meridian_returns_empty(self) -> None:
        crs, _ = _read_crs(
            self._header(projection=5, ellipsoid=16, scale=1000.0,
                         central=float("nan"))
        )
        assert crs == ""

    @pytest.mark.parametrize("projection", [2, 3])
    @pytest.mark.parametrize("bad", [float("nan"), float("inf")])
    def test_nonfinite_conic_parallel_returns_empty(self, projection, bad) -> None:
        # DMS conversion must return NaN for the caller's finite-value gate;
        # projection 2/3 previously leaked ValueError at int(NaN).
        stream = self._header(
            projection=projection, ellipsoid=16, scale=1000.0, central=730000.0
        )
        struct.pack_into("<d", stream.getbuffer(), 175, bad)
        crs, scale = _read_crs(stream)
        assert crs == "" and scale == 1.0

    def test_tmerc_utm_projection_scale_and_unit_coordinate_factor(self) -> None:
        crs, scale = _read_crs(self._header(
            projection=5,
            ellipsoid=7,
            scale=1000.0,
            central=-1170000.0,
            projection_scale=0.9996,
        ))
        assert scale == 1.0
        assert crs.to_epsg() == 32611
        projection_scales = [
            parameter.value
            for parameter in crs.coordinate_operation.params
            if "Scale factor" in parameter.name
        ]
        assert projection_scales == pytest.approx([0.9996])

    def test_truncated_header_raises_mapgis_error(self) -> None:
        with pytest.raises(MapGISError):
            _read_crs(io.BytesIO(b"\x00" * 120))


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

    def test_build_multipolygon_skips_degenerate_rings(self) -> None:
        # A degenerate ring with fewer than 4 coordinates (a collapsed sliver
        # from arc merging) must be skipped, not crash shapely. Real 400 MB
        # MapGIS files produce such rings.
        shell = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
        degenerate = [(1.0, 1.0), (2.0, 2.0)]  # 2 coords: too short to be a ring
        mp = _PolygonTopologyBuilder._build_multipolygon([shell, degenerate])
        assert mp.geom_type == "MultiPolygon"
        assert len(mp.geoms) == 1
        assert len(mp.geoms[0].interiors) == 0

    def test_single_arc_degenerate_yields_empty_polygon(self) -> None:
        # 2026-10-30 审计回归：单弧退化环与多弧路径一致地回退空多边形，
        # 不得泄漏 "A linearring requires at least 4 coordinates"。
        import shapely.geometry

        arcs = [shapely.geometry.LineString([(0.0, 0.0), (1.0, 1.0)])]
        topo = np.array([[0, 0, 1, 0]], dtype="int32")
        g = _PolygonTopologyBuilder(arcs, topo).build(1)
        assert g.is_empty

    def test_topology_longer_than_arcs_raises(self) -> None:
        # 2026-10-30 审计回归：拓扑表长于弧段索引（弧段区截断/损坏）
        # 必须报 MapGISError，不得泄漏 IndexError。
        import shapely.geometry

        arcs = [shapely.geometry.LineString([(0, 0), (1, 0), (1, 1), (0, 0)])]
        topo = np.array([[0, 0, 1, 0], [0, 0, 2, 0]], dtype="int32")
        with pytest.raises(MapGISError):
            _PolygonTopologyBuilder(arcs, topo)


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


class TestMalformedStructureErrors:
    """2026-10-30 审计回归：畸形文件报 MapGISError，不得泄漏原生异常。"""

    def test_negative_record_length_raises(self) -> None:
        with pytest.raises(MapGISError):
            _read_attribute_records(
                io.BytesIO(b"\x00" * 20), 2, -1, [_Field("a", 3, 0, 4, 0)]
            )

    def test_zero_record_length_raises(self) -> None:
        with pytest.raises(MapGISError):
            _read_attribute_records(
                io.BytesIO(b"\x00" * 20), 2, 0, [_Field("a", 3, 0, 4, 0)]
            )

    def test_single_point_arc_rejected(self) -> None:
        # 单点弧无法构成 LineString（shapely 抛原生 GEOSException）——
        # 按损坏报 MapGISError。
        empty = b"\x00" * 57
        rec = bytearray(57)
        struct.pack_into("<i", rec, 10, 1)   # point_count = 1
        struct.pack_into("<i", rec, 14, 0)   # point_offset
        coords = struct.pack("<2d", 1.0, 2.0)
        with pytest.raises(MapGISError):
            _read_lines(io.BytesIO(empty + bytes(rec)), 0, len(empty) + 57,
                        0, len(coords), 1.0)

    def test_negative_header_entry_rejected(self) -> None:
        entry = struct.pack("<2i", -5, 10) + b"\xff\xff"
        with pytest.raises(MapGISError):
            _read_header_entries(io.BytesIO(entry * 16), 0)


class TestPolygonActiveIdAlignment:
    """2026-10-30 审计回归：拓扑引用超出属性表的区号被一致丢弃
    （数据行/几何/区参数同一 filtered ID 集驱动），不再崩 GeoDataFrame。"""

    def test_orphan_topology_id_dropped_consistently(self, tmp_path) -> None:
        import geopandas as gpd
        import shapely.geometry

        from pymapgis import Reader, Writer

        gdf = gpd.GeoDataFrame(
            {"ID": [1, 2]},
            geometry=[
                shapely.geometry.box(0, 0, 1, 1),
                shapely.geometry.box(2, 0, 3, 1),
            ],
            crs="EPSG:4326",
        )
        path = tmp_path / "two.wp"
        Writer(gdf).to_file(path)

        data = bytearray(path.read_bytes())
        data_start = struct.unpack_from("<i", data, 12)[0]
        entries = _read_header_entries(
            io.BytesIO(bytes(data)), data_start, 16
        )
        topo_start, _ = entries[3]
        # 把第一条弧的右区号改成无属性记录的 400（孤立 ID）。
        struct.pack_into("<i", data, topo_start + 24 + 12, 400)
        path.write_bytes(bytes(data))

        with Reader(path) as reader:
            assert len(reader) == 2
            assert len(reader.data) == 2
            assert list(reader.data["ID"]) == [1, 2]


# ---------------------------------------------------------------------------
# Graphic-parameter decodes (official MapGIS layouts, pinned 2026-10-14)
# ---------------------------------------------------------------------------


class TestPublicApi:
    """包级导出：五个图形库解析器及原始渲染入口均为公共 API。

    裁定表（ADJUDICATED / PAIR_SEMANTICS，含地质语义）不是包级导出，
    也不进发布件（2026-10-14 包定位裁定）——它们是仓内
    pymapgis.linesty_adjudicated 的内容。
    """

    def test_library_parsers_exported(self) -> None:
        import pymapgis

        for name in (
            "SubgraphLib", "LinestyLib", "compose_feature_style",
            "classify_form", "census", "symbol_geometries", "fit_circle",
            "ColorLib", "PcolorLib", "FillgrphLib", "FillPattern", "FillStroke",
            "pattern_geometry", "GraphicLibraries", "GraphicRenderer",
            "render_graphic_map",
        ):
            assert hasattr(pymapgis, name), name
        for name in ("ADJUDICATED", "PAIR_SEMANTICS", "pair_semantics"):
            assert not hasattr(pymapgis, name), name
        # Legacy helpers remain importable from pymapgis.linesty, but are not
        # part of the curated top-level public API.
        assert "dotline_params" not in pymapgis.__all__
        assert "linedot_params" not in pymapgis.__all__

    @pytest.mark.skipif(
        not _has_optional_adjudicated_tables(),
        reason="optional adjudicated tables are excluded from clean distributions",
    )
    def test_adjudicated_tables_repo_side(self) -> None:
        """仓内环境（可导入 linesty_adjudicated）裁定表可用。"""
        from pymapgis import linesty

        assert linesty.pair_semantics(17, 0) is not None
        adj, _ = linesty._adjudicated_tables()
        assert 2 in adj  # 线型 2（纯虚线）有裁定

    def test_adjudicated_tables_degrade_without_module(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """发布环境（linesty_adjudicated 缺席）功能完整降级。"""
        import sys

        import pymapgis.linesty as linesty

        real_module = sys.modules.pop("pymapgis.linesty_adjudicated", None)
        monkeypatch.setitem(sys.modules, "pymapgis.linesty_adjudicated", None)
        try:
            adj, pairs = linesty._adjudicated_tables()
            assert adj == {} and pairs == {}
            assert linesty.pair_semantics(17, 0) is None
        finally:
            if real_module is not None:
                sys.modules["pymapgis.linesty_adjudicated"] = real_module


class TestLinestyTruncatedFlag:
    """F2 审计加固：坏子线指针不再静默截断——truncated 标志如实上报。

    记录 = [n_subs×6B（u32 子线绝对偏移, u16 子线长）] + 子线链。
    """

    @staticmethod
    def _lib(tmp_path, record: bytes, n_subs: int = 2):
        from pymapgis.linesty import LinestyLib
        data = (struct.pack("<I", 1) + struct.pack("<H", 0)
                + struct.pack("<IH", 12, n_subs) + record)
        path = tmp_path / "LINESTY.lib"
        path.write_bytes(data)
        return LinestyLib(str(path))

    @staticmethod
    def _solid_subline() -> bytes:
        return (struct.pack("<H", 1) + struct.pack("<3H", 0, 2, 0)
                + struct.pack("<4f", 0.0, 0.0, 0.5, 0.0))

    def test_healthy_record_not_truncated(self, tmp_path) -> None:
        sub = self._solid_subline()
        rec = struct.pack("<IH", 24, len(sub)) + struct.pack("<IH", 24, len(sub)) + sub + sub
        st = self._lib(tmp_path, rec).decode(1)
        assert st is not None
        assert len(st.sublines) == 2 and st.truncated is False

    def test_corrupt_pointer_flagged(self, tmp_path) -> None:
        sub = self._solid_subline()
        # 第 2 子线指针越界（ptr+ln 超记录尾）→ 截断并上报
        rec = (struct.pack("<IH", 24, len(sub))
               + struct.pack("<IH", 24 + len(sub) + 9999, 24) + sub)
        st = self._lib(tmp_path, rec).decode(1)
        assert st is not None
        assert len(st.sublines) == 1 and st.truncated is True


class TestContactForm:
    """地质界线线形→接触类型判定表（2026-10-19 用户定案）。

    适用域 = 地质界线层（GZBD 域）；与 PAIR_SEMANTICS 48|0/17|0/2|0/16|0
    互证一致；2|1/2|4/2|18/16|1 为已裁定等价族。
    """

    @pytest.mark.skipif(
        not _has_optional_adjudicated_tables(),
        reason="optional adjudicated tables are excluded from clean distributions",
    )
    def test_contact_form_entries(self) -> None:
        from pymapgis.linesty import contact_semantics
        assert contact_semantics(1, 0)["contact"] == "整合接触"
        assert contact_semantics(48, 0)["contact"] == "平行不整合接触"
        assert contact_semantics(17, 0)["contact"] == "角度不整合接触"
        assert contact_semantics(2, 0)["contact"] == "推测地质界线"
        assert contact_semantics(2, 18)["contact"] == "推测地质界线"  # 等价族
        assert contact_semantics(16, 1)["contact"] == "岩性渐变/岩相接触"
        assert contact_semantics(3, 0)["contact"] == "脉动接触"
        assert contact_semantics(3, 0)["form"] == "虚线与点（短线点相间）"
        assert contact_semantics(999, 0) is None

    def test_degrades_without_module(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sys

        import pymapgis.linesty as linesty

        real_module = sys.modules.pop("pymapgis.linesty_adjudicated", None)
        monkeypatch.setitem(sys.modules, "pymapgis.linesty_adjudicated", None)
        try:
            assert linesty.contact_semantics(1, 0) is None
        finally:
            if real_module is not None:
                sys.modules["pymapgis.linesty_adjudicated"] = real_module


class TestLineParams:
    """线图形参数：官方字段序 线型号@22/辅助线型号@24/线颜色@26/
    线宽@30/X系数@35/Y系数@39。"""

    def test_decode_includes_color(self) -> None:
        empty = b"\x00" * 57
        record = bytearray(57)
        struct.pack_into("<h", record, 22, 211)
        struct.pack_into("<h", record, 24, 0)
        struct.pack_into("<h", record, 26, 194)
        struct.pack_into("<f", record, 30, 0.7)
        struct.pack_into("<f", record, 35, 10.0)
        struct.pack_into("<f", record, 39, 2.5)
        # 明码补齐三字段（2026-10-15）：辅助色@43/图层@47/透明@48
        struct.pack_into("<h", record, 43, 12)
        struct.pack_into("<B", record, 47, 5)
        struct.pack_into("<B", record, 48, 1)
        buf = empty + bytes(record)

        f = io.BytesIO(buf)
        params = _read_line_params(f, 0, len(buf))
        assert list(params.columns) == [
            "linetype", "aux_linetype", "aux_flag", "color", "width",
            "x_coef", "y_coef", "aux_color", "layer", "transparent",
        ]
        row = params.iloc[0]
        assert row["linetype"] == 211
        assert row["aux_linetype"] == 0
        assert row["aux_flag"] == 0
        assert row["color"] == 194
        assert row["width"] == pytest.approx(0.7)
        assert row["x_coef"] == pytest.approx(10.0)
        assert row["y_coef"] == pytest.approx(2.5)
        assert row["aux_color"] == 12
        assert row["layer"] == 5
        assert row["transparent"] == 1


class TestPolygonParams:
    """区图形参数：布局 v2（2026-10-22 用户 MapGIS 区参数对话框四次
    对账定案，取代旧 2026-10-14 "u8@5=填充色/@6=图案/u16@9=图案色"
    三处全错的读法）。

    布局：u8@1 class；u8@5/6/7 field5/6/7；u16@9 填充颜色；
    u16@13 图案号；u16@17/@21 图案高/宽（f32 位型高16位）；
    u8@23 图案色；u8@30 图层。
    回归锚：BB003 000019 → @9=1226 @13=252 @17=3.0 @21=3.0
    @23=9 @30=3；000016 → @9=1239 @13=293 @17=4.0。
    """

    def test_decode_layout_v2(self) -> None:
        empty = b"\x00" * 40
        record = bytearray(40)
        record[0] = 1
        record[1] = 17          # class
        record[5] = 74          # field5
        record[6] = 130         # field6
        record[7] = 1           # field7
        struct.pack_into("<H", record, 9, 1226)   # 填充颜色
        struct.pack_into("<H", record, 13, 252)   # 图案号（@13-14 LE）
        struct.pack_into("<H", record, 17, 0x4040)  # 图案高度 f32 高16位(3.0)
        struct.pack_into("<H", record, 21, 0x4040)  # 图案宽度 f32 高16位(3.0)
        record[23] = 9          # 图案颜色
        record[30] = 3          # 图层
        buf = empty + bytes(record)

        f = io.BytesIO(buf)
        params = _read_polygon_params(f, 0, len(buf))
        assert list(params.columns) == [
            "class", "fill_color", "pattern", "pattern_height",
            "pattern_width", "pattern_color", "layer",
            "field5", "field6", "field7",
        ]
        row = params.iloc[0]
        assert row["class"] == 17
        assert row["fill_color"] == 1226
        assert row["pattern"] == 252
        assert row["pattern_height"] == pytest.approx(3.0)
        assert row["pattern_width"] == pytest.approx(3.0)
        assert row["pattern_color"] == 9
        assert row["layer"] == 3
        assert row["field5"] == 74
        assert row["field6"] == 130
        assert row["field7"] == 1

    def test_fill_color_is_uint16(self) -> None:
        """填充色 @9 为 u16（低@9 高@10）——u8 读法把 1226 (0x04CA)
        截成 202，>870 扩展色域全数丢失。

        回归锚（2026-10-22 对话框）：BB003 000019 填充色 1226、
        图案号 293；jws 全域填充色值域 2..1465。
        """
        empty = b"\x00" * 40
        record = bytearray(40)
        record[0] = 1
        struct.pack_into("<H", record, 9, 1226)  # 0x04CA
        struct.pack_into("<H", record, 13, 293)
        buf = empty + bytes(record)

        f = io.BytesIO(buf)
        params = _read_polygon_params(f, 0, len(buf))
        row = params.iloc[0]
        assert row["fill_color"] == 1226
        assert row["pattern"] == 293
        assert row["pattern_height"] == pytest.approx(0.0)


class TestPointParams:
    """点图形参数：wat 明码补齐字段（2026-10-15 官方 WMAP9022 序实证）。

    字符串点(0): 高@33f32 宽@37 间隔@41 角度@45 中文字体u8@49
                 西文字体u8@51 字形u8@53 颜色u8@75 图层u8@83
    子图点(1):   号u16@33 高@37 宽@41 角度@45 笔宽f32@49
                 颜色u8@75 图层u8@83（@49 按 kind 分读）
    """

    def test_text_point_tail(self) -> None:
        empty = b"\x00" * 93
        record = bytearray(93)
        struct.pack_into("<f", record, 33, 2.5)   # 字高
        struct.pack_into("<f", record, 37, 2.5)   # 字宽
        struct.pack_into("<f", record, 41, 0.2)   # 间隔
        struct.pack_into("<f", record, 45, 12.0)  # 角度
        record[49] = 4    # 中文字体
        record[51] = 1    # 西文字体
        record[53] = 2    # 字形
        record[75] = 6    # 颜色
        record[83] = 2    # 图层
        buf = empty + bytes(record)

        f = io.BytesIO(buf)
        params = _read_point_params(f, 0, len(buf))
        assert list(params.columns) == [
            "point_type", "symbol_no", "height", "width", "spacing", "angle",
            "color", "layer", "pen_width", "font_zh", "font_en", "font_style",
        ]
        row = params.iloc[0]
        assert row["point_type"] == 0
        assert row["height"] == pytest.approx(2.5)
        assert row["spacing"] == pytest.approx(0.2)
        assert row["angle"] == pytest.approx(12.0)
        assert row["font_zh"] == 4
        assert row["font_en"] == 1
        assert row["font_style"] == 2
        assert row["color"] == 6
        assert row["layer"] == 2
        assert np.isnan(row["pen_width"])

    def test_symbol_point_tail(self) -> None:
        empty = b"\x00" * 93
        record = bytearray(93)
        record[31] = 1                             # 子图点
        struct.pack_into("<h", record, 33, 1281)   # 子图号
        struct.pack_into("<f", record, 37, 1.0)    # 高
        struct.pack_into("<f", record, 41, 1.0)    # 宽
        struct.pack_into("<f", record, 45, 231.55)  # 角度
        struct.pack_into("<f", record, 49, 0.05)   # 笔宽（与字体区同址）
        record[75] = 6    # 颜色
        record[83] = 4    # 图层
        buf = empty + bytes(record)

        f = io.BytesIO(buf)
        params = _read_point_params(f, 0, len(buf))
        row = params.iloc[0]
        assert row["point_type"] == 1
        assert row["symbol_no"] == 1281
        assert row["pen_width"] == pytest.approx(0.05, abs=1e-6)
        assert row["color"] == 6
        assert row["layer"] == 4
        assert np.isnan(row["spacing"])
        assert np.isnan(row["font_zh"])


class TestSlibElements:
    """Subgraph 描述区五字块、图元分组与已裁定填充语义。"""

    @pytest.mark.parametrize("mode,fill_color,expected", [
        (0, 6, 6),       # #43：Colorlib 红色填充
        (0, 4, 4),       # #43：Colorlib 黄色填充
        (5, 7, -1),      # #41：实心黑，w1 不是显示色
        (5, 4, -1),      # #42：同上
        (0, 0, None),
        (0, 1, None),    # #21：编辑器“无填充”值
        (2, 6, None),
        (6, 6, None),
        (1, 6, None),    # 未裁定模式不得擅自填色
        (3, 6, None),
        (4, 6, None),
    ])
    def test_fill_kind(self, mode, fill_color, expected) -> None:
        el = Element(mode=mode, fill_color=fill_color, w2=0, w3=0,
                     sub_start=0, sub_count=1)
        assert el.fill_kind == expected

    def test_parse_groups(self) -> None:
        header = [46, 10,
                  0, 6, 11, 12, 1,
                  5, 4, 21, 22, 2,
                  3, 2, 4]
        elements = parse_elements(header, [3, 2, 4])
        assert [(e.mode, e.fill_color, e.w2, e.w3,
                 e.sub_start, e.sub_count) for e in elements] == [
            (0, 6, 11, 12, 0, 1),
            (5, 4, 21, 22, 1, 2),
        ]
        assert [e.fill_kind for e in elements] == [6, -1]
        assert sum(e.sub_count for e in elements) == 3

    @pytest.mark.parametrize("header,counts", [
        ([], [2]),                         # 缺少记录头
        ([1, 4], []),                     # 缺少点数表
        ([1, 4, 0, 0, 2], [2]),           # 描述区不是五字块
        ([1, 4, 0, 6, 0, 0, 0, 2], [2]),  # w4=0
        ([1, 4, 0, 6, 0, 0, 2, 2], [2]),  # 子路径范围越界
        ([1, 4, 0, 6, 0, 0, 1, 2, 2], [2, 2]),  # 总组数不足
    ])
    def test_malformed_description_rejected(self, header, counts) -> None:
        assert parse_elements(header, counts) == []

    def test_missing_count_table_does_not_fabricate_elements(self, tmp_path) -> None:
        rec = struct.pack(
            "<8H8f",
            2, 8, 0, 6, 0, 0, 1, 9,
            0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0,
        )
        data = struct.pack("<2I", 8, 8 + len(rec)) + rec + b"\x00" * 32
        path = tmp_path / "Subgraph.lib"
        path.write_bytes(data)

        sym = SubgraphLib(str(path)).decode(0)
        assert sym is not None
        assert len(sym.subpaths) == 1
        assert len(sym.subpaths[0].points) == 4
        assert sym.elements == []

    def test_indexed_decode_populates_elements(self, tmp_path) -> None:
        pts = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0),
               (0.2, 0.2), (0.4, 0.4)]
        rec = (struct.pack("<2H5H5H2H", 46, 10,
                           0, 6, 0, 0, 1,
                           5, 4, 0, 0, 1,
                           3, 2)
               + b"".join(struct.pack("<2f", x, y) for x, y in pts))
        rec_b = struct.pack("<4H2f", 1, 2, 0, 1, 0.1, 0.2)
        data = (struct.pack("<2I", 8, 8 + len(rec))
                + rec + rec_b + b"\x00" * 32)
        path = tmp_path / "Subgraph.lib"
        path.write_bytes(data)

        sym = SubgraphLib(str(path)).decode(0)
        assert sym is not None
        assert [len(sp.points) for sp in sym.subpaths] == [3, 2]
        assert [(e.sub_start, e.sub_count, e.fill_kind)
                for e in sym.elements] == [(0, 1, 6), (1, 1, -1)]
        geo = symbol_geometries(SubgraphLib(str(path)), 0)
        assert geo["elements"] == [
            {"mode": 0, "fill_color": 6, "w2": 0, "w3": 0,
             "sub_start": 0, "sub_count": 1, "fill_kind": 6},
            {"mode": 5, "fill_color": 4, "w2": 0, "w3": 0,
             "sub_start": 1, "sub_count": 1, "fill_kind": -1},
        ]


class TestSlibTailChain:
    """Subgraph.lib 未索引尾段走查 + 末条索引记录 0xBE 假阳性回归。

    合成迷你库：2 条索引记录 + 1 条尾段记录（后跟一条签名合法但无法
    出链的终止签名——模拟真实库 #1996 处的诚实停止）。末条索引记录的
    载荷内嵌 0xBEBEBEBE（旧"0xBE×3 预留区"扫描会在此截断记录区）。
    """

    @staticmethod
    def _record(t: int, pts: list) -> bytes:
        n = 2 * len(pts)
        header = struct.pack("<4H", t, n, 0, len(pts))
        payload = b"".join(struct.pack("<2f", x, y) for x, y in pts)
        return header + payload

    def test_tail_access_and_be_regression(self, tmp_path) -> None:
        rec0 = self._record(1, [(0.1, 0.2), (0.3, 0.4)])
        # 末条索引记录：载荷内埋 0xBEBEBEBE×2（0xBE 假阳性陷阱）
        rec1 = (struct.pack("<4H", 2, 4, 0, 2)
                + struct.pack("<2f", 0.1, 0.2) + b"\xbe" * 8)
        rec2 = self._record(3, [(0.5, 0.5), (0.4, 0.4)])
        # 终止签名：(62, 6) + 6 个正常坐标点后接全零（无法出链 → 停）
        sentinel = (struct.pack("<2H", 62, 6)
                    + struct.pack("<6f", 0.1, 0.2, 0.3, 0.4, 0.5, 0.5))
        data = (struct.pack("<2I", 8, 8 + len(rec0))
                + rec0 + rec1 + rec2 + sentinel + b"\x00" * 32)

        path = tmp_path / "Subgraph.lib"
        path.write_bytes(data)
        lib = SubgraphLib(str(path))

        assert lib.n_indexed == 2
        assert lib.n_tail == 1
        assert lib.symbol_count == 3
        # 末条索引记录不再被 0xBE 截断（旧实现此处返回空记录）
        s1 = lib.decode(1)
        assert s1 is not None and s1.n_points == 2
        assert lib.record_bounds(1) == (8 + len(rec0), 8 + len(rec0) + len(rec1))
        # 尾段符号可达
        s2 = lib.decode(2)
        assert s2 is not None and s2.type == 3 and s2.n_points == 2
        # 越界诚实返回 None
        assert lib.decode(3) is None


class TestSlibCenterRefCircle:
    """中心三点组整圆判读（[圆心, 半径参考点, 圆心回点]，全 type）。

    回归锚（2026-10-15 全库扫描 + 符号 7 用户裁定 r≈0.315；2026-10-18
    子图 21 裁定扩展至 type≠6，解除 #56 内圆挂账）：判圆仅当首尾≈同点
    （≤0.01mm）、参考点双侧等距（±2%）、r∈[0.005,1.0]；不满足维持
    点序直连（不产生新 artifact）。
    """

    @staticmethod
    def _record(t: int, pts: list) -> bytes:
        n = 2 * len(pts)
        header = struct.pack("<4H", t, n, 0, len(pts))
        payload = b"".join(struct.pack("<2f", x, y) for x, y in pts)
        return header + payload

    def _lib_with(self, tmp_path, rec: bytes) -> "SubgraphLib":
        # 与 TestSlibTailChain 同构：双槽索引（首 u32 兼作表末标记，
        # 故至少 2 槽），被测记录居槽 0，槽 1 占位 + 全零尾使走查诚实停止。
        rec_b = self._record(1, [(0.4, 0.4), (0.3, 0.3)])
        data = (struct.pack("<2I", 8, 8 + len(rec))
                + rec + rec_b + b"\x00" * 32)
        path = tmp_path / "Subgraph.lib"
        path.write_bytes(data)
        return SubgraphLib(str(path))

    def test_center_ref_circle_detected(self, tmp_path) -> None:
        # 符号 7 子路径 0 实测结构：圆心≈原点、参考点 (0.316, 0)
        rec = self._record(6, [(-0.004, 0.004), (0.316, 0.0), (0.0, 0.0)])
        lib = self._lib_with(tmp_path, rec)
        s = lib.decode(0)
        assert s is not None and s.type == 6
        sp = s.subpaths[0]
        assert sp.closed
        cx, cy, r = sp.circle
        assert cx == pytest.approx(-0.002, abs=1e-6)
        assert cy == pytest.approx(0.002, abs=1e-6)
        assert r == pytest.approx(0.3180125, abs=1e-6)  # ≈ 裁定 0.315

    def test_non_equidistant_rejected(self, tmp_path) -> None:
        # 符号 7 子路径 1 实测结构：参考点双侧不等距 → 维持直连不判圆
        rec = self._record(6, [(-0.003, 0.004), (0.009, 0.0), (0.0, 0.0)])
        lib = self._lib_with(tmp_path, rec)
        s = lib.decode(0)
        sp = s.subpaths[0]
        assert sp.circle is None
        assert not sp.closed

    def test_type_gate(self, tmp_path) -> None:
        # 2026-10-18 用户裁定：同构三点组在 type≠6 记录中同样判圆
        # （子图 21 裁定 + #56 内圆挂账解除；原边界门移除）
        rec = self._record(2, [(0.0, 0.0), (0.32, 0.0), (0.0, 0.0)])
        lib = self._lib_with(tmp_path, rec)
        s = lib.decode(0)
        sp = s.subpaths[0]
        assert sp.circle is not None
        assert sp.closed
        assert sp.circle[2] == pytest.approx(0.32)


class TestSlibThreePointArc:
    """三点参数弧组判读（2026-10-18 子图 23 用户图面裁定定案）。

    [圆心, (半径, 弧起角), (弧终角, 0)]：哨兵 0xB3000000（双槽）→ 整圆；
    起终角非零 → 逆时针弧段。门须拒普通三点折线与退化零值组。
    """

    @staticmethod
    def _record(t: int, pts: list) -> bytes:
        n = 2 * len(pts)
        header = struct.pack("<4H", t, n, 0, len(pts))
        payload = b"".join(struct.pack("<2f", x, y) for x, y in pts)
        return header + payload

    def _lib_with(self, tmp_path, rec: bytes) -> "SubgraphLib":
        rec_b = self._record(1, [(0.4, 0.4), (0.3, 0.3)])
        data = (struct.pack("<2I", 8, 8 + len(rec))
                + rec + rec_b + b"\x00" * 32)
        path = tmp_path / "Subgraph.lib"
        path.write_bytes(data)
        return SubgraphLib(str(path))

    @staticmethod
    def _sentinel() -> float:
        return struct.unpack("<f", b"\x00\x00\x00\xb3")[0]

    def test_arc_detected(self, tmp_path) -> None:
        # 子图 23 sp30 实测结构：左下弧段 174°→273°（= -87.14 mod 360）
        rec = self._record(46, [(0.5549, 0.1494), (0.0291, 173.9906),
                                (-87.1374, 0.0)])
        s = self._lib_with(tmp_path, rec).decode(0)
        sp = s.subpaths[0]
        assert sp.arc is not None and sp.circle is None
        cx, cy, r, a0, a1 = sp.arc
        assert cx == pytest.approx(0.5549)
        assert cy == pytest.approx(0.1494)
        assert r == pytest.approx(0.0291)
        assert a0 == pytest.approx(173.9906 % 360.0)
        assert a1 == pytest.approx(272.8626, abs=0.001)

    def test_sentinel_circle(self, tmp_path) -> None:
        # 子图 23 空槽：双哨兵 → 整圆 r=B.x
        sen = self._sentinel()
        rec = self._record(46, [(0.5488, 0.1402), (0.0550, sen), (sen, 0.0)])
        s = self._lib_with(tmp_path, rec).decode(0)
        sp = s.subpaths[0]
        assert sp.circle is not None and sp.arc is None
        assert sp.closed
        assert sp.circle == pytest.approx((0.5488, 0.1402, 0.0550))

    def test_explicit_zero_to_360_circle(self, tmp_path) -> None:
        # #41/#42：显式 0°→360° 与双哨兵一样表示整圆。
        rec = self._record(46, [(0.5, 0.5), (0.2, 0.0), (360.0, 0.0)])
        s = self._lib_with(tmp_path, rec).decode(0)
        sp = s.subpaths[0]
        assert sp.circle == pytest.approx((0.5, 0.5, 0.2))
        assert sp.arc is None and sp.closed

    def test_zero_start_half_circle(self, tmp_path) -> None:
        # #25：起角 0° 合法，不得把 0°→180° 半圆当普通三点折线。
        rec = self._record(46, [(0.5, 0.5), (0.2, 0.0), (180.0, 0.0)])
        s = self._lib_with(tmp_path, rec).decode(0)
        sp = s.subpaths[0]
        assert sp.circle is None
        assert sp.arc == pytest.approx((0.5, 0.5, 0.2, 0.0, 180.0))

    def test_plain_zero_rejected(self, tmp_path) -> None:
        # 退化零值组（符号 7 不对称小子路径同构）非哨兵 → 不判圆（回归锚）
        rec = self._record(6, [(-0.003, 0.004), (0.009, 0.0), (0.0, 0.0)])
        s = self._lib_with(tmp_path, rec).decode(0)
        sp = s.subpaths[0]
        assert sp.circle is None and sp.arc is None

    def test_center_ref_shape_rejected(self, tmp_path) -> None:
        # 符号 7 sp1 实测结构：尾值带 0xB3000000 哨兵但 p0≈p2 且双侧
        # 不等距（r1≈0.0132 vs r2≈0.0094）→ 中心参考圆通道的"断笔"，
        # 不得被哨兵整圆分支吞掉（2026-10-18 回归锚）
        sen = self._sentinel()
        rec = self._record(6, [(-0.0031, 0.0042), (0.0094, sen), (sen, sen)])
        s = self._lib_with(tmp_path, rec).decode(0)
        sp = s.subpaths[0]
        assert sp.circle is None and sp.arc is None

    def test_p2y_nonzero_rejected(self, tmp_path) -> None:
        rec = self._record(2, [(0.5, 0.5), (0.05, 170.0), (260.0, 0.3)])
        s = self._lib_with(tmp_path, rec).decode(0)
        assert s.subpaths[0].arc is None

    def test_degenerate_sweep_rejected(self, tmp_path) -> None:
        rec = self._record(2, [(0.5, 0.5), (0.05, 170.0), (172.0, 0.0)])
        s = self._lib_with(tmp_path, rec).decode(0)
        assert s.subpaths[0].arc is None

    def test_radius_out_of_range_rejected(self, tmp_path) -> None:
        rec = self._record(2, [(0.5, 0.5), (3.0, 170.0), (260.0, 0.0)])
        s = self._lib_with(tmp_path, rec).decode(0)
        assert s.subpaths[0].arc is None


class TestSlibRegion:
    """尾段区域（#1996 起）记录模型与走查（2026-10-18 破解定案）。

    模型：(u16 type, u16 n) + 描述区（10B 块×L，内容不透明）+
    点数表（k 项 ≥2，总和==n//2）+ n×4 f32 载荷；三重验证 +
    前瞻 3 选链。D:/SLIB 实证 5364 条 100% 覆盖（不在测试内，
    测试用合成夹具验证机制与诚实停止）。
    """

    @staticmethod
    def _region_record(t: int, descs: list, counts: list,
                       pts: list) -> bytes:
        """合成一条尾段区域记录：描述块 + 点数表 + 坐标载荷。"""
        assert sum(counts) == len(pts)
        n = 2 * len(pts)
        blocks = b"".join(struct.pack("<5H", *d) for d in descs)
        return (struct.pack("<HH", t, n) + blocks
                + struct.pack(f"<{len(counts)}H", *counts)
                + b"".join(struct.pack("<2f", x, y) for x, y in pts))

    @staticmethod
    def _record(t: int, pts: list) -> bytes:
        n = 2 * len(pts)
        header = struct.pack("<4H", t, n, 0, len(pts))
        payload = b"".join(struct.pack("<2f", x, y) for x, y in pts)
        return header + payload

    @staticmethod
    def _big_header_region_record() -> bytes:
        """真实 #1996 同型的区域首记录：t=62、n=372、52 描述块（头 648B
        超出旧走查 512B 扫描上限）+ 62×3 点数表 + 186 坐标。"""
        pts = [(0.01 * i, 0.01 * i) for i in range(186)]
        blocks = b"".join(struct.pack("<5H", 6, 0, 0, 0, 1) for _ in range(52))
        return (struct.pack("<HH", 62, 372) + blocks
                + struct.pack("<62H", *([3] * 62))
                + b"".join(struct.pack("<2f", x, y) for x, y in pts))

    def _lib_with_region(self, tmp_path, extra: bytes = b"") -> "SubgraphLib":
        """复刻真实库边界机制：2 索引 + 1 尾链 + 大头区域首记录 +
        FF00 止链填充（任意字节对齐的 (t,n) 均不过 _rec_like——
        偶对齐 t=255/n=255 奇，奇对齐 t=65280 超限）。"""
        rec0 = self._record(1, [(0.1, 0.2), (0.3, 0.4)])
        rec1 = self._record(2, [(0.2, 0.1), (0.4, 0.3)])
        recT = self._record(3, [(0.5, 0.5), (0.4, 0.4)])
        rec3 = self._big_header_region_record()
        data = (struct.pack("<2I", 8, 8 + len(rec0))
                + rec0 + rec1 + recT + rec3 + extra + b"\xff\x00" * 32)
        path = tmp_path / "Subgraph.lib"
        path.write_bytes(data)
        return SubgraphLib(str(path))

    def test_region_record_decoded(self, tmp_path) -> None:
        lib = self._lib_with_region(tmp_path)
        s = lib.decode(3)  # n_indexed=2 + n_tail=1 → 区域首条 = #3
        assert s is not None
        assert s.type == 62
        assert [len(sp.points) for sp in s.subpaths] == [3] * 62

    def test_region_honest_stop(self, tmp_path) -> None:
        """区域后的止链填充不得解码：越界返回 None。"""
        lib = self._lib_with_region(tmp_path)
        lib._walk_region()
        assert lib.decode(2 + lib.n_tail + 1) is None

    def test_region_symbol_count_includes_walked(self, tmp_path) -> None:
        lib = self._lib_with_region(tmp_path)
        assert lib.symbol_count == 2 + lib.n_tail + 1

    def test_region_dense_record_uses_header_window_not_point_count(self, tmp_path) -> None:
        """n>13120 的合法密集记录不得被 npts>_REGION_WIN 误拒。"""
        dense = self._region_record(
            300, [], [2] * 3500, [(0.01, 0.01)] * 7000
        )
        lib = self._lib_with_region(tmp_path, extra=dense)
        symbol = lib.decode(2 + lib.n_tail + 1)
        assert symbol is not None
        assert symbol.n == 14000
        assert len(symbol.subpaths) == 3500
        assert all(len(path.points) == 2 for path in symbol.subpaths)


class TestSlibTruncatedInputs:
    @pytest.mark.parametrize("data", [
        struct.pack("<I", 4),
        struct.pack("<2I", 8, 16),
        b"",
    ])
    def test_index_only_or_truncated_index_stops_honestly(self, tmp_path, data) -> None:
        path = tmp_path / "Subgraph.lib"
        path.write_bytes(data)
        lib = SubgraphLib(str(path))
        assert lib.n_tail == 0
        assert lib.n_region == 0
        assert lib.decode(0) is None

    def test_mid_record_truncation_stops_honestly(self, tmp_path) -> None:
        """合法后继记录头后载荷不完整时，双门抽样不得越过 EOF。"""
        rec0 = TestSlibRegion._record(1, [(0.1, 0.2), (0.3, 0.4)])
        rec1 = TestSlibRegion._record(2, [(0.2, 0.1), (0.4, 0.3)])
        rec_tail = TestSlibRegion._record(3, [(0.5, 0.5), (0.4, 0.4)])
        rec_region = TestSlibRegion._big_header_region_record()
        data = (struct.pack("<2I", 8, 8 + len(rec0))
                + rec0 + rec1 + rec_tail + rec_region + b"\xff\x00" * 32)
        path = tmp_path / "Subgraph.lib"
        path.write_bytes(data[:97])
        lib = SubgraphLib(str(path))
        assert lib.n_tail == 1
        assert lib.decode(2 + lib.n_tail) is None


class TestSlibDenseRmsGate:
    """密集弧拟合残差门（2026-10-18）：非圆曲线不得判圆/弧。

    库内真圆/弧为精确圆（锚 rms=0.00000）；#7331 波浪闭合环
    rms≈0.09 被门拒绝维持折线（用户图面锚）。
    """

    @staticmethod
    def _wavy_loop() -> list:
        """r≈0.29 圆上叠 ±0.09 径向正弦扰动的 32 点闭合环。"""
        import math as _m
        pts = []
        for i in range(32):
            a = 2 * _m.pi * i / 32
            r = 0.29 + 0.09 * _m.sin(5 * a)
            pts.append((0.04 + r * _m.cos(a), 0.04 + r * _m.sin(a)))
        return pts

    def _lib_with_pts(self, tmp_path, pts: list) -> "SubgraphLib":
        n = 2 * len(pts)
        header = struct.pack("<4H", 3, n, 0, len(pts))
        payload = b"".join(struct.pack("<2f", x, y) for x, y in pts)
        rec = header + payload
        rec_b = struct.pack("<4H", 1, 4, 0, 2) + struct.pack(
            "<4f", 0.4, 0.4, 0.3, 0.3)
        data = (struct.pack("<2I", 8, 8 + len(rec))
                + rec + rec_b + b"\x00" * 32)
        path = tmp_path / "Subgraph.lib"
        path.write_bytes(data)
        return SubgraphLib(str(path))

    def test_wavy_loop_not_circle(self, tmp_path) -> None:
        lib = self._lib_with_pts(tmp_path, self._wavy_loop())
        s = lib.decode(0)
        sp = s.subpaths[0]
        assert sp.circle is None and sp.arc is None

    def test_exact_circle_still_classified(self, tmp_path) -> None:
        import math as _m
        pts = [(0.04 + 0.29 * _m.cos(2 * _m.pi * i / 32),
                0.04 + 0.29 * _m.sin(2 * _m.pi * i / 32))
               for i in range(32)]
        pts.append(pts[0])  # 首尾闭合（库内整圆实证 d<0.01）
        lib = self._lib_with_pts(tmp_path, pts)
        s = lib.decode(0)
        assert s.subpaths[0].circle is not None
        assert s.subpaths[0].closed


class TestFillgrph:
    """Fillgrph.lib 图案解析（2026-10-19 记录结构定案）。

    记录 = [grid][unit][M×（10B 笔块 + 2B 对数）][坐标区]；笔块
    kind：0=填充多边形、1/2=折线、3=弧（度）、4/5/6=圆弧族。
    渲染 = 逐笔划消费，笔划分组由文件自身给出——无需逐图案裁定。
    """

    @staticmethod
    def _record(grid: int, unit: int, spec, pairs) -> bytes:
        """合成记录：spec = [(笔块 5 元组, 对数), ...]，pairs = 坐标对。

        布局与实库一致：笔块表在前、计数表随后（非交错）。"""
        header = struct.pack("<HH", grid, unit)
        blocks = b"".join(struct.pack("<5H", *b) for b, _ in spec)
        counts = b"".join(struct.pack("<H", c) for _, c in spec)
        payload = b"".join(struct.pack("<2f", x, y) for x, y in pairs)
        return header + blocks + counts + payload

    def _lib_with(self, tmp_path, rec: bytes, no: int = 220):
        from pymapgis.fillgrph import FillgrphLib
        n = max(no, 220)
        off = 6 + n * 6
        # 索引区：槽 no-1 指向记录，其余全 0（槽后不得跟记录字节——
        # 否则 record_bounds 会把记录误读为后续槽的偏移）
        data = (struct.pack("<I", n) + struct.pack("<H", 0)
                + b"\x00" * ((no - 1) * 6) + struct.pack("<IH", off, 1)
                + b"\x00" * ((n - no) * 6) + rec)
        path = tmp_path / "Fillgrph.lib"
        path.write_bytes(data)
        return FillgrphLib(str(path))

    # ---- 220：实库结构（8 笔划：双 N 填充环 + 四线笔划 +
    #      双 N 轮廓描边（kind=2 宽 3 复用环坐标）） ----
    _P220 = [
        ((0, 0, 0, 0, 1), 10), ((0, 0, 0, 0, 1), 10),
        ((2, 0, 0, 4, 1), 3), ((2, 0, 0, 4, 1), 2),
        ((2, 0, 0, 3, 1), 3), ((2, 0, 0, 3, 1), 2),
        ((2, 0, 0, 3, 1), 10), ((2, 0, 0, 3, 1), 10),
    ]
    _RING1 = [(0.3943, 0.6548), (0.3943, 0.6059), (0.3935, 0.6060),
              (0.3728, 0.6253), (0.3540, 0.6419), (0.3540, 0.6542),
              (0.3540, 0.6542), (0.3540, 0.8748), (0.3943, 0.8748),
              (0.3943, 0.6548)]
    _RING2 = [(0.8997, 0.1537), (0.8997, 0.1048), (0.8989, 0.1049),
              (0.8782, 0.1242), (0.8594, 0.1408), (0.8594, 0.1531),
              (0.8594, 0.1531), (0.8594, 0.3737), (0.8997, 0.3737),
              (0.8997, 0.1537)]
    _LINES = [(0.0985, 0.6058), (0.0985, 0.8748), (0.3916, 0.6082),
              (0.3943, 0.6059), (0.3943, 0.6058), (0.6039, 0.1048),
              (0.6039, 0.3737), (0.8970, 0.1071), (0.8997, 0.1048),
              (0.8997, 0.1048)]

    def _rec_220(self) -> bytes:
        return self._record(8, 100, self._P220,
                            self._RING1 + self._RING2 + self._LINES
                            + self._RING1 + self._RING2)

    def test_decode_220_structure(self, tmp_path) -> None:
        lib = self._lib_with(tmp_path, self._rec_220())
        pat = lib.decode(220)
        assert pat is not None
        assert pat.grid == 8 and pat.unit == 100
        assert len(pat.strokes) == 8          # 2 填充 + 4 线 + 2 环轮廓描边
        assert sum(len(s.points) for s in pat.strokes) == 50
        assert len(pat.raw_points) == 50
        assert len(pat.points) == 23          # 夹具全记录精确去重（实库 24）

    def test_220_geometry_rings_and_lines(self, tmp_path) -> None:
        from pymapgis.fillgrph import pattern_geometry
        lib = self._lib_with(tmp_path, self._rec_220())
        geo = pattern_geometry(lib, 220)
        assert geo is not None
        # 填充区：两个 N 轮廓环（8 顶点——(0.3935,0.6060) 凹口为文件
        # 真实几何，F1 审计后按位保留；环序与目视裁定锚一致）
        assert len(geo["fill_polygons"]) == 2
        ring0 = geo["fill_polygons"][0]
        assert len(ring0) == 8
        assert ring0[0] == pytest.approx((0.3943, 0.6548), abs=1e-3)
        assert ring0[2] == pytest.approx((0.3935, 0.6060), abs=1e-3)
        assert ring0[4] == pytest.approx((0.3540, 0.6419), abs=1e-3)
        assert ring0[7] == pytest.approx((0.3943, 0.8748), abs=1e-3)
        assert len(geo["fill_polygons"][1]) == 8
        # 线笔划：两条连线 + 两条环轮廓描边；两个落笔微段（总长
        # <0.01mm）剔除并计数
        assert [len(line) for line in geo["polylines"]] == [3, 3, 9, 9]
        assert geo["polylines"][0][0] == pytest.approx((0.0985, 0.6058), abs=1e-3)
        assert geo["polylines"][0][2] == pytest.approx((0.3916, 0.6082), abs=1e-3)
        assert geo["polylines"][1][0] == pytest.approx((0.6039, 0.1048), abs=1e-3)
        assert geo["polylines"][2][0] == pytest.approx((0.3943, 0.6548), abs=1e-3)
        assert geo["polylines"][2][-1] == pytest.approx((0.3943, 0.6548), abs=1e-3)
        assert geo["dropped"] == 2
        assert geo["circles"] == [] and geo["arcs"] == []

    def test_dense_curve_not_wiped(self, tmp_path) -> None:
        """F1 回归锚：0.001 级间距的密集曲线不得被冗余合并摧毁。"""
        from pymapgis.fillgrph import pattern_geometry
        # 11 点密集填充环（间距 0.001 级——140 号实证形态）+ 一条密集折线
        dense = [(0.500 + 0.045 * i, 0.250 + 0.012 * math.sin(i * 0.9))
                 for i in range(11)]
        dense.append(dense[0])
        line = [(0.1 + 0.001 * i, 0.05 + 0.0004 * i) for i in range(20)]
        spec = [((0, 0, 0, 0, 1), len(dense)), ((2, 0, 0, 4, 1), len(line))]
        lib = self._lib_with(tmp_path, self._record(4, 24, spec,
                                                    dense + line), no=260)
        geo = pattern_geometry(lib, 260)
        assert geo is not None
        assert len(geo["fill_polygons"]) == 1
        assert len(geo["fill_polygons"][0]) == 11    # 密集顶点全保留
        assert len(geo["polylines"][0]) == 20
        assert geo["dropped"] == 0

    def test_signed_zero_uses_bitwise_identity(self, tmp_path) -> None:
        """±0 的数值相等不代表 f32 位型相同，不得作为重复点合并。"""
        from pymapgis.fillgrph import pattern_geometry
        pts = [(0.0, 0.0), (-0.0, 0.0), (0.0, 0.0),
               (-0.0, -0.0), (-0.0, -0.0), (1.0, 1.0)]
        spec = [((2, 0, 0, 4, 1), len(pts))]
        lib = self._lib_with(tmp_path, self._record(4, 24, spec, pts), no=260)
        pat = lib.decode(260)
        assert pat is not None
        # 全记录去重：(0,0)、(-0,0)、(-0,-0)、(1,1) 四种位型。
        assert len(pat.points) == 4
        assert struct.pack("<2f", *pat.points[0]) != struct.pack(
            "<2f", *pat.points[1]
        )
        geo = pattern_geometry(lib, 260)
        assert geo is not None
        # 连续去重仅移除第二个完全同位型的 (-0,-0)。
        assert len(geo["polylines"][0]) == 5

    def test_record_bounds_use_next_greater_offset(self, tmp_path) -> None:
        """预计算边界仍遵守非单调索引的“下一个更大偏移”规则。"""
        from pymapgis.fillgrph import FillgrphLib
        entries = (struct.pack("<IH", 40, 1) + struct.pack("<IH", 24, 1)
                   + struct.pack("<IH", 56, 1))
        data = (struct.pack("<I", 3) + b"\x00\x00" + entries
                + b"\x00" * 48)
        path = tmp_path / "Fillgrph.lib"
        path.write_bytes(data)
        lib = FillgrphLib(str(path))
        assert lib.record_bounds(1) == (40, 56)
        assert lib.record_bounds(2) == (24, 40)
        assert lib.record_bounds(3) == (56, 72)

    def test_243_252_247_253_polylines(self, tmp_path) -> None:
        from pymapgis.fillgrph import pattern_geometry
        # 243：2 用户折线 = 4 文件笔划（回描段省略——视觉等价）
        spec = [((2, 0, 0, 4, 1), 4), ((2, 0, 0, 4, 1), 2)] * 2
        pts = [(0.3415, 0.8636), (0.1755, 0.8636), (0.1755, 0.8636),
               (0.1755, 0.6145), (0.1755, 0.7391), (0.3083, 0.7391),
               (0.8383, 0.3625), (0.6722, 0.3625), (0.6722, 0.3625),
               (0.6722, 0.1135), (0.6722, 0.2380), (0.8051, 0.2380)]
        lib = self._lib_with(tmp_path, self._record(4, 24, spec, pts), no=243)
        geo = pattern_geometry(lib, 243)
        assert geo is not None
        assert geo["fill_polygons"] == []
        assert len(geo["polylines"]) == 4
        assert geo["polylines"][0][0] == pytest.approx((0.3415, 0.8636), abs=1e-3)
        assert geo["polylines"][0][2] == pytest.approx((0.1755, 0.6145), abs=1e-3)
        assert geo["polylines"][1][0] == pytest.approx((0.1755, 0.7391), abs=1e-3)
        # 252：2 用户 T 形 = 4 笔划（横杠/竖茎各一）
        spec = [((2, 0, 0, 4, 1), 2)] * 4
        pts = [(0.0928, 0.6722), (0.3918, 0.6722), (0.2423, 0.6722),
               (0.2423, 0.8217),
               (0.5925, 0.1725), (0.8915, 0.1725), (0.7420, 0.1725),
               (0.7420, 0.3220)]
        lib = self._lib_with(tmp_path, self._record(4, 16, spec, pts), no=252)
        geo = pattern_geometry(lib, 252)
        assert len(geo["polylines"]) == 4
        assert geo["polylines"][1][0] == pytest.approx((0.2423, 0.6722), abs=1e-3)
        # 247：4 用户折线 = 6 笔划（两 T 各 2 + 两 L 各 1）
        spec = [((2, 0, 0, 4, 1), 2)] * 4 + [((2, 0, 0, 4, 1), 3)] * 2
        pts = [(0.1322, 0.8067), (0.3805, 0.8067), (0.2563, 0.8067),
               (0.2563, 0.6713),
               (0.6289, 0.3056), (0.8772, 0.3056), (0.7531, 0.3056),
               (0.7531, 0.1702),
               (0.8477, 0.8387), (0.6490, 0.8387), (0.6490, 0.6400),
               (0.3553, 0.3289), (0.1566, 0.3289), (0.1566, 0.1302)]
        lib = self._lib_with(tmp_path, self._record(6, 28, spec, pts), no=247)
        geo = pattern_geometry(lib, 247)
        assert len(geo["polylines"]) == 6
        assert geo["polylines"][4][0] == pytest.approx((0.8477, 0.8387), abs=1e-3)
        assert geo["polylines"][4][2] == pytest.approx((0.6490, 0.6400), abs=1e-3)
        assert geo["polylines"][5][0] == pytest.approx((0.3553, 0.3289), abs=1e-3)
        # 253：四角组 = 两对角线各一（X 形），T 组同 252
        spec = [((2, 0, 0, 4, 1), 2)] * 8
        pts = [(0.0928, 0.6722), (0.3918, 0.6722), (0.2423, 0.6722),
               (0.2423, 0.8217),
               (0.1479, 0.1072), (0.3350, 0.3567), (0.1479, 0.3567),
               (0.3350, 0.1072),
               (0.6452, 0.6293), (0.8323, 0.8788), (0.6452, 0.8788),
               (0.8323, 0.6293),
               (0.5925, 0.1725), (0.8915, 0.1725), (0.7420, 0.1725),
               (0.7420, 0.3220)]
        lib = self._lib_with(tmp_path, self._record(8, 32, spec, pts), no=253)
        geo = pattern_geometry(lib, 253)
        assert len(geo["polylines"]) == 8
        assert geo["polylines"][2][0] == pytest.approx((0.1479, 0.1072), abs=1e-3)
        assert geo["polylines"][2][1] == pytest.approx((0.3350, 0.3567), abs=1e-3)
        assert geo["polylines"][3][0] == pytest.approx((0.1479, 0.3567), abs=1e-3)
        assert geo["polylines"][3][1] == pytest.approx((0.3350, 0.1072), abs=1e-3)

    def test_circles_pattern_6(self, tmp_path) -> None:
        from pymapgis.fillgrph import pattern_geometry
        # 图案 6（实库）：8 个点圆（kind=5 满载整圆）
        spec = [((5, 0, 0, 1, 1), 3)] * 8
        pts = [(0.2, 0.8), (0.03125, 0.0), (0.0, 0.0),
               (0.7, 0.8), (0.03125, 0.0), (0.0, 0.0),
               (0.45, 0.55), (0.03125, 0.0), (0.0, 0.0),
               (0.95, 0.55), (0.03125, 0.0), (0.0, 0.0),
               (0.2, 0.3), (0.03125, 0.0), (0.0, 0.0),
               (0.7, 0.3), (0.03125, 0.0), (0.0, 0.0),
               (0.95, 0.05), (0.03125, 0.0), (0.0, 0.0),
               (0.45, 0.05), (0.03125, 0.0), (0.0, 0.0)]
        lib = self._lib_with(tmp_path, self._record(1, 10, spec, pts), no=6)
        geo = pattern_geometry(lib, 6)
        assert geo is not None
        assert geo["polylines"] == [] and geo["arcs"] == []
        assert len(geo["circles"]) == 8
        assert geo["circles"][0] == pytest.approx((0.2, 0.8, 0.03125), abs=1e-3)

    def test_arcs_pattern_725(self, tmp_path) -> None:
        from pymapgis.fillgrph import pattern_geometry
        # 图案 725（实库）：4 段象限弧（kind=3 角度制）
        spec = [((3, 0, 0, 0, 1), 3)] * 4
        pts = [(0.25, 0.0), (0.3492, 45.7252), (135.0, 0.0),
               (0.25, 0.5), (0.3536, 45.0), (135.0, 0.0),
               (0.75, 1.0), (0.3536, 225.0), (-45.0, 0.0),
               (0.75, 0.5), (0.3536, 225.0), (-45.0, 0.0)]
        lib = self._lib_with(tmp_path, self._record(1, 6, spec, pts), no=725)
        geo = pattern_geometry(lib, 725)
        assert geo is not None
        assert geo["polylines"] == [] and geo["circles"] == []
        assert len(geo["arcs"]) == 4
        assert geo["arcs"][0] == pytest.approx(
            (0.25, 0.0, 0.3492, 45.7252, 135.0), abs=1e-3)
        assert geo["arcs"][2][2:] == pytest.approx((0.3536, 225.0, -45.0), abs=1e-3)

    def test_zero_coordinate_and_nonconforming(self, tmp_path) -> None:
        from pymapgis.fillgrph import pattern_geometry
        # 坐标从 (0,0) 起（250/251 教训）：结构定位不依赖坐标值
        spec = [((2, 0, 0, 4, 1), 2)] * 2
        pts = [(0.0, 0.0), (0.5, 0.675), (0.7, 0.0), (1.0, 0.675)]
        lib = self._lib_with(tmp_path, self._record(8, 32, spec, pts), no=250)
        geo = pattern_geometry(lib, 250)
        assert geo is not None
        assert geo["polylines"][0][0] == pytest.approx((0.0, 0.0), abs=1e-6)
        # 旧式/异型记录（无 12M 描述区）：诚实返回 None
        rec = struct.pack("<HH", 8, 100) + b"\x00" * 96 + b"\x00" * 64
        lib = self._lib_with(tmp_path, rec, no=221)
        assert lib.decode(221) is None
        assert pattern_geometry(lib, 221) is None


class TestSlibDigitTemplate:
    """数字 1 模板槽判定（2026-10-19 用户图面裁定定案）。

    符号编辑器存模板数字 "1"（15 点闭合轮廓：斜帽+竖干+底座），
    实例化时替换为实际编号；存储点是描线不是几何，须排除出弧/圆
    分类。锚：#2591/#2600 sp0 实测；345 族符号普查。
    """

    @staticmethod
    def _digit1_pts() -> list:
        """#2591 sp0 实测 15 点轮廓（原位）。"""
        return [(-0.261, 0.109), (-0.269, 0.109), (-0.291, 0.097),
                (-0.289, 0.097), (-0.274, 0.101), (-0.274, 0.091),
                (-0.274, 0.018), (-0.275, 0.014), (-0.285, 0.010),
                (-0.251, 0.010), (-0.259, 0.014), (-0.261, 0.014),
                (-0.261, 0.018), (-0.261, 0.109), (-0.261, 0.109)]

    def _lib_with_pts(self, tmp_path, pts: list) -> "SubgraphLib":
        n = 2 * len(pts)
        header = struct.pack("<4H", 3, n, 0, len(pts))
        payload = b"".join(struct.pack("<2f", x, y) for x, y in pts)
        rec = header + payload
        rec_b = struct.pack("<4H", 1, 4, 0, 2) + struct.pack(
            "<4f", 0.4, 0.4, 0.3, 0.3)
        data = (struct.pack("<2I", 8, 8 + len(rec))
                + rec + rec_b + b"\x00" * 32)
        path = tmp_path / "Subgraph.lib"
        path.write_bytes(data)
        return SubgraphLib(str(path))

    def test_digit_one_detected(self, tmp_path) -> None:
        lib = self._lib_with_pts(tmp_path, self._digit1_pts())
        s = lib.decode(0)
        sp = s.subpaths[0]
        assert sp.template_digit == 1
        assert sp.arc is None and sp.circle is None

    def test_plain_closed_polyline_rejected(self, tmp_path) -> None:
        """纯矩形竖条（无斜帽横伸）不得误判为数字 1。"""
        cx, cy, w, h = 0.0, 0.0, 0.04, 0.10
        rect = [(cx - w/2, cy - h/2), (cx + w/2, cy - h/2),
                (cx + w/2, cy + h/2), (cx - w/2, cy + h/2)]
        pts = []
        for i in range(4):
            a, b = rect[i], rect[(i + 1) % 4]
            for k in range(3):
                t = k / 3.0
                pts.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        pts = (pts * 2)[:15]
        pts.append(pts[0])
        lib = self._lib_with_pts(tmp_path, pts)
        s = lib.decode(0)
        assert s.subpaths[0].template_digit is None

    def test_2591_no_false_arc(self, tmp_path) -> None:
        """#2591 sp0 结构：数字 1 判定优先，密集弧不得误吞为弧段。"""
        lib = self._lib_with_pts(tmp_path, self._digit1_pts())
        s = lib.decode(0)
        assert s.subpaths[0].arc is None
        assert s.subpaths[0].template_digit == 1


class TestConsumptionLaw:
    """offset 即载荷 f32 索引通用律（2026-10-20 定案，全库 984/984）。

    元素模板 offset = 该元素载荷区起始 f32 索引；默认 2×marker 律
    只是 offset 与 marker 一致的特例（388/147/16|0 变体实证）。
    """

    @staticmethod
    def _style(f32, elems, solid=False):
        from pymapgis.linesty import Element, LineStyle, SubLine
        if solid:
            sl = SubLine(n=1, length=24,
                         elements=[Element(unit=0, marker=2, offset=0)],
                         f32_zone=list(f32), f32_start=8)
            sl.width = f32[2] if len(f32) > 2 else None
            sl.yoff = f32[1] if len(f32) > 1 else None
        else:
            sl = SubLine(n=len(elems), length=2 + 6 * len(elems) + 4 * len(f32),
                         elements=[Element(unit=u, marker=m, offset=o)
                                   for u, m, o in elems],
                         f32_zone=list(f32), f32_start=2 + 6 * len(elems))
        return LineStyle(no=900, n_subs=1, sublines=[sl])

    def test_default_law_case(self) -> None:
        # 3|0：(0,2,0),(3,3,4) → 区间 [(0,4),(4,10)]
        sl = self._style([0.0] * 10, ((0, 2, 0), (3, 3, 4))).sublines[0]
        assert sl.consumption == [(0, 4), (4, 10)]

    def test_triple_variant_16(self) -> None:
        # 16|0：4 引用 offset 0/3/6/9 → 三元组区间
        sl = self._style([0.0] * 12, ((258, 2, 0), (258, 2, 3),
                                      (258, 2, 6), (259, 2, 9))).sublines[0]
        assert sl.consumption == [(0, 3), (3, 6), (6, 9), (9, 12)]

    def test_mixed_variant_388(self) -> None:
        # 388|0：offset 0/12/15/18/21/24/27/30/34 → [12,3,3,3,3,3,3,4,4]
        elems = ((1, 6, 0), (2, 2, 12), (3, 2, 15), (2, 2, 18), (3, 2, 21),
                 (2, 2, 24), (3, 2, 27), (0, 2, 30), (0, 2, 34))
        sl = self._style([0.0] * 38, elems).sublines[0]
        assert sl.consumption == [(0, 12), (12, 15), (15, 18), (18, 21),
                                  (21, 24), (24, 27), (27, 30), (30, 34),
                                  (34, 38)]

    def test_147_refs_variant(self) -> None:
        # 147|0：12 三元组引用 + 3 线对
        elems = [(2562, 2, 3 * i) for i in range(12)] + \
                [(768, 2, 36 + 4 * i) for i in range(3)]
        sl = self._style([0.0] * 48, elems).sublines[0]
        iv = sl.consumption
        assert iv[:12] == [(3 * i, 3 * i + 3) for i in range(12)]
        assert iv[12:] == [(36, 40), (40, 44), (44, 48)]

    def test_solid_pen(self) -> None:
        sl = self._style([0.0, -0.0012, 0.635, -0.0012], (), solid=True).sublines[0]
        assert sl.consumption == [(0, 4)]
        assert sl.seg == (0.0, -0.0012, 0.635, -0.0012)

    def test_unresolvable_honest_none(self) -> None:
        # offset 非单调 → None
        sl = self._style([0.0] * 8, ((0, 2, 4), (0, 2, 0))).sublines[0]
        assert sl.consumption is None

    def test_parameter_geometry_dot_fill_is_not_inferred_from_radius(self) -> None:
        # 同一三元组仅因 unit 改变而具有不同证据强度：UNIT_DOT 明确画点，
        # 其他 unit 的 filled 必须保持未知，不套用半径阈值或线型号。
        sl = self._style([0.5, 0.0, 0.05], ((2, 1, 0),)).sublines[0]
        assert sl.parameter_geometry() == [("dot", (0.5, 0.0, 0.05, None))]
        sl = self._style([0.5, 0.0, 0.05], ((3, 1, 0),)).sublines[0]
        assert sl.parameter_geometry() == [("dot", (0.5, 0.0, 0.05, True))]

    def test_parameter_geometry_fill_comes_from_unit(self) -> None:
        pairs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)]
        values = [v for point in pairs for v in point]
        sl = self._style(values, ((2, 4, 0),)).sublines[0]
        assert sl.parameter_geometry() == [("polyline", pairs)]
        sl = self._style(values, ((1, 4, 0),)).sublines[0]
        assert sl.parameter_geometry() == [("fill", pairs)]

    def test_parameter_geometry_preserves_unit_zero_coordinates(self) -> None:
        # unit=0 不能单独证明空移；两个坐标对仍按真实线段输出。
        sl = self._style([0.0, 0.0, 1.0, 0.0], ((0, 2, 0),)).sublines[0]
        sl.length = 26  # n=1/24B 是实线笔结构，本例是非实线元素
        assert sl.parameter_geometry() == [("segment", (0.0, 0.0, 1.0, 0.0))]

    def test_payload_geometry_fill_by_shape_not_unit(self) -> None:
        """825|0 根因回归：unit=1/513 同构闭合多边形载荷均判填充。"""
        fill_pairs = [(0.0975, 0.0739), (0.0975, 0.0729), (0.0975, 0.0739),
                      (0.2462, -0.0748), (0.2439, -0.0748),
                      (0.0975, -0.0748), (0.0975, 0.0729), (0.0975, 0.0739)]
        f32 = [v for p in fill_pairs for v in p]
        f32 += [0.2462, -0.0748, 0.2439, -0.0748, 0.2439, -0.0748,
                0.0975, -0.0748]   # 两段描边
        elems = ((1, 8, 0), (512, 2, 16), (512, 2, 20))
        sl = self._style(f32, elems).sublines[0]
        geo = sl.payload_geometry()
        assert geo[0][0] == "fill"          # unit=1 填充
        assert geo[1][0] == "segment"
        # 同构载荷换 unit=513 仍判填充
        elems2 = ((513, 8, 0), (512, 2, 16), (512, 2, 20))
        sl2 = self._style(f32, elems2).sublines[0]
        assert sl2.payload_geometry()[0][0] == "fill"

    def test_payload_geometry_dot_and_segment(self) -> None:
        # 16|0：三元组 → dot（filled=True——r=0.044 中间带 unit=258 引用）
        sl = self._style([0.5, 0.0, 0.044] * 4,
                         ((258, 2, 0), (258, 2, 3), (258, 2, 6), (259, 2, 9))).sublines[0]
        geo = sl.payload_geometry()
        assert all(k == "dot" for k, _ in geo)
        assert geo[0][1] == (0.5, 0.0, 0.044, True)
        sl = self._style([0.5, 0.1504, 0.04, 0.5, 0.1504, 0.04, 0.0, 0.0, 1.0, 0.0],
                         ((258, 2, 0), (259, 2, 3), (5, 2, 6))).sublines[0]
        geo = sl.payload_geometry()
        assert [k for k, _ in geo] == ["dot", "dot", "segment"]
        assert geo[2][1] == (0.0, 0.0, 1.0, 0.0)

    def test_payload_geometry_dot_fill_rule(self) -> None:
        """dot 填充控制逻辑（2026-10-21 用户裁定族）。

        r < 0.02 → 实心（574|0 小点锚）；r ≥ 0.075 → 空圈（379/574/565
        大点锚）；中间带 0.02–0.075 按 unit 裁定（unit=2 空、unit=3/
        引用 实——379|0 unit=2 r=0.05 空、16|0 unit=258 r=0.044 实）。
        """
        # r=0.01 小点 → 实心
        sl = self._style([0.5, 0.0, 0.01], ((3, 1, 0),)).sublines[0]
        assert sl.payload_geometry()[0][1][3] is True
        # r=0.10 大点 → 空圈
        sl = self._style([0.5, 0.0, 0.10], ((514, 1, 0),)).sublines[0]
        assert sl.payload_geometry()[0][1][3] is False
        # r=0.05 中间带：unit=2 → 空、unit=3 → 实
        sl = self._style([0.5, 0.0, 0.05], ((2, 1, 0),)).sublines[0]
        assert sl.payload_geometry()[0][1][3] is False
        sl = self._style([0.5, 0.0, 0.05], ((3, 1, 0),)).sublines[0]
        assert sl.payload_geometry()[0][1][3] is True

    def test_payload_geometry_solid_pen(self) -> None:
        sl = self._style([0.0, -0.0012, 0.635, -0.0012], (), solid=True).sublines[0]
        geo = sl.payload_geometry()
        assert geo == [("segment", (0.0, -0.0012, 0.635, -0.0012))]


def _slib_library_path(name: str, env_var: str) -> Path:
    from pymapgis.testing import slib_path

    configured = os.environ.get(env_var)
    if configured:
        path = Path(configured)
        if not path.is_file():
            raise FileNotFoundError(f"Required SLIB test library is unavailable: {path}")
        return path
    try:
        path = slib_path(name)
    except FileNotFoundError as exc:
        if os.environ.get("PYMAPGIS_SLIB"):
            raise
        pytest.skip(f"Optional user-supplied SLIB integration is unavailable: {exc}")
    if not path.is_file():
        raise FileNotFoundError(f"Required SLIB test library is unavailable: {path}")
    return path


class TestColorLib:
    """Colorlib.lib 色表：JWD 参考管线使用的 KCMY 原生映射。"""

    @staticmethod
    def _lib():
        from pymapgis.colorlib import ColorLib

        return ColorLib(str(_slib_library_path("Colorlib.lib", "PYMAPGIS_COLORLIB")))

    def test_reference_anchors(self) -> None:
        lib = self._lib()
        expected = {
            1: (0, 0, 0),
            9: (255, 255, 255),
            173: (255, 163, 163),
            175: (255, 0, 0),
            602: (206, 217, 206),  # Qp3pal 原生填充色
            652: (51, 204, 76),    # Qhfl 原生填充色
        }
        for no, rgb in expected.items():
            assert lib.rgb(no) == rgb, no
        assert lib.kcmy(175) == (0, 0, 255, 255)

    def test_out_of_range_none(self) -> None:
        lib = self._lib()
        assert lib.rgb(-1) is None
        assert lib.rgb(lib.max_no + 1) is None
        assert lib.rgb01(3) is not None


    def test_explicit_alternate_channel_model(self) -> None:
        lib = self._lib()
        alternate = type(lib)(_slib_library_path("Colorlib.lib", "PYMAPGIS_COLORLIB"),
                              channel_order="YMCK")
        expected = {
            1: (255, 255, 0),
            2: (255, 0, 255),
            3: (0, 255, 255),
            4: (0, 0, 0),
            194: (0, 255, 175),
            257: (255, 0, 0),
            271: (247, 247, 255),
        }
        for no, rgb in expected.items():
            assert alternate.rgb(no) == rgb, no


class TestPcolorLib:
    """Pcolor.lib 32-byte node layout and native colour anchors."""

    @staticmethod
    def _lib():
        from pymapgis.pcolor import PcolorLib
        return PcolorLib(str(_slib_library_path("Pcolor.lib", "PYMAPGIS_PCOLOR")))

    def test_native_node_layout_and_white(self) -> None:
        lib = self._lib()
        assert lib.count == 4098
        assert lib.max_no == 4097
        assert lib.trailing_bytes == 28
        expected = {
            1: (0, 0, 0),
            2: (0, 255, 255),
            9: (255, 255, 255),
            602: (255, 255, 178),
            652: (255, 255, 204),
            1051: (255, 255, 255),
            1092: (255, 255, 255),
            1167: (255, 255, 127),
            1168: (255, 255, 153),
        }
        for no, rgb in expected.items():
            assert lib.rgb(no) == rgb, no
            assert lib.assigned(no), no
        assert lib.kcmy(1051) == (0, 0, 0, 0)  # 全零 KCMY 是合法白色
        assert lib.rgb(lib.max_no + 1) is None

    def test_extended_dialog_anchors(self) -> None:
        lib = self._lib()
        expected = {
            881: (242, 255, 102), 882: (229, 255, 76),
            903: (242, 178, 76), 904: (242, 153, 51),
            914: (217, 255, 25), 923: (178, 255, 0),
            1045: (255, 255, 215), 1046: (255, 255, 215),
            1051: (255, 255, 255), 1096: (229, 229, 229),
            1224: (255, 76, 215), 1226: (255, 127, 229),
            1239: (242, 242, 242), 1465: (167, 222, 98),
        }
        for no, rgb in expected.items():
            assert lib.rgb(no) == rgb, no

    def test_explicit_alternate_channel_model(self) -> None:
        lib = self._lib()
        alternate = type(lib)(_slib_library_path("Pcolor.lib", "PYMAPGIS_PCOLOR"),
                              channel_order="YMCK")
        assert alternate.rgb(1) == (255, 255, 0)
        assert alternate.rgb(2) == (255, 0, 255)

    def test_synthetic_node_layout(self, tmp_path) -> None:
        from pymapgis.pcolor import PcolorLib
        data = bytearray(6 * 32 + 28)
        data[:8] = b"PCOLOR 3"
        for no, channels in {
            0: (0, 0, 0, 0),
            1: (255, 0, 0, 0),
            2: (0, 255, 0, 0),
        }.items():
            offset = (no + 3) * 32 + 28
            data[offset:offset + 4] = bytes(channels)
        path = tmp_path / "Pcolor.lib"
        path.write_bytes(data)
        lib = PcolorLib(str(path))
        assert (lib.count, lib.max_no, lib.trailing_bytes) == (3, 2, 28)
        assert lib.rgb(0) == (255, 255, 255)
        assert lib.rgb(1) == (0, 0, 0)
        assert lib.rgb(2) == (0, 255, 255)
        assert lib.assigned(0)
        assert lib.rgb(3) is None


class TestFeatureRhythm:
    """线型 3 节奏裁定读法（2026-10-19 用户逐行目视定案，3|x 六行）。

    定案规则：aux 选择主记录子线索引（aux 记录笔弃画）；
    节奏 f32 = (x, y) 坐标对序列（起点/线终点/点位置/点半径/结束）；
    点与线相间、点居中于两端线之间（等距）。
    """

    @staticmethod
    def _style(f32, n=2, elems=((0, 2, 0), (3, 3, 4)), aux=0, no=3):
        from pymapgis.linesty import Element, LineStyle, SubLine
        sl = SubLine(n=n, length=2 + 6 * n + 4 * len(f32),
                     elements=[Element(unit=u, marker=m, offset=o)
                               for u, m, o in elems],
                     f32_zone=list(f32), f32_start=2 + 6 * n)
        # 真实线型 3 记录有 6 条子线；feature_rhythm 按 aux 取 sub[aux]
        dummy = SubLine(n=1, length=24, elements=[Element(unit=0, marker=2, offset=0)],
                        f32_zone=[0.0, 0.0, 0.0, 0.0], f32_start=8)
        sublines = [dummy] * 6
        sublines[aux] = sl
        return LineStyle(no=no, n_subs=6, sublines=sublines)

    def test_16_dotline_lib_r(self) -> None:
        """16|0/16|1 纯圆点串：库内 r 直渲（2026-10-20 用户裁定）。

        载荷 = 三元组 (x,y,r) × 引用数（子图引用与 unit=3 同构消费律）；
        16|0 r=0.044 与 16|1 r=0.0781 是差别实体，M67 可变线宽替换
        规则本族限定适用域——render_ops 不得统一替换为图元线宽。"""
        from pymapgis.linesty import feature_rhythm, render_ops
        # 16|0：同坐标 4 引用；实库还含一个较小同心圆，实心并集仅保留最大圆
        st = self._style([0.5, 0.0, 0.044, 0.5, 0.0, 0.04,
                          0.5, 0.0, 0.044, 0.5, 0.0, 0.044], n=4,
                         elems=((258, 2, 0), (258, 2, 3), (258, 2, 6), (259, 2, 9)),
                         aux=0, no=16)
        r = feature_rhythm(st, 0)
        assert r["kind"] == "dotline_lib_r"
        assert len(r["dots"]) == 1
        assert r["dots"][0] == pytest.approx((0.5, 0.0, 0.044), abs=1e-4)
        ops = render_ops(st, 16, 0)
        # rhythm 单源：render_ops 输出 ("rhythm", 结构体)（2026-10-20 优化）
        assert ops["ops"][0][0] == "rhythm"
        assert ops["verdict_match"] is True
        assert ops["ops"][0][1]["dots"][0] == pytest.approx(
            (0.5, 0.0, 0.044), abs=1e-4)
        # 16|1：unit=3 三元组 r=0.0781（与 16|0 不同——差别实体）
        st = self._style([0.5, 0.0, 0.0781, 0.0, 0.0, 0.0], n=1,
                         elems=((3, 3, 0),), aux=1, no=16)
        r = feature_rhythm(st, 1)
        assert r["kind"] == "dotline_lib_r"
        assert len(r["dots"]) == 1
        assert r["dots"][0][2] == pytest.approx(0.0781, abs=1e-4)
        ops = render_ops(st, 16, 1)
        assert ops["ops"][0][0] == "rhythm"
        assert ops["ops"][0][1]["dots"][0][2] == pytest.approx(0.0781, abs=1e-4)

    def test_223_0_double_circle_tooth(self) -> None:
        """223|0：双正圆+矩形齿+双基线（2026-10-20 用户图面确认）。

        unit=1 闭合多边形经 Kåsa 拟合判别正圆（rms≤0.002）；unit≥5
        展平链成对 y 相等 → 水平线，否则 → 描边段（连续精确重复去重）。"""
        from pymapgis.linesty import feature_rhythm
        f32 = [0.3012, 0.0257, 0.2988, 0.0329, 0.2927, 0.0373, 0.2851, 0.0373,
               0.279, 0.0329, 0.2767, 0.0257, 0.279, 0.0185, 0.2851, 0.014,
               0.2927, 0.014, 0.2988, 0.0185, 0.3012, 0.0257,
               0.2093, -0.0245, 0.2067, -0.0166, 0.2, -0.0117, 0.1917, -0.0117,
               0.1849, -0.0166, 0.1824, -0.0245, 0.1849, -0.0324, 0.1917, -0.0373,
               0.2, -0.0373, 0.2067, -0.0324, 0.2093, -0.0245,
               0.7477, -0.0478, 0.8453, -0.0473, 0.8453, 0.0523, 0.7483, 0.0523,
               0.7481, 0.0523, 0.7481, -0.0476, 0.7477, -0.0478,
               0.1518, 0.0024, 0.344, 0.0024,
               0.2767, 0.0257, 0.279, 0.0185, 0.279, 0.0185, 0.2851, 0.014,
               0.2851, 0.014, 0.2927, 0.014, 0.2927, 0.014, 0.2988, 0.0185,
               0.2988, 0.0185, 0.3012, 0.0257, 0.2, -0.0117, 0.1917, -0.0117,
               0.7483, 0.0523, 0.7481, 0.0523, 0.7481, 0.0523, 0.7481, -0.0476,
               0.7481, -0.0476, 0.7477, -0.0478, 0.8453, 0.0523, 0.8453, -0.0473,
               0.8453, -0.0473, 0.8456, -0.0481, 0.8456, -0.0481, 0.7477, -0.0478,
               0.7477, -0.0478, 0.7477, -0.0478, 0.7477, -0.0478, 0.6482, -0.0478,
               0.6482, -0.0478, 0.6486, -0.0473, 0.6486, -0.0473, 0.6486, 0.0523,
               0.6486, 0.0523, 0.6486, 0.0523, 0.6486, 0.0523, 0.7483, 0.0523,
               0.7483, 0.0523, 0.7483, 0.0523, 0.7483, 0.0523, 0.8453, 0.0523,
               0.0, 0.25, 1.0, 0.25, 0.0, -0.25, 1.0, -0.25]
        elems = [(1, 11, 0), (1, 11, 22), (1, 7, 44), (768, 2, 58),
                 (2560, 2, 62), (2560, 2, 66), (2560, 2, 70), (2560, 2, 74),
                 (2560, 2, 78), (2560, 2, 82)] + [(768, 2, 86 + 4 * i)
                                                  for i in range(14)] + \
                [(5, 2, 142), (5, 2, 146)]
        st = self._style(f32, n=len(elems), elems=elems, aux=0, no=223)
        r = feature_rhythm(st, 0)
        assert r["kind"] == "double_circle_tooth"
        assert len(r["circles"]) == 2
        assert r["circles"][0] == pytest.approx((0.2889, 0.0257, 0.0122), abs=1e-3)
        assert r["circles"][1] == pytest.approx((0.1958, -0.0245, 0.0135), abs=1e-3)
        assert len(r["rects"]) == 1
        assert r["rects"][0][0] == pytest.approx((0.7477, -0.0478), abs=1e-3)
        assert len(r["lines"]) == 2     # 双基线（unit=5；768 基线段入 strokes）
        assert r["lines"][0] == pytest.approx((0.0, 1.0, 0.25), abs=1e-3)
        assert r["lines"][1] == pytest.approx((0.0, 1.0, -0.25), abs=1e-3)
        assert len(r["strokes"]) > 0
        assert r["period_mm"] == pytest.approx(1.0)
        # 未裁定 aux 诚实返回 None
        assert feature_rhythm(st, 1) is None

    def test_17_dash_dot_raised_payload_coords(self) -> None:
        """17|0/17|2：基线+载荷坐标圆点（2026-10-20 用户裁定）。

        (f0,f1)=圆点坐标、(f2)=半径——载荷三元组本体是库内真值；
        10-14 参数化模型分层为图元层缩放（linedot_params）。"""
        from pymapgis.linesty import feature_rhythm
        # 17|0：2 引用三元组（冗余）+ unit=5 基线
        f32 = [0.5, 0.1504, 0.04, 0.5, 0.1504, 0.04, 0.0, 0.0, 1.0, 0.0]
        st = self._style(f32, n=3, elems=((258, 2, 0), (259, 2, 3), (5, 2, 6)),
                         aux=0, no=17)
        r = feature_rhythm(st, 0)
        assert r["kind"] == "dash_dot_raised"
        assert r["dots"][0] == pytest.approx((0.5, 0.1504, 0.04), abs=1e-4)
        assert len(r["dots"]) == 1  # 同坐标冗余引用只画一次
        assert r["lines"][0] == pytest.approx((0.0, 1.0, 0.0), abs=1e-4)
        assert r["period_mm"] == pytest.approx(1.0)
        # 17|2：4 引用 r=0.012（小点变体）
        f32 = [0.5, 0.1504, 0.012] * 4 + [0.0, 0.0, 1.0, 0.0]
        st = self._style(f32, n=5,
                         elems=((258, 2, 0), (258, 2, 3), (258, 2, 6),
                                (259, 2, 9), (5, 2, 12)),
                         aux=2, no=17)
        r = feature_rhythm(st, 2)
        assert r["kind"] == "dash_dot_raised"
        assert len(r["dots"]) == 1  # 4 个同坐标引用合并为一个实心圆
        assert r["dots"][0][2] == pytest.approx(0.012, abs=1e-4)
        # 未裁定 aux 诚实 None
        assert feature_rhythm(st, 1) is None
        assert feature_rhythm(st, 3) is None

    def test_455_0_line_slash_dot(self) -> None:
        """455|0：基线+斜穿线+基线上圆点（2026-10-20 用户图面确认）。

        与 57|0 同模板族（(0,2),(0,2),(3,3)），参数各异。"""
        from pymapgis.linesty import feature_rhythm
        f32 = [0.0, 0.0, 0.6504, 0.0, 0.2715, 0.0762, 0.3516, -0.0781,
               0.8223, 0.0, 0.0547, 0.0, 0.0, 0.0]
        st = self._style(f32, n=3, elems=((0, 2, 0), (0, 2, 4), (3, 3, 8)),
                         aux=0, no=455)
        r = feature_rhythm(st, 0)
        assert r["kind"] == "line_slash_dot"
        assert r["lines"][0] == pytest.approx((0.0, 0.6504), abs=1e-4)
        assert r["slashes"][0] == pytest.approx(
            (0.2715, 0.0762, 0.3516, -0.0781), abs=1e-4)
        assert r["dots"][0] == pytest.approx((0.8223, 0.0, 0.0547), abs=1e-4)
        assert r["period_mm"] == pytest.approx(1.0)
        assert feature_rhythm(st, 1) is None

    def test_388_21_filled_rect_dot_bars(self) -> None:
        """388 家族：填充矩形+右端圆点+两端竖线（同形状双存储路径）。

        388|0 = unit=1/2/3 存储；21|2 = unit=32/33/35 引用存储——
        形状语义与 unit 号解耦的实证（payload_geometry 形状判据）。"""
        from pymapgis.linesty import feature_rhythm
        # 388|0：填充(12 f32)+点三元组×6(3 f32 直接型)+两端线对(4+4)
        # ——真实库消费区间 (0,12),(12,15),...,(27,30),(30,34),(34,38)
        f388 = ([0.0, 0.0508, 0.0, 0.0488, 0.0, -0.0508, 0.5996, -0.0508,
                 0.5996, 0.0508, 0.0, 0.0508]
                + [0.8008, 0.0, 0.0293] * 6
                + [0.0, 0.0996, 0.0, -0.0996, 0.5996, 0.0996, 0.5996, -0.0996])
        st388 = self._style(f388, n=9,
                            elems=((1, 6, 0), (2, 2, 12), (3, 2, 15),
                                   (2, 2, 18), (3, 2, 21), (2, 2, 24),
                                   (3, 2, 27), (0, 2, 30), (0, 2, 34)),
                            aux=0, no=388)
        r = feature_rhythm(st388, 0)
        assert r["kind"] == "filled_rect_dot_bars"
        assert len(r["rects"]) == 1
        assert r["rects"][0][0] == pytest.approx((0.0, 0.0508), abs=1e-4)
        assert len(r["dots"]) == 6
        assert r["dots"][0][:3] == pytest.approx((0.8008, 0.0, 0.0293), abs=1e-4)
        assert r["dots"][0][3] is False   # r=0.0293 中间带 unit=3 → 实
        assert len(r["bars"]) == 2
        assert r["bars"][0] == pytest.approx((0.0, -0.0996, 0.0996), abs=1e-4)
        # 21|2：unit=32/33/35 引用存储，同形
        f21 = ([0.0, 0.0996, 0.0, -0.0996, 0.5996, 0.0996, 0.5996, -0.0996]
               + [0.0, 0.0508, 0.0, 0.0488, 0.0, -0.0508, 0.5996, -0.0508,
                  0.5996, 0.0508, 0.0, 0.0508]
               + [0.8008, 0.0, 0.0293, 0.0, 0.0, 0.0])
        # 真实 21 记录有 10 子线；feature_rhythm 按 aux 取 sub[2]
        dummy = self._style([0.0]*4, n=1, elems=((0, 2, 0),), aux=0, no=21).sublines[0]
        from pymapgis.linesty import Element, LineStyle, SubLine
        sl2 = SubLine(n=4, length=2 + 24 + 4 * len(f21),
                      elements=[Element(unit=u, marker=m, offset=o)
                                for u, m, o in ((32, 2, 0), (32, 2, 4),
                                                (33, 6, 8), (35, 3, 20))],
                      f32_zone=list(f21), f32_start=2 + 24)
        sublines = [dummy] * 10
        sublines[2] = sl2
        st21 = LineStyle(no=21, n_subs=10, sublines=sublines)
        r = feature_rhythm(st21, 2)
        assert r["kind"] == "filled_rect_dot_bars"
        assert len(r["rects"]) == 1
        assert r["dots"][0][:3] == pytest.approx((0.8008, 0.0, 0.0293), abs=1e-4)
        assert r["dots"][0][3] is True    # r=0.0293 中间带 unit=35 引用 → 实
        # 未裁定 aux 诚实 None
        assert feature_rhythm(st388, 1) is None
        assert feature_rhythm(st21, 0) is None

    def test_38_2_tooth_dash(self) -> None:
        """38|2：基线+等腰三角齿（2026-10-20 用户图面确认，断层域）。

        sub2：基线 0→1.0（unit=5）+ 填充三角齿（unit=1：底
        0.4492–0.5508 贴基线、顶点 (0.5,0.1504)）——与 38|0/38|1 的
        tooth_dash 族同构；aux=子线索引。"""
        from pymapgis.linesty import feature_rhythm
        f32 = [0.0, 0.0, 1.0, 0.0,
               0.5, 0.1504, 0.4492, 0.0, 0.5508, 0.0, 0.5, 0.1504]
        st = self._style(f32, n=2, elems=((5, 2, 0), (1, 4, 4)),
                         aux=2, no=38)
        r = feature_rhythm(st, 2)
        assert r["kind"] == "tooth_dash"
        assert r["lines"][0] == pytest.approx((0.0, 1.0), abs=1e-4)
        assert len(r["teeth"]) == 1
        assert r["teeth"][0][0] == pytest.approx((0.5, 0.1504), abs=1e-4)
        assert r["teeth"][0][1] == pytest.approx((0.4492, 0.0), abs=1e-4)
        assert r["period_mm"] == pytest.approx(1.0)
        assert feature_rhythm(st, 3) is None

    def test_1x_solid_pen_provisional(self) -> None:
        """1|x 等价 1|0 单实线（2026-10-21 用户暂定策略）。

        线型 1 仅 1 条 24B 实线笔子线；aux 不参与渲染（MapGIS 库
        界面无 aux 变体实证）——1|0/1|7/1|256 全同判 solid_pen。"""
        from pymapgis.linesty import feature_rhythm
        f32 = [0.0, 0.0, 1.0, 0.0]
        for aux in (0, 1, 7, 256):
            st = self._style(f32, n=1, elems=((0, 2, 0),), aux=0, no=1)
            r = feature_rhythm(st, aux)
            assert r["kind"] == "solid_pen", aux
            assert r["lines"][0] == pytest.approx((0.0, 1.0), abs=1e-6)
            assert r["period_mm"] == pytest.approx(1.0)

    def test_2x_inline_dash_provisional(self) -> None:
        """2|x 等价 2|0 纯虚线（2026-10-21 用户暂定策略，2|9 裁定）。

        线型 2 库变体仅 2|0–2|4；越界 aux（2|9/2|18）为数据字段对，
        aux 不渲染——2|0/2|9/2|18 全同判 inline_dash（实0.3496/
        空0.3008，沿线节奏推导）。"""
        from pymapgis.linesty import Element, LineStyle, SubLine, feature_rhythm
        pen = SubLine(n=1, length=24,
                      elements=[Element(unit=0, marker=2, offset=0)],
                      f32_zone=[0.0, 0.0, 0.625, 0.0], f32_start=8)
        pen.width = 0.625
        sl = SubLine(n=2, length=2 + 12 + 4 * 8,
                     elements=[Element(unit=0, marker=2, offset=0),
                               Element(unit=0, marker=2, offset=4)],
                     f32_zone=[0.0, 0.0, 0.3496, 0.0, 0.6504, 0.0,
                               1.0, 0.0], f32_start=14)
        st = LineStyle(no=2, n_subs=2, sublines=[pen, sl])
        for aux in (0, 1, 4, 9, 18):
            r = feature_rhythm(st, aux)
            assert r["kind"] == "inline_dash", aux
            assert r["lines"][0] == pytest.approx((0.0, 0.3496), abs=1e-4)
            assert r["lines"][1] == pytest.approx((0.6504, 1.0), abs=1e-4)
            assert r["period_mm"] == pytest.approx(1.0)
        # 2|2/2|3 子线变体未裁定 → 诚实 None
        for aux in (2, 3):
            assert feature_rhythm(st, aux) is None, aux

    def test_575_0_long_dash(self) -> None:
        """575|0：长划 0→0.635 + 空白 0.365（2026-10-20 用户图面裁定）。

        24B 笔的 @16 f32 = 笔段终点 x1（载荷对本体），非笔宽——
        1|0 x1=1.0 满周期、575 x1=0.635 长划的双锚。"""
        from pymapgis.linesty import feature_rhythm
        f32 = [0.0, -0.0011692431, 0.6349577904, -0.0011692431]
        st = self._style(f32, n=1, elems=((0, 2, 0),), aux=0, no=575)
        r = feature_rhythm(st, 0)
        assert r["kind"] == "long_dash"
        assert r["lines"][0] == pytest.approx((0.0, 0.635), abs=1e-3)
        assert r["period_mm"] == pytest.approx(1.0)
        assert feature_rhythm(st, 1) is None

    def test_14_0_double_line_band(self) -> None:
        from pymapgis.linesty import feature_rhythm
        # 实库 14|0：双平行线 + 左 0→0.5469 填充带（用户 2026-10-19 裁定）
        f32 = [0.0, 0.0, 1.0, 0.0, 0.0, 0.0781, 1.0, 0.0781,
               0.0, 0.0, 0.5469, 0.0, 0.5469, 0.0781, 0.0, 0.0781, 0.0, 0.0]
        st = self._style(f32, n=3, elems=((5, 2, 0), (5, 2, 4), (1, 5, 8)),
                         aux=0, no=14)
        r = feature_rhythm(st, 0)
        assert r["kind"] == "double_line_band"
        assert r["lines"][0] == pytest.approx((0.0, 1.0, 0.0), abs=1e-4)
        assert r["lines"][1] == pytest.approx((0.0, 1.0, 0.0781), abs=1e-4)
        assert len(r["fills"]) == 1
        assert r["fills"][0][1] == pytest.approx((0.5469, 0.0), abs=1e-4)
        assert r["fills"][0][2] == pytest.approx((0.5469, 0.0781), abs=1e-4)
        assert r["period_mm"] == pytest.approx(1.0)
        # 未裁定 aux 诚实返回 None
        assert feature_rhythm(st, 1) is None

    def test_sub0_dash_dot(self) -> None:
        from pymapgis.linesty import feature_rhythm
        st = self._style([0, 0, 0.625, 0, 0.8203125, 0, 0.03125, 0, 0, 0])
        r = feature_rhythm(st, 0)
        assert r["kind"] == "dash_dot"
        assert r["lines"] == [(0.0, 0.625)]
        assert r["dots"] == [(0.8203125, 0.03125)]
        assert r["period_mm"] == pytest.approx(1.015625)

    def test_sub4_same_decode(self) -> None:
        from pymapgis.linesty import feature_rhythm
        # 记录内第二组 (0.65, 1.0) 为下一周期冗余复写
        st = self._style([0, 0, 0.35, 0, 0.5, 0, 0.008, 0, 0, 0,
                          0.65, 0, 1.0, 0],
                         n=3, elems=((0, 2, 0), (3, 3, 4), (0, 2, 10)), aux=4)
        r = feature_rhythm(st, 4)
        assert r["kind"] == "dash_dot"
        assert r["lines"] == [(0.0, 0.35)]
        assert r["period_mm"] == pytest.approx(0.65)

    def test_sub5_interleave(self) -> None:
        from pymapgis.linesty import feature_rhythm
        f32 = [
            0.005538, -0.004624, 0.0001, 0.005538, -0.004624, 0.0001,
            0.005538, -0.004624, 0.0001, 0.005538, -0.004624, 0.0001,
            0.35046, -0.007267, 0.0001, 0.35046, -0.007267, 0.0001,
            0.35046, -0.007267, 0.0001, 0.35046, -0.007267, 0.0001,
            0.694061, -0.007267, 0.0001, 0.694061, -0.007267, 0.0001,
            0.694061, -0.007267, 0.0001, 0.694061, -0.007267, 0.0001,
            0.069764, -0.005692, 0.279915, -0.004164, 0.763889, -0.006272,
            0.964053, -0.006128, 0.413688, -0.005692, 0.627549, -0.006128,
        ]
        st = self._style(f32, n=15, elems=[(2, 2, 0)] * 15, aux=5)
        r = feature_rhythm(st, 5)
        assert r["kind"] == "tick_dash_interleave"
        assert len(r["lines"]) == 3 and len(r["dots"]) == 3
        assert r["period_mm"] == 1.0
        # 三线起止（升序）——逐线锚定，防配对错位
        expected_lines = [(0.069764, 0.279915), (0.413688, 0.627549), (0.763889, 0.964053)]
        for actual, expected in zip(r["lines"], expected_lines):
            assert actual == pytest.approx(expected)
        # 三档竖短线 = (相邻线间隙中点, 刻度高 |y0|, 顶端)（2026-10-19
        # 用户裁定：档文件序 = 间隙序——档1(短,0.0046)→第1间隙、
        # 档2/档3(0.0073)→第2/3间隙；tick 与两侧 dash 等间距）
        # 注意：本环境 pytest.approx 对嵌套 list 的 abs 容差不生效，
        # 逐元组断言（元组级别 abs 正常）
        assert r["dots"][0] == pytest.approx(
            (0.34680144488811493, 0.0046241446, 0.0001), abs=1e-6)
        assert r["dots"][1] == pytest.approx(
            (0.6957188546657562, 0.0072672353, 0.0001), abs=1e-6)
        assert r["dots"][2] == pytest.approx(
            (1.0169082954525948, 0.0072672353, 0.0001), abs=1e-6)

    def test_4x_family(self) -> None:
        from pymapgis.linesty import feature_rhythm
        # 4|0
        f0 = [0, 0, 0.3008, 0, 0.4492, 0, 0.0081, 0, 0, 0,
              0.5508, 0, 0.0081, 0, 0, 0, 0.6992, 0, 1.0, 0]
        st = self._style(f0, n=4, elems=[(0, 2, 0), (3, 3, 4), (3, 3, 10), (0, 2, 16)], aux=0, no=4)
        r = feature_rhythm(st, 0)
        assert r["kind"] == "dash_double_dot"
        # 2026-10-21 用户复核定案：lines 含尾段线（f[16]→1.0）；
        # 点2 = (f[10], f[12]) = (0.5508, 0.0081)——f[16] 是线2 起点
        # 不是点2 坐标（前空 0.1403 = 后空 0.1403 对称即证）
        assert r["lines"] == [(0.0, 0.3008), (0.6992, 1.0)]
        assert r["dots"][0] == pytest.approx((0.4492, 0.0081), abs=1e-6)
        assert r["dots"][1] == pytest.approx((0.5508, 0.0081), abs=1e-6)
        assert r["period_mm"] == 1.0
        # 4|1
        f1 = [0, 0, 0.5, 0, 0.65, 0, 0.0469, 0, 0, 0, 0.85, 0, 0.0469, 0, 0, 0]
        st = self._style(f1, n=3, elems=[(32, 2, 0), (35, 3, 4), (35, 3, 10)], aux=1, no=4)
        r = feature_rhythm(st, 1)
        assert r["kind"] == "dash_double_dot"
        assert r["dots"][0] == pytest.approx((0.65, 0.0469), abs=1e-6)
        assert r["dots"][1] == pytest.approx((0.85, 0.0469), abs=1e-6)
        # 4|2
        f2 = [0, 0, 0.3008, 0, 0.7031, 0, 1.0, 0, 0.4492, 0,
              0.0117, 0, 0, 0, 0.5508, 0, 0.0124, 0, 0, 0]
        st = self._style(f2, n=4, elems=[(0, 2, 0), (0, 2, 4), (3, 3, 8), (3, 3, 14)], aux=2, no=4)
        r = feature_rhythm(st, 2)
        assert r["kind"] == "dash_double_dot"
        assert r["lines"][0] == pytest.approx((0.0, 0.3008), abs=1e-6)
        assert r["lines"][1] == pytest.approx((0.7031, 1.0), abs=1e-6)
        assert r["dots"][0] == pytest.approx((0.4492, 0.0117), abs=1e-6)
        assert r["dots"][1] == pytest.approx((0.5508, 0.0124), abs=1e-6)
        # 4|3：6 档 ×5 遍 + 尾段三线（逐值锚定）
        tiers = []
        for x, h in [(0.3512, 0.0041), (0.4094, 0.0048), (0.6913, 0.0041),
                     (0.7473, 0.0041), (0.0679, 0.0052), (0.0099, 0.0052)]:
            tiers += [x, -h, 0.001] * 5
        tail = [0.4623, -0.0036, 0.6368, -0.0032, 0.1203, -0.0045,
                0.3044, -0.0054, 0.8077, -0.0045, 0.9744, -0.0052]
        st = self._style(tiers + tail, n=33, elems=[(2, 2, 0)] * 33, aux=3, no=4)
        r = feature_rhythm(st, 3)
        assert r["kind"] == "tick_dash_interleave"
        assert r["lines"][0] == pytest.approx((0.1203, 0.3044), abs=1e-6)
        assert r["lines"][1] == pytest.approx((0.4623, 0.6368), abs=1e-6)
        assert r["lines"][2] == pytest.approx((0.8077, 0.9744), abs=1e-6)
        # 居中组：组1 @0.3542/0.4124（h 0.0041/0.0048）
        assert r["dots"][0] == pytest.approx((0.35425, 0.0041, 0.001), abs=1e-4)
        assert r["dots"][1] == pytest.approx((0.41245, 0.0048, 0.001), abs=1e-4)
        assert r["dots"][2] == pytest.approx((0.69425, 0.0041, 0.001), abs=1e-4)
        assert r["dots"][3] == pytest.approx((0.75025, 0.0041, 0.001), abs=1e-4)
        assert r["dots"][4] == pytest.approx((1.01835, 0.0052, 0.001), abs=1e-4)
        assert r["dots"][5] == pytest.approx((1.07635, 0.0052, 0.001), abs=1e-4)

    def test_unadjudicated_none(self) -> None:
        from pymapgis.linesty import feature_rhythm
        st = self._style([0, 0, 0.5, 0, 0.7, 0, 0.05, 0, 0, 0])
        st.no = 2
        assert feature_rhythm(st, 0) is None
        st.no = 3
        assert feature_rhythm(st, 9) is None
        assert feature_rhythm(None, 0) is None

    def test_5x_and_7x(self) -> None:
        from pymapgis.linesty import feature_rhythm
        # 5|0：档三元组 ×3 + 尾段两线
        f5 = [0.8858, 0.0065, 0.0001] * 3 + [
            0.0, 0.0065, 0.2901, 0.0065, 0.4243, 0.0065, 0.7399, 0.0065]
        st = self._style(f5, n=5, elems=[(2, 2, 0)] * 5, aux=0, no=5)
        r = feature_rhythm(st, 0)
        assert r["kind"] == "tick_dash_interleave"
        assert r["lines"][0] == pytest.approx((0.0, 0.2901), abs=1e-6)
        assert r["lines"][1] == pytest.approx((0.4243, 0.7399), abs=1e-6)
        assert r["dots"][0] == pytest.approx((0.8858, 0.0065, 0.0001), abs=1e-6)
        # 7|0：sub0 —— 基线 + 对称竖线对 @0
        f7a = [0, 0, 1.0, 0, 0.0, 0.125, 0.0, -0.125]
        st = self._style(f7a, n=2, elems=[(5, 2, 0), (0, 2, 4)], aux=0, no=7)
        r = feature_rhythm(st, 0)
        assert r["lines"] == [(0.0, 1.0)]
        assert r["dots"][0] == pytest.approx((0.0, 0.125, 0.125), abs=1e-6)
        # 7|1：sub1 —— 基线 + 对称竖线对 @0.5
        f7b = [0, 0, 1.0, 0, 0.5, 0.1992, 0.5, -0.1992]
        st = self._style(f7b, n=2, elems=[(5, 2, 0), (1280, 2, 4)], aux=1, no=7)
        r = feature_rhythm(st, 1)
        assert r["dots"][0] == pytest.approx((0.5, 0.1992, 0.1992), abs=1e-6)
        # 7|2：sub2 —— 两组对称竖线对 @0.1055/0.1992
        f7c = [0, 0, 1.0, 0, 0.1055, 0.0508, 0.1055, -0.0508,
               0.1992, 0.0508, 0.1992, -0.0508]
        st = self._style(f7c, n=3, elems=[(5, 2, 0), (0, 2, 4), (0, 2, 8)],
                         aux=2, no=7)
        r = feature_rhythm(st, 2)
        assert r["dots"][0] == pytest.approx((0.1055, 0.0508, 0.0508), abs=1e-6)
        assert r["dots"][1] == pytest.approx((0.1992, 0.0508, 0.0508), abs=1e-6)
        # 7|3 未裁定 → None
        assert feature_rhythm(st, 3) is None

    def test_38x_tooth_dash(self) -> None:
        from pymapgis.linesty import feature_rhythm
        # 38|0：单线 + 矩形齿（坐标列 unit=1）
        f0 = [0, 0, 0.6594, 0, 0.2188, 0, 0.2188, 0.1,
              0.4406, 0.1, 0.4406, 0, 0.2188, 0]
        st = self._style(f0, n=2, elems=[(0, 2, 0), (1, 5, 4)], aux=0, no=38)
        r = feature_rhythm(st, 0)
        assert r["kind"] == "tooth_dash"
        assert r["lines"] == [(0.0, 0.6594)]
        assert r["teeth"][0][0] == pytest.approx((0.2188, 0.0), abs=1e-6)
        assert r["teeth"][0][2] == pytest.approx((0.4406, 0.1), abs=1e-6)
        assert r["period_mm"] == pytest.approx(0.6594, abs=1e-6)
        # 38|1：两段线 + 矩形齿；单元等间距 = 线起点差 0.5
        f1 = [0, 0, 0.375, 0, 0.5, 0, 0.875, 0, 0.125, 0,
              0.125, 0.1, 0.25, 0.1, 0.25, 0, 0.125, 0]
        st = self._style(f1, n=3, elems=[(0, 2, 0), (0, 2, 4), (1, 5, 8)],
                         aux=1, no=38)
        r = feature_rhythm(st, 1)
        assert r["kind"] == "tooth_dash"
        assert r["lines"][0] == pytest.approx((0.0, 0.375), abs=1e-6)
        assert r["lines"][1] == pytest.approx((0.5, 0.875), abs=1e-6)
        assert r["period_mm"] == pytest.approx(0.5, abs=1e-6)
        # 38|2 已落码（2026-10-20 用户图面确认：基线+等腰三角齿）——
        # 本夹具在 aux=2 下同为 tooth_dash（同族同构）

    def test_51x_raised_dot(self) -> None:
        from pymapgis.linesty import feature_rhythm
        # 51|0：线 0→1.0 + 抬升圆点 @(0.5, 0.084) r=0.0371
        f = [0, 0, 1.0, 0, 0.5, 0.084, 0.0371, 0, 0, 0]
        st = self._style(f, n=2, elems=[(0, 2, 0), (3, 3, 4)], aux=0, no=51)
        r = feature_rhythm(st, 0)
        assert r["kind"] == "dash_dot_raised"
        assert r["lines"] == [(0.0, 1.0)]
        assert r["dots"][0] == pytest.approx((0.5, 0.084, 0.0371), abs=1e-6)
        assert r["period_mm"] == 1.0
        # 51|1 未裁定 → None
        assert feature_rhythm(st, 1) is None

    def test_48x_raised_lines(self) -> None:
        from pymapgis.linesty import feature_rhythm
        # 48|0：基线 + 两条抬升短线（(x,y) 点对 = 线端点）
        f = [0, 0, 1.0, 0, 0.1, 0.1, 0.4031, 0.1, 0.6, 0.1, 0.9, 0.1]
        st = self._style(f, n=3, elems=[(5, 2, 0), (0, 2, 4), (0, 2, 8)],
                         aux=0, no=48)
        r = feature_rhythm(st, 0)
        assert r["kind"] == "raised_lines"
        assert r["lines"][0] == pytest.approx((0.0, 1.0, 0.0), abs=1e-6)
        assert r["lines"][1] == pytest.approx((0.1, 0.4031, 0.1), abs=1e-6)
        assert r["lines"][2] == pytest.approx((0.6, 0.9, 0.1), abs=1e-6)
        # 48|1：sub1 —— 基线两段 + 双抬升短线
        f1 = [0, 0, 0.4, 0, 0.1, 0.1, 0.3, 0.1,
              0.7, 0.1, 0.9, 0.1, 0.6, 0, 1.0, 0]
        st = self._style(f1, n=4, elems=[(0, 2, 0)] * 4, aux=1, no=48)
        r = feature_rhythm(st, 1)
        assert r["lines"][0] == pytest.approx((0.0, 0.4, 0.0), abs=1e-6)
        assert r["lines"][1] == pytest.approx((0.1, 0.3, 0.1), abs=1e-6)
        assert r["lines"][2] == pytest.approx((0.7, 0.9, 0.1), abs=1e-6)
        assert r["lines"][3] == pytest.approx((0.6, 1.0, 0.0), abs=1e-6)

    def test_16x2_raised_dots(self) -> None:
        from pymapgis.linesty import feature_rhythm
        # 16|2：两段基线 + 双抬升圆点
        f = [0.2541, 0.1504, 0.02] * 2 + [0.7541, 0.1504, 0.02] * 2 + \
            [0.0041, 0, 0.3538, 0, 0.6545, 0, 1.0, 0]
        st = self._style(f, n=6, elems=[(2, 2, 0)] * 6, aux=2, no=16)
        r = feature_rhythm(st, 2)
        assert r["kind"] == "dash_dot_raised"
        assert r["lines"][0] == pytest.approx((0.0041, 0.3538), abs=1e-6)
        assert r["lines"][1] == pytest.approx((0.6545, 1.0), abs=1e-6)
        assert r["dots"][0] == pytest.approx((0.2541, 0.1504, 0.02), abs=1e-6)
        assert r["dots"][1] == pytest.approx((0.7541, 0.1504, 0.02), abs=1e-6)

    def test_18x0_up_tick(self) -> None:
        from pymapgis.linesty import feature_rhythm
        # 18|0：基线 + 周期起点竖线（向上 0.125）
        f = [0.0, 0.125, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        st = self._style(f, n=2, elems=[(0, 2, 0), (5, 2, 4)], aux=0, no=18)
        r = feature_rhythm(st, 0)
        assert r["kind"] == "tick_dash_interleave"
        assert r["lines"] == [(0.0, 1.0)]
        assert r["dots"][0] == pytest.approx((0.0, 0.0, 0.125), abs=1e-6)
        assert r["period_mm"] == 1.0

    def test_58x0_mixed(self) -> None:
        from pymapgis.linesty import feature_rhythm
        # 58|0：基线 + 三竖线 + 三圆点（基线下方）
        f = [0, 0, 1.0, 0, 0, 0, 0, 0.1875, 0.25, 0, 0.25, 0.1875,
             0.125, 0, 0.125, 0.1875,
             0.4375, -0.0625, 0.0312, 0, 0, 0,
             0.8125, -0.0625, 0.0312, 0, 0, 0,
             0.625, -0.0625, 0.0312, 0, 0, 0]
        st = self._style(f, n=7, elems=[(0, 2, 0), (0, 2, 4), (0, 2, 8),
                                        (0, 2, 12), (3, 3, 16), (3, 3, 22),
                                        (3, 3, 28)], aux=0, no=58)
        r = feature_rhythm(st, 0)
        assert r["kind"] == "mixed_dash"
        assert r["lines"] == [(0.0, 1.0, 0.0)]
        assert r["verticals"][0] == pytest.approx((0.0, 0.0, 0.1875), abs=1e-6)
        assert len(r["verticals"]) == 3
        assert r["dots"][0] == pytest.approx((0.4375, -0.0625, 0.0312), abs=1e-6)
        assert len(r["dots"]) == 3
        assert r["period_mm"] == 1.0

    def test_153x0_parallel_brackets(self) -> None:
        from pymapgis.linesty import feature_rhythm
        # 153|0：双平行线 + 两个下垂方括号（重复坐标冗余）
        f = ([0.0, 0.0] + [0.3988, 0.0] * 4 + [0.5371, 0.0] * 4 + [1.0, 0.0] +
             [0.0, 0.0994] + [0.3988, 0.0994] * 4 + [0.5371, 0.0994] * 4 +
             [1.0, 0.0994] +
             [0.144, -0.0022, 0.144, -0.067, 0.144, -0.067, 0.2649, -0.067,
              0.2649, -0.067, 0.2649, -0.0022,
              0.6753, -0.0022, 0.6753, -0.067, 0.6753, -0.067, 0.7963, -0.067,
              0.7963, -0.067, 0.7963, -0.0022])
        st = self._style(f, n=16, elems=[(1280, 2, 0)] * 16, aux=0, no=153)
        r = feature_rhythm(st, 0)
        assert r["kind"] == "mixed_dash"
        assert r["lines"][0] == pytest.approx((0.0, 1.0, 0.0), abs=1e-6)
        assert r["lines"][1] == pytest.approx((0.0, 1.0, 0.0994), abs=1e-6)
        assert r["lines"][2] == pytest.approx((0.144, 0.2649, -0.067), abs=1e-6)
        assert r["lines"][3] == pytest.approx((0.6753, 0.7963, -0.067), abs=1e-6)
        assert len(r["verticals"]) == 4
        assert r["verticals"][0] == pytest.approx((0.144, -0.067, -0.0022), abs=1e-6)

    def test_50x_two_raised_dots(self) -> None:
        from pymapgis.linesty import feature_rhythm
        # 50|0：线 0→1.0 + 双抬升圆点
        f = [0, 0, 1.0, 0, 0.5, 0.0684, 0.0312, 0, 0, 0,
             0.6992, 0.0684, 0.0312, 0, 0, 0]
        st = self._style(f, n=3, elems=[(0, 2, 0), (3, 3, 4), (3, 3, 10)],
                         aux=0, no=50)
        r = feature_rhythm(st, 0)
        assert r["kind"] == "dash_dot_raised"
        assert r["lines"] == [(0.0, 1.0)]
        assert r["dots"][0] == pytest.approx((0.5, 0.0684, 0.0312), abs=1e-6)
        assert r["dots"][1] == pytest.approx((0.6992, 0.0684, 0.0312), abs=1e-6)


# ---------------------------------------------------------------------------
# Writer helpers
# ---------------------------------------------------------------------------

import pandas as pd  # noqa: E402
import shapely.geometry  # noqa: E402

from pymapgis.reader import _FIELD_DESCRIPTOR_STRUCT  # noqa: E402
from pymapgis.writer import (  # noqa: E402
    WriterError,
    _assemble_file,
    _crs_header_fields,
    _degrees_to_raw_dms,
    _encode_gbk_field,
    _fields_from_dataframe,
    _is_missing,
    _pack_attribute_field,
    _pack_field_descriptor,
    _PolygonArcDecomposer,
)


class TestDegreesToRawDms:
    def test_typical_central_meridian(self) -> None:
        assert _degrees_to_raw_dms(73.0) == pytest.approx(730000.0)

    def test_with_minutes_seconds(self) -> None:
        assert _degrees_to_raw_dms(73.2583333333) == pytest.approx(731530.0, abs=1e-3)

    def test_negative(self) -> None:
        assert _degrees_to_raw_dms(-73.2583333333) == pytest.approx(-731530.0, abs=1e-3)

    def test_roundtrip_with_reader(self) -> None:
        for value in (0.0, 73.0, -73.2583333333, 39.5002777777, 1.0):
            assert _raw_dms_to_degrees(_degrees_to_raw_dms(value)) == pytest.approx(value)


class TestEncodeGbkField:
    def test_chinese_padded(self) -> None:
        buf = _encode_gbk_field("你好", 6)
        assert buf == "你好".encode("gbk") + b"\x00\x00"

    def test_truncation_never_splits_multibyte(self) -> None:
        # "中" is 2 bytes in GBK; a 3-byte budget must not keep half of it.
        buf = _encode_gbk_field("中文ab", 3)
        assert buf.decode("gbk").rstrip("\x00") == "中"

    def test_unencodable_replaced(self) -> None:
        buf = _encode_gbk_field("a€b", 3)
        assert buf == b"a?b"

    def test_exact_fit(self) -> None:
        assert _encode_gbk_field("abc", 3) == b"abc"


class TestIsMissing:
    def test_variants(self) -> None:
        assert _is_missing(None)
        assert _is_missing(pd.NA)
        assert _is_missing(pd.NaT)
        assert _is_missing(float("nan"))
        assert not _is_missing(0)
        assert not _is_missing("")


class TestPackAttributeField:
    def _spec(self, type_code, storage, declared=0, decimals=0):
        from pymapgis.writer import _FieldSpec

        return _FieldSpec("f", type_code, 1, storage, declared, decimals, "f")

    def test_string_roundtrip(self) -> None:
        spec = self._spec(0, 5, 4)
        buf = _pack_attribute_field("中文", spec)
        assert _decode_attribute_field(buf, _Field("f", 0, 0, 4, 0)) == "中文"

    def test_int_roundtrip(self) -> None:
        spec = self._spec(3, 4, 8)
        buf = _pack_attribute_field(42, spec)
        assert _decode_attribute_field(buf, _Field("f", 3, 0, 8, 0)) == 42

    def test_double_roundtrip_and_nan(self) -> None:
        spec = self._spec(5, 8, 15, 6)
        buf = _pack_attribute_field(3.14, spec)
        assert _decode_attribute_field(buf, _Field("f", 5, 0, 15, 6)) == pytest.approx(3.14)
        buf_nan = _pack_attribute_field(None, spec)
        assert np.isnan(_decode_attribute_field(buf_nan, _Field("f", 5, 0, 15, 6)))

    def test_missing_int_is_zero(self) -> None:
        spec = self._spec(3, 4, 8)
        assert _decode_attribute_field(
            _pack_attribute_field(pd.NA, spec), _Field("f", 3, 0, 8, 0)
        ) == 0

    def test_date_roundtrip(self) -> None:
        spec = self._spec(6, 4, 8)
        buf = _pack_attribute_field(datetime.date(2020, 1, 2), spec)
        assert _decode_attribute_field(buf, _Field("f", 6, 0, 8, 0)) == datetime.date(2020, 1, 2)

    def test_nat_date_is_zero_bytes(self) -> None:
        spec = self._spec(6, 4, 8)
        buf = _pack_attribute_field(pd.NaT, spec)
        assert buf == b"\x00" * 4
        assert _decode_attribute_field(buf, _Field("f", 6, 0, 8, 0)) is None

    def test_time_roundtrip(self) -> None:
        spec = self._spec(7, 10, 8)
        buf = _pack_attribute_field(datetime.time(3, 4, 5, 500000), spec)
        assert _decode_attribute_field(buf, _Field("f", 7, 0, 8, 0)) == datetime.time(
            3, 4, 5, 500000
        )


class TestFieldsFromDataFrame:
    def test_dtype_mapping(self) -> None:
        df = pd.DataFrame(
            {
                "b": pd.array([1, 2], dtype="int8"),
                "s": pd.array([1, 2], dtype="int16"),
                "i": pd.array([1, 2], dtype="int32"),
                "big": pd.array([2**40, 2**41], dtype="int64"),
                "f": pd.array([1.5, 2.5], dtype="float32"),
                "d": pd.array([1.5, 2.5], dtype="float64"),
                "txt": ["中文", "abc"],
                "dt": pd.to_datetime(["2020-01-01", "2021-02-03"]),
            }
        )
        with pytest.warns(UserWarning):
            specs = _fields_from_dataframe(df)
        codes = {s.source: s.type_code for s in specs}
        assert codes == {"b": 1, "s": 2, "i": 3, "big": 5, "f": 4, "d": 5, "txt": 0, "dt": 6}

    def test_string_capacity_uses_native_minimum_80(self) -> None:
        df = pd.DataFrame({"txt": ["中文", "abcd", None]})
        (spec,) = _fields_from_dataframe(df)
        assert spec.declared == 80
        assert spec.storage == 81

    def test_offsets_are_compact_after_flag_byte(self) -> None:
        df = pd.DataFrame({"a": pd.array([1], dtype="int32"), "b": pd.array([2], dtype="int16")})
        specs = _fields_from_dataframe(df)
        assert specs[0].offset == 1
        assert specs[1].offset == 5

    def test_unsupported_dtype_raises(self) -> None:
        df = pd.DataFrame({"bad": [[1, 2], [3]]})
        with pytest.raises(WriterError):
            _fields_from_dataframe(df)


class TestFieldDescriptorPacking:
    def test_reader_struct_recovers_fields(self) -> None:
        from pymapgis.writer import _FieldSpec

        spec = _FieldSpec("长度", 5, 9, 8, 15, 6, "长度")
        buf = _pack_field_descriptor(3, spec)
        assert len(buf) == 39
        name, type_code, offset, length, decimals = _FIELD_DESCRIPTOR_STRUCT.unpack(buf)
        assert _decode_gbk(name) == "长度"
        assert type_code == 5
        assert offset == 9
        assert length == 15
        # Writer stores the 0-based field index where the reader expects decimals.
        assert decimals == 3


class TestPolygonArcDecomposer:
    def test_shared_boundary_stored_once(self) -> None:
        p1 = shapely.geometry.box(0, 0, 1, 1)
        p2 = shapely.geometry.box(1, 0, 2, 1)
        arcs, topo = _PolygonArcDecomposer([p1, p2]).build()
        assert len(arcs) == 3  # 无向成链：两盒 = 共享边 + 两条开放环链
        pairs = sorted(topo)
        assert pairs == [(1, 0), (2, 0), (2, 1)]
        shared = [t for t in topo if t == (2, 1)]
        assert len(shared) == 1  # the common edge x=1 is a single arc

    def test_rebuild_with_reader_builder(self) -> None:
        p1 = shapely.geometry.box(0, 0, 1, 1)
        p2 = shapely.geometry.box(1, 0, 2, 1)
        arcs, topo = _PolygonArcDecomposer([p1, p2]).build()
        lines = [shapely.geometry.LineString(a) for a in arcs]
        table = np.array([[0, 0, left, right] for left, right in topo])
        builder = _PolygonTopologyBuilder(lines, table)
        g1, g2 = builder.build(1), builder.build(2)
        assert g1.area == pytest.approx(1.0)
        assert g2.area == pytest.approx(1.0)
        assert g1.union(g2).area == pytest.approx(2.0)

    def test_hole_rebuild_excludes_void(self) -> None:
        shell = [(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)]
        hole = [(2, 2), (3, 2), (3, 3), (2, 3), (2, 2)]
        poly = shapely.geometry.Polygon(shell, [hole])
        arcs, topo = _PolygonArcDecomposer([poly]).build()
        # No segment borders another polygon: every arc has one zero side.
        assert all(0 in pair for pair in topo)
        table = np.array([[0, 0, left, right] for left, right in topo])
        lines = [shapely.geometry.LineString(a) for a in arcs]
        rebuilt = _PolygonTopologyBuilder(lines, table).build(1)
        assert rebuilt.area == pytest.approx(15.0)
        assert len(rebuilt.geoms[0].interiors) == 1

    def test_island_in_hole_rebuild(self) -> None:
        shell = [(0, 0), (6, 0), (6, 6), (0, 6), (0, 0)]
        hole = [(1, 1), (5, 1), (5, 5), (1, 5), (1, 1)]
        outer = shapely.geometry.Polygon(shell, [hole])
        island = shapely.geometry.box(2, 2, 4, 4)
        arcs, topo = _PolygonArcDecomposer([outer, island]).build()
        table = np.array([[0, 0, left, right] for left, right in topo])
        lines = [shapely.geometry.LineString(a) for a in arcs]
        builder = _PolygonTopologyBuilder(lines, table)
        assert builder.build(1).area == pytest.approx(20.0)
        assert builder.build(2).area == pytest.approx(4.0)

    def test_closed_isolated_ring_rebuild(self) -> None:
        poly = shapely.geometry.box(0, 0, 1, 1)
        arcs, topo = _PolygonArcDecomposer([poly]).build()
        assert all(pair in ((1, 0), (0, 1)) for pair in topo)
        table = np.array([[0, 0, left, right] for left, right in topo])
        lines = [shapely.geometry.LineString(a) for a in arcs]
        rebuilt = _PolygonTopologyBuilder(lines, table).build(1)
        assert rebuilt.area == pytest.approx(1.0)
        # Topological (point-set) equality: the junction vertex where the two
        # arcs meet appears twice, matching the reader's native merge output.
        assert rebuilt.equals(poly)

    def test_snap_tolerance_merges_noisy_shared_edge(self) -> None:
        p1 = shapely.geometry.box(0, 0, 1, 1)
        # p2 shares x=1 but with a 1e-4 offset: needs snapping to share.
        p2 = shapely.geometry.Polygon(
            [(1 + 1e-4, 0), (2, 0), (2, 1), (1 + 1e-4, 1), (1 + 1e-4, 0)]
        )
        _, topo_exact = _PolygonArcDecomposer([p1, p2], snap_tolerance=0.0).build()
        assert (2, 1) not in topo_exact
        _, topo_snap = _PolygonArcDecomposer([p1, p2], snap_tolerance=0.01).build()
        assert (2, 1) in topo_snap


class TestAssembleFile:
    def test_index_layout(self) -> None:
        sections = {0: b"A" * 10, 2: b"B" * 20}
        data = _assemble_file("LINE", {109: ("B", 0)}, sections)
        # Header: magic + file id + data_start=657.
        assert data[:8] == b"WMAP`D21"
        assert struct.unpack_from("<i", data, 8)[0] == 0
        assert struct.unpack_from("<i", data, 12)[0] == 657
        # 16 index entries of 10 bytes, each ending with 0xFFFF.
        for i in range(16):
            entry = data[657 + i * 10 : 657 + (i + 1) * 10]
            assert entry[8:] == b"\xff\xff"
        # First section at 817, second section's entry records 827.
        start0, vol0 = struct.unpack_from("<2i", data, 657)
        start2, vol2 = struct.unpack_from("<2i", data, 657 + 20)
        assert (start0, vol0) == (817, 10)
        assert (start2, vol2) == (827, 20)
        # Unused entries are zeroed.
        start1, vol1 = struct.unpack_from("<2i", data, 657 + 10)
        assert (start1, vol1) == (0, 0)
        assert data[817:827] == b"A" * 10
        assert data[827:847] == b"B" * 20


class TestCrsHeaderFields:
    def test_none_crs(self) -> None:
        fields = _crs_header_fields(None, 1000.0)
        assert fields[109] == ("B", 0)
        assert fields[110] == ("B", 0)
        assert fields[143] == ("d", 0.0)

    def test_geographic_wgs84(self) -> None:
        fields = _crs_header_fields("EPSG:4326", 1000.0)
        assert fields[109] == ("B", 0)
        assert fields[110] == ("B", 7)
        assert fields[143] == ("d", 1.0)

    def test_unsupported_projection_raises(self) -> None:
        crs = "+proj=merc +datum=WGS84 +units=m +no_defs"
        with pytest.raises(WriterError):
            _crs_header_fields(crs, 1000.0)

    def test_tmerc_central_meridian(self) -> None:
        crs = (
            "+proj=tmerc +lat_0=0 +lon_0=75 +k=1 +x_0=500000 +y_0=0 "
            "+ellps=krass +units=m +no_defs"
        )
        fields = _crs_header_fields(crs, 250000.0)
        assert fields[109] == ("B", 5)
        assert fields[110] == ("B", 16)
        assert fields[143] == ("d", 250000.0)
        assert _raw_dms_to_degrees(fields[151][1]) == pytest.approx(75.0)
