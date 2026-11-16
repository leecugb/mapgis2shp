# Executable geological-data migration example

`geological_workflow.py` reads the seven bundled USGS Conejo Well processed MapGIS layers (two WL files, one WT file and four WP files), retains their native WGS 84 / UTM zone 11N CRS (EPSG:32611) and metre coordinates, and computes attitude counts, line lengths by type, and polygon areas by geological unit.

It demonstrates an open analysis workflow after MapGIS interoperability. It does not present a new geological interpretation and does not replace native-export or native-application validation.

## Run

From the repository root:

```bash
PYTHONPATH=src python3 examples/geological_workflow.py
```

The command prints a JSON summary. To write all seven layers as open GeoPackage outputs as well:

```bash
PYTHONPATH=src python3 examples/geological_workflow.py --output-dir ./example_output
```

The output directory is created only when explicitly requested. The example uses the bundled, redistributable USGS-derived testdata and requires no external survey files or external MapGIS graphic libraries.

## Original-library rendering and GeoPDF

`render_testdata.py` renders the same seven layers with the bundled SLIB libraries. It writes PNG/SVG previews, a strict 1:24,000 fully vector GeoPDF, and JSON reports, then verifies the page scale and rejects raster image objects in the formal PDF.

```bash
PYTHONPATH=src python examples/render_testdata.py --output-dir ./testdata_render
```

Use `--dpi` to change preview/layout resolution. The PNG/SVG files are previews only; the formal scale guarantee belongs to the GeoPDF. See [the rendering and GeoPDF guide](../docs/rendering_geopdf.md).
