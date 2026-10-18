"""Round-trip tests for the MapGIS writer (GeoDataFrame -> .w? -> Reader)."""

from __future__ import annotations

import datetime
import struct

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely.geometry

from pymapgis import Reader, Writer, WriterError, write
from pymapgis.cli import main as cli_main
from pymapgis.reader import _read_polygon_arcs, _read_topology_table


def _write_and_read(gdf: gpd.GeoDataFrame, path, reader_kwargs=None, **kwargs) -> Reader:
    Writer(gdf, **kwargs).to_file(path)
    return Reader(path, **(reader_kwargs or {}))


def _sample_point_gdf() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "ID": pd.array([1, 2], dtype="int32"),
            "名称": ["吉根河", None],
            "DEPTH": pd.array([12.5, np.nan], dtype="float64"),
            "日期": pd.to_datetime(["2020-01-02", None]),
        },
        geometry=[shapely.geometry.Point(73.5, 39.5), shapely.geometry.Point(74.1, 39.9)],
        crs="EPSG:4326",
    )


class TestPointWriter:
    def test_roundtrip_attributes_and_coords(self, tmp_path) -> None:
        gdf = _sample_point_gdf()
        reader = _write_and_read(gdf, tmp_path / "out.wt")
        assert len(reader) == 2
        assert reader.shapeType == "POINT"
        xs = sorted(geom.x for geom in reader.geom)
        assert xs == pytest.approx([73.5, 74.1])
        data = reader.data
        assert data.iloc[0]["ID"] == 1
        assert data.iloc[0]["名称"] == "吉根河"
        assert data.iloc[1]["名称"] == ""
        assert np.isnan(data.iloc[1]["DEPTH"])
        assert data.iloc[0]["日期"] == datetime.date(2020, 1, 2)
        assert data.iloc[1]["日期"] is None

    def test_point_params_fidelity(self, tmp_path) -> None:
        gdf = gpd.GeoDataFrame(
            {
                "point_type": [1, 1],
                "symbol_no": [1281, 1894],
                "height": [2.0, 2.5],
                "width": [1.5, 2.0],
                "spacing": [np.nan, np.nan],
                "angle": [45.0, 90.0],
                "color": [6, 1],
                "layer": [4, 12],
                "pen_width": [0.05, 0.0],
            },
            geometry=[shapely.geometry.Point(0, 0), shapely.geometry.Point(1, 1)],
            crs="EPSG:4326",
        )
        reader = _write_and_read(gdf, tmp_path / "out.wt", {"read_point_params": True})
        params = reader.point_params
        assert params["symbol_no"].tolist() == [1281, 1894]
        assert params["height"].tolist() == pytest.approx([2.0, 2.5], abs=1e-4)
        assert params["angle"].tolist() == pytest.approx([45.0, 90.0], abs=1e-4)
        # wat 明码补齐字段（2026-10-15）往返保真。
        assert params["color"].tolist() == [6, 1]
        assert params["layer"].tolist() == [4, 12]
        assert params["pen_width"].tolist() == pytest.approx([0.05, 0.0], abs=1e-6)
        # Consumed param columns must not leak into the attribute table.
        assert "symbol_no" not in reader.data.columns

    def test_text_point_layout(self, tmp_path) -> None:
        gdf = gpd.GeoDataFrame(
            {
                "point_type": [0],
                "symbol_no": [0],
                "height": [3.0],
                "width": [2.0],
                "spacing": [0.5],
                "angle": [10.0],
                "color": [1],
                "layer": [2],
                "font_zh": [4],
                "font_en": [1],
                "font_style": [2],
            },
            geometry=[shapely.geometry.Point(0, 0)],
            crs="EPSG:4326",
        )
        reader = _write_and_read(gdf, tmp_path / "out.wt", {"read_point_params": True})
        params = reader.point_params.iloc[0]
        assert params["point_type"] == 0
        assert params["height"] == pytest.approx(3.0, abs=1e-4)
        assert params["width"] == pytest.approx(2.0, abs=1e-4)
        assert params["spacing"] == pytest.approx(0.5, abs=1e-4)
        assert params["color"] == 1
        assert params["layer"] == 2
        assert params["font_zh"] == 4
        assert params["font_en"] == 1
        assert params["font_style"] == 2

    def test_multipoint_explodes(self, tmp_path) -> None:
        gdf = gpd.GeoDataFrame(
            {"v": [1]},
            geometry=[shapely.geometry.MultiPoint([(0, 0), (1, 1)])],
            crs="EPSG:4326",
        )
        with pytest.warns(UserWarning):
            reader = _write_and_read(gdf, tmp_path / "out.wt")
        assert len(reader) == 2
        assert reader.data["v"].tolist() == [1, 1]


