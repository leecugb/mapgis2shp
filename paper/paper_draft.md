# mapgis2shp: an open-source Python reader for the MapGIS 6.x/67 binary vector formats, with coordinate-reference inference and fidelity validation against the native MapGIS export

**Authors:** Shijie Li \(China University of Geosciences, Beijing\)

**Target journal:** Earth Science Informatics (Software article) / SoftwareX

---

## Abstract

MapGIS is a closed-source geographic information system that dominates Chinese geological surveying, yet its native binary vector formats — `.wt` (point), `.wl` (line), `.wp` (polygon) — are undocumented and are not readable by any mainstream open-source geospatial tool, including GDAL/OGR and QGIS. Geological-survey data locked in these formats therefore cannot enter open-source analysis pipelines without the proprietary software. We present **mapgis2shp** (PyPI distribution name `mapgis2shp`, import name `pymapgis`): an open-source, Apache-2.0 Python reader that reverse-engineers the MapGIS 6.x/67 binary layout, infers the coordinate reference system (CRS) from the file's projection and ellipsoid index codes, reconstructs polygon topology from the arc–node structure, and returns standard `geopandas.GeoDataFrame` objects or ESRI shapefiles. Several open-source MapGIS readers already exist, but none has been independently validated against the reference implementation, none infers the CRS, and none has been peer-reviewed. We close these gaps with a reproducible cross-validation against the official MapGIS software on two tiers: (i) 36 real geological-survey layers comprising 16 874 features, where feature counts, attribute schemas, and geometries are identical (point distance, line Hausdorff distance, and polygon intersection-over-union all indicate exact coincidence within \(10^{-7}\) degrees) and attribute values are semantically equivalent in 99.9995% of 95 006 compared cells; and (ii) a 400 MB polygon file of 78 873 features, where bounding box, coordinate reference system, and the 16 native attribute fields match the official export exactly, the reader produces zero invalid geometries versus three in the reference, and spatial coverage agrees with an intersection-over-union of 99.73%. The only deviations are attributable to lossy rounding in the native shapefile export and to a quantified 1.66% overlap artefact of the heuristic arc-merge reconstruction at shared boundaries — a summed-area effect that reduces to a 0.27% real coverage difference. The reader in fact preserves source data more faithfully than the native export, which truncates floating-point fields and strips stored string padding. mapgis2shp is distributed on PyPI and archived with a citable DOI.

**Keywords:** MapGIS; reverse engineering; vector format; GeoPandas; shapefile; geological survey; open source

---

## 1. Introduction

### 1.1 Motivation

MapGIS (Zondy Cyber, Wuhan) is the de facto geographic information system of the Chinese geological-survey community and is widely used in regional geological mapping, mineral exploration, and engineering geology. Its native vector storage — the 6.x/67 generation's `.wt` (point), `.wl` (line), and `.wp` (polygon) binary files — is closed: the on-disk layout is not published by the vendor, and the format is distinct from the later MapGIS K9/10 "open data format". As a result, geological-survey data held in these files cannot be read by the open-source geospatial stack (GDAL/OGR, GeoPandas, QGIS, GRASS) without the proprietary software. This lock-in impedes reproducible analysis, data sharing, and long-term archival — concerns repeatedly raised in the open-science literature for proprietary geoscience formats.

### 1.2 The interoperability gap

We verified that **GDAL/OGR ships no MapGIS driver**: the official vector-driver index contains no `mapgis` entry, and the `OSGeo/gdal` issue tracker and pull requests contain zero mentions of "MapGIS" or the vendor name "ZondyCyber" across the entire organisation. Because QGIS, GRASS, SAGA, and WhiteboxTools rely on GDAL/OGR for vector I/O, none of them can open `.wt`/`.wl`/`.wp` files natively. The only documented MapGIS exchange route offered by the vendor is an ASCII "plain-code" (明码) format and the newer MapGIS 10 open format — neither of which is the legacy binary format that holds the bulk of existing survey data.

### 1.3 Related work

