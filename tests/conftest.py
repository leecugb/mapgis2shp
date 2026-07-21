"""Shared pytest fixtures and utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

DATA_DIR = Path(__file__).parent.parent


def _glob_first(pattern: str) -> Path:
    """Return the first file matching a glob pattern, or skip the test."""
    matches = sorted(DATA_DIR.glob(pattern))
    if not matches:
        pytest.skip(f"No test data matching {pattern!r}")
    return matches[0]


@pytest.fixture
def sample_wt() -> Path:
    return _glob_first("*.WT")


@pytest.fixture
def sample_wl() -> Path:
    return _glob_first("*.WL")


@pytest.fixture
def sample_wp() -> Path:
    return _glob_first("*.WP")


@pytest.fixture
def baseline() -> Dict[str, Any]:
    path = DATA_DIR / "pymapgis_baseline.json"
    if not path.exists():
        pytest.skip("pymapgis_baseline.json not found")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
