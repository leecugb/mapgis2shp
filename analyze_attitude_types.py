#!/usr/bin/env python3
"""梳理 LDZOFBA016.WT 中所有地层产状类型，生成统计报告。"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from pymapgis import Reader

ROOT = Path(__file__).parent
TARGET_CRS = "EPSG:32643"


def strike_diff(a: pd.Series, b: pd.Series) -> pd.Series:
    """计算 a 与 b 的锐角差（°），结果 0–90。"""
    diff = (a - b).abs() % 180
    return np.minimum(diff, 180 - diff)


def main() -> int:
    path = ROOT / "LDZOFBA016.WT"
    if not path.exists():
        print(f"[error] {path} not found")
        return 1

    with Reader(path) as r:
        gdf = r.geodataframe.copy()
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    gdf_utm = gdf.to_crs(TARGET_CRS)

    # 数值化
    for col in ("GZBBAB", "GZBBAC", "GZBBAD"):
        gdf[col] = pd.to_numeric(gdf[col], errors="coerce")
        gdf_utm[col] = gdf[col]

    # 计算走向–倾向正交差
    gdf["strike_dip_diff"] = strike_diff(gdf["GZBBAB"], gdf["GZBBAC"])

    # 类型代码推断含义（待图例确认）
    type_meanings = {
        "202001": ("地层产状", "层面产状，最常见"),
        "202005": ("变质岩产状", "片理 / 劈理 / 千枚理，走向线用双平行线"),
        "202004": ("线理 / 擦痕", "数量极少，可能为线理或擦痕产状"),
        "202011": ("节理 / 裂隙", "数量极少，可能为节理或裂隙产状"),
    }

    # 输出完整属性表
    out_csv = ROOT / "attitude_types.csv"
    out_cols = ["ID", "FEATUREID", "CHFCAC", "GZBBGA", "GZBBAB", "GZBBAC", "GZBBAD",
                "strike_dip_diff"]
    gdf[out_cols].to_csv(out_csv, index=False, encoding="utf-8-sig")

    # Markdown 报告
    lines = [
        "# 库尔干幅地层产状类型梳理报告\n",
        f"- 来源图层：`LDZOFBA016.WT`\n",
        f"- 总产状点数：{len(gdf)}\n",
        f"- 投影坐标系：{TARGET_CRS}（UTM Zone 43N）\n",
        "\n## 1. 字段含义\n",
        "| 字段 | 推断含义 | 单位 | 说明 |\n",
        "|------|----------|------|------|\n",
        "| `GZBBGA` | 产状类型代码 | - | 本报告梳理的核心字段 |\n",
        "| `GZBBAB` | 走向 | ° | 0–180，产状线方位 |\n",
        "| `GZBBAC` | 倾向 | ° | 0–359，与走向垂直 |\n",
        "| `GZBBAD` | 倾角 | ° | 0–90 |\n",
        "| `CHFCAC` | 顺序号 | - | 图内唯一序号 |\n",
        "\n## 2. 产状类型代码统计\n",
    ]

    type_counts = gdf["GZBBGA"].astype(str).value_counts().sort_index()
    lines.append("| 类型代码 | 数量 | 占比 | 推断含义 | 说明 |\n")
    lines.append("|----------|------|------|----------|------|\n")
    for code, count in type_counts.items():
        meaning, desc = type_meanings.get(code, ("未知", "待图例确认"))
        pct = count / len(gdf) * 100
        lines.append(f"| `{code}` | {count} | {pct:.1f}% | {meaning} | {desc} |\n")

    lines.append("\n## 3. 各类型产状几何统计\n")
    lines.append("| 类型代码 | 走向范围(°) | 倾向范围(°) | 倾角范围(°) | 平均倾角(°) | 走向–倾向差(°) |\n")
    lines.append("|----------|-------------|-------------|-------------|-------------|----------------|\n")
    for code, group in gdf.groupby("GZBBGA"):
        strike_min = group["GZBBAB"].min()
        strike_max = group["GZBBAB"].max()
        dip_dir_min = group["GZBBAC"].min()
        dip_dir_max = group["GZBBAC"].max()
        dip_min = group["GZBBAD"].min()
        dip_max = group["GZBBAD"].max()
        dip_mean = group["GZBBAD"].mean()
        diff_mean = group["strike_dip_diff"].mean()
        lines.append(
            f"| `{code}` | {strike_min:.0f}–{strike_max:.0f} | "
            f"{dip_dir_min:.0f}–{dip_dir_max:.0f} | "
            f"{dip_min:.0f}–{dip_max:.0f} | {dip_mean:.1f} | {diff_mean:.1f} |\n"
        )

    lines.append("\n## 4. 各类型典型记录\n")
    for code, group in gdf.groupby("GZBBGA"):
        meaning, _ = type_meanings.get(code, ("未知", ""))
        lines.append(f"\n### `{code}` — {meaning}\n")
        sample = group[["ID", "GZBBAB", "GZBBAC", "GZBBAD", "strike_dip_diff"]].head(10)
        lines.append("| ID | 走向(°) | 倾向(°) | 倾角(°) | 走向–倾向差(°) |\n")
        lines.append("|----|---------|---------|---------|----------------|\n")
        for _, row in sample.iterrows():
            lines.append(
                f"| {int(row['ID'])} | {row['GZBBAB']:.0f} | "
                f"{row['GZBBAC']:.0f} | {row['GZBBAD']:.0f} | {row['strike_dip_diff']:.1f} |\n"
            )

    # 整体倾角统计
    lines.append("\n## 5. 整体倾角统计\n")
    dips = gdf["GZBBAD"].dropna()
    lines.append(f"- 有倾角记录数：{len(dips)} / {len(gdf)}\n")
    lines.append(f"- 倾角范围：{dips.min():.0f}° – {dips.max():.0f}°\n")
    lines.append(f"- 平均倾角：{dips.mean():.1f}°\n")
    lines.append(f"- 中位数倾角：{dips.median():.1f}°\n")

    # 走向–倾向正交性
    lines.append("\n## 6. 走向与倾向正交性核验\n")
    diff = gdf["strike_dip_diff"].dropna()
    lines.append(f"- 走向与倾向夹角（锐角）范围：{diff.min():.1f}° – {diff.max():.1f}°\n")
    lines.append(f"- 平均夹角：{diff.mean():.2f}°\n")
    lines.append(f"- 夹角在 85°–95° 内的记录数：{((diff >= 85) & (diff <= 95)).sum()} / {len(diff)}\n")

    lines.append(f"\n## 7. 详细数据\n\n见 [`attitude_types.csv`](attitude_types.csv)。\n")

    out_md = ROOT / "attitude_types_report.md"
    out_md.write_text("".join(lines), encoding="utf-8")

    print(f"Saved: {out_md}")
    print(f"Saved: {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
