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
            "Read, convert and write MapGIS vectors (.wt, .wl, .wp), parse "
            "the five graphic-library types, and render vectors from them."
        ),
        epilog=(
            "Additional interfaces:\n"
            "  pymapgis lib LIB [--symbol N | --style N | --pattern N | --color N]\n"
            "  Inspect Subgraph, LINESTY, Fillgrph, Colorlib and Pcolor libraries.\n"
            "  Original-library rendering: use GraphicRenderer or render_graphic_map "
            "from pymapgis (optional Matplotlib extra)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    validity = parser.add_mutually_exclusive_group()
    validity.add_argument(
        "--make-valid",
        action="store_true",
        help="Apply shapely.make_valid() instead of preserving native rings",
    )
    validity.add_argument(
        "--no-make-valid",
        action="store_true",
        help="Preserve native rings (default; kept for backward compatibility)",
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
                make_valid=args.make_valid,
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
            writer = Writer(gdf, make_valid=args.make_valid)
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
    """Identify a supported MapGIS graphic library by name and magic."""
    name = path.name.lower()
    named = {
        "linesty": "linesty",
        "fillgrph": "fillgrph",
        "subgraph": "subgraph",
        "colorlib": "colorlib",
        "pcolor": "pcolor",
    }
    for token, kind in named.items():
        if token in name:
            return kind
    with path.open("rb") as f:
        head = f.read(16)
    if head.startswith(b"PCOLOR"):
        return "pcolor"
    if head.startswith(b"C.U.G"):
        return "colorlib"
    if len(head) < 8:
        raise MapGISError("library file too short")
    return "linesty" if head[4] == 0 and head[5] == 0 else "subgraph"


def _lib_main(argv: Sequence[str]) -> int:
    """Inspect any of the five supported MapGIS graphic libraries."""
    parser = argparse.ArgumentParser(
        prog="pymapgis lib",
        description=(
            "Inspect Subgraph.lib, LINESTY.lib, Fillgrph.lib, Colorlib.lib "
            "or Pcolor.lib structures and selected records."
        ),
    )
    parser.add_argument("library", type=Path, help="Path to the library file")
    parser.add_argument(
        "--kind",
        choices=["auto", "subgraph", "linesty", "fillgrph", "colorlib", "pcolor"],
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
        "--pattern",
        type=int,
        default=None,
        help="Fillgrph.lib: decode fill-pattern number NO (1-based)",
    )
    parser.add_argument(
        "--color",
        type=int,
        default=None,
        help="Colorlib.lib / Pcolor.lib: decode colour number NO",
    )
    parser.add_argument(
        "--channel-order",
        choices=["KCMY", "YMCK"],
        default="KCMY",
        help="Colour channel model (default: KCMY)",
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
        if kind == "linesty":
            return _lib_linesty(args)
        if kind == "fillgrph":
            return _lib_fillgrph(args)
        if kind in {"colorlib", "pcolor"}:
            return _lib_color(args, pcolor=kind == "pcolor")
        raise MapGISError(f"unsupported library kind: {kind}")
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
    _, aux_style = compose_feature_style(lib, args.style, args.aux)
    form, evidence = classify_form(style)
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
    rhythm = style.rhythm()
    if rhythm:
        print(f"rhythm: pens={rhythm['pens']} segments={rhythm['segments']} "
              f"period={rhythm['period_mm']:.4g}mm")
    if args.aux and aux_style is not None:
        print(f"aux style {args.aux}: {len(aux_style.sublines)} sublines "
              f"(overlaid per the 线型号-辅助线型号 rule)")
    return 0


def _lib_fillgrph(args: argparse.Namespace) -> int:
    from pymapgis.fillgrph import FillgrphLib, pattern_geometry

    lib = FillgrphLib(str(args.library))
    print(f"{args.library.name}: {lib.count} records")
    if args.pattern is None:
        return 0
    geometry = pattern_geometry(lib, args.pattern)
    if geometry is None:
        print(f"error: pattern {args.pattern} is empty or unsupported", file=sys.stderr)
        return 1
    print(
        f"pattern {args.pattern}: "
        f"fill_polygons={len(geometry['fill_polygons'])}, "
        f"polylines={len(geometry['polylines'])}, "
        f"circles={len(geometry['circles'])}, arcs={len(geometry['arcs'])}"
    )
    return 0


def _lib_color(args: argparse.Namespace, *, pcolor: bool) -> int:
    if pcolor:
        from pymapgis.pcolor import PcolorLib as library_class
    else:
        from pymapgis.colorlib import ColorLib as library_class

    lib = library_class(str(args.library), channel_order=args.channel_order)
    if pcolor:
        print(f"{args.library.name}: {lib.count} colour nodes (max_no={lib.max_no})")
    else:
        print(f"{args.library.name}: {lib.max_no + 1} entries (max_no={lib.max_no})")
    if args.color is None:
        return 0
    channels = lib.kcmy(args.color)
    rgb = lib.rgb(args.color)
    if channels is None or rgb is None:
        print(f"error: colour {args.color} out of range", file=sys.stderr)
        return 1
    print(f"colour {args.color}: channels={channels} RGB={rgb} model={lib.channel_order}")
    return 0
