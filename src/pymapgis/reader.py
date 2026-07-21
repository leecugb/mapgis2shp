"""
pymapgis.reader
Provides reading support for MapGIS *.wt, *.wl, *.wp geospatial vector files.

Compatible with Python 3.9+.
"""

from __future__ import annotations

import datetime
import os
import struct
from collections import deque
from dataclasses import dataclass
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
import pyproj
import shapely
import shapely.geometry

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAGIC_POINT = b"WMAP`D22"
_MAGIC_LINE = b"WMAP`D21"
_MAGIC_POLYGON = b"WMAP`D23"

_GEOMETRY_TYPE_MAP = {
    _MAGIC_POINT: "POINT",
    _MAGIC_LINE: "LINE",
    _MAGIC_POLYGON: "POLYGON",
}

_HEADER_COUNT = 10
_HEADER_RECORD_SIZE = 10

_POINT_RECORD_SIZE = 93
_LINE_RECORD_SIZE = 57
_ARC_RECORD_SIZE = 57
_TOPO_RECORD_SIZE = 24

# MapGIS stores geometry type codes in the attribute table.
_ATTR_TYPE_STRING = 0
_ATTR_TYPE_BYTE = 1
_ATTR_TYPE_SHORT = 2
_ATTR_TYPE_INT = 3
_ATTR_TYPE_FLOAT = 4
_ATTR_TYPE_DOUBLE = 5
_ATTR_TYPE_DATE = 6
_ATTR_TYPE_TIME = 7

# CRS parameter byte offsets in the file header.
_CRS_PROJECTION_OFFSET = 109
_CRS_ELLIPSOID_OFFSET = 110
_CRS_SCALE_OFFSET = 143
_CRS_CENTRAL_MERIDIAN_OFFSET = 151
_CRS_STD_LAT_OFFSET = 175

# Which of the 10 header sections holds the attribute table.
_ATTR_HEADER_INDEX = {
    "POINT": 2,
    "LINE": 2,
    "POLYGON": 9,
}

# PROJ4 ellipsoid strings indexed by MapGIS ellipsoid code.
_ELLIPSOID_PROJ4 = {
    1: "+ellps=krass +towgs84=15.8,-154.4,-82.3,0,0,0,0 +units=m +no_defs",
    2: "+a=6378140 +b=6356755.288157528",
    7: "+datum=WGS84",
    9: "+ellps=WGS72",
    10: "+ellps=aust_SA +towgs84=-117.808,-51.536,137.784,0.303,0.446,0.234,-0.29",
    11: "+ellps=aust_SA +towgs84=-134,-48,149,0,0,0,0",
    16: "+ellps=krass",
    116: "+ellps=clrk80 +towgs84=-166,-15,204,0,0,0,0",
    "cgcs2000": "+ellps=GRS80",
}

# struct format characters for little-endian decoding.
_STRUCT_FORMATS = {
    _ATTR_TYPE_BYTE: "B",
    _ATTR_TYPE_SHORT: "h",
    _ATTR_TYPE_INT: "i",
    _ATTR_TYPE_FLOAT: "f",
    _ATTR_TYPE_DOUBLE: "d",
}

_ATTR_TYPE_NAMES = {
    _ATTR_TYPE_STRING: "string",
    _ATTR_TYPE_BYTE: "byte",
    _ATTR_TYPE_SHORT: "short integer",
    _ATTR_TYPE_INT: "integer",
    _ATTR_TYPE_FLOAT: "float",
    _ATTR_TYPE_DOUBLE: "double",
    _ATTR_TYPE_DATE: "date",
    _ATTR_TYPE_TIME: "time",
}

# Little-endian layout of one 39-byte field descriptor:
#   name(20s) type(B) offset(i) pad(2x) length(h) pad(4x) decimals(h) pad(4x)
# Standard (no-alignment) byte order keeps the fields at their documented offsets.
_FIELD_DESCRIPTOR_STRUCT = struct.Struct("<20sBi2xh4xh4x")
assert _FIELD_DESCRIPTOR_STRUCT.size == 39


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class MapGISError(Exception):
    """Base exception for MapGIS reader errors."""


class InvalidFileError(MapGISError):
    """Raised when the file does not appear to be a supported MapGIS file."""

    def __str__(self) -> str:
        return "cannot detect the file's geometry type"


