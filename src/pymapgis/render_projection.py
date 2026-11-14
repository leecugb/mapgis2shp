"""Target-CRS resolution for rendering pipelines.

Reader never calls :func:`to_crs`.  These helpers run after layers are loaded,
choose one target CRS for the whole map, and reproject every layer explicitly.
"""
from __future__ import annotations

import math
import shlex
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pyproj

_DATUM_KEYS = {"ellps", "datum", "towgs84", "R", "a", "b", "f", "rf", "pm"}


def _has_crs(layer: Any) -> bool:
    crs = getattr(layer, "crs", None)
    return crs is not None and str(crs).strip() != ""


def _as_crs(value: Any) -> pyproj.CRS:
    return value if isinstance(value, pyproj.CRS) else pyproj.CRS.from_user_input(value)


def _datum_clause(crs: pyproj.CRS) -> Tuple[Tuple[str, str], ...]:
    """Preserve datum-defining parameters without copying projection settings."""
    tokens = shlex.split(crs.to_proj4())
    values = []
    for token in tokens:
        if not token.startswith("+") or "=" not in token:
            continue
        key, value = token[1:].split("=", 1)
        if key in _DATUM_KEYS:
            values.append((key, value))
    return tuple(sorted(values))


def _central_meridian(longitude: float, zone_width: int) -> Tuple[int, float]:
    if zone_width == 6:
        zone = math.floor((longitude + 180.0) / 6.0) + 1
        return zone, 6.0 * zone - 183.0
    if zone_width == 3:
        zone = math.floor(longitude / 3.0 + 0.5)
        return zone, 3.0 * zone
    raise ValueError("zone_width must be 6 or 3")


def gauss_kruger_crs(
    longitude: float,
    source_crs: Any,
    *,
    zone_width: int = 6,
    latitude: float = 0.0,
) -> Tuple[pyproj.CRS, Dict[str, Any]]:
    """Construct a source-datum Gauss-Kruger CRS around *longitude*."""
    if not math.isfinite(longitude) or not -180.0 <= longitude <= 180.0:
        raise ValueError("Mean longitude must be finite and within [-180, 180]")
    if abs(longitude) == 180.0:
        raise ValueError("Automatic zoning at the antimeridian requires an explicit target CRS")
    if not math.isfinite(latitude) or abs(latitude) > 84.0:
        raise ValueError("Automatic Gauss-Kruger zoning requires |mean latitude| <= 84 degrees")
    source = _as_crs(source_crs)
    zone, central = _central_meridian(longitude, zone_width)
    parameters = [
        "+proj=tmerc",
        "+lat_0=0",
        f"+lon_0={central:g}",
        "+k=1",
        "+x_0=500000",
        f"+y_0={10000000 if latitude < 0 else 0}",
        "+units=m",
    ]
    parameters.extend(f"+{key}={value}" for key, value in _datum_clause(source))
    parameters.append("+no_defs")
    target = pyproj.CRS.from_proj4(" ".join(parameters))
    metadata = {
        "target_source": "default_gauss_kruger",
        "zone": zone,
        "zone_width": zone_width,
        "central_meridian": central,
        "mean_longitude": longitude,
        "mean_latitude": latitude,
        "datum_policy": "preserve_source",
    }
    return target, metadata


def _geographic_bounds(layer: Any) -> Tuple[float, float, float, float]:
    geographic = layer.to_crs(4326)
    values = tuple(float(value) for value in geographic.total_bounds)
    if len(values) != 4 or not all(math.isfinite(value) for value in values):
        raise ValueError("Cannot infer a target CRS from non-finite layer bounds")
    return values


def resolve_render_crs(
    layers: Sequence[Any],
    target_crs: Any = None,
    *,
    zone_width: int = 6,
) -> Tuple[pyproj.CRS, Dict[str, Any]]:
    """Resolve one explicit or mean-longitude Gauss-Kruger target CRS."""
    if target_crs is not None:
        target = _as_crs(target_crs)
        return target, {
            "target_source": "explicit",
            "zone_width": zone_width,
            "datum_policy": "explicit_target",
        }
    non_empty = [layer for layer in layers if len(layer) > 0]
    if not non_empty:
        raise ValueError("Cannot infer a default target CRS when every layer is empty")
    if any(not _has_crs(layer) for layer in non_empty):
        raise ValueError("Default target-CRS inference requires source CRS metadata")
    signatures = {_datum_clause(_as_crs(layer.crs)) for layer in non_empty}
    if len(signatures) != 1:
        raise ValueError("Mixed source datums require an explicit target CRS")
    bounds = [_geographic_bounds(layer) for layer in non_empty]
    xmin = min(item[0] for item in bounds)
    ymin = min(item[1] for item in bounds)
    xmax = max(item[2] for item in bounds)
    ymax = max(item[3] for item in bounds)
    if xmax - xmin > 180.0:
        raise ValueError("Antimeridian-spanning data require an explicit target CRS")
    if xmax - xmin > 9.0:
        raise ValueError("Data spanning more than 9 degrees require an explicit target CRS")
    mean_longitude = (xmin + xmax) / 2.0
    mean_latitude = (ymin + ymax) / 2.0
    target, metadata = gauss_kruger_crs(
        mean_longitude,
        non_empty[0].crs,
        zone_width=zone_width,
        latitude=mean_latitude,
    )
    metadata["geographic_bounds"] = [xmin, ymin, xmax, ymax]
    return target, metadata


def prepare_render_layers(
    layers: Iterable[Any],
    *,
    target_crs: Any = None,
    source_crs: Any = None,
    zone_width: int = 6,
    map_units_per_mm: Optional[float] = None,
) -> Tuple[List[Any], Optional[pyproj.CRS], Dict[str, Any]]:
    """Assign missing source CRS and reproject all layers to one target.

    A CRS-less layer may be drawn without reprojection only when
    ``map_units_per_mm`` is explicitly supplied and no target CRS is requested.
    """
    prepared = []
    for layer in layers:
        if not _has_crs(layer) and source_crs is not None:
            layer = layer.set_crs(source_crs, allow_override=True)
        prepared.append(layer)
    unresolved = [layer for layer in prepared if len(layer) > 0 and not _has_crs(layer)]
    if unresolved:
        if map_units_per_mm is None:
            raise ValueError("Layers without CRS require source_crs or map_units_per_mm")
        if target_crs is not None:
            raise ValueError("A target CRS cannot be applied when source CRS is missing")
        return prepared, None, {
            "target_source": "unprojected_explicit_units",
            "zone_width": zone_width,
            "datum_policy": "unavailable",
        }
    target, metadata = resolve_render_crs(prepared, target_crs, zone_width=zone_width)
    projected = []
    for layer in prepared:
        if len(layer) == 0 and not _has_crs(layer):
            layer = layer.set_crs(target, allow_override=True)
        elif _as_crs(layer.crs) != target:
            layer = layer.to_crs(target)
        projected.append(layer)
    metadata["target_crs_wkt"] = target.to_wkt("WKT2_2019")
    return projected, target, metadata
