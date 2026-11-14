"""Regressions from the graphic-library rendering pipeline audit."""

from __future__ import annotations

import math

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import LineString, MultiLineString, Point, Polygon

import pymapgis.graphic as graphic
from pymapgis import GraphicLibraries, GraphicRenderer
from pymapgis.fillgrph import (
    KIND_ARC_DEG,
    KIND_LINE,
    KIND_LINE_HAIR,
    FillPattern,
    FillStroke,
    pattern_geometry,
)
from pymapgis.linesty import LineStyle, SubLine
from pymapgis.slib import SubPath, Symbol


class FakeColorLib:
    def rgb01(self, number):
        return {1: (0.0, 0.0, 0.0), 6: (1.0, 0.0, 0.0)}.get(number)


class FakeLinestyLib:
    def __init__(self, styles=None):
        self.styles = styles or {}

    def decode(self, number):
        return self.styles.get(number)


class FakeSubgraphLib:
    def __init__(self, symbols=None):
        self.symbols = symbols or {}

    def decode(self, number):
        return self.symbols.get(number)


class FakeFillgrphLib:
    def decode(self, number):
        return None


def make_renderer(styles=None, symbols=None, **kwargs):
    libraries = GraphicLibraries(
        linesty=FakeLinestyLib(styles),
        subgraph=FakeSubgraphLib(symbols),
        fillgrph=FakeFillgrphLib(),
        color=FakeColorLib(),
    )
    kwargs.setdefault("map_units_per_mm", 1.0)
    return GraphicRenderer(libraries, **kwargs)


def make_axes():
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure()
    FigureCanvasAgg(fig)
    return fig, fig.add_subplot(111)


def polygon_frame(labels=("A",), geometries=None):
    if geometries is None:
        geometries = [Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])] * len(labels)
    return gpd.GeoDataFrame(
        {
            "QDUECC": list(labels),
            "fill_color": [6] * len(labels),
            "class": [2] * len(labels),
            "pattern": [0] * len(labels),
        },
        geometry=list(geometries),
        crs="EPSG:32643",
    )


def line_frame(geometry):
    return gpd.GeoDataFrame(
        {
            "linetype": [900],
            "aux_linetype": [0],
            "color": [1],
            "width": [0.1],
            "x_coef": [1.0],
            "y_coef": [1.0],
        },
        geometry=[geometry],
        crs="EPSG:32643",
    )


def pen_style(segment):
    return LineStyle(
        no=900,
        n_subs=1,
        sublines=[SubLine(n=1, length=24, f32_zone=list(segment))],
    )


@pytest.mark.parametrize(
    "segment,expected_kind",
    [
        ((0.0, 0.0, 1.0, 0.0), "solid_pen"),
        ((0.0, 0.0, 0.5, 0.0), "single_pen"),
        ((0.75, 0.0, 0.0, 0.0), "single_pen"),
        ((0.5, 0.2, 0.5, 0.0), "single_pen"),
    ],
)
def test_single_pen_uses_stored_segment(segment, expected_kind):
    renderer = make_renderer(styles={900: pen_style(segment)})
    rhythm = renderer._rhythm(900)
    assert rhythm["kind"] == expected_kind
    assert rhythm["period_mm"] == pytest.approx(1.0)
    if expected_kind == "single_pen":
        x0, y0, x1, y1 = segment
        assert rhythm["polylines"] == [[(x0, y0), (x1, y1)]]


def test_partial_single_pen_draws_dashes_not_a_solid_line():
    renderer = make_renderer(styles={900: pen_style((0.0, 0.0, 0.5, 0.0))})
    fig, ax = make_axes()
    ax.set_xlim(-0.1, 2.1)
    ax.set_ylim(-1, 1)
    report = renderer.draw_layer(ax, line_frame(LineString([(0, 0), (2, 0)])))
    assert report["pattern"] == 1
    assert "solid" not in report
    segments = ax.collections[0].get_segments()
    assert len(segments) == 2
    np.testing.assert_allclose(np.asarray(segments)[:, :, 0], [[0.0, 0.5], [1.0, 1.5]])
    fig.clear()


