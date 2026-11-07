"""Self-contained real-library rendering regression for twelve JWD layers.

The vectors and five SLIB libraries are bundled under tests/fixtures. Explicit
PYMAPGIS_JWD/PYMAPGIS_SLIB paths remain available for external-library checks.
These tests do not replace visual acceptance in the MapGIS application.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import numpy as np
import pytest

from pymapgis import GraphicLibraries, GraphicRenderer, Reader
from pymapgis.graphic import _StampBuffer
from pymapgis.testing import fixture_path, jwd_path, slib_path

pytestmark = pytest.mark.integration

FIXTURE_DIR = fixture_path()
BUNDLED_JWD = jwd_path()
BUNDLED_SLIB = slib_path()
LIBRARY_NAMES = ("Subgraph.lib", "LINESTY.lib", "Fillgrph.lib", "Colorlib.lib", "Pcolor.lib")
LAYER_NAMES = [
    "LDLYAAE002.WP~",
    "LDZOFBB001.WP",
    "LDZOFBB002.WP",
    "LDZOFBB003.WP~",
    "LDZOFBB004.WP",
    "LDLYAAE001.WL",
    "LDZOFBA002.WL",
    "LDZOFBA003.WL",
    "LDZOFBA005.WL",
    "LDZOFBB098.WL",
    "LDZOFBA016.WT",
    "LDZOFBB099.WT",
]


def _require_files(root: Path, names, label: str) -> Path:
    missing = [name for name in names if not (root / name).is_file()]
    if missing:
        raise FileNotFoundError(f"{label} is incomplete at {root}: {missing}")
    return root


def _jwd_root() -> Path:
    root = Path(os.environ.get("PYMAPGIS_JWD") or BUNDLED_JWD)
    return _require_files(root, LAYER_NAMES, "The twelve-layer JWD fixture")


def _slib_root() -> Path:
    root = Path(os.environ.get("PYMAPGIS_SLIB") or BUNDLED_SLIB)
    return _require_files(root, LIBRARY_NAMES, "The five-library SLIB fixture")


def _layers(root: Path):
    layers = []
    for name in LAYER_NAMES:
        path = root / name
        if path.suffix.lower() == ".wp~":
            layers.append(Reader(str(path), read_graphic_params=True).geodataframe)
        else:
            layers.append(path)
    return layers


def test_real_jwd_twelve_layer_render(tmp_path):
    pytest.importorskip("matplotlib")
    root = _jwd_root()
    slib = _slib_root()

    renderer = GraphicRenderer(
        GraphicLibraries.from_directory(slib),
        scale=250000,
        native_text_layout=True,
        font_zh_map={1: "SimSun", 4: "SimHei"},
        font_en_map={0: "DejaVu Sans"},
        text_font_family=["Microsoft YaHei", "SimSun", "DejaVu Sans"],
    )
    png = tmp_path / "jwd.png"
    pdf = tmp_path / "jwd.pdf"
    result = renderer.render(_layers(root), png, figsize=(12, 10), dpi=160)
    result.figure.savefig(pdf, format="pdf")
    result.figure.clear()

    reports = result.reports
    assert len(reports) == 12
    assert sum(item["features"] for item in reports) == 7094
    assert sum(item["drawn"] for item in reports) == 5732
    assert sum(item.get("polygon_label", 0) for item in reports) == 713
    assert sum(item.get("holes", 0) for item in reports) == 68
    assert sum(item.get("pattern", 0) for item in reports if item["kind"] == "wp") == 165
    assert sum(item.get("pattern", 0) for item in reports if item["kind"] == "wl") == 844
    # Only the five 1|2 features have an independent auxiliary record.
    # 38|2 and 65|4 select main-record subline variants instead.
    assert sum(item.get("aux_pattern", 0) for item in reports) == 5
    assert sum(item.get("symbols", 0) for item in reports) == 581
    assert sum(item.get("symbols_unresolved", 0) for item in reports) == 0
    assert sum(item.get("fallback", 0) + item.get("aux_fallback", 0)
               for item in reports) == 0
    assert sum(item.get("text", 0) for item in reports) == 386
    assert sum(item.get("spaced_text", 0) for item in reports) == 386
    assert sum(item.get("compressed_text", 0) for item in reports) == 0
    assert sum(item.get("script_text", 0) for item in reports) == 0
    assert sum(item.get("excluded_text", 0) for item in reports) == 1362
    assert sum(item.get("unknown_fill", 0) + item.get("aux_unknown_fill", 0)
               for item in reports) == 0
    assert sum(item.get("excluded_class", 0) for item in reports) == 0
    assert all(not item.get("unknown_fonts") for item in reports)

    unknown_codes = set()
    unknown_occurrences = 0
    for item in reports:
        unknown_codes.update(item["unknown_colors"])
        unknown_occurrences += sum(item["unknown_colors"].values())
    assert len(unknown_codes) == 0
    assert unknown_occurrences == 0

    assert png.read_bytes().startswith(b"\x89PNG")
    assert pdf.read_bytes().startswith(b"%PDF")


def test_real_jwd_quaternary_library_colors():
    root = _jwd_root()
    slib = _slib_root()
    source = root / "LDZOFBB001.WP"
    from pymapgis import ColorLib, PcolorLib

    gdf = Reader(str(source), read_graphic_params=True).geodataframe
    codes = gdf["QDUECC"].map(lambda value: re.sub(r"[^A-Za-z0-9]", "", str(value)))
    gdf = gdf[codes.isin(["Qp3pal", "Qhfl"])]
    assert len(gdf) == 58
    assert set(gdf["fill_color"]) == {602, 652}
    colorlib = ColorLib(str(slib / "Colorlib.lib"))
    assert colorlib.rgb(602) == (206, 217, 206)
    assert colorlib.rgb(652) == (51, 204, 76)
    pcolor = PcolorLib(str(slib / "Pcolor.lib"))
    assert pcolor.rgb(602) == (255, 255, 178)
    assert pcolor.rgb(652) == (255, 255, 204)

    # WP fills use Pcolor in auto mode; other roles retain Colorlib. The
    # explicit color mode remains available for legacy comparison only.
    libraries = GraphicLibraries.from_directory(slib)
    renderer = GraphicRenderer(libraries)
    assert renderer.fill_library == "auto"
    report = {"unknown_colors": {}, "overridden_colors": {}}
    assert renderer._color(602, report, role="fill") == pcolor.rgb01(602)
    assert renderer._color(652, report, role="fill") == pcolor.rgb01(652)
    assert renderer._color(2, report, role="feature") == colorlib.rgb01(2)
    assert report["unknown_colors"] == {}
    legacy = GraphicRenderer(libraries, fill_library="color")
    assert legacy._color(602, report, role="fill") == colorlib.rgb01(602)


def test_adjudicated_line_style_variants():
    slib = _slib_root()
    renderer = GraphicRenderer(GraphicLibraries.from_directory(slib))
    for linetype, aux, expected_period in [
        (4, 0, 1.0),
        (4, 1, 1.0),
        (38, 2, 1.0),
        (48, 0, 1.0),
        (48, 1, 1.0),
    ]:
        rhythm = renderer._rhythm(linetype, aux)
        assert rhythm is not None
        assert rhythm["period_mm"] == pytest.approx(expected_period), (linetype, aux)
    # 2|2/2|3 在过去裁定中属于未解决变体，不能用通用节奏替代。
    assert renderer._rhythm(2, 2) is None
    assert renderer._rhythm(2, 3) is None


def test_svg_boundary_reference_geometry():
    """Lock the 2026-10-21 boundary SVG's verified library geometry."""
    slib = _slib_root()
    renderer = GraphicRenderer(GraphicLibraries.from_directory(slib))

    assert renderer._rhythm(1, 0)["kind"] == "solid_pen"
    assert renderer._rhythm(1, 1)["kind"] == "solid_pen"

    dash = renderer._rhythm(2, 0)
    assert dash["kind"] == "inline_dash"
    assert dash["period_mm"] == pytest.approx(1.0)
    assert dash["lines"][0] == pytest.approx((0.0, 0.349609375))
    assert dash["lines"][1] == pytest.approx((0.650390625, 1.0))

    dash_dot = renderer._rhythm(3, 0)
    assert dash_dot["period_mm"] == pytest.approx(1.015625)
    assert dash_dot["lines"] == [(0.0, 0.625)]
    assert dash_dot["dots"] == [(0.8203125, 0.0, 0.03125)]

    dot0 = renderer._rhythm(16, 0)
    dot1 = renderer._rhythm(16, 1)
    assert not dot0["polylines"] and not dot1["polylines"]
    assert dot0["dots"] == [(0.5, 0.0, pytest.approx(0.044))]
    assert dot1["dots"] == [(0.5, 0.0, 0.078125)]

    raised_dot = renderer._rhythm(17, 0)
    assert raised_dot["polylines"] == [[(0.0, 0.0), (1.0, 0.0)]]
    assert raised_dot["dots"] == [
        (0.5, pytest.approx(0.150390625), pytest.approx(0.04))
    ]

    tick = renderer._rhythm(18, 0)
    assert tick["polylines"] == [
        [(0.0, 0.0), (1.0, 0.0)],
        [(0.0, 0.0), (0.0, 0.125)],
    ]

    raised = renderer._rhythm(48, 0)
    assert raised["period_mm"] == pytest.approx(1.0)
    assert raised["polylines"][0] == [(0.0, 0.0), (1.0, 0.0)]
    assert raised["polylines"][1][0] == pytest.approx((0.1, 0.1))
    assert raised["polylines"][1][1] == pytest.approx((0.40312498807907104, 0.1))
    assert raised["polylines"][2][0] == pytest.approx((0.6, 0.1))
    assert raised["polylines"][2][1] == pytest.approx((0.9, 0.1))

    # The SVG predates independent auxiliary-record rendering. The main 1|2
    # record remains solid, while its auxiliary 2|0 record is decoded separately.
    assert renderer._rhythm(1, 2)["kind"] == "solid_pen"
    assert renderer._rhythm(2)["kind"] == "inline_dash"


