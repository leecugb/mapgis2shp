# SPDX-License-Identifier: Apache-2.0
"""Tests for the redistributable synthetic MapGIS binary fixtures."""
from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path

import pytest

from pymapgis import Reader, Writer

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mapgis"
MANIFEST_PATH = FIXTURE_DIR.parent / "fixture_manifest.json"
EXPECTED = {
    "synthetic_points.wt": ("POINT", [73.5, 39.5, 74.0, 39.7], 3),
    "synthetic_lines.wl": ("LINE", [73.4, 39.4, 74.0, 39.8], 3),
    "synthetic_polygons.wp": ("POLYGON", [73.4, 39.4, 74.4, 39.7], 4),
}


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("filename", sorted(EXPECTED))
def test_public_mapgis_fixture_manifest_and_reader(filename: str) -> None:
    path = FIXTURE_DIR / filename
    family, bbox, feature_count = EXPECTED[filename]
    record = _manifest()["files"][filename]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]

    with Reader(path, read_graphic_params=True) as reader:
        assert reader.shapeType == family
        assert len(reader) == feature_count
        assert reader.bbox == pytest.approx(bbox)
        assert reader.crs is not None
        assert reader.crs.ellipsoid.name == "WGS 84"
        assert reader.geodataframe.is_valid.all()
        assert set(record["attribute_fields"]) == {field[0] for field in reader.fields}
        assert set(record["graphic_parameter_columns"]).issubset(
            reader.geodataframe.columns
        )


def test_public_fixture_attributes_and_graphic_parameters() -> None:
    with Reader(FIXTURE_DIR / "synthetic_points.wt", read_graphic_params=True) as points:
        assert points.data["NAME"].tolist() == ["产状点A", "产状点B", "产状点C"]
        assert points.data["SURVEY_DATE"].iloc[0] == datetime.date(2026, 1, 1)
        assert points.data["SURVEY_DATE"].iloc[2] is None
        assert points.geodataframe["symbol_no"].tolist() == [1281, 1281, 1281]
        assert points.geodataframe["DIP"].tolist() == [30.0, 45.0, 60.0]

    with Reader(FIXTURE_DIR / "synthetic_lines.wl", read_graphic_params=True) as lines:
        assert lines.data["TYPE"].tolist() == ["boundary", "fault", "river"]
        assert lines.geodataframe["linetype"].tolist() == [1, 2, 1]
        assert lines.geodataframe["width"].tolist() == pytest.approx([0.2, 0.4, 0.2])

    with Reader(FIXTURE_DIR / "synthetic_polygons.wp", read_graphic_params=True) as polygons:
        assert polygons.data["UNIT"].tolist() == ["C1", "C2", "Q", "Q"]
        assert polygons.geodataframe["fill_color"].tolist() == [70, 35, 9, 9]
        assert sum(geom.area for geom in polygons.geodataframe.geometry) == pytest.approx(0.27)
        first, second, with_hole, island = polygons.geodataframe.geometry.tolist()
        assert first.intersection(second).area == pytest.approx(0.0)
        assert first.union(second).area == pytest.approx(0.18)
        assert with_hole.intersection(island).area == pytest.approx(0.0)
        assert with_hole.union(island).area == pytest.approx(0.09)
        assert len(with_hole.geoms) == 1
        assert len(with_hole.geoms[0].interiors) == 1


@pytest.mark.parametrize("filename", sorted(EXPECTED))
def test_public_fixture_reader_writer_reader(filename: str, tmp_path: Path) -> None:
    source_path = FIXTURE_DIR / filename
    with Reader(source_path, read_graphic_params=True) as source:
        frame = source.geodataframe
        expected_bbox = source.bbox
        expected_family = source.shapeType

    output = tmp_path / filename
    Writer(frame).to_file(output)
    with Reader(output, read_graphic_params=True) as rebuilt:
        assert rebuilt.shapeType == expected_family
        assert len(rebuilt) == len(frame)
        assert rebuilt.bbox == pytest.approx(expected_bbox)
        if expected_family == "POLYGON":
            assert sum(geom.area for geom in rebuilt.geodataframe.geometry) == pytest.approx(
                sum(geom.area for geom in frame.geometry)
            )
        elif expected_family == "LINE":
            assert sum(geom.length for geom in rebuilt.geodataframe.geometry) == pytest.approx(
                sum(geom.length for geom in frame.geometry)
            )
