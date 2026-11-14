"""Tests for the public original-graphic-library rendering API."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import LineString, Point, Polygon

import pymapgis.graphic as graphic
from pymapgis import GraphicLibraries, GraphicRenderer, render_graphic_map
from pymapgis.graphic import _annotation_to_mathtext, _StampBuffer
from pymapgis.linesty import Element as LineElement
from pymapgis.linesty import LineStyle, SubLine
from pymapgis.slib import Element, SubPath, Symbol


class FakeColorLib:
    def rgb01(self, number):
        return {
            0: (0.0, 0.0, 0.0),
            1: (0.0, 0.0, 0.0),
            4: (1.0, 1.0, 0.0),
            6: (1.0, 0.0, 0.0),
            9: (1.0, 1.0, 1.0),
        }.get(number)


class FakePcolorLib:
    def rgb01(self, number):
        return {
            2: (1.0, 0.0, 1.0),
            602: (1.0, 1.0, 178 / 255),
            652: (1.0, 1.0, 204 / 255),
        }.get(number)


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


def make_renderer(symbols=None, styles=None, **kwargs):
    libraries = GraphicLibraries(
        linesty=FakeLinestyLib(styles),
        subgraph=FakeSubgraphLib(symbols),
        fillgrph=FakeFillgrphLib(),
        color=FakeColorLib(),
    )
    kwargs.setdefault("map_units_per_mm", 0.25)
    return GraphicRenderer(libraries, **kwargs)


def _make_axes():
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure()
    FigureCanvasAgg(fig)
    return fig, fig.add_subplot(111)


def filled_symbol():
    return Symbol(
        no=41,
        type=1,
        n=8,
        header_len=14,
        header_u16=[1, 8, 0, 6, 0, 0, 1, 4],
        subpaths=[
            SubPath(
                points=[(0.0, 0.0), (0.5, 0.0), (0.0, 0.5), (0.0, 0.0)],
                closed=True,
            )
        ],
        elements=[Element(mode=0, fill_color=6, w2=0, w3=0, sub_start=0, sub_count=1)],
    )


def sample_layers():
    polygon = Polygon(
        [(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)],
        [[(1, 1), (1, 2), (2, 2), (2, 1), (1, 1)]],
    )
    wp = gpd.GeoDataFrame(
        {
            "fill_color": [6],
            "pattern": [0],
            "pattern_color": [0],
            "pattern_height": [0.0],
            "pattern_width": [0.0],
        },
        geometry=[polygon],
        crs="EPSG:32643",
    )
    wl = gpd.GeoDataFrame(
        {
            "linetype": [99],
            "aux_linetype": [0],
            "color": [1],
            "aux_color": [0],
            "width": [0.1],
            "x_coef": [1.0],
            "y_coef": [1.0],
        },
        geometry=[LineString([(0, 0), (1, 0.5), (2, 0)])],
        crs="EPSG:32643",
    )
    wt = gpd.GeoDataFrame(
        {
            "point_type": [1, 0, 0],
            "symbol_no": [41, 0, 0],
            "height": [1.0, 1.0, 1.0],
            "width": [1.0, 1.0, 1.0],
            "angle": [0.0, 0.0, 0.0],
            "color": [1, 1, 1],
            "CHFCED": ["", "Qp#-3#+pl+Qh#+eol", "hidden"],
            "CHFCEC": ["", "注记", "代号"],
        },
        geometry=[Point(3, 3), Point(0, 4), Point(1, 4)],
        crs="EPSG:32643",
    )
    return wp, wl, wt


@pytest.mark.parametrize("suffix", ["png", "pdf"])
def test_composite_render_api_and_output(tmp_path, suffix):
    wp, wl, wt = sample_layers()
    renderer = make_renderer(
        symbols={41: filled_symbol()},
        exclude_text_categories={"代号"},
        text_category_scales={"注记": 0.45},
    )
    output = tmp_path / ("map." + suffix)
    result = renderer.render([wt, wl, wp], output, figsize=(4, 4), dpi=50)

    assert output.is_file()
    assert output.read_bytes().startswith(b"\x89PNG" if suffix == "png" else b"%PDF")
    assert [report["kind"] for report in result.reports] == ["wp", "wl", "wt"]
    assert result.reports[0]["holes"] == 1
    assert result.reports[1]["fallback"] == 1
    assert result.reports[2]["symbols"] == 1
    assert result.reports[2]["text"] == 1
    assert result.reports[2]["excluded_text"] == 1

    # The fallback WL still uses every original coordinate, in original order.
    expected = np.asarray([(0, 0), (1, 0.5), (2, 0)])
    assert any(np.array_equal(line.get_xydata(), expected) for line in result.axes.lines)
    # The Subgraph Element contributes a Colorlib-red filled patch.
    assert any(np.allclose(patch.get_facecolor()[:3], (1, 0, 0)) for patch in result.axes.patches)
    xmin, ymin, xmax, ymax = result.bounds
    assert xmin < 0 and ymin < 0 and xmax > 4 and ymax > 4
    result.figure.clear()


def test_polygon_class_zero_is_not_drawn():
    wp, _, _ = sample_layers()
    wp["class"] = [0]
    renderer = make_renderer()
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure()
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    report = renderer.draw_layer(ax, wp)
    assert report["excluded_class"] == 1
    assert report["drawn"] == 0
    assert len(ax.patches) == 0
    fig.clear()


def test_symbol_pen_width_uses_native_value():
    renderer = make_renderer(symbols={41: filled_symbol()})
    wt = gpd.GeoDataFrame(
        {
            "point_type": [1], "symbol_no": [41], "height": [1.0],
            "width": [1.0], "angle": [0.0], "color": [1], "pen_width": [3.0],
        },
        geometry=[Point(0, 0)], crs="EPSG:32643",
    )
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure()
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    renderer.draw_layer(ax, wt)
    assert ax.lines[-1].get_linewidth() == pytest.approx(3.0 * graphic.MM_TO_PT)
    fig.clear()


def test_symbol_uniform_scale_preserves_arrowhead_symmetry():
    shaft = SubPath(points=[(-0.00018, -0.50126), (-0.00018, 0.49874)])
    head = SubPath(points=[
        (-0.25018, 0.12374),
        (-0.00018, 0.49874),
        (0.24982, 0.12374),
    ])
    symbol = Symbol(
        no=1894,
        type=2,
        n=10,
        header_len=8,
        header_u16=[2, 10, 0, 2],
        subpaths=[shaft, head],
    )
    renderer = make_renderer(symbols={1894: symbol})
    fig, ax = _make_axes()
    report = {"unknown_colors": {}, "overridden_colors": {}}
    assert renderer._draw_symbol(
        ax, 0, 0, 1894, 2.2502, 1.4885, 56.841, (0, 0, 0), 1, report
    )
    shaft_xy = ax.lines[0].get_xydata()
    assert np.linalg.norm(np.diff(shaft_xy, axis=0)[0]) == pytest.approx(1.4885)
    left, tip, right = ax.lines[-1].get_xydata()
    assert np.linalg.norm(left - tip) == pytest.approx(np.linalg.norm(right - tip))
    fig.clear()


def test_one_shot_convenience_api(tmp_path):
    wp, _, _ = sample_layers()
    libraries = make_renderer().libraries
    output = tmp_path / "one_shot.png"
    result = render_graphic_map(
        [wp],
        libraries,
        output,
        map_units_per_mm=0.25,
        figsize=(3, 3),
        dpi=40,
    )
    assert result.output == output
    assert output.stat().st_size > 100
    result.figure.clear()


def test_line_width_converts_display_pixels_to_typographic_points():
    solid = LineStyle(
        no=1,
        n_subs=1,
        sublines=[SubLine(n=1, length=24, f32_zone=[0.0, 0.0, 1.0, 0.0])],
    )
    renderer = make_renderer(styles={1: solid}, map_units_per_mm=1.0)
    wl = gpd.GeoDataFrame(
        {
            "linetype": [1], "aux_linetype": [0], "color": [1],
            "aux_color": [0], "width": [1.0], "x_coef": [1.0], "y_coef": [1.0],
        },
        geometry=[LineString([(0, 0), (100, 0)])], crs="EPSG:32643",
    )
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(10, 2), dpi=100)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 100)
    ax.set_ylim(-1, 1)
    renderer.draw_layer(ax, wl)
    pixels_per_unit = abs(
        ax.transData.transform((1, 0))[0] - ax.transData.transform((0, 0))[0]
    )
    assert ax.lines[0].get_linewidth() == pytest.approx(pixels_per_unit * 72 / 100)
    fig.clear()


def test_parallel_unconformity_uses_selected_subline_variant():
    sub0 = SubLine(
        n=3,
        length=68,
        elements=[
            LineElement(unit=5, marker=2, offset=0),
            LineElement(unit=0, marker=2, offset=4),
            LineElement(unit=0, marker=2, offset=8),
        ],
        f32_zone=[0.0, 0.0, 1.0, 0.0,
                  0.1, 0.1, 0.40312498807907104, 0.1,
                  0.6000000238418579, 0.10000000149011612,
                  0.8999999761581421, 0.10000000149011612],
    )
    sub1 = SubLine(
        n=4,
        length=90,
        elements=[LineElement(unit=0, marker=2, offset=4 * i) for i in range(4)],
        f32_zone=[0.0, 0.0, 0.4, 0.0,
                  0.1, 0.1, 0.3, 0.1,
                  0.7, 0.1, 0.9, 0.1,
                  0.6, 0.0, 1.0, 0.0],
    )
    style = LineStyle(no=48, n_subs=2, sublines=[sub0, sub1])
    renderer = make_renderer(styles={48: style}, map_units_per_mm=1.0)
    rhythm = renderer._rhythm(48)
    assert rhythm["period_mm"] == pytest.approx(1.0)
    assert rhythm["polylines"] == [
        [(0.0, 0.0), (1.0, 0.0)],
        [(0.1, 0.1), (sub0.f32_zone[6], 0.1)],
        [(sub0.f32_zone[8], sub0.f32_zone[9]),
         (sub0.f32_zone[10], sub0.f32_zone[11])],
    ]
    # sub1 is a different variant and must not be overlaid for 48|0.
    assert len(rhythm["polylines"]) == 3
    variant = renderer._payload_rhythm(style, subline=1)
    assert variant["period_mm"] == pytest.approx(1.2)
    assert variant["polylines"][0] == [(0.0, 0.0), (0.4, 0.0)]
    # 已裁定的 48|1 变体必须使用 sub1，而非把 sub0/sub1 混画。
    adjudicated = renderer._rhythm(48, 1)
    assert adjudicated["period_mm"] == pytest.approx(1.0)
    assert len(adjudicated["polylines"]) == 4

    # The SVG reference's 48|0 dash lengths come from the library payload,
    # not Matplotlib's screen-space dash pattern. X/Y coefficients scale the
    # longitudinal rhythm and transverse offset respectively.
    wl = gpd.GeoDataFrame(
        {
            "linetype": [48], "aux_linetype": [0], "color": [1],
            "aux_color": [0], "width": [0.1],
            "x_coef": [2.0], "y_coef": [2.0],
        },
        geometry=[LineString([(0, 0), (2, 0)])], crs="EPSG:32643",
    )
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure()
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    report = renderer.draw_layer(ax, wl)
    assert report["pattern"] == 1
    segments = [line.get_xydata() for line in ax.lines]
    expected = [
        [(0.0, 0.0), (2.0, 0.0)],
        [(0.2, 0.2), (2 * sub0.f32_zone[6], 0.2)],
        [(1.2, 0.2), (1.8, 0.2)],
    ]
    assert len(segments) == len(expected)
    for actual, wanted in zip(segments, expected):
        np.testing.assert_allclose(actual, wanted, atol=1e-7)
    assert all(line.get_linestyle() == "-" for line in ax.lines)
    fig.clear()

    # Curved base lines retain interior source vertices instead of becoming
    # straight one-period chords.
    curved = wl.copy()
    curved.geometry = [LineString([(0, 0), (1, 1), (2, 0)])]
    fig = Figure()
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    renderer.draw_layer(ax, curved)
    assert any(
        np.allclose(point, (1.0, 1.0))
        for line in ax.lines for point in line.get_xydata()
    )
    fig.clear()


def test_supported_but_unresolved_aux_variant_stays_unresolved():
    style = LineStyle(
        no=2,
        n_subs=3,
        sublines=[SubLine(n=1, length=24, f32_zone=[0.0, 0.0, 1.0, 0.0])] * 3,
    )
    renderer = make_renderer(styles={2: style})
    assert renderer._rhythm(2, 2) is None
    assert renderer._rhythm(2, 3) is None


def test_auxiliary_style_is_decoded_as_independent_record():
    """Complete feature rendering must not discard the independent aux record."""
    solid = LineStyle(
        no=1,
        n_subs=1,
        sublines=[SubLine(n=1, length=24, f32_zone=[0.0, 0.0, 1.0, 0.0])],
    )
    renderer = make_renderer(styles={1: solid})
    wl = gpd.GeoDataFrame(
        {
            "linetype": [99],
            "aux_linetype": [1],
            "color": [1],
            "aux_color": [6],
            "width": [0.1],
            "x_coef": [1.0],
            "y_coef": [1.0],
        },
        geometry=[LineString([(0, 0), (1, 0)])],
        crs="EPSG:32643",
    )
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure()
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    report = renderer.draw_layer(ax, wl)
    assert report["fallback"] == 1
    assert report["aux_solid"] == 1
    # The auxiliary solid record is drawn with aux_color, not discarded by
    # feature_rhythm(main, aux)'s single-record selection semantics.
    assert ax.lines[-1].get_color() == (1.0, 0.0, 0.0)
    fig.clear()


def test_aux_subline_variant_does_not_add_independent_solid():
    """16|1 is the reference's large-dot variant, not dots plus a solid line."""
    dot0 = SubLine(
        n=1, length=26,
        elements=[LineElement(unit=258, marker=1, offset=0)],
        f32_zone=[0.5, 0.0, 0.044],
    )
    dot1 = SubLine(
        n=1, length=26,
        elements=[LineElement(unit=3, marker=1, offset=0)],
        f32_zone=[0.5, 0.0, 0.078125],
    )
    solid = LineStyle(
        no=1, n_subs=1,
        sublines=[SubLine(n=1, length=24, f32_zone=[0.0, 0.0, 1.0, 0.0])],
    )
    style = LineStyle(no=16, n_subs=2, sublines=[dot0, dot1])
    renderer = make_renderer(styles={1: solid, 16: style}, map_units_per_mm=1.0)
    wl = gpd.GeoDataFrame(
        {
            "linetype": [16], "aux_linetype": [1], "color": [1],
            "aux_color": [0], "width": [0.1],
            "x_coef": [1.0], "y_coef": [1.0],
        },
        geometry=[LineString([(0, 0), (1, 0)])], crs="EPSG:32643",
    )
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure()
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    report = renderer.draw_layer(ax, wl)
    assert report["pattern"] == 1
    assert "aux_solid" not in report and "aux_fallback" not in report
    assert not ax.lines
    assert len(ax.collections[0].get_offsets()) == 1
    fig.clear()


