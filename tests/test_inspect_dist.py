"""Release-boundary tests for allowed USGS/SLIB and forbidden NGAC content."""
import hashlib
import json

import inspect_dist as inspection
import pytest


def test_processed_usgs_and_authorized_slib_are_allowed():
    names = [
        "pkg/pymapgis/testing/fixtures/testdata/LDZOFBA002.WL",
        "pkg/pymapgis/testing/fixtures/testdata/LDZOFBB001.WP",
        "pkg/tests/fixtures/testdata/LDZOFBA016.WT",
        "pkg/pymapgis/testing/fixtures/slib/Subgraph.lib",
        "pkg/tests/fixtures/slib/Colorlib.lib",
    ]
    inspection._check_common(names, "allowed.zip", allow_slib_fixtures=True)


@pytest.mark.parametrize("path", [
    "pkg/tests/fixtures/jwd/LDZOFBA002.WL",
    "pkg/pymapgis/testing/fixtures/jwd/LDZOFBB001.WP",
    "pkg/tests/fixtures/reader_native/LDZOFBA002.SHP",
    "pkg/pymapgis/testing/fixtures/reader_native/LDZOFBA002.DBF",
])
def test_original_ngac_paths_remain_forbidden(path):
    with pytest.raises(RuntimeError, match="original NGAC data"):
        inspection._check_common([path], "forbidden.zip", allow_slib_fixtures=True)


def test_optional_usgs_native_comparison_is_not_in_clean_package():
    path = "pkg/tests/fixtures/usgs_conejo/native/CWELL_GEO_WP.WP"
    with pytest.raises(RuntimeError, match="optional USGS native comparison"):
        inspection._check_common([path], "optional.zip", allow_slib_fixtures=True)


def test_slib_outside_authorized_fixture_path_is_rejected():
    with pytest.raises(RuntimeError, match="outside the test fixture directory"):
        inspection._check_common(
            ["pkg/pymapgis/Subgraph.lib"], "outside.whl", allow_slib_fixtures=True
        )


def test_forbidden_content_is_detected_after_renaming(monkeypatch):
    payload = b"stand-in for a forbidden native vector"
    digest = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(
        inspection, "_forbidden_hashes", lambda: {digest: "forbidden original"}
    )
    with pytest.raises(RuntimeError, match="disguised under another name"):
        inspection._check_member_hash("allowed-looking-name.wt", payload, "renamed.whl")


def test_allowed_fixture_hashes_do_not_overlap_ngac_hash_registry():
    fixture_root = inspection.Path(__file__).parent / "fixtures"
    forbidden = inspection._forbidden_hashes()
    testdata = json.loads(
        (fixture_root / "testdata/manifest.json").read_text(encoding="utf-8")
    )
    slib = json.loads(
        (fixture_root / "slib/manifest.json").read_text(encoding="utf-8")
    )
    allowed = {
        item["sha256"].lower() for item in testdata["vectors"].values()
    } | {
        item["sha256"].lower() for item in slib["libraries"].values()
    }
    assert not allowed & set(forbidden)
