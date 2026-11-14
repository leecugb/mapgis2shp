#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the bundled USGS Conejo Well fixture inventory and manifest."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.e00_fast import read_coverage  # noqa: E402
from pymapgis import Reader  # noqa: E402

DEST = ROOT / "tests/fixtures/usgs_conejo"
SOURCE = ROOT / "work_usgs/e00/tempfiles"
NATIVE = ROOT / "testdata"

SOURCE_FILES = (
    "cwell_geo.e00", "cwell_dk.e00", "cwell_str.e00", "cwell_orn.e00",
    "cwell_ldr.e00", "lines.rel.e00", "points.rel.e00",
)
METADATA_FILES = ("cwell_met.txt", "cwell_readme.txt", "cwell_pamph.txt")
NATIVE_FILES = {
    "CWELL_GEO_WP.WP": NATIVE / "CWELL_GEO_WP.WP",
    "CWELL_GEO_WL.WL": NATIVE / "CWELL_GEO_WL.WL",
    "CWELL_DK_WL.WL": NATIVE / "CWELL_DK_WL.WL",
    "CWELL_STR_WT.WT": NATIVE / "CWELL_STR_WT.WT",
    "CWELL_ORN_WT.WT": NATIVE / "CWELL_ORN_WT.WT",
    "CWELL_LDR_WL.WL": NATIVE / "CWELL_LDR_WL.WL",
}


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    if DEST.exists():
        raise SystemExit(f"Refusing to overwrite existing fixture directory: {DEST}")
    (DEST / "source").mkdir(parents=True)
    (DEST / "native").mkdir()
    (DEST / "metadata").mkdir()
    for name in SOURCE_FILES:
        shutil.copy2(SOURCE / name, DEST / "source" / name)
    for name in METADATA_FILES:
        shutil.copy2(SOURCE / name, DEST / "metadata" / name)
    for name, source in NATIVE_FILES.items():
        shutil.copy2(source, DEST / "native" / name)

    source_info = {}
    for name in SOURCE_FILES[:5]:
        coverage = read_coverage(str((DEST / "source" / name).resolve()))
        source_info[name] = {
            "sha256": _sha256(DEST / "source" / name),
            "layers": {layer: len(records) for layer, records in coverage.items()},
        }
    native_info = {}
    for name in sorted(NATIVE_FILES):
        path = DEST / "native" / name
        reader = Reader(path, read_graphic_params=True)
        native_info[name] = {
            "sha256": _sha256(path),
            "features": len(reader.geodataframe),
            "empty_geometries": int(reader.geodataframe.geometry.is_empty.sum()),
            "origin": "MapGIS-produced native file",
        }
    manifest = {
        "schema_version": 1,
        "dataset": "USGS Conejo Well 7.5-minute quadrangle",
        "citation": (
            "Powell, Robert E., and Cossette, Pamela M. (digital cartography), 2001. "
            "Geologic map and digital database of the Conejo Well 7.5 minute "
            "quadrangle, Riverside County, California. USGS OFR 01-031, Version 1.0."
        ),
        "url": "https://pubs.usgs.gov/of/2001/of01-031/",
        "distribution": "Bundled six-layer test fixture, not synthetic",
        "rights_note": (
            "USGS-authored public-domain data. Access_Constraints=None. Preserve "
            "attribution, source metadata, as-is disclaimer and spatial-resolution "
            "limits. No SLIB libraries are bundled."
        ),
        "source_crs": "NAD27 Polyconic",
        "native_crs": "UTM11; source SHP declares EPSG:32611",
        "source_files": source_info,
        "native_files": native_info,
        "metadata_files": {
            name: _sha256(DEST / "metadata" / name) for name in METADATA_FILES
        },
    }
    (DEST / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DEST / "README.md").write_text(
        """# USGS Conejo Well 内置测试数据

来源：Powell、Cossette，USGS Open-File Report 01-031，Version 1.0。
https://pubs.usgs.gov/of/2001/of01-031/

本夹具仅使用 `testdata` 下的六个 MapGIS 文件，不包含独立的 lab 注记文件。
WP 中的 LABL、QDUECC、QDUECD、CHFCAC 等属性仍可用于区注记。
`source/` 为原始 ARC/INFO 文件；`native/` 为 MapGIS 可读取的 WT/WL/WP；
`metadata/` 保留原始说明与使用限制。`manifest.json` 记录各文件哈希、要素数、
来源和生成方式。

版权与使用：USGS 政府作品通常属于公共领域，原始元数据声明
`Access_Constraints: None`。仍须保留 USGS 署名、版本、原图说明、as-is 免责和
空间分辨率限制，不得暗示 USGS 对转换结果背书。SLIB 不随本数据分发。
""",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
