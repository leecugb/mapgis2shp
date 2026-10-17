# SPDX-License-Identifier: Apache-2.0
"""pymapgis - Read and write MapGIS vector files with GeoPandas GeoDataFrames.

Also provides parsers for the MapGIS 6.x graphic libraries (Subgraph.lib
symbol library and LINESTY.lib line-style library) that the graphic
parameters of .wt/.wl features reference.
"""

from pymapgis._version import __version__
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
    # MapGIS graphic-library parsers (Subgraph.lib / LINESTY.lib)
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
    "dotline_params",
    "linedot_params",
    "__version__",
]
