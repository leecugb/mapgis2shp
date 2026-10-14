"""Round-trip tests for the MapGIS writer (GeoDataFrame -> .w? -> Reader)."""

from __future__ import annotations

import datetime
import struct

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely.geometry

from pymapgis import Reader, Writer, WriterError, write
from pymapgis.cli import main as cli_main
from pymapgis.reader import _read_polygon_arcs, _read_topology_table


def _write_and_read(gdf: gpd.GeoDataFrame, path, reader_kwargs=None, **kwargs) -> Reader:
    Writer(gdf, **kwargs).to_file(path)
    return Reader(path, **(reader_kwargs or {}))


def _sample_point_gdf() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "ID": pd.array([1, 2], dtype="int32"),
            "名称": ["吉根河", None],
            "DEPTH": pd.array([12.5, np.nan], dtype="float64"),
            "日期": pd.to_datetime(["2020-01-02", None]),
        },
        geometry=[shapely.geometry.Point(73.5, 39.5), shapely.geometry.Point(74.1, 39.9)],
        crs="EPSG:4326",
    )


class TestPointWriter:
    def test_roundtrip_attributes_and_coords(self, tmp_path) -> None:
        gdf = _sample_point_gdf()
        reader = _write_and_read(gdf, tmp_path / "out.wt")
        assert len(reader) == 2
        assert reader.shapeType == "POINT"
        xs = sorted(geom.x for geom in reader.geom)
        assert xs == pytest.approx([73.5, 74.1])
        data = reader.data
        assert data.iloc[0]["ID"] == 1
        assert data.iloc[0]["名称"] == "吉根河"
        assert data.iloc[1]["名称"] == ""
        assert np.isnan(data.iloc[1]["DEPTH"])
        assert data.iloc[0]["日期"] == datetime.date(2020, 1, 2)
        assert data.iloc[1]["日期"] is None

    def test_point_params_fidelity(self, tmp_path) -> None:
        gdf = gpd.GeoDataFrame(
            {
                "point_type": [1, 1],
                "symbol_no": [1281, 1894],
                "height": [2.0, 2.5],
                "width": [1.5, 2.0],
                "spacing": [np.nan, np.nan],
                "angle": [45.0, 90.0],
            },
            geometry=[shapely.geometry.Point(0, 0), shapely.geometry.Point(1, 1)],
            crs="EPSG:4326",
        )
        reader = _write_and_read(gdf, tmp_path / "out.wt", {"read_point_params": True})
        params = reader.point_params
        assert params["symbol_no"].tolist() == [1281, 1894]
        assert params["height"].tolist() == pytest.approx([2.0, 2.5], abs=1e-4)
        assert params["angle"].tolist() == pytest.approx([45.0, 90.0], abs=1e-4)
        # Consumed param columns must not leak into the attribute table.
        assert "symbol_no" not in reader.data.columns

    def test_text_point_layout(self, tmp_path) -> None:
        gdf = gpd.GeoDataFrame(
            {
                "point_type": [0],
                "symbol_no": [0],
                "height": [3.0],
                "width": [2.0],
                "spacing": [0.5],
                "angle": [10.0],
            },
            geometry=[shapely.geometry.Point(0, 0)],
            crs="EPSG:4326",
        )
        reader = _write_and_read(gdf, tmp_path / "out.wt", {"read_point_params": True})
        params = reader.point_params.iloc[0]
        assert params["point_type"] == 0
        assert params["height"] == pytest.approx(3.0, abs=1e-4)
        assert params["width"] == pytest.approx(2.0, abs=1e-4)
        assert params["spacing"] == pytest.approx(0.5, abs=1e-4)

    def test_multipoint_explodes(self, tmp_path) -> None:
        gdf = gpd.GeoDataFrame(
            {"v": [1]},
            geometry=[shapely.geometry.MultiPoint([(0, 0), (1, 1)])],
            crs="EPSG:4326",
        )
        with pytest.warns(UserWarning):
            reader = _write_and_read(gdf, tmp_path / "out.wt")
        assert len(reader) == 2
        assert reader.data["v"].tolist() == [1, 1]


