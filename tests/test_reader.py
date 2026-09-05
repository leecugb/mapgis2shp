"""Integration tests for Reader against real MapGIS files."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest

from pymapgis import POINT_TYPE_SYMBOL, POINT_TYPE_TEXT, InvalidFileError, Reader


class TestReaderPoint:
    @pytest.mark.integration
    def test_reads_points(self, sample_wt: Path, baseline: dict) -> None:
        with Reader(sample_wt) as reader:
            assert reader.shapeType == "POINT"
            assert len(reader) > 0
            assert len(reader.geodataframe) == len(reader)
            assert reader.geodataframe.is_valid.all()

            expected = baseline.get(sample_wt.name, {})
            if "count" in expected:
                assert len(reader) == expected["count"]

    def test_make_valid_does_not_affect_points(self, sample_wt: Path) -> None:
        with Reader(sample_wt, make_valid=False) as r1, Reader(sample_wt, make_valid=True) as r2:
            assert len(r1.geodataframe) == len(r2.geodataframe)


class TestReaderLine:
    @pytest.mark.integration
    def test_reads_lines(self, sample_wl: Path, baseline: dict) -> None:
        with Reader(sample_wl) as reader:
            assert reader.shapeType == "LINE"
            assert len(reader) > 0
            assert (reader.geodataframe.geom_type == "LineString").all()
            assert reader.geodataframe.is_valid.all()

            expected = baseline.get(sample_wl.name, {})
            if "count" in expected:
                assert len(reader) == expected["count"]


class TestReaderPolygon:
    @pytest.mark.integration
    def test_reads_polygons(self, sample_wp: Path, baseline: dict) -> None:
        with Reader(sample_wp) as reader:
            assert reader.shapeType == "POLYGON"
            assert len(reader) > 0
            assert reader.geodataframe.is_valid.all()

            expected = baseline.get(sample_wp.name, {})
            if "count" in expected:
                assert len(reader) == expected["count"]

    @pytest.mark.integration
    def test_make_valid_false_may_be_invalid(self, sample_wp: Path) -> None:
        with Reader(sample_wp, make_valid=False) as reader:
            # Some files contain self-intersecting reconstructed polygons.
            assert len(reader) > 0

    @pytest.mark.integration
    def test_geom_matches_geodataframe(self, sample_wp: Path) -> None:
        with Reader(sample_wp) as reader:
            for g, h in zip(reader.geom, reader.geodataframe.geometry):
                assert g.equals(h)


class TestReaderErrors:
    def test_invalid_file(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.wp"
        bad.write_text("not a mapgis file")
        with pytest.raises(InvalidFileError):
            Reader(bad)

    def test_to_file_roundtrip(self, sample_wt: Path, tmp_path: Path) -> None:
        output = tmp_path / "out.geojson"
        with Reader(sample_wt) as reader:
            count = len(reader)
            reader.to_file(output, driver="GeoJSON")

        gdf = gpd.read_file(output)
        assert len(gdf) == count


class TestReaderAttributes:
    @pytest.mark.integration
    def test_fields_non_empty(self, sample_wt: Path) -> None:
        with Reader(sample_wt) as reader:
            assert len(reader.fields) > 0
            assert len(reader.data.columns) > 0

    @pytest.mark.integration
    def test_crs_detected(self, sample_wt: Path) -> None:
        with Reader(sample_wt) as reader:
            # All sample files in the test suite have a detectable CRS.
            assert reader.crs is not None and reader.crs != ""

    @pytest.mark.integration
    def test_bbox_matches_dataframe(self, sample_wt: Path) -> None:
        with Reader(sample_wt) as reader:
            bounds = reader.geodataframe.bounds
            expected = np.array([
                bounds.minx.min(),
                bounds.miny.min(),
                bounds.maxx.max(),
                bounds.maxy.max(),
            ])
            assert np.allclose(reader.bbox, expected)

    @pytest.mark.integration
    def test_point_attribute_integrity(self) -> None:
        """Verify decoded point attributes match known values from LDLYAAI002.WT."""
        path = Path("LDLYAAI002.WT")
        if not path.exists():
            pytest.skip("LDLYAAI002.WT not found")

        with Reader(path) as reader:
            assert reader.shapeType == "POINT"
            assert [name for name, _, _ in reader.fields] == [
                "ID", "FEATUREID", "CHFCAC", "CODE", "GB", "TN", "NAME"
            ]
            assert len(reader.data) == 242
            # Known first three rows.
            assert reader.data.iloc[0]["ID"] == 915
            assert reader.data.iloc[0]["FEATUREID"] == "YAAI002C1AJ430010020000251"
            assert reader.data.iloc[0]["CHFCAC"] == "000251"
            assert reader.data.iloc[1]["ID"] == 916
            assert reader.data.iloc[2]["FEATUREID"] == "YAAI002C1AJ430010020000253"

    @pytest.mark.integration
    def test_line_attribute_integrity(self) -> None:
        """Verify decoded line attributes match known values from LDLYAAE001.WL."""
        path = Path("LDLYAAE001.WL")
        if not path.exists():
            pytest.skip("LDLYAAE001.WL not found")

        with Reader(path) as reader:
            assert reader.shapeType == "LINE"
            field_names = [name for name, _, _ in reader.fields]
            assert "ID" in field_names
            assert "长度" in field_names
            assert "FEATUREID" in field_names
            assert len(reader.data) == 1143
            # Known first row.
            assert reader.data.iloc[0]["ID"] == 1
            assert reader.data.iloc[0]["FEATUREID"] == "YAAE001C1AJ430010020000001"
            assert reader.data.iloc[0]["CHFCAC"] == "000001"
            assert reader.data.iloc[2]["NAME"] == "吉根河"


class TestPointParams:
    """Graphic-parameter area decoding for .wt files (read_point_params=True)."""

    @pytest.mark.integration
    def test_default_off(self, sample_wt: Path) -> None:
        with Reader(sample_wt) as reader:
            assert reader.point_params.empty
            assert "angle" not in reader.geodataframe.columns

    @pytest.mark.integration
    def test_params_decode(self) -> None:
        """LDZOFBB099.WT: mixed text/symbol annotation layer with known values."""
        path = Path("LDZOFBB099.WT")
        if not path.exists():
            pytest.skip("LDZOFBB099.WT not found")

        with Reader(path, read_point_params=True) as reader:
            pp = reader.point_params
            assert list(pp.columns) == [
                "point_type", "symbol_no", "height", "width", "spacing", "angle"
            ]
            assert len(pp) == 2024
            # 276 symbol points (220 fault-aux + 27 fossil + 21 mud-volcano
            # + 8 fold-aux); the remaining 1748 are text annotations.
            assert (pp["point_type"] == POINT_TYPE_SYMBOL).sum() == 276
            assert (pp["point_type"] == POINT_TYPE_TEXT).sum() == 1748
            # Columns are joined into the GeoDataFrame as well.
            assert "angle" in reader.geodataframe.columns
            assert len(reader.geodataframe) == 2024

            # Row 0 is the text annotation "C#-1": 2.5 x 2.5 mm, spacing 0.2.
            row0 = pp.iloc[0]
            assert row0["point_type"] == POINT_TYPE_TEXT
            assert row0["symbol_no"] == 0
            assert row0["height"] == pytest.approx(2.5, abs=0.01)
            assert row0["width"] == pytest.approx(2.5, abs=0.01)
            assert row0["spacing"] == pytest.approx(0.2, abs=0.01)
            assert 0.0 <= row0["angle"] < 1.0  # near-horizontal text

            # Row 1669 is a fault-auxiliary symbol point: subgraph 1281,
            # ~1 x 1 mm, rotated parallel to the fault strike.
            row = pp.iloc[1669]
            assert row["point_type"] == POINT_TYPE_SYMBOL
            assert row["symbol_no"] == 1281
            assert row["height"] == pytest.approx(1.0, abs=0.01)
            assert row["width"] == pytest.approx(1.0, abs=0.01)
            assert np.isnan(row["spacing"])
            assert row["angle"] == pytest.approx(231.55, abs=0.01)

    @pytest.mark.integration
    def test_all_text_layer(self) -> None:
        """LDLYAAI002.WT is a pure text-annotation layer."""
        path = Path("LDLYAAI002.WT")
        if not path.exists():
            pytest.skip("LDLYAAI002.WT not found")

        with Reader(path, read_point_params=True) as reader:
            pp = reader.point_params
            assert len(pp) == 242
            assert (pp["point_type"] == POINT_TYPE_TEXT).all()
            assert (pp["symbol_no"] == 0).all()
            assert (pp["height"] > 0).all()
            assert (pp["spacing"] >= 0).all()

    @pytest.mark.integration
    def test_all_symbol_layer(self) -> None:
        """LDZOFBA016.WT (attitude points): 305 symbol points, 5 mm glyphs."""
        path = Path("LDZOFBA016.WT")
        if not path.exists():
            pytest.skip("LDZOFBA016.WT not found")

        with Reader(path, read_point_params=True) as reader:
            pp = reader.point_params
            assert len(pp) == 305
            assert (pp["point_type"] == POINT_TYPE_SYMBOL).all()
            assert (pp["symbol_no"] > 0).all()
            assert pp["height"].values == pytest.approx(5.0, abs=0.01)
            assert ((pp["angle"] >= 0) & (pp["angle"] < 360)).all()

    @pytest.mark.integration
    def test_ignored_for_non_point(self, sample_wl: Path) -> None:
        with Reader(sample_wl, read_point_params=True) as reader:
            assert reader.shapeType == "LINE"
            assert reader.point_params.empty
            assert "angle" not in reader.geodataframe.columns


class TestLineParams:
    """Line graphic parameters (read_graphic_params=True, .wl files)."""

    @pytest.mark.integration
    def test_default_off(self, sample_wl: Path) -> None:
        with Reader(sample_wl) as reader:
            assert reader.line_params.empty
            assert "width" not in reader.geodataframe.columns

    @pytest.mark.integration
    def test_fault_widths_and_linetypes(self) -> None:
        """LDZOFBA003.WT fault layer: width follows magnitude, linetype style."""
        path = Path("LDZOFBA003.WL")
        if not path.exists():
            pytest.skip("LDZOFBA003.WL not found")

        with Reader(path, read_graphic_params=True) as reader:
            lp = reader.line_params
            assert list(lp.columns) == [
                "linetype", "aux_linetype", "width", "x_coef", "y_coef"
            ]
            assert len(lp) == 310
            assert "width" in reader.geodataframe.columns

            gdf = reader.geodataframe
            gz = gdf["GZEEB"].astype(str)
            # Boundary faults (41) are thickest, regional faults (28) next.
            assert gdf.loc[gz == "41", "width"].round(2).eq(0.8).all()
            assert gdf.loc[gz == "28", "width"].round(2).eq(0.5).all()
            # Inferred faults (04) use dashed style 2; revived faults (31)
            # style 18; nappe boundaries (07) style 38.
            assert (gdf.loc[gz == "04", "linetype"] == 2).all()
            assert (gdf.loc[gz == "31", "linetype"] == 18).all()
            assert (gdf.loc[gz == "07", "linetype"] == 38).all()
            # Pattern coefficients are positive and of dash-pattern scale.
            assert (lp["x_coef"] > 0).all()
            assert (lp["y_coef"] > 0).all()

    @pytest.mark.integration
    def test_river_linetypes(self) -> None:
        """LDLYAAE001.WL: rivers solid (1), seasonal rivers / ice dashed (2)."""
        path = Path("LDLYAAE001.WL")
        if not path.exists():
            pytest.skip("LDLYAAE001.WL not found")

        with Reader(path, read_graphic_params=True) as reader:
            gdf = reader.geodataframe
            gb = gdf["GB"].astype(str)
            assert (gdf.loc[gb == "21010", "linetype"] == 1).all()
            assert (gdf.loc[gb == "21021", "linetype"] == 2).all()
            assert (gdf.loc[gb == "73020", "linetype"] == 2).all()
            assert gdf["width"].between(0.05, 0.25).all()


class TestPolygonParams:
    """Polygon graphic parameters from the head_9 section (.wp files)."""

    @pytest.mark.integration
    def test_default_off(self, sample_wp: Path) -> None:
        with Reader(sample_wp) as reader:
            assert reader.polygon_params.empty
            assert "pattern" not in reader.geodataframe.columns

    @pytest.mark.integration
    def test_pattern_clusters_by_rock_category(self) -> None:
        """Fill-pattern numbers cluster by layer: sedimentary ~3900,
        intrusive 384-388, metamorphic 751-758."""
        for fname, lo, hi in [
            ("LDZOFBB001.WP", 3866, 3931),
            ("LDZOFBB003.WP", 384, 388),
            ("LDZOFBB004.WP", 751, 758),
        ]:
            path = Path(fname)
            if not path.exists():
                pytest.skip(f"{fname} not found")
            with Reader(path, read_graphic_params=True) as reader:
                pp = reader.polygon_params
                assert list(pp.columns) == ["fill_color", "pattern", "pattern_color"]
                assert len(pp) == len(reader.geodataframe)
                assert pp["pattern"].between(lo, hi).all(), fname
                # Colour indices vary between geological units.
                assert pp["fill_color"].nunique() > 1

    @pytest.mark.integration
    def test_params_align_with_filtered_polygons(self) -> None:
        """head_9 rows align with active polygon IDs after ID filtering."""
        path = Path("LDZOFBB003.WP")
        if not path.exists():
            pytest.skip("LDZOFBB003.WP not found")
        with Reader(path, read_graphic_params=True) as reader:
            gdf = reader.geodataframe
            assert len(gdf) == 46
            # Patterned intrusive bodies carry non-zero pattern params;
            # every row must have a pattern in the intrusive range.
            assert gdf["pattern"].between(384, 388).all()
