"""Unit tests for the strict ARC/INFO E00 example reader."""
from shapely.geometry import Polygon

from examples.e00_fast import _read_info, _ring_coordinates


def test_info_restores_fixed_width_80_column_records():
    fields = [
        ("ID", "4-1   14-1   5-1 50-1"),
        ("VALUE", "8-1   54-1  18 5 60-1"),
        ("TAG", "25-1  134-1  25-1 20-1"),
        ("DESCRIPTION", "100-1  384-1 100-1 20-1"),
        ("SMALL", "3-1  1384-1   3-1 30-1"),
    ]
    lines = ["IFO  2", "DEMO                             5   5 163         1"]
    for index, (name, definition) in enumerate(fields, start=1):
        lines.append(f"{name:16}{definition}  -1  -1-1{index:20}-")
    block = (
        f"{7:11d}{1.25:24.17E}{'ABC':25}{'crosses a physical line':100}{-2:3d}"
    )
    assert len(block) == 163
    lines.extend(block[offset:offset + 80].rstrip() for offset in range(0, 163, 80))
    lines.append("EOI")

    records = _read_info(lines, 0)["DEMO"]
    assert records == [{
        "ID": 7,
        "VALUE": 1.25,
        "TAG": "ABC",
        "DESCRIPTION": "crosses a physical line",
        "SMALL": -2,
    }]


def test_pal_rings_discard_only_non_boundary_dangling_arcs():
    arcs = {
        1: [(0, 0), (10, 0), (10, 10)],
        2: [(10, 10), (0, 10), (0, 0)],
        3: [(2, 2), (4, 2), (4, 4), (2, 2)],
        4: [(20, 20), (21, 21)],
    }
    rings = _ring_coordinates([1, 2, 3, 4], arcs)
    assert len(rings) == 2
    polygon = Polygon(rings[0], rings[1:])
    assert polygon.is_valid
    assert len(polygon.interiors) == 1
    assert polygon.area == 98
