"""Regression tests for the standalone verification script."""

import pytest

from pymapgis.testing import testdata_path as bundled_data_path
from verify_pymapgis import roundtrip_file


@pytest.mark.parametrize(
    ("filename", "expected_count"),
    [
        ("LDZOFBA016.WT", 23),
        ("LDZOFBB002.WP", 9),
    ],
)
def test_roundtrip_compares_default_utm_conversion_in_source_crs(
    tmp_path, filename, expected_count
):
    """Default UTM conversion must not be mistaken for coordinate corruption."""
    result = roundtrip_file(str(bundled_data_path(filename)), tmp_path)

    assert result["ok"], result.get("error")
    assert result["count"] == expected_count
