# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""MapGIS 6.x 填充图案库（Fillgrph.lib）解析器。

记录结构（2026-10-19 定案——220/243/247/252/253 五锚目视裁定 +
全库 1280/1337 结构校验通过（95.7%）；旧版"描述区不透明"挂账解除）：

  文件   = [u32 count][N×6B 索引（u32 记录偏移 + u16 flag）][记录区]
  记录   = [u16 grid][u16 unit][M×（10B 笔块 + 2B 对数）][坐标区]
  坐标区 = 各笔划 (x, y) 点对按笔划顺序拼接；重复点为冗余
           （笔划内 f32 位型相等的连续点=回描/落笔冗余，去重保留首现序；
           非相等点一律保留——0.003 容差曾摧毁密集曲线，F1 审计废止）

笔块 = (kind, 0, 0, width, 1)：
  kind=0  填充多边形（闭合、填充；width=0）
  kind=1  折线（width=65535 发丝线）
  kind=2  折线（width 笔宽档，1–7 实测）
  kind=3  弧（角度制）：载荷 (cx,cy), (r, a0), (a1, 0)
  kind=4/5/6  圆弧族：满载 (cx,cy), (r, 0), (0, 0)（a0=a1=0 整圆锚定，
          与子图弧哨兵同源）；4/6 与 5 的角色细分挂账——统一按圆渲染

渲染逻辑 = 逐笔划消费：0→闭合填充区；1/2→描边折线；3→弧；
4/5/6→圆。笔划分组由文件自身给出，**不需要逐图案人工裁定**。
亚可视微段（合并后总长 <0.01mm）剔除并以 "dropped" 计数。

挂账：
  - kind 4/5/6 的角色差异（4 疑与 6 成对出现=重复描画加深，5=独立点圆）
  - 57/1337 非常规记录（grid=1 旧式等）诚实返回 None
  - 220 线笔划端点 (0.3916,0.6082)≈点1 与目视裁定 3-15-14 的 0.05
    网格差——以文件存储为准（目视裁定为近似连接）
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_U16 = struct.Struct("<H")
_U32 = struct.Struct("<I")
_BLOCK = struct.Struct("<5H")
_PAIR = struct.Struct("<2f")

# 笔块 kind → 角色
KIND_FILL = 0          # 填充多边形
KIND_LINE_HAIR = 1     # 折线（发丝线）
KIND_LINE = 2          # 折线（笔宽）
KIND_ARC_DEG = 3       # 弧（角度制）
KIND_CIRCLE_FAMILY = (4, 5, 6)   # 圆弧族（满载整圆）


@dataclass
class FillStroke:
    """一条笔划：笔块 + 该笔划的坐标点对序列。"""
    kind: int                                   # 笔块首字段（见 KIND_*）
    width: int                                  # 笔宽档（65535=发丝线）
    points: List[Tuple[float, float]] = field(default_factory=list)


@dataclass
class FillPattern:
    """一条图案记录。"""
    no: int
    grid: int                                  # 网格尺寸
    unit: int                                  # 单位
    strokes: List[FillStroke] = field(default_factory=list)
    # 兼容字段：全记录坐标（去重后 / 原始）——由各笔划拼接而来
    points: List[Tuple[float, float]] = field(default_factory=list)
    raw_points: List[Tuple[float, float]] = field(default_factory=list)


class FillgrphLib:
    """Fillgrph.lib 解析器（索引区 + 记录结构 2026-10-19 定案）。"""

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
        """解码图案 no（1-based）。

        结构定位：描述区 = 12M 字节（M×[10B 笔块 + 2B 对数]），且
        坐标区长度 == sum(对数)×8。不满足结构的记录（旧式/异型）
        诚实返回 None，绝不臆断。
        """
        try:
            o, e = self.record_bounds(no)
        except IndexError:
            return None
        rec = self.data[o:e]
        if len(rec) < 16:
            return None
        grid, unit = struct.unpack_from("<HH", rec, 0)
        for zone in range(16, len(rec) - 7, 4):
            if (zone - 4) % 12:
                continue
            m = (zone - 4) // 12
            counts = [_U16.unpack_from(rec, 4 + m * 10 + i * 2)[0]
                      for i in range(m)]
            if sum(counts) * 8 != len(rec) - zone:
                continue
            strokes: List[FillStroke] = []
            raw: List[Tuple[float, float]] = []
            acc = 0
            for i in range(m):
                kind, _, _, width, _ = _BLOCK.unpack_from(rec, 4 + i * 10)
                pts = [_PAIR.unpack_from(rec, zone + (acc + j) * 8)
                       for j in range(counts[i])]
                strokes.append(FillStroke(kind=kind, width=width, points=pts))
                raw.extend(pts)
                acc += counts[i]
            # points = 全记录坐标精确去重（首现序；2026-10-19 F1 审计：
            # 旧 0.003 容差会摧毁密集曲线——367 图案实证，改逐位精确）
            pts: List[Tuple[float, float]] = []
            for p in raw:
                if p not in pts:
                    pts.append(p)
            return FillPattern(no=no, grid=grid, unit=unit,
                               strokes=strokes, points=pts, raw_points=raw)
        return None


