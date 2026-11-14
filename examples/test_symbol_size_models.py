#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compare direct-WT and library-bbox-normalized symbol size models.

This is a diagnostic rendering test, not a production renderer change and not
native MapGIS visual acceptance.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from pymapgis import GraphicLibraries, GraphicRenderer
from pymapgis.testing import slib_path

# The first three targets occur in the bundled WT. The remaining cases use a
# controlled 5 mm target to isolate the effect of different library bboxes.
CASES = (
    (1245, 5.0, 5.0, "bundled WT"),
    (1255, 5.0, 5.0, "bundled WT"),
    (1281, 4.0, 4.0, "bundled WT"),
    (238, 5.0, 5.0, "controlled target"),
    (239, 5.0, 5.0, "controlled target"),
    (1894, 5.0, 5.0, "controlled target"),
    (43, 5.0, 5.0, "controlled target"),
)


def symbol_points(symbol):
    """Return sampled geometry points, including circles and parameter arcs."""
    points = []
    for subpath in symbol.subpaths:
        if subpath.circle is not None:
            cx, cy, radius = subpath.circle
            points.extend([
                (cx + radius * math.cos(2 * math.pi * i / 96),
                 cy + radius * math.sin(2 * math.pi * i / 96))
                for i in range(97)
            ])
        elif subpath.arc is not None:
            cx, cy, radius, a0, a1 = subpath.arc
            sweep = (a1 - a0) % 360.0
            points.extend([
                (
                    cx + radius * math.cos(math.radians(a0 + sweep * i / 96)),
                    cy + radius * math.sin(math.radians(a0 + sweep * i / 96)),
                )
                for i in range(97)
            ])
        else:
            points.extend(subpath.points)
    return points


def model_metrics(symbol, target_width, target_height):
    points = symbol_points(symbol)
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    base_width = max(xs) - min(xs)
    base_height = max(ys) - min(ys)
    if base_width <= 0 or base_height <= 0:
        raise ValueError(f"Symbol {symbol.no} has a degenerate base bbox")
    direct_scale = min(target_width, target_height)
    normalized_scale = min(
        target_width / base_width, target_height / base_height
    )
    direct = (base_width * direct_scale, base_height * direct_scale)
    normalized = (base_width * normalized_scale, base_height * normalized_scale)
    if normalized[0] > target_width + 1e-9 or normalized[1] > target_height + 1e-9:
        raise AssertionError("Normalized symbol exceeds its target dimensions")
    if not math.isclose(
        max(normalized[0] / target_width, normalized[1] / target_height),
        1.0,
        rel_tol=1e-9,
    ):
        raise AssertionError("Normalized symbol touches neither target dimension")
    return {
        "base_width_mm": base_width,
        "base_height_mm": base_height,
        "direct_scale": direct_scale,
        "normalized_scale": normalized_scale,
        "direct_width_mm": direct[0],
        "direct_height_mm": direct[1],
        "normalized_width_mm": normalized[0],
        "normalized_height_mm": normalized[1],
        "width_ratio_direct_over_normalized": direct[0] / normalized[0],
        "height_ratio_direct_over_normalized": direct[1] / normalized[1],
    }


def render_comparison(output_dir: Path):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    libraries = GraphicLibraries.from_directory(slib_path())
    renderer = GraphicRenderer(libraries, scale=24000)
    figure = Figure(figsize=(10, 2.35 * len(CASES)))
    FigureCanvasAgg(figure)
    reports = []
    for index, (number, target_width, target_height, target_source) in enumerate(CASES):
        symbol = libraries.subgraph.decode(number)
        if symbol is None:
            raise ValueError(f"Cannot resolve SLIB symbol {number}")
        metrics = model_metrics(symbol, target_width, target_height)
        metrics.update({
            "symbol_no": number,
            "target_width_mm": target_width,
            "target_height_mm": target_height,
            "target_source": target_source,
        })
        reports.append(metrics)
        points = symbol_points(symbol)
        extents = []
        for scale in (metrics["direct_scale"], metrics["normalized_scale"]):
            xs = [point[0] * scale for point in points]
            ys = [point[1] * scale for point in points]
            extents.append((min(xs), min(ys), max(xs), max(ys)))
        xmin = min(item[0] for item in extents)
        ymin = min(item[1] for item in extents)
        xmax = max(item[2] for item in extents)
        ymax = max(item[3] for item in extents)
        x_margin = max((xmax - xmin) * 0.12, 0.2)
        y_margin = max((ymax - ymin) * 0.12, 0.2)
        for column, model in enumerate(("direct", "normalized")):
            ax = figure.add_subplot(len(CASES), 2, index * 2 + column + 1)
            ax.set_aspect("equal")
            ax.axis("off")
            if model == "direct":
                height = target_height
                width = target_width
                color = (0.0, 0.0, 0.0)
            else:
                height = width = metrics["normalized_scale"]
                color = (0.05, 0.25, 0.65)
            ok = renderer._draw_symbol(
                ax, 0.0, 0.0, number, height, width, 0.0, color, 1.0, {},
                pen_width_mm=0.15,
            )
            if not ok:
                raise AssertionError(f"Failed to draw symbol {number}")
            ax.set_xlim(xmin - x_margin, xmax + x_margin)
            ax.set_ylim(ymin - y_margin, ymax + y_margin)
            ax.set_title(
                f"#{number} {model}\n"
                f"{metrics[model + '_width_mm']:.3f} × "
                f"{metrics[model + '_height_mm']:.3f} mm",
                fontsize=10,
            )
    figure.suptitle(
        "SLIB symbol size models: direct WT dimensions vs library-bbox normalization",
        fontsize=13,
        y=0.997,
    )
    figure.subplots_adjust(left=0.03, right=0.97, top=0.955, bottom=0.01, hspace=0.5)
    output_dir.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_dir / "symbol_size_model_comparison.png", dpi=180)
    figure.savefig(output_dir / "symbol_size_model_comparison.svg", format="svg")
    figure.clear()
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/symbol_size_model_test"),
    )
    args = parser.parse_args()
    reports = render_comparison(args.output_dir)
    document = {
        "scope": "Diagnostic model comparison only; not native MapGIS acceptance",
        "production_renderer_modified": False,
        "cases": reports,
    }
    (args.output_dir / "symbol_size_model_report.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# 子图尺寸模型对比测试",
        "",
        "| 子图 | 目标尺寸 mm | 库基准尺寸 mm | 直接模型 mm | 归一化模型 mm |",
        "|---:|---:|---:|---:|---:|",
    ]
    for item in reports:
        lines.append(
            f"| {item['symbol_no']} | {item['target_width_mm']:.3f} × "
            f"{item['target_height_mm']:.3f} | {item['base_width_mm']:.3f} × "
            f"{item['base_height_mm']:.3f} | {item['direct_width_mm']:.3f} × "
            f"{item['direct_height_mm']:.3f} | {item['normalized_width_mm']:.3f} × "
            f"{item['normalized_height_mm']:.3f} |"
        )
    lines.extend([
        "",
        "本测试不修改生产渲染器，也不替代 MapGIS 原生显示验收。",
    ])
    (args.output_dir / "symbol_size_model_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "output_dir": str(args.output_dir),
        "cases": len(reports),
        "production_renderer_modified": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
