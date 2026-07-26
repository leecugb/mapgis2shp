#!/usr/bin/env python3
"""对 pdf_fault_symbol_images/ 中的表22页面图片进行图像分析，
尝试检测每一行的构造线样式（实线/虚线/点划线/双线等），并输出结构化摘要。

说明：
- DZ/T 0179 的图例为栅格图片，文字部分需 OCR/人工判读；
- 本脚本侧重“线型样式”自动识别，为后续人工建立“代码-样式”映射提供素材。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

ROOT = Path(__file__).parent
IMG_DIR = ROOT / "pdf_fault_symbol_images"
OUT_DIR = ROOT / "pdf_fault_symbol_rows"
OUT_DIR.mkdir(exist_ok=True)


def detect_horizontal_lines(arr: np.ndarray, y: int, x1: int, x2: int) -> Dict[str, any]:
    """在指定行区域检测水平线段的样式特征。"""
    region = arr[y - 2 : y + 3, x1:x2]
    gray = region.mean(axis=2) if region.ndim == 3 else region
    proj = gray.mean(axis=0)
    threshold = proj.max() * 0.7 if proj.max() > 0 else 200
    binary = (proj < threshold).astype(int)

    # 统计黑白交替次数，用于区分实线/虚线/点划线
    runs = []
    current = binary[0]
    count = 1
    for v in binary[1:]:
        if v == current:
            count += 1
        else:
            runs.append((int(current), count))
            current = v
            count = 1
    runs.append((int(current), count))

    ink_runs = [c for on, c in runs if on == 1]
    gap_runs = [c for on, c in runs if on == 0]

    if not ink_runs:
        return {"style": "none", "ink_ratio": 0.0, "transitions": 0}

    avg_ink = np.mean(ink_runs)
    avg_gap = np.mean(gap_runs) if gap_runs else 0
    transitions = len(runs) - 1
    ink_ratio = sum(ink_runs) / (sum(ink_runs) + sum(gap_runs))

    # 简单启发式分类
    if transitions <= 2 and ink_ratio > 0.85:
        style = "solid"
    elif transitions >= 6 and avg_gap > avg_ink * 1.5:
        style = "dashed"
    elif transitions >= 10 and avg_ink < avg_gap * 0.6:
        style = "dotted"
    elif transitions >= 8:
        style = "dash_dot"
    else:
        style = "mixed"

    return {
        "style": style,
        "ink_ratio": round(ink_ratio, 3),
        "transitions": transitions,
        "avg_ink_px": round(float(avg_ink), 1),
        "avg_gap_px": round(float(avg_gap), 1),
    }


def find_table_rows(img: Image.Image, min_row_height: int = 20) -> List[Tuple[int, int]]:
    """通过水平投影找到表格行边界。"""
    arr = np.array(img.convert("RGB"))
    gray = arr.mean(axis=2)
    h = gray.shape[0]

    # 水平投影：每行像素的“非白”程度
    vproj = (gray < 250).mean(axis=1)

    # 用简单阈值找有内容的行段
    active = vproj > 0.03
    rows: List[Tuple[int, int]] = []
    in_row = False
    start = 0
    for y in range(h):
        if active[y] and not in_row:
            start = y
            in_row = True
        elif not active[y] and in_row:
            if y - start >= min_row_height:
                rows.append((start, y))
            in_row = False
    if in_row and h - start >= min_row_height:
        rows.append((start, h))
    return rows


def analyze_image(path: Path) -> Dict:
    """分析单张页面图片，返回检测到的行及线型。"""
    img = Image.open(path).convert("RGB")
    arr = np.array(img)
    h, w = arr.shape[:2]

    rows = find_table_rows(img)
    row_results: List[Dict] = []

    for i, (y1, y2) in enumerate(rows):
        # 裁剪行区域并保存
        row_img = img.crop((0, y1, w, y2))
        row_file = OUT_DIR / f"{path.stem}_row{i:03d}.png"
        row_img.save(row_file)

        # 在行的左半部分（符号区）检测水平线
        mid_y = (y1 + y2) // 2
        sym_x1 = int(w * 0.05)
        sym_x2 = int(w * 0.45)
        line_info = detect_horizontal_lines(arr, mid_y, sym_x1, sym_x2)

        row_results.append(
            {
                "row_index": i,
                "y_range": (int(y1), int(y2)),
                "crop": str(row_file),
                "symbol_zone_line": line_info,
            }
        )

    return {
        "file": str(path),
        "size": (w, h),
        "rows": row_results,
    }


def main() -> int:
    images = sorted(IMG_DIR.glob("page*_img*.png"))
    if not images:
        print(f"[error] no images found in {IMG_DIR}")
        return 1

    all_results: List[Dict] = []
    csv_rows: List[Dict] = []

    for path in images:
        print(f"Analyzing {path.name}...")
        result = analyze_image(path)
        all_results.append(result)

        for r in result["rows"]:
            csv_rows.append(
                {
                    "page_image": path.name,
                    "row_index": r["row_index"],
                    "y_top": r["y_range"][0],
                    "y_bottom": r["y_range"][1],
                    "detected_style": r["symbol_zone_line"]["style"],
                    "ink_ratio": r["symbol_zone_line"]["ink_ratio"],
                    "transitions": r["symbol_zone_line"]["transitions"],
                    "crop_file": Path(r["crop"]).name,
                }
            )

    # JSON 报告
    report_json = ROOT / "fault_symbol_image_analysis.json"
    with open(report_json, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {report_json}")

    # CSV 摘要
    csv_path = ROOT / "fault_symbol_image_analysis.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "page_image", "row_index", "y_top", "y_bottom",
                "detected_style", "ink_ratio", "transitions", "crop_file",
            ],
        )
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"Saved: {csv_path}")

    # Markdown 报告
    md_lines = [
        "# 表22 断裂/构造线符号图像分析结果\n",
        "说明：本报告对 DZ/T 0179 PDF 页 34–35（表22 其他地质要素用色）提取的图片",
        "进行自动行分割与线型检测。**文字内容未做 OCR，需人工对照 crop 图片判读。**\n",
        "| 页面图片 | 行号 | 纵坐标范围 | 检测线型 | 墨迹占比 | 黑白过渡 | 裁剪文件 |",
        "|----------|------|------------|----------|----------|----------|----------|",
    ]
    for row in csv_rows:
        md_lines.append(
            f"| {row['page_image']} | {row['row_index']} | {row['y_top']}–{row['y_bottom']} | "
            f"`{row['detected_style']}` | {row['ink_ratio']} | {row['transitions']} | "
            f"`{row['crop_file']}` |"
        )

    md_lines.extend(
        [
            "\n## 线型说明\n",
            "- `solid`：实线\n",
            "- `dashed`：虚线（长间隔）\n",
            "- `dotted`：点线\n",
            "- `dash_dot`：点划线\n",
            "- `mixed`：混合/复杂图案\n",
            "- `none`：未检测到明显水平线\n",
            "\n## 下一步\n",
            "1. 人工查看 `pdf_fault_symbol_rows/` 中的裁剪图片；\n",
            "2. 将每一行的中文名称/代码与检测到的线型对应；\n",
            "3. 更新 `fault_rendering_styles.json` 中的 `type_map`。\n",
        ]
    )

    md_path = ROOT / "fault_symbol_image_analysis.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Saved: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
