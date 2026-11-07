# SPDX-License-Identifier: Apache-2.0
"""MapGIS Pcolor.lib 32-byte colour-node reader."""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Optional, Tuple

from pymapgis.colorlib import _CHANNEL_ORDERS, _convert_cmyk

_SIGNATURE = b"PCOLOR"
_NODE_SIZE = 32
_NODE_BIAS = 3
_CHANNELS_OFFSET = 28


class PcolorLib:
    """Read the verified Pcolor.lib node layout.

    Colour number ``N`` is stored in 32-byte node ``N + 3``; its four channel
    bytes are at node offset 28. The other node bytes are auxiliary data and
    are not needed for RGB conversion. Up to 31 trailing bytes, when present,
    are excluded from the colour count.

    An all-zero KCMY node is valid white, not an empty slot: native colour 1051
    is a confirmed white anchor. Out-of-range colour numbers alone return None.
    """

    def __init__(self, path: str, *, channel_order: str = "KCMY"):
        if channel_order not in _CHANNEL_ORDERS:
            raise ValueError(f"unsupported channel order: {channel_order}")
        self.channel_order = channel_order
        self.data = Path(path).read_bytes()
        if not self.data.startswith(_SIGNATURE):
            raise ValueError("Pcolor.lib lacks the PCOLOR signature")
        self.count = len(self.data) // _NODE_SIZE - _NODE_BIAS
        if self.count <= 0:
            raise ValueError("Pcolor.lib contains no complete colour nodes")
        self.max_no = self.count - 1
        self.trailing_bytes = len(self.data) % _NODE_SIZE

    def kcmy(self, no: int) -> Optional[Tuple[int, int, int, int]]:
        """Return the four stored channel bytes, or None when out of range."""
        if no < 0 or no > self.max_no:
            return None
        offset = (no + _NODE_BIAS) * _NODE_SIZE + _CHANNELS_OFFSET
        return struct.unpack_from("<4B", self.data, offset)

    def assigned(self, no: int) -> bool:
        """Return whether a complete colour node exists for *no*.

        Zero channels do not make a node unassigned; they encode white.
        """
        return self.kcmy(no) is not None

    def rgb(self, no: int) -> Optional[Tuple[int, int, int]]:
        """Decode a colour node; return None only for an invalid number."""
        channels = self.kcmy(no)
        if channels is None:
            return None
        return _convert_cmyk(channels, self.channel_order)

    def rgb01(self, no: int):
        """Return RGB in the 0–1 range, or None for an invalid number."""
        rgb = self.rgb(no)
        if rgb is None:
            return None
        return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)


__all__ = ["PcolorLib"]
