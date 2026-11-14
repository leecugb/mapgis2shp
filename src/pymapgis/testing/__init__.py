# SPDX-License-Identifier: Apache-2.0
"""Locate bundled fixtures and optional user-supplied JWD/SLIB data.

Synthetic, USGS, Writer, testdata and generic SLIB fixtures are available in
source checkouts under ``tests/fixtures`` and in wheel installations under
``pymapgis/testing/fixtures``. Original NGAC JWD vectors remain external and
must be supplied through ``PYMAPGIS_JWD`` when no authorized local copy exists.
``PYMAPGIS_SLIB`` can always override the bundled generic SLIB directory.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

__all__ = ["fixture_path", "jwd_path", "slib_path", "testdata_path", "usgs_conejo_path"]


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


def _external_path(env_var: str, parts: Tuple[str, ...]) -> Optional[Path]:
    configured = os.environ.get(env_var)
    if not configured:
        return None
    candidate = Path(configured).joinpath(*parts)
    if candidate.exists():
        return candidate
    target = "/".join(parts) or "the fixture root"
    raise FileNotFoundError(f"{env_var} points to a missing fixture: {candidate} ({target})")


def usgs_conejo_path(name: str = "") -> Path:
    """Return the bundled public-domain USGS Conejo Well fixture path."""
    return fixture_path("usgs_conejo", name)


def testdata_path(name: str = "") -> Path:
    """Return the bundled seven-layer standard-renderer testdata path."""
    return fixture_path("testdata", name)


def jwd_path(name: str = "") -> Path:
    """Return an external JWD directory/file or raise acquisition guidance."""
    external = _external_path("PYMAPGIS_JWD", (name,))
    if external is not None:
        return external
    try:
        return fixture_path("jwd", name)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "Original JWD data are not bundled. Obtain sheet J43C001002 through its "
            "official channel, then set PYMAPGIS_JWD to the directory containing "
            "the twelve original vectors. See DATA_ATTRIBUTION.md."
        ) from exc


def slib_path(name: str = "") -> Path:
    """Return bundled generic SLIB or an external override directory/file."""
    external = _external_path("PYMAPGIS_SLIB", (name,))
    if external is not None:
        return external
    try:
        return fixture_path("slib", name)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "The bundled generic SLIB fixture is unavailable. Install the complete "
            "mapgis2shp source/wheel fixture package, or set PYMAPGIS_SLIB to a "
            "directory containing the five matching libraries. See DATA_ATTRIBUTION.md."
        ) from exc
