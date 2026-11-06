# SPDX-License-Identifier: Apache-2.0
"""Render MapGIS vectors with their original MapGIS graphic libraries.

The public entry points are :class:`GraphicLibraries`,
:class:`GraphicRenderer`, and :func:`render_graphic_map`.  Matplotlib is an
optional dependency and is imported only when rendering is requested.

The renderer consumes library geometry rather than replacing it with thematic
styles: WP fill/pattern records, WL line-style rhythms, and WT subgraph/text
records.  Coordinates always come from the vector features.  In particular,
line-style stamps follow the original polyline and never extend its endpoints.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import numpy as np

from pymapgis.colorlib import ColorLib
from pymapgis.fillgrph import FillgrphLib, pattern_geometry
from pymapgis.linesty import LinestyLib, feature_rhythm
from pymapgis.reader import Reader
from pymapgis.slib import SubgraphLib

PathLike = Union[str, Path]
RGB = Tuple[float, float, float]
MM_TO_PT = 72.0 / 25.4


@dataclass
class GraphicLibraries:
    """The four MapGIS libraries required by the graphic renderer.

    Use :meth:`from_directory` for normal MapGIS ``SLIB`` installations.  The
    parser fields are public so callers may also supply already-opened or
    compatible parser objects, which is useful for testing and applications
    with custom library storage.
    """

    linesty: LinestyLib
    subgraph: SubgraphLib
    fillgrph: FillgrphLib
    color: ColorLib
    directory: Optional[Path] = None

    @classmethod
    def from_directory(cls, directory: PathLike) -> "GraphicLibraries":
        """Load ``LINESTY.lib``, ``Subgraph.lib``, ``Fillgrph.lib`` and
        ``Colorlib.lib`` from *directory*.

        A single error lists every missing library instead of failing one file
        at a time.
        """
        root = Path(directory)
        names = ("LINESTY.lib", "Subgraph.lib", "Fillgrph.lib", "Colorlib.lib")
        missing = [name for name in names if not (root / name).is_file()]
        if missing:
            raise FileNotFoundError(
                "Missing MapGIS graphic libraries in {}: {}".format(root, ", ".join(missing))
            )
        return cls(
            linesty=LinestyLib(str(root / "LINESTY.lib")),
            subgraph=SubgraphLib(str(root / "Subgraph.lib")),
            fillgrph=FillgrphLib(str(root / "Fillgrph.lib")),
            color=ColorLib(str(root / "Colorlib.lib")),
            directory=root,
        )


@dataclass
class GraphicRenderResult:
    """Result returned by :meth:`GraphicRenderer.render`."""

    figure: Any
    axes: Any
    reports: List[Dict[str, Any]]
    bounds: Tuple[float, float, float, float]
    output: Optional[Path] = None


@dataclass
class _Layer:
    gdf: Any
    kind: str
    source: str


@dataclass
class _StampBuffer:
    segments: List[np.ndarray] = field(default_factory=list)
    segment_colors: List[RGB] = field(default_factory=list)
    segment_widths: List[float] = field(default_factory=list)
    dots: List[np.ndarray] = field(default_factory=list)
    dot_radii: List[float] = field(default_factory=list)
    dot_colors: List[RGB] = field(default_factory=list)
    fills: List[np.ndarray] = field(default_factory=list)
    fill_colors: List[RGB] = field(default_factory=list)


class GraphicRenderer:
    """Render WL/WP/WT data using original MapGIS graphic parameters.

    Parameters
    ----------
    libraries:
        A :class:`GraphicLibraries` instance.
    scale:
        Map scale denominator.  At 1:250000, one paper millimetre represents
        250 metres on the ground.
    map_units_per_mm:
        Explicit paper-mm to map-coordinate conversion.  Normally this is
        inferred from each layer's CRS.  It is required for layers without a
        CRS and is useful for local engineering coordinate systems.
    color_overrides:
        Optional ``{color_number: (r, g, b)}`` mapping for installation-local
        or extended Pcolor entries.  RGB components must be in the 0–1 range.
        No inferred extended colours are enabled by default.
    fallback_color:
        Colour used for unresolved feature colours; unresolved library-defined
        symbol fills are instead left unfilled.
    fallback_to_solid:
        Draw an original-coordinate solid line when a line style cannot be
        decoded.  Every such feature is counted as ``fallback`` in the report.
    symbol_fills:
        Consume adjudicated Subgraph ``Element.fill_kind`` fills.
    exclude_text_categories:
        Optional CHFCEC categories to omit, for example ``{"代号"}``.
    text_category_scales:
        Optional CHFCEC-specific font-size multipliers.
    text_font_family:
        Optional Matplotlib font family or fallback list for text annotations.

    Notes
    -----
    A renderer caches decoded styles, symbols and pattern tiles.  Create one
    renderer per library set and reuse it for related layers.
    """

    def __init__(
        self,
        libraries: GraphicLibraries,
        *,
        scale: float = 250000.0,
        map_units_per_mm: Optional[float] = None,
        color_overrides: Optional[Mapping[int, RGB]] = None,
        fallback_color: RGB = (0.85, 0.85, 0.85),
        line_min_pt: float = 0.05,
        dot_min_pt: float = 0.2,
        symbol_line_width_pt: float = 0.25,
        polygon_edge_color: str = "none",
        polygon_edge_width_pt: float = 0.0,
        tile_pixels: int = 26,
        max_pattern_tiles: int = 40000,
        fallback_to_solid: bool = True,
        symbol_fills: bool = True,
        exclude_text_categories: Sequence[str] = (),
        text_category_scales: Optional[Mapping[str, float]] = None,
        text_scale: float = 1.0,
        text_font_family: Any = None,
    ) -> None:
        if scale <= 0:
            raise ValueError("scale must be positive")
        if map_units_per_mm is not None and map_units_per_mm <= 0:
            raise ValueError("map_units_per_mm must be positive")
        if tile_pixels < 4:
            raise ValueError("tile_pixels must be at least 4")
        if max_pattern_tiles < 1:
            raise ValueError("max_pattern_tiles must be positive")
        self.libraries = libraries
        self.scale = float(scale)
        self.map_units_per_mm = map_units_per_mm
        self.color_overrides = {
            int(no): self._validate_rgb(rgb) for no, rgb in (color_overrides or {}).items()
        }
        self.fallback_color = self._validate_rgb(fallback_color)
        self.line_min_pt = float(line_min_pt)
        self.dot_min_pt = float(dot_min_pt)
        self.symbol_line_width_pt = float(symbol_line_width_pt)
        self.polygon_edge_color = polygon_edge_color
        self.polygon_edge_width_pt = float(polygon_edge_width_pt)
        self.tile_pixels = int(tile_pixels)
        self.max_pattern_tiles = int(max_pattern_tiles)
        self.fallback_to_solid = bool(fallback_to_solid)
        self.symbol_fills = bool(symbol_fills)
        self.exclude_text_categories = {str(x).strip() for x in exclude_text_categories}
        self.text_category_scales = dict(text_category_scales or {})
        self.text_scale = float(text_scale)
        self.text_font_family = text_font_family
        self._rhythm_cache: Dict[int, Optional[dict]] = {}
        self._symbol_cache: Dict[int, Any] = {}
        self._tile_cache: Dict[int, Optional[np.ndarray]] = {}

    @staticmethod
    def _validate_rgb(rgb: RGB) -> RGB:
        try:
            values = tuple(float(v) for v in rgb)
        except (TypeError, ValueError) as exc:
            raise ValueError("RGB colours must contain three numeric components") from exc
        if len(values) != 3 or any(not 0.0 <= v <= 1.0 for v in values):
            raise ValueError("RGB components must be in the 0–1 range")
        return values  # type: ignore[return-value]

    @staticmethod
    def read_layer(path: PathLike) -> Any:
        """Read a WL/WP/WT file with all graphic parameters enabled."""
        source = Path(path)
        suffix = source.suffix.lower()
        if suffix not in (".wl", ".wp", ".wt"):
            raise ValueError("Expected a .wl, .wp or .wt file: {}".format(source))
        return Reader(
            str(source),
            read_graphic_params=True,
            read_point_params=(suffix == ".wt"),
        ).geodataframe

    def render(
        self,
        layers: Sequence[Any],
        output: Optional[PathLike] = None,
        *,
        figsize: Tuple[float, float] = (10.0, 8.0),
        dpi: int = 300,
        margin: float = 0.01,
        title: Optional[str] = None,
    ) -> GraphicRenderResult:
        """Render layers in WP → WL → WT order and optionally write PNG/PDF.

        Layer paths and GeoDataFrames may be mixed.  GeoDataFrame geometry type
        is used when no file suffix is available.  The returned Figure remains
        open for caller customisation.
        """
        if output is not None and Path(output).suffix.lower() not in (".png", ".pdf"):
            raise ValueError("Graphic output must be .png or .pdf: {}".format(output))
        try:
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            from matplotlib.figure import Figure
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise ImportError(
                "Graphic rendering requires matplotlib; install mapgis2shp[render]"
            ) from exc

        fig = Figure(figsize=figsize)
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)
        reports = self.draw_layers(ax, layers, margin=margin)
        if title:
            ax.set_title(title)
        result = GraphicRenderResult(
            figure=fig,
            axes=ax,
            reports=reports,
            bounds=(0.0, 0.0, 0.0, 0.0),
        )
        # Store bounds in GIS order (xmin, ymin, xmax, ymax), not display order.
        xmin, xmax = ax.get_xlim()
        ymin, ymax = ax.get_ylim()
        result.bounds = (xmin, ymin, xmax, ymax)
        if output is not None:
            result.output = Path(output)
            self._save(fig, result.output, dpi=dpi)
        return result

    def _save(self, fig: Any, output: Path, *, dpi: int) -> None:
        suffix = output.suffix.lower()
        if suffix not in (".png", ".pdf"):
            raise ValueError("Graphic output must be .png or .pdf: {}".format(output))
        output.parent.mkdir(parents=True, exist_ok=True)
        if suffix == ".pdf":
            from matplotlib.backends.backend_pdf import FigureCanvasPdf

            FigureCanvasPdf(fig)
            fig.savefig(str(output), format="pdf")
        else:
            fig.savefig(str(output), format="png", dpi=dpi)

    def draw_layers(
        self,
        ax: Any,
        layers: Sequence[Any],
        *,
        margin: float = 0.01,
        set_extent: bool = True,
    ) -> List[Dict[str, Any]]:
        """Draw layers onto an existing Matplotlib Axes.

        Extent is established before any WL drawing because display point sizes
        and pattern stamps depend on ``ax.transData``.  Set ``set_extent=False``
        only when the caller has already set suitable x/y limits.
        """
        if not layers:
            raise ValueError("At least one graphic layer is required")
        prepared = [self._coerce_layer(layer) for layer in layers]
        order = {"wp": 0, "wl": 1, "wt": 2}
        prepared = sorted(prepared, key=lambda layer: order[layer.kind])
        self._check_crs(prepared)
        if set_extent:
            bounds = self._combined_bounds(prepared)
            self._set_extent(ax, bounds, margin)
        ax.set_aspect("equal", adjustable="box")
        ax.axis("off")
        # Initialise transData before line widths and dot minima are computed.
        ax.figure.canvas.draw()
        return [self._draw_layer(ax, layer) for layer in prepared]

    def draw_layer(self, ax: Any, layer: Any, *, kind: Optional[str] = None) -> Dict[str, Any]:
        """Draw one layer onto an Axes whose extent is already established."""
        prepared = self._coerce_layer(layer, kind=kind)
        ax.figure.canvas.draw()
        return self._draw_layer(ax, prepared)

    def _coerce_layer(self, layer: Any, kind: Optional[str] = None) -> _Layer:
        if isinstance(layer, (str, Path)):
            path = Path(layer)
            inferred = path.suffix.lower().lstrip(".")
            gdf = self.read_layer(path)
            source = str(path)
        else:
            gdf = layer
            inferred = ""
            source = "<GeoDataFrame>"
        kind = (kind or inferred or self._infer_kind(gdf)).lower()
        if kind not in ("wl", "wp", "wt"):
            raise ValueError("Layer kind must be wl, wp or wt; got {!r}".format(kind))
        if not hasattr(gdf, "geometry"):
            raise TypeError("Graphic layers must be file paths or GeoDataFrames")
        required = {"wp": ("fill_color",), "wl": ("linetype",), "wt": ("point_type",)}
        missing = [name for name in required[kind] if name not in gdf.columns]
        if missing:
            raise ValueError(
                "{} layer {} lacks graphic parameter columns: {}. "
                "Read it with read_graphic_params=True{}.".format(
                    kind.upper(),
                    source,
                    ", ".join(missing),
                    " and read_point_params=True" if kind == "wt" else "",
                )
            )
        return _Layer(gdf=gdf, kind=kind, source=source)

    @staticmethod
    def _infer_kind(gdf: Any) -> str:
        if not hasattr(gdf, "geom_type"):
            raise ValueError("Cannot infer layer kind without GeoDataFrame geometry types")
        types = set(gdf.geom_type.dropna())
        if types & {"Polygon", "MultiPolygon"}:
            return "wp"
        if types & {"LineString", "MultiLineString"}:
            return "wl"
        if types & {"Point", "MultiPoint"}:
            return "wt"
        raise ValueError("Cannot infer WL/WP/WT kind from geometry types: {}".format(types))

    @staticmethod
    def _check_crs(layers: Sequence[_Layer]) -> None:
        crs_values = [
            layer.gdf.crs for layer in layers if getattr(layer.gdf, "crs", None) is not None
        ]
        if crs_values and any(crs != crs_values[0] for crs in crs_values[1:]):
            raise ValueError("All graphic layers must use the same CRS; reproject them first")

    @staticmethod
    def _combined_bounds(layers: Sequence[_Layer]) -> Tuple[float, float, float, float]:
        bounds = []
        for layer in layers:
            if len(layer.gdf) == 0:
                continue
            values = np.asarray(layer.gdf.total_bounds, dtype=float)
            if values.shape == (4,) and np.all(np.isfinite(values)):
                bounds.append(values)
        if not bounds:
            raise ValueError("Graphic layers contain no finite, non-empty geometry")
        arr = np.asarray(bounds)
        return (
            float(arr[:, 0].min()),
            float(arr[:, 1].min()),
            float(arr[:, 2].max()),
            float(arr[:, 3].max()),
        )

    def _set_extent(
        self, ax: Any, bounds: Tuple[float, float, float, float], margin: float
    ) -> None:
        if margin < 0:
            raise ValueError("margin must be non-negative")
        xmin, ymin, xmax, ymax = bounds
        width, height = xmax - xmin, ymax - ymin
        base = max(width, height)
        if base <= 0:
            base = (self.map_units_per_mm or self.scale * 0.001) * 10.0
        pad = max(base * margin, 1e-12)
        ax.set_xlim(xmin - pad, xmax + pad)
        ax.set_ylim(ymin - pad, ymax + pad)

    def _draw_layer(self, ax: Any, layer: _Layer) -> Dict[str, Any]:
        report: Dict[str, Any] = {
            "source": layer.source,
            "kind": layer.kind,
            "features": int(len(layer.gdf)),
            "drawn": 0,
            "unknown_colors": {},
            "overridden_colors": {},
        }
        if layer.kind == "wp":
            self._draw_wp(ax, layer.gdf, report)
        elif layer.kind == "wl":
            self._draw_wl(ax, layer.gdf, report)
        else:
            self._draw_wt(ax, layer.gdf, report)
        return report

    def _unit(self, gdf: Any) -> float:
        if self.map_units_per_mm is not None:
            return float(self.map_units_per_mm)
        crs = getattr(gdf, "crs", None)
        if crs is None:
            raise ValueError("Layers without a CRS require explicit map_units_per_mm")
        if crs.is_geographic:
            return self.scale * 0.001 / 111320.0
        axis = crs.axis_info[0] if crs.axis_info else None
        metres_per_unit = getattr(axis, "unit_conversion_factor", None) if axis else None
        if not metres_per_unit or metres_per_unit <= 0:
            raise ValueError("Cannot infer map units from CRS; set map_units_per_mm")
        return self.scale * 0.001 / float(metres_per_unit)

    @staticmethod
    def _float(value: Any, default: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) else default

    @staticmethod
    def _text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (float, np.floating)) and not math.isfinite(value):
            return ""
        return str(value)

    @classmethod
    def _int(cls, value: Any, default: int = 0) -> int:
        return int(cls._float(value, float(default)))

    @staticmethod
    def _bump(report: Dict[str, Any], key: str, amount: int = 1) -> None:
        report[key] = int(report.get(key, 0)) + amount

    def _color(
        self, number: Any, report: Dict[str, Any], *, fallback: bool = True
    ) -> Optional[RGB]:
        no = self._int(number)
        if no in self.color_overrides:
            key = str(no)
            report["overridden_colors"][key] = report["overridden_colors"].get(key, 0) + 1
            return self.color_overrides[no]
        rgb = self.libraries.color.rgb01(no)
        if rgb is not None:
            return tuple(rgb)  # type: ignore[return-value]
        key = str(no)
        report["unknown_colors"][key] = report["unknown_colors"].get(key, 0) + 1
        return self.fallback_color if fallback else None

    # ------------------------------------------------------------------ WP

    @staticmethod
    def _iter_polygons(geom: Any):
        if geom is None or geom.is_empty:
            return
        if geom.geom_type == "Polygon":
            yield geom
        elif hasattr(geom, "geoms"):
            for part in geom.geoms:
                yield from GraphicRenderer._iter_polygons(part)

    @staticmethod
    def _polygon_patch(poly: Any, **kwargs: Any) -> Any:
        from matplotlib.patches import PathPatch
        from matplotlib.path import Path as MplPath
        from shapely.geometry.polygon import orient

        poly = orient(poly, sign=1.0)
        vertices: List[Tuple[float, float]] = []
        codes: List[int] = []
        for ring in [poly.exterior] + list(poly.interiors):
            coords = list(ring.coords)
            vertices.extend(coords)
            codes.extend(
                [MplPath.MOVETO] + [MplPath.LINETO] * (len(coords) - 2) + [MplPath.CLOSEPOLY]
            )
        return PathPatch(MplPath(vertices, codes), **kwargs)

    def _draw_wp(self, ax: Any, gdf: Any, report: Dict[str, Any]) -> None:
        unit = self._unit(gdf)
        for _, row in gdf.iterrows():
            polygons = list(self._iter_polygons(row.geometry))
            if not polygons:
                continue
            self._bump(report, "drawn")
            report["holes"] = int(report.get("holes", 0)) + sum(len(p.interiors) for p in polygons)
            rgb = self._color(row.get("fill_color"), report)
            for poly in polygons:
                ax.add_patch(
                    self._polygon_patch(
                        poly,
                        facecolor=rgb,
                        edgecolor=self.polygon_edge_color,
                        linewidth=self.polygon_edge_width_pt,
                        zorder=2,
                    )
                )
            pattern = self._int(row.get("pattern"))
            height = self._float(row.get("pattern_height"), 0.0)
            width = self._float(row.get("pattern_width"), 0.0)
            if pattern <= 0 or height <= 0 or width <= 0:
                continue
            pattern_rgb = self._color(row.get("pattern_color"), report)
            outcomes = [
                self._draw_pattern(ax, poly, pattern, pattern_rgb, width * unit, height * unit)
                for poly in polygons
            ]
            if "rendered" in outcomes:
                self._bump(report, "pattern")
            elif "too_large" in outcomes:
                self._bump(report, "pattern_too_large")
            else:
                self._bump(report, "pattern_unresolved")

    def _tile_mask(self, number: int) -> Optional[np.ndarray]:
        if number in self._tile_cache:
            return self._tile_cache[number]
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        from matplotlib.patches import Circle, Polygon

        geometry = pattern_geometry(self.libraries.fillgrph, number)
        if geometry is None:
            self._tile_cache[number] = None
            return None
        size = self.tile_pixels
        fig = Figure(figsize=(size / 100.0, size / 100.0), dpi=100, facecolor="none")
        FigureCanvasAgg(fig)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        ax.patch.set_alpha(0)
        for ring in geometry["fill_polygons"]:
            ax.add_patch(Polygon(ring, closed=True, fc="k", ec="none"))
        for points in geometry["polylines"]:
            ax.plot(
                [p[0] for p in points], [p[1] for p in points], "k-", lw=0.8, solid_capstyle="round"
            )
        for cx, cy, radius in geometry["circles"]:
            ax.add_patch(Circle((cx, cy), radius, fc="k", ec="none"))
        for cx, cy, radius, a0, a1 in geometry["arcs"]:
            sweep = (a1 - a0) % 360.0
            angles = [math.radians(a0 + sweep * i / 12.0) for i in range(13)]
            ax.plot(
                [cx + radius * math.cos(t) for t in angles],
                [cy + radius * math.sin(t) for t in angles],
                "k-",
                lw=0.8,
            )
        fig.canvas.draw()
        rgba = np.asarray(fig.canvas.buffer_rgba())
        mask = rgba[..., 3].astype(np.float32) / 255.0
        self._tile_cache[number] = mask
        fig.clear()
        return mask

    def _draw_pattern(
        self, ax: Any, poly: Any, number: int, rgb: RGB, width: float, height: float
    ) -> str:
        mask = self._tile_mask(number)
        if mask is None:
            return "unresolved"
        minx, miny, maxx, maxy = poly.bounds
        x0 = math.floor(minx / width) * width
        y0 = math.floor(miny / height) * height
        nx = max(1, int(math.ceil((maxx - x0) / width)))
        ny = max(1, int(math.ceil((maxy - y0) / height)))
        if nx * ny > self.max_pattern_tiles:
            return "too_large"
        tile = np.zeros((self.tile_pixels, self.tile_pixels, 4), dtype=np.float32)
        tile[..., 0], tile[..., 1], tile[..., 2] = rgb
        tile[..., 3] = mask
        big = np.tile(tile, (ny, nx, 1))
        image = ax.imshow(
            big,
            extent=(x0, x0 + nx * width, y0, y0 + ny * height),
            origin="upper",
            interpolation="bilinear",
            zorder=3,
        )
        clip = self._polygon_patch(poly, facecolor="none", edgecolor="none")
        ax.add_patch(clip)
        image.set_clip_path(clip)
        return "rendered"

    # ------------------------------------------------------------------ WL

    @staticmethod
    def _iter_lines(geom: Any):
        if geom is None or geom.is_empty:
            return
        if geom.geom_type == "LineString":
            yield geom
        elif hasattr(geom, "geoms"):
            for part in geom.geoms:
                yield from GraphicRenderer._iter_lines(part)

    @staticmethod
    def _normalise_rhythm(rhythm: dict) -> dict:
        out = {
            "kind": rhythm.get("kind", "rhythm"),
            "period_mm": float(rhythm.get("period_mm", 1.0)),
            "lines": rhythm.get("lines", []),
            "polylines": [],
            "dots": [],
            "fills": [],
        }
        for values in rhythm.get("lines", []):
            x0, x1 = values[0], values[1]
            y = values[2] if len(values) > 2 else 0.0
            out["polylines"].append([(x0, y), (x1, y)])
        for x, ya, yb in rhythm.get("verticals", []):
            out["polylines"].append([(x, ya), (x, yb)])
        for values in rhythm.get("dots", []):
            x = values[0]
            if len(values) == 2:
                out["dots"].append((x, 0.0, values[1]))
            elif rhythm.get("kind") in (
                "dash_dot_raised",
                "dotline_lib_r",
                "line_slash_dot",
                "filled_rect_dot_bars",
            ):
                out["dots"].append((x, values[1], values[2]))
            else:
                h, top = values[1], values[2]
                ya, yb = (-h, top) if abs(abs(h) - abs(top)) < 1e-9 and h > 0 else (h, top)
                out["polylines"].append([(x, ya), (x, yb)])
        for key in ("fills", "teeth", "rects"):
            out["fills"].extend([[(x, y) for x, y in ring] for ring in rhythm.get(key, [])])
        out["dots"].extend(rhythm.get("circles", []))
        out["polylines"].extend([[tuple(a), tuple(b)] for a, b in rhythm.get("strokes", [])])
        for x, ya, yb in rhythm.get("bars", []):
            out["polylines"].append([(x, ya), (x, yb)])
        for x0, y0, x1, y1 in rhythm.get("slashes", []):
            out["polylines"].append([(x0, y0), (x1, y1)])
        return out

    @staticmethod
    def _payload_rhythm(style: Any) -> Optional[dict]:
        if style is None or not getattr(style, "sublines", None):
            return None
        out = {
            "kind": "payload",
            "period_mm": 1.0,
            "lines": [],
            "polylines": [],
            "dots": [],
            "fills": [],
        }
        for kind, data in style.sublines[0].payload_geometry():
            if kind == "segment":
                x0, y0, x1, y1 = data
                out["polylines"].append([(x0, y0), (x1, y1)])
            elif kind == "polyline":
                out["polylines"].append(list(data))
            elif kind == "fill":
                out["fills"].append(list(data))
            elif kind == "dot":
                x, y, radius, filled = data
                if filled:
                    out["dots"].append((x, y, radius))
                else:
                    out["polylines"].append(
                        [
                            (
                                x + radius * math.cos(2 * math.pi * i / 24.0),
                                y + radius * math.sin(2 * math.pi * i / 24.0),
                            )
                            for i in range(25)
                        ]
                    )
        if not out["polylines"] and not out["dots"] and not out["fills"]:
            return None
        return out

    def _rhythm(self, number: int) -> Optional[dict]:
        if number in self._rhythm_cache:
            return self._rhythm_cache[number]
        style = self.libraries.linesty.decode(number)
        rhythm = feature_rhythm(style, 0) if style is not None else None
        if rhythm is not None:
            result = self._normalise_rhythm(rhythm)
        else:
            result = self._payload_rhythm(style)
        self._rhythm_cache[number] = result
        return result

    def _draw_wl(self, ax: Any, gdf: Any, report: Dict[str, Any]) -> None:
        unit = self._unit(gdf)
        transform = ax.transData
        points_per_unit = abs(
            transform.transform((1.0, 0.0))[0] - transform.transform((0.0, 0.0))[0]
        )
        points_per_unit = max(points_per_unit, 1e-9)
        buffer = _StampBuffer()
        for _, row in gdf.iterrows():
            lines = list(self._iter_lines(row.geometry))
            if not lines:
                continue
            self._bump(report, "drawn")
            color = self._color(row.get("color"), report)
            width_mm = self._float(row.get("width"), 0.1) or 0.1
            line_width = max(width_mm * unit * points_per_unit, self.line_min_pt)
            linetype = self._int(row.get("linetype"))
            aux = self._int(row.get("aux_linetype"))
            xc = self._float(row.get("x_coef"), 1.0) or 1.0
            yc = self._float(row.get("y_coef"), 1.0) or 1.0
            rhythm = self._rhythm(linetype)
            for line in lines:
                points = np.asarray(line.coords, dtype=float)
                self._draw_wl_line(
                    ax,
                    points,
                    rhythm,
                    color,
                    line_width,
                    xc,
                    yc,
                    unit,
                    points_per_unit,
                    buffer,
                    report,
                    prefix="",
                    main=True,
                )
                if aux:
                    aux_rhythm = self._rhythm(aux)
                    aux_number = self._int(row.get("aux_color"))
                    aux_color = self._color(aux_number, report) if aux_number else color
                    self._draw_wl_line(
                        ax,
                        points,
                        aux_rhythm,
                        aux_color,
                        line_width,
                        xc,
                        yc,
                        unit,
                        points_per_unit,
                        buffer,
                        report,
                        prefix="aux_",
                        main=False,
                    )
        self._flush_stamps(ax, buffer, points_per_unit)

    def _draw_wl_line(
        self,
        ax: Any,
        points: np.ndarray,
        rhythm: Optional[dict],
        color: RGB,
        line_width: float,
        xc: float,
        yc: float,
        unit: float,
        points_per_unit: float,
        buffer: _StampBuffer,
        report: Dict[str, Any],
        *,
        prefix: str,
        main: bool,
    ) -> None:
        if len(points) < 2:
            return
        if rhythm is None:
            self._bump(report, prefix + "fallback")
            if self.fallback_to_solid:
                ax.plot(
                    points[:, 0],
                    points[:, 1],
                    color=color,
                    lw=line_width,
                    solid_capstyle="butt",
                    zorder=4,
                )
            return
        if rhythm["kind"] == "solid_pen":
            self._bump(report, prefix + "solid")
            ax.plot(
                points[:, 0],
                points[:, 1],
                color=color,
                lw=line_width,
                solid_capstyle="butt",
                zorder=4,
            )
            return
        self._bump(report, prefix + "pattern")
        if main and rhythm["kind"] == "raised_lines":
            self._draw_raised_parallel(ax, points, rhythm, color, yc, unit, line_width)
        else:
            self._stamp_along(
                points,
                rhythm,
                xc,
                yc,
                unit,
                color,
                line_width,
                self.dot_min_pt / points_per_unit,
                buffer,
            )

    def _draw_raised_parallel(
        self,
        ax: Any,
        points: np.ndarray,
        rhythm: dict,
        color: RGB,
        yc: float,
        unit: float,
        line_width: float,
    ) -> None:
        from shapely.geometry import LineString

        # The base line is the exact original coordinate sequence: no smoothing,
        # simplification, re-sampling or endpoint extrapolation.
        ax.plot(
            points[:, 0], points[:, 1], color=color, lw=line_width, solid_capstyle="butt", zorder=4
        )
        raised = next(
            (float(v[2]) for v in rhythm.get("lines", []) if len(v) > 2 and v[2] != 0.0), 0.1
        )
        offset = raised * yc * unit
        if offset == 0.0:
            return
        curve = LineString(points).offset_curve(offset)
        for part in self._iter_lines(curve):
            xy = np.asarray(part.coords)
            ax.plot(
                xy[:, 0],
                xy[:, 1],
                color=color,
                lw=line_width,
                linestyle=(0, (3, 2)),
                dash_capstyle="butt",
                zorder=4,
            )

    def _stamp_along(
        self,
        points: np.ndarray,
        rhythm: dict,
        xc: float,
        yc: float,
        unit: float,
        color: RGB,
        line_width: float,
        min_radius: float,
        buffer: _StampBuffer,
    ) -> None:
        period = float(rhythm["period_mm"]) * xc * unit
        if period <= 0 or len(points) < 2:
            return
        delta = np.diff(points, axis=0)
        lengths = np.hypot(delta[:, 0], delta[:, 1])
        cumulative = np.concatenate(([0.0], np.cumsum(lengths)))
        total = float(cumulative[-1])
        if total <= 1e-12:
            return
        cycles = np.arange(-1, max(1, int(math.ceil(total / period))) + 1, dtype=float)

        def anchor(distance: np.ndarray):
            distance = np.clip(distance, 0.0, total)
            indices = np.searchsorted(cumulative, distance, side="right") - 1
            indices = np.clip(indices, 0, len(lengths) - 1)
            safe_lengths = np.where(lengths[indices] > 0, lengths[indices], 1.0)
            fraction = (distance - cumulative[indices]) / safe_lengths
            bx = points[indices, 0] + fraction * delta[indices, 0]
            by = points[indices, 1] + fraction * delta[indices, 1]
            tx = delta[indices, 0] / safe_lengths
            ty = delta[indices, 1] / safe_lengths
            return bx, by, tx, ty

        for polyline in rhythm["polylines"]:
            if len(polyline) < 2:
                continue
            px = np.asarray([p[0] for p in polyline], dtype=float) * xc * unit
            py = np.asarray([p[1] for p in polyline], dtype=float) * yc * unit
            for i in range(len(px) - 1):
                s0 = cycles * period + px[i]
                s1 = cycles * period + px[i + 1]
                valid = (np.maximum(s0, s1) > 0.0) & (np.minimum(s0, s1) < total)
                if not np.any(valid):
                    continue
                bx0, by0, tx0, ty0 = anchor(s0[valid])
                bx1, by1, tx1, ty1 = anchor(s1[valid])
                start = np.column_stack((bx0 - ty0 * py[i], by0 + tx0 * py[i]))
                end = np.column_stack((bx1 - ty1 * py[i + 1], by1 + tx1 * py[i + 1]))
                segments = np.stack((start, end), axis=1)
                buffer.segments.append(segments)
                count = len(segments)
                buffer.segment_colors.extend([color] * count)
                buffer.segment_widths.extend([line_width] * count)
        for x, y, radius in rhythm["dots"]:
            distance = cycles * period + x * xc * unit
            valid = (distance >= 0.0) & (distance <= total)
            if not np.any(valid):
                continue
            bx, by, tx, ty = anchor(distance[valid])
            offset = y * yc * unit
            buffer.dots.append(np.column_stack((bx - ty * offset, by + tx * offset)))
            count = int(np.count_nonzero(valid))
            buffer.dot_radii.extend([max(radius * unit, min_radius)] * count)
            buffer.dot_colors.extend([color] * count)
        for ring in rhythm["fills"]:
            if len(ring) < 3:
                continue
            px = np.asarray([p[0] for p in ring], dtype=float) * xc * unit
            py = np.asarray([p[1] for p in ring], dtype=float) * yc * unit
            distances = cycles[:, None] * period + px[None, :]
            valid = ((distances >= 0.0) & (distances <= total)).all(axis=1)
            if not np.any(valid):
                continue
            bx, by, tx, ty = anchor(distances[valid].ravel())
            py2 = np.tile(py, int(np.count_nonzero(valid)))
            x = (bx - ty * py2).reshape((-1, len(px)))
            y = (by + tx * py2).reshape((-1, len(px)))
            for row in np.stack((x, y), axis=-1):
                buffer.fills.append(row)
                buffer.fill_colors.append(color)

    @staticmethod
    def _flush_stamps(ax: Any, buffer: _StampBuffer, points_per_unit: float) -> None:
        from matplotlib.collections import LineCollection, PolyCollection

        if buffer.segments:
            ax.add_collection(
                LineCollection(
                    np.concatenate(buffer.segments, axis=0),
                    colors=buffer.segment_colors,
                    linewidths=buffer.segment_widths,
                    capstyle="butt",
                    zorder=4,
                )
            )
        if buffer.dots:
            points = np.concatenate(buffer.dots, axis=0)
            radii = np.asarray(buffer.dot_radii)
            ax.scatter(
                points[:, 0],
                points[:, 1],
                s=(2 * radii * points_per_unit) ** 2,
                c=buffer.dot_colors,
                linewidths=0,
                zorder=5,
            )
        if buffer.fills:
            ax.add_collection(
                PolyCollection(
                    buffer.fills,
                    facecolors=buffer.fill_colors,
                    edgecolors="none",
                    zorder=3,
                )
            )

    # ------------------------------------------------------------------ WT

    @staticmethod
    def _iter_points(geom: Any):
        if geom is None or geom.is_empty:
            return
        if geom.geom_type == "Point":
            yield geom
        elif hasattr(geom, "geoms"):
            for part in geom.geoms:
                yield from GraphicRenderer._iter_points(part)

    def _symbol(self, number: int) -> Any:
        if number not in self._symbol_cache:
            self._symbol_cache[number] = self.libraries.subgraph.decode(number)
        return self._symbol_cache[number]

    @staticmethod
    def _ring_area(points: Sequence[Tuple[float, float]]) -> float:
        return (
            abs(
                sum(
                    points[i][0] * points[(i + 1) % len(points)][1]
                    - points[(i + 1) % len(points)][0] * points[i][1]
                    for i in range(len(points))
                )
            )
            / 2.0
        )

    def _draw_symbol(
        self,
        ax: Any,
        x: float,
        y: float,
        number: int,
        height_mm: float,
        width_mm: float,
        angle: float,
        stroke_rgb: RGB,
        unit: float,
        report: Dict[str, Any],
    ) -> bool:
        from matplotlib.patches import Polygon

        symbol = self._symbol(number)
        if symbol is None:
            return False
        ca = math.cos(math.radians(angle))
        sa = math.sin(math.radians(angle))
        sx, sy = width_mm * unit, height_mm * unit

        def transform(px: float, py: float) -> Tuple[float, float]:
            return (x + (px * ca - py * sa) * sx, y + (px * sa + py * ca) * sy)

        def circle_points(cx: float, cy: float, radius: float) -> List[Tuple[float, float]]:
            return [
                (
                    cx + radius * math.cos(2 * math.pi * i / 48.0),
                    cy + radius * math.sin(2 * math.pi * i / 48.0),
                )
                for i in range(49)
            ]

        if self.symbol_fills:
            for element in symbol.elements:
                fill_number = element.fill_kind
                if fill_number is None:
                    continue
                fill_rgb = (
                    (0.0, 0.0, 0.0)
                    if fill_number == -1
                    else self._color(fill_number, report, fallback=False)
                )
                if fill_rgb is None:
                    continue
                stop = min(len(symbol.subpaths), element.sub_start + element.sub_count)
                for index in range(max(0, element.sub_start), stop):
                    subpath = symbol.subpaths[index]
                    points = None
                    if subpath.circle is not None:
                        points = circle_points(*subpath.circle)
                    elif subpath.arc is None and subpath.template_digit is None:
                        candidate = subpath.points
                        if (
                            len(candidate) >= 4
                            and self._ring_area(candidate) > 0.005
                            and math.hypot(
                                candidate[0][0] - candidate[-1][0],
                                candidate[0][1] - candidate[-1][1],
                            )
                            <= 0.05
                        ):
                            points = candidate
                    if points:
                        ax.add_patch(
                            Polygon(
                                [transform(px, py) for px, py in points],
                                closed=True,
                                facecolor=fill_rgb,
                                edgecolor="none",
                                zorder=4.8,
                            )
                        )
        for subpath in symbol.subpaths:
            if subpath.circle is not None:
                points = circle_points(*subpath.circle)
            elif subpath.arc is not None:
                cx, cy, radius, a0, a1 = subpath.arc
                sweep = (a1 - a0) % 360.0
                points = [
                    (
                        cx + radius * math.cos(math.radians(a0 + sweep * i / 48.0)),
                        cy + radius * math.sin(math.radians(a0 + sweep * i / 48.0)),
                    )
                    for i in range(49)
                ]
            else:
                points = list(subpath.points)
                if subpath.closed and points:
                    points.append(points[0])
            if not points:
                continue
            transformed = [transform(px, py) for px, py in points]
            if len(transformed) == 1:
                ax.plot(
                    [transformed[0][0]],
                    [transformed[0][1]],
                    ".",
                    color=stroke_rgb,
                    ms=2.0,
                    zorder=5,
                )
            else:
                ax.plot(
                    [p[0] for p in transformed],
                    [p[1] for p in transformed],
                    color=stroke_rgb,
                    lw=self.symbol_line_width_pt,
                    solid_capstyle="round",
                    zorder=5,
                )
        return True

    def _draw_wt(self, ax: Any, gdf: Any, report: Dict[str, Any]) -> None:
        unit = self._unit(gdf)
        for _, row in gdf.iterrows():
            category = self._text(row.get("CHFCEC", "")).strip()
            if category in self.exclude_text_categories:
                self._bump(report, "excluded_text")
                continue
            points = list(self._iter_points(row.geometry))
            if not points:
                continue
            rgb = self._color(row.get("color"), report)
            for point in points:
                if self._int(row.get("point_type")) == 1:
                    ok = self._draw_symbol(
                        ax,
                        point.x,
                        point.y,
                        self._int(row.get("symbol_no")),
                        self._float(row.get("height"), 1.0),
                        self._float(row.get("width"), 1.0),
                        self._float(row.get("angle"), 0.0),
                        rgb,
                        unit,
                        report,
                    )
                    self._bump(report, "symbols" if ok else "symbols_unresolved")
                    if ok:
                        self._bump(report, "drawn")
                else:
                    raw = self._text(row.get("CHFCED", ""))
                    label = _annotation_to_mathtext(raw)
                    if not label:
                        self._bump(report, "text_skipped")
                        continue
                    height = self._float(row.get("height"), 2.0)
                    scale = self.text_scale * self._float(
                        self.text_category_scales.get(category), 1.0
                    )
                    font_size = max(height * MM_TO_PT * scale, 0.8)
                    ax.text(
                        point.x,
                        point.y,
                        label,
                        fontsize=font_size,
                        color=rgb,
                        ha="left",
                        va="baseline",
                        rotation=self._float(row.get("angle"), 0.0),
                        rotation_mode="anchor",
                        fontfamily=self.text_font_family,
                        zorder=6,
                    )
                    self._bump(report, "text")
                    self._bump(report, "drawn")


_GREEK_MATHTEXT = {
    "α": r"\alpha{}",
    "β": r"\beta{}",
    "γ": r"\gamma{}",
    "δ": r"\delta{}",
    "ε": r"\epsilon{}",
    "η": r"\eta{}",
    "θ": r"\theta{}",
    "ι": r"\iota{}",
    "κ": r"\kappa{}",
    "λ": r"\lambda{}",
    "μ": r"\mu{}",
    "ν": r"\nu{}",
    "ξ": r"\xi{}",
    "ο": "o",
    "π": r"\pi{}",
    "ρ": r"\rho{}",
    "σ": r"\sigma{}",
    "τ": r"\tau{}",
    "υ": r"\upsilon{}",
    "φ": r"\phi{}",
    "χ": r"\chi{}",
    "ψ": r"\psi{}",
    "ω": r"\omega{}",
}


def _annotation_to_mathtext(code: str) -> str:
    """Convert MapGIS ``#-/#+/#=`` and arrow annotation controls to mathtext."""
    if not code:
        return ""
    text = str(code)
    for char in ("\x00", "\x01", "\x02", "\x03", " "):
        text = text.replace(char, "")
    text = text.replace("#-", "↓").replace("#+", "↑").replace("#=", "→").strip()
    if not text or not any(mark in text for mark in "→↓↑"):
        return text
    groups: List[Tuple[str, str]] = []
    mode, buffer = "normal", ""
    for char in text:
        if char in "→↓↑":
            if buffer:
                groups.append((mode, buffer))
                buffer = ""
            mode = {"→": "normal", "↓": "sub", "↑": "sup"}[char]
        else:
            buffer += char
    if buffer:
        groups.append((mode, buffer))
    segments: List[str] = []
    for mode, value in groups:
        escaped = "".join(_GREEK_MATHTEXT.get(char, char) for char in value)
        if not escaped:
            continue
        if mode in ("sub", "sup"):
            prefix = "_" if mode == "sub" else "^"
            if segments and segments[-1][:1] == prefix:
                # Adjacent same-type scripts are nested in MapGIS.  Emitting
                # X^{a}^{b} would raise a mathtext ParseFatalException.
                segments[-1] = prefix + "{" + segments[-1][1:] + prefix + "{" + escaped + "}}"
            else:
                segments.append(prefix + "{" + escaped + "}")
        else:
            segments.append(escaped)
    return "$\\mathrm{" + "".join(segments) + "}$" if segments else ""


