"""External MapGIS SHP-import reference tests for the Writer.

These tests run only when the user-supplied native reference batch is present.
They compare bytes and native declarations, not merely Writer/Reader round-trips.
"""
import struct
from pathlib import Path

import geopandas as gpd
import pytest

from examples.convert_usgs_conejo import LAYER_NAMES
from examples.export_usgs_shapefile import FIELD_ALIASES, GAUSS_KRUGER_CRS
from examples.repair_native_mapgis_graphics import NATIVE_FILES
from pymapgis import Reader, Writer

SOURCE = Path(r"F:/1111/usgs_conejo_shp/usgs_conejo_shp/gauss_kruger_117w")
pytestmark = pytest.mark.skipif(
    not SOURCE.is_dir(), reason="native MapGIS reference is unavailable"
)


@pytest.fixture(scope="module")
def source_layers():
    aliases = {alias: original for original, alias in FIELD_ALIASES.items()}
    layers = {}
    for name in LAYER_NAMES:
        _native_name, shp_name = NATIVE_FILES[name]
        layers[name] = gpd.read_file(SOURCE / shp_name, encoding="GBK").rename(
            columns=aliases
        )
    return layers


@pytest.fixture(scope="module")
def writer_outputs(source_layers, tmp_path_factory):
    output = tmp_path_factory.mktemp("writer_usgs_native")
    for name, layer in source_layers.items():
        Writer(layer.to_crs(GAUSS_KRUGER_CRS), make_valid=True).to_file(output / name)
    return output


@pytest.fixture(scope="module")
def native_default_outputs(source_layers, tmp_path_factory):
    output = tmp_path_factory.mktemp("writer_usgs_native_defaults")
    for name, layer in source_layers.items():
        Writer(
            layer.to_crs(GAUSS_KRUGER_CRS), make_valid=True, graphic_params=False
        ).to_file(output / name)
    return output


def _sections(path):
    data = path.read_bytes()
    table = struct.unpack_from("<i", data, 12)[0]
    return data, [struct.unpack_from("<ii", data, table + 10 * i) for i in range(16)]


def test_line_coordinate_sections_match_native(source_layers, writer_outputs):
    for name in ("cwell_geo.WL", "cwell_dk.WL", "cwell_ldr.WL"):
        native_name, _ = NATIVE_FILES[name]
        native, native_sections = _sections(SOURCE / native_name)
        ours, our_sections = _sections(writer_outputs / name)
        native_start, native_size = native_sections[1]
        our_start, our_size = our_sections[1]
        assert our_size == native_size
        assert ours[our_start:our_start + our_size] == (
            native[native_start:native_start + native_size]
        )


def test_point_coordinates_and_native_auxiliary_rules(source_layers, writer_outputs):
    for name in ("cwell_str.WT", "cwell_str_lab.WT", "cwell_orn.WT", "cwell_lab.WT"):
        native_name, _ = NATIVE_FILES[name]
        native, native_sections = _sections(SOURCE / native_name)
        ours, our_sections = _sections(writer_outputs / name)
        layer = source_layers[name].to_crs(GAUSS_KRUGER_CRS)
        minx, miny, maxx, maxy = layer.total_bounds
        assert struct.unpack_from("<4d", ours, 304) == pytest.approx(
            (minx - 0.1, miny - 0.1, maxx + 0.1, maxy + 0.1)
        )
        for i, row in enumerate(layer.itertuples(), start=1):
            native_offset = native_sections[0][0] + i * 93
            our_offset = our_sections[0][0] + i * 93
            assert ours[our_offset + 7:our_offset + 23] == (
                native[native_offset + 7:native_offset + 23]
            )
            flag_offset = our_sections[4][0] + i * 4
            assert struct.unpack_from("<i", ours, flag_offset)[0] == 65536
            x, y = row.geometry.x, row.geometry.y
            if row.point_type == 1:
                # Symbol points use a centred box, not a left-aligned text box.
                expected = (x - row.width, y - row.height, x + row.width, y + row.height)
            else:
                text = str(row.CHFCED).strip()
                text_width = max(row.width, 0.65 * len(text) * row.height)
                expected = (x, y - row.height, x + text_width, y + row.height)
            box = struct.unpack_from("<4d", ours, our_sections[3][0] + i * 32)
            assert box == pytest.approx(expected)


def test_polygon_arc_index_matches_native(writer_outputs):
    native, native_sections = _sections(SOURCE / "CWELL_GEO_WP.WP")
    ours, our_sections = _sections(writer_outputs / "cwell_geo.WP")
    native_start, native_size = native_sections[0]
    our_start, our_size = our_sections[0]
    assert our_size == native_size
    assert ours[our_start:our_start + our_size] == native[native_start:native_start + native_size]


def test_native_attribute_declaration_rules(source_layers, writer_outputs):
    for name in LAYER_NAMES:
        reader = Reader(writer_outputs / name, read_graphic_params=False)
        meta = reader.geodataframe.attrs["mapgis_field_meta"]
        fields = meta["fields"]
        raw, sections = _sections(writer_outputs / name)
        attribute_index = 9 if name.endswith(".WP") else 2
        start, _ = sections[attribute_index]
        assert struct.unpack_from("<i", raw, start + 12)[0] == 348 + 39 * len(fields)
        assert struct.unpack_from("<i", raw, start + 16)[0] == len(source_layers[name])
        for field in fields:
            descriptor = meta["raw_descriptors"][field["name"]]
            flags = struct.unpack_from("<i", descriptor, 29)[0]
            if field["name"] in {"长度", "面积", "周长"}:
                assert field["length"] == 15, (name, field)
                assert flags == 518, (name, field)
                continue
            if field["type_code"] == 0:
                assert field["length"] >= 80, (name, field)
            elif field["type_code"] in {3, 5}:
                expected = 8 if field["name"] == "ID" else 20
                assert field["length"] == expected, (name, field)
            expected_flags = 271 if field["type_code"] in {4, 5} else 256
            assert flags == expected_flags, (name, field, flags)


def test_standard_fields_and_native_default_graphics(source_layers, native_default_outputs):
    for name in LAYER_NAMES:
        reader = Reader(native_default_outputs / name, read_graphic_params=True)
        columns = reader.data.columns.tolist()
        if name.endswith(".WT"):
            assert columns[0] == "ID"
            params = reader.point_params
            assert params["point_type"].eq(1).all()
            assert params["symbol_no"].eq(1).all()
            assert params["height"].to_numpy() == pytest.approx(0.1)
            assert params["width"].to_numpy() == pytest.approx(0.1)
            assert params["color"].eq(6).all()
        elif name.endswith(".WL"):
            assert columns[:2] == ["ID", "长度"]
            assert reader.data["长度"].to_numpy() == pytest.approx(
                source_layers[name].geometry.length.to_numpy()
            )
            params = reader.line_params
            assert params["linetype"].eq(1).all()
            assert params["color"].eq(1).all()
            assert params["width"].to_numpy() == pytest.approx(0.05)
            assert params["aux_flag"].eq(1).all()
            assert params["layer"].eq(0).all()
        else:
            assert columns[:3] == ["ID", "面积", "周长"]
            assert reader.polygon_params.iloc[0]["class"] == 2
            assert reader.polygon_params["fill_color"].head(3).tolist() == [2, 3, 4]
            assert reader.polygon_params.iloc[-2]["fill_color"] == 194


def test_fresh_header_stamp_bytes_are_zero(writer_outputs):
    for name in LAYER_NAMES:
        raw = (writer_outputs / name).read_bytes()
        assert [raw[i] for i in (91, 92, 99, 100, 107, 108)] == [0] * 6
