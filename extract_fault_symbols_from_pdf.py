#!/usr/bin/env python3
"""读取 DZ/T 0179 PDF，聚焦表22（其他地质要素用色）页面，
提取其中的栅格图片与矢量绘图，用于解析断裂/地质构造线类型与样式。

输出：
- pdf_fault_symbol_images/：表22 相关页面提取的图片
- pdf_fault_drawings/：矢量绘图转存为 SVG/JSON
- fault_symbol_extraction_report.json：页面结构摘要
- fault_symbol_extraction_report.md：可读报告
"""

from __future__ import annotations

import json
from pathlib import Path

import fitz  # PyMuPDF

PDF_PATH = Path("F:/P020250429414585946484.pdf")
ROOT = Path(__file__).parent
IMG_DIR = ROOT / "pdf_fault_symbol_images"
DRAW_DIR = ROOT / "pdf_fault_drawings"
IMG_DIR.mkdir(exist_ok=True)
DRAW_DIR.mkdir(exist_ok=True)

# 表22“其他地质要素用色”主要分布在 PDF 页 34–35（1-based）
TARGET_PAGES = [34, 35]


def hex_color(c: tuple) -> str:
    """将 fitz 颜色元组转为 #RRGGBB。"""
    if not c or len(c) < 3:
        return "#000000"
    return "#" + "".join(f"{int(max(0, min(v, 1)) * 255):02x}" for v in c[:3])


def summarize_drawing(d: dict) -> dict:
    """提取矢量绘图对象的关键属性。"""
    return {
        "type": d.get("type"),
        "items": len(d.get("items", [])),
        "color": hex_color(d.get("color")),
        "fill": hex_color(d.get("fill")),
        "width": d.get("width"),
        "rect": [round(x, 2) for x in d.get("rect", [])],
    }


def main() -> int:
    doc = fitz.open(PDF_PATH)
    print(f"PDF: {PDF_PATH}")
    print(f"Total pages: {doc.page_count}")

    summary: list[dict] = []
    for page_num in TARGET_PAGES:
        if page_num > doc.page_count:
            print(f"[skip] page {page_num} out of range")
            continue
        page = doc.load_page(page_num - 1)

        page_info = {
            "page": page_num,
            "text_len": len(page.get_text()),
            "images": len(page.get_images(full=True)),
            "drawings": len(page.get_drawings()),
        }
        print(f"\nPage {page_num}: {page_info}")

        # 1. 提取栅格图片
        extracted_images: list[dict] = []
        for idx, img in enumerate(page.get_images(full=True), start=1):
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)
            if pix.n > 4:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            filename = IMG_DIR / f"page{page_num}_img{idx}.png"
            pix.save(filename)
            extracted_images.append(
                {
                    "image": str(filename),
                    "width": pix.width,
                    "height": pix.height,
                    "colorspace": pix.n,
                }
            )
            print(f"  saved {filename} ({pix.width}x{pix.height})")

        # 2. 提取矢量绘图
        drawings = page.get_drawings()
        drawing_summaries = [summarize_drawing(d) for d in drawings]
        draw_file = DRAW_DIR / f"page{page_num}_drawings.json"
        with open(draw_file, "w", encoding="utf-8") as f:
            json.dump(
                [{"index": i, **d} for i, d in enumerate(drawings)],
                f,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        print(f"  saved {draw_file} ({len(drawings)} drawings)")

        # 3. 尝试将矢量绘图转为 SVG（便于在浏览器/矢量软件中查看）
        svg = page.get_svg_image(matrix=fitz.Matrix(2, 2))
        svg_file = DRAW_DIR / f"page{page_num}.svg"
        svg_file.write_text(svg, encoding="utf-8")
        print(f"  saved {svg_file}")

        page_info["extracted_images"] = extracted_images
        page_info["drawing_summaries"] = drawing_summaries
        summary.append(page_info)

    # 保存摘要
    report_json = ROOT / "fault_symbol_extraction_report.json"
    with open(report_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {report_json}")

    # Markdown 报告
    md_lines = [
        "# DZ/T 0179 PDF 断裂/构造线符号提取报告\n",
        f"来源：`{PDF_PATH}`\n",
        "说明：DZ/T 0179 以栅格图片形式嵌入色标表，文字不可直接抽取。",
        "本报告聚焦 **表22 其他地质要素用色**（PDF 页 34–35），",
        "提取页面中的栅格图片与矢量绘图，供后续人工/图像分析确认断裂类型与样式。\n",
        "## 页面摘要\n",
        "| 页码 | 文本长度 | 图片数 | 矢量绘图数 |",
        "|------|----------|--------|------------|",
    ]
    for p in summary:
        md_lines.append(
            f"| {p['page']} | {p['text_len']} | {len(p['extracted_images'])} | {p['drawings']} |"
        )

    md_lines.extend(["\n## 提取的图片\n", "| 页码 | 文件 | 尺寸 |", "|------|------|------|"])
    for p in summary:
        for img in p["extracted_images"]:
            md_lines.append(
                f"| {p['page']} | `{Path(img['image']).name}` | {img['width']}×{img['height']} |"
            )

    md_lines.extend(
        [
            "\n## 矢量绘图统计\n",
            "| 页码 | 索引 | 类型 | 子项数 | 描边色 | 填充色 | 线宽 | 包围盒 |",
            "|------|------|------|--------|--------|--------|------|--------|",
        ]
    )
    for p in summary:
        for i, d in enumerate(p["drawing_summaries"]):
            md_lines.append(
                f"| {p['page']} | {i} | {d['type']} | {d['items']} | {d['color']} | "
                f"{d['fill']} | {d['width']} | {d['rect']} |"
            )

    md_lines.extend(
        [
            "\n## 下一步分析建议\n",
            "1. 在 `pdf_fault_symbol_images/` 中查看页面截图，定位表22的断裂/构造线图例区域；\n",
            "2. 在 `pdf_fault_drawings/` 中查看矢量绘图 JSON/SVG，提取线条样式（实线/虚线/点划线）、颜色、宽度；\n",
            "3. 结合 `geological_fault_rendering_scheme.md` 中的暂定类型代码，建立 PDF 图例到数据字段的对应关系；\n",
            "4. 确认后更新 `fault_rendering_styles.json` 中的 `type_map`。\n",
        ]
    )

    report_md = ROOT / "fault_symbol_extraction_report.md"
    report_md.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Saved: {report_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
