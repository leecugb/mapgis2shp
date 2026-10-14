"""
pymapgis.writer
Provides writing support for MapGIS *.wt, *.wl, *.wp geospatial vector files.

Encodes a :class:`geopandas.GeoDataFrame` back into the MapGIS 6x binary
layout, mirroring :mod:`pymapgis.reader` so that ``Reader`` can re-read the
output losslessly (round-trip).

Known degradation: text annotations stored in auxiliary sections of native
.wt files are not produced, so written .wt files carry no label text in
MapGIS (symbol points are unaffected).  Auxiliary sections whose content is
not reverse-engineered are written as empty entries, which ``Reader``
tolerates.

Compatible with Python 3.9+.
"""

from __future__ import annotations

import datetime
import os
import struct
import warnings
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
import pyproj
import shapely
import shapely.geometry
from shapely.geometry.polygon import orient

from pymapgis.reader import (
    _ATTR_TYPE_BYTE,
    _ATTR_TYPE_DATE,
    _ATTR_TYPE_DOUBLE,
    _ATTR_TYPE_FLOAT,
    _ATTR_TYPE_INT,
    _ATTR_TYPE_SHORT,
    _ATTR_TYPE_STRING,
    _ATTR_TYPE_TIME,
    _CRS_CENTRAL_MERIDIAN_OFFSET,
    _CRS_ELLIPSOID_OFFSET,
    _CRS_PROJECTION_OFFSET,
    _CRS_SCALE_OFFSET,
    _CRS_STD_LAT_OFFSET,
    _ELLIPSOID_PROJ4,
    _LINE_PARAM_COLUMNS,
    _MAGIC_LINE,
    _MAGIC_POINT,
    _MAGIC_POLYGON,
    _POINT_PARAM_COLUMNS,
    _POLYGON_PARAM_COLUMNS,
    _STRUCT_FORMATS,
    POINT_TYPE_SYMBOL,
    MapGISError,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAGIC_FOR = {"POINT": _MAGIC_POINT, "LINE": _MAGIC_LINE, "POLYGON": _MAGIC_POLYGON}
_FILE_ID_FOR = {"POINT": 1, "LINE": 0, "POLYGON": 2}
_EXT_FOR = {"POINT": ".wt", "LINE": ".wl", "POLYGON": ".wp"}

# ``data_start`` is 657 in every native 6x file inspected; the section index
# area holds 16 entries (10 used + 6 zero-filled), so the first section begins
# at 657 + 160 = 817.
_DATA_START = 657
_HEADER_ENTRY_COUNT = 16
_HEADER_ENTRY_SIZE = 10
_HEADER_ENTRY_TAIL = b"\xff\xff"
_SECTION_BASE = _DATA_START + _HEADER_ENTRY_COUNT * _HEADER_ENTRY_SIZE

_POINT_RECORD_SIZE = 93
_LINE_RECORD_SIZE = 57
_TOPO_RECORD_SIZE = 24
_POLYGON_PARAM_RECORD_SIZE = 40

# Attribute-table constants.
_ATTR_PREFIX_SIZE = 322
_ATTR_PREFIX_SIGNATURE = b"`D"
_FIELD_DESCRIPTOR_WRITE_STRUCT = struct.Struct("<20sBihhih4x")
# name(20s) type(B) offset(i) storage(h) declared(h) flags(i) index(h) pad(4x)
assert _FIELD_DESCRIPTOR_WRITE_STRUCT.size == 39
_ATTR_FLAG_STRING = 256
_ATTR_FLAG_NUMERIC_BASE = 512

# File-header stamp bytes shared by every native 6x file inspected (unknown
# semantics; MapGIS may validate them).
_HEADER_STAMPS = {16: 16, 91: 1, 92: 4}
_HEADER_STAMP_BYTES = {99: 0x59, 100: 0x40, 107: 0x59, 108: 0x40}

# Type stamp stored at offset 12 of the 322-byte attribute-table prefix.
_ATTR_TYPE_STAMP = {"POINT": 621, "LINE": 1011, "POLYGON": 972}

# Native auxiliary-table descriptors, reproduced byte-for-byte from
# J43C001002 files (name/type/offset/storage/declared/flags/index).
_ARC_TABLE_DESCRIPTORS = (
    bytes.fromhex(
        "49440000000000000000000000000000000000000301000000"
        "04000800000100000000000000"
    ),  # ID: int32 @1, flags 0x100
    bytes.fromhex(
        "b3a4b6c8000000000000000000000000000000000505000000"
        "08000f0006020000010000000000"
    ),  # 长度: double @5, flags 518
)
_ARC_TABLE_STAMP = 426

# Per-point auxiliary constants (native values observed in J43C001002).
_POINT_FLAG_INT = 65539  # head5 4-byte record value
_WL_NODE_TABLE_PAD = b"\x00" * 16
_WL_PRMH_TAG = b"PRMH"
_WL_FLAG_BYTES = bytes([5, 0, 1, 0])  # head8 4-byte record value

# Graphic-parameter defaults (validated against native J43C001002 files).
_DEFAULT_POINT_TYPE = POINT_TYPE_SYMBOL
_DEFAULT_SYMBOL_NO = 1
_DEFAULT_POINT_SIZE = 1.0  # mm
_DEFAULT_LINETYPE = 1
_DEFAULT_AUX_LINETYPE = 0
_DEFAULT_LINE_COLOR = 1  # int16 @26 (Colorlib 1-based); 1 in all inspected native files
_DEFAULT_LINE_WIDTH = 0.1  # mm
_DEFAULT_LINE_COEF = 5.0  # x/y pattern coefficient used by this map series


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class WriterError(MapGISError):
    """Raised when a GeoDataFrame cannot be encoded as a MapGIS file."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _encode_gbk_field(text: str, max_bytes: int) -> bytes:
    """Encode *text* as GBK truncated to *max_bytes*, then NUL-pad.

    Truncation never splits a multibyte GBK character; unencodable
    characters are replaced with ``?``.
    """
    raw = text.encode("gbk", errors="replace")
    if len(raw) > max_bytes:
        out = raw[:max_bytes]
        while out:
            try:
                out.decode("gbk")
                break
            except UnicodeDecodeError:
                out = out[:-1]
        raw = out
    return raw + b"\x00" * (max_bytes - len(raw))


def _degrees_to_raw_dms(degrees: float) -> float:
    """Convert decimal degrees to the MapGIS ``DDDMMSS.sss`` double encoding.

    Exact arithmetic inverse of :func:`pymapgis.reader._raw_dms_to_degrees`.
    """
    sign = -1.0 if degrees < 0 else 1.0
    a = abs(degrees)
    d = int(a)
    r = (a - d) * 60.0
    m = int(r)
    s = (r - m) * 60.0
    return sign * (d * 10000.0 + m * 100.0 + s)


def _quantize(value: float, tolerance: float) -> float:
    """Snap *value* to a multiple of *tolerance* (0 = exact value)."""
    if tolerance <= 0:
        return value
    return round(value / tolerance) * tolerance


def _iter_shells(geom: Any) -> List[shapely.geometry.Polygon]:
    """Yield the polygonal parts of a Polygon/MultiPolygon/GeometryCollection."""
    if geom.is_empty:
        return []
    if isinstance(geom, shapely.geometry.Polygon):
        return [geom]
    if isinstance(geom, shapely.geometry.MultiPolygon):
        return list(geom.geoms)
    if isinstance(geom, shapely.geometry.GeometryCollection):
        parts = [g for g in geom.geoms if isinstance(g, shapely.geometry.Polygon)]
        if parts:
            warnings.warn("geometry collection reduced to its polygon parts")
        return parts
    return []


# ---------------------------------------------------------------------------
# Attribute table
# ---------------------------------------------------------------------------


@dataclass
class _FieldSpec:
    """Write-side descriptor for one attribute column."""

    name: str  # truncated/deduplicated GBK-safe field name
    type_code: int
    offset: int  # record offset (bytes; records start with a 0x01 flag byte)
    storage: int  # storage bytes (string: capacity + 1)
    declared: int  # declared length (descriptor bytes 27-28)
    decimals: int
    source: str  # original column name


def _is_missing(value: Any) -> bool:
    """Scalar missing-value check covering None / pd.NA / pd.NaT / NaN."""
    if value is None or value is pd.NA or value is pd.NaT:
        return True
    return isinstance(value, float) and bool(np.isnan(value))


def _series_max_gbk_bytes(series: pd.Series) -> int:
    longest = 0
    for value in series:
        if _is_missing(value):
            continue
        longest = max(longest, len(str(value).encode("gbk", errors="replace")))
    return longest


def _field_spec_for_column(series: pd.Series) -> Tuple[int, int, int, int]:
    """Map a pandas Series to (type_code, storage, declared, decimals)."""
    dtype = series.dtype
    if pd.api.types.is_bool_dtype(dtype) or (
        pd.api.types.is_integer_dtype(dtype) and dtype.itemsize == 1
    ):
        return _ATTR_TYPE_BYTE, 1, 3, 0
    if pd.api.types.is_integer_dtype(dtype):
        if dtype.itemsize == 2:
            return _ATTR_TYPE_SHORT, 2, 6, 0
        if dtype.itemsize <= 4:
            return _ATTR_TYPE_INT, 4, 8, 0
        # 64-bit integers: keep int32 when values fit, else degrade to double.
        non_null = series.dropna()
        if len(non_null) == 0 or (
            non_null.min() >= np.iinfo(np.int32).min
            and non_null.max() <= np.iinfo(np.int32).max
        ):
            return _ATTR_TYPE_INT, 4, 8, 0
        warnings.warn(
            f"column {series.name!r}: int64 values exceed int32 range; "
            "stored as double"
        )
        return _ATTR_TYPE_DOUBLE, 8, 15, 6
    if pd.api.types.is_float_dtype(dtype):
        if dtype.itemsize == 4:
            return _ATTR_TYPE_FLOAT, 4, 15, 6
        return _ATTR_TYPE_DOUBLE, 8, 15, 6
    if pd.api.types.is_datetime64_any_dtype(dtype):
        if (series.dt.hour.any() or series.dt.minute.any() or series.dt.second.any()):
            warnings.warn(
                f"column {series.name!r}: time-of-day truncated; stored as date"
            )
        return _ATTR_TYPE_DATE, 4, 8, 0
    if pd.api.types.is_object_dtype(dtype) or pd.api.types.is_string_dtype(dtype):
        non_null = series.dropna()
        if len(non_null) and all(
            isinstance(v, datetime.date) and not isinstance(v, datetime.datetime)
            for v in non_null
        ):
            return _ATTR_TYPE_DATE, 4, 8, 0
        if len(non_null) and all(isinstance(v, datetime.time) for v in non_null):
            return _ATTR_TYPE_TIME, 10, 8, 0
        bad = non_null.map(lambda v: isinstance(v, (list, tuple, dict, set, bytes)))
        if bad.any():
            raise WriterError(
                f"unsupported value type in column {series.name!r}; "
                "convert it to string/number/date first"
            )
        capacity = max(1, _series_max_gbk_bytes(series))
        return _ATTR_TYPE_STRING, capacity + 1, capacity, 0
    raise WriterError(
        f"unsupported dtype {dtype!r} for column {series.name!r}; "
        "convert it to string/number/date first"
    )


def _truncate_field_name(name: str) -> str:
    """Truncate a field name to 19 GBK bytes without splitting characters."""
    raw = name.encode("gbk", errors="replace")
    if len(raw) <= 19:
        return name
    out = raw[:19]
    while out:
        try:
            return out.decode("gbk")
        except UnicodeDecodeError:
            out = out[:-1]
    return ""


def _fields_from_dataframe(df: pd.DataFrame) -> List[_FieldSpec]:
    """Build field specs for a DataFrame, deduplicating truncated names."""
    specs: List[_FieldSpec] = []
    used: Dict[str, int] = {}
    offset = 1  # records start with a 0x01 flag byte
    for column in df.columns:
        base = _truncate_field_name(str(column))
        name = base
        if name in used:
            used[base] += 1
            while True:
                suffix = f"_{used[base]}"
                candidate = _truncate_field_name(base[: 19 - len(suffix)] + suffix)
                if candidate not in used:
                    name = candidate
                    break
                used[base] += 1
            warnings.warn(f"duplicate field name after truncation: {column!r} -> {name!r}")
        used[name] = used.get(name, 0)
        type_code, storage, declared, decimals = _field_spec_for_column(df[column])
        specs.append(
            _FieldSpec(name, type_code, offset, storage, declared, decimals, str(column))
        )
        offset += storage
    return specs


def _pack_attribute_field(value: Any, spec: _FieldSpec) -> bytes:
    """Pack a single attribute value (inverse of ``_decode_attribute_field``)."""
    missing = _is_missing(value)
    if spec.type_code == _ATTR_TYPE_STRING:
        return _encode_gbk_field("" if missing else str(value), spec.storage)
    if spec.type_code == _ATTR_TYPE_DATE:
        if missing:
            return b"\x00" * 4
        if isinstance(value, pd.Timestamp):
            value = value.date()
        if isinstance(value, datetime.datetime):
            value = value.date()
        return struct.pack("<hBB", value.year, value.month, value.day)
    if spec.type_code == _ATTR_TYPE_TIME:
        if missing:
            return b"\x00" * 10
        seconds = value.second + value.microsecond / 1_000_000.0
        return struct.pack("<BBd", value.hour, value.minute, seconds)
    fmt = _STRUCT_FORMATS.get(spec.type_code)
    if fmt is None:
        raise WriterError(f"unsupported attribute type code {spec.type_code}")
    if spec.type_code in (_ATTR_TYPE_FLOAT, _ATTR_TYPE_DOUBLE):
        number = float("nan") if missing else float(value)
    else:
        number = 0 if missing else int(value)
    return struct.pack(f"<{fmt}", number)


def _pack_field_descriptor(index: int, spec: _FieldSpec) -> bytes:
    """Pack one 39-byte field descriptor (validated against native files)."""
    flags = (
        _ATTR_FLAG_STRING
        if spec.type_code == _ATTR_TYPE_STRING
        else _ATTR_FLAG_NUMERIC_BASE + spec.decimals
    )
    return _FIELD_DESCRIPTOR_WRITE_STRUCT.pack(
        _encode_gbk_field(spec.name, 20),
        spec.type_code,
        spec.offset,
        spec.storage,
        spec.declared,
        flags,
        index,
    )


def _build_attribute_section(
    df: pd.DataFrame, specs: List[_FieldSpec], type_stamp: int
) -> bytes:
    """Build the complete attribute section (322-byte prefix + records)."""
    prefix = bytearray(_ATTR_PREFIX_SIZE)
    prefix[0:2] = _ATTR_PREFIX_SIGNATURE
    today = datetime.date.today()
    struct.pack_into("<hBB", prefix, 2, today.year, today.month, today.day)
    struct.pack_into("<i", prefix, 12, type_stamp)
    prefix[320:322] = _ATTR_PREFIX_SIGNATURE

    record_length = 1 + sum(spec.storage for spec in specs)
    head = struct.pack("<hih", len(specs), len(df) + 1, record_length) + b"\x00" * 18
    descriptors = b"".join(
        _pack_field_descriptor(i, spec) for i, spec in enumerate(specs)
    )

    empty_record = b"\x01" + b"\x00" * (record_length - 1)
    records = bytearray(empty_record)
    for _, row in df.iterrows():
        records += b"\x01"
        for spec in specs:
            records += _pack_attribute_field(row[spec.source], spec)

    return bytes(prefix) + head + descriptors + bytes(records)


# ---------------------------------------------------------------------------
# Coordinate reference system
# ---------------------------------------------------------------------------

_PROJ_CODE_FOR = {"tmerc": 5, "aea": 2, "lcc": 3}

# Lazily built inverse of ``_ELLIPSOID_PROJ4``:
# (a, 1/f, has_towgs84) -> ellipsoid code.
_ELLIPSOID_LOOKUP: Optional[List[Tuple[float, float, bool, int]]] = None


def _ellipsoid_lookup() -> List[Tuple[float, float, bool, int]]:
    global _ELLIPSOID_LOOKUP
    if _ELLIPSOID_LOOKUP is None:
        lookup = []
        for code, proj4 in _ELLIPSOID_PROJ4.items():
            if not isinstance(code, int):
                continue  # "cgcs2000" has no numeric MapGIS code
            try:
                ellps = pyproj.CRS(f"+proj=longlat {proj4} +no_defs").ellipsoid
            except pyproj.exceptions.CRSError:
                continue
            lookup.append(
                (
                    ellps.semi_major_metre,
                    ellps.inverse_flattening,
                    "+towgs84" in proj4,
                    code,
                )
            )
        _ELLIPSOID_LOOKUP = lookup
    return _ELLIPSOID_LOOKUP


def _ellipsoid_code_for(crs: pyproj.CRS) -> int:
    """Map a pyproj CRS to a MapGIS ellipsoid code (0 = unknown)."""
    ellps = crs.ellipsoid
    if ellps is None:
        return 0
    a = ellps.semi_major_metre
    rf = ellps.inverse_flattening
    has_towgs84 = "+towgs84" in crs.to_proj4()
    candidates = [
        (ref_towgs84, code)
        for ref_a, ref_rf, ref_towgs84, code in _ellipsoid_lookup()
        if abs(ref_a - a) < 0.01 and abs(ref_rf - rf) < 1e-4
    ]
    if candidates:
        # Codes may share one ellipsoid (e.g. 1 and 16 for Krassovsky);
        # prefer the entry whose datum transformation matches the input.
        for ref_towgs84, code in candidates:
            if ref_towgs84 == has_towgs84:
                return code
        return candidates[0][1]
    # GRS80 (CGCS2000) has no MapGIS code; it is within 0.1 mm of WGS84.
    if abs(a - 6378137.0) < 0.01 and abs(rf - 298.257222101) < 1e-3:
        warnings.warn("CGCS2000/GRS80 has no MapGIS ellipsoid code; writing WGS84 (7)")
        return 7
    warnings.warn(f"no MapGIS ellipsoid code matches (a={a}, 1/f={rf}); writing 0")
    return 0


def _proj4_params(crs: pyproj.CRS) -> Dict[str, float]:
    """Extract numeric proj4 parameters of a CRS keyed by parameter name."""
    params: Dict[str, float] = {}
    for part in crs.to_proj4().split():
        if not part.startswith("+"):
            continue
        key, _, value = part[1:].partition("=")
        if not value:
            params[key] = 1.0
            continue
        try:
            params[key] = float(value)
        except ValueError:
            continue
    return params


def _crs_header_fields(crs: Any, map_scale: float) -> Dict[int, Tuple[str, Any]]:
    """Compute CRS header fields as {byte_offset: (struct_fmt, value)}."""
    if crs is None or crs == "":
        return {
            _CRS_PROJECTION_OFFSET: ("B", 0),
            _CRS_ELLIPSOID_OFFSET: ("B", 0),
            _CRS_SCALE_OFFSET: ("d", 1.0),
        }
    crs = pyproj.CRS(crs)
    fields: Dict[int, Tuple[str, Any]] = {
        _CRS_ELLIPSOID_OFFSET: ("B", _ellipsoid_code_for(crs)),
    }
    if crs.is_geographic:
        fields[_CRS_PROJECTION_OFFSET] = ("B", 0)
        fields[_CRS_SCALE_OFFSET] = ("d", 1.0)
        return fields

    params = _proj4_params(crs)
    proj = None
    for part in crs.to_proj4().split():
        if part.startswith("+proj="):
            proj = part.split("=", 1)[1]
            break
    code = _PROJ_CODE_FOR.get(proj or "")
    if code is None:
        raise WriterError(
            f"unsupported projection {proj!r}; MapGIS 6x files only carry "
            "longitude/latitude, Transverse Mercator (tmerc), Albers (aea) "
            "and Lambert (lcc)"
        )
    fields[_CRS_PROJECTION_OFFSET] = ("B", code)
    fields[_CRS_SCALE_OFFSET] = ("d", float(map_scale))
    if code == 5:
        if params.get("k", 1.0) != 1.0:
            warnings.warn("Transverse Mercator with k != 1 (e.g. UTM) will be "
                          "written as Gauss-Kruger (k=1)")
        if params.get("x_0", 500000.0) != 500000.0 or params.get("lat_0", 0.0) != 0.0:
            warnings.warn("tmerc with non-standard lat_0/x_0; MapGIS assumes "
                          "lat_0=0 and x_0=500000")
    fields[_CRS_CENTRAL_MERIDIAN_OFFSET] = (
        "d",
        _degrees_to_raw_dms(params.get("lon_0", 0.0)),
    )
    if code in (2, 3):
        fields[_CRS_STD_LAT_OFFSET] = ("d", _degrees_to_raw_dms(params.get("lat_0", 0.0)))
        fields[_CRS_STD_LAT_OFFSET + 8] = ("d", _degrees_to_raw_dms(params.get("lat_1", 0.0)))
        fields[_CRS_STD_LAT_OFFSET + 16] = ("d", _degrees_to_raw_dms(params.get("lat_2", 0.0)))
        fields[_CRS_STD_LAT_OFFSET + 24] = ("d", params.get("x_0", 0.0))
        fields[_CRS_STD_LAT_OFFSET + 32] = ("d", params.get("y_0", 0.0))
    return fields


# ---------------------------------------------------------------------------
# File assembly
# ---------------------------------------------------------------------------


def _assemble_file(
    shape_type: str,
    crs_fields: Dict[int, Tuple[str, Any]],
    sections: Dict[int, bytes],
) -> bytes:
    """Assemble the complete binary file from header, index, and sections."""
    header = bytearray(_DATA_START)
    header[0:8] = _MAGIC_FOR[shape_type]
    struct.pack_into("<i", header, 8, _FILE_ID_FOR[shape_type])
    struct.pack_into("<i", header, 12, _DATA_START)
    # Native header stamps (constant across all inspected files).
    for offset, value in _HEADER_STAMPS.items():
        header[offset] = value
    for offset, value in _HEADER_STAMP_BYTES.items():
        header[offset] = value
    for offset, (fmt, value) in crs_fields.items():
        struct.pack_into(f"<{fmt}", header, offset, value)

    index = bytearray()
    body = bytearray()
    cursor = _SECTION_BASE
    for i in range(_HEADER_ENTRY_COUNT):
        payload = sections.get(i)
        if payload is None:
            index += struct.pack("<2i", 0, 0) + _HEADER_ENTRY_TAIL
            continue
        index += struct.pack("<2i", cursor, len(payload)) + _HEADER_ENTRY_TAIL
        body += payload
        cursor += len(payload)

    return bytes(header) + bytes(index) + bytes(body)


# ---------------------------------------------------------------------------
# Geometry encoders
# ---------------------------------------------------------------------------


def _encode_points(gdf: gpd.GeoDataFrame, params: Optional[pd.DataFrame], factor: float) -> bytes:
    """Encode the .wt point-record section (93 bytes per record, first empty)."""
    buf = bytearray(_POINT_RECORD_SIZE)
    for i, geom in enumerate(gdf.geometry):
        record = bytearray(_POINT_RECORD_SIZE)
        record[0] = 1
        struct.pack_into("<d", record, 7, float(geom.x) * factor)
        struct.pack_into("<d", record, 15, float(geom.y) * factor)

        row = params.iloc[i] if params is not None else None
        point_type = int(row["point_type"]) if row is not None else _DEFAULT_POINT_TYPE
        record[31] = point_type
        if point_type == POINT_TYPE_SYMBOL:
            symbol_no = int(row["symbol_no"]) if row is not None else _DEFAULT_SYMBOL_NO
            height = float(row["height"]) if row is not None else _DEFAULT_POINT_SIZE
            width = float(row["width"]) if row is not None else _DEFAULT_POINT_SIZE
            struct.pack_into("<h", record, 33, symbol_no)
            struct.pack_into("<f", record, 37, height)
            struct.pack_into("<f", record, 41, width)
        else:
            height = float(row["height"]) if row is not None else _DEFAULT_POINT_SIZE
            width = float(row["width"]) if row is not None else _DEFAULT_POINT_SIZE
            spacing = (
                0.0
                if row is None or not np.isfinite(row["spacing"])
                else float(row["spacing"])
            )
            struct.pack_into("<f", record, 33, height)
            struct.pack_into("<f", record, 37, width)
            struct.pack_into("<f", record, 41, spacing)
        angle = float(row["angle"]) if row is not None else 0.0
        struct.pack_into("<f", record, 45, angle)
        buf += record
    return bytes(buf)


def _encode_lines(
    gdf: gpd.GeoDataFrame, params: Optional[pd.DataFrame], factor: float
) -> Tuple[bytes, bytes]:
    """Encode the .wl line index and coordinate sections (first record empty)."""
    index = bytearray(_LINE_RECORD_SIZE)
    coords = bytearray(b"\x00\x00")
    for i, geom in enumerate(gdf.geometry):
        xy = np.asarray(geom.coords, dtype=np.float64) * factor
        offset = len(coords)
        for x, y in xy:
            coords += struct.pack("<2d", x, y)

        record = bytearray(_LINE_RECORD_SIZE)
        struct.pack_into("<i", record, 10, len(xy))
        struct.pack_into("<i", record, 14, offset)

        row = params.iloc[i] if params is not None else None
        linetype = int(row["linetype"]) if row is not None else _DEFAULT_LINETYPE
        aux = int(row["aux_linetype"]) if row is not None else _DEFAULT_AUX_LINETYPE
        color = _DEFAULT_LINE_COLOR
        if row is not None and "color" in row.index:
            color = int(row["color"])
        width = float(row["width"]) if row is not None else _DEFAULT_LINE_WIDTH
        x_coef = float(row["x_coef"]) if row is not None else _DEFAULT_LINE_COEF
        y_coef = float(row["y_coef"]) if row is not None else _DEFAULT_LINE_COEF
        struct.pack_into("<h", record, 22, linetype)
        struct.pack_into("<h", record, 24, aux)
        struct.pack_into("<h", record, 26, color)
        struct.pack_into("<f", record, 30, width)
        struct.pack_into("<f", record, 35, x_coef)
        struct.pack_into("<f", record, 39, y_coef)
        index += record
    return bytes(index), bytes(coords)


def _encode_point_aux(
    gdf: gpd.GeoDataFrame, params: Optional[pd.DataFrame]
) -> Tuple[bytes, bytes, bytes]:
    """Encode the native .wt auxiliary sections.

    head2 (index 1): GBK annotation text pool (written empty; symbol points
    carry no text).  head4 (index 3): per-point label box, 32 bytes = four
    doubles (xmin, ymin, xmax, ymax).  head5 (index 4): 4-byte flags per
    point (native value 65539).
    """
    n = len(gdf)
    pool = b"\x00" * 4
    boxes = bytearray(32)
    for i, geom in enumerate(gdf.geometry):
        row = params.iloc[i] if params is not None else None
        height = float(row["height"]) if row is not None else _DEFAULT_POINT_SIZE
        width = float(row["width"]) if row is not None else _DEFAULT_POINT_SIZE
        # Millimetres to degrees at the sheet's 1:250000 latitude (0.0013 deg/mm,
        # calibrated on native J43C001002 label boxes).
        hx = width * 0.0013
        hy = height * 0.0013
        boxes += struct.pack("<4d", geom.x - hx, geom.y - hy, geom.x + hx, geom.y + hy)
    flags = b"\x00" * 4 + struct.pack("<i", _POINT_FLAG_INT) * n
    return pool, bytes(boxes), flags


def _encode_line_aux(gdf: gpd.GeoDataFrame) -> Tuple[bytes, bytes, bytes]:
    """Encode the native .wl auxiliary sections.

    head4 (index 3): per-line node-id records, 24 bytes = two int32 (native
    assigns sequential fresh node IDs per line).  head7 (index 6): per-line
    32-byte records = "PRMH" tag + four-double bounding box.  head8 (index 7):
    4-byte flag records (native value 05 00 01 00).
    """
    nodes = bytearray(24)
    prmh = bytearray(32)
    flags = bytearray(4)
    for i, geom in enumerate(gdf.geometry):
        nodes += struct.pack("<2i", 2 * i + 1, 2 * i + 2) + _WL_NODE_TABLE_PAD
        minx, miny, maxx, maxy = geom.bounds
        prmh += _WL_PRMH_TAG + struct.pack("<4d", minx, miny, maxx, maxy)
        flags += _WL_FLAG_BYTES
    return bytes(nodes), bytes(prmh), bytes(flags)


def _encode_arc_table(arcs: List[List[Tuple[float, float]]]) -> bytes:
    """Encode the .wp arc attribute table (head3): ID + 长度 per arc.

    Layout mirrors the native table: 322-byte prefix (stamp 426), two field
    descriptors reproduced byte-for-byte, then 13-byte records (0x01 flag +
    int32 arc ID + double planar length in map units).
    """
    prefix = bytearray(_ATTR_PREFIX_SIZE)
    prefix[0:2] = _ATTR_PREFIX_SIGNATURE
    today = datetime.date.today()
    struct.pack_into("<hBB", prefix, 2, today.year, today.month, today.day)
    struct.pack_into("<i", prefix, 12, _ARC_TABLE_STAMP)
    prefix[320:322] = _ATTR_PREFIX_SIGNATURE

    record_length = 13
    head = (
        struct.pack("<hih", 2, len(arcs) + 1, record_length)
        + b"\x00" * 18
        + b"".join(_ARC_TABLE_DESCRIPTORS)
    )
    records = bytearray(b"\x01" + b"\x00" * (record_length - 1))
    for i, arc in enumerate(arcs):
        length = 0.0
        for (x1, y1), (x2, y2) in zip(arc, arc[1:]):
            length += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        records += b"\x01" + struct.pack("<id", i + 1, length)
    return bytes(prefix) + head + bytes(records)


class _PolygonArcDecomposer:
    """Split Polygon/MultiPolygon rings into shared arcs with left/right IDs.

    Rings are oriented (exterior CCW, holes CW) so the polygon interior is
    always on the left while walking.  Each canonical (unordered) segment is
    labelled with the polygon IDs found on its two sides; segments with an
    identical (left, right) signature are then greedily chained into arcs,
    breaking at junctions (vertices where more than one candidate segment
    continues).  Shared boundaries are stored once: the two polygons simply
    land on opposite sides of the same segments.
    """

    def __init__(self, polygons: List[Any], snap_tolerance: float = 0.0) -> None:
        self.polygons = polygons
        self.snap_tolerance = snap_tolerance

    def _rings(self) -> List[Tuple[int, List[Tuple[float, float]]]]:
        rings: List[Tuple[int, List[Tuple[float, float]]]] = []
        tol = self.snap_tolerance
        for pid, geom in enumerate(self.polygons, start=1):
            for shell in _iter_shells(geom):
                shell = orient(shell, sign=1.0)
                rings.append((pid, self._points(shell.exterior.coords, tol)))
                for interior in shell.interiors:
                    rings.append((pid, self._points(interior.coords, tol)))
        return rings

    @staticmethod
    def _points(coords: Any, tol: float) -> List[Tuple[float, float]]:
        pts = [(_quantize(float(c[0]), tol), _quantize(float(c[1]), tol)) for c in coords]
        # Drop consecutive duplicates (zero-length segments break chaining).
        out: List[Tuple[float, float]] = []
        for pt in pts:
            if not out or pt != out[-1]:
                out.append(pt)
        return out

    def build(self) -> Tuple[List[List[Tuple[float, float]]], List[Tuple[int, int]]]:
        sides: Dict[Tuple[Tuple[float, float], Tuple[float, float]], List[int]] = (
            defaultdict(lambda: [0, 0])
        )
        for pid, pts in self._rings():
            for a, b in zip(pts, pts[1:]):
                if a == b:
                    continue
                if a <= b:
                    sides[(a, b)][0] = pid
                else:
                    sides[(b, a)][1] = pid

        adjacency: Dict[Tuple[float, float], List[Any]] = defaultdict(list)
        for seg in sides:
            adjacency[seg[0]].append(seg)
            adjacency[seg[1]].append(seg)

        visited = set()
        arcs: List[List[Tuple[float, float]]] = []
        topo: List[Tuple[int, int]] = []
        for seg, (left, right) in sides.items():
            if seg in visited:
                continue
            visited.add(seg)
            signature = (left, right)
            chain: deque = deque(seg)
            for forward in (True, False):
                while True:
                    vertex = chain[-1] if forward else chain[0]
                    candidates = [
                        s
                        for s in adjacency[vertex]
                        if s not in visited and tuple(sides[s]) == signature
                    ]
                    if len(candidates) != 1:
                        break
                    nxt_seg = candidates[0]
                    visited.add(nxt_seg)
                    other = nxt_seg[1] if nxt_seg[0] == vertex else nxt_seg[0]
                    if forward:
                        chain.append(other)
                    else:
                        chain.appendleft(other)
            coords = list(chain)
            if len(coords) < 2:
                warnings.warn("degenerate arc discarded")
                continue
            # The chain always follows the canonical segment direction, so the
            # arc direction matches the (left, right) signature as stored.
            arcs.append(coords)
            topo.append((left, right))
        return arcs, topo


def _encode_polygon_params(params: Optional[pd.DataFrame], count: int) -> bytes:
    """Encode the head_9 polygon-parameter section (40 bytes, first record
    mirrors the native 0x04 marker).

    Colour/pattern fields are single bytes at @5/@6/@9 (layout pinned
    2026-10-14; the earlier int16 @4/@6/@8 write matched a reader
    misalignment, not the native layout).  Records carry no @7 flag, which
    native files hold per-layer (0/1/2/3/15) -- left zero here.
    """
    buf = bytearray(_POLYGON_PARAM_RECORD_SIZE)
    buf[0] = 0x04
    for i in range(count):
        record = bytearray(_POLYGON_PARAM_RECORD_SIZE)
        record[0] = 1
        if params is not None:
            row = params.iloc[i]
            record[5] = int(row["fill_color"]) & 0xFF
            record[6] = int(row["pattern"]) & 0xFF
            record[9] = int(row["pattern_color"]) & 0xFF
        buf += record
    return bytes(buf)


def _encode_polygons(
    gdf: gpd.GeoDataFrame,
    params: Optional[pd.DataFrame],
    factor: float,
    make_valid: bool,
    snap_tolerance: float,
) -> Tuple[bytes, bytes, bytes, bytes, bytes]:
    """Encode all .wp sections: arc index, coordinates, topology, arc table,
    head_9."""
    polygons = list(gdf.geometry)
    if make_valid:
        polygons = [
            shapely.make_valid(g) if not g.is_valid else g for g in polygons
        ]
    decomposer = _PolygonArcDecomposer(polygons, snap_tolerance)
    arcs, topo = decomposer.build()

    index = bytearray(_LINE_RECORD_SIZE)
    coords = bytearray(b"\x00\x00")
    for arc in arcs:
        offset = len(coords)
        for x, y in arc:
            coords += struct.pack("<2d", x * factor, y * factor)
        record = bytearray(_LINE_RECORD_SIZE)
        struct.pack_into("<i", record, 10, len(arc))
        struct.pack_into("<i", record, 14, offset)
        struct.pack_into("<h", record, 22, _DEFAULT_LINETYPE)
        struct.pack_into("<h", record, 26, _DEFAULT_LINE_COLOR)
        struct.pack_into("<f", record, 30, _DEFAULT_LINE_WIDTH)
        struct.pack_into("<f", record, 35, _DEFAULT_LINE_COEF)
        struct.pack_into("<f", record, 39, _DEFAULT_LINE_COEF)
        index += record

    topo_bytes = bytearray(_TOPO_RECORD_SIZE)
    for left, right in topo:
        topo_bytes += struct.pack("<4i", 0, 0, left, right) + b"\x00" * 8

    return (
        bytes(index),
        bytes(coords),
        bytes(topo_bytes),
        _encode_arc_table(arcs),
        _encode_polygon_params(params, len(gdf)),
    )


# ---------------------------------------------------------------------------
# Geometry normalisation
# ---------------------------------------------------------------------------


def _detect_shape_type(gdf: gpd.GeoDataFrame) -> str:
    types = {t for t in gdf.geom_type.unique() if t is not None}
    if not types:
        raise WriterError(
            "cannot detect the geometry type of an empty GeoDataFrame; "
            "pass geometry_type='POINT'|'LINE'|'POLYGON'"
        )
    if types <= {"Point", "MultiPoint"}:
        return "POINT"
    if types <= {"LineString", "MultiLineString", "LinearRing"}:
        return "LINE"
    if types <= {"Polygon", "MultiPolygon"}:
        return "POLYGON"
    raise WriterError(
        f"mixed geometry types {sorted(types)} are not supported; "
        "write one geometry type per MapGIS file"
    )


def _normalise_geometries(gdf: gpd.GeoDataFrame, shape_type: str) -> gpd.GeoDataFrame:
    """Force 2D, drop empty geometries, and explode Multi* where required."""
    out = gdf.copy()
    mask = out.geometry.is_empty | out.geometry.isna()
    if mask.any():
        warnings.warn(f"dropped {int(mask.sum())} empty/null geometries")
        out = out.loc[~mask].reset_index(drop=True)

    if out.geometry.has_z.any():
        warnings.warn("Z coordinates dropped (MapGIS 6x stores 2D geometry)")
        out = out.set_geometry(
            gpd.GeoSeries(shapely.force_2d(out.geometry.array), index=out.index, crs=out.crs)
        )

    if shape_type == "POINT" and (out.geom_type == "MultiPoint").any():
        warnings.warn("MultiPoint exploded into individual point records")
        out = out.explode(index_parts=False).reset_index(drop=True)
    elif shape_type == "LINE" and (out.geom_type == "MultiLineString").any():
        warnings.warn("MultiLineString exploded into individual line records")
        out = out.explode(index_parts=False).reset_index(drop=True)
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class Writer:
    """Encode a GeoDataFrame as a MapGIS .wt/.wl/.wp binary file.

    Parameters
    ----------
    geodataframe : geopandas.GeoDataFrame
        The features to write.  One geometry type per file: Point/MultiPoint
        for .wt, LineString/MultiLineString for .wl, Polygon/MultiPolygon for
        .wp.  MultiPoint and MultiLineString are exploded (with a warning);
        MultiPolygon stays a single polygon feature, matching the reader.
    make_valid : bool, default True
        Repair invalid polygons with ``shapely.make_valid`` before arc
        decomposition (.wp only).
    map_scale : float, default 1000.0
        Map-scale denominator used for projected CRS: coordinates are stored
        as ``value * 1000 / map_scale`` (the reader's inverse).  Ignored for
        longitude/latitude data.  Set to e.g. 250000 to reproduce a 1:250000
        sheet's native millimetre storage.
    snap_tolerance : float, default 0.0
        Coordinate quantisation step (map units) applied before topology
        construction so that shared boundaries coincide byte-exactly.  0
        disables snapping (suitable for data already noded, e.g. produced by
        ``Reader``).
    graphic_params : bool, default True
        When the GeoDataFrame carries the reader's graphic-parameter columns
        (``point_type``/``symbol_no``/..., ``linetype``/...,
        ``fill_color``/...), write them back into the graphic-parameter
        areas instead of the attribute table, giving mapgis -> shp -> mapgis
        parameter fidelity.  All columns of the group must be present for the
        group to be consumed.
    geometry_type : {"POINT", "LINE", "POLYGON"}, optional
        Explicit geometry type, required only for empty GeoDataFrames.

    Examples
    --------
    >>> Writer(gdf).to_file("out.wp")
    >>> write(gdf, "out.wl")
    """

    def __init__(
        self,
        geodataframe: gpd.GeoDataFrame,
        *,
        make_valid: bool = True,
        map_scale: float = 1000.0,
        snap_tolerance: float = 0.0,
        graphic_params: bool = True,
        geometry_type: Optional[str] = None,
    ) -> None:
        if not isinstance(geodataframe, gpd.GeoDataFrame):
            raise WriterError("Writer expects a geopandas.GeoDataFrame")
        self._make_valid = make_valid
        self._map_scale = float(map_scale)
        self._snap = float(snap_tolerance)
        self._graphic_params = graphic_params

        if geometry_type is not None:
            geometry_type = geometry_type.upper()
            if geometry_type not in _MAGIC_FOR:
                raise WriterError(f"unknown geometry_type {geometry_type!r}")
            self.shapeType: str = geometry_type
        else:
            self.shapeType = _detect_shape_type(geodataframe)

        self._gdf = _normalise_geometries(geodataframe, self.shapeType)
        self._params: Optional[pd.DataFrame] = None
        self._attr = self._split_param_columns(self._gdf)
        self._crs = self._gdf.crs

    # -- internal helpers ---------------------------------------------------

    def _split_param_columns(self, gdf: gpd.GeoDataFrame) -> pd.DataFrame:
        attr = gdf.drop(columns=[gdf.geometry.name])
        if not self._graphic_params:
            return attr
        want = {
            "POINT": _POINT_PARAM_COLUMNS,
            "LINE": _LINE_PARAM_COLUMNS,
            "POLYGON": _POLYGON_PARAM_COLUMNS,
        }[self.shapeType]
        if all(c in attr.columns for c in want):
            self._params = attr[want].reset_index(drop=True)
            return attr.drop(columns=want)
        return attr

    def _scale_factor(self) -> float:
        """Multiplier from map units to stored coordinate values."""
        crs = pyproj.CRS(self._crs) if self._crs not in (None, "") else None
        if crs is None or crs.is_geographic:
            return 1.0
        return 1000.0 / self._map_scale

    def _sections(self) -> Dict[int, bytes]:
        factor = self._scale_factor()
        specs = _fields_from_dataframe(self._attr)
        stamp = _ATTR_TYPE_STAMP[self.shapeType]
        attr_section = _build_attribute_section(self._attr, specs, stamp)

        if self.shapeType == "POINT":
            pool, boxes, flags = _encode_point_aux(self._gdf, self._params)
            return {
                0: _encode_points(self._gdf, self._params, factor),
                1: pool,
                2: attr_section,
                3: boxes,
                4: flags,
            }
        if self.shapeType == "LINE":
            index, coords = _encode_lines(self._gdf, self._params, factor)
            nodes, prmh, flags = _encode_line_aux(self._gdf)
            return {
                0: index,
                1: coords,
                2: attr_section,
                3: nodes,
                6: prmh,
                7: flags,
            }
        index, coords, topo, arc_table, params = _encode_polygons(
            self._gdf, self._params, factor, self._make_valid, self._snap
        )
        return {
            0: index,
            1: coords,
            2: arc_table,
            3: topo,
            8: params,
            9: attr_section,
        }

    # -- public -------------------------------------------------------------

    @property
    def crs(self) -> Any:
        return self._crs

    def to_file(self, filepath: Any) -> None:
        """Write the MapGIS file.  The extension must match the geometry type."""
        path = os.fspath(filepath)
        expected = _EXT_FOR[self.shapeType]
        ext = os.path.splitext(path)[1].lower()
        if ext != expected:
            raise WriterError(
                f"cannot write {self.shapeType} geometry to {path!r}: "
                f"geometry type {self.shapeType} requires a {expected} output file"
            )
        data = _assemble_file(
            self.shapeType, _crs_header_fields(self._crs, self._map_scale), self._sections()
        )
        with open(path, "wb") as file_obj:
            file_obj.write(data)

    def __len__(self) -> int:
        return len(self._gdf)

    def __repr__(self) -> str:
        return f"Writer({len(self)} features, type {self.shapeType})"


def write(geodataframe: gpd.GeoDataFrame, filepath: Any, **kwargs: Any) -> Writer:
    """Write *geodataframe* to a MapGIS file and return the :class:`Writer`."""
    writer = Writer(geodataframe, **kwargs)
    writer.to_file(filepath)
    return writer
