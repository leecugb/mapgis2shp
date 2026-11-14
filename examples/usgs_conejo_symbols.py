#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Source-aware MapGIS symbol construction for the USGS Conejo Well data."""
from __future__ import annotations

import math
from typing import Iterable

import geopandas as gpd

LEFT_SLIP_SYMBOL = 239
LEFT_SLIP_SIZE_MM = 3.0
LEFT_SLIP_PEN_WIDTH_MM = 0.15


def nearest_fault_tangent(point, fault_geometries: Iterable):
    """Return (nearest distance, tangent angle counter-clockwise from east)."""
    best = None
    for geometry in fault_geometries:
        if geometry is None or geometry.is_empty or geometry.length <= 0:
            continue
        distance = point.distance(geometry)
        if best is None or distance < best[0]:
            best = (distance, geometry)
    if best is None:
        raise ValueError("Left-slip ornament requires a non-empty fault layer")

    distance, geometry = best
    position = geometry.project(point)
    before = geometry.interpolate(max(0.0, position - 1.0))
    after = geometry.interpolate(min(geometry.length, position + 1.0))
    dx = after.x - before.x
    dy = after.y - before.y
    if math.hypot(dx, dy) == 0:
        raise ValueError("Cannot determine the local fault tangent")
    return distance, math.degrees(math.atan2(dy, dx))


def nearest_fault_angle(point, fault_geometries: Iterable) -> float:
    """Return the local nearest-fault tangent angle, counter-clockwise from east."""
    return nearest_fault_tangent(point, fault_geometries)[1]


def fault_geometries(frame):
    """Select fault geometry from either converter or six-file field names."""
    if "FEAT_TYPE" in frame:
        mask = frame["FEAT_TYPE"].fillna("").astype(str).str.strip() == "fault"
    elif "FEATURE_TYPE" in frame:
        mask = frame["FEATURE_TYPE"].fillna("").astype(str).str.strip() == "fault"
    else:
        raise ValueError("Fault layer requires FEAT_TYPE or FEATURE_TYPE")
    return frame.loc[mask].geometry


def expand_left_slip_ornaments(frame, faults) -> gpd.GeoDataFrame:
    """Expand each USGS left-slip marker into two native SLIB 239 records.

    SLIB 239 is a half-arrow. A left-slip map marker needs a reverse-directed
    pair, while the source coverage stores only one point for the pair. The two
    output records retain the same ``source_id`` and all source attributes.
    """
    geometries = list(fault_geometries(faults) if hasattr(faults, "columns") else faults)
    records = []
    distances = []
    for row in frame.to_dict("records"):
        distance, angle = nearest_fault_tangent(row["geometry"], geometries)
        distances.append(distance)
        for offset in (0.0, 180.0):
            component = row.copy()
            component.update({
                "point_type": 1,
                "symbol_no": LEFT_SLIP_SYMBOL,
                "height": LEFT_SLIP_SIZE_MM,
                "width": LEFT_SLIP_SIZE_MM,
                "pen_width": max(
                    float(row.get("pen_width") or 0.0), LEFT_SLIP_PEN_WIDTH_MM
                ),
                "angle": angle + offset,
            })
            records.append(component)
    result = gpd.GeoDataFrame(records, geometry="geometry", crs=frame.crs)
    result.attrs = frame.attrs.copy()
    result.attrs["source_feature_count"] = len(frame)
    result.attrs["nearest_fault_distances_m"] = distances
    return result
