# SPDX-License-Identifier: Apache-2.0
"""
pymapgis.writer
Provides writing support for MapGIS *.wt, *.wl, *.wp geospatial vector files.

Encodes a :class:`geopandas.GeoDataFrame` back into the MapGIS 6x binary
layout, mirroring :mod:`pymapgis.reader` so that ``Reader`` can re-read the
output losslessly (round-trip).

Known degradation: text annotations stored in auxiliary sections of native
.wt files are not produced, so written .wt files carry no label text in
MapGIS (symbol points are unaffected).  The .wl auxiliary sections (node
table, 55-byte block, 392-byte metadata block, bounding-box table, per-line
flags) follow the native J43C001002 layout pinned 2026-10-17.

Compatible with Python 3.9+.
"""

from __future__ import annotations

import datetime
import os
import struct
import time
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

# Per-point auxiliary constants (native values observed in J43C001002).
_POINT_FLAG_INT = 65539  # head5 4-byte record value
_WL_NODE_TABLE_PAD = b"\x00" * 16

# Graphic-parameter defaults (validated against native J43C001002 files).
_DEFAULT_POINT_TYPE = POINT_TYPE_SYMBOL
_DEFAULT_SYMBOL_NO = 1
_DEFAULT_POINT_SIZE = 1.0  # mm
_DEFAULT_LINETYPE = 1
_DEFAULT_AUX_LINETYPE = 0
_DEFAULT_LINE_COLOR = 1  # int16 @26 (Colorlib 1-based); 1 in all inspected native files
_DEFAULT_LINE_WIDTH = 0.1  # mm
_DEFAULT_LINE_COEF = 5.0  # x/y pattern coefficient (MapGIS 重存规范值)


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
    raw: Optional[bytes] = None  # verbatim 39-byte descriptor from a source file


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


def _fields_from_dataframe(
    df: pd.DataFrame, meta: Optional[dict] = None
) -> List[_FieldSpec]:
    """Build field specs for a DataFrame, deduplicating truncated names.

    When *meta* carries the original field metadata stashed by ``Reader``
    (``gdf.attrs["mapgis_field_meta"]``) and the columns match, the original
    declared widths and descriptor bytes are reused so a round-tripped file
    keeps its native record layout (2026-10-18 native-acceptance finding:
    MapGIS rejects attribute tables whose field widths were re-packed).
    Columns not present in the metadata are appended densely after the
    preserved block.
    """
    specs: List[_FieldSpec] = []
    used: Dict[str, int] = {}
    offset = 1  # records start with a 0x01 flag byte
    meta_fields = {f["name"]: f for f in (meta or {}).get("fields", [])}
    meta_raw = (meta or {}).get("raw_descriptors", {})
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
        orig = meta_fields.get(name)
        raw = meta_raw.get(name)
        if orig is not None and raw is not None:
            specs.append(
                _FieldSpec(
                    name=name,
                    type_code=int(orig["type_code"]),
                    offset=int(orig["offset"]),
                    storage=int(orig["length"]),
                    declared=struct.unpack_from("<h", raw, 27)[0],
                    decimals=int(orig.get("decimals", 0)),
                    source=str(column),
                    raw=bytes(raw),
                )
            )
            offset = max(offset, int(orig["offset"]) + int(orig["length"]))
            continue
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
    """Pack one 39-byte field descriptor (validated against native files).

    Round-tripped specs carry the verbatim source descriptor (``spec.raw``)
    and are reproduced byte-for-byte.
    """
    if spec.raw is not None:
        return spec.raw
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
    df: pd.DataFrame,
    specs: List[_FieldSpec],
    type_stamp: int,
    record_length: Optional[int] = None,
) -> bytes:
    """Build the complete attribute section (322-byte prefix + records).

    Records are assembled at each spec's record offset so round-tripped
    files keep the native (possibly sparse) field layout; *record_length*
    defaults to the dense packing length.
    """
    prefix = bytearray(_ATTR_PREFIX_SIZE)
    prefix[0:2] = _ATTR_PREFIX_SIGNATURE
    today = datetime.date.today()
    struct.pack_into("<hBB", prefix, 2, today.year, today.month, today.day)
    struct.pack_into("<i", prefix, 12, type_stamp)
    prefix[320:322] = _ATTR_PREFIX_SIGNATURE

    if record_length is None:
        record_length = 1 + sum(spec.storage for spec in specs)
    head = struct.pack("<hih", len(specs), len(df) + 1, record_length) + b"\x00" * 18
    descriptors = b"".join(
        _pack_field_descriptor(i, spec) for i, spec in enumerate(specs)
    )

    records = bytearray(b"\x01" + b"\x00" * (record_length - 1))
    for _, row in df.iterrows():
        rec = bytearray(record_length)
        rec[0] = 0x01
        for spec in specs:
            packed = _pack_attribute_field(row[spec.source], spec)
            end = min(spec.offset + len(packed), record_length)
            rec[spec.offset:end] = packed[: end - spec.offset]
        records += bytes(rec)

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


