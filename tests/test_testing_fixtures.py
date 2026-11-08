# SPDX-License-Identifier: Apache-2.0
"""Public access to installed and source fixture datasets."""
from pymapgis.testing import fixture_path, jwd_path, slib_path


def test_fixture_access_api_and_dataset_inventory():
    assert fixture_path("fixture_manifest.json").is_file()
    assert fixture_path("jwd_slib_manifest.json").is_file()
    assert fixture_path("writer_batch2_manifest.json").is_file()
    assert fixture_path("writer_batch3_manifest.json").is_file()
    assert len(list(fixture_path("writer_batch2").glob("*.shp"))) == 11
    assert len(list(fixture_path("writer_batch3").glob("*.shp"))) == 12
    assert len(list(jwd_path().iterdir())) == 12
    assert all(path.suffix.lower() in {".wt", ".wl", ".wp"} for path in jwd_path().iterdir())
    assert len(list(slib_path().iterdir())) == 5
    assert (jwd_path() / "LDLYAAE002.WP").is_file()
    assert (slib_path() / "Pcolor.lib").is_file()
    assert (fixture_path("mapgis") / "synthetic_points.wt").is_file()
    assert (fixture_path("mapgis") / "synthetic_lines.wl").is_file()
    assert (fixture_path("mapgis") / "synthetic_polygons.wp").is_file()
