"""Regression tests for geosciml4china-backed synthetic semantic data."""
import os
from pathlib import Path

import pytest
from lxml import etree

from examples.generate_semantic_geology import (
    build_semantics,
    emit_gml,
    enrich_layers,
)
from examples.generate_synthetic_geology import (
    generate_layers,
    read_layers,
    render_layers,
    write_layers,
)
from examples.render_bundled_jwd import summarise

NS = {"gsmlb": "http://www.opengis.net/gsml/4.1/GeoSciML-Basic"}


def test_semantic_records_and_gml(tmp_path):
    layers = enrich_layers(generate_layers(seed=42))
    units, contacts, faults, folds, attitudes = build_semantics(layers)
    assert len(units) == 10
    assert len(contacts) == 5
    assert len(faults) == 3
    assert len(folds) == 2
    assert len(attitudes) == 12
    assert [f.faulttype_term for f in faults] == [
        "reverse_fault", "dextral_strike_slip_fault", "fault",
    ]
    assert [f.profile_term for f in folds] == ["anticline", "syncline"]
    assert attitudes[1].overturned is True
    assert contacts[0].contacttype_term == "conformable_contact"
    assert contacts[2].contacttype_term == "angular_unconformable_contact"
    assert units["SIM-G"].event.eventprocess_term == "intrusion"
    assert units["SIM-M"].event.eventprocess_term == "metamorphic_process"

    result = emit_gml(layers, tmp_path / "synthetic.gml")
    assert result["members"] == 64
    root = etree.parse(str(tmp_path / "synthetic.gml")).getroot()
    assert root.get("{http://www.opengis.net/gml/3.2}id") == "sim.semantic"
    for tag, expected in [
        ("GeologicUnit", 10), ("Contact", 5),
        ("ShearDisplacementStructure", 3), ("Fold", 2), ("Foliation", 12),
        ("MappedFeature", 32),
    ]:
        assert len(root.findall(f".//gsmlb:{tag}", NS) ) == expected
    assert root.find(
        ".//gsmlb:eventProcess[@xlink:href='http://resource.geosciml.org/classifier/cgi/eventprocess/intrusion']",
        {"gsmlb": NS["gsmlb"], "xlink": "http://www.w3.org/1999/xlink"},
    ) is not None


def test_semantic_native_roundtrip_and_render(tmp_path, monkeypatch):
    slib = os.environ.get("PYMAPGIS_SLIB")
    if not slib and Path(r"D:\SLIB\SLIB").is_dir():
        slib = r"D:\SLIB\SLIB"
    if not slib:
        pytest.skip("Set PYMAPGIS_SLIB to the five official graphic libraries")
    monkeypatch.setenv("PYMAPGIS_SLIB", slib)
    layers = enrich_layers(generate_layers(seed=42))
    write_layers(layers, tmp_path / "vectors")
    native = read_layers(tmp_path / "vectors")
    assert native[6]["GZBD_eff"].tolist() == ["01", "02", "04", "24", "43"]
    assert native[7]["gzeeb_eff"].tolist() == ["05", "16", "01"]
    assert native[8]["GZCE"].tolist() == ["02", "03"]
    result = render_layers(native, tmp_path, dpi=60)
    summary = summarise(result.reports)
    assert summary["unknown_colour_occurrences"] == 0
    assert summary["unresolved_symbols"] == 0
    assert summary["empty_patterns"] == 0
    assert summary["cycle_limits"] == 0
