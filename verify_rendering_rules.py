#!/usr/bin/env python3
"""验证 DZ/T 0179 渲染规则中间表示（IR）的完整性与一致性。

检查项：
1. IR JSON Schema 结构校验（metadata、palettes、rules 等）。
2. IR 色板与 legacy dz_t_0179_colors.json 完全一致。
3. geological_unit_color_mapping_final.json 中每个地质单元代号都能被 IR 解析为颜色。
4. 统计规则覆盖率与缺失项。

输出：
- 控制台摘要
- rendering_rules_verification_report.json
- rendering_rules_verification_report.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from pymapgis.rendering import load_ir, rgb_to_hex

IR_PATH = ROOT / "dz_t_0179_rendering_rules.json"
LEGACY_COLORS_PATH = ROOT / "dz_t_0179_colors.json"
MAPPING_PATH = ROOT / "geological_unit_color_mapping_final.json"
REPORT_JSON = ROOT / "rendering_rules_verification_report.json"
REPORT_MD = ROOT / "rendering_rules_verification_report.md"


def load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_ir_schema(ir: dict) -> List[str]:
    """返回 schema 错误列表；空列表表示通过。"""
    errors: List[str] = []
    if not isinstance(ir, dict):
        return ["IR root is not a JSON object"]

    required = ("metadata", "palettes", "line_styles", "patterns", "symbols", "rules")
    for key in required:
        if key not in ir:
            errors.append(f"missing top-level key: {key}")

    palettes = ir.get("palettes", {})
    if "dz_t_0179" not in palettes:
        errors.append("palettes missing 'dz_t_0179'")
    else:
        dz = palettes["dz_t_0179"]
        for category in ("period", "cross_period"):
            if category not in dz:
                errors.append(f"dz_t_0179 palette missing '{category}'")

    rules = ir.get("rules", {})
    for section in ("units", "attitudes", "labels"):
        if section not in rules:
            errors.append(f"rules missing section '{section}'")
        elif not isinstance(rules[section], list):
            errors.append(f"rules section '{section}' is not a list")
    if "faults" not in rules:
        errors.append("rules missing section 'faults'")
    elif not isinstance(rules["faults"], dict):
        errors.append("rules section 'faults' is not an object")

    return errors


def compare_palettes(ir: "Any", legacy: dict) -> Tuple[bool, List[Dict[str, Any]]]:
    """比较 IR palettes 与 legacy colors，返回 (是否一致, 差异明细)。"""
    mismatches: List[Dict[str, Any]] = []
    ir_palette = ir.palettes.get("dz_t_0179", {})

    for category, mapping in legacy.items():
        if category == "_comment":
            continue
        ir_mapping = ir_palette.get(category)
        if ir_mapping is None:
            mismatches.append({"category": category, "key": None, "reason": "missing in IR"})
            continue
        for key, value in mapping.items():
            ir_value = ir_mapping.get(key)
            if ir_value is None:
                mismatches.append({"category": category, "key": key, "reason": "missing in IR"})
                continue
            if list(ir_value) != list(value):
                mismatches.append({
                    "category": category,
                    "key": key,
                    "reason": "RGB mismatch",
                    "legacy": value,
                    "ir": ir_value,
                })

    # 反向检查 IR 是否多出来 legacy 没有的键
    for category, mapping in ir_palette.items():
        if category not in legacy:
            mismatches.append({"category": category, "key": None, "reason": "extra in IR"})
        else:
            for key in mapping:
                if key not in legacy[category]:
                    mismatches.append({"category": category, "key": key, "reason": "extra in IR"})

    return len(mismatches) == 0, mismatches


def check_unit_coverage(ir: "Any", mapping: List[dict]) -> Dict[str, Any]:
    """检查每个地质单元代号是否都能解析出颜色，并统计应用了 pattern 的单元。"""
    total = 0
    resolved = 0
    unresolved: List[Dict[str, Any]] = []
    key_counts: Dict[str, int] = {}
    pattern_matches: Dict[str, int] = {}

    for record in mapping:
        code = str(record.get("code", "")).strip()
        if not code:
            continue
        total += 1
        style = ir.resolve_unit_style(code)
        rgb = np.array(style["fill"]["rgb"]) / 255.0
        key = style["fill"].get("key") or "unknown"
        pattern = style["fill"].get("pattern")
        if key == "unknown":
            unresolved.append({
                "code": code,
                "layer": record.get("layer"),
                "rgb": [int(c * 255) for c in rgb],
            })
        else:
            resolved += 1
            key_counts[key] = key_counts.get(key, 0) + 1
        if pattern:
            pattern_matches[pattern] = pattern_matches.get(pattern, 0) + int(record.get("count", 1))

    return {
        "total_codes": total,
        "resolved": resolved,
        "unresolved": unresolved,
        "key_counts": dict(sorted(key_counts.items(), key=lambda x: -x[1])),
        "pattern_matches": dict(sorted(pattern_matches.items(), key=lambda x: -x[1])),
    }


def check_patterns(ir: "Any") -> Tuple[bool, List[Dict[str, Any]]]:
    """检查 IR 中每个 pattern 是否有对应的瓦片文件。"""
    missing: List[Dict[str, Any]] = []
    for pattern_id, pattern in ir.patterns.items():
        tile_file = pattern.get("tile_file")
        if not tile_file:
            missing.append({"pattern": pattern_id, "reason": "no tile_file"})
            continue
        tile_path = ROOT / tile_file
        if not tile_path.exists():
            missing.append({"pattern": pattern_id, "reason": f"missing tile: {tile_file}"})
    return len(missing) == 0, missing


def main() -> int:
    print("Loading IR...")
    try:
        ir = load_ir(IR_PATH)
    except Exception as exc:
        print(f"[FAIL] IR load error: {exc}")
        return 1

    print("Validating IR schema...")
    schema_errors = validate_ir_schema(ir.data)

    print("Loading legacy colors...")
    legacy = load_json(LEGACY_COLORS_PATH)

    print("Comparing palettes...")
    palettes_ok, mismatches = compare_palettes(ir, legacy)

    print("Loading unit mapping...")
    mapping = load_json(MAPPING_PATH)

    print("Checking unit coverage...")
    coverage = check_unit_coverage(ir, mapping)

    print("Checking patterns...")
    patterns_ok, missing_tiles = check_patterns(ir)

    report = {
        "ir_path": str(IR_PATH),
        "schema_errors": schema_errors,
        "palettes_consistent": palettes_ok,
        "palette_mismatches": mismatches,
        "unit_coverage": coverage,
        "patterns_ok": patterns_ok,
        "missing_tiles": missing_tiles,
        "overall_ok": (
            len(schema_errors) == 0
            and palettes_ok
            and coverage["unresolved"] == []
            and patterns_ok
        ),
    }

    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    lines = [
        "# DZ/T 0179 渲染规则 IR 验证报告",
        "",
        f"- IR 文件：`{IR_PATH.name}`",
        f"- Legacy 色表：`{LEGACY_COLORS_PATH.name}`",
        f"- 单元映射：`{MAPPING_PATH.name}`",
        "",
        "## Schema 校验",
        "通过。" if not schema_errors else f"失败：{len(schema_errors)} 项错误。",
    ]
    if schema_errors:
        lines.extend([""] + [f"- {e}" for e in schema_errors])

    lines.extend([
        "",
        "## 色板一致性",
        f"{'一致' if palettes_ok else f'不一致（{len(mismatches)} 处差异）'}。",
    ])
    if mismatches:
        lines.append("")
        for m in mismatches[:20]:
            lines.append(f"- `{m['category']}/{m['key']}`: {m['reason']}")
        if len(mismatches) > 20:
            lines.append(f"- ... 共 {len(mismatches)} 处差异")

    lines.extend([
        "",
        "## 地质单元代号覆盖率",
        f"- 总代码数：{coverage['total_codes']}",
        f"- 可解析：{coverage['resolved']}",
        f"- 未解析：{len(coverage['unresolved'])}",
    ])
    if coverage["unresolved"]:
        lines.append("")
        for u in coverage["unresolved"]:
            lines.append(f"- `{u['code']}` (layer {u['layer']})")

    lines.extend([
        "",
        "## 颜色键分布（前 20）",
    ])
    for key, count in list(coverage["key_counts"].items())[:20]:
        lines.append(f"- `{key}`: {count}")

    lines.extend([
        "",
        "## 花纹瓦片检查",
        f"{'通过' if patterns_ok else f'失败（{len(missing_tiles)} 处缺失）'}。",
    ])
    if missing_tiles:
        lines.append("")
        for m in missing_tiles[:20]:
            lines.append(f"- `{m['pattern']}`: {m['reason']}")

    lines.extend([
        "",
        "## Pattern 应用统计",
    ])
    if coverage["pattern_matches"]:
        for pattern, count in list(coverage["pattern_matches"].items())[:20]:
            lines.append(f"- `{pattern}`: {count} features")
    else:
        lines.append("- 当前没有 unit 匹配到 pattern。")

    lines.extend([
        "",
        "## 总体结论",
        "✅ IR 通过 Phase 2 验证。" if report["overall_ok"] else "❌ IR 未通过 Phase 2 验证，请查看上述错误。",
    ])

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\nReport written to {REPORT_JSON} and {REPORT_MD}")
    print("Overall:", "OK" if report["overall_ok"] else "FAILED")
    return 0 if report["overall_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
