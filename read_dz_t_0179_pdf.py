#!/usr/bin/env python3
"""使用 Python 读取 DZ/T 0179 地质图用色标准 PDF。

说明：
- 该 PDF 的色标表以栅格图片形式嵌入（page.get_text 返回空）。
- 本脚本用 PyMuPDF 提取每一页的元信息，并把含表的页面（14–36）中的
  表格图片单独保存到 pdf_table_images/，便于后续 OCR / 人工校色。
- 颜色值最终来自对表格图片中色块的采样，整理后写入 dz_t_0179_colors.json。
"""

from __future__ import annotations

import json
from pathlib import Path

import fitz  # PyMuPDF

PDF_PATH = Path("/media/lee/KINGSTON/P020250429414585946484.pdf")
ROOT = Path(__file__).parent
OUT_DIR = ROOT / "pdf_table_images"
OUT_DIR.mkdir(exist_ok=True)

# 根据 PDF 目录/页眉整理的“页码 -> 表名”映射（1-based）
PAGE_TO_TABLE: dict[int, str] = {
    14: "表2 正式地层单位用色（第1页）",
    15: "表2 正式地层单位用色（续）",
    16: "表2 正式地层单位用色（续）",
    17: "表2 正式地层单位用色（续）",
    18: "表2 正式地层单位用色（续）",
    19: "表2 正式地层单位用色（续）",
    20: "表2 正式地层单位用色（续）+ 表3 跨时代地层单位用色",
    21: "表3 跨时代地层单位用色（续）+ 表4 非正式地层单位用色",
    22: "表5 第四系成因类型花纹及用色",
    23: "表5 第四系成因类型花纹及用色（续）+ 表6 新生代—古生代酸性—中酸性侵入岩用色",
    24: "表6 新生代—古生代酸性—中酸性侵入岩用色（续）",
    25: "表6 新生代—古生代酸性—中酸性侵入岩用色（续）+ 表7 元古宙酸性—中酸性侵入岩用色",
    26: "表7 元古宙酸性—中酸性侵入岩用色（续）+ 表8 太古宙—冥古宙酸性—中酸性侵入岩用色",
    27: "表9 中性侵入岩用色",
    28: "表9 中性侵入岩用色（续）+ 表10 基性侵入岩用色",
    29: "表10 基性侵入岩用色（续）+ 表11 超基性侵入岩用色 + 表12 碱性侵入岩用色",
    30: "表12 碱性侵入岩用色（续）+ 表13 煌斑岩、碳酸岩用色",
    31: "表13 煌斑岩、碳酸岩用色（续）+ 表14 脉岩用色 + 表15 侵入岩填充花纹用色",
    32: "表15 侵入岩填充花纹用色（续）+ 表16 新生代以前火山岩用色 + 表17 新生代火山岩用色",
    33: "表18 潜火山岩用色 + 表19 变质表壳岩用色 + 表20 变质深成岩用色 + 表21 特殊岩石单位用色",
    34: "表21 特殊岩石单位用色（续）+ 表22 其他地质要素用色",
    35: "表22 其他地质要素用色（续）+ 表23 地理要素用色 + 表24 网纹用色",
    36: "表24 网纹用色（续）",
}


def main() -> int:
    doc = fitz.open(PDF_PATH)
    print(f"PDF: {PDF_PATH}")
    print(f"Total pages: {doc.page_count}\n")

    summary: list[dict] = []
    for page_num in range(1, doc.page_count + 1):
        page = doc.load_page(page_num - 1)
        text_len = len(page.get_text())
        img_count = len(page.get_images(full=True))
        drawing_count = len(page.get_drawings())
        summary.append(
            {
                "page": page_num,
                "text_len": text_len,
                "images": img_count,
                "drawings": drawing_count,
                "table": PAGE_TO_TABLE.get(page_num),
            }
        )

    # 保存每页结构摘要
    with open(ROOT / "pdf_page_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("Saved: pdf_page_summary.json")

    # 提取含表页面的栅格图片
    extracted: list[dict] = []
    for page_num, table_name in PAGE_TO_TABLE.items():
        page = doc.load_page(page_num - 1)
        images = page.get_images(full=True)
        for idx, img in enumerate(images, start=1):
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)
            if pix.n > 4:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            filename = OUT_DIR / f"page{page_num}_img{idx}.png"
            pix.save(filename)
            extracted.append(
                {
                    "page": page_num,
                    "table": table_name,
                    "image": str(filename),
                    "width": pix.width,
                    "height": pix.height,
                }
            )
            print(f"  saved {filename} ({pix.width}x{pix.height})")

    with open(ROOT / "pdf_extracted_tables.json", "w", encoding="utf-8") as f:
        json.dump(extracted, f, ensure_ascii=False, indent=2)
    print("\nSaved: pdf_extracted_tables.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
