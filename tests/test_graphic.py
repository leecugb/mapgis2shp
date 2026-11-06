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
from pymapgis.slib import Element, SubPath, Symbol


class FakeColorLib:
    def rgb01(self, number):
        return {
            0: (0.0, 0.0, 0.0),
            1: (0.0, 0.0, 0.0),
            4: (1.0, 1.0, 0.0),
            6: (1.0, 0.0, 0.0),
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
    assert renderer._color(1167, report) == (0.0, 0.0, 1.0)
    assert report["overridden_colors"] == {"1167": 1}
    assert renderer._color(9999, report) == renderer.fallback_color
    assert report["unknown_colors"] == {"9999": 1}


def test_library_directory_validation_and_loading(tmp_path, monkeypatch):
    with pytest.raises(FileNotFoundError) as error:
        GraphicLibraries.from_directory(tmp_path)
    for name in ("LINESTY.lib", "Subgraph.lib", "Fillgrph.lib", "Colorlib.lib"):
        assert name in str(error.value)
        (tmp_path / name).touch()

    for class_name in ("LinestyLib", "SubgraphLib", "FillgrphLib", "ColorLib"):
        monkeypatch.setattr(
            graphic, class_name, lambda path, name=class_name: (name, Path(path).name)
        )
    libraries = GraphicLibraries.from_directory(tmp_path)
    assert libraries.linesty == ("LinestyLib", "LINESTY.lib")
    assert libraries.subgraph == ("SubgraphLib", "Subgraph.lib")
    assert libraries.fillgrph == ("FillgrphLib", "Fillgrph.lib")
    assert libraries.color == ("ColorLib", "Colorlib.lib")
    assert libraries.directory == tmp_path


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
