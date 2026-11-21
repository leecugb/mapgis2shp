#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Small, strict ARC/INFO E00 reader for the USGS conversion example.

GDAL's AVCE00 driver can spend an excessive amount of time assembling the
Conejo Well coverage.  This reader handles the uncompressed, double-precision
ARC, PAL, LAB and IFO sections used by that product.  It intentionally rejects
unsupported sections rather than silently approximating their contents.
"""
from __future__ import annotations

import math
import re
from functools import lru_cache
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon

_FIELD_RE = re.compile(
    r"\s*(\d+)-1\s+(\d+)-1\s+(\d+)(?:-1)?\s+"
    r"(?:(-?\d+)\s+)?(\d+)(?:-1)?"
)


def _display_width(output_width, value_type):
    if value_type == 20:  # character
        return output_width
    if value_type == 30:  # native integer
        return output_width
    if value_type == 50:  # four-byte binary integer, exported as I11
        return 11
    if value_type == 60:  # eight-byte binary real, exported as E24.17
        return 24
    raise ValueError(f"Unsupported E00 INFO value type: {value_type}")


def _number(text, value_type):
    value = text.strip()
    if not value:
        return None
    if value_type in (30, 50):
        return int(value)
    return float(value)


def _read_info(lines, start):
    """Read INFO tables, including fields split across 80-column lines."""
    tables = {}
    i = start + 1
    while i < len(lines) and lines[i] != "EOI":
        header = lines[i].split()
        if len(header) < 5:
            raise ValueError(f"Malformed E00 INFO header at line {i + 1}: {lines[i]!r}")
        name = header[0]
        field_count = int(header[-4])
        record_count = int(header[-1])
        i += 1
        fields = []
        for _ in range(field_count):
            line = lines[i]
            i += 1
            match = _FIELD_RE.match(line[16:])
            if match is None:
                raise ValueError(f"Malformed E00 INFO field at line {i}: {line!r}")
            size, _offset, output_width, _decimals, value_type = match.groups()
            fields.append((
                line[:16].strip(),
                int(output_width),
                int(value_type),
                _display_width(int(output_width), int(value_type)),
            ))
        record_width = sum(field[3] for field in fields)
        lines_per_record = math.ceil(record_width / 80)
        records = []
        for _ in range(record_count):
            # E00 removes trailing blanks on each physical line.  Restore the
            # full 80-column records before slicing fixed-width field values.
            block = "".join(
                line.ljust(80) for line in lines[i:i + lines_per_record]
            )[:record_width].ljust(record_width)
            i += lines_per_record
            record = {}
            offset = 0
            for field_name, _output_width, value_type, width in fields:
                text = block[offset:offset + width]
                offset += width
                record[field_name] = (
                    text.strip() if value_type == 20
                    else _number(text, value_type)
                )
            records.append(record)
        tables[name] = records
    return tables


def _read_arcs(lines, start):
    arcs = {}
    records = []
    i = start + 1
    while True:
        values = lines[i].split()
        i += 1
        if len(values) == 7 and int(values[0]) == -1:
            break
        if len(values) != 7:
            raise ValueError(f"Malformed E00 ARC header at line {i}: {values!r}")
        arc_id, user_id, fnode, tnode, lpoly, rpoly, count = map(int, values)
        coordinates = []
        for line in lines[i:i + count]:
            x, y = line.split()
            coordinates.append((float(x), float(y)))
        i += count
        arcs[arc_id] = coordinates
        records.append({
            "CoverageId": arc_id,
            "UserId": user_id,
            "FNODE_": fnode,
            "TNODE_": tnode,
            "LPOLY_": lpoly,
            "RPOLY_": rpoly,
            "geometry": LineString(coordinates),
        })
    return arcs, records


def _read_lab(lines, start):
    records = []
    i = start + 1
    while True:
        line = lines[i]
        i += 1
        value_id = int(line[:10])
        if value_id == -1:
            break
        records.append({
            "ValueId": value_id,
            "PolyId": int(line[10:20]),
            "geometry": Point(float(line[20:41]), float(line[41:62])),
        })
        i += 2  # The two label bounding-box lines do not alter the point.
    return records


def _ring_coordinates(arc_ids, arcs):
    """Assemble the single exterior and optional holes of one PAL polygon."""
    rings = []
    current = []
    first = None
    end = None

    def close(a, b):
        return math.isclose(a[0], b[0], abs_tol=0.02) and math.isclose(
            a[1], b[1], abs_tol=0.02
        )

    for arc_id in arc_ids:
        coordinates = arcs[abs(arc_id)]
        if arc_id < 0:
            coordinates = coordinates[::-1]
        if current and (close(end, first) or not close(end, coordinates[0])):
            rings.append(current)
            current = []
        if not current:
            first = coordinates[0]
            current = list(coordinates)
        else:
            current.extend(coordinates[1:])
        end = coordinates[-1]
    if current:
        rings.append(current)
    # Some PAL records terminate with dangling arcs used by the original
    # coverage topology.  They are not polygon boundaries; only closed,
    # non-degenerate rings participate in the OGIS polygon.
    rings = [
        ring for ring in rings
        if len(ring) >= 3 and close(ring[0], ring[-1]) and Polygon(ring).area > 0
    ]
    if not rings:
        raise ValueError(f"PAL polygon has no closed ring: {arc_ids!r}")
    return rings


def _read_pal(lines, start, arcs):
    records = []
    i = start + 1
    while True:
        count = int(lines[i][:10])
        i += 1
        if count == -1:
            break
        i += 1  # Maximum bounds; minimum bounds were on the header line.
        arc_ids = []
        for line in lines[i:i + math.ceil(count / 2)]:
            values = [int(value) for value in line.split()]
            if len(values) % 3:
                raise ValueError(f"Malformed E00 PAL arc entry at line {i}: {line!r}")
            arc_ids.extend(value for value in values[0::3] if value)
        i += math.ceil(count / 2)
        rings = _ring_coordinates(arc_ids, arcs)
        records.append({
            "ArcIds": arc_ids,
            "geometry": Polygon(rings[0], rings[1:]),
        })
    return records


def _merge_geometry_and_attributes(records, attributes, prefix, geometry_id=None):
    if len(records) != len(attributes):
        raise ValueError(
            f"E00 geometry/attribute count mismatch for {prefix}: "
            f"{len(records)} != {len(attributes)}"
        )
    key = f"{prefix}#"
    for index, (record, attribute) in enumerate(zip(records, attributes), start=1):
        if key in attribute and geometry_id is not None:
            expected = record[geometry_id]
            if attribute[key] != expected:
                raise ValueError(
                    f"E00 {prefix} key mismatch at record {index}: "
                    f"{attribute[key]} != {expected}"
                )
        record.update(attribute)


def read_info_tables(filename):
    """Read a standalone INFO/relate E00 such as ``lines.rel.e00``."""
    path = Path(filename).resolve()
    lines = path.read_text(encoding="ascii").splitlines()
    start = next(
        (index for index, line in enumerate(lines) if re.match(r"^IFO  +[23]$", line)),
        None,
    )
    if start is None:
        raise ValueError(f"E00 file has no INFO section: {path}")
    return _read_info(lines, start)


@lru_cache(maxsize=8)
def read_coverage(filename):
    """Return ARC/PAL/LAB records with their original INFO attributes."""
    path = Path(filename).resolve()
    lines = path.read_text(encoding="ascii").splitlines()
    sections = {
        line.split()[0]: index
        for index, line in enumerate(lines)
        if re.match(r"^(ARC|PAL|LAB|IFO)  +[23]$", line)
    }
    tables = _read_info(lines, sections["IFO"]) if "IFO" in sections else {}
    prefix = path.stem.upper()
    result = {}
    if "ARC" in sections:
        arcs, records = _read_arcs(lines, sections["ARC"])
        _merge_geometry_and_attributes(
            records, tables[f"{prefix}.AAT"], prefix, "CoverageId"
        )
        result["ARC"] = records
    else:
        arcs = {}
    if "PAL" in sections:
        records = _read_pal(lines, sections["PAL"], arcs)
        _merge_geometry_and_attributes(records, tables[f"{prefix}.PAT"], prefix)
        # ARC/INFO's universe polygon is not a mapped geologic unit.
        result["PAL"] = records[1:]
    if "LAB" in sections:
        records = _read_lab(lines, sections["LAB"])
        attributes = tables[f"{prefix}.PAT"]
        if "PAL" in result:
            attributes = attributes[1:]
        _merge_geometry_and_attributes(records, attributes, prefix)
        result["LAB"] = records
    return result
