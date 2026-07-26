#!/usr/bin/env python3
"""对 extract_fill_patterns_from_pdf.py 提取的花纹候选进行分类并生成无缝瓦片。

处理流程：
1. 读取 data/pattern_swatches/pattern_manifest.csv。
2. 对每个候选裁剪中央花纹区，去除表格边框和可能的文字带。
3. 通过 FFT / 梯度方向直方图判断花纹类型：
   - hatch：有明显主导方向的线状纹理
   - symbol_tiled：点阵/网格状纹理
   - image：复杂或不规则纹理（保留原始栅格瓦片）
4. 生成 32×32 px（或 64×64 px）无缝 PNG 瓦片到 data/patterns/。
5. 更新 manifest 的 pattern_type、tile_path、tile_size 等字段。

注意：
- 自动分类仅作初判；最终 pattern_type 需人工在 manifest 中确认。
- 未填写 code 的条目不会进入最终 IR。
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
RAW_DIR = ROOT / "data" / "pattern_swatches" / "raw"
PATTERN_DIR = ROOT / "data" / "patterns"
MANIFEST_PATH = ROOT / "data" / "pattern_swatches" / "pattern_manifest.csv"
TILE_SIZE = 32


def crop_center(img: Image.Image, margin_ratio: float = 0.15) -> Image.Image:
    """裁剪图像中央区域，去除四周可能的边框/文字。"""
    w, h = img.size
    left = int(w * margin_ratio)
    top = int(h * margin_ratio)
    right = int(w * (1 - margin_ratio))
    bottom = int(h * (1 - margin_ratio))
    if right - left < 8 or bottom - top < 8:
        return img
    return img.crop((left, top, right, bottom))


def dominant_orientation_energy(gray: np.ndarray) -> Tuple[Optional[float], float]:
    """通过 FFT 返回主导方向角度（度）和能量比。能量比低表示无明显方向。"""
    h, w = gray.shape
    # 加汉宁窗减少边缘伪影
    win_y = np.hanning(h).reshape(-1, 1)
    win_x = np.hanning(w).reshape(1, -1)
    windowed = gray.astype(float) * win_y * win_x
    f = np.fft.fftshift(np.fft.fft2(windowed))
    mag = np.abs(f)

    # 极坐标汇总
    cy, cx = h // 2, w // 2
    max_r = min(cy, cx) // 2
    if max_r < 4:
        return None, 0.0

    # 按角度汇总能量（0-180 度，因为线方向有 180° 周期性）
    angles = np.linspace(0, 180, 180, endpoint=False)
    energies = []
    for deg in angles:
        rad = np.radians(deg)
        total = 0.0
        count = 0
        for r in range(2, max_r):
            dy = int(r * np.sin(rad))
            dx = int(r * np.cos(rad))
            y, x = cy + dy, cx + dx
            if 0 <= y < h and 0 <= x < w:
                total += mag[y, x]
                count += 1
        energies.append(total / count if count else 0)
    energies = np.array(energies)
    peak = float(energies.max())
    mean = float(energies.mean())
    if mean <= 0:
        return None, 0.0
    ratio = peak / mean
    peak_angle = float(angles[energies.argmax()])
    return peak_angle, ratio


def classify_pattern(img: Image.Image) -> Tuple[str, Optional[str], Dict[str, Any]]:
    """返回 (pattern_type, hatch_char, details)。"""
    center = crop_center(img)
    arr = np.array(center.convert("L"))

    # 空白或近似纯色 → image（可能是色块或文字区）
    std = float(arr.std())
    if std < 8:
        return "image", None, {"reason": "low_variance", "std": std}

    angle, ratio = dominant_orientation_energy(arr)
    details = {"std": std, "dominant_angle": angle, "energy_ratio": ratio}

    # 能量比高且角度明确 → hatch
    if ratio > 2.5 and angle is not None:
        # 把角度映射到 matplotlib hatch 字符
        # 0°≈水平, 90°≈垂直; 实际线条垂直于 FFT 峰值方向，这里简化为角度映射
        norm_angle = angle % 180
        if norm_angle < 22.5 or norm_angle >= 157.5:
            hatch = "-"  # 水平线
        elif 22.5 <= norm_angle < 67.5:
            hatch = "/"  # 45°（近似）
        elif 67.5 <= norm_angle < 112.5:
            hatch = "|"  # 垂直线
        else:
            hatch = "\\"  # 135°（近似）
        return "hatch", hatch, details

    # 点阵/网格：通过局部二值化后连通域大小和密度判断
    binary = arr < np.percentile(arr, 50)
    labeled, num_features = _label(binary)
    if num_features >= 3:
        sizes = np.bincount(labeled.ravel())[1:]
        if len(sizes):
            median_size = float(np.median(sizes))
            density = float(binary.sum()) / binary.size
            details["num_components"] = int(num_features)
            details["median_component_size"] = median_size
            details["density"] = density
            # 小而分散的组件 → symbol_tiled
            if median_size <= 30 and 0.05 < density < 0.6:
                return "symbol_tiled", None, details

    return "image", None, details


def _label(binary: np.ndarray) -> Tuple[np.ndarray, int]:
    """简单的四连通二值图像连通域标记（scipy 不可用时回退）。"""
    try:
        from scipy.ndimage import label
        return label(binary)
    except Exception:
        pass

    h, w = binary.shape
    labels = np.zeros_like(binary, dtype=int)
    next_label = 1
    for y in range(h):
        for x in range(w):
            if not binary[y, x] or labels[y, x] != 0:
                continue
            # BFS
            stack = [(y, x)]
            labels[y, x] = next_label
            while stack:
                cy, cx = stack.pop()
                for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and binary[ny, nx] and labels[ny, nx] == 0:
                        labels[ny, nx] = next_label
                        stack.append((ny, nx))
            next_label += 1
    return labels, next_label - 1


def make_seamless_tile(img: Image.Image, size: int = TILE_SIZE) -> Image.Image:
    """把任意尺寸的花纹图归一化为正方形无缝瓦片。

    策略：
    - 先裁剪中央区域，缩放到 size×size。
    - 用淡入淡出（fade）处理边缘以减少接缝感。
    """
    w, h = img.size
    # 取较短边做正方形裁剪
    min_side = min(w, h)
    left = (w - min_side) // 2
    top = (h - min_side) // 2
    square = img.crop((left, top, left + min_side, top + min_side))
    tile = square.resize((size, size), Image.Resampling.LANCZOS)

    # 边缘羽化：让瓦片在平铺时减少硬边
    arr = np.array(tile).astype(float)
    if len(arr.shape) == 3 and arr.shape[2] == 4:
        # 保持 alpha
        rgb = arr[:, :, :3]
        alpha = arr[:, :, 3:4]
    else:
        rgb = arr
        alpha = None

    h, w = rgb.shape[:2]
    fade = 4
    if fade < min(h, w) // 4:
        # 水平/垂直线性渐变权重
        y_weight = np.ones((h, 1))
        x_weight = np.ones((1, w))
        y_weight[:fade, 0] = np.linspace(0, 1, fade)
        y_weight[-fade:, 0] = np.linspace(1, 0, fade)
        x_weight[0, :fade] = np.linspace(0, 1, fade)
        x_weight[0, -fade:] = np.linspace(1, 0, fade)
        weight = y_weight * x_weight
        weight = weight.reshape(h, w, 1)
        rgb = rgb * weight + 255 * (1 - weight)

    out = np.clip(rgb, 0, 255).astype(np.uint8)
    if alpha is not None:
        out = np.concatenate([out, alpha.astype(np.uint8)], axis=2)
    return Image.fromarray(out)


def main() -> int:
    if not MANIFEST_PATH.exists():
        print(f"[ERROR] {MANIFEST_PATH} not found. Run extract_fill_patterns_from_pdf.py first.")
        return 1

    shutil.rmtree(PATTERN_DIR, ignore_errors=True)
    PATTERN_DIR.mkdir(parents=True, exist_ok=True)

    with open(MANIFEST_PATH, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    out_rows: List[Dict[str, str]] = []
    stats = {"hatch": 0, "symbol_tiled": 0, "image": 0}

    for row in rows:
        img_path = ROOT / row["swatch_path"]
        if not img_path.exists():
            continue
        try:
            img = Image.open(img_path)
        except Exception:
            continue

        ptype, hatch, details = classify_pattern(img)
        stats[ptype] = stats.get(ptype, 0) + 1

        tile = make_seamless_tile(img, size=TILE_SIZE)
        tile_name = f"{Path(row['image']).stem}_tile32.png"
        tile_path = PATTERN_DIR / tile_name
        tile.save(tile_path)

        row["pattern_type"] = ptype
        row["hatch_char"] = hatch if hatch else ""
        row["tile_path"] = str(tile_path.relative_to(ROOT))
        row["tile_size"] = str(TILE_SIZE)
        row["details"] = json.dumps(details, ensure_ascii=False)
        out_rows.append(row)

    fieldnames = list(out_rows[0].keys()) if out_rows else []
    with open(MANIFEST_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Classified {len(out_rows)} pattern candidates:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"Tiles saved to: {PATTERN_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
