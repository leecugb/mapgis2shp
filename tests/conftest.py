"""Shared pytest fixtures and utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

DATA_DIR = Path(__file__).parent.parent
PUBLIC_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mapgis"


def _glob_first(pattern: str, public_name: str) -> Path:
    """Return a local real-data match, or fall back to a public fixture."""
    matches = sorted(DATA_DIR.glob(pattern))
    if matches:
        return matches[0]
    public = PUBLIC_FIXTURE_DIR / public_name
    if public.is_file():
        return public
    pytest.skip(f"No test data matching {pattern!r} or public fixture {public_name!r}")


@pytest.fixture
def sample_wt() -> Path:
    return _glob_first("*.WT", "synthetic_points.wt")


@pytest.fixture
def sample_wl() -> Path:
    return _glob_first("*.WL", "synthetic_lines.wl")


@pytest.fixture
def sample_wp() -> Path:
    return _glob_first("*.WP", "synthetic_polygons.wp")


@pytest.fixture
def baseline() -> Dict[str, Any]:
    path = DATA_DIR / "pymapgis_baseline.json"
    if not path.exists():
        pytest.skip("pymapgis_baseline.json not found")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