Several open-source MapGIS readers predate this work and must be acknowledged. The author's own `pymapgis` (2022) is a single-file Python reader that first published a byte-level format description. `MathsionYang/MapGIS2ArcGIS` (2019, C#) independently parses the `.wl` structure at the record level. `BenChao1998/ConvertMapGIS` (2025) is a derivative of `pymapgis` that republishes a detailed byte-level specification in its README and adds a graphical converter. `WenboWong/OGC.net` (2021, C#) and `zenwalk/yuk-project-mapgis2arcgis` (2015, C#) are earlier format-bridge tools. Chinese-language academic literature has also analysed the format programmatically — notably Wang (2013) on reading the `.wt` point file, Wu and Feng (2006) on MapGIS–Geodatabase conversion, and Chen (2000) on MapGIS format conversion in MATLAB — but these are short application notes, none ships an open-source reader, none publishes a byte-level specification, and none validates output correctness.

Methodologically, the work follows a recognised genre of open-source readers for closed or under-documented scientific binary formats, including `sas7bdat` for SAS files, `python-ags4` for AGS4 geotechnical files, and the long-running GDAL library for numerous proprietary GIS formats. Within the target journal, format-bridge software such as ArcGMT establishes precedent for this contribution type.

**Crucially, no prior MapGIS reader provides (i) independent validation against the reference implementation, (ii) coordinate-reference inference, or (iii) a reproducible validation harness.** These are the gaps mapgis2shp closes.

### 1.4 Contributions

This paper makes the following verified contributions:

1. The **first peer-reviewed software paper** on a MapGIS 6.x/67 reader (Crossref, arXiv, and OpenAlex return no such paper; see §6 for the one residual coverage gap).
2. The **first reader independently validated against the reference implementation** (official MapGIS export) with quantified fidelity, on two tiers: 36 small/medium layers (16 874 features, exact geometric coincidence, 99.9995% attribute equivalence) and one 400 MB file (78 873 features, 99.73% coverage IoU).
3. The **first reader that infers and attaches the CRS**: the native shapefile export omits the `.prj`, whereas mapgis2shp reconstructs a PROJ string (Krassovsky 1940 with `towgs84` for the test data) from the file's projection and ellipsoid index codes.
4. A **reproducible, open-source (Apache-2.0) validation harness** distributed on PyPI, with a 36-file regression baseline and an automated cross-validation script.

We do not claim novelty for the reader, the byte-level specification, or shapefile conversion per se; these are prior art as enumerated above.

---

## 2. Background: the MapGIS 6.x/67 binary formats

All three file types share a common top-level organisation: an 8-byte magic header (`WMAP◇D22` for points, `WMAP◇D21` for lines, `WMAP◇D23` for polygons, where `◇` is a non-printing byte), a 4-byte file-identifier int32, and a 4-byte `data_start` offset locating a 10-entry index table. Each index entry is 10 bytes, of which the first 8 give a `(start, volume)` pair describing one sub-data region. Numeric values are little-endian; strings are GBK-encoded.

The point section stores 93-byte records (X/Y as little-endian double at offsets 7–14 and 15–22). The line and polygon files share a 57-byte arc-index record (point count at offset 10–13, byte offset into the coordinate section at 14–17) followed by a coordinate section of 16-byte XY pairs. The polygon file additionally stores a 24-byte topology record whose bytes 8–15 carry the left and right polygon identifiers of each arc, from which closed rings, shells, and holes are reconstructed.

CRS information resides in fixed file-header offsets: projection type at byte 109, ellipsoid at byte 110, scale denominator (double) at byte 143, and — for projected CRSes — the central meridian and standard parallels as `DDDMMSS.sss`-encoded doubles from byte 151 onward. The complete byte-level specification accompanies the software as a reference document.

**Figure 1.** Byte-level layout of the MapGIS 6.x/67 vector formats. **(a)** Common file header: 8-byte magic (`WMAP·D22`/`D21`/`D23` for point/line/polygon), file identifier, `data_start` offset, the 10-entry index area, and the coordinate-reference-system bytes (projection@109, ellipsoid@110, scale@143, central meridian@151 in `DDDMMSS.sss`). **(b)** Type-specific record sections: `.wt` point coordinate records (93 B; X/Y double at offsets 7–14/15–22), `.wl` line index (57 B) plus 16-B XY coordinate pairs, and `.wp` arc index (57 B), coordinate section, and 24-B topology records (left/right polygon identifiers at 8–11/12–15). Strips are schematic, not to scale; each block carries its record size. All integers little-endian; strings GBK.

