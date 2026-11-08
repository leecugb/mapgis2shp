"""Large-offset, projected-CRS and exceptional-input Writer regressions."""
from __future__ import annotations

import geopandas as gpd
import pytest

from pymapgis import Writer, WriterError
from pymapgis.testing import fixture_path
from pymapgis.writer import _proj4_params
from tests.test_writer_native_batch2 import _expected_source, _read_native, _records

FIXTURE_ROOT = fixture_path("writer_batch3")
CASES = sorted(FIXTURE_ROOT.glob("*.shp"))


def _ring_offset(row):
    return int(row.field5) + (int(row.field6) << 8) + (int(row.field7) << 16)


def _output_path(shp, tmp_path):
    suffix = ".WT" if shp.stem.startswith("10_") else ".WL" if shp.stem.startswith("11_") else ".WP"
    return tmp_path / (shp.stem + suffix.lower()), suffix


@pytest.mark.parametrize("shp", CASES, ids=lambda path: path.stem)
def test_writer_native_batch3(shp, tmp_path):
    output, suffix = _output_path(shp, tmp_path)
    native_path = FIXTURE_ROOT / (shp.stem.upper() + suffix)
    source = gpd.read_file(shp)
    native = _read_native(native_path).geodataframe

    if shp.stem == "12_degenerate_ring":
        with pytest.raises(WriterError, match="fewer than three distinct vertices"):
            Writer(source).to_file(output)
        return

    if shp.stem == "09_null_geometry":
        with pytest.raises(WriterError, match="empty/null geometries"):
            Writer(source).to_file(output)
        empty_mask = source.geometry.isna() | source.geometry.is_empty
        Writer(source, on_empty="drop").to_file(output)
        expected = _expected_source(source.loc[~empty_mask])
    else:
        Writer(source).to_file(output)
        expected = _expected_source(source)

    ours = _read_native(output).geodataframe
    assert _records(ours) == _records(expected)
    assert len(ours) == len(expected)

    if shp.stem == "07_projected_utm":
        restored = ours.to_crs(source.crs)
        for expected_geom, actual_geom in zip(expected.geometry, restored.geometry):
            assert expected_geom.hausdorff_distance(actual_geom) <= 1e-5
        proj4 = ours.crs.to_proj4()
        params = _proj4_params(ours.crs)
        assert "+proj=tmerc" in proj4
        assert params["lon_0"] == 75.0
        assert params["k"] == 1.0
    else:
        for expected_geom, actual_geom in zip(expected.geometry, ours.geometry):
            assert expected_geom.equals(actual_geom)

    if suffix == ".WP":
        for row in ours.itertuples():
            offset = _ring_offset(row)
            assert 0 <= offset <= 0xFFFFFFFF
        if shp.stem == "05_large_ring_over_64k":
            assert _ring_offset(ours.iloc[0]) > 65535
            assert _ring_offset(ours.iloc[0]) == _ring_offset(native.iloc[0])
        if shp.stem == "06_large_then_small":
            assert all(_ring_offset(row) > 65535 for row in ours.itertuples())
        if shp.stem == "02_identical_polygons":
            assert ours["FID"].tolist() == [1, 2]
            assert ours.geometry.iloc[0].equals(ours.geometry.iloc[1])

    if suffix == ".WT":
        for name in ("height", "width", "color", "pen_width"):
            assert ours[name].tolist() == native[name].tolist()

    if suffix == ".WL":
        for name in ("width", "x_coef", "y_coef", "aux_flag"):
            assert set(ours[name]) == set(native[name])