class InvalidDirectoryError(MapGISError):
    """Raised when a required directory or project file is missing."""


class TopoError(MapGISError):
    """Raised when polygon topology cannot be reconstructed."""

    def __str__(self) -> str:
        return "topo error in this wp file"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decode_gbk(buf: bytes) -> str:
    """Decode a byte buffer as GBK, stripping trailing nulls.

    If the buffer contains invalid GBK bytes, decode up to the first invalid
    byte. This matches the behaviour of the original implementation.
    """
    buf = buf.split(b"\x00", 1)[0]
    try:
        return buf.decode("gbk")
    except UnicodeDecodeError as exc:
        return buf[: exc.start].decode("gbk")


def _raw_dms_to_degrees(raw: float) -> float:
    """Convert a MapGIS DMS-encoded double to decimal degrees.

    The value is stored as ``DDDMMSS.sss`` (degrees, minutes, seconds) where
    the integer part packs degrees, minutes, and seconds and the fractional
    part holds sub-second precision. Arithmetic decoding avoids the rounding
    and sign pitfalls of a string-based approach: it preserves fractional
    seconds (lost when formatting with ``:.0f``) and handles western
    longitudes (negative values) and short values without zero-padding.
    """
    sign = -1.0 if raw < 0 else 1.0
    a = abs(raw)
    # Split off the MMSS.sss tail; the remaining whole is DDD * 10000.
    ms = a % 10000.0
    degrees = (a - ms) / 10000.0
    minutes = int(ms // 100.0)
    seconds = ms - minutes * 100.0
    return sign * (degrees + minutes / 60.0 + seconds / 3600.0)


def _read_struct(file_obj: BinaryIO, fmt: str) -> Tuple[Any, ...]:
    """Read *size* bytes from *file_obj* and unpack with struct."""
    size = struct.calcsize(fmt)
    buf = file_obj.read(size)
    if len(buf) < size:
        raise MapGISError(f"unexpected end of file: needed {size} bytes, got {len(buf)}")
    return struct.unpack(fmt, buf)

# ---------------------------------------------------------------------------
# Attribute table
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Field:
    """Descriptor for one column in the MapGIS attribute table."""

    name: str
    type_code: int
    offset: int
    length: int
    decimals: int

    @property
    def type_name(self) -> str:
        return _ATTR_TYPE_NAMES.get(self.type_code, f"unknown({self.type_code})")


def _decode_attribute_field(record: bytes, field: _Field) -> Any:
    """Decode a single attribute field from a raw record."""
    if field.type_code == _ATTR_TYPE_STRING:
        return _decode_gbk(record[field.offset : field.offset + field.length])

    if field.type_code == _ATTR_TYPE_DATE:
        chunk = record[field.offset : field.offset + max(field.length, 4)]
        if len(chunk) < 4:
            return None
        year = struct.unpack("<h", chunk[:2])[0]
        month = chunk[2]
        day = chunk[3]
        # Source data occasionally carries a zero month/day for missing dates;
        # fall back to None instead of raising ValueError mid-parse.
        try:
            return datetime.date(year, month, day)
        except (ValueError, OverflowError):
            return None

    if field.type_code == _ATTR_TYPE_TIME:
        chunk = record[field.offset : field.offset + max(field.length, 10)]
        if len(chunk) < 10:
            return None
        hour = chunk[0]
        minute = chunk[1]
        seconds = struct.unpack("<d", chunk[2:10])[0]
        sec_whole = int(np.floor(seconds))
        microsec = int(1_000_000 * (seconds - sec_whole))
        try:
            return datetime.time(hour, minute, sec_whole, microsec)
        except (ValueError, OverflowError):
            return None

    fmt = _STRUCT_FORMATS.get(field.type_code)
    if fmt is None:
        return None
    size = struct.calcsize(f"<{fmt}")
    chunk = record[field.offset : field.offset + size]
    return struct.unpack(f"<{fmt}", chunk)[0]


def _read_attribute_records(
    file_obj: BinaryIO,
    record_count: int,
    record_length: int,
    fields: List[_Field],
) -> pd.DataFrame:
    """Read attribute records assuming the file position is at the first record."""
    # Skip the empty first record (MapGIS convention).
    file_obj.read(record_length)

    if record_count <= 1:
        return pd.DataFrame(columns=[field.name for field in fields])

    # Read all remaining records in one go, then split into fixed-length views.
    total_bytes = (record_count - 1) * record_length
    records_buf = file_obj.read(total_bytes)
    if len(records_buf) < total_bytes:
        usable = len(records_buf) // record_length
        records_buf = records_buf[: usable * record_length]
    else:
        usable = record_count - 1

    records: List[List[Any]] = []
    for i in range(usable):
        start = i * record_length
        record = records_buf[start : start + record_length]
        records.append([_decode_attribute_field(record, field) for field in fields])

    return pd.DataFrame(records, columns=[field.name for field in fields])


def _read_attribute_header(
    file_obj: BinaryIO, start: int
) -> Tuple[int, int, List[_Field]]:
    """Read the attribute table header and return (record_count, record_length, fields).

    The 322-byte fixed prefix is followed by field_count (int16), record_count
    (int32) and record_length (int16), then 18 bytes of padding, so the field
    descriptors begin at offset 348 within the attribute section. The prefix
    and descriptors are read in two bulk reads and unpacked structurally,
    avoiding one syscall per field as the previous per-read loop did.
    """
    file_obj.seek(start)

    # 322 (prefix) + 2 + 4 + 2 + 18 (padding) = 348 bytes precede the descriptors.
    head = file_obj.read(348)
    if len(head) < 348:
        raise MapGISError("attribute header too short")
    field_count, record_count, record_length = struct.unpack_from("<hih", head, 322)

    if field_count <= 0:
        return record_count, record_length, []

    desc_size = _FIELD_DESCRIPTOR_STRUCT.size
    desc_buf = file_obj.read(field_count * desc_size)
    n_fields = len(desc_buf) // desc_size

    fields: List[_Field] = []
    for i in range(n_fields):
        name_raw, type_code, offset, length, decimals = (
            _FIELD_DESCRIPTOR_STRUCT.unpack_from(desc_buf, i * desc_size)
        )
        if type_code in _ATTR_TYPE_NAMES:
            fields.append(
                _Field(_decode_gbk(name_raw), type_code, offset, length, decimals)
            )

    return record_count, record_length, fields


# ---------------------------------------------------------------------------
# Coordinate reference system
# ---------------------------------------------------------------------------


def _read_crs(file_obj: BinaryIO) -> Tuple[Any, float]:
    """Read the coordinate reference system and geometry scale factor.

    Returns
    -------
    crs : pyproj.CRS or str
        The detected CRS, or an empty string if no valid CRS was found.
    scale : float
        Factor applied to raw coordinates to obtain map units.
    """
    file_obj.seek(_CRS_PROJECTION_OFFSET)
    projection_code = ord(file_obj.read(1))

    file_obj.seek(_CRS_ELLIPSOID_OFFSET)
    ellipsoid_code = ord(file_obj.read(1))

    file_obj.seek(_CRS_SCALE_OFFSET)
    scale = _read_struct(file_obj, "<d")[0]

    proj_name = {5: "tmerc", 2: "aea", 3: "lcc"}.get(projection_code)
    ellipsoid = _ELLIPSOID_PROJ4.get(ellipsoid_code)

    if ellipsoid is None or scale == 0:
        return "", 1.0

    # Longitude/latitude (unprojected).
    if projection_code == 0:
        crs = pyproj.CRS(f"+proj=longlat {ellipsoid} +no_defs")
        return crs, scale

    if proj_name is None:
        return "", 1.0

    # Projected CRS: scale is stored in mm/map-unit; convert to m.
    scale = scale / 1000.0

    file_obj.seek(_CRS_CENTRAL_MERIDIAN_OFFSET)
    central_meridian = _read_struct(file_obj, "<d")[0]
    central_meridian = _raw_dms_to_degrees(central_meridian)

    if projection_code == 5:  # Transverse Mercator
        crs = pyproj.CRS(
            f"+proj={proj_name} +lat_0=0 +lon_0={central_meridian} +k=1 "
            f"+x_0=500000 +y_0=0 {ellipsoid} +units=m +no_defs"
        )
        return crs, scale

    if projection_code in (2, 3):  # Albers / Lambert
        file_obj.seek(_CRS_STD_LAT_OFFSET)
        lat0 = _read_struct(file_obj, "<d")[0]
        lat1 = _read_struct(file_obj, "<d")[0]
        lat2 = _read_struct(file_obj, "<d")[0]
        x_0 = _read_struct(file_obj, "<d")[0]
        y_0 = _read_struct(file_obj, "<d")[0]

        lat_0 = _raw_dms_to_degrees(lat0)
        lat_1 = _raw_dms_to_degrees(lat1)
        lat_2 = _raw_dms_to_degrees(lat2)

        crs = pyproj.CRS(
            f"+proj={proj_name} +lat_0={lat_0} +lon_0={central_meridian} "
            f"+lat_1={lat_1} +lat_2={lat_2} +x_0={x_0} +y_0={y_0} "
            f"{ellipsoid} +units=m +no_defs"
        )
        return crs, scale

    return "", 1.0


# ---------------------------------------------------------------------------
# Geometry parsing
# ---------------------------------------------------------------------------


def _read_header_entries(file_obj: BinaryIO, data_start: int) -> List[Tuple[int, int]]:
    """Read the 10 header section entries and return (start, volume) tuples."""
    file_obj.seek(data_start)
    entries: List[Tuple[int, int]] = []
    for _ in range(_HEADER_COUNT):
        buf = file_obj.read(_HEADER_RECORD_SIZE)
        if len(buf) < 8:
            raise MapGISError("header entry too short")
        start, volume = struct.unpack("<2i", buf[:8])
        entries.append((start, volume))
    return entries


def _read_points(
    file_obj: BinaryIO, start: int, section_size: int, scale: float
) -> List[shapely.geometry.Point]:
    """Read point geometries from the point section.

    PDF article: each point record is 93 bytes; the first record is empty.
    X coordinate is stored at bytes 7-14 and Y coordinate at bytes 15-22.
    """
    file_obj.seek(start)
    buf = file_obj.read(section_size)
    count = max(0, len(buf) // _POINT_RECORD_SIZE - 1)
    if count == 0:
        return []

    # Structured layout of the 93-byte point record.
    dtype = np.dtype([
        ("_pad1", "u1", 7),
        ("x", "<d"),
        ("y", "<d"),
        ("_pad2", "u1", 70),
    ])
    records = np.frombuffer(buf, dtype=dtype, offset=_POINT_RECORD_SIZE, count=count)
    coords = np.column_stack([records["x"], records["y"]]) * scale
    return [shapely.geometry.Point(xy) for xy in coords]


def _read_arc_index(
    file_obj: BinaryIO, start: int, section_size: int, record_size: int
) -> List[Tuple[int, int]]:
    """Read an arc index section and return (point_count, point_offset) pairs.

    PDF article: each arc/line index record is 57 bytes; the first record is
    empty.  The anchor point count is at bytes 10-13 and the coordinate offset
    (relative to the coordinate section start) is at bytes 14-17.
    """
    file_obj.seek(start)
    buf = file_obj.read(section_size)
    count = max(0, len(buf) // record_size - 1)
    if count == 0:
        return []

    dtype = np.dtype([
        ("_pad1", "u1", 10),
        ("point_count", "<i4"),
        ("point_offset", "<i4"),
        ("_pad2", "u1", record_size - 18),
    ])
    records = np.frombuffer(buf, dtype=dtype, offset=record_size, count=count)
    return list(zip(records["point_count"].tolist(), records["point_offset"].tolist()))


def _read_lines(
    file_obj: BinaryIO,
    start: int,
    section_size: int,
    coord_start: int,
    coord_size: int,
    scale: float,
) -> List[shapely.geometry.LineString]:
    """Read line geometries from the line/arc index and coordinate sections.

    PDF article: coordinates are stored sequentially as double-precision XY
    pairs (16 bytes per pair).  The arc index gives the byte offset and point
    count for each line.
    """
    index = _read_arc_index(file_obj, start, section_size, _LINE_RECORD_SIZE)
    if not index:
        return []

    file_obj.seek(coord_start)
    coord_buf = file_obj.read(coord_size)

    # NOTE: ``point_offset`` is a byte offset into the coordinate section and is
    # not guaranteed to be 8-byte aligned (MapGIS coordinate blocks can start at
    # arbitrary byte positions). Decode each arc from its own buffer slice
    # instead of treating the whole section as an aligned double array.
    geoms: List[shapely.geometry.LineString] = []
    for point_count, point_offset in index:
        if point_count < 0 or point_offset < 0:
            raise MapGISError(
                f"invalid arc index: point_count={point_count}, point_offset={point_offset}"
            )
        nbytes = point_count * 16
        raw = coord_buf[point_offset : point_offset + nbytes]
        if len(raw) < nbytes:
            raise MapGISError(
                f"coordinate block out of range: offset={point_offset}, "
                f"points={point_count}, section_size={len(coord_buf)}"
            )
        coords = np.frombuffer(raw, dtype="<d").reshape(-1, 2) * scale
        geoms.append(shapely.geometry.LineString(coords))
    return geoms


# ---------------------------------------------------------------------------
# Polygon topology
# ---------------------------------------------------------------------------


def _read_polygon_arcs(
    file_obj: BinaryIO,
    index_start: int,
    index_size: int,
    coord_start: int,
    coord_size: int,
    scale: float,
) -> List[shapely.geometry.LineString]:
    """Read raw polygon arcs (same structure as lines)."""
    return _read_lines(
        file_obj,
        index_start,
        index_size,
        coord_start,
        coord_size,
        scale,
    )


def _read_topology_table(file_obj: BinaryIO, start: int, section_size: int) -> np.ndarray:
    """Read the polygon topology table.

    PDF article: each topology record is 24 bytes; the first record is empty.
    The first 16 bytes contain 4 little-endian int32 values; columns 2 and 3
    (0-indexed) hold the left and right polygon IDs of the arc.
    """
    file_obj.seek(start)
    buf = file_obj.read(section_size)
    count = max(0, len(buf) // _TOPO_RECORD_SIZE - 1)
    if count == 0:
        return np.empty((0, 4), dtype=np.int32)

    dtype = np.dtype([
        ("ids", "<4i4"),
        ("_pad", "u1", 8),
    ])
    records = np.frombuffer(buf, dtype=dtype, offset=_TOPO_RECORD_SIZE, count=count)
    return records["ids"].copy()


class _PolygonTopologyBuilder:
    """Reconstruct shapely Polygon/MultiPolygon objects from MapGIS arcs."""

    def __init__(self, arcs: List[shapely.geometry.LineString], topology: np.ndarray):
        self.arcs = arcs
        self.topology = topology
        # Precompute polygon-ID -> [(arc_index, reverse), ...] mapping so that
        # ``build()`` does not rescan the full topology table for every polygon.
        self._pid_to_arcs: Dict[int, List[Tuple[int, bool]]] = {}
        for idx in range(len(topology)):
            left = int(topology[idx, 2])
            right = int(topology[idx, 3])
            if left != 0:
                self._pid_to_arcs.setdefault(left, []).append((idx, True))
            if right != 0 and right != left:
                self._pid_to_arcs.setdefault(right, []).append((idx, False))

    # Spatial-hash cell size for endpoint matching, in map units. Shared
    # endpoints coincide to within ~1e-6 (double-precision noise after the
    # scale multiply); 1e-5 covers that with a 10x margin while staying far
    # below any real vertex spacing, so distinct vertices never collide.
    _ENDPOINT_MATCH_TOL = 1e-5

    @staticmethod
    def _merge_arcs_into_rings(
        arcs: List[List[Tuple[float, float]]]
    ) -> List[List[Tuple[float, float]]]:
        """Chain arcs by matching endpoints into one or more closed rings.

        Arcs that share an endpoint are linked greedily until every arc has
        been consumed into a ring. Shared endpoints are *not* deduplicated,
        matching the behaviour of the original MapGIS reader: two arcs of
        length 2 and 4 sharing one endpoint yield a 6-point ring.

        This reproduces the original greedy global nearest-pair walk but
        replaces its O(n**3) per-iteration distance matrix with a spatial
        hash. At every step the nearest unused endpoint to each open end of
        the current chain is found in O(1) via a 3x3 cell probe (with an
        O(n) linear fallback for genuine topological gaps larger than the
        cell). The chain closes when its own two ends are at least as close
        as any external endpoint -- the same closure condition the original
        used to decide that a ring is complete -- so disjoint rings that
        share a polygon ID are kept separate rather than fused. The chain
        grows at whichever end is nearer its next neighbour, mirroring the
        original's ability to extend the chain in either direction.
        """
        tol = _PolygonTopologyBuilder._ENDPOINT_MATCH_TOL

        def key(pt: Tuple[float, float]) -> Tuple[int, int]:
            return (int(pt[0] // tol), int(pt[1] // tol))

        # endpoint_map: grid cell -> list of (arc_index, is_start)
        endpoint_map: Dict[Tuple[int, int], List[Tuple[int, bool]]] = {}
        for ai, arc in enumerate(arcs):
            if not arc:
                continue
            endpoint_map.setdefault(key(arc[0]), []).append((ai, True))
            endpoint_map.setdefault(key(arc[-1]), []).append((ai, False))

        used = [False] * len(arcs)

        def nearest(target: Tuple[float, float]) -> Optional[Tuple[float, int, bool]]:
            """Return (distance, arc_index, is_start) for the nearest unused
            endpoint to *target*, or None when no unused arc remains.

            Fast path probes the 3x3 neighbourhood of hashed candidates; if
            none is present the slow path scans every unused arc, matching
            the original global-nearest behaviour for genuine gaps.
            """
            tx, ty = target
            kx, ky = key(target)

            best: Optional[Tuple[float, int, bool]] = None
            for dkx in (-1, 0, 1):
                for dky in (-1, 0, 1):
                    for ai, is_start in endpoint_map.get((kx + dkx, ky + dky), ()):
                        if used[ai]:
                            continue
                        pt = arcs[ai][0] if is_start else arcs[ai][-1]
                        # Chebyshev distance, matching the original heuristic.
                        d = max(abs(pt[0] - tx), abs(pt[1] - ty))
                        if best is None or d < best[0]:
                            best = (d, ai, is_start)
            if best is not None:
                return best

            for ai, arc in enumerate(arcs):
                if used[ai] or not arc:
                    continue
                for is_start, pt in ((True, arc[0]), (False, arc[-1])):
                    d = max(abs(pt[0] - tx), abs(pt[1] - ty))
                    if best is None or d < best[0]:
                        best = (d, ai, is_start)
            return best

        rings: List[List[Tuple[float, float]]] = []
        for start in range(len(arcs)):
            if used[start] or not arcs[start]:
                continue
            used[start] = True
            chain: deque = deque(arcs[start])
            head = chain[0]
            tail = chain[-1]

            while True:
                d_head_tail = max(abs(head[0] - tail[0]), abs(head[1] - tail[1]))
                nt = nearest(tail)
                nh = nearest(head)
                d_tail = nt[0] if nt is not None else float("inf")
                d_head = nh[0] if nh is not None else float("inf")

                # Close when the chain's own ends are the nearest pair, i.e.
                # no external endpoint is strictly closer than head-to-tail.
                if d_head_tail <= d_tail and d_head_tail <= d_head:
                    break

                # Otherwise attach at whichever end is nearer its neighbour.
                # Ties favour the head, matching the original's endpoint
                # ordering (head precedes tail in the distance matrix).
                if d_head <= d_tail:
                    _, ai, is_start = nh
                    used[ai] = True
                    arc = arcs[ai]
                    if is_start:
                        # arc[0] sits at head; prepend arc so new head = arc[-1]
                        chain.extendleft(arc)
                    else:
                        # arc[-1] sits at head; prepend reversed so new head = arc[0]
                        chain.extendleft(reversed(arc))
                    head = chain[0]
                else:
                    _, ai, is_start = nt
                    used[ai] = True
                    arc = arcs[ai]
                    if is_start:
                        chain.extend(arc)            # arc starts at the tail
                    else:
                        chain.extend(reversed(arc))  # arc ends at the tail
                    tail = chain[-1]

            rings.append(list(chain))

        return rings

    @staticmethod
    def _build_multipolygon(
        rings: List[List[Tuple[float, float]]]
    ) -> shapely.geometry.MultiPolygon:
        """Build a MultiPolygon from closed rings, classifying shells and holes.

        This is a cleaned-up, iterative version of the original recursive
        ``get_multipolygons`` function.
        """
        if not rings:
            return shapely.geometry.MultiPolygon()

        remaining = [list(ring) for ring in rings]
        polygons: List[shapely.geometry.Polygon] = []

        while remaining:
            n = len(remaining)
            # Precompute shapely polygons and bounds once per ring; the naive
            # approach rebuilds every polygon inside the inner loop.
            polys: List[Optional[shapely.geometry.Polygon]] = []
            bounds: List[Optional[Tuple[float, float, float, float]]] = []
            for ring in remaining:
                try:
                    p = shapely.geometry.Polygon(ring)
                    polys.append(p)
                    bounds.append(p.bounds)
                except Exception:
                    polys.append(None)
                    bounds.append(None)

            within = np.zeros((n, n), dtype=bool)
            for i in range(n):
                poly_i = polys[i]
                if poly_i is None:
                    continue
                bounds_i = bounds[i]
                for j in range(n):
                    if i == j or polys[j] is None:
                        continue
                    # Bounding-box prefilter: a ring can only be within another
                    # ring if its bbox is fully inside the other's bbox.
                    bj = bounds[j]
                    if not (
                        bj[0] <= bounds_i[0]
                        and bj[1] <= bounds_i[1]
                        and bounds_i[2] <= bj[2]
                        and bounds_i[3] <= bj[3]
                    ):
                        continue
                    try:
                        contained = poly_i.within(polys[j])
                    except Exception:
                        contained = any(
                            shapely.geometry.Point(pt).within(polys[j])
                            for pt in remaining[i]
                        )
                    within[i, j] = bool(contained)

            # Rings with no parent are shells; rings contained in exactly one
            # other ring are direct holes of that shell.
            shell_to_holes: Dict[int, List[int]] = {}
            next_remaining: List[List[Tuple[float, float]]] = []

            for i in range(n):
                parent_count = int(within[i].sum())
                if parent_count == 0:
                    shell_to_holes.setdefault(i, [])
                elif parent_count == 1:
                    parent = int(np.argwhere(within[i])[0][0])
                    shell_to_holes.setdefault(parent, []).append(i)
                else:
                    # Nested hole: process in a later iteration.
                    next_remaining.append(remaining[i])

            for shell_idx, hole_indices in shell_to_holes.items():
                shell = remaining[shell_idx]
                holes = [remaining[h] for h in hole_indices]
                polygons.append(shapely.geometry.Polygon(shell, holes))

            remaining = next_remaining

        return shapely.geometry.MultiPolygon(polygons)

    def build(self, polygon_id: int) -> shapely.geometry.BaseGeometry:
        """Build the geometry for a single polygon ID."""
        entries = self._pid_to_arcs.get(polygon_id, [])
        if not entries:
            return shapely.geometry.Polygon()

        # Preserve the original orientation hint: when the left polygon ID
        # (column 2) matches the target ID, reverse the arc coordinates.
        oriented_arcs: List[List[Tuple[float, float]]] = []
        for arc_idx, reverse in entries:
            coords = list(self.arcs[arc_idx].coords)
            if reverse:
                coords = coords[::-1]
            oriented_arcs.append(coords)

        if len(oriented_arcs) == 1:
            # Single-arc polygon: preserve the original simple Polygon path.
            return shapely.geometry.Polygon(oriented_arcs[0])

        rings = self._merge_arcs_into_rings(oriented_arcs)
        return self._build_multipolygon(rings)


# ---------------------------------------------------------------------------
# Public Reader
# ---------------------------------------------------------------------------


class Reader:
    """Read a MapGIS vector file (*.wt, *.wl, *.wp) into a GeoDataFrame.

    Parameters
    ----------
    filepath : str or pathlib.Path
        Path to the MapGIS file.
    make_valid : bool, optional
        If True (default), apply ``shapely.make_valid`` to polygon geometries
        that are invalid after reconstruction. This fixes most self-intersection
        artifacts produced by the MapGIS arc-merging step without changing areas
        in any meaningful way. Set to False to obtain the raw reconstructed
        geometries (matching the behaviour of the original 1.0 reader).

    Examples
    --------
    >>> with Reader("example.wp") as r:
    ...     print(r)
    ...     r.geodataframe.to_file("example.shp")
    """

    def __init__(self, filepath: Any, make_valid: bool = True) -> None:
        self._filepath = os.fspath(filepath)
        self._make_valid = make_valid
        self.shapeType: Optional[str] = None
        self.crs: Any = ""
        self.bbox: Optional[np.ndarray] = None
        self.fields: List[Tuple[str, str, int]] = []
        self.data: pd.DataFrame = pd.DataFrame()
        self.geom: List[shapely.geometry.base.BaseGeometry] = []
        self.geodataframe: gpd.GeoDataFrame = gpd.GeoDataFrame()

        # The file is fully parsed and closed here; the context-manager
        # interface is kept only for backward compatibility.
        with open(self._filepath, "rb") as file_obj:
            self._parse(file_obj)

    def _parse(self, file_obj: BinaryIO) -> None:
        """Parse the entire file."""
        magic = file_obj.read(8)
        if magic not in _GEOMETRY_TYPE_MAP:
            raise InvalidFileError()
        self.shapeType = _GEOMETRY_TYPE_MAP[magic]

        file_obj.read(4)
        data_start = _read_struct(file_obj, "<i")[0]
        header_entries = _read_header_entries(file_obj, data_start)

        attr_start, _ = header_entries[_ATTR_HEADER_INDEX[self.shapeType]]
        record_count, record_length, fields = _read_attribute_header(
            file_obj, attr_start
        )
        self.fields = [
            (field.name, field.type_name, field.length) for field in fields
        ]
        self.data = _read_attribute_records(
            file_obj, record_count, record_length, fields
        )

        self.crs, scale = _read_crs(file_obj)

        geom_start, geom_size = header_entries[0]
        coord_start, coord_size = header_entries[1]

        if self.shapeType == "POINT":
            self.geom = _read_points(file_obj, geom_start, geom_size, scale)
        elif self.shapeType == "LINE":
            self.geom = _read_lines(
                file_obj, geom_start, geom_size, coord_start, coord_size, scale
            )
        elif self.shapeType == "POLYGON":
            self.geom = self._read_polygons(
                file_obj,
                geom_start,
                geom_size,
                coord_start,
                coord_size,
                scale,
                header_entries[3],
            )

        self._build_geodataframe()

    def _read_polygons(
        self,
        file_obj: BinaryIO,
        index_start: int,
        index_size: int,
        coord_start: int,
        coord_size: int,
        scale: float,
        topo_entry: Tuple[int, int],
    ) -> List[shapely.geometry.base.BaseGeometry]:
        """Read polygon geometries."""
        arcs = _read_polygon_arcs(
            file_obj, index_start, index_size, coord_start, coord_size, scale
        )
        topo_start, topo_size = topo_entry
        topology = _read_topology_table(file_obj, topo_start, topo_size)

        builder = _PolygonTopologyBuilder(arcs, topology)

        # Active polygon IDs are the non-zero values in columns 2 and 3.
        active_ids = sorted({int(pid) for pid in topology[:, 2:4].flatten() if pid != 0})

        # MapGIS polygon IDs are 1-based; the attribute table rows are 0-based.
        self.data = self.data.iloc[[pid - 1 for pid in active_ids if 1 <= pid <= len(self.data)]]

        geoms = [builder.build(pid) for pid in active_ids]
        if self._make_valid:
            geoms = [shapely.make_valid(g) if not g.is_valid else g for g in geoms]
        return geoms

    def _build_geodataframe(self) -> None:
        """Assemble the final GeoDataFrame and bounding box."""
        self.geodataframe = gpd.GeoDataFrame(self.data, crs=self.crs, geometry=self.geom)
        if self.geom:
            bounds = self.geodataframe.bounds
            self.bbox = np.array([
                bounds.minx.min(),
                bounds.miny.min(),
                bounds.maxx.max(),
                bounds.maxy.max(),
            ])
        else:
            self.bbox = np.array([0.0, 0.0, 0.0, 0.0])

    def to_file(self, filepath: Any, **kwargs: Any) -> None:
        """Write the GeoDataFrame to a file.

        Any keyword arguments are forwarded to ``geopandas.GeoDataFrame.to_file``.
        """
        self.geodataframe.to_file(filepath, **kwargs)

    def __len__(self) -> int:
        return len(self.geom)

    def __str__(self) -> str:
        n = len(self)
        plural = "s" if n != 1 else ""
        return f"mapgis file Reader\n{n} feature{plural} (type {self.shapeType})"

    def __repr__(self) -> str:
        return f"Reader({self._filepath!r}, make_valid={self._make_valid!r})"

    def __enter__(self) -> "Reader":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass
