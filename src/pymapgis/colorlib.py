# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""MapGIS 6.x 颜色库（Colorlib.lib）解析器（2026-10-21 三锚定案 + 第四锚复核）。

格式（四锚全中：1 号=黑、9 号=白、175 号=纯红、173 号=淡桃红，
用户图面核验定案）：

  文件 = ["C.U.G  Colorg" 头（13B）][\x03 等 3B][色表区 @16]
  色表 = 连续 4B 条目；色号 N 的条目 @ offset = 16 + N×4（0 基）
  条目 on-disk 字节 = (K, C, M, Y)——K 在首字节（1 号 (255,0,0,0)
  即纯黑即证）；CMYK 反算：
      R = 255(1-C/255)(1-K/255)
      G = 255(1-M/255)(1-K/255)
      B = 255(1-Y/255)(1-K/255)

  破译教训：表首错位 1 字节（17 vs 16）+ 1 基槽位双错叠加仍"看似
  合理"（调色板前 16 色碰巧可读）——必须多锚交叉验证，单锚不可信。

挂账：Pcolor.lib（专用色板，131KB）结构未破；若发现 fill_color
越出 Colorlib 值域（0..~870）再启。
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Optional, Tuple

_TABLE_START = 16        # 色表区起点（"C.U.G  Colorg"13B + \x03 3B）
_ENTRY = 4               # 4B/条目 (K, C, M, Y)


class ColorLib:
    """Colorlib.lib 解析器（色号 → RGB）。"""

    def __init__(self, path: str):
        self.data = Path(path).read_bytes()
        # 魔数校验（2026-10-26 审计）：Colorlib.lib 头 13B = "C.U.G  Colorg"。
        # 旧实现无校验——Pcolor.lib 等异型文件会静默产出"看似合理"的
        # 垃圾色（docstring 破译教训：表首错位 1 字节仍看似合理）
        if not self.data.startswith(b"C.U.G  Colorg"):
            from pymapgis.reader import MapGISError
            raise MapGISError(
                f"{path}: not a Colorlib.lib (missing 'C.U.G  Colorg' header)"
            )
        # 可容纳的最大色号（0 基）
        self.max_no = (len(self.data) - _TABLE_START) // _ENTRY - 1

    def kcmy(self, no: int) -> Optional[Tuple[int, int, int, int]]:
        """色号 no（0 基）→ on-disk (K, C, M, Y)；越界返回 None。"""
        off = _TABLE_START + no * _ENTRY
        if no < 0 or off + _ENTRY > len(self.data):
            return None
        return struct.unpack_from("<4B", self.data, off)

    def rgb(self, no: int) -> Optional[Tuple[int, int, int]]:
        """色号 no（0 基）→ (R, G, B) 0–255；越界返回 None。"""
        kcmy = self.kcmy(no)
        if kcmy is None:
            return None
        k, c, m, y = kcmy
        fk = (255 - k) / 255.0
        return (round((255 - c) * fk), round((255 - m) * fk),
                round((255 - y) * fk))

    def rgb01(self, no: int) -> Optional[Tuple[float, float, float]]:
        """色号 → matplotlib 风格 (r, g, b) 0–1；越界返回 None。"""
        rgb = self.rgb(no)
        if rgb is None:
            return None
        return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
