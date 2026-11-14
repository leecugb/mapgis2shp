#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate an independent synthetic geological map with GeoSciML semantics.

All features are synthetic. The semantic model is assembled through
geosciml4china's UnitRec/ContactRec/FaultRec/FoldRec/AttitudeRec and its official
GML emitters; it is not a reinterpretation of any measured JWD feature.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from geosciml4china.convert import config, mapping, model, validate  # noqa: E402
from geosciml4china.convert.emit import document, features  # noqa: E402
from lxml import etree  # noqa: E402

from examples.generate_synthetic_geology import (  # noqa: E402
    generate_layers,
    read_layers,
    render_layers,
    write_layers,
)
from examples.render_bundled_jwd import summarise  # noqa: E402


def enrich_layers(layers):
    """Attach geosciml4china semantic fields to independent synthetic layers."""
    layers = {name: layer.copy() for name, layer in layers.items()}
    layers["SIM_LDZOFBA002.WL"]["GZBD_eff"] = ["01", "02", "04", "24", "43"]
    layers["SIM_LDZOFBA002.WL"]["sem_label"] = [
        "整合接触", "实测地质界线", "角度不整合", "平行不整合", "岩性过渡渐变界线"
    ]
    layers["SIM_LDZOFBA002.WL"]["verdict"] = "仿真标定通过"
    layers["SIM_LDZOFBA003.WL"]["gzeeb_eff"] = ["05", "16", "01"]
    layers["SIM_LDZOFBA003.WL"]["structural_type"] = ["逆断层", "右型走滑断层", "断层"]
    layers["SIM_LDZOFBA003.WL"]["evidence_class"] = ["实测", "部分覆盖", "推测"]
    layers["SIM_LDZOFBA005.WL"]["GZCE"] = ["02", "03"]
    layers["SIM_LDZOFBA005.WL"]["fold_name"] = ["SIM-ANTICLINE", "SIM-SYNCLINE"]
    attitude_codes = [
        "202001", "202004", "202001", "202005", "202011", "202001",
        "202005", "202004", "202011", "202001", "202005", "202011",
    ]
    layers["SIM_LDZOFBA016.WT"]["GZBBGA"] = attitude_codes
    layers["SIM_LDZOFBA016.WT"]["host_norm"] = [f"SIM_{chr(65 + i % 6)}" for i in range(12)]
    return layers


def _unit(norm, role, era_name, rank, lithology=None):
    event = model.EventRec(
        eventprocess_term=mapping.eventprocess(role),
        eventprocess_label=mapping.eventprocess(role).replace("_", " "),
        older_era=era_name,
        younger_era=era_name,
    )
    era = validate_vocab_era(era_name)
    event.older_ma = era["older_Ma"]
    event.younger_ma = era["younger_Ma"]
    compositions = []
    if lithology:
        uri, label = _vocab_lithology(lithology)
        compositions.append(model.CompositionRec(
            lithology_term=lithology, lithology_label=label, lithology_uri=uri
        ))
    return model.UnitRec(
        norm=norm,
        name=norm.replace("_", "-"),
        layer_role=role,
        unittype_term=mapping.unit_type(role),
        rank_term=rank,
        description=f"Synthetic {role} unit ({norm})",
        event=event,
        compositions=compositions,
    )


def validate_vocab_era(name):
    from geosciml4china.convert import vocab

    era = vocab.era(name)
    if era is None:
        raise ValueError(f"Unsupported ICS era: {name}")
    return era


def _vocab_lithology(term):
    from geosciml4china.convert import vocab

    return vocab.lithology_uri(term)


