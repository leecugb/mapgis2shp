"""Verify that one WT can contain both subgraph and annotation records."""
import os
import struct
from pathlib import Path

import pytest

from examples.build_mixed_attitude_layer import build_mixed
from pymapgis import GraphicLibraries, GraphicRenderer
from pymapgis.testing import slib_path


def test_mixed_attitude_wt_symbols_and_annotations(tmp_path):
    if not Path("work_usgs/e00/tempfiles").is_dir():
        pytest.skip("USGS source is unavailable")
    path, reader = build_mixed(tmp_path / "mixed")
    params = reader.point_params
    assert len(reader) == 46
    assert params["point_type"].tolist() == [1] * 23 + [0] * 23
    assert params["symbol_no"].iloc[:23].eq(1245).sum() == 21
    assert params["symbol_no"].iloc[23:].eq(0).all()
    assert params["height"].iloc[23:].eq(6).all()
    assert reader.geodataframe["CHFCED"].iloc[23:].tolist() == [
        "51", "20", "15", "47", "62", "42", "47", "55", "65", "30", "58",
        "42", "45", "17", "55", "78", "19", "16", "60", "40", "27", "35", "42",
    ]

    raw = path.read_bytes()
    table = struct.unpack_from("<i", raw, 12)[0]
    start, _ = struct.unpack_from("<2i", raw, table + 40)
    flags = struct.unpack_from("<46i", raw, start + 4)
    assert flags[:23] == (65536,) * 23
    assert flags[23:] == (65538,) * 23

    if not os.environ.get("PYMAPGIS_SLIB") and not Path(r"D:/SLIB/SLIB").is_dir():
        pytest.skip("SLIB is unavailable")
    layer = reader.geodataframe
    layer.attrs["source"] = path.name
    layer.attrs["kind"] = "wt"
    renderer = GraphicRenderer(GraphicLibraries.from_directory(slib_path()), scale=24000)
    result = renderer.render([layer], tmp_path / "mixed.png", figsize=(5, 4), dpi=60)
    report = result.reports[0]
    assert report["features"] == 46
    assert report["drawn"] == 46
    assert report["symbols"] == 23
    assert report["text"] == 23
    assert report.get("symbols_unresolved", 0) == 0
