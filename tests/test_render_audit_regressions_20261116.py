# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""2026-11-16 渲染审计修复回归。

  ① symbol_geometries() 的 bbox 按**实际可绘制几何**计算——判圆子路径取
     整圆范围 (cx±r, cy±r)，判弧子路径取 CCW 弧端点 + 弧上 0/90/180/270°
     极值点；圆/弧的原始编码控制点（[圆心, 半径参考点, 圆心回点] 或
     [圆心, (半径, 起角), (终角, 0)] 三点组）不再被当作坐标混入；
     多子路径取联合范围。
  ② write_geopdf() 仅支持 north-up geotransform：旋转/剪切项
     （geotransform[2]/[4]）非零、非有限值、退化（零）像素尺寸一律
     明确 ValueError；正常 north-up 路径不受影响。
  ③ ColorLib.kcmy() 恒返回 on-disk 通道顺序（文档修正的锚定测试）——
     channel_order="YMCK" 下盘上字节序为 (Y, M, C, K)，kcmy 仍按盘上
     原序返回，通道语义解释只在 rgb()/rgb01() 中发生。
"""
from __future__ import annotations

import math
import struct
import zlib

import pytest

from pymapgis.colorlib import ColorLib
from pymapgis.geopdf import inspect_geopdf, write_geopdf
from pymapgis.slib import SubgraphLib, symbol_geometries

pymupdf = pytest.importorskip("pymupdf")
pyproj = pytest.importorskip("pyproj")


# -- ① symbol_geometries bbox：可绘制几何，不用编码控制点 -------------------


def _mini_slib(tmp_path, records):
    """合成迷你 Subgraph.lib：索引表 = N×u32 记录偏移，记录头 =
    [type, n, 各子路径点数…]（点数表在头尾，decode 自尾向前识别）。"""
    blobs = []
    offset = 4 * len(records)
    offsets = []
    for t, subpaths in records:
        pts = [p for sp in subpaths for p in sp]
        counts = [len(sp) for sp in subpaths]
        header = struct.pack("<%dH" % (2 + len(counts)), t, 2 * len(pts), *counts)
        payload = b"".join(struct.pack("<2f", x, y) for x, y in pts)
        rec = header + payload
        offsets.append(offset)
        blobs.append(rec)
        offset += len(rec)
    data = struct.pack("<%dI" % len(offsets), *offsets) + b"".join(blobs)
    path = tmp_path / "Subgraph.lib"
    path.write_bytes(data)
    return SubgraphLib(str(path))


class TestSymbolGeometryBBox:
    """bbox 必须覆盖渲染实际画出的几何，且只覆盖它。"""

    def test_circle_uses_full_circle_extent_not_control_points(self, tmp_path):
        # type=6 中心参考圆编码：[圆心, 半径参考点, 圆心回点]
        lib = _mini_slib(tmp_path, [(6, [[(0.1, -0.1), (0.4, -0.1), (0.1, -0.1)]])])
        geo = symbol_geometries(lib, 0)
        assert geo["circles"] == [[0.1, -0.1, 0.3]]
        # 控制点 y 恒为 -0.1；渲染出的是整圆，bbox 须含 ±r 两个方向
        assert geo["bbox"] == [-0.2, -0.4, 0.4, 0.2]

    def test_arc_uses_ccw_endpoints_and_cardinal_extrema(self, tmp_path):
        # 三点参数弧编码：[圆心, (半径, 起角), (终角, 0)]——原始值含 120.0
        # 度的"伪坐标"，旧实现会把它计入 bbox（x 上限冲到 120）。
        lib = _mini_slib(tmp_path, [(2, [[(0.0, 0.0), (1.0, 30.0), (120.0, 0.0)]])])
        geo = symbol_geometries(lib, 0)
        assert geo["arcs"] == [[0.0, 0.0, 1.0, 30.0, 120.0]]
        # CCW 30°→120°：端点 (cos30,sin30)/(cos120,sin120)，极值点 90°→(0,1)
        assert geo["bbox"] == pytest.approx([-0.5, 0.5, 0.866, 1.0], abs=1e-4)
        assert geo["bbox"][2] < 2.0  # 编码值 120.0 不得泄漏进 bbox

    def test_arc_wrapping_past_zero_degrees(self, tmp_path):
        # CCW 270°→90°（右半圆，跨 0°）：x ∈ [0, r]，y ∈ [-r, r]；
        # 0° 极值点 (r, 0) 在张角内必须补上。
        lib = _mini_slib(tmp_path, [(2, [[(0.0, 0.0), (1.0, 270.0), (90.0, 0.0)]])])
        geo = symbol_geometries(lib, 0)
        assert geo["arcs"] == [[0.0, 0.0, 1.0, 270.0, 90.0]]
        assert geo["bbox"] == pytest.approx([0.0, -1.0, 1.0, 1.0], abs=1e-4)

    def test_mixed_subpaths_take_union_extent(self, tmp_path):
        # 圆 + 弧 + 普通折线组合：联合范围；普通子路径仍用其折线点。
        records = [(
            2,
            [
                [(1.0, 1.0), (1.25, 1.0), (1.0, 1.0)],          # 圆 r=0.25
                [(0.0, 0.0), (1.0, 270.0), (90.0, 0.0)],        # 弧 右半圆
                [(-2.0, 0.5), (0.5, -3.0)],                     # 普通折线
            ],
        )]
        lib = _mini_slib(tmp_path, records)
        geo = symbol_geometries(lib, 0)
        assert geo["circles"] == [[1.0, 1.0, 0.25]]
        assert geo["arcs"] == [[0.0, 0.0, 1.0, 270.0, 90.0]]
        # x: min(0.75, 0, -2)=-2 → max(1.25, 1, 0.5)=1.25
        # y: min(0.75, -1, -3)=-3 → max(1.25, 1, 0.5)=1.25
        assert geo["bbox"] == pytest.approx([-2.0, -3.0, 1.25, 1.25], abs=1e-4)

    def test_plain_polyline_bbox_unchanged(self, tmp_path):
        lib = _mini_slib(
            tmp_path, [(1, [[(0.1, 0.2), (-0.3, 0.4), (0.2, -0.5)]])]
        )
        geo = symbol_geometries(lib, 0)
        assert geo["circles"] == [] and geo["arcs"] == []
        assert geo["bbox"] == [-0.3, -0.5, 0.2, 0.4]

    def test_bbox_structure_keys_preserved(self, tmp_path):
        lib = _mini_slib(tmp_path, [(6, [[(0.0, 0.0), (0.3, 0.0), (0.0, 0.0)]])])
        geo = symbol_geometries(lib, 0)
        assert set(geo) == {"no", "type", "subpaths", "circles", "arcs",
                            "elements", "bbox"}
        assert set(geo["subpaths"][0]) == {"points", "closed", "circle",
                                           "arc", "template_digit"}


# -- ② write_geopdf 仅支持 north-up GT -------------------------------------


def _make_png(path, width=8, height=6):
    """用标准库写一张合法 RGB PNG（避免 matplotlib 画布依赖）。"""

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress((b"\x00" + b"\xff\xff\xff" * width) * height)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat)
        + chunk(b"IEND", b"")
    )
    return path


# 正常 north-up：原点左上、x 向东 0.5 m/px、y 向南 −0.5 m/px
NORTH_UP_GT = (400000.0, 0.5, 0.0, 4300300.0, 0.0, -0.5)


class TestWriteGeoPDFNorthUpOnly:
    def test_north_up_geotransform_still_succeeds(self, tmp_path):
        image = _make_png(tmp_path / "map.png")
        output = tmp_path / "map.pdf"
        written = write_geopdf(
            output, image, NORTH_UP_GT, pyproj.CRS.from_epsg(32643),
            dpi=100, scale_denominator=100,
        )
        assert written["encoding"] == "ISO32000"
        readback = inspect_geopdf(output)
        assert readback["gpts"] == pytest.approx(written["gpts"], abs=1e-5)
        assert all(math.isfinite(v) for v in readback["gpts"])
        # 8 px × 0.5 m/px = 4 m 地面宽；1:100 → 纸面 40 mm
        assert written["page_width_mm"] == pytest.approx(40.0)
        assert written["page_height_mm"] == pytest.approx(30.0)

    @pytest.mark.parametrize("index", (2, 4), ids=["rotation", "shear"])
    def test_rotation_shear_terms_rejected(self, tmp_path, index):
        image = _make_png(tmp_path / "map.png")
        gt = list(NORTH_UP_GT)
        gt[index] = 0.25
        with pytest.raises(ValueError, match="north-up"):
            write_geopdf(tmp_path / "rot.pdf", image, gt, pyproj.CRS.from_epsg(32643))

    @pytest.mark.parametrize(
        "bad", (float("nan"), float("inf"), -float("inf")),
        ids=["nan", "inf", "-inf"],
    )
    def test_non_finite_geotransform_rejected(self, tmp_path, bad):
        image = _make_png(tmp_path / "map.png")
        gt = list(NORTH_UP_GT)
        gt[1] = bad
        with pytest.raises(ValueError, match="finite"):
            write_geopdf(tmp_path / "inf.pdf", image, gt, pyproj.CRS.from_epsg(32643))

    @pytest.mark.parametrize("index", (1, 5), ids=["pixel_width", "pixel_height"])
    def test_degenerate_pixel_size_rejected(self, tmp_path, index):
        image = _make_png(tmp_path / "map.png")
        gt = list(NORTH_UP_GT)
        gt[index] = 0.0
        with pytest.raises(ValueError, match="non-zero"):
            write_geopdf(tmp_path / "deg.pdf", image, gt, pyproj.CRS.from_epsg(32643))


# -- ③ ColorLib.kcmy 恒返回 on-disk 通道顺序（文档锚定） --------------------


def test_kcmy_returns_on_disk_channel_order_under_both_models(tmp_path):
    header = b"C.U.G  Colorg" + b"\x03\x00\x00"          # 13B + 3B = 16
    data = header + bytes([10, 20, 30, 40]) + bytes([1, 2, 3, 4])
    path = tmp_path / "Colorlib.lib"
    path.write_bytes(data)

    for order in ("KCMY", "YMCK"):
        lib = ColorLib(str(path), channel_order=order)
        # 同一盘上字节，两种模型下 kcmy 返回值完全一致（不做通道重排）
        assert lib.kcmy(0) == (10, 20, 30, 40)
        assert lib.kcmy(1) == (1, 2, 3, 4)
        assert lib.kcmy(2) is None

    # 通道语义解释只发生在 rgb()：YMCK 把 (10,20,30,40) 读作 Y,M,C,K
    kcmy_rgb = ColorLib(str(path), channel_order="KCMY").rgb(0)
    ymck_rgb = ColorLib(str(path), channel_order="YMCK").rgb(0)
    assert kcmy_rgb != ymck_rgb
    k, c, m, y = 40, 30, 20, 10  # YMCK 盘上 (Y=10, M=20, C=30, K=40)
    factor = (255 - k) / 255.0
    assert ymck_rgb == (
        round((255 - c) * factor),
        round((255 - m) * factor),
        round((255 - y) * factor),
    )
