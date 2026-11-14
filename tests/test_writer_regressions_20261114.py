"""Regression tests for Writer projection, attribute and polygon-passthrough fixes."""
import struct
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

from pymapgis import Reader, Writer

FIXTURES = Path(__file__).parents[1] / "tests" / "fixtures"


@pytest.mark.parametrize("projection", ["aea", "lcc"])
def test_conic_first_standard_parallel_roundtrip(tmp_path, projection):
    crs = (
        f"+proj={projection} +lat_0=30 +lon_0=105 +lat_1=36.25 +lat_2=47 "
        "+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    )
    frame = gpd.GeoDataFrame(
        {"name": ["conic"]},
        geometry=[Point(0, 0)],
        crs=crs,
    )
    path = tmp_path / f"{projection}.wt"
    Writer(frame, map_scale=1000).to_file(path)
    assert "+lat_1=36.25" in Reader(path).crs.to_proj4()


def test_append_native_attribute_preserves_values_and_layout(tmp_path):
    source = Reader(
        FIXTURES / "writer_batch3/08_ATTRIBUTE_TYPES.WP",
        read_graphic_params=True,
    )
    frame = source.geodataframe
    frame["新增字段"] = ["值X", "值Y", "值Z"]
    path = tmp_path / "append.wp"
    Writer(frame, preserve_utm=True, map_scale=1000).to_file(path)

    result = Reader(path, read_graphic_params=True)
    assert result.data["新增字段"].tolist() == ["值X", "值Y", "值Z"]
    for name in source.data.columns:
        assert result.data[name].equals(source.data[name])
    assert all(
        left.equals_exact(right, 1e-8)
        for left, right in zip(source.geom, result.geom)
    )
    assert result.polygon_params.equals(source.polygon_params)

    data_start = struct.unpack_from("<i", path.read_bytes(), 12)[0]
    attr_start, _ = struct.unpack_from("<2i", path.read_bytes(), data_start + 9 * 10)
    new_length = struct.unpack_from("<h", path.read_bytes(), attr_start + 328)[0]
    assert new_length == 612  # Native 531 + one 81-byte string slot.


def _small_notch(geometry):
    """Insert a small inward vertex on the longest edge without changing bounds."""
    coordinates = list(geometry.exterior.coords)
    index = max(
        range(len(coordinates) - 1),
        key=lambda i: (
            (coordinates[i + 1][0] - coordinates[i][0]) ** 2
            + (coordinates[i + 1][1] - coordinates[i][1]) ** 2
        ),
    )
    x0, y0 = coordinates[index]
    x1, y1 = coordinates[index + 1]
    midpoint = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
    centroid = geometry.centroid
    notch = (
        midpoint[0] + (centroid.x - midpoint[0]) * 0.0001,
        midpoint[1] + (centroid.y - midpoint[1]) * 0.0001,
    )
    return Polygon(coordinates[: index + 1] + [notch] + coordinates[index + 1 :])


def test_small_polygon_edit_is_not_discarded_by_passthrough(tmp_path):
    source = Reader(FIXTURES / "writer_batch2/01_MINIMAL_TRIANGLE.WP")
    frame = source.geodataframe
    edited = _small_notch(frame.geometry.iloc[0])
    frame.loc[frame.index[0], "geometry"] = edited
    path = tmp_path / "small-edit.wp"
    Writer(frame, preserve_utm=True, map_scale=1000).to_file(path)

    result = Reader(path).geodataframe.geometry.iloc[0]
    assert result.equals_exact(edited, 1e-8)
    assert len(result.exterior.coords) == len(edited.exterior.coords)
    assert result.area == pytest.approx(edited.area)


def test_small_polygon_edit_without_native_fixture(tmp_path):
    original = tmp_path / "original.wp"
    frame = gpd.GeoDataFrame(
        {"n": [1]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])],
        crs="EPSG:4326",
    )
    Writer(frame).to_file(original)
    before = Reader(original).geodataframe
    coordinates = list(before.geometry.iloc[0].exterior.coords)
    edited = Polygon(coordinates[:3] + [(0.5, 0.99997)] + coordinates[3:])
    before.loc[before.index[0], "geometry"] = edited
    changed = tmp_path / "changed.wp"
    Writer(before).to_file(changed)
    result = Reader(changed).geodataframe.geometry.iloc[0]
    assert result.equals_exact(edited, 1e-12)
    assert result.area == pytest.approx(0.999985)
