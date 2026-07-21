"""pymapgis - Read MapGIS vector files into GeoPandas GeoDataFrames."""

from pymapgis._version import __version__
from pymapgis.reader import (
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
    "__version__",
]
