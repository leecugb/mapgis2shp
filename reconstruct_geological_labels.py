#!/usr/bin/env python3
"""从地质面图层重构完整地质单元代号标注点。

LDZOFBB099.WT 中的代号注记是分散的标注对象（如 N#-1 与 a 分开存储），
本脚本直接根据地层/侵入岩面图层的 QDUECC/QDUECD 完整代号，计算每个连通地块的
representative_point()，生成完整的标注点图层。
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from pymapgis import Reader

ROOT = Path(__file__).parent
TARGET_CRS = "EPSG:32643"  # WGS84 UTM Zone 43N
LAYER_ORDER = ["LDZOFBB004", "LDZOFBB001", "LDZOFBB002", "LDZOFBB003"]


def load_layer(name: str) -> gpd.GeoDataFrame:
    for ext in ("WP", "WL", "WT"):
        path = ROOT / f"{name}.{ext}"
        if path.exists():
            with Reader(path) as r:
                gdf = r.geodataframe.copy()
            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:4326")
            return gdf.to_crs(TARGET_CRS)
    raise FileNotFoundError(f"No file found for {name}")


def main() -> int:
    records = []
    for layer in LAYER_ORDER:
        gdf = load_layer(layer)
        if gdf.empty:
            continue
        code_col = None
        for c in ("QDUECC", "QDUECD"):
            if c in gdf.columns:
                code_col = c
                break
        if code_col is None:
            print(f"[skip] {layer}: no code column")
            continue

        gdf = gdf.copy()
        gdf["__code__"] = gdf[code_col].astype(str).str.strip()

        # 按相同代号融合，再 explode 多部分，保证每个连通地块一个标注点
        dissolved = gdf.dissolve(by="__code__", as_index=False)
        dissolved = dissolved.explode(index_parts=True).reset_index(drop=True)
        dissolved["__label_point__"] = dissolved.geometry.representative_point()

        for _, row in dissolved.iterrows():
            records.append(
                {
                    "layer": layer,
                    "code": row["__code__"],
                    "geometry": row["__label_point__"],
                }
            )

    labels = gpd.GeoDataFrame(records, crs=TARGET_CRS)

    out_geojson = ROOT / "geological_labels_reconstructed.geojson"
    out_csv = ROOT / "geological_labels_reconstructed.csv"

    labels.to_file(out_geojson, driver="GeoJSON")
    labels.drop(columns="geometry").to_csv(
        out_csv, index=False, encoding="utf-8-sig"
    )

    print(f"Generated {len(labels)} reconstructed labels")
    print(f"  GeoJSON: {out_geojson}")
    print(f"  CSV: {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
