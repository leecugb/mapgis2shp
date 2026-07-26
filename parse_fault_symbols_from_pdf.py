#!/usr/bin/env python3
"""使用 RapidOCR 识别 pdf_fault_symbol_rows/ 中表22相关行的文字，
生成 DZ/T 0179 断裂/构造线符号解析表。
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Dict, List

import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

ROOT = Path(__file__).parent
ROW_DIR = ROOT / "pdf_fault_symbol_rows"
OUT_JSON = ROOT / "dz_t_0179_fault_symbols.json"
OUT_CSV = ROOT / "dz_t_0179_fault_symbols.csv"
OUT_MD = ROOT / "dz_t_0179_fault_symbols.md"

# 只处理表22（其他地质要素用色）所在页面：page34_img2 与 page35_img1
TARGET_PREFIXES = ("page34_img2", "page35_img1")

ocr = RapidOCR()


def ocr_image(path: Path) -> str:
    img = Image.open(path).convert("RGB")
    arr = np.array(img)
    result, _ = ocr(arr)
    if not result:
        return ""
    texts = [line[1] for line in result]
    return " ".join(texts)


def extract_rgb(text: str) -> Dict[str, int]:
    """从 OCR 文本中提取 R/G/B 数值。"""
    # 常见 OCR 模式：R123 G456 B789 或 123 456 789
    patterns = [
        r"R\s*(\d{1,3})\s*G\s*(\d{1,3})\s*B\s*(\d{1,3})",
        r"R(\d{1,3})G(\d{1,3})B(\d{1,3})",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return {"R": int(m.group(1)), "G": int(m.group(2)), "B": int(m.group(3))}

    # 兜底：连续三个 0-255 整数
    nums = [int(n) for n in re.findall(r"\b(\d{1,3})\b", text) if 0 <= int(n) <= 255]
    if len(nums) >= 3:
        return {"R": nums[0], "G": nums[1], "B": nums[2]}
    return {}


def clean_name(text: str) -> str:
    """提取行左侧的中文名称，去掉色值数字。"""
    # 去掉 RGB 标记与数字
    text = re.sub(r"R\s*\d+\s*G\s*\d+\s*B\s*\d+", "", text)
    text = re.sub(r"\b\d{1,3}\b", "", text)
    text = text.replace("色值", "").replace("示例", "").strip()
    return text


def main() -> int:
    rows: List[Dict] = []
    for path in sorted(ROW_DIR.glob("*.png")):
        if not any(path.name.startswith(p) for p in TARGET_PREFIXES):
            continue
        print(f"OCR {path.name}...")
        text = ocr_image(path)
        rgb = extract_rgb(text)
        name = clean_name(text)
        rows.append(
            {
                "source_image": path.name,
                "raw_ocr": text,
                "name": name,
                "R": rgb.get("R"),
                "G": rgb.get("G"),
                "B": rgb.get("B"),
            }
        )

    # 人工校正映射：基于对 page34_img2 / page35_img1 的视觉判读
    # 顺序与图片自上而下一致
    manual_correction = [
        {"name": "实测、推测地质界线", "symbol": "实线/虚线曲线", "category": "boundary"},
        {"name": "角度不整合、平行不整合、岩相界线", "symbol": "实线+虚线/点线", "category": "unconformity"},
        {"name": "实测正断层、实测逆断层", "symbol": "实线+齿/三角齿", "category": "fault"},
        {"name": "实测平推断层", "symbol": "实线+半箭头", "category": "fault"},
        {"name": "实测性质不明断层", "symbol": "实线", "category": "fault"},
        {"name": "推测性质不明断层", "symbol": "长虚线", "category": "fault"},
        {"name": "实测冲断层", "symbol": "实线+三角齿", "category": "fault"},
        {"name": "韧性剪切带", "symbol": "红色平行双线", "category": "shear_zone"},
        {"name": "实测活动断层", "symbol": "实线+双箭头", "category": "fault"},
        {"name": "推测活动断层", "symbol": "长虚线+双箭头", "category": "fault"},
        {"name": "隐伏或物探推测断层", "symbol": "长虚线+点", "category": "fault"},
        {"name": "航卫片解译断层", "symbol": "点划线", "category": "fault"},
        {"name": "层理、片理、片麻理产状", "symbol": "产状符号", "category": "attitude"},
        {"name": "劈理、裂隙、面理产状", "symbol": "产状符号", "category": "attitude"},
        {"name": "脆韧性剪切带", "symbol": "红色平行双线", "category": "shear_zone"},
        {"name": "实测逆冲推覆断层", "symbol": "实线+三角齿", "category": "fault"},
        {"name": "推测逆冲推覆断层", "symbol": "虚线+三角齿", "category": "fault"},
        {"name": "飞来峰构造", "symbol": "闭合曲线+齿", "category": "structure"},
        {"name": "构造窗", "symbol": "闭合曲线+齿", "category": "structure"},
    ]

    # 合并 OCR 结果与人工校正
    records: List[Dict] = []
    for i, row in enumerate(rows):
        corr = manual_correction[i] if i < len(manual_correction) else {"name": "", "symbol": "", "category": ""}
        records.append(
            {
                "order": i + 1,
                "source_image": row["source_image"],
                "name": corr["name"] or row["name"],
                "symbol": corr["symbol"],
                "category": corr["category"],
                "R": row["R"],
                "G": row["G"],
                "B": row["B"],
                "raw_ocr": row["raw_ocr"],
            }
        )

    # JSON
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {OUT_JSON}")

    # CSV
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["order", "name", "symbol", "category", "R", "G", "B", "source_image"],
        )
        writer.writeheader()
        for r in records:
            writer.writerow(
                {
                    "order": r["order"],
                    "name": r["name"],
                    "symbol": r["symbol"],
                    "category": r["category"],
                    "R": r["R"],
                    "G": r["G"],
                    "B": r["B"],
                    "source_image": r["source_image"],
                }
            )
    print(f"Saved: {OUT_CSV}")

    # Markdown
    lines = [
        "# DZ/T 0179 表22 断裂/构造线符号解析表\n",
        "来源：PDF 页 34–35（表22 其他地质要素用色）\n",
        "| 序号 | 名称 | 符号样式 | 类别 | R | G | B | 来源裁剪 |",
        "|------|------|----------|------|---|---|---|----------|",
    ]
    for r in records:
        rgb = f"{r['R'] or '-'} | {r['G'] or '-'} | {r['B'] or '-'}"
        lines.append(
            f"| {r['order']} | {r['name']} | {r['symbol']} | {r['category']} | {rgb} | `{r['source_image']}` |"
        )

    lines.extend(
        [
            "\n## 与项目数据的对应建议\n",
            "| 图例名称 | 建议对应数据字段/代码 | 备注 |",
            "|----------|----------------------|------|",
            "| 实测正断层 | `LDZOFBA003.WL` `GZEEB=05`（暂定） | 图例确认后替换 |",
            "| 实测逆断层 | `LDZOFBA003.WL` `GZEEB=31`（暂定） | 图例确认后替换 |",
            "| 实测冲断层 / 逆冲推覆断层 | `LDZOFBA003.WL` `GZEEB=31`（暂定） | 三角齿符号 |",
            "| 实测平推断层 | 待确认 | 半箭头符号 |",
            "| 实测性质不明断层 | `LDZOFBA003.WL` `GZEEB=01/07` | 仅用实线 |",
            "| 推测性质不明断层 | `LDZOFBA003.WL` `GZEEB=04` | 长虚线 |",
            "| 韧性/脆韧性剪切带 | `LDZOFBA003.WL` `GZEEB=41/28` | 红色/黑色双线 |",
            "| 实测活动断层 | `LDZOFBA003.WL` `GZEEB=18/16` | 双箭头 |",
            "| 隐伏/物探推测断层 | `LYGREBA001.WL` `GZEEBM=05/GZEGD=05` | 点线/虚线 |",
            "| 航卫片解译断层 | `LYGREBA001.WL` `GZEEBM=01,02/GZEGD=04,03` | 点划线 |",
        ]
    )

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved: {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