def test_structural_aux_variant_selects_matching_subline():
    sub0 = SubLine(
        n=1, length=30,
        elements=[LineElement(unit=0, marker=2, offset=0)],
        f32_zone=[0.0, 0.0, 0.4, 0.0],
    )
    sub1 = SubLine(
        n=1, length=30,
        elements=[LineElement(unit=0, marker=2, offset=0)],
        f32_zone=[0.1, 0.1, 0.8, 0.1],
    )
    style = LineStyle(no=900, n_subs=2, sublines=[sub0, sub1])
    renderer = make_renderer(styles={900: style})
    rhythm = renderer._rhythm(900, 1)
    assert rhythm["polylines"] == [[(0.1, 0.1), (0.8, 0.1)]]
    assert rhythm["period_mm"] == pytest.approx(0.8)


def test_structural_rhythm_overlays_all_solid_pens():
    """All-solid pen records are overlays, not alternative subline variants."""
    style = LineStyle(
        no=900,
        n_subs=2,
        sublines=[
            SubLine(n=1, length=24, f32_zone=[0.0, 0.0, 0.4, 0.0]),
            SubLine(n=1, length=24, f32_zone=[0.0, 0.2, 0.8, 0.2]),
        ],
    )
    renderer = make_renderer(styles={900: style})
    rhythm = renderer._rhythm(900)
    assert rhythm["kind"] == "payload"
    assert rhythm["polylines"] == [
        [(0.0, 0.0), (0.4, 0.0)],
        [(0.0, 0.2), (0.8, 0.2)],
    ]
    assert rhythm["period_mm"] == pytest.approx(0.8)