class TestLineWriter:
    def test_roundtrip(self, tmp_path) -> None:
        gdf = gpd.GeoDataFrame(
            {"名称": ["断层一"], "GZEEB": ["05"]},
            geometry=[shapely.geometry.LineString([(73.0, 39.0), (73.1, 39.1), (73.2, 39.05)])],
            crs="EPSG:4326",
        )
        reader = _write_and_read(gdf, tmp_path / "out.wl")
        assert len(reader) == 1
        assert reader.shapeType == "LINE"
        assert reader.data.iloc[0]["名称"] == "断层一"
        coords = list(reader.geom[0].coords)
        assert coords[0] == pytest.approx((73.0, 39.0))
        assert coords[2] == pytest.approx((73.2, 39.05))

    def test_line_params_fidelity(self, tmp_path) -> None:
        gdf = gpd.GeoDataFrame(
            {
                "linetype": [3],
                "aux_linetype": [2],
                "color": [5],
                "width": [0.35],
                "x_coef": [5.0],
                "y_coef": [4.0],
                "aux_color": [12],
                "layer": [5],
                "transparent": [1],
            },
            geometry=[shapely.geometry.LineString([(0, 0), (1, 1)])],
            crs="EPSG:4326",
        )
        reader = _write_and_read(gdf, tmp_path / "out.wl", {"read_graphic_params": True})
        params = reader.line_params.iloc[0]
        assert params["linetype"] == 3
        assert params["aux_linetype"] == 2
        assert params["color"] == 5
        assert params["width"] == pytest.approx(0.35, abs=1e-4)
        assert params["y_coef"] == pytest.approx(4.0, abs=1e-4)
        assert params["aux_color"] == 12
        assert params["layer"] == 5
        assert params["transparent"] == 1
        assert "linetype" not in reader.data.columns

    def test_line_params_partial_columns(self, tmp_path) -> None:
        """旧版 6 列 gdf（无 aux_flag 及明码补齐三列）不得整体静默丢弃。

        回归锚：列集扩充后旧 all-or-nothing 守卫会把整个 params 判为
        不齐 → 全部退回默认（linetype 变 1）；现以 linetype 为主键宽松
        吸收，缺失列填默认值，给出的列必须保住。
        """
        gdf = gpd.GeoDataFrame(
            {
                "linetype": [7],
                "color": [3],
                "width": [0.2],
                "x_coef": [2.0],
                "y_coef": [2.0],
            },
            geometry=[shapely.geometry.LineString([(0, 0), (1, 1)])],
            crs="EPSG:4326",
        )
        reader = _write_and_read(gdf, tmp_path / "out.wl", {"read_graphic_params": True})
        params = reader.line_params.iloc[0]
        assert params["linetype"] == 7
        assert params["color"] == 3
        assert params["width"] == pytest.approx(0.2, abs=1e-4)
        assert params["aux_linetype"] == 0
        assert params["aux_color"] == 0
        assert params["layer"] == 0
        assert params["transparent"] == 0

    def test_multilinestring_explodes(self, tmp_path) -> None:
        gdf = gpd.GeoDataFrame(
            {"v": [7]},
            geometry=[
                shapely.geometry.MultiLineString([[(0, 0), (1, 1)], [(2, 2), (3, 3)]])
            ],
            crs="EPSG:4326",
        )
        with pytest.warns(UserWarning):
            reader = _write_and_read(gdf, tmp_path / "out.wl")
        assert len(reader) == 2
        assert reader.data["v"].tolist() == [7, 7]


