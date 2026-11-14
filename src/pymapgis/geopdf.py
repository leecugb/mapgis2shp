"""ISO 32000 geospatial PDF output for rendered rasters and vector maps.

The implementation follows GDAL's ``WriteSRS_ISO32000`` structure: a page
``/VP`` viewport, a ``/Measure /GEO`` dictionary, four geographic ``/GPTS``
points, normalized ``/LPTS`` points and a WKT2 ``/GCS`` dictionary. The
coordinate definition uses WKT2 so numeric ``BOUNDCRS`` transformation
parameters are retained. JWD uses the fully vector writer, which rejects
raster image XObjects and sizes the vector Axes to the requested paper scale.
"""
from __future__ import annotations

import re
import math
from pathlib import Path
from typing import Any, Dict, Sequence, Tuple

import pymupdf
import pyproj

GeoTransform = Tuple[float, float, float, float, float, float]


def matplotlib_geotransform(figure: Any, axes: Any, dpi: int) -> GeoTransform:
    """Return a north-up GeoTransform for a full-canvas Matplotlib PNG."""
    if dpi <= 0:
        raise ValueError("dpi must be positive")
    figure.canvas.draw()
    bbox = axes.get_window_extent()
    # ``get_window_extent`` uses figure.dpi, while savefig may use another DPI.
    # Convert the display bbox into the actual output raster's pixel frame.
    output_scale = float(dpi) / float(figure.dpi)
    x0 = float(bbox.x0) * output_scale
    y0 = float(bbox.y0) * output_scale
    x1 = float(bbox.x1) * output_scale
    y1 = float(bbox.y1) * output_scale
    width_px = int(round(figure.get_size_inches()[0] * dpi))
    height_px = int(round(figure.get_size_inches()[1] * dpi))
    xmin, xmax = (float(value) for value in axes.get_xlim())
    ymin, ymax = (float(value) for value in axes.get_ylim())
    pixel_width = (xmax - xmin) / (x1 - x0)
    pixel_height = (ymax - ymin) / (y1 - y0)
    origin_x = xmin - x0 * pixel_width
    origin_y = ymax + (height_px - y1) * pixel_height
    return (origin_x, pixel_width, 0.0, origin_y, 0.0, -pixel_height)


def _apply_gt(gt: Sequence[float], pixel: float, line: float) -> Tuple[float, float]:
    return (
        gt[0] + pixel * gt[1] + line * gt[2],
        gt[3] + pixel * gt[4] + line * gt[5],
    )


def _number(value: float) -> str:
    return format(float(value), ".15g")


def _pdf_literal(value: str) -> str:
    # ESRI WKT is normally ASCII.  Replacing non-ASCII keeps the PDF literal
    # valid on every PyMuPDF version without weakening coordinate parameters.
    value = value.encode("ascii", "replace").decode("ascii")
    value = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return "(" + value + ")"


def _pdf_unescape(value: str) -> str:
    return value.replace(r"\(", "(").replace(r"\)", ")").replace("\\\\", "\\")