def test_unknown_dot_fill_is_reported_not_adjudicated():
    style = LineStyle(
        no=900,
        n_subs=1,
        sublines=[
            SubLine(
                n=1,
                length=26,
                elements=[LineElement(unit=258, marker=1, offset=0)],
                f32_zone=[0.5, 0.0, 0.05],
            )
        ],
    )
    renderer = make_renderer(styles={900: style})
    wl = gpd.GeoDataFrame(
        {
            "linetype": [900],
            "aux_linetype": [0],
            "color": [1],
            "aux_color": [0],
            "width": [0.1],
            "x_coef": [1.0],
            "y_coef": [1.0],
        },
        geometry=[LineString([(0, 0), (1, 0)])],
        crs="EPSG:32643",
    )
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure()
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    report = renderer.draw_layer(ax, wl)
    assert report["pattern"] == 1
    assert report["unknown_fill"] == 1
    assert "solid" not in report
    fig.clear()


def test_stamp_clips_partial_cycle_at_original_endpoint():
    renderer = make_renderer()
    buffer = _StampBuffer()
    rhythm = {
        "kind": "payload",
        "period_mm": 1.0,
        "lines": [],
        "polylines": [[(0.0, 0.0), (1.0, 0.0)]],
        "dots": [(0.5, 0.0, 0.05)],
        "fills": [],
    }
    renderer._stamp_along(
        np.asarray([(0.0, 0.0), (1.4, 0.0)]),
        rhythm,
        xc=1.0,
        yc=1.0,
        unit=1.0,
        color=(0, 0, 0),
        line_width=1.0,
        min_radius=0.001,
        buffer=buffer,
    )
    segments = np.concatenate(buffer.segments)
    assert segments[..., 0].min() >= 0.0
    assert segments[..., 0].max() <= 1.4
    assert np.any(np.isclose(segments[..., 0], 1.4))
    dots = np.concatenate(buffer.dots)
    assert dots[:, 0].tolist() == [0.5]
    assert not np.any(np.linalg.norm(np.diff(segments, axis=1), axis=-1) == 0)


def test_stamp_clips_partial_fill_at_original_endpoint():
    renderer = make_renderer()
    buffer = _StampBuffer()
    rhythm = {
        "kind": "payload",
        "period_mm": 1.0,
        "lines": [],
        "polylines": [],
        "dots": [],
        "fills": [[(0.0, 0.0), (1.0, 0.2), (1.0, -0.2)]],
    }
    renderer._stamp_along(
        np.asarray([(0.0, 0.0), (0.75, 0.0)]),
        rhythm,
        xc=1.0,
        yc=1.0,
        unit=1.0,
        color=(0, 0, 0),
        line_width=1.0,
        min_radius=0.001,
        buffer=buffer,
    )
    assert buffer.fills
    vertices = np.concatenate(buffer.fills)
    assert vertices[:, 0].min() >= 0.0
    assert vertices[:, 0].max() <= 0.75
    assert np.any(np.isclose(vertices[:, 0], 0.75))