def test_trailing_duplicate_vertex_preserves_endpoint_tangent():
    renderer = make_renderer()
    buffer = graphic._StampBuffer()
    rhythm = {
        "kind": "payload",
        "period_mm": 1.0,
        "polylines": [],
        "dots": [(0.0, 0.5, 0.05)],
        "fills": [],
    }
    renderer._stamp_along(
        np.asarray([(0.0, 0.0), (1.0, 0.0), (1.0, 0.0)]),
        rhythm,
        1,
        1,
        1,
        (0, 0, 0),
        1,
        0.001,
        buffer,
    )
    dots = np.concatenate(buffer.dots)
    np.testing.assert_allclose(dots[-1], [1.0, 0.5])


def unknown_fill_rhythm():
    return {
        "kind": "payload",
        "period_mm": 1.0,
        "polylines": [[(0.0, 0.0), (1.0, 0.0)]],
        "dots": [],
        "fills": [],
        "unknown_fills": 2,
    }


def test_unknown_fill_is_counted_once_per_multipart_feature(monkeypatch):
    renderer = make_renderer()
    monkeypatch.setattr(renderer, "_rhythm", lambda number, aux=0: unknown_fill_rhythm())
    geometry = MultiLineString([
        [(0, 0), (1, 0)],
        [(2, 0), (3, 0)],
        [(4, 0), (5, 0)],
    ])
    fig, ax = make_axes()
    ax.set_xlim(-1, 6)
    ax.set_ylim(-1, 1)
    report = renderer.draw_layer(ax, line_frame(geometry))
    assert report["drawn"] == 1
    assert report["pattern"] == 3
    assert report["unknown_fill"] == 2
    fig.clear()


def test_cycle_limited_feature_does_not_report_unknown_fill(monkeypatch):
    renderer = make_renderer(max_pattern_cycles=3)
    monkeypatch.setattr(renderer, "_rhythm", lambda number, aux=0: unknown_fill_rhythm())
    fig, ax = make_axes()
    ax.set_xlim(-1, 101)
    ax.set_ylim(-1, 1)
    report = renderer.draw_layer(ax, line_frame(LineString([(0, 0), (100, 0)])))
    assert report["cycle_limit"] == 1
    assert "unknown_fill" not in report
    fig.clear()


def test_draw_layer_resets_collision_boxes_and_seeded_rng():
    renderer = make_renderer(
        polygon_label_avoid_collisions=True,
        polygon_label_randomize=True,
        polygon_label_seed=42,
        polygon_label_buffer_pt=100.0,
        polygon_label_max_offset_pt=4.0,
    )
    layer = polygon_frame(("A", "B", "C"))

    fig1, ax1 = make_axes()
    report1 = renderer.draw_layer(ax1, layer)
    labels1 = [text.get_text() for text in ax1.texts]
    fig2, ax2 = make_axes()
    report2 = renderer.draw_layer(ax2, layer)
    labels2 = [text.get_text() for text in ax2.texts]

    assert report1["polygon_label"] == 1
    assert report2["polygon_label"] == 1
    assert report1["label_skipped_collision"] == 2
    assert report2["label_skipped_collision"] == 2
    assert labels1 == labels2
    fig1.clear()
    fig2.clear()


def test_collision_labels_work_after_pdf_save_and_on_pdf_canvas(tmp_path):
    renderer = make_renderer(polygon_label_avoid_collisions=True)
    layer = polygon_frame()
    result = renderer.render([layer], tmp_path / "labels.pdf", dpi=50)
    assert hasattr(result.figure.canvas, "get_renderer")
    report = renderer.draw_layer(result.axes, layer)
    assert report["polygon_label"] == 1
    result.figure.clear()

    from matplotlib.backends.backend_pdf import FigureCanvasPdf

    fig, ax = make_axes()
    FigureCanvasPdf(fig)
    report = renderer.draw_layer(ax, layer)
    assert report["polygon_label"] == 1
    fig.clear()


