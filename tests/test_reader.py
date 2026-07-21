"""Integration tests for Reader against real MapGIS files."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest

from pymapgis import InvalidFileError, Reader


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