def test_stamp_retains_origin_tick_without_end_seam_duplicate():
    renderer = make_renderer()
    buffer = _StampBuffer()
    rhythm = {
        "kind": "tick_dash_interleave",
        "period_mm": 1.0,
        "lines": [],
        "polylines": [
            [(0.0, 0.0), (1.0, 0.0)],
            [(0.0, 0.0), (0.0, 0.125)],
        ],
        "dots": [],
        "fills": [],
    }
    renderer._stamp_along(
        np.asarray([(0.0, 0.0), (2.0, 0.0)]),
        rhythm,
        xc=1.0, yc=1.0, unit=1.0, color=(0, 0, 0),
        line_width=1.0, min_radius=0.001, buffer=buffer,
    )
    segments = np.concatenate(buffer.segments)
    vertical = [
        segment for segment in segments
        if segment[0, 0] == segment[1, 0] and segment[0, 1] != segment[1, 1]
    ]
    assert len(vertical) == 2
    assert [segment[0, 0] for segment in vertical] == [0.0, 1.0]
    assert all(segment[1, 1] == pytest.approx(0.125) for segment in vertical)


def test_tooth_dash_baseline_preserves_every_source_vertex():
    renderer = make_renderer()
    buffer = _StampBuffer()
    points = np.asarray([(0.0, 0.0), (0.5, 0.5), (1.0, 0.0), (1.5, 0.5)])
    rhythm = {
        "kind": "tooth_dash", "period_mm": 1.0, "lines": [],
        "polylines": [[(0.0, 0.0), (1.0, 0.0)]],
        "dots": [], "fills": [[(0.45, 0.0), (0.5, 0.15), (0.55, 0.0)]],
    }
    renderer._stamp_along(
        points, rhythm, xc=1.0, yc=1.0, unit=1.0, color=(0, 0, 0),
        line_width=1.0, min_radius=0.001, buffer=buffer,
    )
    segments = np.concatenate(buffer.segments)
    endpoints = np.concatenate(segments)
    for vertex in points:
        assert np.any(np.all(np.isclose(endpoints, vertex, atol=1e-12), axis=1)), vertex
    assert buffer.fills  # 齿形仍独立叠加


def test_constant_offset_stroke_uses_full_offset_curve():
    from shapely.geometry import LineString

    renderer = make_renderer()
    buffer = _StampBuffer()
    points = np.asarray([(0.0, 0.0), (0.5, 0.5), (1.0, 0.0), (1.5, 0.5)])
    rhythm = {
        "kind": "parallel", "period_mm": 10.0, "lines": [],
        "polylines": [[(0.0, 0.1), (10.0, 0.1)]], "dots": [], "fills": [],
    }
    renderer._stamp_along(
        points, rhythm, xc=1.0, yc=1.0, unit=1.0, color=(0, 0, 0),
        line_width=1.0, min_radius=0.001, buffer=buffer,
    )
    endpoints = np.concatenate(np.concatenate(buffer.segments))
    expected = LineString(points).offset_curve(0.1)
    for vertex in np.asarray(expected.coords):
        assert np.any(np.all(np.isclose(endpoints, vertex, atol=1e-9), axis=1)), vertex


def test_subgraph_arc_uses_ccw_wraparound():
    arc = SubPath(points=[(0, 0), (0.5, -0.0), (180.0, 0)])
    arc.arc = (0.0, 0.0, 0.5, 360.0, 180.0)
    symbol = Symbol(no=25, type=46, n=6, header_len=8, header_u16=[46, 6, 0, 3], subpaths=[arc])
    renderer = make_renderer(symbols={25: symbol})
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(2, 2))
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    report = {"unknown_colors": {}, "overridden_colors": {}}
    assert renderer._draw_symbol(ax, 0, 0, 25, 1, 1, 0, (0, 0, 0), 1, report)
    xy = ax.lines[-1].get_xydata()
    # 360°→180° must sweep through 450°, not backwards through 270°.
    assert xy[:, 1].min() >= -1e-12
    assert xy[:, 1].max() == pytest.approx(0.5)
    fig.clear()


def test_nested_annotation_scripts_are_valid_mathtext():
    label = _annotation_to_mathtext("Qp#-3#+pl+Qh#+eol")
    from matplotlib.mathtext import MathTextParser

    MathTextParser("agg").parse(label)
    assert "Qp" in label and "eol" in label


@pytest.mark.parametrize("spacing,compressed", [(0.5, False), (-0.5, True)])
def test_native_text_advance_and_compression(spacing, compressed):
    wt = gpd.GeoDataFrame(
        {
            "point_type": [0], "CHFCED": ["AB"], "CHFCEC": ["注记"],
            "height": [2.0], "width": [2.0], "spacing": [spacing],
            "angle": [0.0], "color": [1], "font_zh": [1], "font_en": [0],
            "font_style": [0],
        },
        geometry=[Point(0, 0)], crs="EPSG:32643",
    )
    renderer = make_renderer()
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure()
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    report = renderer.draw_layer(ax, wt)
    assert len(ax.texts) == 2
    assert ax.texts[1].get_position()[0] == pytest.approx((2.0 + spacing) * 0.25)
    assert report["spaced_text"] == 1
    assert report.get("compressed_text", 0) == int(compressed)
    fig.clear()


def test_attitude_text_scale_compounds_with_category_scale():
    wt = gpd.GeoDataFrame(
        {
            "point_type": [0, 0, 0, 0],
            "CHFCED": ["60", "60", "60", "60"],
            "CHFCEC": ["产状", "断层产状", "注记", "断层辅助点"],
            "height": [5.0, 5.0, 5.0, 5.0],
            "width": [2.0, 2.0, 2.0, 2.0],
            "spacing": [0.5, 0.5, 0.5, 0.5],
            "angle": [0.0, 0.0, 0.0, 0.0],
            "color": [1, 1, 1, 1],
        },
        geometry=[Point(0, 0), Point(0, 1), Point(0, 2), Point(0, 3)],
        crs="EPSG:32643",
    )
    renderer = make_renderer(text_category_scales={"产状": 0.5})
    fig, ax = _make_axes()
    renderer.draw_layer(ax, wt)
    base = 5.0 * graphic.MM_TO_PT
    assert ax.texts[0].get_fontsize() == pytest.approx(base * 0.5 * 0.3)
    assert ax.texts[2].get_fontsize() == pytest.approx(base * 0.3)
    assert ax.texts[4].get_fontsize() == pytest.approx(base)
    assert ax.texts[6].get_fontsize() == pytest.approx(base * 0.3)
    assert ax.texts[1].get_position()[0] == pytest.approx(2.5 * 0.25 * 0.5 * 0.3)
    assert ax.texts[3].get_position()[0] == pytest.approx(2.5 * 0.25 * 0.3)
    assert ax.texts[5].get_position()[0] == pytest.approx(2.5 * 0.25)
    assert ax.texts[7].get_position()[0] == pytest.approx(2.5 * 0.25 * 0.3)
    fig.clear()