# Header CRS-block constants observed in every inspected native J43C001002
# file (2026-10-17, WT/WL/WP alike): small fixed stamps between the scale
# field and the millimetre-to-degree coefficients.  Reproduced verbatim.
_HEADER_CRS_BLOCK_BYTES = {
    132: 0x00,
    133: 0x59,
    134: 0x40,
    140: 0x00,
    141: 0x59,
    142: 0x40,
}
# float32 constants as little-endian byte patterns (~11.0014 / 11.0967 /
# 8.9073 / 9.7929), identical across inspected native files.
_HEADER_CRS_BLOCK_F32_BYTES = {
    163: bytes.fromhex("90053041"),
    171: bytes.fromhex("308c3141"),
    187: bytes.fromhex("80840e41"),
    195: bytes.fromhex("c0af1c41"),
}
_HEADER_CRS_NEG_ZERO_OFFSET = 220  # float32 -0.0 sentinel
_HEADER_CRS_UNIT_DOUBLE_OFFSET = 232  # double 1.0
_HEADER_CRS_BLOCK_U8 = {240: 0x04, 242: 0x01}
_HEADER_MM_DEG_X_OFFSET = 244  # double: degrees per millimetre, east-west
_HEADER_MM_DEG_Y_OFFSET = 252  # double: degrees per millimetre, north-south


def _mm_to_degree_coefs(crs: Any, map_scale: float, bbox) -> Tuple[float, float]:
    """Degrees per millimetre for a geographic file, native header convention.

    Native files store the map-scale ground distance of one millimetre
    expressed in degrees along the parallel (x) and meridian (y) at the data
    centre latitude.  MapGIS uses these coefficients to convert millimetre
    graphic sizes (symbol heights, line widths) into degree units for
    display; a zero coefficient collapses every millimetre-sized graphic to
    zero size.  Arc lengths are computed on the CRS ellipsoid (Krassovsky
    fallback, matching the native Beijing-54 convention).
    """
    import pyproj as _pyproj

    minx, miny, maxx, maxy = bbox
    lat = (miny + maxy) / 2.0
    try:
        ell = _pyproj.CRS(crs).ellipsoid
        geod = _pyproj.Geod(a=ell.semi_major_metre, b=ell.semi_minor_metre)
    except Exception:
        geod = _pyproj.Geod(ellps="krass")
    _, _, meridian_m = geod.inv(0.0, lat, 0.0, min(lat + 1.0, 89.99))
    _, _, parallel_m = geod.inv(0.0, lat, 1.0, lat)
    meridian_mm = max(meridian_m * 1000.0, 1.0)
    parallel_mm = max(parallel_m * 1000.0, 1.0)
    return map_scale / parallel_mm, map_scale / meridian_mm


def _header_crs_block_fields(
    crs: Any, map_scale: float, bbox
) -> Dict[int, Tuple[str, Any]]:
    """Fixed CRS-block stamps plus millimetre-to-degree coefficients.

    The constant block is written for every file type; the coefficients only
    make sense for geographic CRSes and are left at zero otherwise (the
    native projected layout is not yet pinned).
    """
    fields: Dict[int, Tuple[str, Any]] = {
        off: ("B", val) for off, val in _HEADER_CRS_BLOCK_BYTES.items()
    }
    for off, raw in _HEADER_CRS_BLOCK_F32_BYTES.items():
        fields.update({off + i: ("B", byte) for i, byte in enumerate(raw)})
    fields[_HEADER_CRS_NEG_ZERO_OFFSET] = ("f", -0.0)
    fields[_HEADER_CRS_UNIT_DOUBLE_OFFSET] = ("d", 1.0)
    fields.update({off: ("B", val) for off, val in _HEADER_CRS_BLOCK_U8.items()})
    if crs not in (None, "") and pyproj.CRS(crs).is_geographic:
        x_coef, y_coef = _mm_to_degree_coefs(crs, map_scale, bbox)
        fields[_HEADER_MM_DEG_X_OFFSET] = ("d", x_coef)
        fields[_HEADER_MM_DEG_Y_OFFSET] = ("d", y_coef)
    return fields


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
        # 2026-10-15 wat 明码补齐（reader.py 对称）：颜色@75/图层@83 两类点
        # 共用；@49 按 kind 分写——字符串点=中文字体 u8(+西文字体@51/字形@53)，
        # 子图点=笔宽 f32。
        color = int(row["color"]) if (row is not None and "color" in row.index) else 1
        layer = int(row["layer"]) if (row is not None and "layer" in row.index) else 0
        struct.pack_into("<B", record, 75, color & 0xFF)
        struct.pack_into("<B", record, 83, layer & 0xFF)
        if point_type == POINT_TYPE_SYMBOL:
            pen = (float(row["pen_width"])
                   if (row is not None and "pen_width" in row.index
                       and np.isfinite(row["pen_width"]))
                   else 0.05)
            struct.pack_into("<f", record, 49, pen)
        else:
            fzh = int(row["font_zh"]) if (row is not None and "font_zh" in row.index) else 1
            fen = int(row["font_en"]) if (row is not None and "font_en" in row.index) else 0
            fst = int(row["font_style"]) if (row is not None and "font_style" in row.index) else 0
            struct.pack_into("<B", record, 49, fzh & 0xFF)
            struct.pack_into("<B", record, 51, fen & 0xFF)
            struct.pack_into("<B", record, 53, fst & 0xFF)
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
        # 原生线记录头常量 01 02 00 00 00 00 00（2026-10-17 5 文件逐字节一致）
        record[0] = 1
        record[1] = 2
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
        # 2026-10-15 修复：aux 写 u8@24 + 标志字节 @25（原 int16 写两字节，
        # 会把 0 写进 @25 覆盖标志位；现按 reader 对称拆 u8 对）。
        aux_flag = int(row["aux_flag"]) if (row is not None and "aux_flag" in row.index) else 0
        struct.pack_into("<B", record, 24, aux & 0xFF)
        struct.pack_into("<B", record, 25, aux_flag & 0xFF)
        struct.pack_into("<h", record, 26, color)
        struct.pack_into("<f", record, 30, width)
        struct.pack_into("<f", record, 35, x_coef)
        struct.pack_into("<f", record, 39, y_coef)
        # 2026-10-15 明码补齐三字段（reader.py 对称，官方 wal 9 参数定位）：
        # @43 u16 辅助色（0=无）、@47 u8 图层、@48 u8 透明输出。
        aux_color = int(row["aux_color"]) if (row is not None and "aux_color" in row.index) else 0
        layer = int(row["layer"]) if (row is not None and "layer" in row.index) else 0
        transparent = (
            int(row["transparent"])
            if (row is not None and "transparent" in row.index)
            else 0
        )
        struct.pack_into("<h", record, 43, aux_color)
        struct.pack_into("<B", record, 47, layer & 0xFF)
        struct.pack_into("<B", record, 48, transparent & 0xFF)
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


