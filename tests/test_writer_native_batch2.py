"""Native SHP-to-MapGIS conversion regressions for the Writer."""
from __future__ import annotations

import geopandas as gpd
import pandas as pd
import pytest

from pymapgis import Reader, Writer
from pymapgis.testing import fixture_path

FIXTURE_ROOT = fixture_path("writer_batch2")
CASES = sorted(FIXTURE_ROOT.glob("*.shp"))
assert CASES, "writer_batch2 SHP fixtures are missing"
ATTRIBUTES = ("FID", "NAME", "CODE", "VALUE", "DATE")


def _scalar(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _records(gdf):
    return [
        {name: _scalar(row[name]) for name in ATTRIBUTES}
        for _, row in gdf.iterrows()
    ]


def _expected_source(gdf):
    if (gdf.geom_type == "MultiLineString").any():
        return gdf.explode(index_parts=False)
    return gdf


def _read_native(path):
    return Reader(str(path), read_graphic_params=True, read_point_params=True)


@pytest.mark.parametrize("shp", CASES, ids=lambda path: path.stem)
def test_writer_against_native_shp_conversion(shp, tmp_path):
    """Writer preserves source semantics and native default line/point styles."""
    suffix = ".WT" if shp.stem.startswith("10_") else ".WL" if shp.stem.startswith("11_") else ".WP"
    native_path = FIXTURE_ROOT / (shp.stem.upper() + suffix)
    source = gpd.read_file(shp)
    native = _read_native(native_path).geodataframe
    output = tmp_path / (shp.stem + suffix.lower())

    Writer(source).to_file(output)
    ours = _read_native(output).geodataframe
    expected = _expected_source(source)

    assert _records(ours) == _records(expected)
    assert len(ours) == len(expected)
    assert ours.crs is not None
    assert ours.crs.to_epsg() == 4326

    if shp.stem == "09_invalid_bowtie":
        # Both native conversion and Writer split the invalid ring into triangles.
        assert [geom.wkt for geom in ours.geometry] == [geom.wkt for geom in native.geometry]
    else:
        for expected_geom, actual_geom in zip(expected.geometry, ours.geometry):
            assert expected_geom.equals(actual_geom)

    if suffix == ".WP":
        for row in ours.itertuples():
            for name in ("field5", "field6", "field7"):
                value = getattr(row, name)
                assert 0 <= value <= 0xFFFFFFFF

    if suffix == ".WT":
        for name in ("height", "width", "color", "pen_width"):
            assert ours[name].tolist() == native[name].tolist()

    if suffix == ".WL":
        for name in ("width", "x_coef", "y_coef", "aux_flag"):
            assert set(ours[name]) == set(native[name])
