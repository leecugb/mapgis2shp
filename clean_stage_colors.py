#!/usr/bin/env python3
"""对 dz_t_0179_stage_colors_raw.json 做简单清洗，得到部分可识别的阶一级颜色。"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
RAW_JSON = ROOT / "dz_t_0179_stage_colors_raw.json"
OUT_JSON = ROOT / "dz_t_0179_stage_colors_partial.json"
OUT_MD = ROOT / "dz_t_0179_stage_colors_partial.md"
OUT_CSV = ROOT / "dz_t_0179_stage_colors_partial.csv"

KNOWN_SERIES = ["Qh", "Qp", "Qn", "QpQh", "N", "E", "K", "J", "T", "P", "C", "D", "S", "O", "Pt", "Ch", "Nh", "Z", "Qb", "Ar", "Hd", "Є"]


def is_gray(rgb: list[int]) -> bool:
    return max(rgb) - min(rgb) < 15


def clean_text(t: str) -> str:
    if not t:
        return ""
    return (
        t.strip()
        .replace(" ", "")
        .replace("!", "1")
        .replace("l", "1")
        .replace("I", "1")
        .replace("?", "")
    )


def looks_like_cmyk(text: str) -> bool:
    t = text.upper()
    letters = [letter for letter in ["C", "M", "Y", "K"] if re.search(rf"{letter}\d", t)]
    return len(letters) >= 2


def extract_code(text: str, allow_cmyk: bool = False) -> str:
    t = clean_text(text)
    if not t:
        return ""
    if not allow_cmyk and looks_like_cmyk(text):
        return ""
    for s in sorted(KNOWN_SERIES, key=len, reverse=True):
        if t.upper().startswith(s.upper()):
            rest = t[len(s) :]
            rest_core = re.split(r"[^0-9\-]", rest)[0]
            return s + rest_core
    m = re.match(r"([A-Za-z]+)([0-9\-]*)", t)
    if m:
        prefix = m.group(1)
        if any(prefix.upper() == s.upper() for s in KNOWN_SERIES):
            return prefix + m.group(2)
    return ""


def main() -> int:
    with open(RAW_JSON, encoding="utf-8") as f:
        raw = json.load(f)

    clean: list[dict] = []
    for r in raw:
        rec = r["recommended_rgb"]
        if is_gray(rec) or all(c > 250 for c in rec) or all(c < 80 for c in rec):
            continue
        code = extract_code(r["stage_ocr"], allow_cmyk=False)
        if not code:
            code = extract_code(r["label_ocr"], allow_cmyk=False)
        if not code:
            continue
        clean.append(
            {
                "page": r["page"],
                "row": r["row"],
                "code": code,
                "rgb": rec,
                "hex": "#{:02x}{:02x}{:02x}".format(*rec),
                "stage_ocr": r["stage_ocr"],
                "label_ocr": r["label_ocr"],
            }
        )

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)
    print(f"Saved: {OUT_JSON} ({len(clean)} rows)")

    md_lines = [
        "# DZ/T 0179 表2 阶一级颜色（部分自动提取，待人工校核）\n",
        "说明：本表由 `extract_stage_level_colors.py` 自动从 PDF 表2 栅格图片中提取，",
        "RapidOCR 对部分中文阶名识别不完整，因此只保留了 OCR 可识别代号的行，",
        "完整 150 行原始结果见 `dz_t_0179_stage_colors_raw.csv`。\n",
        "| 代号 | R | G | B | HEX | 原始 stage_ocr | 原始 label_ocr |",
        "|------|---|---|---|-----|----------------|----------------|",
    ]
    csv_rows: list[dict] = []
    for c in clean:
        md_lines.append(
            f"| `{c['code']}` | {c['rgb'][0]} | {c['rgb'][1]} | {c['rgb'][2]} | {c['hex']} | "
            f"{c['stage_ocr']} | {c['label_ocr']} |"
        )
        csv_rows.append(
            {
                "code": c["code"],
                "R": c["rgb"][0],
                "G": c["rgb"][1],
                "B": c["rgb"][2],
                "HEX": c["hex"],
                "stage_ocr": c["stage_ocr"],
                "label_ocr": c["label_ocr"],
            }
        )

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"Saved: {OUT_MD}")

    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["code", "R", "G", "B", "HEX", "stage_ocr", "label_ocr"]
        )
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"Saved: {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
