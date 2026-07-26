#!/usr/bin/env python3
"""从 DZ/T 0179 PDF 的表2（正式地层单位用色）栅格图片中提取“阶”一级的颜色。

处理策略：
1. 对每一页选取面积最大的表格图片。
2. 用垂直投影找到右侧的色块列（stage 列 + 备选色列）。
3. 在 stage 列内按颜色变化分割出行。
4. 对每行：
   - 用 RapidOCR 识别阶代号（如 Qh、Qh1-2、Qp3 等）。
   - 用中位数/众数采样 stage 列的推荐色以及备选色列颜色。
5. 输出原始结果，供人工校核后使用。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from rapidocr_onnxruntime import RapidOCR
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

ROOT = Path(__file__).parent
IMG_DIR = ROOT / "pdf_table_images"
OUT_JSON = ROOT / "dz_t_0179_stage_colors_raw.json"
OUT_CSV = ROOT / "dz_t_0179_stage_colors_raw.csv"

PAGES = list(range(14, 21))  # 表2 分布在 PDF 页 14-20

ocr_engine = RapidOCR()


def choose_table_image(page: int) -> Path | None:
    """同一页可能有多个图片，选面积最大的作为表格主体。"""
    candidates = sorted(IMG_DIR.glob(f"page{page}_img*.png"), key=lambda p: p.stat().st_size, reverse=True)
    if not candidates:
        return None
    # 用尺寸面积再确认一次
    best = max(candidates, key=lambda p: Image.open(p).size[0] * Image.open(p).size[1])
    return best


def detect_columns(arr: np.ndarray) -> tuple[list[tuple[int, int]], tuple[int, int]]:
    """检测色块列，返回 (色块列列表, 左侧标签列)。"""
    h, w, _ = arr.shape
    nonwhite = np.any(arr < 245, axis=2)
    vproj = nonwhite.mean(axis=0)
    active = vproj > 0.18
    diff = np.diff(active.astype(int))
    starts = (np.where(diff == 1)[0] + 1).tolist()
    ends = (np.where(diff == -1)[0] + 1).tolist()
    if active[0]:
        starts.insert(0, 0)
    if active[-1]:
        ends.append(w)
    segments = [(int(s), int(e)) for s, e in zip(starts, ends)]

    # 右侧色块列：x > 250，宽度 > 80
    color_cols = [(s, e) for s, e in segments if s > 250 and (e - s) > 80]
    # 左侧标签列：最左边的宽段
    label_segs = [(s, e) for s, e in segments if e < color_cols[0][0] and (e - s) > 50]
    label_col = label_segs[0] if label_segs else (0, color_cols[0][0])
    return color_cols, label_col


def detect_row_boundaries(arr: np.ndarray, col: tuple[int, int]) -> list[int]:
    """根据 stage 列的颜色变化检测行边界。"""
    h = arr.shape[0]
    region = arr[:, col[0]:col[1], :]
    med = np.median(region, axis=1)
    smooth = gaussian_filter1d(med.astype(float), sigma=2, axis=0)
    diff_y = np.abs(np.diff(smooth, axis=0)).sum(axis=1)

    # 头部/表头通常在前 80px 以内，忽略
    header_end = 80
    peaks, _ = find_peaks(diff_y, distance=15, prominence=8)
    valid = peaks[peaks > header_end].tolist()

    # 表格内容起始：第一个颜色明显非白的行
    first_y_arr = np.where(np.any(med < 252, axis=1))[0]
    first_y = int(first_y_arr[0]) if first_y_arr.size else header_end
    first_y = max(first_y, header_end)

    boundaries = [first_y] + sorted(valid) + [h]
    boundaries = sorted(set(boundaries))
    return boundaries


def sample_color(arr: np.ndarray, y1: int, y2: int, x1: int, x2: int) -> list[int]:
    """采样色块颜色，剔除白/黑文字像素后取中位数。"""
    block = arr[y1:y2, x1:x2, :]
    gray = block.mean(axis=2)
    mask = (gray < 250) & (gray > 60)
    if mask.sum() == 0:
        return np.median(block, axis=(0, 1)).astype(int).tolist()
    return np.median(block[mask], axis=0).astype(int).tolist()


def ocr_crop(img: Image.Image, box: tuple[int, int, int, int]) -> list[str]:
    crop = img.crop(box)
    arr = np.array(crop)
    result, _ = ocr_engine(arr)
    if not result:
        return []
    return [line[1] for line in result]


def main() -> int:
    all_rows: list[dict] = []
    for page in PAGES:
        img_path = choose_table_image(page)
        if img_path is None:
            print(f"[skip] page {page}: no image")
            continue
        print(f"Processing page {page}: {img_path}")
        img = Image.open(img_path).convert("RGB")
        arr = np.array(img)

        try:
            color_cols, label_col = detect_columns(arr)
        except Exception as exc:
            print(f"[warn] page {page}: column detection failed: {exc}")
            continue

        if len(color_cols) < 2:
            print(f"[warn] page {page}: only {len(color_cols)} color columns")
            continue

        stage_col = color_cols[0]
        alt_cols = color_cols[1:]
        boundaries = detect_row_boundaries(arr, stage_col)

        for i in range(len(boundaries) - 1):
            y1, y2 = boundaries[i], boundaries[i + 1]
            if y2 - y1 < 12:
                continue

            rec_color = sample_color(arr, y1, y2, stage_col[0], stage_col[1])
            alt_colors = [
                sample_color(arr, y1, y2, c[0], c[1]) for c in alt_cols
            ]

            stage_texts = ocr_crop(img, (stage_col[0], y1, stage_col[1], y2))
            label_texts = ocr_crop(img, (label_col[0], y1, label_col[1], y2))

            # 过滤掉明显是分隔/空白的行：stage 列采样到灰色或白色
            if all(c > 245 for c in rec_color) or all(c < 100 for c in rec_color):
                continue

            all_rows.append(
                {
                    "page": page,
                    "row": i,
                    "y": (int(y1), int(y2)),
                    "stage_ocr": " ".join(stage_texts),
                    "label_ocr": " ".join(label_texts),
                    "recommended_rgb": rec_color,
                    "alternative_rgbs": alt_colors,
                }
            )

    # 保存 JSON
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_rows, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {OUT_JSON} ({len(all_rows)} rows)")

    # 保存 CSV
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["page", "row", "stage_ocr", "label_ocr", "R", "G", "B", "Alt1_R", "Alt1_G", "Alt1_B"]
        )
        for r in all_rows:
            rec = r["recommended_rgb"]
            alt1 = r["alternative_rgbs"][0] if r["alternative_rgbs"] else ["", "", ""]
            writer.writerow(
                [
                    r["page"],
                    r["row"],
                    r["stage_ocr"],
                    r["label_ocr"],
                    rec[0],
                    rec[1],
                    rec[2],
                    alt1[0],
                    alt1[1],
                    alt1[2],
                ]
            )
    print(f"Saved: {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