def write_geopdf(
    output_path: Any,
    image_path: Any,
    geotransform: Sequence[float],
    crs: Any,
    *,
    dpi: int = 600,
    scale_denominator: float = 250000,
    title: str = "Georeferenced map",
) -> Dict[str, Any]:
    """Write a one-page ISO 32000 GeoPDF at an exact paper scale."""
    if dpi <= 0:
        raise ValueError("dpi must be positive")
    if not math.isfinite(scale_denominator) or scale_denominator <= 0:
        raise ValueError("scale_denominator must be positive and finite")
    if len(geotransform) != 6:
        raise ValueError("geotransform must contain six values")
    target = crs if isinstance(crs, pyproj.CRS) else pyproj.CRS.from_user_input(crs)
    if target.is_geographic:
        raise ValueError("An exact paper-scale GeoPDF requires a projected CRS")
    axis_info = target.axis_info
    metres_per_unit = axis_info[0].unit_conversion_factor if axis_info else None
    if not metres_per_unit or metres_per_unit <= 0:
        raise ValueError("Exact paper scale requires CRS axes with a metric conversion factor")
    image = pymupdf.Pixmap(str(image_path))
    width_px, height_px = image.width, image.height
    ground_width_m = abs(geotransform[1]) * width_px * metres_per_unit
    ground_height_m = abs(geotransform[5]) * height_px * metres_per_unit
    page_width_mm = ground_width_m / scale_denominator * 1000.0
    page_height_mm = ground_height_m / scale_denominator * 1000.0
    corners = [
        _apply_gt(geotransform, 0, 0),
        _apply_gt(geotransform, 0, height_px),
        _apply_gt(geotransform, width_px, height_px),
        _apply_gt(geotransform, width_px, 0),
    ]
    geographic = target.geodetic_crs
    if geographic is None:
        raise ValueError("GeoPDF requires a CRS with a geodetic reference frame")
    transformer = pyproj.Transformer.from_crs(target, geographic, always_xy=True)
    gpts = []
    for x, y in corners:
        longitude, latitude = transformer.transform(x, y)
        gpts.extend((latitude, longitude))
    if not all(math.isfinite(value) for value in gpts):
        raise ValueError("GeoPDF geographic control points are not finite")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open()
    page = document.new_page(
        width=page_width_mm * 72.0 / 25.4,
        height=page_height_mm * 72.0 / 25.4,
    )
    page.insert_image(page.rect, filename=str(image_path))
    viewport_xref = document.get_new_xref()
    measure_xref = document.get_new_xref()
    gcs_xref = document.get_new_xref()
    document.update_object(
        viewport_xref,
        "<< /Type /Viewport /Name (Layer) "
        f"/BBox [0 0 {_number(page.rect.width)} {_number(page.rect.height)}] "
        f"/Measure {measure_xref} 0 R >>",
    )
    document.update_object(
        measure_xref,
        "<< /Type /Measure /Subtype /GEO "
        "/Bounds [0 1 0 0 1 0 1 1] "
        "/GPTS [" + " ".join(_number(value) for value in gpts) + "] "
        "/LPTS [0 1 0 0 1 0 1 1] "
        f"/GCS {gcs_xref} 0 R >>",
    )
    wkt = target.to_wkt("WKT2_2019")
    gcs = f"<< /Type /{'GEOGCS' if target.is_geographic else 'PROJCS'} /WKT {_pdf_literal(wkt)}"
    epsg = target.to_epsg()
    if epsg is not None:
        gcs += f" /EPSG {epsg}"
    gcs += " >>"
    document.update_object(gcs_xref, gcs)
    document.xref_set_key(page.xref, "VP", f"[{viewport_xref} 0 R]")
    metadata = document.metadata or {}
    metadata.update(
        {
            "title": title,
            "subject": "ISO 32000 geospatial PDF",
            "keywords": "GeoPDF, ISO32000, MapGIS, pymapgis",
            "creator": "pymapgis",
        }
    )
    document.set_metadata(metadata)
    document.save(output_path, garbage=4, deflate=True)
    document.close()
    return {
        "output": str(output_path),
        "encoding": "ISO32000",
        "raster_dpi": dpi,
        "scale_denominator": scale_denominator,
        "scale_policy": "page_size_from_ground_extent",
        "metres_per_unit": metres_per_unit,
        "page_width_mm": page_width_mm,
        "page_height_mm": page_height_mm,
        "raster_width_px": width_px,
        "raster_height_px": height_px,
        "geotransform": list(geotransform),
        "gpts": gpts,
        "crs_wkt": wkt,
        "epsg": epsg,
        "viewport_xref": viewport_xref,
        "measure_xref": measure_xref,
        "gcs_xref": gcs_xref,
    }


