# SPDX-License-Identifier: Apache-2.0
"""Inspect release archives for required content and packaging boundaries."""
from __future__ import annotations

import sys
import tarfile
import zipfile
from pathlib import Path

JWD_FIXTURE_NAMES = (
    "LDLYAAE002.WP~", "LDZOFBB001.WP", "LDZOFBB002.WP", "LDZOFBB003.WP~",
    "LDZOFBB004.WP", "LDLYAAE001.WL", "LDZOFBA002.WL", "LDZOFBA003.WL",
    "LDZOFBA005.WL", "LDZOFBB098.WL", "LDZOFBA016.WT", "LDZOFBB099.WT",
)
SLIB_FIXTURE_NAMES = (
    "Subgraph.lib", "LINESTY.lib", "Fillgrph.lib", "Colorlib.lib", "Pcolor.lib",
)
SYNTHETIC_FIXTURE_NAMES = (
    "synthetic_points.wt", "synthetic_lines.wl", "synthetic_polygons.wp",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _check_common(names: list[str], artifact: str, *, allow_slib_fixtures: bool = False) -> None:
    _require(not any("__pycache__" in name or name.endswith(".pyc") for name in names),
             f"{artifact}: Python cache files are included")
    library_names = {"colorlib.lib", "pcolor.lib", "subgraph.lib", "linesty.lib", "fillgrph.lib"}
    bundled = []
    for name in names:
        normalised = name.lower().replace("\\", "/")
        sanctioned = allow_slib_fixtures and (
            "tests/fixtures/slib/" in normalised
            or "pymapgis/testing/fixtures/slib/" in normalised
        )
        if Path(name).name.lower() in library_names and not sanctioned:
            bundled.append(name)
    _require(
        not bundled,
        f"{artifact}: graphic libraries outside the test fixture directory: {bundled}",
    )


def _check_wheel(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    required = {
        "pymapgis/reader.py",
        "pymapgis/writer.py",
        "pymapgis/colorlib.py",
        "pymapgis/pcolor.py",
        "pymapgis/fillgrph.py",
        "pymapgis/graphic.py",
        "pymapgis/testing/__init__.py",
        "pymapgis/testing/fixtures/jwd_slib_manifest.json",
        "pymapgis/testing/fixtures/fixture_manifest.json",
    }
    for name in JWD_FIXTURE_NAMES:
        required.add("pymapgis/testing/fixtures/jwd/" + name)
    for name in SLIB_FIXTURE_NAMES:
        required.add("pymapgis/testing/fixtures/slib/" + name)
    for name in SYNTHETIC_FIXTURE_NAMES:
        required.add("pymapgis/testing/fixtures/mapgis/" + name)
    _require(required.issubset(names), f"{path.name}: required release modules missing")
    forbidden = ("pymapgis/rendering/", "pymapgis/semantics/")
    _require(not any(name.startswith(forbidden) for name in names),
             f"{path.name}: experimental rendering or semantics included")
    _require("pymapgis/linesty_adjudicated.py" not in names,
             f"{path.name}: map-specific adjudication included")
    _check_common(names, path.name, allow_slib_fixtures=True)
    print(f"WHEEL_OK {path.name} {len(names)} entries")


def _check_sdist(path: Path) -> None:
    with tarfile.open(path) as archive:
        names = archive.getnames()
    required_suffixes = (
        "/CITATION.cff",
        "/examples/geological_workflow.py",
        "/tests/test_graphic.py",
        "/tests/test_graphic_real_jwd.py",
        "/tests/fixtures/build_mapgis_fixtures.py",
        # test_public_fixtures.py reads the manifest at module scope; an sdist
        # without it passes inspection but crashes the shipped tests.
        "/tests/fixtures/fixture_manifest.json",
        "/tests/fixtures/mapgis/synthetic_points.wt",
        "/tests/fixtures/mapgis/synthetic_lines.wl",
        "/tests/fixtures/mapgis/synthetic_polygons.wp",
        "/tests/fixtures/jwd_slib_manifest.json",
        "/tests/fixtures/jwd/LDLYAAE002.WP~",
        "/tests/fixtures/jwd/LDZOFBB001.WP",
        "/tests/fixtures/jwd/LDZOFBB002.WP",
        "/tests/fixtures/jwd/LDZOFBB003.WP~",
        "/tests/fixtures/jwd/LDZOFBB004.WP",
        "/tests/fixtures/jwd/LDLYAAE001.WL",
        "/tests/fixtures/jwd/LDZOFBA002.WL",
        "/tests/fixtures/jwd/LDZOFBA003.WL",
        "/tests/fixtures/jwd/LDZOFBA005.WL",
        "/tests/fixtures/jwd/LDZOFBB098.WL",
        "/tests/fixtures/jwd/LDZOFBA016.WT",
        "/tests/fixtures/jwd/LDZOFBB099.WT",
        "/tests/fixtures/slib/Subgraph.lib",
        "/tests/fixtures/slib/LINESTY.lib",
        "/tests/fixtures/slib/Fillgrph.lib",
        "/tests/fixtures/slib/Colorlib.lib",
        "/tests/fixtures/slib/Pcolor.lib",
    )
    for suffix in required_suffixes:
        _require(any(name.endswith(suffix) for name in names),
                 f"{path.name}: required source-archive content missing: {suffix}")
    _require(not any("/pymapgis/rendering/" in name or "/pymapgis/semantics/" in name
                     for name in names),
             f"{path.name}: experimental rendering or semantics included")
    _check_common(names, path.name, allow_slib_fixtures=True)
    print(f"SDIST_OK {path.name} {len(names)} entries")


def main() -> None:
    dist = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    _require(len(wheels) == 1, f"Expected exactly one wheel in {dist}, found {len(wheels)}")
    _require(len(sdists) == 1, f"Expected exactly one sdist in {dist}, found {len(sdists)}")
    _check_wheel(wheels[0])
    _check_sdist(sdists[0])


if __name__ == "__main__":
    main()