def test_label_candidate_search_buffers_once_and_skips_duplicate_origin(monkeypatch):
    from matplotlib.transforms import Bbox

    class CountingGeometry:
        def __init__(self):
            self.buffer_calls = 0

        def buffer(self, distance):
            self.buffer_calls += 1
            return self

        def contains(self, candidate):
            return True

    renderer = make_renderer(polygon_label_avoid_collisions=True)
    fig, ax = make_axes()
    renderer._label_boxes = [Bbox.from_extents(-1e6, -1e6, 1e6, 1e6)]
    attempts = []
    original_text = ax.text

    def recording_text(x, y, *args, **kwargs):
        attempts.append((x, y))
        return original_text(x, y, *args, **kwargs)

    monkeypatch.setattr(ax, "text", recording_text)
    geometry = CountingGeometry()
    placed = renderer._place_polygon_label_with_buffer(
        ax, "A", Point(0, 0), geometry, 4.0, {}, {}
    )
    assert not placed
    assert geometry.buffer_calls == 1
    assert len(attempts) == 41  # one origin + five offset rings × eight directions
    fig.clear()


def test_fillgrph_width_arrays_stay_aligned_with_geometry():
    pattern = FillPattern(
        no=1,
        grid=8,
        unit=100,
        strokes=[
            FillStroke(KIND_LINE, 1, [(0, 0), (1, 0)]),
            FillStroke(KIND_LINE_HAIR, 65535, [(0, 0), (0, 1)]),
            FillStroke(KIND_ARC_DEG, 7, [(0, 0), (1, 0), (90, 0)]),
        ],
    )

    class Library:
        def decode(self, number):
            return pattern

    geometry = pattern_geometry(Library(), 1)
    assert geometry["polyline_widths"] == [1, 65535]
    assert geometry["arc_widths"] == [7]


def test_tile_mask_consumes_native_stroke_widths(monkeypatch):
    geometry = {
        "fill_polygons": [],
        "polylines": [[(0, 0), (1, 0)], [(0, 1), (1, 1)]],
        "polyline_widths": [1, 7],
        "circles": [],
        "arcs": [(0.5, 0.5, 0.2, 0, 90)],
        "arc_widths": [3],
    }
    monkeypatch.setattr(graphic, "pattern_geometry", lambda library, number: geometry)
    widths = []
    from matplotlib.axes import Axes

    original_plot = Axes.plot

    def recording_plot(self, *args, **kwargs):
        widths.append(kwargs.get("lw"))
        return original_plot(self, *args, **kwargs)

    monkeypatch.setattr(Axes, "plot", recording_plot)
    renderer = make_renderer(tile_pixels=26)
    assert renderer._tile_mask(1) is not None
    assert widths == [
        renderer._tile_stroke_lw(1, 26),
        renderer._tile_stroke_lw(7, 26),
        renderer._tile_stroke_lw(3, 26),
    ]
    assert widths[1] > widths[2] > widths[0]
    assert renderer._tile_stroke_lw(65535, 26) < renderer._tile_stroke_lw(1, 26)


def test_nonfinite_single_pen_uses_reported_fallback_not_empty_pattern():
    renderer = make_renderer(styles={900: pen_style((0.0, 0.0, float("nan"), 0.0))})
    fig, ax = make_axes()
    ax.set_xlim(-0.1, 2.1)
    ax.set_ylim(-1, 1)
    report = renderer.draw_layer(ax, line_frame(LineString([(0, 0), (2, 0)])))
    assert report["fallback"] == 1
    assert "empty_pattern" not in report
    assert len(ax.lines) == 1
    np.testing.assert_allclose(ax.lines[0].get_xdata(), [0, 2])
    fig.clear()