class TestPolygonWriter:
    def test_shared_boundary_roundtrip(self, tmp_path) -> None:
        p1 = shapely.geometry.box(0, 0, 1, 1)
        p2 = shapely.geometry.box(1, 0, 2, 1)
        gdf = gpd.GeoDataFrame(
            {"QDUECC": ["C1y", "C2ak"]}, geometry=[p1, p2], crs="EPSG:4326"
        )
        path = tmp_path / "out.wp"
        reader = _write_and_read(gdf, path)
        assert len(reader) == 2
        assert reader.shapeType == "POLYGON"
        assert reader.data["QDUECC"].tolist() == ["C1y", "C2ak"]
        total = sum(g.area for g in reader.geom)
        assert total == pytest.approx(2.0)
        assert reader.geom[0].union(reader.geom[1]).area == pytest.approx(2.0)

        # The shared edge must be stored as ONE arc with left/right = (2, 1)
        # （无向成链约定：存储方向上 right_id 内域在左 → (walkR, walkL)）。
        with open(path, "rb") as f:
            data_start = struct.unpack_from("<i", f.read(16), 12)[0]
            f.seek(data_start)
            entries = []
            for _ in range(10):
                entries.append(struct.unpack("<2i", f.read(10)[:8]))
        with open(path, "rb") as f:
            arcs = _read_polygon_arcs(
                f, *entries[0], *entries[1], 1.0
            )
            f.seek(0)
            topo = _read_topology_table(f, *entries[3])
        shared = [t for t in topo if t[2] == 2 and t[3] == 1]
        assert len(arcs) == 3
        assert len(shared) == 1

    def test_hole_and_island(self, tmp_path) -> None:
        outer = shapely.geometry.Polygon(
            [(0, 0), (6, 0), (6, 6), (0, 6), (0, 0)],
            [[(1, 1), (5, 1), (5, 5), (1, 5), (1, 1)]],
        )
        island = shapely.geometry.box(2, 2, 4, 4)
        gdf = gpd.GeoDataFrame(
            {"n": [1, 2]}, geometry=[outer, island], crs="EPSG:4326"
        )
        reader = _write_and_read(gdf, tmp_path / "out.wp")
        assert len(reader) == 2
        areas = sorted(g.area for g in reader.geom)
        assert areas == pytest.approx([4.0, 20.0])

    def test_multipolygon_stays_single_feature(self, tmp_path) -> None:
        mp = shapely.geometry.MultiPolygon(
            [shapely.geometry.box(0, 0, 1, 1), shapely.geometry.box(2, 2, 3, 3)]
        )
        gdf = gpd.GeoDataFrame({"n": [1]}, geometry=[mp], crs="EPSG:4326")
        reader = _write_and_read(gdf, tmp_path / "out.wp")
        assert len(reader) == 1
        assert reader.geom[0].area == pytest.approx(2.0)
        assert reader.geom[0].geom_type == "MultiPolygon"

    def test_invalid_polygon_repaired(self, tmp_path) -> None:
        bowtie = shapely.geometry.Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
        gdf = gpd.GeoDataFrame({"n": [1]}, geometry=[bowtie], crs="EPSG:4326")
        reader = _write_and_read(gdf, tmp_path / "out.wp")
        assert len(reader) == 1
        assert reader.geom[0].area == pytest.approx(2.0)

    def test_polygon_params_fidelity(self, tmp_path) -> None:
        # Native head_9 stores fill/pattern as single bytes at @5/@6 and the
        # pattern colour as uint16 LE at @9 (widened 2026-10-15 on official
        # .wap evidence; aoy sheet reaches 948).  Exercise the >255 path.
        gdf = gpd.GeoDataFrame(
            {"fill_color": [35], "pattern": [26], "pattern_color": [603]},
            geometry=[shapely.geometry.box(0, 0, 1, 1)],
            crs="EPSG:4326",
        )
        reader = _write_and_read(gdf, tmp_path / "out.wp", {"read_graphic_params": True})
        params = reader.polygon_params.iloc[0]
        assert params["fill_color"] == 35
        assert params["pattern"] == 26
        assert params["pattern_color"] == 603
        assert "fill_color" not in reader.data.columns

    def test_polygon_area_conservation_real(self, tmp_path, sample_wp) -> None:
        with Reader(sample_wp, read_graphic_params=True) as source:
            gdf = source.geodataframe
        path = tmp_path / "out.wp"
        with _write_and_read(gdf, path) as reader:
            assert len(reader) == len(gdf)
            assert sum(g.area for g in reader.geom) == pytest.approx(
                gdf.geometry.area.sum(), rel=1e-9
            )
            src_bounds = gdf.total_bounds
            assert np.allclose(reader.bbox, src_bounds, atol=1e-9)
            if len(reader.polygon_params):
                assert reader.polygon_params["pattern"].tolist() == (
                    gdf["pattern"].tolist()
                )


