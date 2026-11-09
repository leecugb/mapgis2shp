"""Verify Writer-native fixture inventories and per-file checksums."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from pymapgis.testing import fixture_path

TEXT_SUFFIXES = {".cpg", ".prj", ".csv", ".md", ".json"}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_file_bytes(path):
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n"), True
    return data, False


@pytest.mark.parametrize("batch", [2, 3])
def test_writer_manifest_bytes_and_sha256(batch):
    root = fixture_path(f"writer_batch{batch}")
    manifest = json.loads(
        fixture_path(f"writer_batch{batch}_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["case_count"] == len(list(root.glob("*.shp")))
    assert manifest["file_count"] == len(manifest["files"])
    assert manifest["file_count"] == len(list(root.iterdir()))
    assert manifest["total_bytes"] == sum(item["bytes"] for item in manifest["files"].values())
    for name, expected in manifest["files"].items():
        path = root / name
        assert path.is_file(), name
        data, is_text = manifest_file_bytes(path)
        expected_size = expected["lf_bytes"] if is_text else expected["bytes"]
        expected_hash = expected["lf_sha256"] if is_text else expected["sha256"]
        assert len(data) == expected_size, name
        assert hashlib.sha256(data).hexdigest() == expected_hash, name


def test_writer_batch4_manifest_bytes_and_sha256():
    root = fixture_path("writer_batch4")
    manifest_path = fixture_path("writer_batch4_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert (root / "writer_batch4_manifest.json").read_bytes() == manifest_path.read_bytes()
    assert len(manifest["cases"]) == 20
    assert len(list(root.glob("*.shp"))) == 20
    assert sum(len(case["files"]) for case in manifest["cases"]) == 100
    assert sum(case["native_file"] is not None for case in manifest["cases"]) == 18
    expected_names = {"README_转换说明.md", "writer_batch4_manifest.json"}
    for case in manifest["cases"]:
        for expected in case["files"]:
            path = root / expected["file"]
            expected_names.add(expected["file"])
            assert path.is_file(), expected["file"]
            assert path.stat().st_size == expected["bytes"], expected["file"]
            assert sha256(path) == expected["sha256"], expected["file"]
        if case["native_file"] is not None:
            native = root / case["native_file"]
            expected_names.add(case["native_file"])
            assert native.is_file(), case["native_file"]
            assert sha256(native) == case["native_sha256"], case["native_file"]
    assert {path.name for path in root.iterdir()} == expected_names
    assert len(list(root.iterdir())) == 120


def test_writer_case_lists_cannot_be_empty():
    from tests import test_writer_native_batch2 as batch2
    from tests import test_writer_native_batch3 as batch3
    from tests import test_writer_native_batch4 as batch4

    assert len(batch2.CASES) == 11
    assert len(batch3.CASES) == 12
    assert len(batch4.CASES) == 20


def test_reader_native_manifest_bytes_and_sha256():
    configured = os.environ.get("PYMAPGIS_READER_NATIVE")
    if configured:
        root = Path(configured)
    else:
        try:
            root = fixture_path("reader_native")
        except FileNotFoundError as exc:
            pytest.skip(f"Optional native SHP fixture is unavailable: {exc}")
    manifest = json.loads(fixture_path("reader_native_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["files"]) == 16
    expected_names = {expected["file"] for expected in manifest["files"]}
    assert {path.name for path in root.iterdir()} == expected_names
    for expected in manifest["files"]:
        path = root / expected["file"]
        assert path.is_file(), expected["file"]
        assert path.stat().st_size == expected["bytes"], expected["file"]
        assert sha256(path) == expected["sha256"], expected["file"]