def test_pdf_canvas_label_renderer_is_resolved_once_per_draw(monkeypatch):
    from matplotlib.backends.backend_pdf import FigureCanvasPdf

    renderer = make_renderer(polygon_label_avoid_collisions=True)
    fig, ax = make_axes()
    FigureCanvasPdf(fig)
    original_get_renderer = fig._get_renderer
    calls = []

    def counting_get_renderer(*args, **kwargs):
        calls.append(1)
        return original_get_renderer(*args, **kwargs)

    monkeypatch.setattr(fig, "_get_renderer", counting_get_renderer)
    report = renderer.draw_layer(ax, polygon_frame(("A", "B")))
    assert report["polygon_label"] == 2
    assert len(calls) == 1
    fig.clear()


def test_vector_pattern_uses_only_clipped_vector_collections(monkeypatch):
    geometry = {
        "fill_polygons": [[(0.1, 0.1), (0.4, 0.1), (0.4, 0.4)]],
        "polylines": [[(0.0, 0.0), (1.0, 1.0)]],
        "polyline_widths": [7],
        "circles": [(0.5, 0.5, 0.1)],
        "arcs": [(0.5, 0.5, 0.2, 0, 90)],
        "arc_widths": [1],
    }
    monkeypatch.setattr(graphic, "pattern_geometry", lambda library, number: geometry)
    renderer = make_renderer(vector_patterns=True)
    fig, ax = make_axes()
    polygon = Polygon(
        [(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)],
        [[(0.5, 0.5), (0.5, 1.0), (1.0, 1.0), (1.0, 0.5), (0.5, 0.5)]],
    )
    outcome = renderer._draw_pattern(ax, polygon, 1, (1, 0, 0), 1.0, 1.0)
    assert outcome == "rendered"
    assert not ax.images
    assert len(ax.collections) == 2
    assert all(collection.get_clip_path() is not None for collection in ax.collections)
    output = fig.canvas
    assert output is not None
    fig.clear()


def test_vector_pattern_element_limit_is_reported(monkeypatch):
    geometry = {
        "fill_polygons": [],
        "polylines": [[(0.0, 0.0), (1.0, 1.0)]],
        "polyline_widths": [4],
        "circles": [],
        "arcs": [],
    }
    monkeypatch.setattr(graphic, "pattern_geometry", lambda library, number: geometry)
    renderer = make_renderer(vector_patterns=True, max_vector_pattern_elements=0)
    fig, ax = make_axes()
    outcome = renderer._draw_pattern(
        ax, Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]), 1, (1, 0, 0), 1.0, 1.0
    )
    assert outcome == "too_large"
    assert not ax.images and not ax.collections
    fig.clear()


def test_geosciml_attitude_dip_label_placement_and_lineation_exclusion():
    symbol = Symbol(
        no=1245,
        type=1,
        n=2,
        header_len=4,
        header_u16=[1, 2],
        subpaths=[SubPath(points=[(0, -0.5), (0, 0.5)])],
    )
    renderer = make_renderer(
        symbols={1245: symbol},
        attitude_dip_labels=True,
        map_units_per_mm=1.0,
    )
    wt = gpd.GeoDataFrame(
        {
            "point_type": [1, 1],
            "symbol_no": [1245, 1245],
            "height": [5.0, 4.0],
            "width": [5.0, 4.0],
            "spacing": [np.nan, np.nan],
            "angle": [75.0, 255.0],
            "color": [1, 1],
            "CHFCEC": ["产状", "线理"],
            "GZBBAB": [75.0, 0.0],
            "GZBBAC": [315.0, 0.0],
            "GZBBAD": [51.0, 15.0],
            "P_PLUNGE": [0.0, 15.0],
            "P_BEARING": [0.0, 255.0],
        },
        geometry=[Point(0, 0), Point(1000, 1000)],
        crs="EPSG:32611",
    )
    fig, ax = make_axes()
    ax.set_xlim(-100, 1100)
    ax.set_ylim(-100, 1100)
    report = renderer.draw_layer(ax, wt)
    assert report["symbols"] == 2
    assert report["attitude_dip_label"] == 1
    assert len(ax.texts) == 1
    label = ax.texts[0]
    assert label.get_text() == "51"
    assert label.get_fontsize() == pytest.approx(3.5)
    tick = 2.0
    direction = math.radians(315.0)
    dx, dy = math.sin(direction), math.cos(direction)
    rx, ry = dy, -dx
    offset = 60.0 + (2 * 180.0 / 2) * abs(rx) + (310.0 / 2) * abs(ry)
    expected = (dx * tick + rx * offset, dy * tick + ry * offset)
    assert label.get_position() == pytest.approx(expected)
    assert label.get_rotation() == 0.0
    fig.clear()