def test_polygon_label_scale_applies_to_caller_base_fontsize():
    wp = gpd.GeoDataFrame(
        {
            "fill_color": [6],
            "pattern": [0],
            "pattern_color": [0],
            "pattern_height": [0.0],
            "pattern_width": [0.0],
            "QDUECC": ["Qh"],
        },
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:32643",
    )
    renderer = make_renderer(polygon_label_fontsize=5.0)
    fig, ax = _make_axes()
    renderer.draw_layer(ax, wp)
    assert ax.texts[0].get_fontsize() == pytest.approx(3.5)
    fig.clear()


def test_geosciml_polygon_labels_replace_wt_unit_annotations():
    wp = gpd.GeoDataFrame(
        {
            "fill_color": [6], "pattern": [0], "pattern_color": [0],
            "pattern_height": [0.0], "pattern_width": [0.0],
            "QDUECC": ["→Qp↓3→pal"],
        },
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])], crs="EPSG:32643",
    )
    wt = gpd.GeoDataFrame(
        {
            "point_type": [0], "CHFCED": ["Qh"], "CHFCEC": ["代号"],
            "height": [2.0], "width": [2.0], "spacing": [0.0],
            "angle": [0.0], "color": [1], "font_zh": [1], "font_en": [0],
            "font_style": [0],
        },
        geometry=[Point(0.5, 0.5)], crs="EPSG:32643",
    )
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    renderer = make_renderer()
    fig = Figure()
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    reports = renderer.draw_layers(ax, [wt, wp])
    assert reports[0]["polygon_label"] == 1
    assert reports[1]["excluded_text"] == 1
    assert len(ax.texts) == 1
    label = ax.texts[0]
    assert label.get_text() == r"$\mathrm{Qp_{3}pal}$"
    assert label.get_position() == (0.5, 0.5)
    assert label.get_fontsize() == pytest.approx(4.5 * 0.7)
    assert label.get_bbox_patch().get_alpha() == 0.5
    fig.clear()

    # Explicit compatibility switch: no polygon labels, legacy WT annotations.
    legacy = make_renderer(polygon_labels=False, exclude_text_categories=())
    fig = Figure()
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    reports = legacy.draw_layers(ax, [wt, wp])
    assert "polygon_label" not in reports[0]
    assert reports[1]["text"] == 1
    assert len(ax.texts) == 2
    fig.clear()


def test_geosciml_polygon_label_uses_greek_font():
    wp = gpd.GeoDataFrame(
        {
            "fill_color": [6], "pattern": [0], "pattern_color": [0],
            "pattern_height": [0.0], "pattern_width": [0.0],
            "QDUECC": ["→γδC↓2"],
        },
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])], crs="EPSG:32643",
    )
    renderer = make_renderer()
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure()
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    report = renderer.draw_layer(ax, wp)
    assert report["polygon_label"] == 1
    assert len(ax.texts) == 1
    assert ax.texts[0].get_fontfamily() == ["Times New Roman"]
    assert r"\gamma{}\delta{}" in ax.texts[0].get_text()
    fig.clear()


def test_annotation_scripts_and_font_maps():
    wt = gpd.GeoDataFrame(
        {
            "point_type": [0], "CHFCED": ["δ#-1"], "CHFCEC": ["代号"],
            "height": [2.0], "width": [2.0], "spacing": [0.5],
            "angle": [0.0], "color": [1], "font_zh": [4], "font_en": [0],
            "font_style": [0],
        },
        geometry=[Point(0, 0)], crs="EPSG:32643",
    )
    renderer = make_renderer(
        font_zh_map={4: "SimHei"},
        font_en_map={0: "DejaVu Sans"},
        font_style_map={0: {"style": "normal"}},
        exclude_text_categories=(),
    )
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure()
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    report = renderer.draw_layer(ax, wt)
    assert len(ax.texts) == 2
    assert ax.texts[0].get_fontfamily() == ["SimHei"]
    assert ax.texts[1].get_fontfamily() == ["DejaVu Sans"]
    assert ax.texts[1].get_position()[1] < ax.texts[0].get_position()[1]
    assert ax.texts[1].get_fontsize() < ax.texts[0].get_fontsize()
    assert report["script_text"] == 1
    assert report["unknown_fonts"] == {}
    fig.clear()


def test_crs_unit_inference_and_extended_color_override():
    wp, _, _ = sample_layers()
    renderer = GraphicRenderer(
        make_renderer().libraries,
        scale=250000,
        color_overrides={1167: (0.0, 0.0, 1.0)},
    )
    assert renderer._unit(wp) == pytest.approx(250.0)
    geographic = wp.to_crs("EPSG:4326")
    assert renderer._unit(geographic) == pytest.approx(250 / 111320)
    report = {"unknown_colors": {}, "overridden_colors": {}}
    assert renderer._color(1167, report, role="fill") == (0.0, 0.0, 1.0)
    assert report["overridden_colors"] == {"1167": 1}
    assert renderer._color(9999, report) == renderer.fallback_color
    assert report["unknown_colors"] == {"9999": 1}


def test_extended_color_override_is_fill_only():
    renderer = make_renderer(color_overrides={6: (0.0, 0.0, 1.0)})
    report = {"unknown_colors": {}, "overridden_colors": {}}
    assert renderer._color(6, report, role="fill") == (0.0, 0.0, 1.0)
    assert renderer._color(6, report, role="feature") == (1.0, 0.0, 0.0)
    assert report["overridden_colors"] == {"6": 1}


def test_auto_fill_library_uses_pcolor_only_for_wp_fills():
    base = make_renderer().libraries
    libraries = GraphicLibraries(
        linesty=base.linesty,
        subgraph=base.subgraph,
        fillgrph=base.fillgrph,
        color=base.color,
        pcolor=FakePcolorLib(),
    )
    renderer = GraphicRenderer(libraries)
    report = {"unknown_colors": {}, "overridden_colors": {}}
    assert renderer._color(602, report, role="fill") == (1.0, 1.0, 178 / 255)
    assert renderer._color(652, report, role="fill") == (1.0, 1.0, 204 / 255)
    assert renderer._color(6, report, role="feature") == (1.0, 0.0, 0.0)
    assert renderer._color(6, report, role="pattern") == (1.0, 0.0, 0.0)
    assert report["unknown_colors"] == {}

    legacy = GraphicRenderer(libraries, fill_library="color")
    assert legacy._color(6, report, role="fill") == (1.0, 0.0, 0.0)


