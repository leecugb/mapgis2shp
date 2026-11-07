# SPDX-License-Identifier: Apache-2.0
"""Locate the synthetic and real MapGIS regression fixtures.

The same files are available in source checkouts under ``tests/fixtures`` and
in wheel installations under ``pymapgis/testing/fixtures``. Callers should use
these helpers rather than depending on either absolute layout.
"""
from __future__ import annotations

from pathlib import Path

__all__ = ["fixture_path", "jwd_path", "slib_path"]


def _candidate_roots():
    yield Path(__file__).with_name("fixtures")
    yield Path(__file__).resolve().parents[3] / "tests" / "fixtures"


def fixture_path(*parts: str) -> Path:
    """Return an existing fixture path, or raise a clear FileNotFoundError."""
    for root in _candidate_roots():
        candidate = root.joinpath(*parts)
        if candidate.exists():
            return candidate
    target = "/".join(parts) or "the fixture root"
    raise FileNotFoundError(f"Cannot locate {target} in installed or source fixtures")


def jwd_path(name: str = "") -> Path:
    """Return the JWD fixture directory or one of its twelve vector files."""
    return fixture_path("jwd", name)


def slib_path(name: str = "") -> Path:
    """Return the SLIB fixture directory or one of its five library files."""
    return fixture_path("slib", name)
