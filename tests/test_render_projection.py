import geopandas as gpd
import pyproj
import pytest
from shapely.geometry import Point

from pymapgis.render_projection import gauss_kruger_crs, prepare_render_layers

JWD_CRS = "+proj=longlat +ellps=krass +towgs84=15.8,-154.4,-82.3,0,0,0,0 +no_defs"


def make_layer(longitude=74.25, latitude=39.5, crs=JWD_CRS):
    return gpd.GeoDataFrame(geometry=[Point(longitude, latitude)], crs=crs)


def test_jwd_default_is_source_datum_gk75():
    layers, target, metadata = prepare_render_layers(
        [make_layer(73.5, 39.0), make_layer(75.0, 40.0)]
    )
    proj4 = target.to_proj4()
    assert metadata["target_source"] == "default_gauss_kruger"
    assert metadata["central_meridian"] == 75.0
    assert metadata["zone"] == 43
    assert "+lon_0=75" in proj4
    assert "+k=1" in proj4
    assert "+ellps=krass" in proj4
    assert "+towgs84=15.8,-154.4,-82.3,0,0,0,0" in proj4
    assert "+units=m" in proj4
    assert all(layer.crs == target for layer in layers)


def test_explicit_target_crs_wins():
    layers, target, metadata = prepare_render_layers(
        [make_layer()], target_crs="EPSG:32643"
    )
    assert target.to_epsg() == 32643
    assert metadata["target_source"] == "explicit"
    assert layers[0].crs.to_epsg() == 32643


def test_zone_boundary_and_three_degree_option():
    target, metadata = gauss_kruger_crs(73.5, JWD_CRS)
    assert metadata["central_meridian"] == 75.0
    target3, metadata3 = gauss_kruger_crs(74.25, JWD_CRS, zone_width=3)
    assert metadata3["central_meridian"] == 75.0
    with pytest.raises(ValueError, match="zone_width"):
        gauss_kruger_crs(74.25, JWD_CRS, zone_width=4)


def test_missing_crs_requires_source_or_explicit_units():
    layer = make_layer(crs=None)
    with pytest.raises(ValueError, match="source_crs or map_units_per_mm"):
        prepare_render_layers([layer])
    layers, target, metadata = prepare_render_layers([layer], map_units_per_mm=250)
    assert target is None
    assert metadata["target_source"] == "unprojected_explicit_units"
    assert layers[0].crs is None
    with pytest.raises(ValueError, match="source CRS is missing"):
        prepare_render_layers(
            [make_layer(crs=None)], target_crs="EPSG:32643", map_units_per_mm=250
        )


def test_missing_crs_can_be_supplied():
    layers, target, _ = prepare_render_layers(
        [make_layer(crs=None)], source_crs=JWD_CRS
    )
    assert "+lon_0=75" in target.to_proj4()


def test_empty_layer_receives_shared_target():
    empty = gpd.GeoDataFrame(geometry=[])
    layers, target, _ = prepare_render_layers([make_layer(), empty])
    assert layers[1].crs == target
    assert len(layers[1]) == 0


def test_mixed_datums_require_explicit_target():
    with pytest.raises(ValueError, match="Mixed source datums"):
        prepare_render_layers(
            [make_layer(), make_layer(crs="EPSG:4326")]
        )


def test_large_span_and_antimeridian_are_rejected():
    with pytest.raises(ValueError, match="more than 9 degrees"):
        prepare_render_layers(
            [make_layer(0, 39), make_layer(10, 39)]
        )
    with pytest.raises(ValueError, match="antimeridian"):
        gauss_kruger_crs(180, JWD_CRS)