def test_unit_color_override_precedes_numeric_fill_override():
    polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    wp = gpd.GeoDataFrame(
        {
            "QDUECC": ["→Qp↓3↑pal", "Other"],
            "fill_color": [602, 602],
            "pattern": [0, 0],
            "pattern_color": [0, 0],
            "pattern_height": [0.0, 0.0],
            "pattern_width": [0.0, 0.0],
        },
        geometry=[polygon, polygon],
        crs="EPSG:32643",
    )
    renderer = make_renderer(
        color_overrides={602: (0.0, 0.0, 1.0)},
        unit_color_overrides={"Qp3pal": (1.0, 217 / 255, 102 / 255)},
    )
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure()
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    report = renderer.draw_layer(ax, wp)
    assert report["unit_overrides"] == {"Qp3pal": 1}
    facecolors = ax.collections[0].get_facecolor()
    assert np.allclose(facecolors[0][:3], (1.0, 217 / 255, 102 / 255))
    assert np.allclose(facecolors[1][:3], (0.0, 0.0, 1.0))
    fig.clear()


def test_library_directory_validation_and_loading(tmp_path, monkeypatch):
    with pytest.raises(FileNotFoundError) as error:
        GraphicLibraries.from_directory(tmp_path)
    for name in ("LINESTY.lib", "Subgraph.lib", "Fillgrph.lib", "Colorlib.lib"):
        assert name in str(error.value)
        (tmp_path / name).touch()
    (tmp_path / "Pcolor.lib").touch()

    for class_name in ("LinestyLib", "SubgraphLib", "FillgrphLib", "ColorLib", "PcolorLib"):
        monkeypatch.setattr(
            graphic, class_name, lambda path, name=class_name, **kwargs: (name, Path(path).name)
        )
    libraries = GraphicLibraries.from_directory(tmp_path)
    assert libraries.linesty == ("LinestyLib", "LINESTY.lib")
    assert libraries.subgraph == ("SubgraphLib", "Subgraph.lib")
    assert libraries.fillgrph == ("FillgrphLib", "Fillgrph.lib")
    assert libraries.color == ("ColorLib", "Colorlib.lib")
    assert libraries.pcolor == ("PcolorLib", "Pcolor.lib")
    assert libraries.directory == tmp_path


def test_multi_part_offset_curves_are_supported():
    renderer = make_renderer()
    points = np.asarray([(0, 0), (1, 1), (2, 0), (1, 0.1), (0, 1)])
    from shapely.geometry import MultiLineString

    # Construct the multipart input explicitly: GEOS versions differ in whether
    # offsetting this self-crossing source splits it into one or two line strings.
    curve = MultiLineString([[(0, 0), (1, 1)], [(1, 1), (2, 0)]])
    assert len(curve.geoms) == 2
    parts = renderer._substring_parts(curve, 0.0, curve.length)
    assert len(parts) == 2
    assert sum(part.length for part in parts) == pytest.approx(curve.length)

    rhythm = {"period_mm": 1.0, "lines": [(0.0, 1.0, 0.1)]}
    fig, ax = _make_axes()
    renderer._draw_raised_parallel(ax, points, rhythm, (0, 0, 0), 1, 1, 1, 1)
    assert ax.lines
    fig.clear()

    buffer = _StampBuffer()
    renderer._stamp_along(
        points,
        {
            "kind": "parallel",
            "period_mm": 1.0,
            "polylines": [[(0.0, 0.1), (1.0, 0.1)]],
            "dots": [],
            "fills": [],
        },
        1,
        1,
        1,
        (0, 0, 0),
        1,
        0.01,
        buffer,
    )
    assert buffer.segments


def test_annotation_special_characters_survive_mathtext_and_save(tmp_path):
    from matplotlib.mathtext import MathTextParser

    raw = "a_b^{}$%\\#&~#-1"
    MathTextParser("agg").parse(_annotation_to_mathtext(raw))
    wt = gpd.GeoDataFrame(
        {
            "point_type": [0],
            "CHFCED": [raw],
            "CHFCEC": ["注记"],
            "height": [2.0],
            "width": [2.0],
            "spacing": [0.0],
            "angle": [0.0],
            "color": [1],
        },
        geometry=[Point(0, 0)],
        crs="EPSG:32643",
    )
    output = tmp_path / "special-text.png"
    result = make_renderer().render([wt], output)
    assert output.is_file()
    result.figure.clear()


def test_symbol_fill_uses_descriptor_for_triangle_and_arc():
    triangle = SubPath(points=[(0, 0), (0.2, 0), (0, 0.2)])
    arc = SubPath(points=[(0, 0), (0.5, 0), (180, 360)])
    arc.arc = (0, 0, 0.5, 180, 360)
    symbol = Symbol(
        no=42,
        type=2,
        n=6,
        header_len=8,
        header_u16=[2, 6, 0, 2],
        subpaths=[triangle, arc],
        elements=[Element(mode=0, fill_color=6, w2=0, w3=0, sub_start=0, sub_count=2)],
    )
    renderer = make_renderer(symbols={42: symbol})
    fig, ax = _make_axes()
    report = {"unknown_colors": {}, "overridden_colors": {}}
    assert renderer._draw_symbol(ax, 0, 0, 42, 1, 1, 0, (0, 0, 0), 1, report)
    assert len(ax.patches) == 2
    assert all(np.allclose(patch.get_facecolor()[:3], (1, 0, 0)) for patch in ax.patches)
    fig.clear()


def test_circle_dots_keep_shape_and_fill_state():
    mixed = GraphicRenderer._normalise_rhythm(
        {"kind": "mixed_dash", "period_mm": 1, "dots": [(0.25, -0.1, 0.05)]}
    )
    assert mixed["dots"] == [(0.25, -0.1, 0.05)]
    assert mixed["polylines"] == []

    rhythm = GraphicRenderer._normalise_rhythm(
        {
            "kind": "filled_rect_dot_bars",
            "period_mm": 1,
            "dots": [(0.25, 0, 0.05, False), (0.75, 0, 0.05, True)],
        }
    )
    assert [dot[3] for dot in rhythm["dots"]] == [False, True]
    renderer = make_renderer()
    buffer = _StampBuffer()
    renderer._stamp_along(
        np.asarray([(0, 0), (1, 0)]),
        rhythm,
        1,
        1,
        1,
        (1, 0, 0),
        0.5,
        0.01,
        buffer,
    )
    assert buffer.dot_filled == [False, True]
    fig, ax = _make_axes()
    renderer._flush_stamps(ax, buffer, 100)
    dots = ax.collections[0]
    assert dots.get_facecolors()[:, 3].tolist() == [0, 1]
    assert dots.get_edgecolors()[:, 3].tolist() == [1, 0]
    fig.clear()


def test_payload_period_includes_negative_extent():
    from types import SimpleNamespace

    subline = SimpleNamespace(
        is_solid=False,
        period_mm=None,
        parameter_geometry=lambda: [("polyline", [(-2.0, 0.0), (3.0, 0.0)])],
    )
    style = SimpleNamespace(sublines=[subline])
    rhythm = GraphicRenderer._payload_rhythm(style)
    assert rhythm["period_mm"] == pytest.approx(5.0)