class TestHeaderExtentFields:
    """头部图幅范围与记录数字段（2026-10-17 原生 J43C001002 布局定案）。

    @260=记录数（点/线=要素数，面=弧段数）、@264=+1、@292=1、
    @304..328=存储坐标单位下的边界框。MapGIS 用边界框做复位窗口与
    符号缩放；全零框会让文件不可显示（原生验收实证）。
    """

    def _header(self, path) -> bytes:
        return path.read_bytes()[:400]

    def test_point_counts_and_bbox(self, tmp_path) -> None:
        gdf = gpd.GeoDataFrame(
            {"n": [1, 2]},
            geometry=[
                shapely.geometry.Point(74.0, 39.5),
                shapely.geometry.Point(74.2, 39.7),
            ],
            crs="EPSG:4326",
        )
        path = tmp_path / "t.wt"
        Writer(gdf).to_file(path)
        b = self._header(path)
        assert struct.unpack_from("<I", b, 260)[0] == 2
        assert struct.unpack_from("<I", b, 264)[0] == 3
        assert struct.unpack_from("<I", b, 292)[0] == 1
        box = struct.unpack_from("<4d", b, 304)
        assert box == pytest.approx((74.0, 39.5, 74.2, 39.7))

    def test_line_counts_and_bbox(self, tmp_path) -> None:
        gdf = gpd.GeoDataFrame(
            {"n": [1]},
            geometry=[shapely.geometry.LineString([(74.0, 39.5), (74.1, 39.6)])],
            crs="EPSG:4326",
        )
        path = tmp_path / "t.wl"
        Writer(gdf).to_file(path)
        b = self._header(path)
        assert struct.unpack_from("<I", b, 260)[0] == 1
        assert struct.unpack_from("<I", b, 264)[0] == 2
        box = struct.unpack_from("<4d", b, 304)
        assert box == pytest.approx((74.0, 39.5, 74.1, 39.6))

    def test_polygon_counts_arcs_and_bbox(self, tmp_path) -> None:
        p1 = shapely.geometry.box(0, 0, 1, 1)
        p2 = shapely.geometry.box(1, 0, 2, 1)
        gdf = gpd.GeoDataFrame(
            {"n": [1, 2]}, geometry=[p1, p2], crs="EPSG:4326"
        )
        path = tmp_path / "t.wp"
        Writer(gdf).to_file(path)
        b = self._header(path)
        # 两区共享一条边：3 条弧段（共享边 + 两条开放环链；2026-10-17
        # 无向成链定案，原生同构）
        assert struct.unpack_from("<I", b, 260)[0] == 3
        assert struct.unpack_from("<I", b, 264)[0] == 4
        box = struct.unpack_from("<4d", b, 304)
        assert box == pytest.approx((0.0, 0.0, 2.0, 1.0))

    def test_projected_bbox_in_stored_units(self, tmp_path) -> None:
        # 投影坐标：头部框须为存储单位（坐标 × 1000/map_scale）
        gdf = gpd.GeoDataFrame(
            {"n": [1]},
            geometry=[shapely.geometry.Point(500100.0, 4375000.0)],
            crs="+proj=tmerc +lat_0=0 +lon_0=75 +k=1 +x_0=500000 "
            "+y_0=0 +ellps=krass +units=m +no_defs",
        )
        path = tmp_path / "t.wt"
        Writer(gdf, map_scale=1000.0).to_file(path)
        b = self._header(path)
        box = struct.unpack_from("<4d", b, 304)
        # 存储值 = 米 × 1000/1000 = 米；框即点本身
        assert box == pytest.approx((500100.0, 4375000.0, 500100.0, 4375000.0))
        # 非退化框：若回归全零框，此断言失败
        assert any(box)


