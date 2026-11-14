"""Validate the bundled public-domain USGS Conejo Well fixture."""
import hashlib
import json

from pymapgis import Reader
from pymapgis.testing import usgs_conejo_path


def test_usgs_conejo_fixture_manifest_and_files():
    root = usgs_conejo_path()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["distribution"] == "USGS source fixture; optional native six-layer comparison data"
    assert "public-domain" in manifest["rights_note"]
    assert "Generic SLIB is bundled separately" in manifest["rights_note"]
    assert len(manifest["native_files"]) == 6
    assert len(manifest["source_files"]) == 5
    if (root / "native").is_dir():
        for name, info in manifest["native_files"].items():
            path = root / "native" / name
            assert path.is_file() and path.stat().st_size > 0
            assert hashlib.sha256(path.read_bytes()).hexdigest() == info["sha256"]
            reader = Reader(path, read_graphic_params=True)
            assert len(reader.geodataframe) == info["features"] > 0
            assert reader.geodataframe.geometry.is_empty.sum() == 0
    for name, info in manifest["source_files"].items():
        path = root / "source" / name
        assert path.is_file() and path.stat().st_size > 0
        assert hashlib.sha256(path.read_bytes()).hexdigest() == info["sha256"]


def test_usgs_conejo_fixture_metadata_and_access_api():
    root = usgs_conejo_path()
    metadata = (root / "metadata/cwell_met.txt").read_text(encoding="utf-8")
    assert "Access_Constraints: None" in metadata
    assert "Metadata_Access_Constraints: none" in metadata
    assert "Metadata_Use_Constraints: none" in metadata
    assert usgs_conejo_path("source/cwell_geo.e00").is_file()
    assert not (root / "native/CWELL_LAB_WT.WT").exists()
    assert not (root / "native/CWELL_STR_LAB_WT.WT").exists()
    assert not (root / "slib").exists()
