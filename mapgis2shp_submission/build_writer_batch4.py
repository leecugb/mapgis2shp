"""Build a domestic Gauss-Kruger SHP batch for native MapGIS Writer auditing."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import affinity
from shapely.geometry import (
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)

GK75 = "+proj=tmerc +lat_0=0 +lon_0=75 +k=1 +x_0=500000 +y_0=0 +ellps=krass +units=m +no_defs"
X0, Y0 = 500000.0, 4300000.0


def shift(geometry, dx=0.0, dy=0.0):
    return affinity.translate(geometry, xoff=X0 + dx, yoff=Y0 + dy)


def frame(geometries, attributes=None):
    count = len(geometries)
    data = {"ID": np.arange(1, count + 1, dtype=np.int64)}
    if attributes:
        data.update(attributes)
    return gpd.GeoDataFrame(data, geometry=geometries, crs=GK75)


def write_case(output, name, focus, gdf):
    case_dir = output / name
    case_dir.mkdir(parents=True, exist_ok=True)
    target = case_dir / f"{name}.shp"
    gdf.to_file(target, encoding="GBK", index=False)
    files = []
    for path in sorted(case_dir.iterdir()):
        if path.is_file():
            files.append(
                {
                    "file": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    return {
        "case": name,
        "focus": focus,
        "features": len(gdf),
        "geometry_types": gdf.geometry.geom_type.value_counts().to_dict(),
        "crs": GK75,
        "files": files,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("F:/writer_shp_batch4_20261108"))
    args = parser.parse_args()
    output = args.output_dir
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"Output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    cases = []

    basic = frame(
        [shift(Point(10, 10)), shift(Point(30, 20))],
        {"NAME": ["基本点一", "基本点二"], "VALUE": [1.25, 2.5]},
    )
    cases.append(write_case(output, "01_POINT_BASIC", "基本点、中文名称和浮点属性", basic))

    attributes = frame(
        [shift(Point(10, 10)), shift(Point(20, 20)), shift(Point(30, 30))],
        {
            "NAME": ["空值", "数值极值", "控制符"],
            "TEXT_NULL": [None, "", "→D↓2→t#-1"],
            "INT32": [-2147483648, 2147483647, 0],
            "FLOAT64": [np.nan, np.inf, -np.inf],
            "DATE_NULL": [None, None, None],
        },
    )
    cases.append(
        write_case(output, "02_POINT_ATTR_NULL", "空值、int32极值、非有限浮点和控制符", attributes)
    )

    multipoint = frame(
        [
            MultiPoint([shift(Point(10, 10)), shift(Point(20, 20))]),
            MultiPoint([shift(Point(30, 30))]),
        ]
    )
    cases.append(write_case(output, "03_POINT_MULTIPOINT", "MultiPoint与单点混合", multipoint))

    many = frame(
        [shift(Point((i % 16) * 10, (i // 16) * 10)) for i in range(257)],
        {"SEQ": np.arange(257), "NAME": [f"点{i:03d}" for i in range(257)]},
    )
    cases.append(write_case(output, "04_POINT_257", "超过255条记录的属性与坐标对齐", many))

    lines = frame(
        [
            shift(LineString([(0, 0), (100, 0), (100, 100)])),
            shift(LineString([(0, 100), (50, 150), (120, 170)])),
        ],
        {"NAME": ["折线一", "折线二"], "WIDTH": [0.1, 0.2]},
    )
    cases.append(write_case(output, "05_LINE_BASIC", "基本折线与中文属性", lines))

    duplicate = frame(
        [
            MultiLineString(
                [
                    shift(LineString([(0, 0), (10, 0), (10, 0), (20, 10), (20, 10), (30, 20)])),
                ]
            ),
            MultiLineString(
                [
                    shift(LineString([(0, 0), (20, 0)])),
                    shift(LineString([(30, 0), (30, 20), (50, 20)])),
                ]
            ),
        ]
    )
    cases.append(
        write_case(output, "06_LINE_MULTI_DUPLICATE", "连续重复点和MultiLineString", duplicate)
    )

    empty_line = frame(
        [
            shift(LineString([(0, 0), (10, 10)])),
            None,
            LineString(),
        ]
    )
    cases.append(write_case(output, "07_LINE_EMPTY", "正常线、null和空线混合", empty_line))

    large_line = frame([shift(LineString([(i * 0.5, np.sin(i / 100) * 20) for i in range(10001)]))])
    cases.append(
        write_case(output, "08_LINE_10001_VERTICES", "一万零一个线顶点及大坐标段", large_line)
    )

    polygons = frame(
        [
            shift(Polygon([(0, 0), (100, 0), (0, 100), (0, 0)])),
            shift(Polygon([(200, 0), (300, 0), (300, 100), (200, 100), (200, 0)])),
        ]
    )
    cases.append(write_case(output, "09_POLY_BASIC", "最小三角形和矩形", polygons))

    outer = shift(
        Polygon(
            [(0, 0), (300, 0), (300, 300), (0, 300), (0, 0)],
            [
                [(50, 50), (100, 50), (100, 100), (50, 100), (50, 50)],
                [(150, 150), (200, 150), (200, 200), (150, 200), (150, 150)],
            ],
        )
    )
    multipart = MultiPolygon(
        [
            outer,
            shift(Polygon([(400, 0), (450, 0), (425, 50), (400, 0)])),
        ]
    )
    cases.append(
        write_case(output, "10_POLY_HOLE_MULTIPART", "双孔、多部件和独立三角面", frame([multipart]))
    )

    shared = frame(
        [
            shift(Polygon([(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)])),
            shift(Polygon([(100, 0), (200, 0), (200, 100), (100, 100), (100, 0)])),
            shift(
                Polygon(
                    [(300, 0), (400, 0), (400, 100), (300, 100), (300, 0)],
                    [[(325, 25), (375, 25), (375, 75), (325, 75), (325, 25)]],
                )
            ),
            shift(Polygon([(325, 25), (375, 25), (375, 75), (325, 75), (325, 25)])),
        ]
    )
    cases.append(
        write_case(output, "11_POLY_SHARED_ISLAND", "共边、孔洞与边界完全一致的独立岛", shared)
    )

    duplicates = frame(
        [
            shift(
                Polygon(
                    [
                        (0, 0),
                        (50, 0),
                        (50, 0),
                        (100, 0),
                        (100, 100),
                        (50, 100),
                        (0, 100),
                        (0, 50),
                        (0, 50),
                        (0, 0),
                    ]
                )
            )
        ]
    )
    cases.append(
        write_case(output, "12_POLY_DUPLICATE_VERTICES", "连续及非连续重复环顶点", duplicates)
    )

    bowtie = frame([shift(Polygon([(0, 0), (100, 100), (100, 0), (0, 100), (0, 0)]))])
    cases.append(write_case(output, "13_POLY_BOWTIE", "自交蝴蝶结无效面", bowtie))

    degenerate = frame([shift(Polygon([(10, 10)] * 5))])
    cases.append(write_case(output, "14_POLY_DEGENERATE", "全部顶点相同的退化环", degenerate))

    empty_polygon = frame(
        [
            shift(Polygon([(0, 0), (50, 0), (0, 50), (0, 0)])),
            None,
            Polygon(),
        ]
    )
    cases.append(write_case(output, "15_POLY_EMPTY", "正常面、null和空面混合", empty_polygon))

    fields = {f"FIELD_{i:02d}": [i, i + 0.5, None] for i in range(1, 81)}
    fields["中文名称"] = ["多字段一", "多字段二", "多字段三"]
    many_fields = frame(
        [
            shift(Polygon([(0, 0), (10, 0), (0, 10), (0, 0)])),
            shift(Polygon([(20, 0), (30, 0), (20, 10), (20, 0)])),
            shift(Polygon([(40, 0), (50, 0), (40, 10), (40, 0)])),
        ],
        fields,
    )
    cases.append(write_case(output, "16_POLY_80_FIELDS", "80个附加字段及中文字段", many_fields))

    angles = np.linspace(0, 2 * np.pi, 5001)
    exterior = list(zip(500 + 400 * np.cos(angles), 500 + 400 * np.sin(angles)))
    hole_angles = np.linspace(0, 2 * np.pi, 101)
    hole = list(zip(500 + 100 * np.cos(hole_angles), 500 + 100 * np.sin(hole_angles)))
    large_ring = frame([Polygon(exterior, [hole])])
    cases.append(write_case(output, "17_POLY_LARGE_RING", "5001点外环和101点孔洞", large_ring))

    duplicate_polygons = frame(
        [
            shift(Polygon([(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)])),
            shift(Polygon([(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)])),
        ],
        {"NAME": ["几何相同属性一", "几何相同属性二"], "VALUE": [1, 2]},
    )
    cases.append(
        write_case(
            output,
            "18_POLY_DUPLICATE_ATTRIBUTES",
            "相同几何、不同属性及原生参数归属",
            duplicate_polygons,
        )
    )

    long_text = frame(
        [
            shift(Polygon([(0, 0), (20, 0), (0, 20), (0, 0)])),
        ],
        {
            "NAME": ["长中文属性" * 20],
            "CONTROL": ["→D↓2→kz↑1，#-1，#+2，#=3"],
            "DESCRIPTION": ["仅用于Writer属性宽度核验，不表示真实地层。" * 8],
        },
    )
    cases.append(write_case(output, "19_POLY_LONG_TEXT", "长中文、控制码与属性宽度", long_text))

    empty = gpd.GeoDataFrame(
        {
            "ID": pd.Series(dtype="int64"),
            "NAME": pd.Series(dtype="object"),
            "geometry": gpd.GeoSeries([], crs=GK75),
        },
        crs=GK75,
    )
    cases.append(write_case(output, "20_EMPTY_FILE", "零要素文件及几何类型显式处理", empty))

    manifest = {
        "title": "Writer native SHP audit batch 4",
        "created": "2026-11-08",
        "crs": {
            "name": "Gauss-Kruger central meridian 75E",
            "proj4": GK75,
            "central_meridian": 75,
            "scale_factor": 1,
            "false_easting": 500000,
            "units": "m",
        },
        "conversion_requested": "Use MapGIS native SHP-to-MapGIS conversion, never pymapgis.Writer",
        "cases": cases,
    }
    (output / "writer_batch4_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# 第四批 Writer 原生转换 SHP 用例",
        "",
        "本批聚焦几何、属性、拓扑和原生默认参数，不以坐标系覆盖为目标。全部用例使用高斯-克吕格中央经线75°E、k=1、东偏500000m、单位米。",
        "",
        "## 请转换",
        "",
        "请使用 MapGIS 原生软件将各子目录中的 SHP 转为对应 WT/WL/WP，"
        "保持原文件名，输出到 `mapgis_native/`。不要使用 pymapgis.Writer 生成对照文件。",
        "",
        "同时请尽量提供：",
        "",
        "1. MapGIS 版本和构建号；",
        "2. 转换界面设置或截图，特别是投影、编码、空几何及默认图形参数；",
        "3. 转换失败日志（空文件、空几何、退化环等不得静默跳过）；",
        "4. 如方便，同时导出对应 WAT/WAL/WAP 明码文件。",
        "",
        "## 用例",
        "",
        "| 用例 | 要素数 | 审计重点 |",
        "|---|---:|---|",
    ]
    for case in cases:
        lines.append(f"| {case['case']} | {case['features']} | {case['focus']} |")
    lines.extend(
        [
            "",
            "空值、无效几何和不支持类型的预期行为不预设为成功；"
            "请保留 MapGIS 的实际成功、失败或跳过结果，以便与 Writer 的显式错误处理比较。",
            "",
        ]
    )
    (output / "README_转换说明.md").write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "cases": len(cases),
                "features": sum(c["features"] for c in cases),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