class TestHeaderCrsBlock:
    """坐标系区常量块与毫米-度系数（2026-10-17 原生 J43C001002 定案）。

    原生头部 @244/@252 存"每毫米对应度数"（经线/纬线方向），MapGIS
    用它把毫米级符号尺寸换算成度来显示；零系数会让符号尺寸归零。
    """

    def _write(self, tmp_path, map_scale=250000.0, crs="EPSG:4326") -> bytes:
        gdf = gpd.GeoDataFrame(
            {"n": [1]},
            geometry=[shapely.geometry.Point(74.0, 39.5)],
            crs=crs,
        )
        path = tmp_path / "t.wt"
        Writer(gdf, map_scale=map_scale).to_file(path)
        return path.read_bytes()[:400]

    def test_native_anchor_coefficients(self, tmp_path) -> None:
        # 1:250000、中心纬度 39.5 → 原生锚值 y≈0.0022517、x≈0.0029064
        b = self._write(tmp_path)
        x = struct.unpack_from("<d", b, 244)[0]
        y = struct.unpack_from("<d", b, 252)[0]
        assert y == pytest.approx(0.0022517, rel=1e-2)
        assert x == pytest.approx(0.0029064, rel=1e-2)
        assert x > y  # 纬线弧长 < 经线弧长

    def test_coefficients_scale_with_map_scale(self, tmp_path) -> None:
        y_250k = struct.unpack_from("<d", self._write(tmp_path, 250000.0), 252)[0]
        y_1000 = struct.unpack_from("<d", self._write(tmp_path, 1000.0), 252)[0]
        assert y_250k == pytest.approx(y_1000 * 250.0, rel=1e-9)

    def test_constant_block_written(self, tmp_path) -> None:
        b = self._write(tmp_path)
        assert struct.unpack_from("<f", b, 163)[0] == pytest.approx(11.0014, abs=1e-3)
        assert struct.unpack_from("<f", b, 171)[0] == pytest.approx(11.0967, abs=1e-3)
        assert struct.unpack_from("<f", b, 187)[0] == pytest.approx(8.9073, abs=1e-3)
        assert struct.unpack_from("<f", b, 195)[0] == pytest.approx(9.7929, abs=1e-3)
        assert struct.unpack_from("<f", b, 220)[0] == 0.0
        assert struct.unpack_from("<f", b, 220)[0] == -0.0
        assert struct.unpack_from("<d", b, 232)[0] == 1.0
        assert b[240] == 4 and b[242] == 1

    def test_projected_crs_leaves_coefficients_zero(self, tmp_path) -> None:
        b = self._write(
            tmp_path,
            crs="+proj=tmerc +lat_0=0 +lon_0=75 +k=1 +x_0=500000 "
            "+y_0=0 +ellps=krass +units=m +no_defs",
        )
        assert struct.unpack_from("<d", b, 244)[0] == 0.0
        assert struct.unpack_from("<d", b, 252)[0] == 0.0
        assert struct.unpack_from("<d", b, 232)[0] == 1.0


class TestLineAuxSections:
    """线辅助段原生布局（2026-10-17 J43C001002 定案）。

    head_5=55 字节零块；head_6=392 字节元数据块（FILETIME+常量 387+1）；
    head_7=(n+1)×32B 纯边界框记录（无 PRMH 标签、无前导零框）；
    head_8=4B 首值 + 每线 int32=0x00010000|图层；线记录头=01 02 常量。
    """

    def _sections(self, path) -> dict:
        b = path.read_bytes()
        ds = struct.unpack_from("<i", b, 12)[0]
        out = {}
        for i in range(10):
            s, v = struct.unpack_from("<2i", b, ds + i * 10)
            out[i] = b[s : s + v]
        return out

    def _write(self, tmp_path, layers=(0, 5)) -> None:
        gdf = gpd.GeoDataFrame(
            {
                "linetype": [1, 1],
                "layer": list(layers),
            },
            geometry=[
                shapely.geometry.LineString([(74.0, 39.5), (74.1, 39.6)]),
                shapely.geometry.LineString([(74.2, 39.7), (74.3, 39.8)]),
            ],
            crs="EPSG:4326",
        )
        path = tmp_path / "t.wl"
        Writer(gdf, map_scale=250000).to_file(path)
        return path

    def test_aux_section_layout(self, tmp_path) -> None:
        sec = self._sections(self._write(tmp_path))
        assert len(sec[4]) == 55 and not any(sec[4])
        assert len(sec[5]) == 392
        assert struct.unpack_from("<Q", sec[5], 0)[0] > 0  # FILETIME 非零
        assert struct.unpack_from("<I", sec[5], 12)[0] == 387
        assert struct.unpack_from("<I", sec[5], 16)[0] == 1
        # head_7: (2+1) x 32B，首记录 = 整体框，随后逐线框
        assert len(sec[6]) == 3 * 32
        assert struct.unpack_from("<4d", sec[6], 0) == pytest.approx(
            (74.0, 39.5, 74.3, 39.8)
        )
        assert struct.unpack_from("<4d", sec[6], 32) == pytest.approx(
            (74.0, 39.5, 74.1, 39.6)
        )
        # head_8: 4B 首值 + 每线标志 = 0x00010000 | 图层
        assert len(sec[7]) == 4 + 2 * 4
        assert struct.unpack_from("<i", sec[7], 4)[0] == 0x00010000
        assert struct.unpack_from("<i", sec[7], 8)[0] == 0x00010005

    def test_line_record_head_constant(self, tmp_path) -> None:
        sec = self._sections(self._write(tmp_path))
        for k in (1, 2):
            assert sec[0][k * 57 : k * 57 + 7] == b"\x01\x02\x00\x00\x00\x00\x00"


