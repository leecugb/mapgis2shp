#!/usr/bin/env python3
"""将库尔干幅 DZ/T 0179 标准色地质图渲染为 Raster MBTiles。

用法示例：
    python render_mbtiles.py --zooms 6 12 --tile-size 256 -o kurgan.mbtiles
"""

from __future__ import annotations

import argparse
import io
import sqlite3
import sys
import warnings
from pathlib import Path
from typing import Iterable, List, Tuple

import matplotlib.pyplot as plt
import mercantile

# 复用 render_strict_standard_map.py 中的图层准备与绘制逻辑
from render_strict_standard_map import load_and_prepare_layers, draw_map_content, PreparedLayers

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent

# MBTiles 使用 Web Mercator
TARGET_CRS = "EPSG:3857"


def parse_zooms(value: str) -> List[int]:
    """解析形如 '6-12' 或 '6,7,8,9,10,11,12' 的 zoom 范围。"""
    value = value.strip()
    if "-" in value:
        parts = value.split("-")
        if len(parts) != 2:
            raise argparse.ArgumentTypeError(f"Invalid zoom range: {value}")
        return list(range(int(parts[0]), int(parts[1]) + 1))
    if "," in value:
        return [int(z.strip()) for z in value.split(",")]
    return [int(value)]


def init_mbtiles(path: Path, bounds_wgs84: Tuple[float, float, float, float], zooms: List[int]) -> None:
    """创建 MBTiles 文件并初始化 schema。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE metadata (name TEXT, value TEXT);")
    cur.execute(
        "CREATE TABLE tiles ("
        "zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB);"
    )
    cur.execute(
        "CREATE UNIQUE INDEX tile_index ON tiles (zoom_level, tile_column, tile_row);"
    )

    west, south, east, north = bounds_wgs84
    center_lon = (west + east) / 2.0
    center_lat = (south + north) / 2.0
    center_zoom = (min(zooms) + max(zooms)) // 2

    metadata = {
        "name": "库尔干幅 DZ/T 0179 标准色地质图",
        "type": "baselayer",
        "version": "1.0",
        "description": "1:250000 库尔干幅（J43C001002）地质图 Raster MBTiles",
        "format": "png",
        "bounds": f"{west:.6f},{south:.6f},{east:.6f},{north:.6f}",
        "center": f"{center_lon:.6f},{center_lat:.6f},{center_zoom}",
        "minzoom": str(min(zooms)),
        "maxzoom": str(max(zooms)),
        "attribution": "DZ/T 0179 标准色",
    }
    cur.executemany(
        "INSERT INTO metadata (name, value) VALUES (?, ?);",
        list(metadata.items()),
    )
    conn.commit()
    conn.close()


def insert_tiles(path: Path, tiles: Iterable[Tuple[int, int, int, bytes]]) -> int:
    """批量插入瓦片，返回插入数量。"""
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    count = 0
    # 使用 REPLACE 避免重复，并一次性提交
    rows = []
    for z, x, y, data in tiles:
        # MBTiles 使用 TMS 行号：row = (2^z - 1) - y（OSM/XYZ 编号）
        row = (2 ** z - 1) - y
        rows.append((z, x, row, data))
        count += 1
    if rows:
        cur.executemany(
            "INSERT OR REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data) "
            "VALUES (?, ?, ?, ?);",
            rows,
        )
        conn.commit()
    conn.close()
    return count


def render_tile(
    prepared: PreparedLayers,
    tile: mercantile.Tile,
    tile_size: int = 256,
    margin_m: float = 2000.0,
    draw_labels: bool = True,
) -> bytes:
    """渲染单个瓦片并返回 PNG 字节。"""
    # Web Mercator 边界（米）
    bounds = mercantile.xy_bounds(tile)
    minx, miny, maxx, maxy = bounds.left, bounds.bottom, bounds.right, bounds.top

    # 创建与瓦片像素 1:1 的画布：1 英寸 × dpi = tile_size 像素
    dpi = tile_size
    fig, ax = plt.subplots(figsize=(1, 1), dpi=dpi)
    ax.set_position([0, 0, 1, 1])
    ax.axis("off")
    fig.patch.set_alpha(0)
    ax.set_facecolor("none")

    draw_map_content(
        ax,
        prepared,
        bounds=(minx, miny, maxx, maxy),
        margin_m=margin_m,
        draw_unit_labels=draw_labels,
        unit_label_sample_limit=None,
    )

    buf = io.BytesIO()
    fig.savefig(
        buf,
        format="png",
        dpi=dpi,
        bbox_inches=None,
        pad_inches=0,
        transparent=True,
    )
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def iter_tiles(
    prepared: PreparedLayers,
    zooms: List[int],
    tile_size: int = 256,
    margin_m: float = 2000.0,
    draw_labels_at_low_zoom: bool = False,
) -> Iterable[Tuple[int, int, int, bytes]]:
    """逐瓦片渲染并产生 (z, x, y, png_bytes)。"""
    # 计算 WGS84 边界以枚举瓦片
    lonlat_bounds = prepared.geology_all.to_crs("EPSG:4326").total_bounds
    west, south, east, north = lonlat_bounds

    for z in zooms:
        tiles = list(mercantile.tiles(west, south, east, north, zooms=[z]))
        print(f"Zoom {z}: {len(tiles)} tiles")
        for tile in tiles:
            # 低 zoom 下不绘制注记，避免过于拥挤
            draw_labels = draw_labels_at_low_zoom or z >= 9
            png = render_tile(prepared, tile, tile_size, margin_m, draw_labels=draw_labels)
            yield (tile.z, tile.x, tile.y, png)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render Kurgan geological map to Raster MBTiles")
    parser.add_argument(
        "--zooms",
        type=parse_zooms,
        default="6-12",
        help="Zoom range, e.g. '6-12' or '6,7,8,9,10,11,12' (default: 6-12)",
    )
    parser.add_argument(
        "--tile-size",
        type=int,
        default=256,
        choices=[256, 512],
        help="Tile size in pixels (default: 256)",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=ROOT / "kurgan_strict_standard_map.mbtiles",
        help="Output MBTiles file path",
    )
    parser.add_argument(
        "--margin-m",
        type=float,
        default=2000.0,
        help="Buffer margin in meters around each tile to avoid clipping symbols (default: 2000)",
    )
    parser.add_argument(
        "--labels-at-low-zoom",
        action="store_true",
        help="Draw unit labels even at low zoom levels (z < 9)",
    )
    args = parser.parse_args(argv)

    print(f"Loading and preparing layers in {TARGET_CRS}...")
    prepared = load_and_prepare_layers(ROOT, TARGET_CRS)

    lonlat_bounds = prepared.geology_all.to_crs("EPSG:4326").total_bounds
    print(f"Bounds (WGS84): {lonlat_bounds}")
    print(f"Zoom levels: {args.zooms}")
    print(f"Output: {args.output}")

    init_mbtiles(args.output, lonlat_bounds, args.zooms)

    print("Rendering tiles...")
    tiles_iter = iter_tiles(
        prepared,
        args.zooms,
        tile_size=args.tile_size,
        margin_m=args.margin_m,
        draw_labels_at_low_zoom=args.labels_at_low_zoom,
    )
    count = insert_tiles(args.output, tiles_iter)
    print(f"\nSaved {count} tiles to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