def test_attitude_symbol_scale_enlarges_only_attitudes():
    symbol = Symbol(
        no=1245,
        type=1,
        n=2,
        header_len=4,
        header_u16=[1, 2],
        subpaths=[SubPath(points=[(0, -0.5), (0, 0.5)])],
    )
    renderer = make_renderer(
        symbols={1245: symbol},
        attitude_dip_labels=True,
        attitude_symbol_scale=1.5,
        map_units_per_mm=1.0,
    )
    wt = gpd.GeoDataFrame(
        {
            "point_type": [1, 1],
            "symbol_no": [1245, 1245],
            "height": [5.0, 4.0],
            "width": [5.0, 4.0],
            "angle": [0.0, 0.0],
            "color": [1, 1],
            "CHFCEC": ["产状", "线理"],
            "GZBBAC": [315.0, 0.0],
            "GZBBAD": [51.0, 15.0],
        },
        geometry=[Point(0, 0), Point(1000, 1000)],
        crs="EPSG:32611",
    )
    fig, ax = make_axes()
    report = renderer.draw_layer(ax, wt)
    assert report["symbols"] == 2
    assert report["attitude_dip_label"] == 1
    assert np.ptp(ax.lines[0].get_xydata()[:, 1]) == pytest.approx(7.5)
    assert np.ptp(ax.lines[1].get_xydata()[:, 1]) == pytest.approx(4.0)
    assert ax.texts[0].get_fontsize() == pytest.approx(3.5)
    tick = 2.0 * 1.5
    direction = math.radians(315.0)
    dx, dy = math.sin(direction), math.cos(direction)
    rx, ry = dy, -dx
    offset = 60.0 + (2 * 180.0 / 2) * abs(rx) + (310.0 / 2) * abs(ry)
    assert ax.texts[0].get_position() == pytest.approx(
        (dx * tick + rx * offset, dy * tick + ry * offset)
    )
    fig.clear()


def test_dip_label_uses_actual_subgraph_tick_endpoint_and_right_side():
    symbol = Symbol(
        no=1245,
        type=1,
        n=4,
        header_len=6,
        header_u16=[1, 4, 0, 2],
        subpaths=[
            SubPath(points=[(-0.5, 0.0), (0.5, 0.0)]),
            SubPath(points=[(0.0, 0.0), (0.0, 0.2)]),
        ],
    )
    renderer = make_renderer(
        symbols={1245: symbol},
        attitude_dip_labels=True,
        attitude_dip_label_direction="symbol",
        attitude_symbol_scale=1.5,
        map_units_per_mm=1.0,
    )
    wt = gpd.GeoDataFrame(
        {
            "point_type": [1], "symbol_no": [1245], "height": [5.0],
            "width": [5.0], "angle": [30.0], "color": [1],
            "CHFCEC": ["产状"], "GZBBAC": [315.0], "GZBBAD": [51.0],
        },
        geometry=[Point(0, 0)], crs="EPSG:32611",
    )
    fig, ax = make_axes()
    report = renderer.draw_layer(ax, wt)
    assert report["attitude_dip_label"] == 1
    angle = math.radians(30.0)
    end = np.asarray([-0.2 * 7.5 * math.sin(angle), 0.2 * 7.5 * math.cos(angle)])
    dx, dy = -math.sin(angle), math.cos(angle)
    rx, ry = dy, -dx
    offset = 60.0 + (2 * 180.0 / 2) * abs(rx) + (310.0 / 2) * abs(ry)
    expected = end + np.asarray([rx * offset, ry * offset])
    assert ax.texts[0].get_position() == pytest.approx(tuple(expected))
    fig.clear()


