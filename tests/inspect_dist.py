# SPDX-License-Identifier: Apache-2.0
"""Inspect release archives for required content and packaging boundaries."""
from __future__ import annotations

import sys
import tarfile
import zipfile
from pathlib import Path

SYNTHETIC_FIXTURE_NAMES = (
    "synthetic_points.wt", "synthetic_lines.wl", "synthetic_polygons.wp",
)
WRITER_BATCH2_SHP_STEMS = (
    "01_minimal_triangle", "02_two_sizes", "03_three_holes",
    "04_multipart_with_holes", "05_touching_point", "06_shared_edge",
    "07_hole_and_island", "08_duplicate_vertices", "09_invalid_bowtie",
    "10_points", "11_multiline_and_duplicate",
)
WRITER_BATCH2_NAMES = tuple(
    stem + suffix
    for stem in WRITER_BATCH2_SHP_STEMS
    for suffix in (".shp", ".shx", ".dbf", ".cpg", ".prj")
) + tuple(
    stem.upper() + (
        ".WT" if stem.startswith("10_") else ".WL" if stem.startswith("11_") else ".WP"
    )
    for stem in WRITER_BATCH2_SHP_STEMS
) + ("README_转换说明.md", "manifest.csv")
WRITER_BATCH3_SHP_STEMS = (
    "01_reference_triangle", "02_identical_polygons", "03_shared_edge_duplicate",
    "04_nested_hole_island", "05_large_ring_over_64k", "06_large_then_small",
    "07_projected_utm", "08_attribute_types", "09_null_geometry", "10_points",
    "11_multiline", "12_degenerate_ring",
)
WRITER_BATCH3_NAMES = tuple(
    stem + suffix
    for stem in WRITER_BATCH3_SHP_STEMS
    for suffix in (".shp", ".shx", ".dbf", ".cpg", ".prj")
) + tuple(
    stem.upper() + (
        ".WT" if stem.startswith("10_") else ".WL" if stem.startswith("11_") else ".WP"
    )
    for stem in WRITER_BATCH3_SHP_STEMS
) + ("README_转换说明.md", "manifest.csv")
WRITER_BATCH4_SHP_STEMS = (
    "01_POINT_BASIC", "02_POINT_ATTR_NULL", "03_POINT_MULTIPOINT", "04_POINT_257",
    "05_LINE_BASIC", "06_LINE_MULTI_DUPLICATE", "07_LINE_EMPTY", "08_LINE_10001_VERTICES",
    "09_POLY_BASIC", "10_POLY_HOLE_MULTIPART", "11_POLY_SHARED_ISLAND",
    "12_POLY_DUPLICATE_VERTICES", "13_POLY_BOWTIE", "14_POLY_DEGENERATE",
    "15_POLY_EMPTY", "16_POLY_80_FIELDS", "17_POLY_LARGE_RING",
    "18_POLY_DUPLICATE_ATTRIBUTES", "19_POLY_LONG_TEXT", "20_EMPTY_FILE",
)
WRITER_BATCH4_NATIVE_STEMS = tuple(
    stem for stem in WRITER_BATCH4_SHP_STEMS
    if stem not in {"03_POINT_MULTIPOINT", "20_EMPTY_FILE"}
)
WRITER_BATCH4_NAMES = tuple(
    stem + suffix
    for stem in WRITER_BATCH4_SHP_STEMS
    for suffix in (".shp", ".shx", ".dbf", ".cpg", ".prj")
) + tuple(
    stem + (".WT" if stem.startswith(("01", "02", "04")) else
            ".WL" if stem.startswith(("05", "06", "07", "08")) else ".WP")
    for stem in WRITER_BATCH4_NATIVE_STEMS
) + ("README_转换说明.md",)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _check_common(names: list[str], artifact: str, *, allow_slib_fixtures: bool = False) -> None:
    _require(not any("__pycache__" in name or name.endswith(".pyc") for name in names),
             f"{artifact}: Python cache files are included")
    _require(
        not any("mapgis2shp_submission" in name.replace("\\", "/") for name in names),
        f"{artifact}: manuscript submission content is included",
    )
    ngac_prefixes = (
        "/tests/fixtures/jwd/",
        "/tests/fixtures/slib/",
        "/tests/fixtures/reader_native/",
        "/pymapgis/testing/fixtures/jwd/",
        "/pymapgis/testing/fixtures/slib/",
        "/pymapgis/testing/fixtures/reader_native/",
    )
    for name in names:
        normalised = "/" + name.lower().replace("\\", "/")
        _require(
            not any(prefix in normalised for prefix in ngac_prefixes),
            f"{artifact}: user-supplied NGAC data must not be packaged: {name}",
        )
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
        "pymapgis/testing/fixtures/writer_batch2_manifest.json",
        "pymapgis/testing/fixtures/writer_batch3_manifest.json",
        "pymapgis/testing/fixtures/writer_batch4_manifest.json",
        "pymapgis/testing/fixtures/reader_native_manifest.json",
        "pymapgis/testing/fixtures/DATA_ATTRIBUTION.md",
        "pymapgis/testing/examples/render_bundled_jwd.py",
    }
    for name in WRITER_BATCH2_NAMES:
        required.add("pymapgis/testing/fixtures/writer_batch2/" + name)
    for name in WRITER_BATCH3_NAMES:
        required.add("pymapgis/testing/fixtures/writer_batch3/" + name)
    for name in WRITER_BATCH4_NAMES:
        required.add("pymapgis/testing/fixtures/writer_batch4/" + name)
    for name in SYNTHETIC_FIXTURE_NAMES:
        required.add("pymapgis/testing/fixtures/mapgis/" + name)
    _require(required.issubset(names), f"{path.name}: required release modules missing")
    _require(
        not any(name.startswith(("examples/", "mapgis2shp_submission/")) for name in names),
        f"{path.name}: unnamespaced example or submission files included",
    )
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
        "/DATA_ATTRIBUTION.md",
        "/tests/fixtures/DATA_ATTRIBUTION.md",
        "/examples/geological_workflow.py",
        "/examples/render_bundled_jwd.py",
        "/tests/test_graphic.py",
        "/tests/test_graphic_real_jwd.py",
        "/tests/test_writer_native_batch2.py",
        "/tests/test_writer_native_batch3.py",
        "/tests/test_writer_native_batch4.py",
        "/tests/test_reader_native_exports.py",
        "/tests/test_writer_fixture_manifests.py",
        "/tests/fixtures/build_mapgis_fixtures.py",
        # test_public_fixtures.py reads the manifest at module scope; an sdist
        # without it passes inspection but crashes the shipped tests.
        "/tests/fixtures/fixture_manifest.json",
        "/tests/fixtures/writer_batch2_manifest.json",
        "/tests/fixtures/writer_batch3_manifest.json",
        "/tests/fixtures/writer_batch4_manifest.json",
        "/tests/fixtures/reader_native_manifest.json",
        "/tests/fixtures/mapgis/synthetic_points.wt",
        "/tests/fixtures/mapgis/synthetic_lines.wl",
        "/tests/fixtures/mapgis/synthetic_polygons.wp",
        "/tests/fixtures/jwd_slib_manifest.json",
    )
    required_suffixes += tuple(
        "/tests/fixtures/writer_batch2/" + name for name in WRITER_BATCH2_NAMES
    )
    required_suffixes += tuple(
        "/tests/fixtures/writer_batch3/" + name for name in WRITER_BATCH3_NAMES
    )
    required_suffixes += tuple(
        "/tests/fixtures/writer_batch4/" + name for name in WRITER_BATCH4_NAMES
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
