#!/usr/bin/env python3
"""核验 LDZOFBA016.WT 中产状走向与倾向是否垂直。"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from pymapgis import Reader


def main() -> int:
    path = Path("LDZOFBA016.WT")
    if not path.exists():
        print(f"[error] {path} not found")
        return 1

    with Reader(path) as r:
        gdf = r.geodataframe.copy()

    for col in ("GZBBAC", "GZBBAD", "GZBBAB"):
        gdf[col] = pd.to_numeric(gdf[col], errors="coerce")

    # 方法1：方位角差值
    diff = (gdf["GZBBAC"] - gdf["GZBBAB"]) % 360
    dev = pd.Series(np.minimum(np.abs(diff - 90), np.abs(diff - 270)))

    # 方法2：向量点积
    strike_rad = np.radians(gdf["GZBBAB"])
    dip_rad = np.radians(gdf["GZBBAC"])
    sx, sy = np.sin(strike_rad), np.cos(strike_rad)
    dx, dy = np.sin(dip_rad), np.cos(dip_rad)
    dot = sx * dx + sy * dy
    angle = np.degrees(np.arccos(np.clip(np.abs(dot), 0, 1)))

    print("=== 走向与倾向垂直性核验 ===")
    print(f"总记录数: {len(gdf)}")
    print(f"方位角差值法：偏差 < 1° 的比例 = {(dev < 1).sum()} / {len(gdf)} = {(dev < 1).mean()*100:.1f}%")
    print(f"向量点积法：平均夹角 = {angle.mean():.6f}°，std = {angle.std():.2e}")
    print(f"结论：{'全部垂直' if (dev < 1).all() else '存在不垂直记录'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
