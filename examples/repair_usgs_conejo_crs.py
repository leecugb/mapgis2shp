#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Repair the six USGS MapGIS headers as WGS84 UTM 11N without moving geometry.

The native projected-CRS block uses Transverse Mercator, central meridian -117
and k=0.9996. Header scale=1000 makes Reader's geometry multiplier 1000/1000=1.
Only header bytes are changed; original fixtures are never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pymapgis import Reader  # noqa: E402
from pymapgis.testing import usgs_conejo_path  # noqa: E402
from pymapgis.writer import (  # noqa: E402
    _HEADER_CRS_BLOCK_BYTES,
    _HEADER_CRS_BLOCK_F32_BYTES,
    _HEADER_CRS_BLOCK_U8,
    _HEADER_CRS_NEG_ZERO_OFFSET,
)

NAMES = (
    "CWELL_GEO_WP.WP",
    "CWELL_GEO_WL.WL",
    "CWELL_DK_WL.WL",
    "CWELL_STR_WT.WT",
    "CWELL_ORN_WT.WT",
    "CWELL_LDR_WL.WL",
)
PROJECTION_K = 0.9996
CENTRAL_MERIDIAN_RAW = -1170000.0
HEADER_SCALE = 1000.0
PROJECTION_SCALE_OFFSET = 232


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _ranges(positions):
    if not positions:
        return []
    result = []
    start = previous = positions[0]
    for position in positions[1:]:
        if position != previous + 1:
            result.append([start, previous + 1])
            start = position
        previous = position
    result.append([start, previous + 1])
    return result


def _geometry_hash(reader):
    digest = hashlib.sha256()
    for geometry in reader.geom:
        digest.update(geometry.wkb)
    return digest.hexdigest()


def _header_fields():
    fields = [
        (109, "B", 5),
        (110, "B", 7),
        (143, "d", HEADER_SCALE),
        (151, "d", CENTRAL_MERIDIAN_RAW),
        (PROJECTION_SCALE_OFFSET, "d", PROJECTION_K),
        (_HEADER_CRS_NEG_ZERO_OFFSET, "f", -0.0),
    ]
    fields.extend((offset, "B", value) for offset, value in _HEADER_CRS_BLOCK_BYTES.items())
    fields.extend((offset, "B", value) for offset, value in _HEADER_CRS_BLOCK_U8.items())
    for offset, raw in _HEADER_CRS_BLOCK_F32_BYTES.items():
        fields.extend((offset + index, "B", value) for index, value in enumerate(raw))
    return fields


def repair_file(source: Path, destination: Path):
    original_bytes = source.read_bytes()
    patched = bytearray(original_bytes)
    allowed = set()
    for offset, fmt, value in _header_fields():
        struct.pack_into("<" + fmt, patched, offset, value)
        allowed.update(range(offset, offset + struct.calcsize("<" + fmt)))
    changed = [
        index
        for index, (left, right) in enumerate(zip(original_bytes, patched))
        if left != right
    ]
    unexpected = [index for index in changed if index not in allowed]
    if unexpected:
        raise AssertionError(f"Unexpected changed bytes in {source.name}: {unexpected[:10]}")
    patched_bytes = bytes(patched)
    if len(patched_bytes) != len(original_bytes):
        raise AssertionError("Header repair changed the file length")
    destination.write_bytes(patched_bytes)

    original = Reader(source)
    repaired = Reader(destination)
    original_geometry_hash = _geometry_hash(original)
    repaired_geometry_hash = _geometry_hash(repaired)
    if original_geometry_hash != repaired_geometry_hash:
        raise AssertionError(f"Geometry changed in {source.name}")
    if repaired.crs in (None, "") or repaired.crs.to_epsg() != 32611:
        raise AssertionError(f"CRS repair failed in {source.name}: {repaired.crs}")
    if repaired.coordinate_scale_factor != 1.0:
        raise AssertionError(f"Coordinate scale is not 1.0 in {source.name}")
    return {
        "file": source.name,
        "bytes": len(original_bytes),
        "features": len(repaired.geom),
        "source_sha256": _sha256(original_bytes),
        "repaired_sha256": _sha256(patched_bytes),
        "changed_byte_ranges": _ranges(changed),
        "geometry_sha256_before": original_geometry_hash,
        "geometry_sha256_after": repaired_geometry_hash,
        "bounds": list(repaired.bbox),
        "reader_crs": repaired.crs.to_wkt(),
        "reader_epsg": repaired.crs.to_epsg(),
        "reader_coordinate_scale_factor": repaired.coordinate_scale_factor,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=usgs_conejo_path("native"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/usgs_conejo/six_file_tests/utm11_crs_repaired"),
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reports = [
        repair_file(args.input_dir / name, args.output_dir / name)
        for name in NAMES
    ]
    report = {
        "target": {
            "crs": "WGS84 / UTM Zone 11N",
            "epsg": 32611,
            "native_projection": "Transverse Mercator",
            "central_meridian_degrees": -117.0,
            "projection_scale_factor_k": PROJECTION_K,
            "projection_scale_offset": PROJECTION_SCALE_OFFSET,
            "header_scale": HEADER_SCALE,
            "reader_coordinate_scale_factor": 1.0,
            "coordinate_units": "metre",
            "external_cartographic_scale": 24000,
        },
        "method": (
            "Copy files and patch only the native CRS header; "
            "no geometry or attribute rewrite"
        ),
        "original_fixtures_modified": False,
        "native_mapgis_acceptance": (
            "Pending open/save/close/reopen testing in MapGIS. Reader/Writer verification "
            "is not a substitute for native MapGIS acceptance."
        ),
        "files": reports,
    }
    (args.output_dir / "crs_repair_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / "README.md").write_text(
        "# 六文件 UTM 11N 空间参考修补\n\n"
        "- 原生投影：横轴墨卡托，中央经线 −117°，k=0.9996，WGS84 椭球。\n"
        "- Reader 回读 CRS 与 EPSG:32611 等效，`coordinate_scale_factor=1.0`。\n"
        "- 文件头 scale=1000，仅用于使几何读取因子为 1000/1000=1；外部制图比例尺仍为 1:24000。\n"
        "- 仅修补文件头，几何 WKB 哈希逐层一致，属性与图形记录未重写。\n"
        "- 原始内置夹具未修改。MapGIS 原生打开、保存、关闭、重开验收仍待测试电脑完成。\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output_dir": str(args.output_dir),
        "files": len(reports),
        "epsg": sorted({item["reader_epsg"] for item in reports}),
        "coordinate_scale_factor": sorted({
            item["reader_coordinate_scale_factor"] for item in reports
        }),
        "geometry_hash_unchanged": all(
            item["geometry_sha256_before"] == item["geometry_sha256_after"]
            for item in reports
        ),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
