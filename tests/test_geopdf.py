import math
import subprocess
import sys
from pathlib import Path

import pyproj
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from pymapgis.geopdf import (
    inspect_geopdf,
    matplotlib_geotransform,
    write_geopdf,
    write_vector_geopdf,
)
from pymapgis.render_projection import gauss_kruger_crs

pymupdf = pytest.importorskip("pymupdf")
osr = pytest.importorskip("osgeo.osr")

JWD_CRS = "+proj=longlat +ellps=krass +towgs84=15.8,-154.4,-82.3,0,0,0,0 +no_defs"


def make_png(tmp_path):
    figure = Figure(figsize=(4, 3), dpi=100)
    FigureCanvasAgg(figure)
    axes = figure.add_axes([0.1, 0.1, 0.8, 0.8])
    axes.set_xlim(400000, 400400)
    axes.set_ylim(4300000, 4300300)
    path = tmp_path / "map.png"
    figure.savefig(path, dpi=100)
    return figure, axes, path


def test_matplotlib_geotransform_uses_full_canvas_origin(tmp_path):
    figure, axes, _ = make_png(tmp_path)
    gt = matplotlib_geotransform(figure, axes, 100)
    bbox = axes.get_window_extent()
    assert gt[1] == pytest.approx(400 / bbox.width)
    assert gt[5] == pytest.approx(-300 / bbox.height)
    assert gt[0] == pytest.approx(400000 - bbox.x0 * gt[1])
    height_px = 300
    assert gt[3] == pytest.approx(4300300 + (height_px - bbox.y1) * (-gt[5]))


def test_geotransform_scales_figure_display_bbox_to_output_dpi(tmp_path):
    figure, axes, _ = make_png(tmp_path)
    bbox = axes.get_window_extent()
    gt = matplotlib_geotransform(figure, axes, 600)
    output_scale = 6.0
    assert gt[1] == pytest.approx(400 / (bbox.width * output_scale))
    assert gt[5] == pytest.approx(-300 / (bbox.height * output_scale))
    assert gt[0] == pytest.approx(400000 - bbox.x0 * output_scale * gt[1])
    assert gt[3] == pytest.approx(
        4300300 + (1800 - bbox.y1 * output_scale) * (-gt[5])
    )


def test_geopdf_iso32000_structure_wkt_and_control_points(tmp_path):
    figure, axes, image = make_png(tmp_path)
    gt = matplotlib_geotransform(figure, axes, 100)
    target, _ = gauss_kruger_crs(74.25, JWD_CRS)
    output = tmp_path / "map_geopdf.pdf"
    written = write_geopdf(
        output, image, gt, target, dpi=100, scale_denominator=100000, title="Test GeoPDF"
    )
    readback = inspect_geopdf(output)
    assert readback["encoding"] == "ISO32000"
    assert readback["image_count"] == 1
    assert "/Type /Viewport" in readback["viewport_object"]
    assert "/Subtype /GEO" in readback["measure_object"]
    normalized_measure = " ".join(readback["measure_object"].split())
    assert "/LPTS [ 0 1 0 0 1 0 1 1 ]" in normalized_measure
    assert "/Type /PROJCS" in readback["gcs_object"]
    assert readback["gpts"] == pytest.approx(written["gpts"], abs=1e-5)
    assert len(readback["gpts"]) == 8
    assert all(math.isfinite(value) for value in readback["gpts"])

    spatial_ref = osr.SpatialReference()
    assert spatial_ref.ImportFromWkt(readback["wkt"]) == 0
    assert spatial_ref.GetProjParm("central_meridian") == pytest.approx(75.0)
    assert spatial_ref.GetProjParm("scale_factor") == pytest.approx(1.0)
    assert spatial_ref.GetTOWGS84()[:3] == pytest.approx((15.8, -154.4, -82.3))

    document = pymupdf.open(output)
    assert len(document) == 1
    assert document.metadata["title"] == "Test GeoPDF"
    expected_width_mm = gt[1] * 400 / 100000 * 1000
    expected_height_mm = -gt[5] * 300 / 100000 * 1000
    assert written["page_width_mm"] == pytest.approx(expected_width_mm)
    assert written["page_height_mm"] == pytest.approx(expected_height_mm)
    assert document[0].rect.width == pytest.approx(expected_width_mm * 72.0 / 25.4)
    assert document[0].rect.height == pytest.approx(expected_height_mm * 72.0 / 25.4)
    actual_scale = gt[1] * 400 / (written["page_width_mm"] / 1000.0)
    assert actual_scale == pytest.approx(100000)


