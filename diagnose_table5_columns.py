#!/usr/bin/env python3
"""生成 page22 表 5 的列定位诊断页面，帮助人工确定图例列位置。"""

from __future__ import annotations

import base64
import io
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
from PIL import Image

ROOT = Path(__file__).parent
IMG_PATH = ROOT / "pdf_table_images" / "page22_img1.png"
OUTPUT_HTML = ROOT / "data" / "pattern_swatches" / "table5_column_diagnosis.html"

# 候选 ROI（x0, x1, 标签）
CANDIDATE_ROIS = [
    (400, 550, "候选1: x=400-550 (高方差)"),
    (550, 700, "候选2: x=550-700"),
    (700, 900, "候选3: x=700-900"),
    (900, 1070, "候选4: x=900-1070"),
    (1070, 1290, "候选5: x=1070-1290"),
]


def detect_rows(img: Image.Image) -> List[Tuple[int, int]]:
    arr = np.array(img)
    gray = np.mean(arr, axis=2).astype(np.uint8) if len(arr.shape) == 3 else arr
    h_proj = np.mean(gray, axis=1)
    lines = []
    in_run = False
    start = 0
    for i, v in enumerate(h_proj):
        if v < 210 and not in_run:
            in_run = True
            start = i
        elif v >= 210 and in_run:
            in_run = False
            lines.append((start, i))
    if in_run:
        lines.append((start, len(h_proj)))
    lines = [(s, e) for s, e in lines if 10 < s < len(h_proj) - 10]
    if not lines:
        return []
    merged = [lines[0]]
    for s, e in lines[1:]:
        ps, pe = merged[-1]
        if s - pe <= 3:
            merged[-1] = (ps, e)
        else:
            merged.append((s, e))
    rows = [(merged[i][1], merged[i + 1][0]) for i in range(len(merged) - 1) if merged[i + 1][0] - merged[i][1] > 20]
    return rows


def image_to_data_uri(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def main() -> int:
    img = Image.open(IMG_PATH)
    rows = detect_rows(img)

    html_parts = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="UTF-8">',
        "<title>表5 图例列定位诊断</title>",
        "<style>",
        "body { font-family: sans-serif; margin: 20px; background: #f5f5f5; }",
        "h1 { font-size: 20px; }",
        ".row { display: flex; align-items: flex-start; gap: 10px; margin: 20px 0; padding: 10px; background: #fff; border-radius: 8px; flex-wrap: wrap; }",
        ".roi { text-align: center; }",
        ".roi img { border: 1px solid #ccc; max-height: 100px; }",
        ".roi-label { font-size: 11px; color: #666; margin-top: 4px; max-width: 120px; }",
        "</style>",
        "</head>",
        "<body>",
        "<h1>表5 图例列定位诊断</h1>",
        "<p>每行左侧是原始 PDF 行；右侧是不同 x 范围的候选区域裁剪。请告诉我哪一列是真正的“图例列”（花纹图案）。</p>",
    ]

    for idx, (y0, y1) in enumerate(rows):
        html_parts.append(f'<div class="row">')
        html_parts.append(f'<div><strong>Row {idx}</strong><br>y={y0}-{y1}</div>')
        full_row = img.crop((0, y0, img.width, y1))
        html_parts.append(f'<div class="roi"><img src="{image_to_data_uri(full_row)}" title="原始行"><div class="roi-label">原始行</div></div>')
        for x0, x1, label in CANDIDATE_ROIS:
            crop = img.crop((x0, y0, x1, y1))
            html_parts.append(f'<div class="roi"><img src="{image_to_data_uri(crop)}" title="{label}"><div class="roi-label">{label}</div></div>')
        html_parts.append('</div>')

    html_parts.extend(["</body>", "</html>"])
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write("\n".join(html_parts))

    print(f"Diagnosis page saved to: {OUTPUT_HTML}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
