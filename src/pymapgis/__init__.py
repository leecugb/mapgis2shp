# SPDX-License-Identifier: Apache-2.0
"""pymapgis - Read and write MapGIS vector files with GeoPandas GeoDataFrames.

Also provides parsers for the MapGIS 6.x graphic libraries (Subgraph.lib
symbol library, LINESTY.lib line-style library, Fillgrph.lib pattern library,
Colorlib.lib colour table and optional Pcolor.lib 32-byte colour nodes) and an
optional original-library rendering pipeline for the .wt/.wl/.wp features that
reference them. Geological interpretation and GeoSciML conversion are outside
the package's public API scope.
"""

from pymapgis._version import __version__
from pymapgis.colorlib import ColorLib
from pymapgis.fillgrph import FillPattern, FillStroke, FillgrphLib, pattern_geometry
from pymapgis.graphic import (
    GraphicLibraries,
    GraphicRenderer,
    GraphicRenderResult,
    render_graphic_map,
)
from pymapgis.linesty import (
    Element,
    LineStyle,
    LinestyLib,
    SubLine,
    census,
    classify_form,
    compose_feature_style,
    dotline_params,
    linedot_params,
)
from pymapgis.pcolor import PcolorLib
from pymapgis.reader import (
    POINT_TYPE_SYMBOL,
    POINT_TYPE_TEXT,
    InvalidDirectoryError,
    InvalidFileError,
    MapGISError,
    Reader,
    TopoError,
)
from pymapgis.slib import SubgraphLib, SubPath, Symbol, fit_circle, symbol_geometries
from pymapgis.writer import Writer, WriterError, write

__all__ = [
    "Reader",
    "Writer",
    "write",
    "WriterError",
    "MapGISError",
    "InvalidFileError",
    "InvalidDirectoryError",
    "TopoError",
    "POINT_TYPE_TEXT",
    "POINT_TYPE_SYMBOL",
    # MapGIS graphic-library parsers
    # (Subgraph / LINESTY / Fillgrph / Colorlib / Pcolor)
    "SubgraphLib",
    "SubPath",
    "Symbol",
    "fit_circle",
    "symbol_geometries",
    "LinestyLib",
    "LineStyle",
    "SubLine",
    "Element",
    "classify_form",
    "census",
    "compose_feature_style",
    "ColorLib",
    "PcolorLib",
    "FillgrphLib",
    "FillPattern",
    "FillStroke",
    "pattern_geometry",
    # Original graphic-library rendering (optional matplotlib dependency)
    "GraphicLibraries",
    "GraphicRenderer",
    "GraphicRenderResult",
    "render_graphic_map",
    "__version__",
]
