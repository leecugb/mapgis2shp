"""Command-line interface for pymapgis."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from pymapgis import InvalidFileError, MapGISError, Reader


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for the ``pymapgis`` CLI."""
    parser = argparse.ArgumentParser(
        prog="pymapgis",
        description="Convert MapGIS vector files (.wt, .wl, .wp) to common GIS formats.",
    )
    parser.add_argument("input", type=Path, help="Input MapGIS file (.wt, .wl, or .wp)")
    parser.add_argument("output", type=Path, help="Output file")
    parser.add_argument(
        "--driver",
        default=None,
        help="OGR driver short name (default: auto-detect from output extension)",
    )
    parser.add_argument(
        "--no-make-valid",
        action="store_true",
        help="Do not apply shapely.make_valid() to reconstructed polygons",
    )

    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 1

    try:
        with Reader(args.input, make_valid=not args.no_make_valid) as reader:
            kwargs = {"driver": args.driver} if args.driver else {}
            reader.to_file(args.output, **kwargs)
            print(f"Wrote {len(reader)} feature(s) to {args.output}")
    except (InvalidFileError, MapGISError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: failed to convert file: {exc}", file=sys.stderr)
        return 1

    return 0
