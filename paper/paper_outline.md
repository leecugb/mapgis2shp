# Paper 1 Outline — mapgis2shp: open-source MapGIS 6.x/67 reader with native-validated fidelity

> Strategy: two-paper split. **Paper 1 (this) = reader + native cross-validation**, submit now.
> Paper 2 (later, when rendering is finished) = DZ/T 0179 rendering pipeline (the genuinely-novel pillar).

## 0. Provisional title
*mapgis2shp: an open-source Python reader for the MapGIS 6.x/67 binary vector formats, with coordinate-reference inference and fidelity validation against the native MapGIS export*

## 1. Target journal & article type
- **Primary: SoftwareX** (Elsevier, SCIE, IF ~1.5–2). Software description paper; requires Zenodo/OSF DOI. Safe.
- **Stretch: Earth Science Informatics** (Springer, SCIE, IF ~4.2). Dedicated *Software article* type with "Design and Implementation" + "Availability and Requirements" sections; median 7-day first decision.
- Write to the ESI Software-article template (superset of SoftwareX); downshift to SoftwareX if ESI rejects.

## 2. Honest novelty positioning (MUST be stated exactly like this)
**Do NOT claim**: "first open-source reader", "first byte-level specification", "first converter". All are prior art (own pymapgis 2022; MathsionYang 2019 C#; BenChao1998/ConvertMapGIS 2025 derivative with public spec; Wang 2013 / Wu & Feng 2006 / Chen 2000 Chinese academic precedents).

**DO claim (all verified defensible)**:
1. First **peer-reviewed** software paper on a MapGIS 6.x/67 reader (Crossref/arXiv zero; ⚠️ CNKI manual check pending).
2. First reader **independently validated against the reference implementation** (official MapGIS export) with **quantified fidelity**: 36 layers, 16 874 features, 100% geometric identity, 99.9995% attribute equivalence.
3. First reader that **infers and attaches the CRS** (native shapefile export drops the .prj; pymapgis reconstructs Krassovsky 1940 + towgs84).
4. Open-source (Apache-2.0), PyPI-distributed, with a reproducible validation harness — none of the prior tools ship a validation suite.

## 3. Section-by-section outline

### Abstract (~250 words)
Problem (MapGIS closed-source, dominant in CN geology, GDAL/QGIS no driver — verified), gap (prior readers exist but none validated, none peer-reviewed, native export loses CRS), what mapgis2shp does (vectorized parser, CRS inference, topology reconstruction), validation (36 layers vs official MapGIS: 100% geometric, 99.9995% attribute equivalence, more precise than native), availability (PyPI, GitHub, Zenodo/OSF DOI, Apache-2.0).

### 1. Introduction
- 1.1 MapGIS dominance in Chinese geological survey; closed-format lock-in; interoperability barrier with open-source stack (GDAL/GeoPandas/QGIS).
- 1.2 GDAL has **no** MapGIS driver (verified: no `ogr/ogrsf_frmts/mapgis*`, zero OSGeo/gdal issues/PRs) — cite [GDAL drivers page](https://gdal.org/drivers/vector/index.html).
- 1.3 Related work (see §4 citation list): prior readers (own pymapgis 2022, MathsionYang 2019, ConvertMapGIS 2025, OGC.net 2021, yuk-project 2015), Chinese academic precedents (Wang 2013, Wu & Feng 2006, Chen 2000), methodology analogs (sas7bdat, python-ags4, ArcGMT), foundational (GDAL/Warmerdam 2008, GeoSciML). State explicitly: all prior work lacks independent validation and CRS inference.
- 1.4 Contributions (the 4 claims in §2).

### 2. Background: the MapGIS 6.x/67 binary formats
- 2.1 Three file types (.wt/.wl/.wp), magic bytes `WMAP◇D22/D21/D23`, index-area + sub-data-area layout.
- 2.2 Logical record model (header, data/coord/attr/topo blocks).
- 2.3 Why a spec matters; reference the companion spec doc (your `MapGIS_Vector_Format.md`) and note prior public disclosure by ConvertMapGIS (cite it).
- **Fig 1**: byte-layout diagram of the three file types.

### 3. Design and Implementation
- 3.1 Architecture: binary I/O → record model → Shapely geometries → GeoPandas GeoDataFrame; CLI.
- 3.2 Vectorized parsing via NumPy structured dtypes (point/arc/topo tables).
- 3.3 CRS inference: projection/ellipsoid index codes → PROJ4 (Krassovsky/Xi'an80/WGS84 + tmerc/aea/lcc); DMS decode.
- 3.4 Polygon topology reconstruction: arc-node → rings (hash-based merge, O(n)) → shells/holes → make_valid.
- **Fig 2**: reader pipeline / architecture diagram.

### 4. Validation (CORE chapter — largest)
- 4.1 Dataset: 36 real layers (Kurgan sheet J43C001002 region), 16 874 features, point/line/polygon.
- 4.2 Protocol: read each layer with mapgis2shp AND export with official MapGIS to shapefile; align by ID; compare count, schema, geometry (point distance / line Hausdorff / polygon IoU, tol 1e-7°), attributes (semantic equivalence classifying native lossy artifacts).
- 4.3 Results:
  - Count: 36/36 identical; 16 874 = 16 874.
  - Schema: 36/36 identical.
  - Geometry: 36/36 layers 100% match; zero geometric discrepancy.
  - Attributes: 99.9995% equivalence (2 cells differ, both native's coarse rounding of sub-1e-6 floats; pymapgis more precise).
  - CRS: pymapgis sets CRS; native export drops .prj.
- 4.4 Native-export lossy artifacts catalogued (Table 4): float truncation, numeric formatting, whitespace stripping — pymapgis preserves source more faithfully.
- **Table 1**: sample dataset (layer, type, feature count).
- **Table 2**: cross-validation per-layer results (36 rows: count, geom_match, attr_equiv, attr_mismatch).
- **Table 4**: native lossy-artifact categories with examples.

### 5. Comparison with prior tools
- **Table 3**: mapgis2shp vs pymapgis(2022) vs MathsionYang(2019) vs ConvertMapGIS(2025) vs Wang(2013) — axes: open-source, language, spec doc, CRS inference, independent validation, PyPI, license, peer-reviewed.
- Honest statement of what each prior tool does and where mapgis2shp's increment lies (validation + CRS + peer-reviewed + reproducible harness).

### 6. Discussion
- Limitations: ellipsoid/projection coverage (4+3 codes), K9 unsupported, CRS depends on external index tables, topology heuristic (make_valid fallback), no write support.
- Generalizability: methodology (reverse-engineered-reader validation against reference implementation) transfers to other proprietary formats.
- Open-science implication: enables CN geological-survey data to enter GDAL/GeoPandas/QGIS reproducibly.

### 7. Conclusions

### 8. Availability and Requirements (ESI/SoftwareX block)
- Software name: mapgis2shp (import `pymapgis`).
- PyPI: `pip install mapgis2shp` (v2.0.4).
- GitHub: https://github.com/leecugb/mapgis2shp
- Archived DOI: Zenodo/OSF (to obtain — see pre-submission checklist).
- License: Apache-2.0.
- OS: Windows/Linux/macOS; Python ≥3.9; deps: geopandas, numpy, pandas, pyproj, shapely.
- Data availability: 36 sample layers are real CGS survey data (not redistributable); validation script + baseline included; synthetic minimal fixtures in tests/.

### 9. CRediT / competing interests / acknowledgements

## 4. Related-work citation list (verified DOIs / URLs)
Prior MapGIS readers (cite + differentiate):
- leecugb/pymapgis (2022) — https://github.com/leecugb/pymapgis  [own prior work]
- MathsionYang/MapGIS2ArcGIS (2019, C#) — https://github.com/MathsionYang/MapGIS2ArcGIS
- BenChao1998/ConvertMapGIS (2025, derivative w/ public spec) — https://github.com/BenChao1998/ConvertMapGIS
- WenboWong/OGC.net (2021) — https://github.com/WenboWong/OGC.net
- zenwalk/yuk-project-mapgis2arcgis (2015) — https://github.com/zenwalk/yuk-project-mapgis2arcgis

Chinese academic precedents:
- Wang Xingjie (2013), "Data analysis and reading test on MapGIS point file," 《测绘科学》. [no DOI; OpenAlex]
- Wu Lihong, Feng Ju (2006), "Study on key techniques of MapGIS and Geodatabase data format conversion." [OpenAlex]
- Chen Hua (2000), "Realization of format conversion in MapGIS with MATLAB," 《物探化探计算技术》.
- Xia M. (2013), polygon topology reconstruction with MapGIS/MapStar. [Semantic Scholar, no DOI]
- MA/WANG/XIE (2012), HAN/PANG (2012), WEN/ZHANG (2012) — MapGIS application papers, Geo-information Science, DOI 10.3724/sp.j.1047.2011.00758 / .00742 / .00750.

Methodology analogs (reverse-engineered binary readers):
- Shotwell (2011), sas7bdat — DOI 10.32614/cran.package.sas7bdat
- Senanayake et al. (2022), python-ags4, JOSS — DOI 10.21105/joss.04569  [closest structural template]
- ArcGMT, C&G (1998) — DOI 10.1016/s0098-3004(98)00067-3  [format-bridge precedent in target journal]

Foundational:
- Warmerdam (2008), GDAL — DOI 10.1007/978-3-540-74831-1_5
- Sen & Duffy (2005), GeoSciML, C&G — DOI 10.1016/j.cageo.2004.12.003
- van den Bos (2014), binary-format RE — DOI 10.1109/csmr-wcre.2014.6747196

## 5. Pre-submission checklist
- [ ] **CNKI/万方 manual search** for MapGIS 文件格式/逆向/wt wl wp (only unverified gap).
- [ ] Obtain Zenodo or **OSF** DOI (Zenodo blocked in CN; OSF reachable) for v2.0.4 archive.
- [ ] Add the cross-validation script + report to the GitHub repo (already local: `cross_validate_native.py`, `cross_validation_report.{csv,md}`).
- [ ] Confirm author affiliation (Li Shijie, CUGB) and CRediT roles.
- [ ] Make figures (Fig 1 byte layout, Fig 2 architecture).
- [ ] Polished English; target ESI template.
- [ ] Delete exposed PyPI + GitHub tokens (already flagged).

## 6. Risk notes
- CNKI gap is the only unverified novelty risk; a Chinese thesis with a byte-level spec + validation would weaken claims 1–2. Must check before submission.
- If ESI reviewers want a "methods" contribution beyond validation, the fallback is SoftwareX (lower bar, still SCIE).
- Do **not** mention rendering/DZ/T 0179 in Paper 1 — reserved for Paper 2.