def test_geopdf_writes_epsg_when_available(tmp_path):
    figure, axes, image = make_png(tmp_path)
    gt = matplotlib_geotransform(figure, axes, 100)
    output = tmp_path / "utm_geopdf.pdf"
    write_geopdf(output, image, gt, pyproj.CRS.from_epsg(32643), dpi=100, scale_denominator=100000)
    readback = inspect_geopdf(output)
    assert "/EPSG 32643" in readback["gcs_object"]
    spatial_ref = osr.SpatialReference()
    assert spatial_ref.ImportFromWkt(readback["wkt"]) == 0
    assert spatial_ref.GetProjParm("central_meridian") == pytest.approx(75.0)
    assert spatial_ref.GetProjParm("scale_factor") == pytest.approx(0.9996)


def test_geopdf_rejects_geographic_crs_for_exact_paper_scale(tmp_path):
    figure, axes, image = make_png(tmp_path)
    gt = matplotlib_geotransform(figure, axes, 100)
    with pytest.raises(ValueError, match="requires a projected CRS"):
        write_geopdf(tmp_path / "bad.pdf", image, gt, pyproj.CRS.from_epsg(4326), dpi=100)


def make_vector_figure(with_image=False):
    figure = Figure(figsize=(4, 3), dpi=100)
    FigureCanvasAgg(figure)
    axes = figure.add_axes([0.1, 0.1, 0.8, 0.8])
    axes.set_xlim(400000, 400400)
    axes.set_ylim(4300000, 4300300)
    axes.plot([400000, 400400], [4300000, 4300300], color="red")
    axes.text(400100, 4300100, "Vector")
    if with_image:
        axes.imshow([[0, 1], [1, 0]], extent=(400000, 400400, 4300000, 4300300))
    figure.canvas.draw()
    return figure, axes


def test_vector_geopdf_has_no_raster_and_exact_page_scale(tmp_path):
    figure, axes = make_vector_figure()
    target, _ = gauss_kruger_crs(74.25, JWD_CRS)
    output = tmp_path / "vector_geopdf.pdf"
    written = write_vector_geopdf(
        output, figure, axes, target, scale_denominator=1000, title="Vector GeoPDF"
    )
    readback = inspect_geopdf(output)
    assert written["content_mode"] == "vector"
    assert readback["image_count"] == 0
    assert readback["image_xobject_count"] == 0
    assert readback["drawing_count"] > 0
    assert readback["text_character_count"] >= len("Vector")
    assert readback["page_width_pt"] == pytest.approx(written["page_width_pt"])
    assert readback["page_height_pt"] == pytest.approx(written["page_height_pt"])
    actual_x_scale = (
        abs(written["page_transform"][1])
        * written["page_width_pt"]
        * written["metres_per_unit"]
        / (written["page_width_mm"] / 1000.0)
    )
    actual_y_scale = (
        abs(written["page_transform"][5])
        * written["page_height_pt"]
        * written["metres_per_unit"]
        / (written["page_height_mm"] / 1000.0)
    )
    assert actual_x_scale == pytest.approx(1000, rel=1e-9)
    assert actual_y_scale == pytest.approx(1000, rel=1e-9)
    spatial_ref = osr.SpatialReference()
    assert spatial_ref.ImportFromWkt(readback["wkt"]) == 0
    assert spatial_ref.GetProjParm("central_meridian") == pytest.approx(75.0)
    assert spatial_ref.GetTOWGS84()[:3] == pytest.approx((15.8, -154.4, -82.3))


def test_vector_geopdf_rejects_raster_source(tmp_path):
    figure, axes = make_vector_figure(with_image=True)
    target, _ = gauss_kruger_crs(74.25, JWD_CRS)
    with pytest.raises(ValueError, match="contains raster image objects"):
        write_vector_geopdf(tmp_path / "hybrid.pdf", figure, axes, target)


def test_example_help_does_not_import_pymupdf_when_geopdf_is_disabled():
    root = Path(__file__).resolve().parents[1]
    script = root / "examples/render_bundled_jwd.py"
    code = (
        "import runpy,sys; sys.modules['pymupdf']=None; "
        f"sys.argv=['render_bundled_jwd.py','--help']; "
        f"runpy.run_path({str(script)!r},run_name='__main__')"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "--no-geopdf" in completed.stdout
