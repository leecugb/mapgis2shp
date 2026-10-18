# mapgis2shp — OSGeo Community Project page draft

> **Draft status:** This page is prepared for an application to the OSGeo
> Community Projects Initiative. It does not state or imply current OSGeo
> hosting, endorsement, incubation, or membership. Remove this drafting note
> only when the page is used in the application process.

## Summary

**mapgis2shp** (Python import name `pymapgis`) is an Apache-2.0 Python library
and command-line tool for reading, writing, and converting MapGIS 6.x/67 binary
vector formats. It enables legacy point, line, and polygon survey data to move
between MapGIS and the open-source geospatial stack through GeoPandas
GeoDataFrames and common GIS formats.

The project addresses a practical geospatial interoperability problem: legacy
`.wt`, `.wl`, and `.wp` files are not natively supported by the usual
GDAL/OGR-based vector-I/O path. The current release is **2.5.0**, distributed
through PyPI as `mapgis2shp`.

## Main capabilities

- Read MapGIS 6.x/67 `.wt`, `.wl`, and `.wp` files into GeoDataFrames
- Write GeoDataFrames back to native MapGIS binary files
- Convert through the `pymapgis` command-line interface in either direction
- Decode GBK attributes and infer coordinate reference systems from MapGIS
  projection and ellipsoid index codes
- Reconstruct polygon shells, holes, and shared-boundary topology, and
  regenerate topology when writing
- Decode point, line, and polygon graphic parameters
- Parse `Subgraph.lib` point-symbol and `LINESTY.lib` line-style structures
- Preserve unknown or unsupported conditions explicitly rather than inventing
  CRS definitions or symbol geometry

## Download and documentation

- **Install:** `python -m pip install mapgis2shp`
- **Source and issue tracker:** <https://github.com/leecugb/mapgis2shp>
- **PyPI:** <https://pypi.org/project/mapgis2shp/>
- **Quick start:** [README — Quick start](../README.md#quick-start)
- **Command-line usage:** [README — Command-line usage](../README.md#command-line-usage)
- **Python API:** [README — API](../README.md#api)
- **Binary format reference:** [MapGIS Vector Format](MapGIS_Vector_Format.md)
- **Software archive DOI:** <https://doi.org/10.5281/zenodo.21487339>

The package supports Python 3.9 and later. Runtime dependencies are declared in
`pyproject.toml` and installed by the Python package manager.

## Validation and testing

The reader has been compared with official MapGIS 6.7 exports on 36 real
geological-survey layers containing 16,874 features, and with a separate
large polygon dataset. The project also provides a regression baseline,
Reader–Writer–Reader round-trip checks, and unit and integration tests.

These validation categories are reported separately: round-trip consistency
does not imply acceptance by the proprietary MapGIS application, and structural
graphic-library parsing does not imply vendor-identical rendering. Current
limitations and data-availability conditions are documented in the repository
and software paper.

## Community and contributions

The project welcomes bug reports, format evidence, documentation, tests, and
focused code contributions. Technical discussions and decisions are maintained
in public GitHub issues and pull requests.

- [Contributing guide](../CONTRIBUTING.md)
- [Code of Conduct](../CODE_OF_CONDUCT.md)
- [Licence and provenance review](license_provenance.md)

Participation follows the Contributor Covenant. Conduct in OSGeo forums is
additionally subject to the OSGeo Code of Conduct and its reporting guidance.

## Licence

mapgis2shp is distributed under the
[Apache License 2.0](../LICENSE). Contributions must preserve notices and
provide provenance for third-party material. Proprietary survey datasets and
MapGIS graphic libraries are not redistributed with the package.

## Project contact

**Shijie Li**

Email: [1045105061@qq.com](mailto:1045105061@qq.com)

Technical questions should normally be asked through the public
[GitHub issue tracker](https://github.com/leecugb/mapgis2shp/issues) so that the
answers remain available to other users.
