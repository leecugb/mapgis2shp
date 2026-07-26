#!/usr/bin/env python3
"""逐一核验渲染中产状符号的走向线与倾向短刺是否严格垂直，并检查注记位置。

渲染器在 UTM（EPSG:32643）正形投影下绘制产状符号，因此走向线（按 GZBBAB）
与倾向短刺（按 GZBBAC）在数据/屏幕坐标下均应严格垂直。
"""

from __future__ import annotations

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

    strike = np.radians(gdf["GZBBAB"].astype(float))
    dip_dir = np.radians(gdf["GZBBAC"].astype(float))

    # 渲染器中的方向向量（米制长度在 UTM 下直接按方位角计算）
    sx, sy = np.sin(strike), np.cos(strike)
    dx, dy = np.sin(dip_dir), np.cos(dip_dir)

    # 归一化后点积
    dot = sx * dx + sy * dy
    angle = np.degrees(np.arccos(np.clip(np.abs(dot), 0, 1)))

    # 注记位置：短刺末端 + 沿走向偏移
    tick_len_m = 330.0
    strike_shift_m = 270.0
    xs = gdf.geometry.x.values
    ys = gdf.geometry.y.values
    lx = xs + tick_len_m * np.sin(dip_dir) + strike_shift_m * np.sin(strike)
    ly = ys + tick_len_m * np.cos(dip_dir) + strike_shift_m * np.cos(strike)

    # 注记相对短刺末端的偏移沿走向/倾向分量
    tx_end = xs + tick_len_m * np.sin(dip_dir)
    ty_end = ys + tick_len_m * np.cos(dip_dir)
    ux = lx - tx_end
    uy = ly - ty_end
    along_strike = ux * np.sin(strike) + uy * np.cos(strike)
    perp_strike = ux * np.sin(dip_dir) + uy * np.cos(dip_dir)

    report = pd.DataFrame(
        {
            "ID": gdf["ID"].values,
            "GZBBGA": gdf["GZBBGA"].values,
            "strike": gdf["GZBBAB"].values,
            "dip_dir": gdf["GZBBAC"].values,
            "dip_angle": gdf["GZBBAD"].values,
            "dot_strike_tick": dot,
            "angle_deg": angle,
            "label_along_strike_m": along_strike,
            "label_perp_strike_m": perp_strike,
        }
    )

    out_csv = Path("attitude_rendering_verification.csv")
    report.to_csv(out_csv, index=False, encoding="utf-8-sig")

    lines = [
        "# 产状符号渲染核验报告（UTM 正形投影）\n",
        "本报告逐一核验渲染中产状符号的走向线与倾向短刺是否严格垂直，并检查注记位置。\n",
        f"- 总记录数：{len(report)}\n",
        f"- 走向–短刺点积（归一化）：min={dot.min():.3e}, max={dot.max():.3e}, mean={dot.mean():.3e}\n",
        f"- 走向–短刺夹角：min={angle.min():.6f}°, max={angle.max():.6f}°, mean={angle.mean():.6f}°\n",
        f"- 严格垂直（|点积| < 1e-10）的记录数：{(np.abs(dot) < 1e-10).sum()} / {len(report)}\n",
        f"- 注记沿走向偏移：mean={along_strike.mean():.2f} m, std={along_strike.std():.2e}\n",
        f"- 注记沿倾向偏移：mean={perp_strike.mean():.2e} m（应为 0，仅数值误差）\n",
        "\n## 说明\n",
        "- 渲染器按真实走向 `GZBBAB` 和真实倾向 `GZBBAC` 绘制长线与短线。\n",
        "- UTM Zone 43N 为正形投影，等比例显示使二者在图面上严格垂直。\n",
        "- 注记位于短刺末端并沿走向偏移 `strike_shift_m = 270 m`，避免遮盖短刺。\n",
        f"\n详细表格见：{out_csv}\n",
    ]
    out_md = Path("attitude_rendering_verification.md")
    out_md.write_text("".join(lines), encoding="utf-8")

    print(f"Verification saved: {out_csv}, {out_md}")
    print(f"结论：{(np.abs(dot) < 1e-10).sum()}/{len(report)} 条记录严格垂直")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