def render_graphic_map(
    layers: Sequence[Any],
    slib: Union[PathLike, GraphicLibraries],
    output: Optional[PathLike] = None,
    **kwargs: Any,
) -> GraphicRenderResult:
    """Convenience API for one-shot graphic-library rendering.

    ``slib`` may be an SLIB directory or an existing :class:`GraphicLibraries`.
    Renderer options (``scale``, ``map_units_per_mm``, ``color_overrides``, …)
    and output options (``figsize``, ``dpi``, ``margin``, ``title``) are passed
    as keyword arguments.

    Example
    -------
    >>> result = render_graphic_map(
    ...     ["area.wp", "boundary.wl", "labels.wt"], "SLIB", "map.png",
    ...     scale=250000, dpi=300,
    ... )  # doctest: +SKIP
    """
    output_keys = {"figsize", "dpi", "margin", "title"}
    render_options = {key: kwargs.pop(key) for key in list(kwargs) if key in output_keys}
    libraries = (
        slib if isinstance(slib, GraphicLibraries) else GraphicLibraries.from_directory(slib)
    )
    renderer = GraphicRenderer(libraries, **kwargs)
    return renderer.render(layers, output, **render_options)


__all__ = [
    "GraphicLibraries",
    "GraphicRenderer",
    "GraphicRenderResult",
    "render_graphic_map",
]
