# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""MapGIS 6.x 颜色库（Colorlib.lib）解析器。

格式（与 JWD 参考 12 层渲染管线一致）：

  文件 = ["C.U.G  Colorg" 头（13B）][\x03 等 3B][色表区 @16]
  色表 = 连续 4B 条目；色号 N 的条目 @ offset = 16 + N×4（0 基）
  条目 on-disk 字节 = (K, C, M, Y)，首字节为黑版 K。
  CMYK 反算：
      R = 255(1-C/255)(1-K/255)
      G = 255(1-M/255)(1-K/255)
      B = 255(1-Y/255)(1-K/255)

核验锚：1=黑、9=白、173=(255,163,163)、175=(255,0,0)。
默认 channel_order="KCMY"，与 JWD 参考库一致。其他安装环境可显式
指定 channel_order="YMCK"；解析器不根据少量候选锚自动切换模型。

WP 填充色还应结合 `PcolorLib` 的 32B 节点布局解析；不能将本文件的
连续 4B 索引模型套到 Pcolor.lib。
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Optional, Tuple

_TABLE_START = 16        # 色表区起点（"C.U.G  Colorg"13B + \x03 3B）
_ENTRY = 4               # 4B/条目 (K, C, M, Y)
_CHANNEL_ORDERS = {"KCMY", "YMCK"}


def _convert_cmyk(channels: Tuple[int, int, int, int], order: str) -> Tuple[int, int, int]:
    """Convert a four-channel record using an explicit installation model."""
    if order == "KCMY":
        k, c, m, y = channels
    elif order == "YMCK":
        y, m, c, k = channels
    else:
        raise ValueError(f"unsupported channel order: {order}")
    factor = (255 - k) / 255.0
    return (round((255 - c) * factor), round((255 - m) * factor),
            round((255 - y) * factor))


class ColorLib:
    """Colorlib.lib 解析器（色号 → RGB）。"""

    def __init__(self, path: str, *, channel_order: str = "KCMY"):
        if channel_order not in _CHANNEL_ORDERS:
            raise ValueError(f"unsupported channel order: {channel_order}")
        self.channel_order = channel_order
        self.data = Path(path).read_bytes()
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
        channels = self.kcmy(no)
        if channels is None:
            return None
        return _convert_cmyk(channels, self.channel_order)

    def rgb01(self, no: int) -> Optional[Tuple[float, float, float]]:
        """色号 → matplotlib 风格 (r, g, b) 0–1；越界返回 None。"""
        rgb = self.rgb(no)
        if rgb is None:
            return None
        return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
