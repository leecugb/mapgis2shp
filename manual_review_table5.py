#!/usr/bin/env python3
"""为 DZ/T 0179 表5（第四系成因类型花纹）生成人工校核页面。

输出一个 HTML 文件，每行展示：
- 原始 PDF 裁剪行
- 左侧文字区（OCR 结果）
- 右侧花纹区 / 32px 瓦片
- 当前自动分配的 code

用户可直接在浏览器中对比 PDF 与瓦片，然后在 data/pattern_swatches/pattern_manifest.csv 中修正 code。
"""

from __future__ import annotations

import base64
import csv
import io
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
from PIL import Image

ROOT = Path(__file__).parent
TABLE_IMAGES_DIR = ROOT / "pdf_table_images"
RAW_DIR = ROOT / "data" / "pattern_swatches" / "raw"
TILE_DIR = ROOT / "data" / "patterns"
OUTPUT_HTML = ROOT / "data" / "pattern_swatches" / "table5_manual_review.html"


def find_horizontal_lines(gray: np.ndarray, threshold: int = 210, min_thickness: int = 1) -> List[Tuple[int, int]]:
    h_proj = np.mean(gray, axis=1)
    runs: List[Tuple[int, int]] = []
    in_run = False
    start = 0
    for i, v in enumerate(h_proj):
        if v < threshold and not in_run:
            in_run = True
            start = i
        elif v >= threshold and in_run:
            in_run = False
            runs.append((start, i))
    if in_run:
        runs.append((start, len(h_proj)))
    lines = [(s, e) for s, e in runs if e - s >= min_thickness and 10 < s < len(h_proj) - 10]
    if not lines:
        return []
    merged = [lines[0]]
    for s, e in lines[1:]:
        ps, pe = merged[-1]
        if s - pe <= 3:
            merged[-1] = (ps, e)
        else:
            merged.append((s, e))
    return merged


def detect_rows(page_img: Image.Image) -> List[Tuple[int, int]]:
    arr = np.array(page_img)
    gray = np.mean(arr, axis=2).astype(np.uint8) if len(arr.shape) == 3 else arr
    lines = find_horizontal_lines(gray)
    rows = []
    for i in range(len(lines) - 1):
        y0, y1 = lines[i][1], lines[i + 1][0]
        if y1 - y0 >= 20:
            rows.append((y0, y1))
    return rows


def image_to_data_uri(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def ocr_region(img: Image.Image) -> str:
    """对图像区域运行 RapidOCR，返回识别文本。"""
    try:
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()
        arr = np.array(img)
        result = engine(arr)
        if result and result[0]:
            texts = [line[1] for line in result[0] if len(line) > 1]
            return " ".join(texts)
    except Exception as exc:
        return f"[OCR error: {exc}]"
    return ""


def main() -> int:
    # 读取当前 manifest
    manifest = {}
    manifest_path = ROOT / "data" / "pattern_swatches" / "pattern_manifest.csv"
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row["page"] == "22":
                    manifest[int(row["row"])] = row

    rows_data = []
    row_global = 0
    for img_path in sorted(TABLE_IMAGES_DIR.glob("page22_img*.png")):
        img = Image.open(img_path)
        rows = detect_rows(img)
        w = img.width
        text_right = int(w * 0.35)
        for y0, y1 in rows:
            full_row = img.crop((0, y0, w, y1))
            text_crop = img.crop((0, y0, text_right, y1))
            pattern_crop = img.crop((text_right, y0, w, y1))
            ocr_text = ocr_region(text_crop)
            tile_path = TILE_DIR / f"page22_row{row_global:03d}_tile32.png"
            tile_img = Image.open(tile_path) if tile_path.exists() else None
            current = manifest.get(row_global, {})
            rows_data.append({
                "row": row_global,
                "full": full_row,
                "text": text_crop,
                "pattern": pattern_crop,
                "tile": tile_img,
                "ocr": ocr_text,
                "code": current.get("code", ""),
                "name": current.get("name", ""),
            })
            row_global += 1

    html_parts = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="UTF-8">',
        "<title>表5 第四系成因类型花纹校核</title>",
        "<style>",
        "body { font-family: sans-serif; margin: 20px; background: #f5f5f5; }",
        "h1 { font-size: 20px; }",
        ".row { display: flex; align-items: center; gap: 20px; margin: 15px 0; padding: 10px; background: #fff; border-radius: 8px; }",
        ".row img { border: 1px solid #ccc; max-height: 120px; }",
        ".info { min-width: 200px; }",
        ".ocr { color: #666; font-size: 12px; max-width: 300px; }",
        "</style>",
        "</head>",
        "<body>",
        "<h1>表5 第四系成因类型花纹校核</h1>",
        "<p>左侧为原始 PDF 行；中间为 OCR 识别的文字区；右侧为提取的花纹区与 32px 瓦片。请根据 PDF 实际内容在 <code>data/pattern_swatches/pattern_manifest.csv</code> 中修正 code/name。</p>",
    ]

    for d in rows_data:
        html_parts.append('<div class="row">')
        html_parts.append(f'<div class="info">')
        html_parts.append(f'<strong>Row {d["row"]}</strong><br>')
        html_parts.append(f'当前 code: <code>{d["code"] or "未分配"}</code><br>')
        html_parts.append(f'当前 name: {d["name"] or "未分配"}')
        html_parts.append('</div>')
        html_parts.append(f'<img src="{image_to_data_uri(d["full"])}" title="原始行">')
        html_parts.append(f'<img src="{image_to_data_uri(d["text"])}" title="文字区">')
        html_parts.append(f'<div class="ocr">OCR: {d["ocr"]}</div>')
        html_parts.append(f'<img src="{image_to_data_uri(d["pattern"])}" title="花纹区">')
        if d["tile"]:
            html_parts.append(f'<img src="{image_to_data_uri(d["tile"])}" title="32px 瓦片">')
        html_parts.append('</div>')

    html_parts.extend(["</body>", "</html>"])

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write("\n".join(html_parts))

    print(f"Manual review page saved to: {OUTPUT_HTML}")
    print(f"Total rows: {len(rows_data)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