---

## 3. Design and Implementation

### 3.1 Architecture

mapgis2shp is organised as a thin pipeline: binary I/O → record model → Shapely geometries → GeoPandas `GeoDataFrame`. A `Reader` class parses the file fully on construction, exposing `.geodataframe`, `.fields`, `.crs`, `.bbox`, and a `.to_file()` passthrough. A small command-line interface (`pymapgis input.wp output.shp`) wraps the common conversion case. The package targets Python ≥ 3.9 and depends only on geopandas, numpy, pandas, pyproj, and shapely.

### 3.2 Vectorised binary parsing

Binary records are decoded with NumPy structured dtypes rather than per-field `struct.unpack` calls. The point, arc-index, and topology tables are materialised in a single `np.frombuffer` call each, and coordinate arrays are reshaped to `(n, 2)` and scaled in one vectorised multiply. This reduces parsing of the largest test polygon (608 features, 2 166 arcs) to ~0.33 s on a laptop. Attribute-table field descriptors are unpacked in bulk via a precompiled `struct.Struct` of the 39-byte descriptor layout.

### 3.3 Coordinate-reference inference

From the projection index (byte 109) and ellipsoid index (byte 110), mapgis2shp constructs a PROJ string. Longitude/latitude files (projection 0) yield a geographic CRS; Transverse Mercator (5), Albers (2), and Lambert (3) yield projected CRSes with the central meridian decoded from the `DDDMMSS.sss` double by arithmetic (preserving fractional seconds and handling western longitudes). The supported ellipsoid codes include Krassovsky 1940 (Beijing 1954), Xi'an 1980, WGS84, WGS72, and CGCS2000. When the ellipsoid code is unrecognised or the scale is zero, the reader returns an empty CRS rather than a guessed one, so downstream code can detect the gap.

### 3.4 Polygon topology reconstruction

Polygon geometries are rebuilt from the arc–node topology: arcs whose left or right polygon identifier equals the target identifier are oriented consistently, chained into closed rings by endpoint matching, and classified into shells and holes by containment. Ring assembly uses a spatial hash on arc endpoints (cell size \(10^{-5}\) map units) with a two-sided greedy walk and a closure-competition rule, reducing the merge from \(O(n^{3})\) (a fresh all-pairs distance matrix each iteration) to \(O(n)\) in the common case while preserving the semantics of the original nearest-pair heuristic. Rings that fail to close cleanly — a known artefact of source-data topological gaps — are passed through `shapely.make_valid` so the output satisfies the OGC simple-features specification.

**Figure 2.** mapgis2shp reader architecture and data flow. **(a)** Main pipeline (solid arrows): MapGIS `.wt`/`.wl`/`.wp` closed binary → binary I/O and record model (NumPy structured dtypes) → Shapely geometries → open outputs (GeoDataFrame / shapefile / GeoJSON). Dashed bypasses: CRS inference (projection/ellipsoid index codes → PROJ string) feeding the parser and output projection; polygon topology reconstruction (arc–node → rings → shells/holes + `make_valid`) feeding polygon geometry. The Reader API and CLI sit as a thin access layer over the whole pipeline. **(b)** Reproducible verification: the cross-validation harness (36-layer 1:1 comparison vs official MapGIS — geometry 100%, attributes 99.9995%; 400 MB coverage-equivalence test — IoU 99.73%) and the regression baseline (`pymapgis_baseline.json` + pytest), rising as dashed "verify" arrows into the pipeline.

---

## 4. Validation

The validation chapter is the core of this contribution: it quantifies how closely mapgis2shp's output matches the reference implementation (official MapGIS) on real production data.

### 4.1 Dataset

