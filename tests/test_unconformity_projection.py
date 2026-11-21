"""Unconformity double-line geometry under geographic and projected units."""
from __future__ import annotations

import pytest

gpd = pytest.importorskip("geopandas")
pw = pytest.importorskip(
    "pymapgis.rendering.pdf_writer",
    reason="optional local rendering extension is excluded from clean distributions",
)
from shapely.geometry import LineString, box


def _axes():
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    fig = Figure()
    FigureCanvasAgg(fig)
    return fig, fig.add_subplot(111)


def _render_contact(ax, coords, semantic, contact_type, evidence=None):
    gdf = gpd.GeoDataFrame({
        "sem_label": [semantic],
        "contactType": [contact_type],
        "younger_side": ["left"],
        "status": ["normal"],
    }, geometry=[LineString(coords)])
    mapping = {"line_layers": {"LDZOFBA002.WL": {
        "type_field": "sem_label",
        "line_styles": {semantic: {
            "rgb": [51, 51, 51], "width": 0.5, "style": "solid"}},
    }}}
    context = gpd.GeoDataFrame(
        {"QDUECC": ["Q"]}, geometry=[box(-1e7, -1e7, 1e7, 1e7)])
    pw.render_line_layer(
        ax, gdf, mapping, "LDZOFBA002.WL", context_polygons=context,
        render_evidence=evidence)


@pytest.mark.parametrize("semantic,contact_type", [
    ("角度不整合", "angular unconformable contact"),
    ("平行不整合", "disconformable contact"),
])
def test_projected_unconformity_has_visible_metric_secondary_line(
        monkeypatch, semantic, contact_type):
    monkeypatch.setattr(pw, "_UNIT_SCALE", (1.0, 1.0))
    fig, ax = _axes()
    try:
        _render_contact(
            ax, [(400000, 4400000), (401000, 4400000)], semantic, contact_type,
            evidence := {})
        assert len(ax.lines) == 2
        base, secondary = ax.lines
        assert list(base.get_ydata()) == [4400000, 4400000]
        assert list(secondary.get_ydata()) == pytest.approx([4400111.32, 4400111.32])
        assert secondary.get_linestyle() != "-"
        assert pw._unconformity_offset_map_units() == pytest.approx(111.32)
        record = evidence["unconformities"][0]
        assert record["secondary_artists"] == 1
        assert record["younger_side"] == "left"
        assert record["offset_map_units"] == pytest.approx(111.32)
    finally:
        fig.clear()


def test_projected_younger_side_probe_crosses_narrow_contact_gap(monkeypatch):
    monkeypatch.setattr(pw, "_UNIT_SCALE", (1.0, 1.0))
    x0, y0 = 400000.0, 4400000.0
    # Eastward contact: older C on the left/north, younger N on right/south.
    # The 20 m gap defeats the old 0.0012 m probe but not 133.584 m.
    polygons = gpd.GeoDataFrame({
        "QDUECC": ["C1", "N1a"], "_age": [600.0, 1200.0],
    }, geometry=[
        box(x0 - 1000, y0 + 10, x0 + 2000, y0 + 1000),
        box(x0 - 1000, y0 - 1000, x0 + 2000, y0 - 10),
    ])
    side = pw._younger_side([(x0, y0), (x0 + 1000, y0)], polygons)
    assert side == "right"
    assert pw._legacy_degrees_to_map_units(0.0012) == pytest.approx(133.584)


def test_identity_unconformity_offset_remains_legacy_degree_value(monkeypatch):
    monkeypatch.setattr(pw, "_UNIT_SCALE", None)
    monkeypatch.setattr(pw, "_LAT_REF_DEG", 39.5)
    fig, ax = _axes()
    try:
        _render_contact(
            ax, [(74.0, 39.5), (74.01, 39.5)],
            "角度不整合", "angular unconformable contact")
        assert len(ax.lines) == 2
        assert list(ax.lines[1].get_ydata()) == pytest.approx([39.501, 39.501])
        assert pw._unconformity_offset_map_units() == 0.001
        assert pw._legacy_degrees_to_map_units(0.0012) == 0.0012
    finally:
        fig.clear()
