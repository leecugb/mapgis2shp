# SPDX-License-Identifier: Apache-2.0
"""Command-line interface for pymapgis."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

import geopandas as gpd

from pymapgis import InvalidFileError, MapGISError, Reader, Writer

_MAPGIS_SUFFIXES = {".wt", ".wl", ".wp"}


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for the ``pymapgis`` CLI."""
    args_list = list(argv) if argv is not None else sys.argv[1:]
    if args_list and args_list[0] == "lib":
        return _lib_main(args_list[1:])

    parser = argparse.ArgumentParser(
        prog="pymapgis",
        description=(
            "Convert between MapGIS vector files (.wt, .wl, .wp) and common "
            "GIS formats (.shp, .geojson, .gpkg, ...)."
        ),
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Input file (.wt/.wl/.wp for MapGIS-to-GIS, or a GIS file for GIS-to-MapGIS)",
    )
    parser.add_argument("output", type=Path, help="Output file")
    parser.add_argument(
        "--driver",
        default=None,
        help="OGR driver short name (default: auto-detect from output extension)",
    )
    parser.add_argument(
        "--encoding",
        default=None,
        help="Character encoding used when reading the input GIS file (e.g. GBK)",
    )
    parser.add_argument(
        "--no-make-valid",
        action="store_true",
        help="Do not apply shapely.make_valid() to reconstructed polygons",
    )
    parser.add_argument(
        "--graphic-params",
        action="store_true",
        help=(
            "Also decode the graphic-parameter area of each feature and write "
            "the values (style/colour numbers, width, coefficients, symbol "
            "number, angle, ...) as extra attribute columns where the output "
            "format supports them"
        ),
    )

    args = parser.parse_args(args_list)

    if not args.input.exists():
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 1

    try:
        if args.input.suffix.lower() in _MAPGIS_SUFFIXES:
            with Reader(
                args.input,
                make_valid=not args.no_make_valid,
                read_graphic_params=args.graphic_params,
            ) as reader:
                kwargs = {"driver": args.driver} if args.driver else {}
                reader.to_file(args.output, **kwargs)
                print(f"Wrote {len(reader)} feature(s) to {args.output}")
        else:
            if args.driver:
                print(
                    "warning: --driver is ignored when writing MapGIS output",
                    file=sys.stderr,
                )
            if args.graphic_params:
                print(
                    "warning: --graphic-params is ignored when writing MapGIS output",
                    file=sys.stderr,
                )
            kwargs = {"encoding": args.encoding} if args.encoding else {}
            gdf = gpd.read_file(args.input, **kwargs)
            writer = Writer(gdf, make_valid=not args.no_make_valid)
            writer.to_file(args.output)
            print(f"Wrote {len(writer)} feature(s) to {args.output}")
    except (InvalidFileError, MapGISError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: failed to convert file: {exc}", file=sys.stderr)
        return 1

    return 0


def _sniff_lib_kind(path: Path) -> str:
    """Identify a MapGIS graphic library by name, then by magic.

    LINESTY.lib / Fillgrph.lib start with ``[u32 count][u16 reserved=0]``;
    Subgraph.lib starts with ``[u32 index_bytes][u32 first_offset>0]``.
    """
    name = path.name.lower()
    if "linesty" in name or "fillgrph" in name:
        return "linesty"
    if "subgraph" in name:
        return "subgraph"
    with path.open("rb") as f:
        head = f.read(8)
    if len(head) < 8:
        raise MapGISError("library file too short")
    return "linesty" if head[4] == 0 and head[5] == 0 else "subgraph"


def _lib_main(argv: Sequence[str]) -> int:
    """Inspect a MapGIS graphic library (Subgraph.lib / LINESTY.lib)."""
    parser = argparse.ArgumentParser(
        prog="pymapgis lib",
        description=(
            "Inspect MapGIS 6.x graphic libraries: Subgraph.lib (point-symbol "
            "library) and LINESTY.lib (line-style library)."
        ),
    )
    parser.add_argument("library", type=Path, help="Path to the library file")
    parser.add_argument(
        "--kind",
        choices=["auto", "subgraph", "linesty"],
        default="auto",
        help="Library kind (default: auto-detect from name/magic)",
    )
    parser.add_argument(
        "--symbol",
        type=int,
        default=None,
        help="Subgraph.lib: decode symbol number NO and print its geometry",
    )
    parser.add_argument(
        "--style",
        type=int,
        default=None,
        help="LINESTY.lib: decode line-style number NO (1-based, as in .wl records)",
    )
    parser.add_argument(
        "--aux",
        type=int,
        default=0,
        help="LINESTY.lib: auxiliary style number for the (style, aux) pair "
        "(default 0 = style alone)",
    )
    args = parser.parse_args(list(argv))

    if not args.library.exists():
        print(f"error: library file not found: {args.library}", file=sys.stderr)
        return 1

    kind = args.kind
    if kind == "auto":
        try:
            kind = _sniff_lib_kind(args.library)
        except MapGISError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    try:
        if kind == "subgraph":
            return _lib_subgraph(args)
        return _lib_linesty(args)
    except MapGISError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: failed to decode library: {exc}", file=sys.stderr)
        return 1


def _lib_subgraph(args: argparse.Namespace) -> int:
    from pymapgis.slib import SubgraphLib

    lib = SubgraphLib(str(args.library))
    print(
        f"{args.library.name}: {lib.n_indexed} indexed + "
        f"{lib.n_tail} tail-chain = {lib.symbol_count} symbols"
    )
    if args.symbol is None:
        return 0

    sym = lib.decode(args.symbol)
    if sym is None:
        print(f"error: symbol {args.symbol} out of range "
              f"(0..{lib.symbol_count - 1})", file=sys.stderr)
        return 1
    print(f"symbol #{args.symbol}: type={sym.type} n={sym.n} "
          f"header={sym.header_len}B points={sym.n_points}")
    for i, sp in enumerate(sym.subpaths):
        circle = ""
        if sp.circle is not None:
            cx, cy, r = sp.circle
            circle = f" circle=({cx:.4f},{cy:.4f}) r={r:.4f}"
        closed = " closed" if sp.closed else ""
        print(f"  subpath[{i}]: {len(sp.points)} points{closed}{circle}")
    return 0


def _lib_linesty(args: argparse.Namespace) -> int:
    from pymapgis.linesty import (
        LinestyLib,
        census,
        classify_form,
        compose_feature_style,
        pair_semantics,
    )

    lib = LinestyLib(str(args.library))
    print(f"{args.library.name}: {lib.count} slots, "
          f"{len(lib._nonempty)} non-empty")
    if args.style is None:
        stats = census(lib)
        print(f"decoded: {stats['decoded']}/{stats['total']}, "
              f"sublines matching length law: {stats['subline_law_ok']}, "
              f"coord-list sublines: {stats['coord_list_sublines']}, "
              f"inline-rhythm sublines: {stats['inline_pattern_sublines']}, "
              f"rhythm styles: {stats['rhythm_styles']}")
        if stats["bad"]:
            print(f"decode failures: {stats['bad']}")
        return 0

    style = lib.decode(args.style)
    if style is None:
        print(f"error: style {args.style} empty or out of range",
              file=sys.stderr)
        return 1
    main_style, aux_style = compose_feature_style(lib, args.style, args.aux)
    form, evidence = classify_form(style)
    sem = pair_semantics(args.style, args.aux)
    print(f"style {args.style} (aux={args.aux}): {len(style.sublines)} sublines")
    for s in style.sublines:
        if s.is_solid:
            print(f"  solid pen: color={s.color} width={s.width} "
                  f"yoff={s.yoff}")
        else:
            kinds = s.unit_kinds
            desc = ", ".join(f"{k}={v}" for k, v in kinds.items() if v)
            print(f"  template subline: n={s.n} length={s.length} [{desc}]")
    print(f"form: {form}")
    print(f"evidence: {evidence}")
    if sem:
        print(f"pair semantics: {sem}")
    rhythm = style.rhythm()
    if rhythm:
        print(f"rhythm: pens={rhythm['pens']} segments={rhythm['segments']} "
              f"period={rhythm['period_mm']:.4g}mm")
    if args.aux and aux_style is not None:
        print(f"aux style {args.aux}: {len(aux_style.sublines)} sublines "
              f"(overlaid per the 线型号-辅助线型号 rule)")
    return 0
