import json
import subprocess
import sys
from pathlib import Path

import pytest
from osgeo import osr

from pymapgis.geopdf import inspect_geopdf
from pymapgis.testing import jwd_path, slib_path

try:
    JWD = jwd_path()
    SLIB = slib_path()
except FileNotFoundError as exc:
    pytest.skip(str(exc), allow_module_level=True)


def test_real_jwd_default_gauss_kruger_geopdf(tmp_path):
    root = Path(__file__).resolve().parents[1]
    command = [
        sys.executable,
        str(root / "examples/render_bundled_jwd.py"),
        "--input-dir",
        str(JWD),
        "--slib-dir",
        str(SLIB),
        "--output-dir",
        str(tmp_path),
        "--legacy-label-layout",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=600)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads((tmp_path / "jwd_render_reports.json").read_text(encoding="utf-8"))
    rendering = report["rendering"]
    assert rendering["target_source"] == "default_gauss_kruger"
    assert rendering["central_meridian"] == 75.0
    assert rendering["zone_width"] == 6
    assert rendering["scale_denominator"] == 250000
    assert rendering["datum_policy"] == "preserve_source"
    assert rendering["label_layout"]["mode"] == "legacy"
    assert rendering["label_layout"]["attitude_dip_source"] == "native_annotations"
    assert report["summary"]["layers"] == 12
    assert report["summary"]["drawn"] == 5732
    assert report["summary"]["polygon_labels"] == 713
    assert sum(item.get("symbols", 0) for item in report["layers"]) == 581
    assert report["summary"]["unknown_colour_occurrences"] == 0
    assert report["summary"]["unresolved_symbols"] == 0
    assert report["summary"]["geopdf_actual_scale_x"] == pytest.approx(250000)
    assert report["summary"]["geopdf_actual_scale_y"] == pytest.approx(250000)
    assert report["summary"]["geopdf_image_objects"] == 0
    assert len(report["sources"]) == 12
    assert all(len(item["sha256"]) == 64 for item in report["sources"])
    assert all(item["native_map_scale_at_byte_143"] is not None for item in report["sources"])
    assert sum(
        item.get("pattern", 0) for item in report["layers"] if item["kind"] == "wp"
    ) == 165
    assert sum(item.get("pattern_too_large", 0) for item in report["layers"]) == 0
    assert sum(item.get("pattern_unresolved", 0) for item in report["layers"]) == 0
    assert rendering["output_policy"] == {
        "preview_formats": ["png", "svg"],
        "formal_pdf": "strict_scale_geopdf",
        "ordinary_pdf": False,
    }
    assert not (tmp_path / "jwd_map.pdf").exists()

    geopdf = tmp_path / "jwd_map_geopdf.pdf"
    readback = inspect_geopdf(geopdf)
    assert readback["encoding"] == "ISO32000"
    assert readback["image_count"] == 0
    assert readback["image_xobject_count"] == 0
    assert readback["drawing_count"] > 0
    assert readback["text_character_count"] > 0
    assert not (tmp_path / "jwd_map_geopdf_source.png").exists()
    assert "/Type /Viewport" in readback["viewport_object"]
    assert "/Subtype /GEO" in readback["measure_object"]
    assert "/Type /PROJCS" in readback["gcs_object"]
    spatial_ref = osr.SpatialReference()
    assert spatial_ref.ImportFromWkt(readback["wkt"]) == 0
    assert spatial_ref.GetProjParm("central_meridian") == 75.0
    assert spatial_ref.GetProjParm("scale_factor") == 1.0
    assert spatial_ref.GetTOWGS84()[:3] == (15.8, -154.4, -82.3)

    longitudes = readback["gpts"][1::2]
    latitudes = readback["gpts"][0::2]
    xmin, ymin, xmax, ymax = rendering["geographic_bounds"]
    assert min(longitudes) <= xmin
    assert max(longitudes) >= xmax
    assert min(latitudes) <= ymin
    assert max(latitudes) >= ymax

    geopdf_info = rendering["geopdf"]
    assert geopdf_info["content_mode"] == "vector"
    assert geopdf_info["scale_denominator"] == 250000
    assert geopdf_info["scale_policy"] == "axes_page_size_from_ground_extent"
    actual_x_scale = (
        abs(geopdf_info["page_transform"][1])
        * geopdf_info["page_width_pt"]
        * geopdf_info["metres_per_unit"]
        / (geopdf_info["page_width_mm"] / 1000.0)
    )
    actual_y_scale = (
        abs(geopdf_info["page_transform"][5])
        * geopdf_info["page_height_pt"]
        * geopdf_info["metres_per_unit"]
        / (geopdf_info["page_height_mm"] / 1000.0)
    )
    assert actual_x_scale == pytest.approx(250000, rel=1e-9)
    assert actual_y_scale == pytest.approx(250000, rel=1e-9)
    assert readback["page_width_pt"] == pytest.approx(
        geopdf_info["page_width_mm"] * 72.0 / 25.4
    )
    assert readback["page_height_pt"] == pytest.approx(
        geopdf_info["page_height_mm"] * 72.0 / 25.4
    )