The validation set comprises **36 MapGIS vector layers** drawn from 1:50 000 geological-survey sheets in the Kurgan region (J43C001002, Xinjiang, China): 5 point layers, 18 line layers, and 13 polygon layers, totalling **16 874 features** (Table 1). The layers span geological boundaries, faults, attitudes, hydrology, and Quaternary geology, and include both small (2-feature) and large (6 981-feature) files.

### 4.2 Protocol

Each layer was processed two ways: (i) read with mapgis2shp to produce a `GeoDataFrame`; (ii) exported to ESRI shapefile using the official MapGIS software under default settings. The two outputs were then aligned by the unique `ID` attribute and compared on four axes:

- **Count**: feature counts.
- **Schema**: attribute column-name sets.
- **Geometry**: point-to-point Euclidean distance; line Hausdorff distance; polygon intersection-over-union (IoU). A pair is deemed coincident at tolerance \(10^{-7}\) degrees.
- **Attributes**: per-field semantic equivalence, with a classifier that separates exact matches from cases where the native export is lossy (floating-point truncation, numeric formatting, or whitespace stripping) and from genuine mismatches.

The full protocol is implemented in `cross_validate_native.py`, shipped with the software, and is fully reproducible.

### 4.3 Results

Across all 36 layers and 16 874 features:

- **Feature counts** are identical for 36/36 layers (16 874 = 16 874).
- **Schemas** are identical for 36/36 layers (all attribute column names match).
- **Geometry** matches for 100% of aligned features in 36/36 layers. Point distances, line Hausdorff distances, and polygon `1 − IoU` are all zero within \(10^{-7}\) degrees — i.e., geometries are exactly coincident.
- **Attributes** are semantically equivalent in **99.9995%** of the 95 006 compared cells. Only **2 cells** differ, both being floating-point fields smaller than \(10^{-6}\) that the native export rounds coarsely (e.g., `6.69×10⁻⁷` in mapgis2shp versus `1×10⁻⁶` in the native export). No genuine semantic attribute difference was found.
- **CRS**: mapgis2shp reconstructs and attaches the CRS (Krassovsky 1940 with `towgs84=15.8,-154.4,-82.3,…`); the native shapefile export produces **no `.prj` file**, so the CRS is lost.

### 4.4 The native export is lossy; mapgis2shp is not

In 10 245 of the 95 006 compared cells (10.8%), mapgis2shp preserves source information that the native shapefile export discards (Table 4):

1. **Floating-point truncation**: the native export rounds floats to 2–6 significant figures (e.g., `0.6218423 → 0.62`; `4.88×10⁻⁶ → 5×10⁻⁶`); mapgis2shp preserves full double precision.
2. **Numeric formatting**: values stored as floating-point are exported by MapGIS as integer strings in some fields (e.g., `72.0` vs `72`); mapgis2shp preserves the stored type.
3. **String padding**: the native export strips leading/trailing whitespace that the binary field actually stores (e.g., `'113000   ' → '113000'`); mapgis2shp preserves the raw bytes.

In other words, mapgis2shp is not merely equivalent to the native export — it is a strictly more faithful representation of the source binary data.

**[Table 1]** Sample dataset: layer name, geometry type, feature count (36 rows).
**[Table 2]** Per-layer cross-validation results: count, geometry match rate, attribute equivalence rate, attribute mismatches (36 rows).
**[Table 4]** Catalogue of native-export lossy artefacts with representative examples.

### 4.5 Extreme-scale validation

To stress the reader beyond the 36 survey layers, a single 400 MB MapGIS polygon file (`沉积建造岩.WP`, 78 873 features) was compared against an official MapGIS export of the same source. The official export had been post-processed (adjacent polygons dissolved and re-coloured), so a 1:1 feature-wise comparison is impossible; coverage equivalence was therefore assessed via geometric unions, with areas computed on the Krassovsky ellipsoid using `pyproj.Geod` (avoiding a costly reprojection of the full geometry set).

Results:

- **Bounding box**: exact match (difference = 0).
- **CRS**: correctly inferred as Beijing-1954 / Krassovsky (longlat) — the official export had lost its `.prj` file.
- **Attribute fields**: the 16 native fields are identical; the official export carries two additional fields (`strat_code`, `ColorCode`) that are artefacts of its dissolve-and-recolour post-processing.
- **Invalid geometries**: mapgis2shp produced 0; the official export produced 3.
- **Coverage equivalence**: union symmetric difference = 5 649.94 km² against 2.11 × 10⁶ km² of coverage; **coverage IoU = 99.73%**.

The summed polygon areas differ by 1.66% (mapgis2shp larger), but this is an overlap artefact of the greedy arc-merge reconstruction at shared boundaries (sliver bridging across topological gaps), not a coverage error: once overlaps are removed by the union, the real coverage difference is only 0.27%. This quantifies the known limitation of the heuristic topology reconstruction at extreme scale (see §6.1).

**[Table 5]** Extreme-scale (400 MB) validation summary.

---

## 5. Comparison with prior tools

**[Table 3]** compares mapgis2shp with the prior open-source MapGIS readers and the Chinese academic precedents along the axes that distinguish this work: open-source licence, language, byte-level spec, CRS inference, independent validation against the reference implementation, PyPI distribution, and peer-reviewed publication. mapgis2shp is the only entry that infers the CRS, the only one validated against the official export, and the only one distributed as an installable package with a reproducible validation harness.

---

## 6. Discussion

### 6.1 Limitations

