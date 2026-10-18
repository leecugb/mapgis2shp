#!/usr/bin/env python3
"""Generate a persistent MapGIS write-test package for native MapGIS 6.7 check.

Output directory: D:/JWD/write_test_output/
Contents:
  1. 36 round-tripped real layers (Reader -> Writer -> Reader, graphic params on)
  2. demo_shared_edge.wp  - two adjacent polygons sharing one boundary arc
  3. demo_attrs.wt        - synthetic points: Chinese/date/time/float attributes
  4. demo_style.wl        - synthetic line with explicit style/colour/width params
  5. demo_fill.wp         - synthetic polygon with fill/pattern/pattern-colour params
  6. README_检查清单.md    - what to check in MapGIS 6.7, per file
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import datetime  # noqa: E402

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shapely.geometry  # noqa: E402

from pymapgis import Reader, Writer  # noqa: E402

OUT = Path(__file__).parent / "write_test_output"
OUT.mkdir(exist_ok=True)
SRC = Path(__file__).parent


def roundtrip_all() -> list[dict]:
    rows = []
    for path in sorted(list(SRC.glob("*.WT")) + list(SRC.glob("*.WL")) + list(SRC.glob("*.WP"))):
        with Reader(path, read_graphic_params=True) as source:
            gdf = source.geodataframe
            expected = (len(source), source.bbox)
        out = OUT / path.name
        Writer(gdf).to_file(out)
        with Reader(out) as reader:
            ok = len(reader) == expected[0] and np.allclose(reader.bbox, expected[1], atol=1e-9)
            area = None
            if reader.shapeType == "POLYGON":
                rel = abs(gdf.geometry.area.sum() - reader.geodataframe.geometry.area.sum()) / max(
                    gdf.geometry.area.sum(), 1e-30
                )
                area = f"{rel:.2e}"
                ok = ok and rel < 1e-9
        rows.append({"file": out.name, "type": path.suffix, "features": len(source),
                     "ok": ok, "area_rel_diff": area})
    return rows


def make_demos() -> None:
    # 1) shared-edge polygons
    gdf = gpd.GeoDataFrame(
        {"QDUECC": ["C1y", "C2ak"]},
        geometry=[shapely.geometry.box(0, 0, 1, 1), shapely.geometry.box(1, 0, 2, 1)],
        crs="EPSG:4326",
    )
    Writer(gdf, map_scale=250000).to_file(OUT / "demo_shared_edge.wp")

    # 2) point attributes: Chinese GBK, date, time, float.
    # Symbol points (point_type=1) with symbol 1281 (产状双短线, known-good in
    # the J43C001002 SLIB environment), 2 mm size, colour 6, so the points are
    # visible on the canvas after 复位窗口.  Without graphic params the writer's
    # default is a 1 mm symbol #1, which may be blank under another SLIB.
    gdf = gpd.GeoDataFrame(
        {
            "ID": pd.array([1, 2, 3], dtype="int32"),
            "名称": ["吉根河", "克孜勒苏", None],
            "深度": pd.array([12.5, 3.1415926, np.nan], dtype="float64"),
            "日期": pd.to_datetime(["2020-01-02", "2021-12-31", None]),
            "point_type": [1, 1, 1],
            "symbol_no": [1281, 1281, 1281],
            "height": [2.0, 2.0, 2.0],
            "width": [2.0, 2.0, 2.0],
            "angle": [0.0, 0.0, 0.0],
            "color": [6, 6, 6],
            "layer": [1, 1, 1],
            "pen_width": [0.05, 0.05, 0.05],
        },
        geometry=[
            shapely.geometry.Point(74.0, 39.5),
            shapely.geometry.Point(74.1, 39.6),
            shapely.geometry.Point(74.2, 39.7),
        ],
        crs="EPSG:4326",
    )
    Writer(gdf, map_scale=250000).to_file(OUT / "demo_attrs.wt")

    # 3) line style parameters
    gdf = gpd.GeoDataFrame(
        {
            "GZEEB": ["04", "05"],
            "linetype": [1, 2],        # 1=实线, 2=虚线
            "aux_linetype": [0, 0],
            "color": [1, 6],           # Colorlib 色号
            "width": [0.3, 0.6],       # mm
            "x_coef": [10.0, 10.0],
            "y_coef": [10.0, 10.0],
            "aux_color": [0, 0],
            "layer": [1, 1],
            "transparent": [0, 0],
        },
        geometry=[
            shapely.geometry.LineString([(74.0, 39.5), (74.5, 39.6), (74.8, 39.55)]),
            shapely.geometry.LineString([(74.0, 40.0), (74.4, 40.1), (74.9, 40.05)]),
        ],
        crs="EPSG:4326",
    )
    Writer(gdf, map_scale=250000).to_file(OUT / "demo_style.wl")

    # 4) polygon fill/pattern parameters
    gdf = gpd.GeoDataFrame(
        {
            "QDUECC": ["C1y", "C2ak"],
            "fill_color": [70, 35],      # Colorlib 填充色号
            "pattern": [26, 16],         # Fillgrph 图案号
            "pattern_color": [9, 603],   # 图案色（u16，603 覆盖 >255 路径）
        },
        geometry=[shapely.geometry.box(0, 0, 2, 2), shapely.geometry.box(2, 0, 4, 2)],
        crs="EPSG:4326",
    )
    Writer(gdf, map_scale=250000).to_file(OUT / "demo_fill.wp")


def main() -> int:
    rows = roundtrip_all()
    make_demos()
    failed = [r for r in rows if not r["ok"]]
    lines = [
        "# mapgis2shp 写文件测试包 —— MapGIS 6.7 原生验证清单",
        "",
        "目录：`D:\\JWD\\write_test_output\\`",
        "",
        "## 一、36 个真实图层往返件",
        "",
        "来源：J43C001002 库尔干幅，Reader(含图形参数) → Writer → 原文件名输出。",
        "建议任选 1 个点、1 个线、1 个面图层打开检查。",
        "",
        "| 文件 | 类型 | 要素数 | 往返自检 | 面积相对差 |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        status = "OK" if r["ok"] else "FAIL"
        area = r["area_rel_diff"] or "—"
        lines.append(f"| {r['file']} | {r['type']} | {r['features']} | {status} | {area} |")
    lines += [
        "",
        "## 二、合成演示件",
        "",
        "- `demo_shared_edge.wp`：两相邻区，共享边界应显示为一条无缝公共边；",
        "  两区填充颜色应可分别修改。",
        "- `demo_attrs.wt`：3 个点（子图符号 1281，2mm，色 6）。打开后先执行",
        "  「复位窗口」（菜单 窗口→复位窗口），否则画布可能停留在其他范围而看不到点。",
        "  右键文件→浏览属性，应有 3 条记录：中文属性（吉根河/克孜勒苏）、",
        "  日期（2020-01-02）、浮点深度（12.5）；空值不报错。",
        "- `demo_style.wl`：2 条线。检查线型（1=实线、2=虚线）、颜色、宽度(0.3/0.6mm)是否按参数显示。",
        "- `demo_fill.wp`：2 个区。检查填充颜色（色号 70/35）与图案是否显示；",
        "  图案色 603 用于覆盖 u16 高位字节路径。",
        "",
        "## 三、统一检查项",
        "",
        "1. 打开文件时无「文件损坏 / 数据错误」提示；",
        "2. 图形位置、形状与原文件一致（可对照 D:\\JWD 下同名源文件）；",
        "3. 属性表中文、日期、小数正常显示；",
        "4. 区文件：填充颜色/图案可修改并保存；",
        "5. 另存为副本后，`pymapgis.Reader` 能正常读回。",
        "",
        "## 四、说明",
        "",
        "- 已知写侧限制：.wt 不产出注记文本段；仅支持 longlat/tmerc/aea/lcc；",
        "  CGCS2000 按 WGS84 写入（含警告）。",
        "- 若某项检查失败，请记录文件、操作和报错信息，作为写路径缺陷案例。",
        "",
    ]
    (OUT / "README_检查清单.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"written {len(rows)} round-trip files + 4 demo files + checklist to {OUT}")
    if failed:
        print("FAILED:", failed)
        return 1
    print("all round-trip self-checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
