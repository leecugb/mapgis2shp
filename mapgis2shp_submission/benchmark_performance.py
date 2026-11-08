#!/usr/bin/env python3
"""Benchmark pymapgis Reader runtime and peak memory on MapGIS vector layers.

The parent process starts a fresh Python process for every layer and for the
whole-corpus sequential pass. Reader construction and GeoDataFrame access are
timed; package import time is excluded. On Windows, peak memory is the process
peak working set reported by psutil. The post-import baseline, absolute peak,
and peak-minus-baseline values are all retained.

Run from the repository root or the submission directory, for example:

    python benchmark_performance.py --data-dir D:/JWD --repeats 3

The default source tree is ../src relative to this script's parent directory,
so the benchmark uses the current source rather than an older installed wheel.
"""

from __future__ import annotations

import argparse
import csv
import gc
import importlib.metadata
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

MIB = 1024**2


def _memory(process: psutil.Process) -> dict[str, int]:
    info = process.memory_info()
    return {
        "rss_bytes": int(info.rss),
        "peak_rss_bytes": int(getattr(info, "peak_wset", info.rss)),
    }


def _read_layer(path: Path, reader_class: Any) -> dict[str, Any]:
    start = time.perf_counter()
    with reader_class(path) as reader:
        # Reader parses in its constructor; accessing the GeoDataFrame makes the
        # benchmark's consumed output explicit rather than timing only file I/O.
        frame = reader.geodataframe
        result = {
            "features": len(reader),
            "geometry_type": reader.shapeType,
            "frame_rows": len(frame),
            "bbox": [float(v) for v in reader.bbox],
        }
    result["duration_seconds"] = time.perf_counter() - start
    return result


def _worker_one(args: argparse.Namespace) -> dict[str, Any]:
    sys.path.insert(0, str(args.src.resolve()))
    import pymapgis
    from pymapgis import Reader

    process = psutil.Process()
    gc.collect()
    baseline = _memory(process)["rss_bytes"]
    samples: list[float] = []
    result: dict[str, Any] = {}
    for _ in range(args.repeats):
        gc.collect()
        result = _read_layer(args.worker, Reader)
        samples.append(float(result.pop("duration_seconds")))

    gc.collect()
    memory = _memory(process)
    return {
        **result,
        "file": args.worker.name,
        "size_bytes": args.worker.stat().st_size,
        "pymapgis_version": pymapgis.__version__,
        "pymapgis_source": str(Path(pymapgis.__file__).resolve()),
        "duration_samples_seconds": samples,
        "first_seconds": samples[0],
        "median_seconds": statistics.median(samples),
        "min_seconds": min(samples),
        "max_seconds": max(samples),
        "baseline_rss_bytes": baseline,
        "final_rss_bytes": memory["rss_bytes"],
        "peak_rss_bytes": memory["peak_rss_bytes"],
        "peak_increment_bytes": max(0, memory["peak_rss_bytes"] - baseline),
    }


def _mapgis_files(data_dir: Path) -> list[Path]:
    files = sorted(
        path
        for pattern in ("*.WT", "*.WL", "*.WP")
        for path in data_dir.glob(pattern)
    )
    if not files:
        raise FileNotFoundError(f"No .WT/.WL/.WP files found in {data_dir}")
    return files


def _worker_corpus(args: argparse.Namespace) -> dict[str, Any]:
    sys.path.insert(0, str(args.src.resolve()))
    import pymapgis
    from pymapgis import Reader

    files = _mapgis_files(args.data_dir)
    process = psutil.Process()
    gc.collect()
    baseline = _memory(process)["rss_bytes"]
    samples: list[float] = []
    features = 0
    for _ in range(args.repeats):
        gc.collect()
        start = time.perf_counter()
        repeat_features = 0
        for path in files:
            result = _read_layer(path, Reader)
            repeat_features += int(result["features"])
        samples.append(time.perf_counter() - start)
        features = repeat_features

    gc.collect()
    memory = _memory(process)
    return {
        "file_count": len(files),
        "features": features,
        "size_bytes": sum(path.stat().st_size for path in files),
        "pymapgis_version": pymapgis.__version__,
        "pymapgis_source": str(Path(pymapgis.__file__).resolve()),
        "duration_samples_seconds": samples,
        "first_seconds": samples[0],
        "median_seconds": statistics.median(samples),
        "min_seconds": min(samples),
        "max_seconds": max(samples),
        "baseline_rss_bytes": baseline,
        "final_rss_bytes": memory["rss_bytes"],
        "peak_rss_bytes": memory["peak_rss_bytes"],
        "peak_increment_bytes": max(0, memory["peak_rss_bytes"] - baseline),
    }


