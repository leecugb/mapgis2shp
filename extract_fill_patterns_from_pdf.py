#!/usr/bin/env python3
"""从 DZ/T 0179 PDF 表页提取填充花纹候选单元格。

目标表：
- 表5  第四系成因类型花纹及用色（page 22）
- 表15 侵入岩填充花纹用色（page 31-32）
- 表16 新生代以前火山岩用色（page 32）
- 表17 新生代火山岩用色（page 32）
- 表18 潜火山岩用色（page 33）
- 表19 变质表壳岩用色（page 33）
- 表20 变质深成岩用色（page 33）
- 表21 特殊岩石单位用色（page 33-34）
- 表24 网纹用色（page 35-36）

当前实现：
- 读取 pdf_table_images/ 下已提取的 PNG。
- 通过水平投影检测表格横线，将页面分割为行。
- 对每一行，在水平方向通过垂直投影或固定 ROI 提取右侧花纹候选区。
- 输出原始裁剪图到 data/pattern_swatches/raw/，供 analyze_fill_patterns.py 进一步处理。

注意：
- 由于表格结构不一，本脚本使用启发式规则；不确定的分割会标记为 manual_review。
- 文字与代码的关联需要人工在 pattern_manifest.csv 中填写。
"""

from __future__ import annotations

import csv
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

ROOT = Path(__file__).parent
TABLE_IMAGES_DIR = ROOT / "pdf_table_images"
SWATCH_DIR = ROOT / "data" / "pattern_swatches" / "raw"
MANIFEST_PATH = ROOT / "data" / "pattern_swatches" / "pattern_manifest.csv"

# 页面到表的映射（来自 pdf_extracted_tables.json 的人工摘要）
PATTERN_PAGES: Dict[int, List[str]] = {
    22: ["表5"],
    31: ["表13", "表14", "表15"],
    32: ["表15", "表16", "表17"],
    33: ["表18", "表19", "表20", "表21"],
    34: ["表21", "表22"],
    35: ["表22", "表23", "表24"],
    36: ["表24"],
}


def find_horizontal_lines(gray: np.ndarray, threshold: int = 200, min_thickness: int = 1) -> List[Tuple[int, int]]:
    """返回水平暗线（上，下）列表，按 y 坐标排序。"""
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
    return [(s, e) for s, e in runs if e - s >= min_thickness]


def detect_rows(page_img: Image.Image, header_rows: int = 1) -> List[Tuple[int, int, bool]]:
    """把页面按水平线分割为行，返回 [(y0, y1, needs_manual_review), ...]。"""
    arr = np.array(page_img)
    gray = np.mean(arr, axis=2).astype(np.uint8) if len(arr.shape) == 3 else arr

    lines = find_horizontal_lines(gray, threshold=210, min_thickness=1)
    # 过滤页面边缘线，只保留内部横线
    h, w = gray.shape
    lines = [(s, e) for s, e in lines if 10 < s < h - 10]

    if len(lines) < 2:
        return []

    # 合并过近的线（有时双线只隔 1px）
    merged: List[Tuple[int, int]] = [lines[0]]
    for s, e in lines[1:]:
        ps, pe = merged[-1]
        if s - pe <= 3:
            merged[-1] = (ps, e)
        else:
            merged.append((s, e))

    rows: List[Tuple[int, int, bool]] = []
    for i in range(len(merged) - 1):
        y0 = merged[i][1]
        y1 = merged[i + 1][0]
        height = y1 - y0
        if height < 20:
            continue
        # 行高异常时标记人工复核
        needs_review = height > 250 or height < 30
        rows.append((y0, y1, needs_review))
    return rows


# 页面特定的花纹列 ROI（根据页面结构诊断结果设定）
# page22 表5：文字区 160-400，花纹区 400-530，色块/空白 530-1292
PATTERN_ROIS: Dict[int, Dict[str, Tuple[int, int]]] = {
    22: {
        "page22_img1.png": (400, 530),
        "page22_img2.png": (400, 530),
    },
}


def crop_pattern_swatch(
    page_img: Image.Image,
    row_y0: int,
    row_y1: int,
    pattern_roi: Optional[Tuple[int, int]] = None,
) -> Optional[Image.Image]:
    """从一行中裁剪花纹候选区。

    优先使用 page-specific pattern_roi；若未提供，则回退到启发式检测。
    """
    w, h = page_img.size
    if pattern_roi is None:
        # 回退：取右侧 1/3 区域，避开左侧文字
        left = int(w * 0.55)
        right = int(w * 0.85)
    else:
        left, right = pattern_roi

    if left >= right or right - left < 20:
        return None

    return page_img.crop((left, row_y0, right, row_y1))


def process_page(page_num: int, out_dir: Path, writer) -> int:
    """处理一页，返回提取的候选数。"""
    count = 0
    row_global = 0
    candidates = []
    rois = PATTERN_ROIS.get(page_num, {})
    for img_path in sorted(TABLE_IMAGES_DIR.glob(f"page{page_num}_img*.png")):
        img = Image.open(img_path)
        rows = detect_rows(img)
        tables = PATTERN_PAGES.get(page_num, [f"page{page_num}"])
        table_hint = tables[0] if len(tables) == 1 else "/".join(tables)
        pattern_roi = rois.get(img_path.name)

        for y0, y1, review in rows:
            swatch = crop_pattern_swatch(img, y0, y1, pattern_roi=pattern_roi)
            if swatch is None:
                continue
            name = f"page{page_num}_row{row_global:03d}.png"
            swatch_path = out_dir / name
            swatch.save(swatch_path)
            count += 1
            candidates.append({
                "page": page_num,
                "row": row_global,
                "table": table_hint,
                "image": name,
                "swatch_path": str(swatch_path.relative_to(ROOT)),
                "needs_review": review,
                "code": "",
                "name": "",
                "pattern_type": "auto",
                "verified": "no",
            })
            row_global += 1

    for c in candidates:
        writer.writerow(c)
    return count


def main() -> int:
    if not TABLE_IMAGES_DIR.exists():
        print(f"[ERROR] {TABLE_IMAGES_DIR} not found. Run read_dz_t_0179_pdf.py first.")
        return 1

    shutil.rmtree(SWATCH_DIR, ignore_errors=True)
    SWATCH_DIR.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "page", "row", "table", "image", "swatch_path",
        "needs_review", "code", "name", "pattern_type", "verified",
    ]
    with open(MANIFEST_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        total = 0
        for page in sorted(PATTERN_PAGES.keys()):
            n = process_page(page, SWATCH_DIR, writer)
            print(f"Page {page}: {n} pattern candidates extracted")
            total += n

    print(f"\nTotal candidates: {total}")
    print(f"Manifest: {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