def write_vector_geopdf(
    output_path: Any,
    figure: Any,
    axes: Any,
    crs: Any,
    *,
    scale_denominator: float = 250000,
    title: str = "Georeferenced vector map",
) -> Dict[str, Any]:
    """Write a fully vector, one-page ISO 32000 GeoPDF at exact paper scale.

    The Matplotlib figure is resized so the *Axes* has the physical dimensions
    required by its ground extent. No tight bounding box is used. The returned
    page transform maps PDF points (origin at bottom-left) to projected map
    coordinates. Any raster image XObject is rejected rather than silently
    presenting a hybrid PDF as fully vector.
    """
    if not math.isfinite(scale_denominator) or scale_denominator <= 0:
        raise ValueError("scale_denominator must be positive and finite")
    target = crs if isinstance(crs, pyproj.CRS) else pyproj.CRS.from_user_input(crs)
    if target.is_geographic:
        raise ValueError("An exact paper-scale GeoPDF requires a projected CRS")
    axis_info = target.axis_info
    metres_per_unit = axis_info[0].unit_conversion_factor if axis_info else None
    if not metres_per_unit or metres_per_unit <= 0:
        raise ValueError("Exact paper scale requires CRS axes with a metric conversion factor")
    xmin, xmax = (float(value) for value in axes.get_xlim())
    ymin, ymax = (float(value) for value in axes.get_ylim())
    span_x, span_y = xmax - xmin, ymax - ymin
    if not all(math.isfinite(value) for value in (span_x, span_y)) or not span_x or not span_y:
        raise ValueError("Vector GeoPDF requires finite, non-zero Axes extents")
    desired_axes_width_pt = abs(span_x) * metres_per_unit / scale_denominator * 1000 * 72 / 25.4
    desired_axes_height_pt = abs(span_y) * metres_per_unit / scale_denominator * 1000 * 72 / 25.4

    # Iterative ratio resizing preserves the existing Axes margins while
    # accommodating Matplotlib's equal-aspect adjustment. It normally
    # converges in one pass; the remaining passes are floating-point guards.
    for _ in range(4):
        figure.canvas.draw()
        bbox = axes.get_window_extent()
        axes_width_pt = float(bbox.width) * 72.0 / float(figure.dpi)
        axes_height_pt = float(bbox.height) * 72.0 / float(figure.dpi)
        if axes_width_pt <= 0 or axes_height_pt <= 0:
            raise ValueError("Vector GeoPDF requires a visible Axes")
        if (
            math.isclose(axes_width_pt, desired_axes_width_pt, rel_tol=1e-9, abs_tol=1e-6)
            and math.isclose(axes_height_pt, desired_axes_height_pt, rel_tol=1e-9, abs_tol=1e-6)
        ):
            break
        width_in, height_in = figure.get_size_inches()
        figure.set_size_inches(
            float(width_in) * desired_axes_width_pt / axes_width_pt,
            float(height_in) * desired_axes_height_pt / axes_height_pt,
            forward=True,
        )
    else:
        raise ValueError("Could not size the vector Axes to the requested paper scale")

    figure.canvas.draw()
    bbox = axes.get_window_extent()
    axes_x0_pt = float(bbox.x0) * 72.0 / float(figure.dpi)
    axes_y0_pt = float(bbox.y0) * 72.0 / float(figure.dpi)
    axes_x1_pt = float(bbox.x1) * 72.0 / float(figure.dpi)
    axes_y1_pt = float(bbox.y1) * 72.0 / float(figure.dpi)
    axes_width_pt = axes_x1_pt - axes_x0_pt
    axes_height_pt = axes_y1_pt - axes_y0_pt
    scale_x = span_x / axes_width_pt
    scale_y = span_y / axes_height_pt
    page_transform = (
        xmin - axes_x0_pt * scale_x,
        scale_x,
        0.0,
        ymin - axes_y0_pt * scale_y,
        0.0,
        scale_y,
    )

    geographic = target.geodetic_crs
    if geographic is None:
        raise ValueError("GeoPDF requires a CRS with a geodetic reference frame")
    transformer = pyproj.Transformer.from_crs(target, geographic, always_xy=True)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    import tempfile

    with tempfile.TemporaryDirectory(prefix="pymapgis-vector-geopdf-") as directory:
        source_path = Path(directory) / "vector-source.pdf"
        figure.savefig(source_path, format="pdf")
        document = pymupdf.open(source_path)
        try:
            if len(document) != 1:
                raise ValueError("Vector GeoPDF expects exactly one source page")
            image_xrefs = [
                xref for xref in range(1, document.xref_length())
                if document.xref_is_image(xref)
            ]
            if image_xrefs:
                raise ValueError(
                    "Vector GeoPDF source contains raster image objects; "
                    "enable vector_patterns and remove other image artists"
                )
            page = document[0]
            page_width_pt = float(page.rect.width)
            page_height_pt = float(page.rect.height)
            corners = [
                _apply_gt(page_transform, 0.0, page_height_pt),
                _apply_gt(page_transform, 0.0, 0.0),
                _apply_gt(page_transform, page_width_pt, 0.0),
                _apply_gt(page_transform, page_width_pt, page_height_pt),
            ]
            gpts = []
            for x, y in corners:
                longitude, latitude = transformer.transform(x, y)
                gpts.extend((latitude, longitude))
            if not all(math.isfinite(value) for value in gpts):
                raise ValueError("GeoPDF geographic control points are not finite")

            viewport_xref = document.get_new_xref()
            measure_xref = document.get_new_xref()
            gcs_xref = document.get_new_xref()
            document.update_object(
                viewport_xref,
                "<< /Type /Viewport /Name (Layer) "
                f"/BBox [0 0 {_number(page_width_pt)} {_number(page_height_pt)}] "
                f"/Measure {measure_xref} 0 R >>",
            )
            document.update_object(
                measure_xref,
                "<< /Type /Measure /Subtype /GEO "
                "/Bounds [0 1 0 0 1 0 1 1] "
                "/GPTS [" + " ".join(_number(value) for value in gpts) + "] "
                "/LPTS [0 1 0 0 1 0 1 1] "
                f"/GCS {gcs_xref} 0 R >>",
            )
            wkt = target.to_wkt("WKT2_2019")
            gcs = (
                f"<< /Type /{'GEOGCS' if target.is_geographic else 'PROJCS'} "
                f"/WKT {_pdf_literal(wkt)}"
            )
            epsg = target.to_epsg()
            if epsg is not None:
                gcs += f" /EPSG {epsg}"
            gcs += " >>"
            document.update_object(gcs_xref, gcs)
            document.xref_set_key(page.xref, "VP", f"[{viewport_xref} 0 R]")
            metadata = document.metadata or {}
            metadata.update({
                "title": title,
                "subject": "ISO 32000 geospatial vector PDF",
                "keywords": "GeoPDF, ISO32000, vector, MapGIS, pymapgis",
                "creator": "pymapgis",
            })
            document.set_metadata(metadata)
            document.save(output_path, garbage=4, deflate=True)
        finally:
            document.close()

    return {
        "output": str(output_path),
        "encoding": "ISO32000",
        "content_mode": "vector",
        "scale_denominator": scale_denominator,
        "scale_policy": "axes_page_size_from_ground_extent",
        "metres_per_unit": metres_per_unit,
        "page_width_mm": page_width_pt * 25.4 / 72.0,
        "page_height_mm": page_height_pt * 25.4 / 72.0,
        "page_width_pt": page_width_pt,
        "page_height_pt": page_height_pt,
        "axes_width_pt": axes_width_pt,
        "axes_height_pt": axes_height_pt,
        "axes_bounds_pt": [axes_x0_pt, axes_y0_pt, axes_x1_pt, axes_y1_pt],
        "page_transform": list(page_transform),
        "gpts": gpts,
        "crs_wkt": wkt,
        "epsg": epsg,
        "viewport_xref": viewport_xref,
        "measure_xref": measure_xref,
        "gcs_xref": gcs_xref,
    }


