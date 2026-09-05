"""pymapgis - Read MapGIS vector files into GeoPandas GeoDataFrames."""

from pymapgis._version import __version__
from pymapgis.reader import (
    POINT_TYPE_SYMBOL,
    POINT_TYPE_TEXT,
    InvalidDirectoryError,
    InvalidFileError,
    MapGISError,
    Reader,
    TopoError,
)

__all__ = [
    "Reader",
    "MapGISError",
    "InvalidFileError",
    "InvalidDirectoryError",
    "TopoError",
    "POINT_TYPE_TEXT",
    "POINT_TYPE_SYMBOL",
    "__version__",
]