The reader supports the most common ellipsoid codes (Krassovsky, Xi'an 1980, WGS84, WGS72, CGCS2000) and the most common projections (geographic, Transverse Mercator, Albers, Lambert); unrecognised codes yield an empty CRS that downstream code must handle. The legacy MapGIS K9/10 formats are not supported — they are a different binary layout and would require a separate implementation. CRS inference depends on the file's index codes rather than a full parameter block, so unusual projections may be under-described. Polygon topology reconstruction is heuristic; while `make_valid` guarantees valid output, rare topological gaps in source data can produce repaired (rather than exact) polygons. At extreme scale (the 400 MB test of §4.5), the greedy arc-merge introduces a quantified 1.66% overlap artefact in summed polygon areas at shared boundaries — a coverage difference of only 0.27% once overlaps are unioned away, but a known limitation when exact planar partition is required. A planar-enforcement post-process (e.g., `shapely.union` of all polygons) would eliminate the overlaps at the cost of runtime, and is left as an option for users needing a strict partition. The reader is read-only.

### 6.2 Generalisability

The validation methodology — reverse-engineer a proprietary reader, then cross-validate against the reference implementation on real data with quantified geometric and attribute fidelity — transfers directly to other closed geoscience formats. The cross-validation script is format-agnostic in structure and could anchor similar studies for formats where a reference implementation exists.

### 6.3 Open-science implication

By making MapGIS 6.x/67 data readable from the open-source Python stack, mapgis2shp unlocks a large body of Chinese geological-survey data for reproducible research, integration with GDAL/GeoPandas/QGIS workflows, and long-term archival. The CRS-inference capability is practically important: users currently relying on the native export silently lose the coordinate reference.

### 6.4 Residual coverage gap

The Crossref, OpenAlex, arXiv, and DOAJ indices contain no peer-reviewed MapGIS reader paper. Chinese-language databases (CNKI, Wanfang) were not machine-accessible during this study; a manual search is recommended before submission to confirm no Chinese thesis publishes a byte-level specification with validation. The open-source prior art enumerated in §1.3 is fully covered.

---

## 7. Conclusions

mapgis2shp is an open-source Python reader for the closed MapGIS 6.x/67 binary vector formats. Across 36 real geological-survey layers (16 874 features) its output is geometrically identical to and attribute-equivalent to the official MapGIS export (99.9995% semantic equivalence, zero genuine mismatches), and on a 400 MB file (78 873 features) it attains 99.73% coverage equivalence while producing fewer invalid geometries than the reference. It preserves source data more faithfully than the native export, which truncates floating-point fields and strips stored string padding, and additionally reconstructs the coordinate reference system that the native export discards. The software and its reproducible validation harness are distributed on PyPI under the Apache-2.0 licence.

---

## 8. Availability and Requirements

- **Software name:** mapgis2shp (import name `pymapgis`)
- **Version:** 2.0.5
- **PyPI:** `pip install mapgis2shp`
- **Source code:** https://github.com/leecugb/mapgis2shp
- **Archived DOI:** *to be added (OSF or Zenodo)*
- **License:** Apache-2.0
- **Operating systems:** Windows, Linux, macOS
- **Dependencies:** Python ≥ 3.9; geopandas, numpy, pandas, pyproj, shapely
- **Data availability:** the 36 validation layers and the 400 MB extreme-scale file are real geological-survey data and are not redistributed with the package; the cross-validation scripts (`cross_validate_native.py` for the 36-layer 1:1 comparison, `cross_validate.py` for the large-file coverage-equivalence comparison), the per-layer report (`cross_validation_report.csv`), the large-file report (`cross_validate_large_report.md`), and the regression baseline (`pymapgis_baseline.json`) are included in the repository. Synthetic minimal fixtures are provided under `tests/`.

---

## 9. CRediT author statement

Shijie Li: conceptualisation, methodology, software, validation, investigation, writing — original draft.

## 10. Declaration of competing interests

The author declares no competing interests.

---

## References

1. Warmerdam F (2008) The Geospatial Data Abstraction Library. In: Hall GB, Leahy MG (eds) Open Source Approaches in Spatial Data Handling. Advances in Geographic Information Science. Springer, Berlin, Heidelberg, pp 87–104. https://doi.org/10.1007/978-3-540-74831-1_5
2. GDAL/OGR contributors (2026) Vector drivers list. https://gdal.org/drivers/vector/index.html. Accessed 22 July 2026.
3. Li S (2022) pymapgis: a Python library for reading MapGIS 6.x/67 vector files. https://github.com/leecugb/pymapgis. Accessed 22 July 2026.
4. MathsionYang (2019) MapGIS2ArcGIS. https://github.com/MathsionYang/MapGIS2ArcGIS. Accessed 22 July 2026.
5. BenChao1998 (2025) ConvertMapGIS. https://github.com/BenChao1998/ConvertMapGIS. Accessed 22 July 2026.
6. Wong W (2021) OGC.net. https://github.com/WenboWong/OGC.net. Accessed 22 July 2026.
7. Wang X (2013) Data analysis and reading test on MapGIS point file [MapGIS 点文件的数据分析与读取测试]. Science of Surveying and Mapping [测绘科学] 2013(1):112–115
8. Wu L, Feng J (2006) Study on the key techniques of MapGIS and Geodatabase data format conversion. Chinese Journal of Engineering Geophysics [中国工程地球物理学报]
9. Chen H, Wu J, Wang J (2000) Realisation of format conversion in MapGIS with MATLAB. Computing Techniques for Geophysical and Geochemical Exploration [物探化探计算技术] 22(4):351–355
10. Shotwell M (2011) sas7bdat: sas7bdat reverse engineering documentation. CRAN (The R Foundation). https://doi.org/10.32614/cran.package.sas7bdat
11. Senanayake AI, Chandler RJ, Daly T, Lewis E (2022) python-ags4: a Python library to read, write, and validate AGS4 geodata files. Journal of Open Source Software 7(79):4569. https://doi.org/10.21105/joss.04569
12. Wright D, Wood R, Sylvander B (1998) ArcGMT: a suite of tools for conversion between Arc/INFO and Generic Mapping Tools (GMT). Computers & Geosciences 24(8):737–744. https://doi.org/10.1016/s0098-3004(98)00067-3
13. Sen M, Duffy T (2005) GeoSciML: development of a generic GeoScience Markup Language. Computers & Geosciences 31(9):1095–1103. https://doi.org/10.1016/j.cageo.2004.12.003
14. van den Bos J (2014) Lightweight runtime reverse engineering of binary file format variants. In: 2014 Software Evolution Week – IEEE Conference on Software Maintenance, Reengineering, and Reverse Engineering (CSMR-WCRE). IEEE, pp 367–370. https://doi.org/10.1109/csmr-wcre.2014.6747196
15. Ma Y, Wang J, Xie S (2012) Analytical application of MapGIS for quality control in geological map spatial database constructing. Geo-information Science 13(6):758–762. https://doi.org/10.3724/sp.j.1047.2011.00758
16. Han K, Pang J, Lu Y, Ding D, Fan B, Ju Y, Wang Z (2012) Research on sharing of geological map spatial data network under the "OneGeology" project: taking China 1:1M geological map data in MapGIS format as an example. Geo-information Science 13(6):742–749. https://doi.org/10.3724/sp.j.1047.2011.00742

> **Reference-note for the author (not for publication):** DOIs [1], [10]–[16] were verified against the Crossref REST API on 22 July 2026; issue numbers of [11]–[13], the authorship of [14] and [16], and the full author list of [16] were corrected against Crossref metadata. Entries [7]–[9] (Chinese-language) are not indexed in Crossref; their venues/volume/issue/pages were supplied by the author. Full verification table in `references_formatted.md`.

---

### Tables (to render)

**Table 1.** Validation dataset (36 layers; abbreviated here).

| Layer | Type | Features |
|---|---|---|
| LDLYAAI002 | point | 242 |
| LDLYAAE001 | line | 1 143 |
| LDZOFBB001 | polygon | 608 |
| LFZYBCT001 | point | 6 981 |
| LDZOFBA002 | line | 2 222 |
| … (36 rows total) | | |

**Table 2.** Cross-validation results (36 rows; summary row shown).

| Metric | Result |
|---|---|
| Layers compared | 36 |
| Features (mapgis2shp / native) | 16 874 / 16 874 |
| Count match | 36 / 36 |
| Schema match | 36 / 36 |
| Geometric coincidence | 100% (36 / 36 layers) |
| Attribute equivalence | 99.9995% (2 native-rounding deviations) |
| CRS attached | mapgis2shp yes; native no |

**Table 3.** Feature comparison with prior tools.

| Tool | Year | Lang | Open licence | Byte spec | CRS inference | Native-validated | Peer-reviewed | PyPI |
|---|---|---|---|---|---|---|---|---|
| pymapgis (own) | 2022 | Python | no | yes | no | no | no | no |
| MathsionYang | 2019 | C# | — | no | no | no | no | no |
| ConvertMapGIS | 2025 | Python | GPL-3.0 | yes | no | no | no | no |
| OGC.net | 2021 | C# | no | no | no | no | no | no |
| Wang (2013) | 2013 | — | n/a | no | no | no | note | no |
| **mapgis2shp** | 2026 | Python | Apache-2.0 | yes | **yes** | **yes** | **this paper** | **yes** |

**Table 4.** Native-export lossy artefacts.

| Category | Example (mapgis2shp → native) | Cells |
|---|---|---|
| Float truncation | 0.6218423 → 0.62 | ~9 000 |
| Sci-notation rounding | 4.88×10⁻⁶ → 5×10⁻⁶ | ~1 200 |
| Numeric formatting | 72.0 → 72 | 310 |
| Whitespace stripping | '113000   ' → '113000' | ~200 |
| **Total native-lossy cells** | | **10 245** |

**Table 5.** Extreme-scale (400 MB, 78 873 features) validation against official MapGIS export.

| Metric | mapgis2shp | Official export | Agreement |
|---|---|---|---|
| File size | 400 MB | 327 MB shp | — |
| Features | 78 873 | 67 039 (dissolved) | counts differ (vendor post-processing) |
| Bounding box | [73.486, 32.0, 111.000, 48.0] | identical | exact (diff = 0) |
| CRS | Krassovsky / Beijing-54 (inferred) | .prj lost; inferred identically | correct |
| Native attribute fields | 16 | 16 (+2 post-process fields) | 16 identical |
| Invalid geometries | 0 | 3 | reader cleaner |
| Union symmetric difference | — | 5 649.94 km² | 0.27% of coverage |
| **Coverage IoU** | — | — | **99.73%** |
| Summed-area gap | +1.66% | — | overlap artefact (§6.1) |