# Native .wl auxiliary-section constants (2026-10-17, J43C001002 line files):
# head_5 (index 4) is a 55-byte block, zero-filled in every inspected file;
# head_6 (index 5) is a 392-byte metadata block (Windows FILETIME, the
# constant 387, the constant 1, and a zero-padded source-path area).
_LINE_AUX5_SIZE = 55
_LINE_META_SIZE = 392
_LINE_META_LENGTH_CONST = 387
_LINE_FLAG_BASE = 0x00010000
_POLY_META3_SIZE = 645  # 最小观测原生值（LHCPGDAC05.WP）
_POLY_META3_LEN_CONST = 426


def _filetime_now() -> int:
    """Current time as a Windows FILETIME (100 ns units since 1601-01-01)."""
    return int((time.time() + 11644473600.0) * 10_000_000)


def _encode_line_aux(
    gdf: gpd.GeoDataFrame, params: Optional[pd.DataFrame]
) -> Tuple[bytes, bytes, bytes, bytes, bytes]:
    """Encode the native .wl auxiliary sections.

    head4 (index 3): per-line node-id records, 24 bytes = two int32 (native
    assigns sequential fresh node IDs per line).  head5 (index 4): 55-byte
    zero block (native minimal form).  head6 (index 5): 392-byte metadata
    block (FILETIME + constants + empty path area).  head7 (index 6): n+1
    32-byte records of four-double bounding boxes (record 0 = file extent).
    head8 (index 7): 4-byte lead plus one int32 per line, 0x00010000 ORed
    with the line layer (layer 100 -> 0x64, layer 5 -> 0x05, native-verified).
    """
    nodes = bytearray(24)
    boxes = struct.pack("<4d", *gdf.total_bounds)
    flags = struct.pack("<i", _LINE_FLAG_BASE)
    for i, geom in enumerate(gdf.geometry):
        nodes += struct.pack("<2i", 2 * i + 1, 2 * i + 2) + _WL_NODE_TABLE_PAD
        minx, miny, maxx, maxy = geom.bounds
        boxes += struct.pack("<4d", minx, miny, maxx, maxy)
        row = params.iloc[i] if params is not None else None
        layer = int(row["layer"]) if (row is not None and "layer" in row.index) else 0
        flags += struct.pack("<i", _LINE_FLAG_BASE | (layer & 0xFF))

    meta = bytearray(_LINE_META_SIZE)
    struct.pack_into("<Q", meta, 0, _filetime_now())
    struct.pack_into("<I", meta, 12, _LINE_META_LENGTH_CONST)
    struct.pack_into("<I", meta, 16, 1)
    return (
        bytes(nodes),
        b"\x00" * _LINE_AUX5_SIZE,
        bytes(meta),
        bytes(boxes),
        bytes(flags),
    )


