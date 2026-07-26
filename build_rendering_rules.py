#!/usr/bin/env python3
"""从 pattern_manifest.csv 等来源组装 dz_t_0179_rendering_rules.json。

目前支持：
- 从 pattern_manifest.csv 读取已验证的花纹条目，生成 IR patterns 和 unit rules。
- 保留已有的 palettes / line_styles / symbols。

使用方式：
    python3 build_rendering_rules.py
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).parent
IR_PATH = ROOT / "dz_t_0179_rendering_rules.json"
MANIFEST_PATH = ROOT / "data" / "pattern_swatches" / "pattern_manifest.csv"
FAULT_STYLES_PATH = ROOT / "fault_rendering_styles.json"


# fault_rendering_styles.json source -> IR line_style ref 的映射
BASE_STYLE_REFS = {
    "LDZOFBA003": "fault_measured",
    "LYGREBA001": "fault_inferred",
    "LZLPGDJ002": "deep_fault",
}


def load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_patterns_from_manifest(manifest_rows: List[dict]) -> Dict[str, dict]:
    patterns: Dict[str, dict] = {}
    for row in manifest_rows:
        if not row.get("code") or row.get("verified") == "no":
            continue
        code = row["code"].strip()
        name = row.get("name", "").strip()
        ptype = row.get("pattern_type", "image")
        pattern_id = f"unit_pattern_{code}"
        tile_path = row.get("tile_path", "")
        hatch_char = row.get("hatch_char", "")

        pattern: Dict[str, Any] = {
            "name": name or pattern_id,
            "source": {
                "pdf_page": int(row["page"]),
                "table": row.get("table", ""),
                "row": int(row["row"]),
            },
            "type": ptype,
            "tile_file": tile_path,
            "verified": row.get("verified", "no"),
        }
        if ptype == "hatch" and hatch_char:
            pattern["hatch"] = {
                "char": hatch_char,
                "color": "#000000",
                "linewidth": 0.2,
            }
        patterns[pattern_id] = pattern
    return patterns


def build_unit_rules(patterns: Dict[str, dict]) -> List[dict]:
    rules: List[dict] = []
    for pattern_id, pattern in patterns.items():
        code = pattern_id.replace("unit_pattern_", "")
        escaped = re.escape(code)
        table = str(pattern.get("source", {}).get("table", ""))
        # 表5 为第四系成因类型，必须出现在以 Q 开头的地质代号中，避免误匹配 N1a 等岩性后缀
        if "表5" in table:
            pattern_re = f"Q.*[↑→]{escaped}($|[-.])"
        else:
            pattern_re = f"[↑→]{escaped}($|[-.])"
        rules.append({
            "id": f"unit_{code}",
            "target": {
                "layer": "*",
                "property": "QDUECC",
                "match": {"type": "regex", "pattern": pattern_re},
            },
            "style": {
                "fill": {
                    "palette": "dz_t_0179",
                    "key": None,
                    "pattern": pattern_id,
                },
                "stroke": {"ref": "unit_boundary"},
            },
        })
    return rules


def migrate_fault_styles() -> Dict[str, Any]:
    """把 fault_rendering_styles.json 迁移为 IR rules.faults 结构。"""
    if not FAULT_STYLES_PATH.exists():
        return {}
    src = load_json(FAULT_STYLES_PATH)

    faults: Dict[str, Any] = {
        "global": src.get("global", {}),
        "sources": {},
        "named_faults": src.get("named_faults", {}),
    }

    for src_name, cfg in src.get("sources", {}).items():
        base_style = cfg.get("base_style", {})
        # 把具体 base_style 转为 line_style ref + 保留 alpha
        ref = BASE_STYLE_REFS.get(src_name, "fault_measured")
        base_style_ir = {"ref": ref}
        if "alpha" in base_style:
            base_style_ir["alpha"] = base_style["alpha"]

        faults["sources"][src_name] = {
            "file": cfg.get("file"),
            "data_type": cfg.get("data_type"),
            "type_field": cfg.get("type_field"),
            "dip_field": cfg.get("dip_field"),
            "tendency_field": cfg.get("tendency_field"),
            "name_field": cfg.get("name_field"),
            "description_field": cfg.get("description_field"),
            "reliability_field": cfg.get("reliability_field"),
            "base_style": base_style_ir,
            "symbol_defaults": cfg.get("symbol_defaults", {}),
            "type_map": cfg.get("type_map", {}),
        }
    return faults


def main() -> int:
    ir = load_json(IR_PATH)

    manifest_rows: List[dict] = []
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, encoding="utf-8", newline="") as f:
            manifest_rows = list(csv.DictReader(f))

    new_patterns = build_patterns_from_manifest(manifest_rows)
    # 合并到现有 patterns（不覆盖）
    ir.setdefault("patterns", {})
    ir["patterns"].update(new_patterns)

    new_rules = build_unit_rules(new_patterns)
    ir.setdefault("rules", {})
    ir["rules"].setdefault("units", [])
    # 去重：以 id 为键
    existing = {r["id"]: r for r in ir["rules"]["units"]}
    for r in new_rules:
        existing[r["id"]] = r
    ir["rules"]["units"] = list(existing.values())

    # 迁移 fault 样式到 IR
    ir["rules"]["faults"] = migrate_fault_styles()

    ir["metadata"]["rule_build_time"] = None  # will be updated if needed
    ir["metadata"]["pattern_count"] = len(ir["patterns"])
    ir["metadata"]["unit_rule_count"] = len(ir["rules"]["units"])

    save_json(IR_PATH, ir)
    print(f"Updated {IR_PATH}")
    print(f"  patterns: {len(ir['patterns'])}")
    print(f"  unit rules: {len(ir['rules']['units'])}")
    print(f"  fault sources: {len(ir['rules'].get('faults', {}).get('sources', {}))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
