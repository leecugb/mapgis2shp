# SPDX-License-Identifier: Apache-2.0
"""Render MapGIS vectors with their original MapGIS graphic libraries.

The public entry points are :class:`GraphicLibraries`,
:class:`GraphicRenderer`, and :func:`render_graphic_map`.  Matplotlib is an
optional dependency and is imported only when rendering is requested.

The renderer consumes library geometry rather than replacing it with thematic
styles: WP fill/pattern records, WL line-style rhythms, and WT subgraph/text
records. WL geometry first uses adjudicated variants where they have already
been verified against MapGIS output, then falls back to the library's direct
rhythm structure or the selected subline's ``parameter_geometry()`` for other
records. Multiple solid pens are retained as overlays, while alternative
non-solid sublines are not merged. Per-style-number adjudication is not part
of the generic fallback. Coordinates always come from the vector features.
In particular, line-style stamps follow the original polyline and never extend
its endpoints.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import numpy as np

from pymapgis.colorlib import ColorLib
from pymapgis.fillgrph import FillgrphLib, pattern_geometry
from pymapgis.linesty import (
    _RHYTHM_SUPPORTED_NOS,
    LinestyLib,
    _aux_selects_subline,
    feature_rhythm,
)
from pymapgis.pcolor import PcolorLib
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
    pcolor: Optional[PcolorLib] = None
    directory: Optional[Path] = None

    @classmethod
    def from_directory(
        cls, directory: PathLike, *, channel_order: str = "KCMY"
    ) -> "GraphicLibraries":
        """Load ``LINESTY.lib``, ``Subgraph.lib``, ``Fillgrph.lib`` and
        ``Colorlib.lib`` from *directory*.

        ``channel_order`` is forwarded to both colour-library parsers for
        installations with a verified alternate channel model. A single error
        lists every missing library instead of failing one file at a time.
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
            color=ColorLib(str(root / "Colorlib.lib"), channel_order=channel_order),
            pcolor=(PcolorLib(str(root / "Pcolor.lib"), channel_order=channel_order)
                    if (root / "Pcolor.lib").is_file() else None),
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
    dot_filled: List[bool] = field(default_factory=list)
    dot_widths: List[float] = field(default_factory=list)
    fills: List[np.ndarray] = field(default_factory=list)
    fill_colors: List[RGB] = field(default_factory=list)