class TestPolygonAuxSections:
    """面辅助段原生布局（2026-10-17 J43C001002 定案）。

    head_3=元数据块（FILETIME+常量 426，645B）；head_5=55 字节零块；
    head_6=392B 元数据块（387/1）；head_7=(弧段数+1)×32B 边界框；
    head_8=4B 首值+每弧段 int32=0x00010000；弧段记录头=01 02 常量。
    """

    def _sections(self, path) -> dict:
        b = path.read_bytes()
        ds = struct.unpack_from("<i", b, 12)[0]
        out = {}
        for i in range(10):
            s, v = struct.unpack_from("<2i", b, ds + i * 10)
            out[i] = b[s : s + v]
        return out

    def _write(self, tmp_path):
        p1 = shapely.geometry.box(0, 0, 1, 1)
        p2 = shapely.geometry.box(1, 0, 2, 1)
        gdf = gpd.GeoDataFrame(
            {"n": [1, 2]}, geometry=[p1, p2], crs="EPSG:4326"
        )
        path = tmp_path / "t.wp"
        Writer(gdf, map_scale=250000).to_file(path)
        return path

    def test_aux_section_layout(self, tmp_path) -> None:
        sec = self._sections(self._write(tmp_path))
        # 两区共享边：3 条弧段、2 个端点结点（无向成链定案）
        assert len(sec[0]) == 4 * 57  # 弧段索引 (n+1)
        # head_2 前导 = [u16 0] + 每结点 (0, 结点号)；首弧坐标对紧随其后
        lead = struct.unpack("<5H", sec[1][:10])
        assert lead[0] == 0
        pairs = struct.unpack("<8H", sec[1][:16])
        assert pairs[1:5] == (0, 1, 0, 2)
        assert len(sec[3]) == 4 * 24  # 拓扑
        assert len(sec[2]) == 645 and struct.unpack_from("<Q", sec[2], 0)[0] > 0
        assert struct.unpack_from("<I", sec[2], 12)[0] == 426
        assert len(sec[4]) == 55 and not any(sec[4])
        assert len(sec[5]) == 392
        assert struct.unpack_from("<I", sec[5], 12)[0] == 387
        assert len(sec[6]) == 4 * 32  # 弧段框 (arcs+1)
        assert len(sec[7]) == 4 + 3 * 4  # 标志 (lead + arcs)
        assert struct.unpack_from("<i", sec[7], 4)[0] == 0x00010000  # MapGIS 规范弧图层 0
        # 弧段框 = 存储单位边界框（首记录零填充；共享边 x=1）
        assert not any(sec[6][:32])
        for k in range(1, 4):
            xmin, ymin, xmax, ymax = struct.unpack_from("<4d", sec[6], k * 32)
            assert xmin <= xmax and ymin <= ymax
            assert 0.0 <= xmin and xmax <= 2.0 and 0.0 <= ymin and ymax <= 1.0

    def test_arc_record_head_constant(self, tmp_path) -> None:
        sec = self._sections(self._write(tmp_path))
        assert sec[0][57 : 57 + 7] == b"\x01\x02\x00\x00\x00\x00\x00"