def test_symbol_direction_falls_back_for_triangle_attitude_symbol():
    triangle = SubPath(points=[(-0.1, 0.0), (0.0, 0.2), (0.1, 0.0), (-0.1, 0.0)])
    strike = SubPath(points=[(-0.5, 0.0), (0.5, 0.0)])
    symbol = Symbol(
        no=1255, type=2, n=8, header_len=8, header_u16=[2, 8, 0, 2],
        subpaths=[triangle, strike],
    )
    renderer = make_renderer(
        symbols={1255: symbol},
        attitude_dip_labels=True,
        attitude_dip_label_direction="symbol",
        attitude_symbol_scale=1.5,
        map_units_per_mm=1.0,
    )
    wt = gpd.GeoDataFrame(
        {
            "point_type": [1], "symbol_no": [1255], "height": [5.0],
            "width": [5.0], "angle": [0.0], "color": [1],
            "CHFCEC": ["产状"], "GZBBGA": ["202011"],
            "GZBBAC": [90.0], "GZBBAD": [51.0],
        },
        geometry=[Point(0, 0)], crs="EPSG:32611",
    )
    fig, ax = make_axes()
    report = renderer.draw_layer(ax, wt)
    assert report["symbols"] == 1
    assert report["attitude_dip_label"] == 1
    assert ax.texts[0].get_text() == "51"
    tick = 2.0 * 1.5
    offset = 60.0 + (2 * 180.0 / 2) * 0.0 + (310.0 / 2)
    assert ax.texts[0].get_position() == pytest.approx((tick, -offset))
    fig.clear()


def _tick_symbol():
    return Symbol(
        no=1245,
        type=1,
        n=4,
        header_len=6,
        header_u16=[1, 4, 0, 2],
        subpaths=[
            SubPath(points=[(-0.5, 0.0), (0.5, 0.0)]),
            SubPath(points=[(0.0, 0.0), (0.0, 0.2)]),
        ],
    )


def test_predrawn_dip_label_moves_polygon_label_instead_of_deleting_it():
    renderer = make_renderer(
        symbols={1245: _tick_symbol()},
        attitude_dip_labels=True,
        attitude_dip_label_direction="symbol",
        polygon_label_avoid_collisions=True,
        polygon_label_buffer_pt=2.0,
        polygon_label_max_offset_pt=24.0,
    )
    wp = polygon_frame(
        ("A",),
        geometries=[Polygon([
            (230, -10), (250, -10), (250, 10), (230, 10), (230, -10),
        ])],
    )
    wt = gpd.GeoDataFrame(
        {
            "point_type": [1], "symbol_no": [1245], "height": [5.0],
            "width": [5.0], "angle": [0.0], "color": [1],
            "CHFCEC": ["产状"], "GZBBAC": [0.0], "GZBBAD": [51.0],
        },
        geometry=[Point(0, 0)], crs="EPSG:32643",
    )
    fig, ax = make_axes()
    reports = renderer.draw_layers(ax, [wp, wt])
    polygon_report = next(report for report in reports if report["kind"] == "wp")
    attitude_report = next(report for report in reports if report["kind"] == "wt")
    assert polygon_report["polygon_label"] == 1
    assert polygon_report["label_offset"] >= 1
    assert polygon_report.get("label_skipped_collision", 0) == 0
    assert attitude_report["attitude_dip_label"] == 1
    assert len(ax.texts) == 2
    assert {text.get_text() for text in ax.texts} == {"A", "51"}
    assert renderer.inspect_text_collisions(ax)["overlap_count"] == 0
    fig.clear()