def _run_worker(script: Path, common: list[str], selector: list[str]) -> dict[str, Any]:
    command = [sys.executable, str(script), *common, *selector]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=os.environ.copy(),
    )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Worker did not return JSON. stdout={completed.stdout!r}; "
            f"stderr={completed.stderr!r}"
        ) from exc


def _cpu_name() -> str:
    if os.name == "nt":
        try:
            completed = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance Win32_Processor).Name",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            return completed.stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            pass
    return platform.processor()


def _environment() -> dict[str, Any]:
    packages = {}
    for name in ("geopandas", "numpy", "pandas", "pyogrio", "pyproj", "shapely", "psutil"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu": _cpu_name(),
        "cpu_physical_cores": psutil.cpu_count(logical=False),
        "cpu_logical_cores": psutil.cpu_count(logical=True),
        "physical_memory_bytes": psutil.virtual_memory().total,
        "package_versions": packages,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "file",
        "geometry_type",
        "features",
        "size_MiB",
        "first_seconds",
        "median_seconds",
        "min_seconds",
        "max_seconds",
        "features_per_second",
        "MiB_per_second",
        "baseline_rss_MiB",
        "peak_rss_MiB",
        "peak_increment_MiB",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            median = row["median_seconds"]
            writer.writerow(
                {
                    "file": row["file"],
                    "geometry_type": row["geometry_type"],
                    "features": row["features"],
                    "size_MiB": f"{row['size_bytes'] / MIB:.6f}",
                    "first_seconds": f"{row['first_seconds']:.9f}",
                    "median_seconds": f"{median:.9f}",
                    "min_seconds": f"{row['min_seconds']:.9f}",
                    "max_seconds": f"{row['max_seconds']:.9f}",
                    "features_per_second": f"{row['features'] / median:.3f}",
                    "MiB_per_second": f"{row['size_bytes'] / MIB / median:.3f}",
                    "baseline_rss_MiB": f"{row['baseline_rss_bytes'] / MIB:.3f}",
                    "peak_rss_MiB": f"{row['peak_rss_bytes'] / MIB:.3f}",
                    "peak_increment_MiB": f"{row['peak_increment_bytes'] / MIB:.3f}",
                }
            )


def _parent(args: argparse.Namespace) -> None:
    script = Path(__file__).resolve()
    files = _mapgis_files(args.data_dir)
    common = ["--src", str(args.src.resolve()), "--repeats", str(args.repeats)]
    rows = []
    for path in files:
        row = _run_worker(script, common, ["--worker", str(path.resolve())])
        rows.append(row)
        print(
            f"{row['file']}: {row['features']} features; "
            f"median={row['median_seconds']:.4f}s; "
            f"peak increment={row['peak_increment_bytes'] / MIB:.1f} MiB",
            flush=True,
        )

    corpus = _run_worker(
        script,
        [*common, "--data-dir", str(args.data_dir.resolve())],
        ["--corpus-worker"],
    )
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": {
            "reader_defaults": {
                "make_valid": True,
                "read_point_params": False,
                "read_graphic_params": False,
            },
            "repeats_per_layer_and_corpus": args.repeats,
            "statistic": "median; first/min/max samples retained",
            "process_isolation": "fresh Python process per layer and per corpus pass",
            "timing_scope": "Reader construction plus GeoDataFrame access; imports excluded",
            "memory_metric": "Windows peak working set (peak_wset) via psutil",
            "memory_baseline": "RSS after pymapgis import and garbage collection",
            "cache_note": "Repeated reads may benefit from operating-system file caching",
        },
        "environment": _environment(),
        "layers": rows,
        "corpus": corpus,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    csv_path = args.output.with_suffix(".csv")
    _write_csv(csv_path, rows)
    print(
        f"Corpus: {corpus['file_count']} layers, {corpus['features']} features; "
        f"median={corpus['median_seconds']:.4f}s; "
        f"peak increment={corpus['peak_increment_bytes'] / MIB:.1f} MiB",
        flush=True,
    )
    print(f"Wrote {args.output} and {csv_path}", flush=True)


def main() -> int:
    submission_dir = Path(__file__).resolve().parent
    repository_root = submission_dir.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=repository_root)
    parser.add_argument("--src", type=Path, default=repository_root / "src")
    parser.add_argument(
        "--output",
        type=Path,
        default=submission_dir / "performance_benchmark.json",
    )
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--corpus-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")

    if args.worker:
        result = _worker_one(args)
    elif args.corpus_worker:
        result = _worker_corpus(args)
    else:
        _parent(args)
        return 0
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