def _merge_close(
        pts: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """合并笔划内**逐位精确重复**的连续点（存储冗余）。

    2026-10-19 审计定案（F1）：旧版 0.003 距离容差摧毁密集曲线——
    全库 33397 对真实连续点（367 图案）间距 <0.003，与落笔冗余对
    （1.6e-5–0.0014）分布重叠、无阈值可分（140 填充环被并没、
    71 号 56% 点损实证）。故只合并 f32 位型相等的连续点；
    亚可视微段（总长 <0.01mm，如 220 落笔对 1e-4 间距）由
    pattern_geometry 按可视性剔除并计数（"dropped"），不在此吞并。
    """
    out: List[Tuple[float, float]] = []
    for x, y in pts:
        if not out or (x != out[-1][0] or y != out[-1][1]):
            out.append((x, y))
    return out


def _close(a: Tuple[float, float], b: Tuple[float, float]) -> bool:
    """两点是否在 0.003 内（仅用于填充环首尾闭合判定，非冗余合并）。"""
    return abs(a[0] - b[0]) < 0.003 and abs(a[1] - b[1]) < 0.003


def _stroke_len(pts: List[Tuple[float, float]]) -> float:
    """笔划折线总长（mm）——可视性过滤用（亚可视微段 <0.01mm 剔除）。"""
    return sum(math.hypot(b[0] - a[0], b[1] - a[1])
               for a, b in zip(pts, pts[1:]))


def pattern_geometry(lib: FillgrphLib, no: int) -> Optional[dict]:
    """图案几何（结构解码，无需人工裁定）。

    返回 {"fill_polygons": [[(x,y),...]], "polylines": [[(x,y),...]],
    "circles": [(cx,cy,r),...], "arcs": [(cx,cy,r,a0,a1),...],
    "dropped": int}——dropped = 未进几何输出的笔划数（亚可视微段/
    退化笔划，如 220 的落笔单点对）；解析失败或结构不合时返回
    None（诚实停止，绝不臆断）。
    笔宽档见 pat.strokes[].width（发丝线=65535）。
    """
    pat = lib.decode(no)
    if pat is None:
        return None
    fill_polygons: List[List[Tuple[float, float]]] = []
    polylines: List[List[Tuple[float, float]]] = []
    circles: List[Tuple[float, float, float]] = []
    arcs: List[Tuple[float, float, float, float, float]] = []
    dropped = 0
    for s in pat.strokes:
        pts = _merge_close(s.points)
        if s.kind == KIND_FILL:
            if len(pts) > 2 and _close(pts[0], pts[-1]):
                pts = pts[:-1]
            if len(pts) > 2 and _stroke_len(pts) >= 0.01:
                fill_polygons.append(pts)
            else:
                dropped += 1
        elif s.kind in (KIND_LINE_HAIR, KIND_LINE):
            if len(pts) > 1 and _stroke_len(pts) >= 0.01:
                polylines.append(pts)
            else:
                dropped += 1
        elif s.kind in (KIND_ARC_DEG,) + KIND_CIRCLE_FAMILY and len(pts) == 3:
            cx, cy = pts[0]
            r, a0 = pts[1]
            a1 = pts[2][0]
            if abs(a0) < 1e-6 and abs(a1) < 1e-6:
                circles.append((cx, cy, r))
            else:
                arcs.append((cx, cy, r, a0, a1))
        else:
            # 非常规 kind/载荷 → 剔除并计数（不静默）
            dropped += 1
    return {
        "fill_polygons": fill_polygons,
        "polylines": polylines,
        "circles": circles,
        "arcs": arcs,
        "dropped": dropped,
    }
