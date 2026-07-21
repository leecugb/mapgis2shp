#!/usr/bin/env python3
"""Smoke-test / regression script for pymapgis.

Discover all MapGIS vector files in the current directory, load them with
``pymapgis.Reader``, and verify that:

* the file loads without raising,
* feature count matches the stored baseline (if available),
* every geometry is valid,
* the CRS is detected or explicitly reported missing.

A baseline file ``pymapgis_baseline.json`` can be generated with the
``capture_baseline`` function below.
"""

from __future__ import annotations

import glob
import json
import sys
import time
import warnings
from pathlib import Path
from typing import Any, Dict

import numpy as np

# Allow running this script directly from the repository root before the
# package is installed.
_SRC = Path(__file__).parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from pymapgis import Reader


def load_baseline(path: str = "pymapgis_baseline.json") -> Dict[str, Any]:
    """Load the baseline captured from a previous reader version."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def check_file(path: str, baseline: Dict[str, Any]) -> Dict[str, Any]:
    """Load one MapGIS file and return a status dictionary."""
    result: Dict[str, Any] = {"path": path, "ok": False}
    t0 = time.time()
    try:
        with Reader(path) as reader:
            dt = time.time() - t0
            result["duration"] = dt
            result["count"] = len(reader)
            result["crs_wkt"] = reader.crs.to_wkt() if reader.crs else None
            result["geom_types"] = reader.geodataframe.geom_type.value_counts().to_dict()
            result["bbox"] = reader.bbox.tolist()
            result["invalid"] = int((~reader.geodataframe.is_valid).sum())
            result["ok"] = result["invalid"] == 0

            if path in baseline:
                expected = baseline[path]
                if "error" in expected:
                    result["baseline_error"] = expected["error"]
                    result["ok"] = False
                else:
                    if result["count"] != expected.get("count"):
                        result["ok"] = False
                        result["baseline_count_diff"] = (
                            result["count"],
                            expected.get("count"),
                        )
                    if not np.allclose(result["bbox"], expected.get("bbox", result["bbox"])):
                        result["ok"] = False
                        result["baseline_bbox_diff"] = (
                            result["bbox"],
                            expected.get("bbox"),
                        )
                    if result["crs_wkt"] != expected.get("crs_wkt"):
                        result["ok"] = False
                        result["baseline_crs_diff"] = (
                            result["crs_wkt"],
                            expected.get("crs_wkt"),
                        )
                    if result["invalid"] != expected.get("invalid", result["invalid"]):
                        result["ok"] = False
                        result["baseline_invalid_diff"] = (
                            result["invalid"],
                            expected.get("invalid"),
                        )
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["duration"] = time.time() - t0
    return result


def main() -> int:
    warnings.filterwarnings("ignore")
    baseline = load_baseline()

    files = sorted(glob.glob("*.WT") + glob.glob("*.WL") + glob.glob("*.WP"))
    if not files:
        print("No MapGIS files found in the current directory.")
        return 0

    errors = []
    baseline_diffs = []
    print(f"Checking {len(files)} files...")
    for path in files:
        result = check_file(path, baseline)
        status = "OK" if result["ok"] else "FAIL"
        invalid = result.get("invalid", "-")
        duration = result.get("duration", 0.0)
        line = (
            f"{path}: {status} | {result.get('count', '-')} features | "
            f"invalid={invalid} | {duration:.3f}s"
        )
        if "baseline_count_diff" in result:
            line += f" | count_diff={result['baseline_count_diff']}"
        if "baseline_error" in result:
            line += f" | baseline_error={result['baseline_error']}"
        print(line)

        if not result["ok"]:
            errors.append(result)
            if "baseline_count_diff" in result or "baseline_bbox_diff" in result or "baseline_crs_diff" in result:
                baseline_diffs.append(result)

    print()
    if errors:
        print(f"FAILED: {len(errors)} file(s)")
        for result in errors:
            print(f"  {result['path']}: {result.get('error', 'baseline mismatch')}")
        return 1

    print("All files loaded successfully.")
    if baseline:
        print(f"Compared against baseline ({len(baseline)} entries).")
    return 0


def capture_baseline(output: str = "pymapgis_baseline.json") -> None:
    """Capture a lightweight baseline for regression testing."""
    warnings.filterwarnings("ignore")
    baseline: Dict[str, Any] = {}
    files = sorted(glob.glob("*.WT") + glob.glob("*.WL") + glob.glob("*.WP"))
    for path in files:
        try:
            with Reader(path) as reader:
                baseline[path] = {
                    "count": len(reader),
                    "bbox": reader.bbox.tolist(),
                    "crs_wkt": reader.crs.to_wkt() if reader.crs else None,
                    "geom_types": reader.geodataframe.geom_type.value_counts().to_dict(),
                    "invalid": int((~reader.geodataframe.is_valid).sum()),
                }
                print(f"{path}: {len(reader)} features")
        except Exception as exc:
            baseline[path] = {"error": f"{type(exc).__name__}: {exc}"}
            print(f"{path}: ERROR {exc}")

    with open(output, "w", encoding="utf-8") as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2)
    print(f"Baseline saved to {output}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--capture-baseline":
        sys.exit(capture_baseline())
    sys.exit(main())
