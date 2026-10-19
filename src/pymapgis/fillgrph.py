# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""MapGIS 6.x 填充图案库（Fillgrph.lib）解析器。

格式（与 LINESTY.lib 同构的索引；记录内部结构 2026-10-19 首锚定案，
图案 220 用户目视裁定）：

  文件 = [u32 count][N×6B 索引（u32 记录偏移 + u16 flag）][记录区]
  记录 = [u16 网格][u16 单位][描述区（内容不透明，挂账）][f32 坐标区]

坐标区 = (x, y) 点对；**重复点为冗余**（去重、保留首现序）；
笔划点序由用户目视裁定连接（首例图案 220：两条独立 N 形笔划，
各自末段为加粗右竖——见 ADJUDICATED_STROKES）。

挂账：描述区字段语义（[c,p1,p2,p3,anchor] 块疑与子图描述块同构，
x=4/3 疑为笔宽档）；其余图案未裁定，pattern_strokes 诚实返回 None。
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_U16 = struct.Struct("<H")
_U32 = struct.Struct("<I")


@dataclass
class FillPattern:
    """一条图案记录。"""
    no: int
    grid: int                                  # 网格尺寸（220 实证 8）
    unit: int                                  # 单位（220 实证 100）
    points: List[Tuple[float, float]] = field(default_factory=list)
    # 去重后坐标（首现序）——重复点是冗余（220 实证 ×2 遍）
    raw_points: List[Tuple[float, float]] = field(default_factory=list)


class FillgrphLib:
    """Fillgrph.lib 解析器（索引区 + 记录结构 2026-10-19 首锚）。"""

    def __init__(self, path: str):
        self.data = Path(path).read_bytes()
        self.count = _U32.unpack_from(self.data, 0)[0]
        self.entries: List[Tuple[int, int]] = [
            struct.unpack_from("<IH", self.data, 6 + i * 6)
            for i in range(self.count)
        ]

    def record_bounds(self, no: int) -> Tuple[int, int]:
        """no = 1-based 图案号；返回记录字节区间。"""
        i = no - 1
        if not (0 <= i < self.count):
            raise IndexError(f"pattern {no} out of range")
        off = self.entries[i][0]
        if off == 0:
            raise IndexError(f"pattern {no} is an empty slot")
        for k in range(i + 1, self.count):
            if self.entries[k][0] > off:
                return off, self.entries[k][0]
        return off, len(self.data)

    def decode(self, no: int) -> Optional[FillPattern]:
        """解码图案 no（1-based）；结构不可判时返回 None。"""
        try:
            o, e = self.record_bounds(no)
        except IndexError:
            return None
        rec = self.data[o:e]
        if len(rec) < 8:
            return None
        grid = _U16.unpack_from(rec, 0)[0]
        unit = _U16.unpack_from(rec, 2)[0]
        # 坐标区定位：首个 f32 落 [0.01, grid] 且 ≥80% 后续值亦落的
        # 4 字节对齐偏移（描述区小整数的 f32 为 ≈0，被首值门排除）
        zone = None
        for off in range(4, min(len(rec), 256), 4):
            n = (len(rec) - off) // 4
            if n < 4:
                break
            vals = struct.unpack_from(f"<{n}f", rec, off)
            if not (0.01 <= vals[0] <= float(grid or 8)):
                continue
            good = sum(1 for v in vals if 0.01 <= v <= float(grid or 8))
            if good * 5 >= n * 4:
                zone = off
                break
        if zone is None:
            return None
        n = (len(rec) - zone) // 4
        vals = struct.unpack_from(f"<{n}f", rec, zone)
        raw = list(zip(vals[0::2], vals[1::2]))
        pts: List[Tuple[float, float]] = []
        for x, y in raw:
            if not any(abs(x - ux) < 0.003 and abs(y - uy) < 0.003
                       for ux, uy in pts):
                pts.append((x, y))
        return FillPattern(no=no, grid=grid, unit=unit,
                           points=pts, raw_points=raw)


# 图案几何裁定表（2026-10-19 用户目视裁定首例，图案 220）。
# 点号 = decode() 去重后首现序索引；fill_polygons = 闭合填充区点序，
# polylines = 描边折线点序。220 定案：两组对称结构——N 轮廓区填充
# （0-1-2-3-4-5-6-0 与 7-8-9-10-11-12-13-7）+ 连接折线
# （3-15-14 与 10-17-16）。
ADJUDICATED_PATTERNS: Dict[int, dict] = {
    220: {
        "fill_polygons": [[0, 1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12, 13]],
        "polylines": [[3, 15, 14], [10, 17, 16]],
    },
    # 243/252（2026-10-19 用户目视裁定）：不填充，两组折线描边
    243: {
        "fill_polygons": [],
        "polylines": [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9]],
    },
    252: {
        "fill_polygons": [],
        "polylines": [[0, 1, 2, 3], [4, 5, 6, 7]],
    },
}


def pattern_geometry(lib: FillgrphLib, no: int) -> Optional[dict]:
    """图案几何（裁定解码）：返回 {"fill_polygons": [[(x,y),...]],
    "polylines": [[(x,y),...]]}——未裁定图案返回 None（诚实停止，
    绝不臆断）。"""
    spec = ADJUDICATED_PATTERNS.get(no)
    if spec is None:
        return None
    pat = lib.decode(no)
    if pat is None:
        return None
    return {
        "fill_polygons": [[pat.points[i] for i in ring]
                          for ring in spec["fill_polygons"]],
        "polylines": [[pat.points[i] for i in chain]
                      for chain in spec["polylines"]],
    }