def test_zero_width_and_coefficients_are_not_replaced(monkeypatch):
    solid = LineStyle(
        no=1,
        n_subs=1,
        sublines=[SubLine(n=1, length=24, f32_zone=[0.0, 0.0, 1.0, 0.0])],
    )
    renderer = make_renderer(styles={1: solid}, line_min_pt=0.05)
    wl = gpd.GeoDataFrame(
        {
            "linetype": [1],
            "aux_linetype": [0],
            "color": [1],
            "width": [0.0],
            "x_coef": [1.0],
            "y_coef": [1.0],
        },
        geometry=[LineString([(0, 0), (1, 0)])],
        crs="EPSG:32643",
    )
    fig, ax = _make_axes()
    renderer.draw_layer(ax, wl)
    assert ax.lines[0].get_linewidth() == pytest.approx(0.05)
    fig.clear()

    patterned = wl.copy()
    patterned["x_coef"] = [0.0]
    patterned["y_coef"] = [0.0]
    monkeypatch.setattr(
        renderer,
        "_rhythm",
        lambda number, aux=0: {
            "kind": "payload",
            "period_mm": 1.0,
            "polylines": [[(0, 0), (1, 0)]],
            "dots": [],
            "fills": [],
        },
    )
    fig, ax = _make_axes()
    report = renderer.draw_layer(ax, patterned)
    assert report["empty_pattern"] == 1
    assert "pattern" not in report
    assert not ax.lines and not ax.collections
    fig.clear()


def test_tile_mask_has_exact_requested_size(monkeypatch):
    monkeypatch.setattr(
        graphic,
        "pattern_geometry",
        lambda library, number: {
            "fill_polygons": [[(0.1, 0.1), (0.9, 0.1), (0.9, 0.9)]],
            "polylines": [],
            "circles": [],
            "arcs": [],
        },
    )
    renderer = make_renderer(tile_pixels=29)
    assert renderer._tile_mask(1).shape == (29, 29)


def test_pattern_byte_limit_prevents_large_allocation(monkeypatch):
    monkeypatch.setattr(
        graphic,
        "pattern_geometry",
        lambda library, number: {
            "fill_polygons": [[(0.1, 0.1), (0.9, 0.1), (0.9, 0.9)]],
            "polylines": [],
            "circles": [],
            "arcs": [],
        },
    )
    renderer = make_renderer(tile_pixels=4, max_pattern_bytes=1)
    fig, ax = _make_axes()
    outcome = renderer._draw_pattern(
        ax,
        Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
        1,
        (0, 0, 0),
        1,
        1,
    )
    assert outcome == "too_large"
    assert not ax.images
    fig.clear()


def test_bare_string_parameters_are_single_values():
    renderer = make_renderer(
        exclude_text_categories="代号",
        unit_code_fields="QDUECC",
        polygon_label_fields="QDUECC_eff",
    )
    assert renderer.exclude_text_categories == {"代号"}
    assert renderer.unit_code_fields == ("QDUECC",)
    assert renderer.polygon_label_fields == ("QDUECC_eff",)


def test_aux_flag_disables_residual_auxiliary_style(monkeypatch):
    renderer = make_renderer()
    calls = []
    monkeypatch.setattr(
        renderer,
        "_rhythm",
        lambda number, aux=0: calls.append((number, aux)) or {"kind": "solid_pen"},
    )
    wl = gpd.GeoDataFrame(
        {
            "linetype": [1],
            "aux_linetype": [7],
            "aux_flag": [1],
            "color": [1],
            "width": [0.1],
            "x_coef": [1.0],
            "y_coef": [1.0],
        },
        geometry=[LineString([(0, 0), (1, 0)])],
        crs="EPSG:32643",
    )
    fig, ax = _make_axes()
    report = renderer.draw_layer(ax, wl)
    assert calls == [(1, 0)]
    assert "aux_pattern" not in report
    fig.clear()


@pytest.mark.parametrize(
    "color,transparent,expected_collections", [(9, 0, 1), (9, 1, 0), (6, 1, 1)]
)
def test_transparent_output_skips_only_white_fills(
    monkeypatch, color, transparent, expected_collections
):
    renderer = make_renderer()
    monkeypatch.setattr(
        renderer,
        "_rhythm",
        lambda number, aux=0: {
            "kind": "payload",
            "period_mm": 1.0,
            "polylines": [],
            "dots": [],
            "fills": [[(0, 0), (0.5, 0), (0, 0.5)]],
            "unknown_fills": 0,
        },
    )
    wl = gpd.GeoDataFrame(
        {
            "linetype": [1],
            "aux_linetype": [0],
            "color": [color],
            "width": [0.1],
            "x_coef": [1.0],
            "y_coef": [1.0],
            "transparent": [transparent],
        },
        geometry=[LineString([(0, 0), (1, 0)])],
        crs="EPSG:32643",
    )
    fig, ax = _make_axes()
    renderer.draw_layer(ax, wl)
    assert len(ax.collections) == expected_collections
    fig.clear()


def test_library_directory_forwards_channel_order(tmp_path, monkeypatch):
    for name in ("LINESTY.lib", "Subgraph.lib", "Fillgrph.lib", "Colorlib.lib", "Pcolor.lib"):
        (tmp_path / name).touch()
    for name in ("LinestyLib", "SubgraphLib", "FillgrphLib"):
        monkeypatch.setattr(graphic, name, lambda path: object())
    seen = {}

    def fake_color(path, **kwargs):
        seen["color"] = kwargs["channel_order"]
        return object()

    def fake_pcolor(path, **kwargs):
        seen["pcolor"] = kwargs["channel_order"]
        return object()

    monkeypatch.setattr(graphic, "ColorLib", fake_color)
    monkeypatch.setattr(graphic, "PcolorLib", fake_pcolor)
    GraphicLibraries.from_directory(tmp_path, channel_order="YMCK")
    assert seen == {"color": "YMCK", "pcolor": "YMCK"}


def test_plain_dollar_text_never_enters_mathtext_mode(tmp_path):
    raw = "a$b$c"
    wt = gpd.GeoDataFrame(
        {
            "point_type": [0],
            "CHFCED": [raw],
            "CHFCEC": ["注记"],
            "height": [3.0],
            "width": [3.0],
            "spacing": [0.0],
            "angle": [0.0],
            "color": [1],
        },
        geometry=[Point(0, 0)],
        crs="EPSG:32643",
    )
    renderer = make_renderer(native_text_layout=False)
    result = renderer.render([wt], tmp_path / "plain-dollar.png")
    assert result.axes.texts[0].get_text() == raw
    assert not result.axes.texts[0].get_parse_math()
    result.figure.clear()

    native = make_renderer(native_text_layout=True)
    result = native.render([wt], tmp_path / "native-dollar.png")
    assert all(not text.get_parse_math() for text in result.axes.texts)
    result.figure.clear()


