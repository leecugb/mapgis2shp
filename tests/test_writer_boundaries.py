import geopandas as gpd
import pytest
import shapely.geometry

from pymapgis import Reader, Writer, WriterError


def test_make_valid_non_polygon_result_raises_writer_error(tmp_path):
    collapsed = shapely.geometry.Polygon([(0, 0), (0, 0), (0, 0), (0, 0)])
    gdf = gpd.GeoDataFrame(geometry=[collapsed], crs="EPSG:4326")
    with pytest.raises(WriterError, match="no polygonal geometry"):
        Writer(gdf, make_valid=True).to_file(tmp_path / "collapsed.wp")


def test_polygon_ring_index_exact_24bit_boundary():
    from pymapgis.writer import _encode_polygon_params

    encoded = _encode_polygon_params(None, 1, {1: 0xFFFFFF})
    assert encoded[45:48] == b"\xff\xff\xff"
    for invalid in (-1, 0x1000000):
        with pytest.raises(WriterError, match="exceeds 24 bits"):
            _encode_polygon_params(None, 1, {1: invalid})


def test_empty_geodataframe_type_contract(tmp_path):
    empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    with pytest.raises(WriterError, match="geometry_type"):
        Writer(empty)
    output = tmp_path / "empty.wp"
    Writer(empty, geometry_type="POLYGON").to_file(output)
    assert len(Reader(output)) == 0


@pytest.mark.parametrize("projection", ["aea", "lcc"])
def test_albers_and_lambert_positive_roundtrip(tmp_path, projection):
    crs = (
        f"+proj={projection} +lat_0=30 +lon_0=105 +lat_1=25 +lat_2=45 "
        "+x_0=100 +y_0=200 +datum=WGS84 +units=m +no_defs"
    )
    gdf = gpd.GeoDataFrame(geometry=[shapely.geometry.Point(100000, 200000)], crs=crs)
    output = tmp_path / f"{projection}.wt"
    Writer(gdf).to_file(output)
    reader = Reader(output)
    proj4 = reader.geodataframe.crs.to_proj4()
    assert f"+proj={projection}" in proj4
    assert "+lat_0=30" in proj4
    assert "+lon_0=105" in proj4
    assert "+lat_1=25" in proj4
    assert "+lat_2=45" in proj4
    assert "+x_0=100" in proj4
    assert "+y_0=200" in proj4
    assert reader.geodataframe.geometry.iloc[0].x == pytest.approx(100000)
    assert reader.geodataframe.geometry.iloc[0].y == pytest.approx(200000)
