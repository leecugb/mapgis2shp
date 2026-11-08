"""Verify the manuscript Quickstart against an isolated published wheel."""
from pathlib import Path
from tempfile import TemporaryDirectory
import argparse
import json
import sys

parser = argparse.ArgumentParser()
parser.add_argument("package_dir", type=Path)
parser.add_argument("--dpi", type=int, default=80)
args = parser.parse_args()
sys.path.insert(0, str(args.package_dir))

import pymapgis  # noqa: E402
from pymapgis import GraphicLibraries, GraphicRenderer, Reader  # noqa: E402
from pymapgis.testing import jwd_path, slib_path  # noqa: E402

print("PUBLISHED_PACKAGE", pymapgis.__file__)
paths = sorted(jwd_path().iterdir())
print("PUBLISHED_FIXTURE_NAMES", [path.name for path in paths])
layers = []
for path in paths:
    if path.suffix.lower() == ".wp~":
        layers.append(Reader(str(path), read_graphic_params=True).geodataframe)
    else:
        layers.append(path)

renderer = GraphicRenderer(
    GraphicLibraries.from_directory(slib_path()),
    scale=250000,
    native_text_layout=True,
    polygon_labels=True,
    polygon_label_fontsize=5.0,
    text_font_family=["Microsoft YaHei", "SimSun", "DejaVu Sans"],
    font_zh_map={1: "SimSun", 4: "SimHei"},
    font_en_map={0: "DejaVu Sans"},
)
with TemporaryDirectory() as output:
    result = renderer.render(
        layers,
        str(Path(output) / "map.png"),
        figsize=(12, 7.5),
        dpi=args.dpi,
    )
    reports = result.reports
    summary = {
        "layers": len(reports),
        "features": sum(report["features"] for report in reports),
        "drawn": sum(report["drawn"] for report in reports),
        "excluded_text": sum(report.get("excluded_text", 0) for report in reports),
        "unknown_colours": sum(
            sum(report.get("unknown_colors", {}).values()) for report in reports
        ),
        "fallbacks": sum(
            report.get("fallback", 0) + report.get("aux_fallback", 0)
            for report in reports
        ),
        "unknown_fills": sum(
            report.get("unknown_fill", 0) + report.get("aux_unknown_fill", 0)
            for report in reports
        ),
        "unresolved_symbols": sum(report.get("symbols_unresolved", 0) for report in reports),
        "unknown_fonts": sorted(
            {font for report in reports for font in report.get("unknown_fonts", {})}
        ),
    }
    print("PUBLISHED_QUICKSTART_SUMMARY", json.dumps(summary, sort_keys=True))
    assert summary["layers"] == 12
    assert summary["features"] == 7094
    assert summary["drawn"] + summary["excluded_text"] == 7094
    assert summary["unknown_colours"] == 0
    assert summary["fallbacks"] == 0
    assert summary["unknown_fills"] == 0
    assert summary["unresolved_symbols"] == 0
    assert summary["unknown_fonts"] == []
    result.figure.clear()
print("PUBLISHED_271_QUICKSTART_OK")