class TestLineWriter:
    def test_roundtrip(self, tmp_path) -> None:
        gdf = gpd.GeoDataFrame(
            {"名称": ["断层一"], "GZEEB": ["05"]},
            geometry=[shapely.geometry.LineString([(73.0, 39.0), (73.1, 39.1), (73.2, 39.05)])],
            crs="EPSG:4326",
        )
        reader = _write_and_read(gdf, tmp_path / "out.wl")
        assert len(reader) == 1
        assert reader.shapeType == "LINE"
        assert reader.data.iloc[0]["名称"] == "断层一"
        coords = list(reader.geom[0].coords)
        assert coords[0] == pytest.approx((73.0, 39.0))
        assert coords[2] == pytest.approx((73.2, 39.05))

    def test_line_params_fidelity(self, tmp_path) -> None:
        gdf = gpd.GeoDataFrame(
            {
                "linetype": [3],
                "aux_linetype": [2],
                "color": [5],
                "width": [0.35],
                "x_coef": [5.0],
                "y_coef": [4.0],
            },
            geometry=[shapely.geometry.LineString([(0, 0), (1, 1)])],
            crs="EPSG:4326",
        )
        reader = _write_and_read(gdf, tmp_path / "out.wl", {"read_graphic_params": True})
        params = reader.line_params.iloc[0]
        assert params["linetype"] == 3
        assert params["aux_linetype"] == 2
        assert params["color"] == 5
        assert params["width"] == pytest.approx(0.35, abs=1e-4)
        assert params["y_coef"] == pytest.approx(4.0, abs=1e-4)
        assert "linetype" not in reader.data.columns

    def test_multilinestring_explodes(self, tmp_path) -> None:
        gdf = gpd.GeoDataFrame(
            {"v": [7]},
            geometry=[
                shapely.geometry.MultiLineString([[(0, 0), (1, 1)], [(2, 2), (3, 3)]])
            ],
            crs="EPSG:4326",
        )
        with pytest.warns(UserWarning):
            reader = _write_and_read(gdf, tmp_path / "out.wl")
        assert len(reader) == 2
        assert reader.data["v"].tolist() == [7, 7]


class TestPolygonWriter:
    def test_shared_boundary_roundtrip(self, tmp_path) -> None:
        p1 = shapely.geometry.box(0, 0, 1, 1)
        p2 = shapely.geometry.box(1, 0, 2, 1)
        gdf = gpd.GeoDataFrame(
            {"QDUECC": ["C1y", "C2ak"]}, geometry=[p1, p2], crs="EPSG:4326"
        )
        path = tmp_path / "out.wp"
        reader = _write_and_read(gdf, path)
        assert len(reader) == 2
        assert reader.shapeType == "POLYGON"
        assert reader.data["QDUECC"].tolist() == ["C1y", "C2ak"]
        total = sum(g.area for g in reader.geom)
        assert total == pytest.approx(2.0)
        assert reader.geom[0].union(reader.geom[1]).area == pytest.approx(2.0)

        # The shared edge must be stored as ONE arc with left/right = (1, 2).
        with open(path, "rb") as f:
            data_start = struct.unpack_from("<i", f.read(16), 12)[0]
            f.seek(data_start)
            entries = []
            for _ in range(10):
                entries.append(struct.unpack("<2i", f.read(10)[:8]))
        with open(path, "rb") as f:
            arcs = _read_polygon_arcs(
                f, *entries[0], *entries[1], 1.0
            )
            f.seek(0)
            topo = _read_topology_table(f, *entries[3])
        shared = [t for t in topo if t[2] == 1 and t[3] == 2]
        assert len(arcs) == 5
        assert len(shared) == 1

    def test_hole_and_island(self, tmp_path) -> None:
        outer = shapely.geometry.Polygon(
            [(0, 0), (6, 0), (6, 6), (0, 6), (0, 0)],
            [[(1, 1), (5, 1), (5, 5), (1, 5), (1, 1)]],
        )
        island = shapely.geometry.box(2, 2, 4, 4)
        gdf = gpd.GeoDataFrame(
            {"n": [1, 2]}, geometry=[outer, island], crs="EPSG:4326"
        )
        reader = _write_and_read(gdf, tmp_path / "out.wp")
        assert len(reader) == 2
        areas = sorted(g.area for g in reader.geom)
        assert areas == pytest.approx([4.0, 20.0])

    def test_multipolygon_stays_single_feature(self, tmp_path) -> None:
        mp = shapely.geometry.MultiPolygon(
            [shapely.geometry.box(0, 0, 1, 1), shapely.geometry.box(2, 2, 3, 3)]
        )
        gdf = gpd.GeoDataFrame({"n": [1]}, geometry=[mp], crs="EPSG:4326")
        reader = _write_and_read(gdf, tmp_path / "out.wp")
        assert len(reader) == 1
        assert reader.geom[0].area == pytest.approx(2.0)
        assert reader.geom[0].geom_type == "MultiPolygon"

    def test_invalid_polygon_repaired(self, tmp_path) -> None:
        bowtie = shapely.geometry.Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
        gdf = gpd.GeoDataFrame({"n": [1]}, geometry=[bowtie], crs="EPSG:4326")
        reader = _write_and_read(gdf, tmp_path / "out.wp")
        assert len(reader) == 1
        assert reader.geom[0].area == pytest.approx(2.0)

    def test_polygon_params_fidelity(self, tmp_path) -> None:
        # Native head_9 stores fill/pattern/pattern colour as single bytes
        # at @5/@6/@9, so all values must fit in 0..255.
        gdf = gpd.GeoDataFrame(
            {"fill_color": [35], "pattern": [26], "pattern_color": [6]},
            geometry=[shapely.geometry.box(0, 0, 1, 1)],
            crs="EPSG:4326",
        )
        reader = _write_and_read(gdf, tmp_path / "out.wp", {"read_graphic_params": True})
        params = reader.polygon_params.iloc[0]
        assert params["fill_color"] == 35
        assert params["pattern"] == 26
        assert params["pattern_color"] == 6
        assert "fill_color" not in reader.data.columns

    def test_polygon_area_conservation_real(self, tmp_path, sample_wp) -> None:
        with Reader(sample_wp, read_graphic_params=True) as source:
            gdf = source.geodataframe
        path = tmp_path / "out.wp"
        with _write_and_read(gdf, path) as reader:
            assert len(reader) == len(gdf)
            assert sum(g.area for g in reader.geom) == pytest.approx(
                gdf.geometry.area.sum(), rel=1e-9
            )
            src_bounds = gdf.total_bounds
            assert np.allclose(reader.bbox, src_bounds, atol=1e-9)
            if len(reader.polygon_params):
                assert reader.polygon_params["pattern"].tolist() == (
                    gdf["pattern"].tolist()
                )