class GraphicRenderer:
    """Render WL/WP/WT data using original MapGIS graphic parameters.

    Parameters
    ----------
    libraries:
        A :class:`GraphicLibraries` instance.
    fill_library:
        Library used for WP fill colours. ``"auto"`` (default) uses Pcolor
        when available and Colorlib otherwise; ``"pcolor"`` requires Pcolor;
        ``"color"`` explicitly selects the legacy Colorlib-only comparison.
        The other colour roles always use Colorlib.
    scale:
        Map scale denominator.  At 1:250000, one paper millimetre represents
        250 metres on the ground.
    map_units_per_mm:
        Explicit paper-mm to map-coordinate conversion.  Normally this is
        inferred from each layer's CRS.  It is required for layers without a
        CRS and is useful for local engineering coordinate systems.
    color_overrides:
        Optional ``{color_number: (r, g, b)}`` mapping for installation-local
        or extended Pcolor entries. Applied to WP ``fill_color`` only; pattern,
        line, auxiliary and point colours resolve directly through Colorlib.
        RGB components must be in the 0–1 range. No inferred extended colours
        are enabled by default. Overrides are for thematic/comparison output,
        not for original graphic-library rendering.
    unit_color_overrides:
        Optional ``{normalised_unit_code: (r, g, b)}`` map for verified
        unit-specific corrections (for example ``Qp3pal``). A matching unit
        takes precedence over its numeric fill colour and numeric overrides.
        No geological recolouring is enabled without this explicit map.
        Overrides are for thematic/comparison output only, never for original
        graphic-library rendering.
    unit_code_fields:
        Attribute fields searched in order for a unit code. Defaults to
        ``("QDUECC", "QDUECD")``.
    fallback_color:
        Colour used for unresolved feature colours; unresolved library-defined
        symbol fills are instead left unfilled.
    fallback_to_solid:
        Draw an original-coordinate solid line when a line style cannot be
        decoded.  Every such feature is counted as ``fallback`` in the report.
    max_pattern_bytes:
        Maximum size of one expanded RGBA pattern image. The default is
        128 MiB; larger requests are reported as ``pattern_too_large`` before
        allocation.
    max_pattern_cycles:
        Maximum repeat cycles for one WL feature. Excessively dense patterns
        are skipped and counted as ``cycle_limit`` in the layer report.
    symbol_fills:
        Consume adjudicated Subgraph ``Element.fill_kind`` fills.
    polygon_labels:
        Draw one complete label per polygon from its unit-code attributes at
        ``representative_point()``, following the geosciml4china scheme.
    polygon_label_fields:
        Attribute fields searched in order for the complete polygon label.
        Defaults to ``("QDUECC_eff", "QDUECC", "QDUECD")``.
    polygon_label_fontsize:
        Polygon-label size in typographic points; default 4.5 pt.
    polygon_label_scale:
        Multiplier applied to ``polygon_label_fontsize``. The default 0.70
        produces 3.15 pt from the default base size.
    exclude_text_categories:
        Optional CHFCEC categories to omit. Defaults to ``{"代号"}`` so
        fragmented WT unit-code annotations are not duplicated over the
        polygon-derived labels. Use ``exclude_text_categories=()`` together
        with ``polygon_labels=False`` for the legacy WT-only behaviour.
    text_category_scales:
        Optional CHFCEC-specific font-size multipliers.
    attitude_text_scale:
        Additional multiplier for the CHFCEC categories ``产状``、``断层产状``
        and ``断层辅助点``. The default 0.30 is compounded with ``text_scale``
        and any category-specific multiplier.
    text_font_family:
        Optional Matplotlib font family or fallback list for text annotations.
    native_text_layout:
        Place characters using the stored ``width + spacing`` advance, scaled
        by the same text multiplier as the font. Script size/baseline and font
        substitution remain display approximations.
    font_zh_map / font_en_map:
        Optional ``{native_font_number: Matplotlib_font_family}`` mappings.
        Unknown mapped numbers are reported as ``unknown_fonts``.
    font_style_map:
        Optional ``{native_font_style: {Matplotlib_text_keyword: value}}`` map.

    Notes
    -----
    A renderer caches decoded styles, symbols and pattern tiles.  Create one
    renderer per library set and reuse it for related layers.
    """

    def __init__(
        self,
        libraries: GraphicLibraries,
        *,
        fill_library: str = "auto",
        scale: float = 250000.0,
        map_units_per_mm: Optional[float] = None,
        color_overrides: Optional[Mapping[int, RGB]] = None,
        unit_color_overrides: Optional[Mapping[str, RGB]] = None,
        unit_code_fields: Sequence[str] = ("QDUECC", "QDUECD"),
        fallback_color: RGB = (0.85, 0.85, 0.85),
        line_min_pt: float = 0.05,
        dot_min_pt: float = 0.2,
        symbol_line_width_pt: float = 0.25,
        polygon_edge_color: str = "none",
        polygon_edge_width_pt: float = 0.0,
        tile_pixels: int = 26,
        max_pattern_tiles: int = 40000,
        max_pattern_bytes: int = 128 * 1024 ** 2,
        max_pattern_cycles: int = 100000,
        fallback_to_solid: bool = True,
        symbol_fills: bool = True,
        polygon_labels: bool = True,
        polygon_label_fields: Sequence[str] = ("QDUECC_eff", "QDUECC", "QDUECD"),
        polygon_label_fontsize: float = 4.5,
        polygon_label_scale: float = 0.7,
        exclude_text_categories: Sequence[str] = ("代号",),
        text_category_scales: Optional[Mapping[str, float]] = None,
        attitude_text_scale: float = 0.3,
        text_scale: float = 1.0,
        text_font_family: Any = None,
        native_text_layout: bool = True,
        font_zh_map: Optional[Mapping[int, Any]] = None,
        font_en_map: Optional[Mapping[int, Any]] = None,
        font_style_map: Optional[Mapping[int, Mapping[str, Any]]] = None,
    ) -> None:
        if scale <= 0:
            raise ValueError("scale must be positive")
        if fill_library not in {"auto", "color", "pcolor"}:
            raise ValueError("fill_library must be 'auto', 'color' or 'pcolor'")
        if fill_library == "pcolor" and libraries.pcolor is None:
            raise ValueError("fill_library='pcolor' requires Pcolor.lib")
        self.fill_library = fill_library
        if map_units_per_mm is not None and map_units_per_mm <= 0:
            raise ValueError("map_units_per_mm must be positive")
        if tile_pixels < 4:
            raise ValueError("tile_pixels must be at least 4")
        if max_pattern_tiles < 1:
            raise ValueError("max_pattern_tiles must be positive")
        if max_pattern_bytes < 1:
            raise ValueError("max_pattern_bytes must be positive")
        if max_pattern_cycles < 1:
            raise ValueError("max_pattern_cycles must be positive")
        self.libraries = libraries
        self.scale = float(scale)
        self.map_units_per_mm = map_units_per_mm
        self.color_overrides = {
            int(no): self._validate_rgb(rgb) for no, rgb in (color_overrides or {}).items()
        }
        self.unit_color_overrides = {
            self._normalise_unit_code(code): self._validate_rgb(rgb)
            for code, rgb in (unit_color_overrides or {}).items()
        }
        self.unit_code_fields = self._string_tuple(unit_code_fields)
        self.fallback_color = self._validate_rgb(fallback_color)
        self.line_min_pt = float(line_min_pt)
        self.dot_min_pt = float(dot_min_pt)
        self.symbol_line_width_pt = float(symbol_line_width_pt)
        self.polygon_edge_color = polygon_edge_color
        self.polygon_edge_width_pt = float(polygon_edge_width_pt)
        self.tile_pixels = int(tile_pixels)
        self.max_pattern_tiles = int(max_pattern_tiles)
        self.max_pattern_bytes = int(max_pattern_bytes)
        self.max_pattern_cycles = int(max_pattern_cycles)
        self.fallback_to_solid = bool(fallback_to_solid)
        self.symbol_fills = bool(symbol_fills)
        self.polygon_labels = bool(polygon_labels)
        self.polygon_label_fields = self._string_tuple(polygon_label_fields)
        self.polygon_label_fontsize = float(polygon_label_fontsize)
        if self.polygon_label_fontsize <= 0:
            raise ValueError("polygon_label_fontsize must be positive")
        self.polygon_label_scale = float(polygon_label_scale)
        if not math.isfinite(self.polygon_label_scale) or self.polygon_label_scale <= 0:
            raise ValueError("polygon_label_scale must be positive and finite")
        self.exclude_text_categories = {
            str(x).strip() for x in self._string_tuple(exclude_text_categories)
        }
        self.text_category_scales = {
            str(category): float(value)
            for category, value in (text_category_scales or {}).items()
        }
        if any(
            not math.isfinite(value) or value <= 0
            for value in self.text_category_scales.values()
        ):
            raise ValueError("text_category_scales must contain positive finite values")
        self.attitude_text_scale = float(attitude_text_scale)
        if not math.isfinite(self.attitude_text_scale) or self.attitude_text_scale <= 0:
            raise ValueError("attitude_text_scale must be positive and finite")
        self.text_scale = float(text_scale)
        if not math.isfinite(self.text_scale) or self.text_scale <= 0:
            raise ValueError("text_scale must be positive and finite")
        self.text_font_family = text_font_family
        self.native_text_layout = bool(native_text_layout)
        self.font_zh_map = {int(code): value for code, value in (font_zh_map or {}).items()}
        self.font_en_map = {int(code): value for code, value in (font_en_map or {}).items()}
        self.font_style_map = {
            int(code): dict(options) for code, options in (font_style_map or {}).items()
        }
        self._rhythm_cache: Dict[Tuple[int, int], Optional[dict]] = {}
        self._line_style_cache: Dict[int, Any] = {}
        self._symbol_cache: Dict[int, Any] = {}
        self._tile_cache: Dict[int, Optional[np.ndarray]] = {}

    @staticmethod
    def _string_tuple(values: Union[str, Sequence[str]]) -> Tuple[str, ...]:
        """Treat a bare string as one field/category, not as characters."""
        return (values,) if isinstance(values, str) else tuple(values)

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
        """Draw one layer onto an Axes whose extent is already established.

        GeoDataFrames may set ``attrs['source']`` for report attribution and
        ``attrs['kind']`` to ``wl``/``wp``/``wt`` when geometry is empty.
        """
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
            metadata = getattr(gdf, "attrs", {}) or {}
            inferred = str(metadata.get("kind", ""))
            source = str(metadata.get("source", "<GeoDataFrame>"))
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

    @staticmethod
    def _normalise_unit_code(value: Any) -> str:
        """Remove MapGIS script controls without changing unit letters/digits."""
        text = GraphicRenderer._text(value)
        text = text.replace("#-", "↓").replace("#+", "↑").replace("#=", "→")
        return re.sub(r"[\x00-\x03\s→↓↑]", "", text)

    def _unit_code(self, row: Any) -> str:
        for field_name in self.unit_code_fields:
            code = self._normalise_unit_code(row.get(field_name, ""))
            if code:
                return code
        return ""

    def _unit_label(self, row: Any) -> str:
        for field_name in self.polygon_label_fields:
            label = self._text(row.get(field_name, "")).strip()
            if label:
                return label
        return ""

    def _color(
        self,
        number: Any,
        report: Dict[str, Any],
        *,
        fallback: bool = True,
        role: str = "feature",
    ) -> Optional[RGB]:
        no = self._int(number)
        # Installation-specific comparison overrides apply only to WP fills.
        # Native WP fills use Pcolor in auto mode; every other role uses
        # Colorlib and never inherits a fill override.
        if role == "fill" and no in self.color_overrides:
            key = str(no)
            report["overridden_colors"][key] = report["overridden_colors"].get(key, 0) + 1
            return self.color_overrides[no]
        use_pcolor = role == "fill" and (
            self.fill_library == "pcolor"
            or (self.fill_library == "auto" and self.libraries.pcolor is not None)
        )
        library = self.libraries.pcolor if use_pcolor else self.libraries.color
        rgb = library.rgb01(no) if library is not None else None
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

    def _draw_polygon_label(
        self, ax: Any, row: Any, geom: Any, report: Dict[str, Any]
    ) -> None:
        """Draw a complete unit code using the geosciml4china polygon scheme."""
        if not self.polygon_labels:
            return
        raw_label = self._unit_label(row)
        label = _annotation_to_mathtext(raw_label)
        if not label:
            return
        point = geom.representative_point()
        has_greek = any("Ͱ" <= char <= "Ͽ" for char in raw_label)
        kwargs = {"fontfamily": "Times New Roman"} if has_greek else {}
        ax.text(
            point.x,
            point.y,
            label,
            fontsize=self.polygon_label_fontsize * self.polygon_label_scale,
            ha="center",
            va="center",
            zorder=12,
            parse_math=label.startswith("$\\mathrm{"),
            bbox={"boxstyle": "round,pad=0.05", "fc": "white", "ec": "none", "alpha": 0.5},
            **kwargs,
        )
        self._bump(report, "polygon_label")

    def _draw_wp(self, ax: Any, gdf: Any, report: Dict[str, Any]) -> None:
        unit = self._unit(gdf)
        fill_patches = []
        for _, row in gdf.iterrows():
            if self._int(row.get("class", 1), 1) == 0:
                self._bump(report, "excluded_class")
                continue
            polygons = list(self._iter_polygons(row.geometry))
            if not polygons:
                continue
            self._bump(report, "drawn")
            report["holes"] = int(report.get("holes", 0)) + sum(len(p.interiors) for p in polygons)
            unit_code = self._unit_code(row)
            rgb = self.unit_color_overrides.get(unit_code)
            if rgb is not None:
                counts = report.setdefault("unit_overrides", {})
                counts[unit_code] = counts.get(unit_code, 0) + 1
            else:
                rgb = self._color(row.get("fill_color"), report, role="fill")
            for poly in polygons:
                fill_patches.append(
                    self._polygon_patch(
                        poly,
                        facecolor=rgb,
                        edgecolor=self.polygon_edge_color,
                        linewidth=self.polygon_edge_width_pt,
                        zorder=2,
                    )
                )
            self._draw_polygon_label(ax, row, row.geometry, report)
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
        if fill_patches:
            from matplotlib.collections import PatchCollection

            collection = PatchCollection(fill_patches, match_original=True)
            collection.set_zorder(2)
            ax.add_collection(collection)

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
        # A one-inch square at dpi=size has exact pixel dimensions. Using
        # size/100 inches at dpi=100 can round down to size-1 on some
        # Matplotlib versions.
        fig = Figure(figsize=(1.0, 1.0), dpi=size, facecolor="none")
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
                [p[0] for p in points],
                [p[1] for p in points],
                "k-",
                lw=0.8 * 100.0 / size,
                solid_capstyle="round",
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
                lw=0.8 * 100.0 / size,
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
        tile_count = nx * ny
        if tile_count > self.max_pattern_tiles:
            return "too_large"
        rgba_bytes = (
            tile_count * self.tile_pixels * self.tile_pixels * 4 * np.dtype(np.float32).itemsize
        )
        if rgba_bytes > self.max_pattern_bytes:
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
    def _substring_parts(curve: Any, start: float, end: float) -> List[Any]:
        """Return LineString slices for either single- or multi-part curves."""
        from shapely.ops import substring

        if start >= end or curve.is_empty:
            return []
        if curve.geom_type == "LineString":
            return [substring(curve, start, end)]
        parts = []
        offset = 0.0
        for line in getattr(curve, "geoms", []):
            if line.geom_type != "LineString":
                continue
            length = line.length
            lo = max(0.0, start - offset)
            hi = min(length, end - offset)
            if hi > lo:
                parts.append(substring(line, lo, hi))
            offset += length
        return parts

    @staticmethod
    def _normalise_rhythm(rhythm: dict) -> dict:
        out = {
            "kind": rhythm.get("kind", "rhythm"),
            "period_mm": float(rhythm.get("period_mm", 1.0)),
            "lines": rhythm.get("lines", []),
            "polylines": [],
            "dots": [],
            "fills": [],
            "unknown_fills": 0,
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
                "mixed_dash",
            ):
                dot = (x, values[1], values[2])
                if len(values) > 3:
                    dot += (bool(values[3]),)
                out["dots"].append(dot)
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
    def _payload_rhythm(style: Any, subline: int = 0) -> Optional[dict]:
        """Build a rhythm from stored parameter geometry.

        Non-solid sublines are alternative variants: consume the selected one
        (zero-based) rather than merging variants. Multiple solid pen records
        are genuine overlays and are all retained.
        """
        if style is None or not getattr(style, "sublines", None):
            return None
        sublines = style.sublines
        if not all(item.is_solid for item in sublines):
            if not 0 <= subline < len(sublines):
                return None
            sublines = [sublines[subline]]
        out = {
            "kind": "payload",
            "period_mm": 0.0,
            "lines": [],
            "polylines": [],
            "dots": [],
            "fills": [],
            "unknown_fills": 0,
        }
        periods = []
        for subline in sublines:
            period = subline.period_mm
            if period is not None and period > 0:
                periods.append(period)
            for kind, data in subline.parameter_geometry():
                if kind == "gap":
                    continue
                if kind == "segment":
                    x0, y0, x1, y1 = data
                    out["polylines"].append([(x0, y0), (x1, y1)])
                elif kind == "polyline":
                    out["polylines"].append(list(data))
                elif kind == "fill":
                    out["fills"].append(list(data))
                elif kind == "dot":
                    x, y, radius, filled = data
                    if filled is True:
                        out["dots"].append((x, y, radius))
                    elif filled is False:
                        out["dots"].append((x, y, radius, False))
                    else:
                        # Unknown fill remains an outline; no radius/unit/style
                        # adjudication is substituted for missing evidence.
                        out["unknown_fills"] += 1
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
        xs = [p[0] for line in out["polylines"] for p in line]
        xs.extend(p[0] for ring in out["fills"] for p in ring)
        xs.extend(dot[0] for dot in out["dots"])
        # Offset describes layout position, while payload endpoints describe
        # the actual extent. Both are required for a non-gapped base segment.
        if xs:
            # Preserve positive offsets while also accounting for payload that
            # extends left of the repeat origin.
            extent = max(xs) - min(0.0, min(xs))
            out["period_mm"] = max(periods + [extent])
        else:
            out["period_mm"] = max(periods + [1.0])
        if out["period_mm"] <= 0:
            out["period_mm"] = 1.0
        return out

    def _line_style(self, number: int) -> Any:
        if number not in self._line_style_cache:
            self._line_style_cache[number] = self.libraries.linesty.decode(number)
        return self._line_style_cache[number]

    def _rhythm(self, number: int, aux: int = 0) -> Optional[dict]:
        """Resolve verified variants first, then structural library geometry."""
        key = (number, aux)
        if key in self._rhythm_cache:
            return self._rhythm_cache[key]
        style = self._line_style(number)
        result = None
        if style is not None and getattr(style, "sublines", None):
            if style.no in _RHYTHM_SUPPORTED_NOS:
                # Adjudicated variants have already been verified against
                # MapGIS output. Unsupported aux variants stay unresolved
                # rather than silently falling back to a different shape.
                rhythm = feature_rhythm(style, aux)
                if rhythm is not None:
                    result = self._normalise_rhythm(rhythm)
            elif len(style.sublines) == 1 and style.sublines[0].is_solid:
                result = self._normalise_rhythm(
                    {"kind": "solid_pen", "lines": [], "period_mm": 1.0}
                )
            else:
                variant = (
                    _aux_selects_subline(style, aux)
                    and not all(item.is_solid for item in style.sublines)
                )
                native = None if variant else style.rhythm()
                if native and native.get("segments"):
                    result = self._normalise_rhythm(
                        {
                            "kind": "inline_dash",
                            "lines": native["segments"],
                            "period_mm": native["period_mm"],
                        }
                    )
                else:
                    result = self._payload_rhythm(style, aux if variant else 0)
        self._rhythm_cache[key] = result
        return result

    def _draw_wl(self, ax: Any, gdf: Any, report: Dict[str, Any]) -> None:
        unit = self._unit(gdf)
        transform = ax.transData
        pixels_per_unit = abs(
            transform.transform((1.0, 0.0))[0] - transform.transform((0.0, 0.0))[0]
        )
        pixels_per_unit = max(pixels_per_unit, 1e-9)
        # transData yields display pixels, while Matplotlib line widths and
        # scatter areas use typographic points (1/72 inch).
        points_per_unit = pixels_per_unit * 72.0 / ax.figure.dpi
        buffer = _StampBuffer()
        for _, row in gdf.iterrows():
            lines = list(self._iter_lines(row.geometry))
            if not lines:
                continue
            self._bump(report, "drawn")
            color = self._color(row.get("color"), report)
            width_mm = self._float(row.get("width"), 0.1)
            line_width = max(width_mm * unit * points_per_unit, self.line_min_pt)
            linetype = self._int(row.get("linetype"))
            aux = self._int(row.get("aux_linetype"))
            if self._int(row.get("aux_flag"), 0) != 0:
                aux = 0
            xc = self._float(row.get("x_coef"), 1.0)
            yc = self._float(row.get("y_coef"), 1.0)
            transparent_fills = self._int(row.get("transparent"), 0) != 0 and all(
                abs(component - 1.0) <= 1e-12 for component in color
            )
            style = self._line_style(linetype)
            independent_aux = bool(aux) and not _aux_selects_subline(style, aux)
            rhythm = self._rhythm(linetype, aux)
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
                    transparent_fills=transparent_fills,
                )
                if independent_aux:
                    aux_rhythm = self._rhythm(aux)
                    aux_number = self._int(row.get("aux_color"))
                    aux_color = self._color(aux_number, report) if aux_number else color
                    aux_transparent_fills = self._int(row.get("transparent"), 0) != 0 and all(
                        abs(component - 1.0) <= 1e-12 for component in aux_color
                    )
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
                        transparent_fills=aux_transparent_fills,
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
        transparent_fills: bool = False,
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
        before = (
            len(buffer.segments),
            len(buffer.dots),
            len(buffer.fills),
            len(ax.lines),
        )
        unknown_fills = int(rhythm.get("unknown_fills", 0))
        if unknown_fills:
            self._bump(report, prefix + "unknown_fill", unknown_fills)
        if rhythm["kind"] == "raised_lines":
            outcome = self._draw_raised_parallel(
                ax, points, rhythm, color, xc, yc, unit, line_width
            )
        else:
            outcome = self._stamp_along(
                points,
                rhythm,
                xc,
                yc,
                unit,
                color,
                line_width,
                self.dot_min_pt / points_per_unit,
                buffer,
                transparent_fills=transparent_fills,
            )
        after = (
            len(buffer.segments),
            len(buffer.dots),
            len(buffer.fills),
            len(ax.lines),
        )
        if outcome == "too_many_cycles":
            self._bump(report, prefix + "cycle_limit")
        elif before == after:
            self._bump(report, prefix + "empty_pattern")
        else:
            self._bump(report, prefix + "pattern")

    def _draw_raised_parallel(
        self,
        ax: Any,
        points: np.ndarray,
        rhythm: dict,
        color: RGB,
        xc: float,
        yc: float,
        unit: float,
        line_width: float,
    ) -> Optional[str]:
        """Draw raised-line variants using library lengths on the source curve.

        Unlike a screen-space dash pattern, every interval here is a paper-mm
        interval from ``LINESTY.lib``. Base-chainage interpolation preserves the
        original vertices; offset curves are used only for non-zero library y
        levels, with endpoints mapped back from base chainage.
        """
        from shapely.geometry import LineString

        base = LineString(points)
        total = base.length
        period = float(rhythm["period_mm"]) * xc * unit
        if total <= 1e-12 or period <= 0:
            return None
        ratio = total / period
        if not math.isfinite(ratio) or ratio + 4 > self.max_pattern_cycles:
            return "too_many_cycles"
        curves = {}
        for values in rhythm.get("lines", []):
            if len(values) < 2:
                continue
            x0, x1 = float(values[0]), float(values[1])
            y = float(values[2]) if len(values) > 2 else 0.0
            start = x0 * xc * unit
            end = x1 * xc * unit
            if start == end:
                continue
            offset = y * yc * unit
            if offset not in curves:
                curves[offset] = base if offset == 0.0 else base.offset_curve(offset)
            curve = curves[offset]
            if curve.is_empty:
                continue
            first = math.floor(-start / period)
            last = math.ceil((total - start) / period)
            for cycle in range(first, last + 1):
                a = start + cycle * period
                b = end + cycle * period
                lo = max(0.0, min(a, b))
                hi = min(total, max(a, b))
                if hi <= lo:
                    continue
                if offset == 0.0:
                    parts = self._substring_parts(base, lo, hi)
                else:
                    # Pattern phase is measured on the original line, not on
                    # the longer/shorter offset curve.
                    c0 = curve.project(base.interpolate(lo))
                    c1 = curve.project(base.interpolate(hi))
                    parts = self._substring_parts(curve, min(c0, c1), max(c0, c1))
                for part in parts:
                    for line in self._iter_lines(part):
                        xy = np.asarray(line.coords)
                        if len(xy) >= 2:
                            ax.plot(
                                xy[:, 0], xy[:, 1], color=color, lw=line_width,
                                solid_capstyle="butt", zorder=4,
                            )

    @staticmethod
    def _clip_fill_to_range(
        distances: np.ndarray, offsets: np.ndarray, total: float
    ) -> List[np.ndarray]:
        """Clip one fill ring to the source-line chainage interval."""
        points = np.column_stack((distances, offsets))
        if len(points) < 3 or not np.all(np.isfinite(points)):
            return []
        if not np.array_equal(points[0], points[-1]):
            points = np.vstack((points, points[0]))
        x, y = points[:, 0], points[:, 1]
        signed_twice_area = np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))
        if abs(signed_twice_area) <= 1e-18:
            return []
        from shapely.errors import GEOSException
        from shapely.geometry import Polygon
        from shapely.ops import clip_by_rect
        from shapely.validation import make_valid

        margin = max(float(np.ptp(offsets)), 1.0)
        try:
            polygon = Polygon(points)
            if not polygon.is_valid:
                polygon = make_valid(polygon)
            clipped = clip_by_rect(
                polygon,
                0.0,
                float(np.min(offsets)) - margin,
                total,
                float(np.max(offsets)) + margin,
            )
        except (GEOSException, ValueError):
            return []
        if clipped.is_empty:
            return []
        candidates = [clipped] if clipped.geom_type == "Polygon" else list(
            getattr(clipped, "geoms", [])
        )
        return [
            np.asarray(part.exterior.coords)
            for part in candidates
            if part.geom_type == "Polygon" and part.area > 0
        ]

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
        transparent_fills: bool = False,
    ) -> Optional[str]:
        period = float(rhythm["period_mm"]) * xc * unit
        if period <= 0 or len(points) < 2:
            return None
        delta = np.diff(points, axis=0)
        lengths = np.hypot(delta[:, 0], delta[:, 1])
        cumulative = np.concatenate(([0.0], np.cumsum(lengths)))
        total = float(cumulative[-1])
        if total <= 1e-12:
            return None
        ratio = total / period
        if not math.isfinite(ratio) or ratio + 2 > self.max_pattern_cycles:
            return "too_many_cycles"
        cycles = np.arange(-1, max(1, int(math.ceil(ratio))) + 1, dtype=float)

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

        offset_curves = {}
        base = None
        for polyline in rhythm["polylines"]:
            if len(polyline) < 2:
                continue
            px = np.asarray([p[0] for p in polyline], dtype=float) * xc * unit
            py = np.asarray([p[1] for p in polyline], dtype=float) * yc * unit
            for i in range(len(px) - 1):
                s0 = cycles * period + px[i]
                s1 = cycles * period + px[i + 1]
                if px[i] == px[i + 1]:
                    # A vertical tick has no longitudinal length. Keep its
                    # origin instance, but do not duplicate it at a closed
                    # line's end seam.
                    valid = (s0 >= 0.0) & (s0 < total)
                else:
                    valid = (np.maximum(s0, s1) > 0.0) & (np.minimum(s0, s1) < total)
                if not np.any(valid):
                    continue
                if px[i] != px[i + 1] and py[i] == 0.0 and py[i + 1] == 0.0:
                    # Zero-offset strokes (including the 38|2 solid baseline)
                    # must follow every source vertex, not become straight
                    # chords between rhythm endpoints.
                    for d0, d1 in zip(s0[valid], s1[valid]):
                        lo = max(0.0, min(d0, d1))
                        hi = min(total, max(d0, d1))
                        if hi <= lo:
                            continue
                        bx0, by0, _, _ = anchor(np.asarray([lo]))
                        bx1, by1, _, _ = anchor(np.asarray([hi]))
                        start = np.asarray([bx0[0], by0[0]])
                        end = np.asarray([bx1[0], by1[0]])
                        interior = points[(cumulative > lo) & (cumulative < hi)]
                        xy = np.concatenate(([start], interior, [end]), axis=0)
                        if d0 > d1:
                            xy = xy[::-1]
                        segments = np.stack((xy[:-1], xy[1:]), axis=1)
                        segments = segments[np.any(segments[:, 0] != segments[:, 1], axis=1)]
                        if not len(segments):
                            continue
                        buffer.segments.append(segments)
                        count = len(segments)
                        buffer.segment_colors.extend([color] * count)
                        buffer.segment_widths.extend([line_width] * count)
                    continue
                if px[i] != px[i + 1] and py[i] == py[i + 1]:
                    # Constant-offset parallel strokes follow the complete
                    # offset curve too; only zero-offset lines use raw points.
                    from shapely.geometry import LineString

                    if base is None:
                        base = LineString(points)
                    offset = float(py[i])
                    if offset not in offset_curves:
                        offset_curves[offset] = base.offset_curve(offset)
                    curve = offset_curves[offset]
                    if not curve.is_empty:
                        for d0, d1 in zip(s0[valid], s1[valid]):
                            lo = max(0.0, min(d0, d1))
                            hi = min(total, max(d0, d1))
                            if hi <= lo:
                                continue
                            c0 = curve.project(base.interpolate(lo))
                            c1 = curve.project(base.interpolate(hi))
                            for part in self._substring_parts(
                                curve, min(c0, c1), max(c0, c1)
                            ):
                                for line in self._iter_lines(part):
                                    xy = np.asarray(line.coords)
                                    if d0 > d1:
                                        xy = xy[::-1]
                                    if len(xy) < 2:
                                        continue
                                    segments = np.stack((xy[:-1], xy[1:]), axis=1)
                                    segments = segments[
                                        np.any(segments[:, 0] != segments[:, 1], axis=1)
                                    ]
                                    if not len(segments):
                                        continue
                                    buffer.segments.append(segments)
                                    count = len(segments)
                                    buffer.segment_colors.extend([color] * count)
                                    buffer.segment_widths.extend([line_width] * count)
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
        for values in rhythm["dots"]:
            x, y, radius = values[:3]
            filled = len(values) < 4 or bool(values[3])
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
            buffer.dot_filled.extend([filled] * count)
            buffer.dot_widths.extend([line_width] * count)
        if transparent_fills:
            return
        for ring in rhythm["fills"]:
            if len(ring) < 3:
                continue
            px = np.asarray([p[0] for p in ring], dtype=float) * xc * unit
            py = np.asarray([p[1] for p in ring], dtype=float) * yc * unit
            distances = cycles[:, None] * period + px[None, :]
            inside = (distances >= 0.0) & (distances <= total)
            complete = inside.all(axis=1)
            if np.any(complete):
                bx, by, tx, ty = anchor(distances[complete].ravel())
                py2 = np.tile(py, int(np.count_nonzero(complete)))
                x = (bx - ty * py2).reshape((-1, len(px)))
                y = (by + tx * py2).reshape((-1, len(px)))
                for row in np.stack((x, y), axis=-1):
                    buffer.fills.append(row)
                    buffer.fill_colors.append(color)
            # A partial motif at either endpoint is clipped, not discarded.
            # Bounding-box overlap also catches a wide ring whose vertices all
            # fall outside the source interval while its interior covers it.
            overlaps = (distances.max(axis=1) >= 0.0) & (
                distances.min(axis=1) <= total
            )
            partial = overlaps & ~complete
            for index in np.flatnonzero(partial):
                for clipped in self._clip_fill_to_range(distances[index], py, total):
                    bx, by, tx, ty = anchor(clipped[:, 0])
                    x = bx - ty * clipped[:, 1]
                    y = by + tx * clipped[:, 1]
                    buffer.fills.append(np.column_stack((x, y)))
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
            filled = (
                buffer.dot_filled
                if len(buffer.dot_filled) == len(buffer.dot_colors)
                else [True] * len(buffer.dot_colors)
            )
            widths = (
                buffer.dot_widths
                if len(buffer.dot_widths) == len(buffer.dot_colors)
                else [0.0] * len(buffer.dot_colors)
            )
            ax.scatter(
                points[:, 0],
                points[:, 1],
                s=(2 * radii * points_per_unit) ** 2,
                facecolors=[color if is_filled else "none"
                            for color, is_filled in zip(buffer.dot_colors, filled)],
                edgecolors=["none" if is_filled else color
                            for color, is_filled in zip(buffer.dot_colors, filled)],
                linewidths=[0.0 if is_filled else width
                            for width, is_filled in zip(widths, filled)],
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
        pen_width_mm: Optional[float] = None,
    ) -> bool:
        from matplotlib.patches import Polygon

        symbol = self._symbol(number)
        if symbol is None:
            return False
        line_width_pt = (
            self.symbol_line_width_pt
            if pen_width_mm is None or pen_width_mm <= 0
            else pen_width_mm * MM_TO_PT
        )
        ca = math.cos(math.radians(angle))
        sa = math.sin(math.radians(angle))
        # Fit the native shape inside the requested dimensions without changing
        # its aspect ratio: uniform scale in symbol space, then rotate/translate.
        # A missing/zero dimension falls back to the other one instead of
        # collapsing the whole symbol to a point.
        dimensions = [abs(width_mm), abs(height_mm)]
        positive = [value for value in dimensions if value > 0]
        scale = (min(positive) if positive else 1.0) * unit

        def transform(px: float, py: float) -> Tuple[float, float]:
            px *= scale
            py *= scale
            return (x + px * ca - py * sa, y + px * sa + py * ca)

        def circle_points(cx: float, cy: float, radius: float) -> List[Tuple[float, float]]:
            return [
                (
                    cx + radius * math.cos(2 * math.pi * i / 48.0),
                    cy + radius * math.sin(2 * math.pi * i / 48.0),
                )
                for i in range(49)
            ]

        def arc_points(
            cx: float, cy: float, radius: float, a0: float, a1: float
        ) -> List[Tuple[float, float]]:
            sweep = (a1 - a0) % 360.0
            return [
                (
                    cx + radius * math.cos(math.radians(a0 + sweep * i / 48.0)),
                    cy + radius * math.sin(math.radians(a0 + sweep * i / 48.0)),
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
                    elif subpath.arc is not None:
                        points = arc_points(*subpath.arc)
                    elif len(subpath.points) >= 3:
                        # The library descriptor, not a geometric similarity
                        # threshold, decides whether this subpath is filled.
                        points = list(subpath.points)
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
                points = arc_points(*subpath.arc)
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
                    lw=line_width_pt,
                    solid_capstyle="round",
                    zorder=5,
                )
        return True

    def _font_kwargs(self, row: Any, char: str, report: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve optional native font-number maps for one character."""
        family = self.text_font_family
        unknown = report.setdefault("unknown_fonts", {})
        if ord(char) < 128 and self.font_en_map:
            code = self._int(row.get("font_en"))
            if code in self.font_en_map:
                family = self.font_en_map[code]
            else:
                key = f"font_en:{code}"
                unknown[key] = unknown.get(key, 0) + 1
        elif self.font_zh_map:
            code = self._int(row.get("font_zh"))
            if code in self.font_zh_map:
                family = self.font_zh_map[code]
            else:
                key = f"font_zh:{code}"
                unknown[key] = unknown.get(key, 0) + 1
        kwargs: Dict[str, Any] = {"fontfamily": family}
        if self.font_style_map:
            code = self._int(row.get("font_style"))
            options = self.font_style_map.get(code)
            if options is None:
                key = f"font_style:{code}"
                unknown[key] = unknown.get(key, 0) + 1
            else:
                kwargs.update(options)
        return kwargs

    @staticmethod
    def _annotation_tokens(raw: str) -> List[Tuple[str, str]]:
        """Split MapGIS annotation controls into per-character display tokens."""
        text = str(raw)
        for char in ("\x00", "\x01", "\x02", "\x03", " "):
            text = text.replace(char, "")
        text = text.replace("#-", "↓").replace("#+", "↑").replace("#=", "→").strip()
        tokens: List[Tuple[str, str]] = []
        mode = "normal"
        for char in text:
            if char in "→↓↑":
                mode = {"→": "normal", "↓": "sub", "↑": "sup"}[char]
            else:
                tokens.append((char, mode))
        return tokens

    def _draw_annotation(
        self, ax: Any, row: Any, point: Any, rgb: RGB, unit: float, report: Dict[str, Any]
    ) -> None:
        raw = self._text(row.get("CHFCED", ""))
        if not raw.strip():
            self._bump(report, "text_skipped")
            return
        height = self._float(row.get("height"), 2.0)
        category = self._text(row.get("CHFCEC", "")).strip()
        category_scale = self._float(self.text_category_scales.get(category), 1.0)
        if category in {"产状", "断层产状", "断层辅助点"}:
            category_scale *= self.attitude_text_scale
        scale = self.text_scale * category_scale
        base_size = max(height * MM_TO_PT * scale, 0.8)
        angle = self._float(row.get("angle"), 0.0)
        width = self._float(row.get("width"), height)
        spacing = self._float(row.get("spacing"), 0.0)
        advance = (width + spacing) * scale
        tokens = self._annotation_tokens(raw)
        if self.native_text_layout and advance > 0 and tokens and "\n" not in raw:
            ca = math.cos(math.radians(angle))
            sa = math.sin(math.radians(angle))
            has_controls = any(mark in raw for mark in ("#-", "#+", "#=", "→", "↓", "↑"))
            for index, (char, mode) in enumerate(tokens):
                # Script size/baseline is a display approximation; the stored
                # character advance itself is used without an inferred factor.
                offset = (0.0 if mode == "normal" else
                          (-0.35 if mode == "sub" else 0.5) * height * unit)
                x = point.x + index * advance * unit * ca - offset * sa
                y = point.y + index * advance * unit * sa + offset * ca
                content = _mathtext_escape(char) if has_controls else char
                if has_controls:
                    content = "$\\mathrm{" + content + "}$"
                ax.text(
                    x,
                    y,
                    content,
                    fontsize=max(base_size * (0.7 if mode != "normal" else 1.0), 0.6),
                    color=rgb,
                    ha="left",
                    va="baseline",
                    rotation=angle,
                    rotation_mode="anchor",
                    parse_math=has_controls,
                    zorder=6,
                    **self._font_kwargs(row, char, report),
                )
            self._bump(report, "text")
            self._bump(report, "spaced_text")
            if spacing < 0:
                self._bump(report, "compressed_text")
            if any(mode != "normal" for _, mode in tokens):
                self._bump(report, "script_text")
            self._bump(report, "drawn")
            return

        if self.native_text_layout and advance <= 0:
            self._bump(report, "invalid_spacing")
        label = _annotation_to_mathtext(raw)
        if not label:
            self._bump(report, "text_skipped")
            return
        ax.text(
            point.x,
            point.y,
            label,
            fontsize=base_size,
            color=rgb,
            ha="left",
            va="baseline",
            rotation=angle,
            rotation_mode="anchor",
            parse_math=label.startswith("$\\mathrm{"),
            zorder=6,
            **self._font_kwargs(row, raw[:1] or " ", report),
        )
        self._bump(report, "text")
        self._bump(report, "drawn")

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
                        pen_width_mm=self._float(row.get("pen_width"), 0.0),
                    )
                    self._bump(report, "symbols" if ok else "symbols_unresolved")
                    if ok:
                        self._bump(report, "drawn")
                else:
                    self._draw_annotation(ax, row, point, rgb, unit, report)


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


_MATHTEXT_LITERAL_ESCAPES = {
    "\\": r"\backslash{}",
    "{": r"\{",
    "}": r"\}",
    "_": r"\_",
    "^": r"\textasciicircum{}",
    "$": r"\$",
    "%": r"\%",
    "#": r"\#",
    "~": r"\textasciitilde{}",
}


def _mathtext_escape(value: str) -> str:
    """Escape literal label text while retaining supported Greek commands."""
    return "".join(
        _GREEK_MATHTEXT.get(char, _MATHTEXT_LITERAL_ESCAPES.get(char, char))
        for char in value
    )


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
        escaped = _mathtext_escape(value)
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
    as keyword arguments. ``channel_order`` is forwarded when ``slib`` is a
    directory.

    Example
    -------
    >>> result = render_graphic_map(
    ...     ["area.wp", "boundary.wl", "labels.wt"], "SLIB", "map.png",
    ...     scale=250000, dpi=300,
    ... )  # doctest: +SKIP
    """
    output_keys = {"figsize", "dpi", "margin", "title"}
    render_options = {key: kwargs.pop(key) for key in list(kwargs) if key in output_keys}
    channel_order = kwargs.pop("channel_order", "KCMY")
    if isinstance(slib, GraphicLibraries):
        if channel_order != "KCMY":
            raise ValueError("channel_order is only valid when slib is a directory")
        libraries = slib
    else:
        libraries = GraphicLibraries.from_directory(slib, channel_order=channel_order)
    renderer = GraphicRenderer(libraries, **kwargs)
    return renderer.render(layers, output, **render_options)


__all__ = [
    "GraphicLibraries",
    "GraphicRenderer",
    "GraphicRenderResult",
    "render_graphic_map",
]