def test_aux_variant_roles_and_structural_65_4():
    slib = _slib_root()
    libraries = GraphicLibraries.from_directory(slib)
    renderer = GraphicRenderer(libraries)
    from pymapgis import compose_feature_style

    assert compose_feature_style(libraries.linesty, 16, 1)[1] is None
    assert compose_feature_style(libraries.linesty, 38, 2)[1] is None
    assert compose_feature_style(libraries.linesty, 65, 4)[1] is None
    independent = compose_feature_style(libraries.linesty, 1, 2)[1]
    assert independent is not None and independent.no == 2

    rhythm = renderer._rhythm(65, 4)
    assert rhythm is not None
    assert rhythm["period_mm"] == pytest.approx(30.4)
    assert len(rhythm["fills"]) == 6


def test_38_2_solid_segments_preserve_all_real_source_vertices():
    slib = _slib_root()
    root = _jwd_root()
    renderer = GraphicRenderer(GraphicLibraries.from_directory(slib), map_units_per_mm=1.0)
    rhythm = renderer._rhythm(38, 2)
    checked_features = 0
    checked_parts = 0
    for name in ("LDZOFBA002.WL", "LDZOFBA003.WL"):
        gdf = Reader(str(root / name), read_graphic_params=True).geodataframe
        selected = gdf[(gdf["linetype"] == 38) & (gdf["aux_linetype"] == 2)]
        for _, row in selected.iterrows():
            checked_features += 1
            for line in renderer._iter_lines(row.geometry):
                points = np.asarray(line.coords, dtype=float)
                buffer = _StampBuffer()
                renderer._stamp_along(
                    points, rhythm,
                    xc=float(row["x_coef"]), yc=float(row["y_coef"]), unit=1.0,
                    color=(0.0, 0.0, 0.0), line_width=1.0,
                    min_radius=1e-9, buffer=buffer,
                )
                assert buffer.segments, (name, checked_features)
                endpoints = np.concatenate(np.concatenate(buffer.segments))
                for vertex in points:
                    distance = np.min(np.linalg.norm(endpoints - vertex, axis=1))
                    assert distance <= 1e-9, (name, checked_features, vertex, distance)
                checked_parts += 1
    assert checked_features == 37
    assert checked_parts >= checked_features


def test_bundled_jwd_slib_fixture_manifest():
    manifest = json.loads((FIXTURE_DIR / "jwd_slib_manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["vectors"]) == set(LAYER_NAMES)
    assert set(manifest["libraries"]) == set(LIBRARY_NAMES)
    for section, root in (("vectors", BUNDLED_JWD), ("libraries", BUNDLED_SLIB)):
        for name, expected in manifest[section].items():
            data = (root / name).read_bytes()
            assert len(data) == expected["bytes"], name
            assert hashlib.sha256(data).hexdigest() == expected["sha256"], name
    assert manifest["totals"]["bytes"] == 19381767