def test_one_shot_forwards_channel_order(monkeypatch, tmp_path):
    wp, _, _ = sample_layers()
    libraries = make_renderer().libraries
    seen = {}

    def from_directory(path, **kwargs):
        seen.update(kwargs)
        return libraries

    monkeypatch.setattr(GraphicLibraries, "from_directory", from_directory)
    result = render_graphic_map(
        [wp],
        "ignored",
        tmp_path / "channel.png",
        channel_order="YMCK",
        map_units_per_mm=0.25,
    )
    assert seen == {"channel_order": "YMCK"}
    result.figure.clear()
    with pytest.raises(ValueError, match="only valid"):
        render_graphic_map([wp], libraries, channel_order="YMCK")


def test_nonpositive_text_scales_are_rejected():
    with pytest.raises(ValueError, match="text_scale"):
        make_renderer(text_scale=0)
    with pytest.raises(ValueError, match="text_category_scales"):
        make_renderer(text_category_scales={"产状": -1})


def test_pattern_cycle_limit_prevents_unbounded_work():
    renderer = make_renderer(max_pattern_cycles=2)
    points = np.asarray([(0.0, 0.0), (100.0, 0.0)])
    rhythm = {
        "kind": "payload",
        "period_mm": 1.0,
        "polylines": [[(0, 0), (1, 0)]],
        "dots": [],
        "fills": [],
    }
    buffer = _StampBuffer()
    outcome = renderer._stamp_along(
        points, rhythm, 1, 1, 1, (0, 0, 0), 1, 0.01, buffer
    )
    assert outcome == "too_many_cycles"
    assert not buffer.segments

    fig, ax = _make_axes()
    outcome = renderer._draw_raised_parallel(
        ax,
        points,
        {"period_mm": 1.0, "lines": [(0.0, 1.0, 0.1)]},
        (0, 0, 0),
        1,
        1,
        1,
        1,
    )
    assert outcome == "too_many_cycles"
    report = {}
    renderer._draw_wl_line(
        ax,
        points,
        rhythm,
        (0, 0, 0),
        1,
        1,
        1,
        1,
        1,
        _StampBuffer(),
        report,
        prefix="",
    )
    assert report["cycle_limit"] == 1
    assert "pattern" not in report
    fig.clear()


def test_zero_symbol_dimension_does_not_collapse_geometry():
    symbol = Symbol(
        no=99,
        type=1,
        n=2,
        header_len=4,
        header_u16=[1, 2],
        subpaths=[SubPath(points=[(0, -1), (0, 1)])],
    )
    renderer = make_renderer(symbols={99: symbol})
    fig, ax = _make_axes()
    report = {"unknown_colors": {}, "overridden_colors": {}}
    assert renderer._draw_symbol(ax, 0, 0, 99, 2, 0, 0, (0, 0, 0), 1, report)
    assert np.ptp(ax.lines[0].get_xydata()[:, 1]) == pytest.approx(4.0)
    assert renderer._draw_symbol(ax, 0, 0, 99, 0, 0, 0, (0, 0, 0), 1, report)
    assert np.ptp(ax.lines[-1].get_xydata()[:, 1]) == pytest.approx(2.0)
    fig.clear()


def test_line_style_decode_is_cached():
    class CountingLinesty:
        def __init__(self):
            self.calls = 0

        def decode(self, number):
            self.calls += 1
            return None

    linesty = CountingLinesty()
    libraries = GraphicLibraries(
        linesty=linesty,
        subgraph=FakeSubgraphLib(),
        fillgrph=FakeFillgrphLib(),
        color=FakeColorLib(),
    )
    renderer = GraphicRenderer(libraries)
    for _ in range(4):
        assert renderer._line_style(7) is None
    assert linesty.calls == 1


def test_fill_clipping_handles_covering_and_degenerate_rings():
    renderer = make_renderer()
    points = np.asarray([(0.0, 0.0), (0.75, 0.0)])
    covering = {
        "kind": "payload",
        "period_mm": 1.0,
        "polylines": [],
        "dots": [],
        "fills": [[(-1.0, 0.2), (2.0, 0.2), (2.0, -0.2), (-1.0, -0.2)]],
    }
    buffer = _StampBuffer()
    renderer._stamp_along(points, covering, 1, 1, 1, (0, 0, 0), 1, 0.01, buffer)
    assert buffer.fills
    vertices = np.concatenate(buffer.fills)
    assert vertices[:, 0].min() >= 0.0
    assert vertices[:, 0].max() <= 0.75

    degenerate = dict(covering)
    degenerate["fills"] = [[(-1.0, 0.0), (2.0, 0.0), (2.0, 0.0), (-1.0, 0.0)]]
    buffer = _StampBuffer()
    renderer._stamp_along(points, degenerate, 1, 1, 1, (0, 0, 0), 1, 0.01, buffer)
    assert not buffer.fills


def test_geodataframe_metadata_supports_attribution_and_empty_layers():
    empty = gpd.GeoDataFrame(
        {"point_type": []},
        geometry=[],
        crs="EPSG:32643",
    )
    empty.attrs["source"] = "empty.wt"
    empty.attrs["kind"] = "wt"
    renderer = make_renderer()
    fig, ax = _make_axes()
    report = renderer.draw_layer(ax, empty)
    assert report["source"] == "empty.wt"
    assert report["kind"] == "wt"
    assert report["features"] == 0
    assert report["drawn"] == 0
    fig.clear()


def test_nonfinite_label_scales_are_rejected():
    with pytest.raises(ValueError, match="polygon_label_scale"):
        make_renderer(polygon_label_scale=float("nan"))
    with pytest.raises(ValueError, match="attitude_text_scale"):
        make_renderer(attitude_text_scale=float("nan"))


def test_numpy_bool_dot_fill_state_is_preserved():
    rhythm = GraphicRenderer._normalise_rhythm(
        {
            "kind": "filled_rect_dot_bars",
            "period_mm": 1,
            "dots": [(0.5, 0.0, 0.1, np.True_)],
        }
    )
    assert rhythm["dots"][0][3] is True


def test_invalid_output_and_missing_graphic_fields(tmp_path):
    wp, _, _ = sample_layers()
    renderer = make_renderer()
    with pytest.raises(ValueError, match="png or .pdf"):
        renderer.render([wp], tmp_path / "map.svg")
    del wp["fill_color"]
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure()
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    with pytest.raises(ValueError, match="fill_color"):
        renderer.draw_layer(ax, wp)