class TestCrsAndErrors:
    def test_tmerc_roundtrip(self, tmp_path) -> None:
        crs = (
            "+proj=tmerc +lat_0=0 +lon_0=75 +k=1 +x_0=500000 +y_0=0 "
            "+ellps=krass +units=m +no_defs"
        )
        gdf = gpd.GeoDataFrame(
            {"n": [1]},
            geometry=[shapely.geometry.Point(500100.0, 4375000.0)],
            crs=crs,
        )
        reader = _write_and_read(gdf, tmp_path / "out.wt", map_scale=1000.0)
        assert reader.geom[0].x == pytest.approx(500100.0, abs=1e-6)
        assert reader.geom[0].y == pytest.approx(4375000.0, abs=1e-6)

    def test_suffix_mismatch_message(self, tmp_path) -> None:
        gdf = _sample_point_gdf()
        with pytest.raises(WriterError, match="requires a .wt output file"):
            Writer(gdf).to_file(tmp_path / "out.wp")

    def test_mixed_geometry_raises(self) -> None:
        gdf = gpd.GeoDataFrame(
            {"n": [1, 2]},
            geometry=[
                shapely.geometry.Point(0, 0),
                shapely.geometry.LineString([(0, 0), (1, 1)]),
            ],
            crs="EPSG:4326",
        )
        with pytest.raises(WriterError, match="mixed geometry"):
            Writer(gdf)

    def test_empty_geodataframe_with_explicit_type(self, tmp_path) -> None:
        gdf = gpd.GeoDataFrame(
            {"ID": pd.array([], dtype="int32")},
            geometry=gpd.GeoSeries([], crs="EPSG:4326"),
        )
        reader = _write_and_read(gdf, tmp_path / "out.wt", geometry_type="POINT")
        assert len(reader) == 0

    def test_unsupported_projection(self, tmp_path) -> None:
        gdf = gpd.GeoDataFrame(
            {"n": [1]},
            geometry=[shapely.geometry.Point(0, 0)],
            crs="+proj=merc +datum=WGS84 +units=m +no_defs",
        )
        with pytest.raises(WriterError, match="unsupported projection"):
            Writer(gdf).to_file(tmp_path / "out.wt")

    def test_write_convenience_function(self, tmp_path) -> None:
        path = tmp_path / "out.wt"
        writer = write(_sample_point_gdf(), path)
        assert isinstance(writer, Writer)
        assert len(Reader(path)) == 2


class TestShpIntermediary:
    def test_mapgis_shp_mapgis(self, tmp_path, sample_wt) -> None:
        """mapgis -> shp -> mapgis must preserve count/bbox and point params."""
        with Reader(sample_wt, read_graphic_params=True) as source:
            gdf = source.geodataframe
        shp_path = tmp_path / "mid.shp"
        gdf.to_file(shp_path)
        back = gpd.read_file(shp_path)
        # Point param columns are all <= 10 chars, so shapefile keeps them.
        out = tmp_path / "out.wt"
        with _write_and_read(back, out, {"read_point_params": True}) as reader:
            assert len(reader) == len(gdf)
            assert np.allclose(reader.bbox, gdf.total_bounds, atol=1e-9)
            if len(reader.point_params):
                assert reader.point_params["symbol_no"].tolist() == (
                    gdf["symbol_no"].tolist()
                )

    def test_cli_shp_to_wp(self, tmp_path) -> None:
        gdf = gpd.GeoDataFrame(
            {"n": [1]}, geometry=[shapely.geometry.box(0, 0, 1, 1)], crs="EPSG:4326"
        )
        shp_path = tmp_path / "in.shp"
        gdf.to_file(shp_path)
        out = tmp_path / "out.wp"
        assert cli_main([str(shp_path), str(out)]) == 0
        with Reader(out) as reader:
            assert len(reader) == 1
            assert reader.geom[0].area == pytest.approx(1.0)

    def test_cli_mapgis_direction_unchanged(self, tmp_path, sample_wl) -> None:
        out = tmp_path / "out.geojson"
        assert cli_main([str(sample_wl), str(out)]) == 0
        assert out.exists()