def test_unresolved_dip_collision_is_reported_without_deleting_text():
    renderer = make_renderer(
        symbols={1245: _tick_symbol()},
        attitude_dip_labels=True,
        attitude_dip_label_direction="symbol",
        polygon_label_avoid_collisions=True,
        polygon_label_max_offset_pt=0.001,
    )
    wt = gpd.GeoDataFrame(
        {
            "point_type": [1, 1], "symbol_no": [1245, 1245],
            "height": [5.0, 5.0], "width": [5.0, 5.0],
            "angle": [0.0, 0.0], "color": [1, 1],
            "CHFCEC": ["产状", "产状"], "GZBBAC": [0.0, 0.0],
            "GZBBAD": [51.0, 42.0],
        },
        geometry=[Point(0, 0), Point(0, 0)], crs="EPSG:32643",
    )
    fig, ax = make_axes()
    report = renderer.draw_layers(ax, [wt])[0]
    assert report["attitude_dip_label"] == 2
    assert report["attitude_dip_label_collision"] >= 1
    assert len(ax.texts) == 2
    assert {text.get_text() for text in ax.texts} == {"51", "42"}
    audit = renderer.inspect_text_collisions(ax)
    assert audit["checked_text_artists"] == 2
    assert audit["overlap_count"] >= 1
    fig.clear()


def test_dip_tick_mm_is_independent_of_output_dpi():
    renderer = make_renderer(
        symbols={1245: _tick_symbol()},
        attitude_dip_labels=True,
        attitude_symbol_scale=1.5,
        attitude_dip_tick_mm=2.0,
    )
    wt = gpd.GeoDataFrame(
        {
            "point_type": [1], "symbol_no": [1245], "height": [5.0],
            "width": [5.0], "angle": [0.0], "color": [1],
            "CHFCEC": ["产状"], "GZBBAC": [0.0], "GZBBAD": [51.0],
        },
        geometry=[Point(0, 0)], crs="EPSG:32643",
    )
    positions = []
    for dpi in (80, 160):
        fig, ax = make_axes()
        fig.set_dpi(dpi)
        ax.set_xlim(-100, 100)
        ax.set_ylim(-100, 100)
        report = renderer.draw_layer(ax, wt)
        assert report["attitude_dip_label"] == 1
        positions.append(ax.texts[0].get_position())
        fig.clear()
    assert positions[0] == pytest.approx(positions[1])
    # Dip direction north: 2.0 mm tick × 1.5 = (0, 3), then 240 units right.
    assert positions[0] == pytest.approx((240.0, 3.0))


def test_text_category_exclusion_retains_attitude_subgraph_and_derived_dip():
    renderer = make_renderer(
        symbols={1245: _tick_symbol()},
        attitude_dip_labels=True,
        exclude_text_categories=("产状",),
        native_text_layout=False,
    )
    wt = gpd.GeoDataFrame(
        {
            "point_type": [1, 0], "symbol_no": [1245, 0],
            "height": [5.0, 2.0], "width": [5.0, 2.0],
            "angle": [0.0, 0.0], "color": [1, 1],
            "CHFCEC": ["产状", "产状"], "CHFCED": ["", "51"],
            "GZBBAC": [0.0, 0.0], "GZBBAD": [51.0, 0.0],
        },
        geometry=[Point(0, 0), Point(10, 10)], crs="EPSG:32643",
    )
    fig, ax = make_axes()
    report = renderer.draw_layer(ax, wt)
    assert report["symbols"] == 1
    assert report["drawn"] == 1
    assert report["excluded_text"] == 1
    assert report["attitude_dip_label"] == 1
    assert [text.get_text() for text in ax.texts] == ["51"]
    fig.clear()


def test_render_uses_requested_dpi_and_axes_rect():
    renderer = make_renderer()
    result = renderer.render(
        [polygon_frame()], figsize=(4.0, 3.0), dpi=177,
        axes_rect=(0.1, 0.2, 0.5, 0.6),
    )
    assert result.figure.dpi == 177
    bounds = result.axes.get_position(original=True)
    assert (bounds.x0, bounds.y0, bounds.width, bounds.height) == pytest.approx(
        (0.1, 0.2, 0.5, 0.6)
    )
    result.figure.clear()