class TestCrsAndErrors:
    def test_tmerc_roundtrip(self, tmp_path) -> None:
        crs = (
            "+proj=tmerc +lat_0=0 +lon_0=75 +k=1 +x_0=500000 +y_0=0 "
            "+ellps=krass +units=m +no_defs"
        )
        gdf = gpd.GeoDataFrame(
            {"n": [1]},
            geometry=[shapely.geometry.Point(500100.0, 4375000.0)],
            crs=crs,
        )
        reader = _write_and_read(gdf, tmp_path / "out.wt", map_scale=1000.0)
        assert reader.geom[0].x == pytest.approx(500100.0, abs=1e-6)
        assert reader.geom[0].y == pytest.approx(4375000.0, abs=1e-6)

    def test_suffix_mismatch_message(self, tmp_path) -> None:
        gdf = _sample_point_gdf()
        with pytest.raises(WriterError, match="requires a .wt output file"):
            Writer(gdf).to_file(tmp_path / "out.wp")

    def test_mixed_geometry_raises(self) -> None:
        gdf = gpd.GeoDataFrame(
            {"n": [1, 2]},
            geometry=[
                shapely.geometry.Point(0, 0),
                shapely.geometry.LineString([(0, 0), (1, 1)]),
            ],
            crs="EPSG:4326",
        )
        with pytest.raises(WriterError, match="mixed geometry"):
            Writer(gdf)

    def test_empty_geodataframe_with_explicit_type(self, tmp_path) -> None:
        gdf = gpd.GeoDataFrame(
            {"ID": pd.array([], dtype="int32")},
            geometry=gpd.GeoSeries([], crs="EPSG:4326"),
        )
        reader = _write_and_read(gdf, tmp_path / "out.wt", geometry_type="POINT")
        assert len(reader) == 0

    def test_unsupported_projection(self, tmp_path) -> None:
        gdf = gpd.GeoDataFrame(
            {"n": [1]},
            geometry=[shapely.geometry.Point(0, 0)],
            crs="+proj=merc +datum=WGS84 +units=m +no_defs",
        )
        with pytest.raises(WriterError, match="unsupported projection"):
            Writer(gdf).to_file(tmp_path / "out.wt")

    def test_write_convenience_function(self, tmp_path) -> None:
        path = tmp_path / "out.wt"
        writer = write(_sample_point_gdf(), path)
        assert isinstance(writer, Writer)
        assert len(Reader(path)) == 2


class TestShpIntermediary:
    def test_mapgis_shp_mapgis(self, tmp_path, sample_wt) -> None:
        """mapgis -> shp -> mapgis must preserve count/bbox and point params."""
        with Reader(sample_wt, read_graphic_params=True) as source:
            gdf = source.geodataframe
        shp_path = tmp_path / "mid.shp"
        gdf.to_file(shp_path)
        back = gpd.read_file(shp_path)
        # Point param columns are all <= 10 chars, so shapefile keeps them.
        out = tmp_path / "out.wt"
        with _write_and_read(back, out, {"read_point_params": True}) as reader:
            assert len(reader) == len(gdf)
            assert np.allclose(reader.bbox, gdf.total_bounds, atol=1e-9)
            if len(reader.point_params):
                assert reader.point_params["symbol_no"].tolist() == (
                    gdf["symbol_no"].tolist()
                )

    def test_cli_shp_to_wp(self, tmp_path) -> None:
        gdf = gpd.GeoDataFrame(
            {"n": [1]}, geometry=[shapely.geometry.box(0, 0, 1, 1)], crs="EPSG:4326"
        )
        shp_path = tmp_path / "in.shp"
        gdf.to_file(shp_path)
        out = tmp_path / "out.wp"
        assert cli_main([str(shp_path), str(out)]) == 0
        with Reader(out) as reader:
            assert len(reader) == 1
            assert reader.geom[0].area == pytest.approx(1.0)

    def test_cli_mapgis_direction_unchanged(self, tmp_path, sample_wl) -> None:
        out = tmp_path / "out.geojson"
        assert cli_main([str(sample_wl), str(out)]) == 0
        assert out.exists()