def inspect_geopdf(path: Any) -> Dict[str, Any]:
    """Read back the ISO 32000 viewport, measure dictionary and GCS WKT."""
    document = pymupdf.open(path)
    if len(document) != 1:
        raise ValueError("GeoPDF inspection expects exactly one page")
    page = document[0]
    kind, value = document.xref_get_key(page.xref, "VP")
    if kind != "array":
        raise ValueError("GeoPDF page has no /VP array")
    viewport_match = re.search(r"(\d+) 0 R", value)
    if not viewport_match:
        raise ValueError("GeoPDF /VP does not reference a viewport object")
    viewport_xref = int(viewport_match.group(1))
    viewport = document.xref_object(viewport_xref)
    measure_match = re.search(r"/Measure (\d+) 0 R", viewport)
    if not measure_match:
        raise ValueError("GeoPDF viewport has no /Measure reference")
    measure_xref = int(measure_match.group(1))
    measure = document.xref_object(measure_xref)
    gcs_match = re.search(r"/GCS (\d+) 0 R", measure)
    if not gcs_match:
        raise ValueError("GeoPDF measure has no /GCS reference")
    gcs_xref = int(gcs_match.group(1))
    gcs = document.xref_object(gcs_xref)
    gpts_match = re.search(r"/GPTS \[([^]]+)\]", measure)
    if not gpts_match:
        raise ValueError("GeoPDF measure has no /GPTS array")
    gpts = [float(value) for value in gpts_match.group(1).split()]
    if len(gpts) != 8:
        raise ValueError("GeoPDF requires four /GPTS control points")
    wkt_match = re.search(r"/WKT \((.*)\)(?:\s*/EPSG \d+)?\s*>>", gcs, re.S)
    wkt = _pdf_unescape(wkt_match.group(1)) if wkt_match else None
    if not wkt and "/EPSG" not in gcs:
        raise ValueError("GeoPDF GCS has neither WKT nor EPSG")
    image_xobject_count = sum(
        bool(document.xref_is_image(xref)) for xref in range(1, document.xref_length())
    )
    drawing_count = len(page.get_drawings())
    text_character_count = len(page.get_text("text").strip())
    return {
        "encoding": "ISO32000",
        "viewport_xref": viewport_xref,
        "measure_xref": measure_xref,
        "gcs_xref": gcs_xref,
        "viewport_object": viewport,
        "measure_object": measure,
        "gcs_object": gcs,
        "gpts": gpts,
        "wkt": wkt,
        "page_width_pt": page.rect.width,
        "page_height_pt": page.rect.height,
        "image_count": len(page.get_images(full=True)),
        "image_xobject_count": image_xobject_count,
        "drawing_count": drawing_count,
        "text_character_count": text_character_count,
    }
