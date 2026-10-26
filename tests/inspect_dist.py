# SPDX-License-Identifier: Apache-2.0
"""Inspect release archives for required content and packaging boundaries."""
from __future__ import annotations

import sys
import tarfile
import zipfile
from pathlib import Path


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _check_common(names: list[str], artifact: str) -> None:
    _require(not any("__pycache__" in name or name.endswith(".pyc") for name in names),
             f"{artifact}: Python cache files are included")
    proprietary = {"colorlib.lib", "subgraph.lib", "linesty.lib", "fillgrph.lib"}
    bundled = [name for name in names if Path(name).name.lower() in proprietary]
    _require(not bundled, f"{artifact}: proprietary graphic libraries included: {bundled}")


def _check_wheel(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    required = {
        "pymapgis/reader.py",
        "pymapgis/writer.py",
        "pymapgis/colorlib.py",
        "pymapgis/fillgrph.py",
    }
    _require(required.issubset(names), f"{path.name}: required release modules missing")
    forbidden = ("pymapgis/rendering/", "pymapgis/semantics/")
    _require(not any(name.startswith(forbidden) for name in names),
             f"{path.name}: experimental rendering or semantics included")
    _require("pymapgis/linesty_adjudicated.py" not in names,
             f"{path.name}: map-specific adjudication included")
    _check_common(names, path.name)
    print(f"WHEEL_OK {path.name} {len(names)} entries")


def _check_sdist(path: Path) -> None:
    with tarfile.open(path) as archive:
        names = archive.getnames()
    required_suffixes = (
        "/CITATION.cff",
        "/examples/geological_workflow.py",
        "/tests/fixtures/build_mapgis_fixtures.py",
        "/tests/fixtures/mapgis/synthetic_points.wt",
        "/tests/fixtures/mapgis/synthetic_lines.wl",
        "/tests/fixtures/mapgis/synthetic_polygons.wp",
    )
    for suffix in required_suffixes:
        _require(any(name.endswith(suffix) for name in names),
                 f"{path.name}: required source-archive content missing: {suffix}")
    _require(not any("/pymapgis/rendering/" in name or "/pymapgis/semantics/" in name
                     for name in names),
             f"{path.name}: experimental rendering or semantics included")
    _check_common(names, path.name)
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