def build_semantics(layers):
    """Build semantic records and their mapped-feature links."""
    units = {}
    specifications = {
        "SIM-A": _unit("SIM_A", "沉积岩建造", "Holocene", "formation", "shale"),
        "SIM-B": _unit("SIM_B", "沉积岩建造", "Pleistocene", "formation", "limestone"),
        "SIM-C": _unit("SIM_C", "沉积岩建造", "Cretaceous", "formation", "shale"),
        "SIM-D": _unit("SIM_D", "沉积岩建造", "Jurassic", "formation", "limestone"),
        "SIM-E": _unit("SIM_E", "沉积岩建造", "Triassic", "formation", "shale"),
        "SIM-F": _unit("SIM_F", "沉积岩建造", "Permian", "formation", "limestone"),
        "SIM-V": _unit("SIM_V", "火山岩性岩相", "Cretaceous", "formation", "basalt"),
        "SIM-G": _unit("SIM_G", "侵入岩", "Jurassic", "lithodeme", "granodiorite"),
        "SIM-M": _unit("SIM_M", "变质岩建造", "Proterozoic", "suite", "schist"),
        "SIM-WATER": _unit("SIM_WATER", "沉积岩建造", "Holocene", "formation"),
    }
    units = dict(specifications)
    unit_by_norm = {unit.norm: unit for unit in specifications.values()}
    ordered_norms = ["SIM-A", "SIM-B", "SIM-C", "SIM-D", "SIM-E", "SIM-F"]
    for younger, older in zip(ordered_norms[1:], ordered_norms[:-1]):
        code = younger.split("-")[1].lower()
        unit_by_norm[younger.replace("-", "_")].relations.append({
            "target_norm": older.replace("-", "_"),
            "term": "conformable_contact",
            "note": f"Synthetic conformable relation {younger} -> {older} ({code})",
        })
    for code, unit in specifications.items():
        units[code] = unit
    units["SIM-WATER"].relations = []

    contacts = []
    contact_types = ["conformable_contact", "depositional_contact",
                     "angular_unconformable_contact", "disconformable_contact",
                     "igneous_phase_contact"]
    for i, row in enumerate(layers["SIM_LDZOFBA002.WL"].itertuples(), start=1):
        contact = model.ContactRec(
            src_id=i,
            code=row.GZBD_eff,
            sem_label=row.sem_label,
            verdict=row.verdict,
            younger_side=ordered_norms[i] if i < len(ordered_norms) else None,
            geometry=row.geometry.__geo_interface__,
            decided=True,
            contacttype_term=contact_types[i - 1],
            contacttype_label=contact_types[i - 1].replace("_", " "),
            observation_term="outcrop_observation",
            observation_label="outcrop observation",
            ord=i,
        )
        contacts.append(contact)

    faults = []
    for i, row in enumerate(layers["SIM_LDZOFBA003.WL"].itertuples(), start=1):
        structural_type = row.structural_type
        faulttype = mapping.faulttype_by_semantics(structural_type)
        azimuth = [45.0, 70.0, 110.0][i - 1]
        movement = ["reverse", "dextral", "no_movement_sense"][i - 1]
        fault = model.FaultRec(
            feature_id=f"F{i:03d}",
            fault_id=f"F{i:03d}",
            fault_name=row.GZEAB,
            gzeeb_eff=row.gzeeb_eff,
            structural_type=structural_type,
            evidence_class=row.evidence_class,
            faulttype_term=faulttype,
            faulttype_label=faulttype.replace("_", " "),
            observation_term=mapping.evidence_observation(row.evidence_class),
            observation_label=row.evidence_class,
            description_append=f"Synthetic {structural_type}",
            gzece=float(row.GZECE),
            slip_sense="dextral" if i == 2 else "",
            slip_span="synthetic segment" if i == 2 else "",
            planes=[model.FaultAuxPlane(
                azimuth=azimuth,
                dip=float(row.GZECE),
                mode="synthetic fault attitude",
                movement_sense=movement,
                mp_id=f"fp.F{i:03d}.1",
                mp_label=f"F{i:03d} synthetic measurement",
                foot=row.geometry.interpolate(0.52, normalized=True).__geo_interface__,
            )],
            geometry=row.geometry.__geo_interface__,
        )
        faults.append(fault)

    folds = []
    for i, row in enumerate(layers["SIM_LDZOFBA005.WL"].itertuples(), start=1):
        profile = "anticline" if i == 1 else "syncline"
        folds.append(model.FoldRec(
            feature_id=f"fold.{i}",
            name=row.fold_name,
            gzce=row.GZCE,
            profile_term=profile,
            geometry=row.geometry.__geo_interface__,
        ))

    attitudes = []
    for i, row in enumerate(layers["SIM_LDZOFBA016.WT"].itertuples(), start=1):
        vocab_row = mapping.foliation_row(row.GZBBGA)
        attitudes.append(model.AttitudeRec(
            src_id=i,
            gzbbga=row.GZBBGA,
            sem_type="synthetic foliation",
            azimuth=float(row.angle),
            dip=float(row.CHFCED),
            foliation_term=vocab_row.get("term"),
            foliation_label=str(vocab_row.get("term", "")),
            overturned=vocab_row.get("polarity") == "overturned",
            host_norm=row.host_norm,
            host_name=row.host_norm,
            note="synthetic measurement",
            ord=i,
            geometry=row.geometry.__geo_interface__,
        ))
    return units, contacts, faults, folds, attitudes


