# Executable geological-data migration example

`geological_workflow.py` reads the public synthetic MapGIS point, line, and polygon binaries, converts the layers to WGS 84 / UTM zone 43N (EPSG:32643), and computes attitude counts, line lengths by type, and polygon areas by geological unit.

It demonstrates an open analysis workflow after MapGIS interoperability. It does not present a new geological interpretation and does not replace native-export or native-application validation.

## Run

From the repository root:

```bash
PYTHONPATH=src python3 examples/geological_workflow.py
```

The command prints a JSON summary. To write three open GeoPackage outputs as well:

```bash
PYTHONPATH=src python3 examples/geological_workflow.py --output-dir ./example_output
```

The output directory is created only when explicitly requested. The example uses no restricted survey files and no proprietary MapGIS graphic libraries.