def _filetime_block(total_size: int, len_const: int, path_len: int) -> bytes:
    """Windows-FILETIME metadata block with native constants and zero padding.

    Used for the .wl head6 and the .wp head3/head6 metadata blocks observed in
    native J43C001002 files (2026-10-17): [FILETIME u64][u32 0][u32 len_const]
    [u32 path_len][zero-padded path area].
    """
    blk = bytearray(total_size)
    struct.pack_into("<Q", blk, 0, _filetime_now())
    struct.pack_into("<I", blk, 12, len_const)
    struct.pack_into("<I", blk, 16, path_len)
    return bytes(blk)


class _PolygonArcDecomposer:
    """Split Polygon/MultiPolygon rings into shared arcs with left/right IDs.

    Rings are oriented (exterior CCW, holes CW) so the polygon interior is
    always on the left while walking.  Each canonical (unordered) segment is
    labelled with the polygon IDs found on its two sides; segments whose
    unordered side-pair matches are greedily chained into arcs, breaking at
    junctions (vertices where more than one candidate segment continues).
    A ring with no shared boundary therefore stays ONE closed arc (native
    convention, 2026-10-17: splitting each ring at the canonical-direction
    flip leaves the file undisplayable in MapGIS).  Shared boundaries are
    stored once: the two polygons simply land on opposite sides of the same
    segments.

    Topology follows the reader convention: in the stored arc direction the
    right-id polygon's interior lies on the left of the walk, so each arc
    stores ``(left, right) = (pid_on_right_of_walk, pid_on_left_of_walk)``.
    Single-polygon arcs are normalised to the native ``(pid, 0)`` form (ring
    stored clockwise).
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
        ring_order: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        seen_seg: set = set()
        for pid, pts in self._rings():
            for a, b in zip(pts, pts[1:]):
                if a == b:
                    continue
                seg = (a, b) if a <= b else (b, a)
                if seg not in seen_seg:
                    seen_seg.add(seg)
                    ring_order.append(seg)
                if a <= b:
                    sides[seg][0] = pid
                else:
                    sides[seg][1] = pid

        adjacency: Dict[Tuple[float, float], List[Any]] = defaultdict(list)
        for seg in sides:
            adjacency[seg[0]].append(seg)
            adjacency[seg[1]].append(seg)

        visited = set()
        arcs: List[List[Tuple[float, float]]] = []
        topo: List[Tuple[int, int]] = []
        # 环比保序：按环顺序取段起链，保持源文件弧旋转/顶点序（2026-10-18
        # 原生显示实证：坐标环旋转是面显示闸门之一）
        for start_seg in ring_order:
            if start_seg in visited:
                continue
            visited.add(start_seg)
            left, right = sides[start_seg]
            key = frozenset((left, right))
            chain: deque = deque(start_seg)
            for forward in (True, False):
                while True:
                    vertex = chain[-1] if forward else chain[0]
                    candidates = [
                        s
                        for s in adjacency[vertex]
                        if s not in visited and frozenset(sides[s]) == key
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
            # 判定存储走向的左右多边形：取链中部一条段，与其规范方向比对
            i = max(0, (len(coords) - 1) // 2)
            p, q = coords[i], coords[i + 1]
            mid = (p, q) if p <= q else (q, p)
            side_l, side_r = sides[mid]
            if (p, q) == mid:
                walk_left, walk_right = side_l, side_r
            else:
                walk_left, walk_right = side_r, side_l
            # 单多边形弧归一化为原生 (pid, 0) 形态（多边形内域在行走右侧）
            if walk_left != 0 and walk_right == 0:
                coords = coords[::-1]
                walk_left, walk_right = walk_right, walk_left
            arcs.append(coords)
            topo.append((walk_right, walk_left))
        return arcs, topo


def _encode_polygon_params(params: Optional[pd.DataFrame], count: int) -> bytes:
    """Encode the head_9 polygon-parameter section (40 bytes, first record
    mirrors the native 0x04 marker).

    Colour/pattern fields are single bytes at @5/@6 and a uint16 LE at @9
    (layout pinned 2026-10-14, pattern_color widened to u16 2026-10-15 on
    the official .wap export evidence -- see reader._read_polygon_params).
    Byte @1 is the per-polygon class code (native values 2/9/10 observed;
    zero leaves the fill undisplayable -- 2026-10-17 native-acceptance
    finding), taken from the optional ``layer`` column with default 1.
    """
    buf = bytearray(_POLYGON_PARAM_RECORD_SIZE)
    buf[0] = 0x04
    # 原生数据记录的子参数块 @12-23（2026-10-17 原生 J43C001002 实证；
    # 内容含义未解码，写零会让区填充不可显示）
    _NATIVE_PARAM_SUBBLOCK = bytes.fromhex("001b010000c0400000c04001")
    for i in range(count):
        record = bytearray(_POLYGON_PARAM_RECORD_SIZE)
        record[0] = 1
        record[1] = 1
        record[12:24] = _NATIVE_PARAM_SUBBLOCK
        if params is not None:
            row = params.iloc[i]
            if "class" in row.index:
                record[1] = int(row["class"]) & 0xFF
            elif "layer" in row.index:
                record[1] = int(row["layer"]) & 0xFF
            record[5] = int(row["fill_color"]) & 0xFF
            record[6] = int(row["pattern"]) & 0xFF
            struct.pack_into("<H", record, 9, int(row["pattern_color"]) & 0xFFFF)
        buf += record
    return bytes(buf)


def _encode_polygons(
    gdf: gpd.GeoDataFrame,
    params: Optional[pd.DataFrame],
    factor: float,
    make_valid: bool,
    snap_tolerance: float,
) -> Tuple[
    bytes,
    bytes,
    bytes,
    bytes,
    List[List[Tuple[float, float]]],
    List[int],
    List[Tuple[int, int]],
]:
    """Encode the .wp core sections: arc index, coordinates, topology, head_9.

    Also returns the decomposed arcs (unscaled) and their per-arc layers for
    the auxiliary sections.
    """
    polygons = list(gdf.geometry)
    if make_valid:
        polygons = [
            shapely.make_valid(g) if not g.is_valid else g for g in polygons
        ]
    decomposer = _PolygonArcDecomposer(polygons, snap_tolerance)
    arcs, topo = decomposer.build()

    # 结点注册（弧段端点去重，1 起编号）。原生 head_2 前导表 =
    # [u16 0] + 每结点 (0, 结点号)，topo 记录前两字段 = 弧的起止结点号
    # （2026-10-17 原生 J43C001002 面文件定案：LDZOFBB010 26 弧 52 结点
    # → 前导 210 字节，arc1 偏移 210 实测吻合）。
    node_ids: Dict[Tuple[float, float], int] = {}
    node_list: List[Tuple[float, float]] = []

    def node_id(pt: Tuple[float, float]) -> int:
        key = (round(float(pt[0]), 12), round(float(pt[1]), 12))
        if key not in node_ids:
            node_ids[key] = len(node_list) + 1
            node_list.append(key)
        return node_ids[key]

    for arc in arcs:
        node_id(arc[0])
        node_id(arc[-1])

    lead = struct.pack("<H", 0)
    for nid in range(1, len(node_list) + 1):
        # 原生表项 = (0, 结点号)（MapGIS 重存版逐字节实证 2026-10-18；
        # 新建文件 lee.wp 则整表缺省、坐标紧随 u16 前导）
        lead += struct.pack("<2H", 0, nid)

    # 弧段所在图层 = 其区要素的类码图层（原生实证：区类码 2 → 弧记录
    # 图层@47=2、head_8 标志=0x10002；默认 1）
    # MapGIS 保存时把弧图层规范为 0（重存版逐字节实证 2026-10-18）
    polygon_layers: List[int] = [0] * len(polygons)
    if params is not None:
        layer_col = "class" if "class" in params.columns else (
            "layer" if "layer" in params.columns else None
        )
        if layer_col is not None:
            polygon_layers = [0 for _ in params[layer_col]]

    index = bytearray(_LINE_RECORD_SIZE)
    coords = bytearray(lead)
    topo_rows: List[Tuple[int, int, int, int]] = []
    arc_layers: List[int] = []
    for i, (arc, (left, right)) in enumerate(zip(arcs, topo)):
        sid = node_id(arc[0])
        eid = node_id(arc[-1])
        topo_rows.append((sid, eid, left, right))
        offset = len(coords)
        for x, y in arc:
            coords += struct.pack("<2d", x * factor, y * factor)
        owner = left if left != 0 else right
        layer = polygon_layers[owner - 1] if 1 <= owner <= len(polygon_layers) else 1
        arc_layers.append(layer)
        record = bytearray(_LINE_RECORD_SIZE)
        # 原生面弧段记录头常量 01 02（与线记录一致，2026-10-17 实证）
        record[0] = 1
        record[1] = 2
        struct.pack_into("<i", record, 10, len(arc))
        struct.pack_into("<i", record, 14, offset)
        struct.pack_into("<h", record, 22, _DEFAULT_LINETYPE)
        struct.pack_into("<h", record, 26, _DEFAULT_LINE_COLOR)
        struct.pack_into("<f", record, 30, _DEFAULT_LINE_WIDTH)
        struct.pack_into("<f", record, 35, _DEFAULT_LINE_COEF)
        struct.pack_into("<f", record, 39, _DEFAULT_LINE_COEF)
        record[47] = layer
        index += record

    topo_bytes = bytearray(_TOPO_RECORD_SIZE)
    for sid, eid, left, right in topo_rows:
        topo_bytes += struct.pack("<4i", sid, eid, left, right) + b"\x00" * 8

    return (
        bytes(index),
        bytes(coords),
        bytes(topo_bytes),
        _encode_polygon_params(params, len(gdf)),
        arcs,
        arc_layers,
        topo,
    )


def _encode_polygon_label_boxes(
    gdf: gpd.GeoDataFrame, factor: float
) -> bytes:
    """Encode the 11th-index label-box section (2026-10-18 native finding).

    Native polygon files carry a 16-entry index whose entry 11 points at a
    ``32 + 32 * n_polygons`` byte section: [u32 3086][28 zero bytes] followed
    by one ``(xmin, ymin, xmax, ymax)`` double quad per polygon (its label
    box / display anchor).  MapGIS's renderer requires this section; without
    it the regions parse but never draw.
    """
    out = struct.pack("<I", 3086) + b"\x00" * 28
    for geom in gdf.geometry:
        minx, miny, maxx, maxy = geom.bounds
        out += struct.pack(
            "<4d",
            minx * factor,
            miny * factor,
            maxx * factor,
            maxy * factor,
        )
    return out


def _encode_polygon_footer(gdf: gpd.GeoDataFrame) -> bytes:
    """Encode the 12th-index footer section (2026-10-18 native finding).

    entry[12] = [u32 lead (0 in fresh files)][one (u16 0, u16 1) record per
    polygon].  Sizes across natives: 4 + 4*n_polygons (lee 8B/1 poly,
    LDZOFBB010 20B/4, LDLYAAE002 516B/128, LDZOFBB001 2436B/608).
    """
    out = struct.pack("<I", 0)
    for _ in gdf.geometry:
        out += struct.pack("<2H", 0, 1)
    return out


def _encode_polygon_aux(
    arcs: List[List[Tuple[float, float]]],
    factor: float,
    layers: Optional[List[int]] = None,
) -> Tuple[bytes, bytes, bytes, bytes, bytes]:
    """Encode the .wp auxiliary sections (native layout, 2026-10-17).

    head3 (index 2): metadata block (FILETIME, constant 426, empty path area).
    head5 (index 4): 55-byte zero block.  head6 (index 5): 392-byte metadata
    block (FILETIME, constants 387/1).  head7 (index 6): arcs+1 32-byte
    records, record 0 zero-filled and record k the stored-unit bounding box
    of arc k.  head8 (index 7): 4-byte lead plus one int32 per arc,
    0x00010000 ORed with the arc layer (its polygon's class layer).
    """
    meta3 = _filetime_block(_POLY_META3_SIZE, _POLY_META3_LEN_CONST, 0)
    meta6 = _filetime_block(_LINE_META_SIZE, _LINE_META_LENGTH_CONST, 1)
    boxes = bytearray(32)
    for arc in arcs:
        xs = [p[0] * factor for p in arc]
        ys = [p[1] * factor for p in arc]
        boxes += struct.pack("<4d", min(xs), min(ys), max(xs), max(ys))
    if layers is None:
        layers = [0] * len(arcs)
    flags = struct.pack("<i", _LINE_FLAG_BASE) + struct.pack(
        f"<{len(arcs)}i",
        *[(_LINE_FLAG_BASE | (layer & 0xFF)) for layer in layers],
    )
    return bytes(meta3), b"\x00" * _LINE_AUX5_SIZE, meta6, bytes(boxes), bytes(flags)


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
        if self.shapeType == "POLYGON":
            self._attr = self._add_polygon_standard_fields(self._attr)
        self._crs = self._gdf.crs

    def _add_polygon_standard_fields(self, attr: pd.DataFrame) -> pd.DataFrame:
        """Append the native ID/面积/周长 standard fields for .wp tables.

        Native MapGIS polygon tables always start with ID (int32), followed
        by 面积 (area) and 周长 (perimeter) as computed double fields; the
        native display path expects them (2026-10-17 native-acceptance
        finding).  Missing fields are generated from the geometry or a
        sequential ID; user-supplied values are kept.
        """
        geom = self._gdf.geometry
        if "ID" not in attr.columns:
            attr = attr.copy()
            attr.insert(
                0, "ID", pd.array(range(1, len(attr) + 1), dtype="int32")
            )
        if "面积" not in attr.columns:
            attr = attr.copy()
            attr.insert(
                attr.columns.get_loc("ID") + 1,
                "面积",
                pd.array(geom.area, dtype="float64"),
            )
        if "周长" not in attr.columns:
            attr = attr.copy()
            attr.insert(
                attr.columns.get_loc("面积") + 1,
                "周长",
                pd.array(geom.length, dtype="float64"),
            )
        return attr

    # -- internal helpers ---------------------------------------------------

    def _split_param_columns(self, gdf: gpd.GeoDataFrame) -> pd.DataFrame:
        attr = gdf.drop(columns=[gdf.geometry.name])
        if not self._graphic_params:
            return attr
        if self.shapeType == "LINE" and "linetype" in attr.columns:
            # 宽松吸收（2026-10-15）：以 linetype 为图形参数主键——旧版
            # 全列齐备才吸收，列集扩充（aux_flag/aux_color/layer/
            # transparent）后旧 6 列 gdf 会被整体静默丢弃退回默认。
            # 现 reindex 补缺失列 + 按列默认值填充，部分给出的参数不再丢失。
            present = [c for c in _LINE_PARAM_COLUMNS if c in attr.columns]
            params = attr[present].reindex(columns=_LINE_PARAM_COLUMNS)
            self._params = params.fillna(
                {
                    "linetype": _DEFAULT_LINETYPE,
                    "aux_linetype": _DEFAULT_AUX_LINETYPE,
                    "aux_flag": 0,
                    "color": _DEFAULT_LINE_COLOR,
                    "width": _DEFAULT_LINE_WIDTH,
                    "x_coef": _DEFAULT_LINE_COEF,
                    "y_coef": _DEFAULT_LINE_COEF,
                    "aux_color": 0,
                    "layer": 0,
                    "transparent": 0,
                }
            )
            return attr.drop(columns=present)
        if self.shapeType == "POINT" and "point_type" in attr.columns:
            # 同 LINE 宽松吸收（2026-10-15 wat 补齐后列集 6→12）。
            present = [c for c in _POINT_PARAM_COLUMNS if c in attr.columns]
            params = attr[present].reindex(columns=_POINT_PARAM_COLUMNS)
            self._params = params.fillna(
                {
                    "point_type": _DEFAULT_POINT_TYPE,
                    "symbol_no": _DEFAULT_SYMBOL_NO,
                    "height": _DEFAULT_POINT_SIZE,
                    "width": _DEFAULT_POINT_SIZE,
                    "spacing": 0.0,
                    "angle": 0.0,
                    "color": 1,
                    "layer": 0,
                    "pen_width": 0.05,
                    "font_zh": 1,
                    "font_en": 0,
                    "font_style": 0,
                }
            )
            return attr.drop(columns=present)
        want = {
            "POINT": _POINT_PARAM_COLUMNS,
            "LINE": _LINE_PARAM_COLUMNS,
            "POLYGON": ["fill_color", "pattern", "pattern_color"],
        }[self.shapeType]
        if all(c in attr.columns for c in want):
            self._params = attr[want].reset_index(drop=True)
            attr = attr.drop(columns=want)
            # 区参数类码 @1（=区图层，须与弧记录/head_8 标志一致）：
            # 取可选 class 列（往返来源）或 layer 列，默认 1
            for key in ("class", "layer"):
                if self.shapeType == "POLYGON" and key in attr.columns:
                    self._params["class"] = attr[key].reset_index(drop=True)
                    attr = attr.drop(columns=key)
                    break
            return attr
        return attr

    def _scale_factor(self) -> float:
        """Multiplier from map units to stored coordinate values."""
        crs = pyproj.CRS(self._crs) if self._crs not in (None, "") else None
        if crs is None or crs.is_geographic:
            return 1.0
        return 1000.0 / self._map_scale

    def _sections(self) -> Dict[int, bytes]:
        factor = self._scale_factor()
        meta = getattr(self._gdf, "attrs", {}).get("mapgis_field_meta")
        specs = _fields_from_dataframe(self._attr, meta)
        stamp = _ATTR_TYPE_STAMP[self.shapeType]
        record_length = None
        if meta and all(
            any(s.source == f["name"] or s.name == f["name"] for s in specs)
            for f in meta.get("fields", [])
        ):
            record_length = int(meta.get("record_length") or 0) or None
        attr_section = _build_attribute_section(
            self._attr, specs, stamp, record_length=record_length
        )

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
            nodes, aux5, meta, boxes, flags = _encode_line_aux(
                self._gdf, self._params
            )
            return {
                0: index,
                1: coords,
                2: attr_section,
                3: nodes,
                4: aux5,
                5: meta,
                6: boxes,
                7: flags,
            }
        index, coords, topo_bytes, params, arcs, arc_layers, topo_pairs = _encode_polygons(
            self._gdf, self._params, factor, self._make_valid, self._snap
        )
        meta3, aux5, meta6, boxes, flags = _encode_polygon_aux(
            arcs, factor, arc_layers
        )
        passthrough = self._polygon_passthrough(arcs, topo_pairs, factor)
        if passthrough is not None:
            # 未修改几何的往返：原始弧段/元数据块/尾部逐字节复用
            # （2026-10-18 实证：MapGIS 按内部期望校验元数据块尺寸与弧段
            # 形态，自行重建无法复现；透传保证往返件与原生同构）
            secs = {int(k): bytes(v) for k, v in passthrough["sections"].items()}
            secs[8] = params
            secs[9] = attr_section
            if 10 not in secs:
                secs[10] = _encode_polygon_label_boxes(self._gdf, factor)
            if 12 not in secs:
                secs[12] = _encode_polygon_footer(self._gdf)
            result = {i: secs[i] for i in range(13) if i in secs}
            result["_tail"] = passthrough.get("tail", b"")
            return result
        return {
            0: index,
            1: coords,
            2: meta3,
            3: topo_bytes,
            4: aux5,
            5: meta6,
            6: boxes,
            7: flags,
            8: params,
            9: attr_section,
            10: _encode_polygon_label_boxes(self._gdf, factor),
            12: _encode_polygon_footer(self._gdf),
        }

    def _header_extent_fields(
        self, sections: Dict[int, bytes]
    ) -> Dict[int, Tuple[str, Any]]:
        """Header record-count and file-extent fields (native layout).

        Count sequence pinned 2026-10-18 on a MapGIS-6.7-created reference
        file (``lee.wp``): @260 record count (features for point/line, arcs
        for polygon), @264 count + 1, @272 the constant 1, @276/@280 the
        polygon feature count and count + 1 (zero elsewhere), @284 count + 1
        again, @292 the constant 1.  MapGIS's renderer consults this sequence,
        so missing entries leave written polygons undisplayable.  @304..328
        holds the four-double file bounding box in stored coordinate units
        (window reset and symbol scaling).
        """
        factor = self._scale_factor()
        minx, miny, maxx, maxy = self._gdf.total_bounds * factor
        features = len(self._gdf)
        if self.shapeType == "POLYGON":
            count = len(sections[0]) // _LINE_RECORD_SIZE - 1
            fields: Dict[int, Tuple[str, Any]] = {
                260: ("I", count),
                264: ("I", count + 1),
                268: ("I", 0),
                272: ("I", 1),
                276: ("I", features),
                280: ("I", features + 1),
                284: ("I", count + 1),
            }
        else:
            count = features
            fields = {
                260: ("I", count),
                264: ("I", count + 1),
                268: ("I", 0),
                272: ("I", 1),
                276: ("I", 0),
                280: ("I", 0),
                284: ("I", count + 1),
            }
        fields[292] = ("I", 1)
        # 类型标志字节（2026-10-18 原生实证：区=0x84，点=0x80，线=0）
        fields[336] = ("B", {"POINT": 0x80, "LINE": 0, "POLYGON": 0x84}[self.shapeType])
        fields.update(
            {
                304: ("d", float(minx)),
                312: ("d", float(miny)),
                320: ("d", float(maxx)),
                328: ("d", float(maxy)),
            }
        )
        return fields

    def _polygon_passthrough(
        self,
        arcs: List[List[Tuple[float, float]]],
        topo: List[Tuple[int, int]],
        factor: float,
    ) -> Optional[dict]:
        """Return the reader-stashed raw sections when the geometry is unchanged.

        Compares area/bbox fingerprints of the polygons rebuilt from our
        arcs against those from the source file's raw sections (the read-
        rebuild chain may nudge individual vertices via make_valid / endpoint
        matching, so vertex-exact comparison is too strict).  On a match the
        original arc/metadata/tail bytes are reused, keeping a round-tripped
        file byte-isomorphic to the native original.
        """
        pt = getattr(self._gdf, "attrs", {}).get("mapgis_section_passthrough")
        sections = (pt or {}).get("sections", {})
        if not pt or not all(k in sections for k in ("0", "1", "3")):
            return None
        try:
            import io as _io

            import shapely as _shp

            from pymapgis.reader import (
                _PolygonTopologyBuilder,
                _read_polygon_arcs,
                _read_topology_table,
            )

            raw_index = bytes(sections["0"])
            raw_coords = bytes(sections["1"])
            raw_topo = bytes(sections["3"])
            stream = _io.BytesIO(
                b"\x00" * 16 + raw_index + b"\x00" * 8 + raw_coords
            )
            src_arcs = _read_polygon_arcs(
                stream,
                16,
                len(raw_index),
                16 + len(raw_index) + 8,
                len(raw_coords),
                1.0,
            )
            src_topo = _read_topology_table(_io.BytesIO(raw_topo), 0, len(raw_topo))
        except Exception:
            return None

        def _fingerprint(arc_list, topo_pairs):
            import numpy as _np

            lines = [_shp.geometry.LineString(a) for a in arc_list]
            table = _np.array(
                [[0, 0, int(lf), int(rt)] for lf, rt in topo_pairs]
            )
            builder = _PolygonTopologyBuilder(lines, table)
            pids = sorted(
                {int(lf) for lf, _ in topo_pairs if lf}
                | {int(r) for _, r in topo_pairs if r}
            )
            out = []
            for pid in pids:
                g = builder.build(pid)
                out.append(
                    (round(float(g.area), 4), tuple(round(v, 4) for v in g.bounds))
                )
            return sorted(out)

        ours = _fingerprint(arcs, topo)
        theirs = _fingerprint(
            [list(a.coords) for a in src_arcs],
            [(int(t[2]), int(t[3])) for t in src_topo],
        )
        if not ours or ours != theirs:
            return None
        return pt

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
        sections = self._sections()
        tail = sections.pop("_tail", b"")
        header_fields = {
            **_crs_header_fields(self._crs, self._map_scale),
            **_header_crs_block_fields(
                self._crs, self._map_scale, self._gdf.total_bounds
            ),
            **self._header_extent_fields(sections),
        }
        data = _assemble_file(self.shapeType, header_fields, sections)
        if tail:
            data += bytes(tail)
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
