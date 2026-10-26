# SPDX-License-Identifier: Apache-2.0
"""面元填充性能/等价性回归（2026-10-25）。

旧实现逐行 geopandas.plot()：每行触发一次 canvas.draw_idle，整幅
已有图元随面元数近二次方重画。新实现直接 PathPatch，但必须保留
geopandas 的地理 CRS 纬度纵横比与即时 autoscale 语义。
"""
import geopandas as gpd
import matplotlib
import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from shapely.geometry import MultiPolygon, Polygon

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

pdf_writer = pytest.importorskip(
    "pymapgis.rendering.pdf_writer",
    reason="optional rendering module is not present in the public source archive",
)
_rgb = pdf_writer._rgb
render_polygon_layer = pdf_writer.render_polygon_layer


def _fixture():
    p1 = Polygon([(0, 0), (3, 0), (3, 3), (0, 3)],
                 [[(1, 1), (1, 2), (2, 2), (2, 1)]])
    p2 = Polygon([(3, 0), (6, 0), (6, 3), (3, 3)])
    mp = MultiPolygon([
        Polygon([(0, 3), (2, 3), (2, 5), (0, 5)]),
        Polygon([(3, 3), (5, 3), (5, 5), (3, 5)]),
    ])
    gdf = gpd.GeoDataFrame({"QDUECC": ["U", "U", "U"]},
                           geometry=[p1, p2, mp], crs="EPSG:4326")
    mapping = {"polygon_layers": {"L": {"code_field": "QDUECC", "units": {
        "U": {"rgb": [51, 102, 153], "name": "unit"}}}}}
    return gdf, mapping


def _canvas():
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.set_xlim(-1, 7)
    ax.set_ylim(-1, 6)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    return fig, ax


def _counting_draw(monkeypatch):
    calls = []
    original = FigureCanvasAgg.draw

    def draw(self, *args, **kwargs):
        calls.append(1)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(FigureCanvasAgg, "draw", draw)
    return calls


def _finish(fig, ax):
    # 与生产 bare 路径一致：图层完成后统一给定显示范围。
    ax.set_xlim(-1, 7)
    ax.set_ylim(-1, 6)
    fig.canvas.draw()
    return np.array(fig.canvas.buffer_rgba()).copy()


def test_unpatterned_polygons_no_draw_idle_and_pixel_equivalent(monkeypatch):
    gdf, mapping = _fixture()

    # 旧路径：每行 geopandas.plot；它自身会 aspect/auto + autoscale + draw_idle。
    fig, ax = _canvas()
    old_calls = _counting_draw(monkeypatch)
    fill = _rgb([51, 102, 153])
    for i, _ in gdf.iterrows():
        gdf.iloc[[i]].plot(ax=ax, facecolor=fill, edgecolor="none",
                           linewidth=0.0, zorder=2, alpha=0.9)
    assert old_calls, "geopandas 旧路径应触发 draw_idle（测试有效性锚）"
    monkeypatch.undo()
    old = _finish(fig, ax)
    plt.close(fig)

    # 新路径：生产函数，装配期间不得进行任何整幅 draw。
    fig, ax = _canvas()
    new_calls = _counting_draw(monkeypatch)
    render_polygon_layer(ax, gdf, mapping, "L", draw_labels=False)
    assert new_calls == [], f"面元装配触发整幅 draw ×{len(new_calls)}"
    monkeypatch.undo()
    new = _finish(fig, ax)
    plt.close(fig)

    assert new.shape == old.shape
    diff = np.abs(new.astype(np.int16) - old.astype(np.int16))
    changed = diff.max(axis=2) > 0
    # PatchCollection → 独立 PathPatch 的抗锯齿残余；生产两幅大图实测同量级。
    assert int(diff.max()) <= 3
    assert float(changed.mean()) < 0.01
