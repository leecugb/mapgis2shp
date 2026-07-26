#!/usr/bin/env python3
"""由 dz_t_0179_colors.json 生成完整、可读的配色映射表（Markdown + CSV）。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).parent
JSON_PATH = ROOT / "dz_t_0179_colors.json"
MD_PATH = ROOT / "dz_t_0179_color_mapping_table.md"
CSV_PATH = ROOT / "dz_t_0179_color_mapping_table.csv"

SECTION_NAMES: dict[str, str] = {
    "period": "表2 正式地层单位用色",
    "cross_period": "表3 跨时代地层单位用色",
    "intrusive_acid_intermediate": "表6–8 酸性—中酸性侵入岩用色",
    "intrusive_neutral": "表9 中性侵入岩用色",
    "intrusive_basic": "表10 基性侵入岩用色",
    "intrusive_ultrabasic": "表11 超基性侵入岩用色",
    "intrusive_alkaline": "表12 碱性侵入岩用色",
    "rock_type_fallback": "侵入岩岩性大类兜底色",
    "fallback": "其他兜底/特殊用色",
}


def rgb_to_hex(rgb: list[int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(rgb[0], rgb[1], rgb[2])


def main() -> int:
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    md_lines: list[str] = []
    md_lines.append("# DZ/T 0179 地质图用色标准完整配色映射表\n")
    md_lines.append(
        "来源：`/media/lee/KINGSTON/P020250429414585946484.pdf`\n"
    )
    md_lines.append(
        "说明：PDF 中的色标表为栅格图片，本表颜色值通过对表格图片色块采样并人工校核得到。\n"
    )

    csv_rows: list[dict[str, str]] = []

    for key, section_name in SECTION_NAMES.items():
        values = data.get(key)
        if not values:
            continue
        md_lines.append(f"## {section_name}\n")
        md_lines.append("| 代号/键 | R | G | B | HEX | 备注 |")
        md_lines.append("|---------|---|---|---|-----|------|")

        if isinstance(values, dict):
            for code, rgb in values.items():
                hex_val = rgb_to_hex(rgb)
                note = ""
                if key.startswith("intrusive_"):
                    note = "按侵入岩大类及时代选用"
                elif key == "rock_type_fallback":
                    note = "该岩性无具体时代信息时的兜底色"
                elif key == "fallback":
                    note = "标准未规定面色时的兜底色"
                md_lines.append(
                    f"| `{code}` | {rgb[0]} | {rgb[1]} | {rgb[2]} | {hex_val} | {note} |"
                )
                csv_rows.append(
                    {
                        "section": section_name,
                        "code": code,
                        "R": str(rgb[0]),
                        "G": str(rgb[1]),
                        "B": str(rgb[2]),
                        "HEX": hex_val,
                        "note": note,
                    }
                )
        md_lines.append("")

    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"Saved: {MD_PATH}")

    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["section", "code", "R", "G", "B", "HEX", "note"],
        )
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"Saved: {CSV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
