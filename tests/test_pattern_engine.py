"""Regression tests for custom and hatch pattern rendering."""

from __future__ import annotations

import numpy as np
import pytest
from shapely.geometry import box

pattern_engine = pytest.importorskip(
    "pymapgis.rendering.pattern_engine",
    reason="optional local rendering extension is excluded from clean distributions",
)


def make_axes():
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure()
    FigureCanvasAgg(fig)
    return fig, fig.add_subplot(111)


def segments(ax):
    return [
        np.asarray(segment)
        for collection in ax.collections
        if hasattr(collection, "get_segments")
        for segment in collection.get_segments()
    ]


def test_custom_pattern_uses_absolute_metre_grid(monkeypatch):
    monkeypatch.setattr(pattern_engine, "_geo_lat", lambda: 0.0)
    fig, ax = make_axes()
    polygon = box(0.00123, 0.00177, 0.00321, 0.00411)
    pattern_engine.apply_tile_pattern(
        ax, polygon, (1.0, 1.0, 1.0), "up_tack"
    )
    horizontal = []
    for segment in segments(ax):
        dx = (segment[1, 0] - segment[0, 0]) * 111320.0
        dy = (segment[1, 1] - segment[0, 1]) * 111320.0
        if abs(dy) < 1e-6 and abs(abs(dx) - 300.0) < 1e-6:
            horizontal.append(segment)
    assert horizontal
    for segment in horizontal:
        center_x = float(segment[:, 0].mean()) * 111320.0
        center_y = float(segment[:, 1].mean()) * 111320.0
        assert center_x / 600.0 == pytest.approx(round(center_x / 600.0), abs=1e-8)
        assert center_y / 600.0 == pytest.approx(round(center_y / 600.0), abs=1e-8)
    fig.clear()


@pytest.mark.parametrize(
    "polygon",
    [
        box(-0.005, -0.005, 0.005, 0.005),
        box(0.001, 0.001, 0.009, 0.009),
    ],
)
def test_checkerboard_parity_is_shared_across_polygon_bounds(monkeypatch, polygon):
    monkeypatch.setattr(pattern_engine, "_geo_lat", lambda: 0.0)
    fig, ax = make_axes()
    pattern_engine.apply_tile_pattern(
        ax, polygon, (1.0, 1.0, 1.0), "cross_up_tack"
    )
    extents = []
    for segment in segments(ax):
        if np.allclose(segment[:, 0], 0.0, atol=1e-12):
            extents.append((
                float(segment[:, 1].min()) * 111320.0,
                float(segment[:, 1].max()) * 111320.0,
            ))
    # Cell (0, 0) is even in the absolute grid and must always be a cross,
    # not the alternate up-tack whose vertical segment runs from 0 to +150 m.
    assert any(
        ymin == pytest.approx(-150.0, abs=1e-6)
        and ymax == pytest.approx(150.0, abs=1e-6)
        for ymin, ymax in extents
    )
    fig.clear()


def test_unknown_pattern_warns_and_solid_fallback_has_no_border():
    fig, ax = make_axes()
    with pytest.warns(UserWarning, match="Unknown pattern"):
        pattern_engine.apply_pattern_to_geometries(
            ax,
            [box(0, 0, 1, 1)],
            (0.8, 0.9, 1.0),
            "not_a_registered_pattern",
        )
    assert len(ax.patches) == 1
    patch = ax.patches[0]
    assert patch.get_linewidth() == 0.0
    assert patch.get_edgecolor()[3] == 0.0
    fig.clear()


def test_direct_unknown_tile_name_warns_instead_of_aliasing_cross_diag():
    fig, ax = make_axes()
    with pytest.warns(UserWarning, match="Unknown tile pattern"):
        pattern_engine.apply_tile_pattern(
            ax, box(0, 0, 0.01, 0.01), (0.8, 0.9, 1.0), "misspelled_tile"
        )
    assert len(ax.patches) == 1
    assert not ax.collections
    assert ax.patches[0].get_linewidth() == 0.0
    fig.clear()


def test_unresolvable_svg_pattern_ref_warns_and_fills_polygon(monkeypatch):
    monkeypatch.setattr(pattern_engine, "_PATTERN_ENABLED", True)
    monkeypatch.setattr(pattern_engine, "resolve_pattern_ref", lambda ref: None)
    fig, ax = make_axes()
    with pytest.warns(UserWarning, match="Unresolvable pattern_ref"):
        pattern_engine.apply_svg_tile_pattern(
            ax,
            box(0, 0, 1, 1),
            (0.8, 0.9, 1.0),
            {"family": "missing", "code": "missing"},
        )
    assert len(ax.patches) == 1
    assert ax.patches[0].get_linewidth() == 0.0
    fig.clear()


def test_svg_tile_culling_cannot_drop_protruding_stroke(monkeypatch):
    """A non-intersecting source tile may own a stroke inside the polygon."""
    monkeypatch.setattr(pattern_engine, "_PATTERN_ENABLED", True)
    monkeypatch.setattr(pattern_engine, "_geo_lat", lambda: 0.0)
    monkeypatch.setattr(pattern_engine, "resolve_pattern_ref", lambda ref: {"svg": "stub"})
    template = {
        "tw_m": 600.0,
        "th_m": 600.0,
        "segs": [
            (
                (0.0, 0.0, 0.0),
                0.3,
                np.asarray([(600.0, 300.0), (1200.0, 300.0)]),
            )
        ],
        "polys": [],
        "texts": [],
    }
    monkeypatch.setattr(pattern_engine, "_tile_template", lambda svg, mpp: template)
    polygon = box(900 / 111320, 250 / 111320, 1000 / 111320, 350 / 111320)
    fig, ax = make_axes()
    pattern_engine.apply_svg_tile_pattern(
        ax,
        polygon,
        (1.0, 1.0, 1.0),
        {"family": "custom", "code": "protruding"},
    )
    expected = np.asarray([
        (600 / 111320, 300 / 111320),
        (1200 / 111320, 300 / 111320),
    ])
    assert any(np.allclose(segment, expected) for segment in segments(ax))
    assert all(collection.get_clip_path() is not None for collection in ax.collections)
    fig.clear()