def emit_gml(layers, output_path):
    units, contacts, faults, folds, attitudes = build_semantics(layers)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    config.BASE_URI = "https://example.org/synthetic-geology/"
    config.SCALE_DENOMINATOR = 250000
    config.SHEET_KEY = "sim"
    config.SHEET = "semantic"
    elements = [features.emit_geologic_unit(unit) for unit in units.values()]

    for unit in units.values():
        for layer_name in ("SIM_LDZOFBB001.WP", "SIM_LDZOFBB002.WP", "SIM_LDZOFBB003.WP",
                           "SIM_LDZOFBB004.WP", "SIM_LDLYAAE002.WP"):
            for row in layers[layer_name].itertuples():
                if row.QDUECC.replace("-", "_") == unit.norm:
                    elements.append(features.emit_mapped_feature(model.MappedFeatureRec(
                        feature_id=f"mf.{unit.norm}",
                        specification_uri=unit.uri,
                        specification_title=unit.name,
                        observation_term="outcrop_observation",
                        geometry=row.geometry.__geo_interface__,
                        map_code=unit.norm,
                        src_file=layer_name,
                    )))
    for contact in contacts:
        elements.append(features.emit_contact(contact))
        elements.append(features.emit_mapped_feature(model.MappedFeatureRec(
            feature_id=contact.gml_id,
            specification_uri=contact.uri,
            specification_title=contact.sem_label,
            observation_term=contact.observation_term,
            geometry=contact.geometry,
            map_code=contact.code,
            src_file="SIM_LDZOFBA002.WL",
        )))
    for fault in faults:
        elements.append(features.emit_sds(fault))
        elements.append(features.emit_mapped_feature(model.MappedFeatureRec(
            feature_id=f"fp.{fault.feature_id}.1",
            specification_uri=fault.uri,
            specification_title=fault.fault_name,
            observation_term=fault.observation_term,
            geometry=fault.geometry,
            map_code=fault.gzeeb_eff,
            src_file="SIM_LDZOFBA003.WL",
        )))
    for fold in folds:
        elements.append(features.emit_fold(fold, mapping.fold_profile(fold.gzce)))
        elements.append(features.emit_mapped_feature(model.MappedFeatureRec(
            feature_id=f"mf.{fold.feature_id}",
            specification_uri=fold.uri,
            specification_title=fold.name,
            observation_term="outcrop_observation",
            geometry=fold.geometry,
            map_code=fold.gzce,
            src_file="SIM_LDZOFBA005.WL",
        )))
    for attitude in attitudes:
        elements.append(features.emit_foliation(attitude))
        elements.append(features.emit_mapped_feature(model.MappedFeatureRec(
            feature_id=f"mf.{attitude.gml_id}",
            specification_uri=attitude.uri,
            specification_title=attitude.sem_type,
            observation_term="outcrop_observation",
            geometry=attitude.geometry,
            map_code=attitude.gzbbga,
            src_file="SIM_LDZOFBA016.WT",
        )))
    root = document.assemble(elements)
    document.write(root, output_path)
    return {
        "units": len(units),
        "contacts": len(contacts),
        "faults": len(faults),
        "folds": len(folds),
        "attitudes": len(attitudes),
        "members": len(elements),
    }


def semantic_report(layers, gml_result, xsd_result):
    units, contacts, faults, folds, attitudes = build_semantics(layers)
    return {
        "notice": "Synthetic semantic model only; no real JWD feature is reused.",
        "counts": gml_result,
        "units": [
            {
                "norm": unit.norm,
                "type": unit.unittype_term,
                "rank": unit.rank_term,
                "event_process": unit.event.eventprocess_term,
                "older_era": unit.event.older_era,
                "younger_era": unit.event.younger_era,
                "relations": unit.relations,
                "compositions": [c.lithology_term for c in unit.compositions],
            }
            for unit in units.values()
        ],
        "contacts": [
            {
                "code": c.code,
                "type": c.contacttype_term,
                "observation": c.observation_term,
                "younger_side": c.younger_side,
            }
            for c in contacts
        ],
        "faults": [
            {
                "id": f.feature_id,
                "type": f.faulttype_term,
                "observation": f.observation_term,
                "dip": f.gzece,
                "slip_sense": f.slip_sense,
            }
            for f in faults
        ],
        "folds": [{"id": f.feature_id, "profile": f.profile_term} for f in folds],
        "attitudes": [
            {
                "code": a.gzbbga,
                "type": a.foliation_term,
                "azimuth": a.azimuth,
                "dip": a.dip,
                "overturned": a.overturned,
                "host": a.host_norm,
            }
            for a in attitudes
        ],
        "xsd_validation": xsd_result,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("output/semantic_geology"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dpi", type=int, default=160)
    args = parser.parse_args()

    layers = enrich_layers(generate_layers(seed=args.seed))
    vectors = args.output_dir / "vectors"
    write_layers(layers, vectors)
    native_layers = read_layers(vectors)
    result = render_layers(native_layers, args.output_dir, dpi=args.dpi)
    gml_path = args.output_dir / "synthetic_geology.gml"
    gml_result = emit_gml(layers, gml_path)
    try:
        valid, errors = validate.validate(gml_path)
        xsd_result = {"valid": bool(valid), "errors": str(errors)}
    except (FileNotFoundError, etree.XMLSchemaParseError) as exc:
        xsd_result = {"valid": None, "skipped": str(exc)}
    report = semantic_report(layers, gml_result, xsd_result)
    report["summary"] = summarise(result.reports)
    (args.output_dir / "semantic_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"output_dir": str(args.output_dir), "gml": str(gml_path),
                      "counts": gml_result, "summary": report["summary"],
                      "xsd_validation": xsd_result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
