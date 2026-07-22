# Cover Letter — Earth Science Informatics

**To:** The Editor-in-Chief, *Earth Science Informatics*
**From:** Shijie Li (corresponding author), on behalf of all authors
(Shijie Li, Haiyang He, Xu Sun, Haoyang Qin, Xiaoyu Liu)
**Affiliation:** Xi'an Mineral Resources Survey, China Geological Survey, Xi'an, China
**Date:** 22 July 2026
**Article type:** Software article
**Manuscript title:** *mapgis2shp: an open-source Python reader for the MapGIS 6.x/67 binary vector formats, with coordinate-reference inference and fidelity validation against the native MapGIS export*

---

Dear Editor,

I am pleased to submit the enclosed manuscript for consideration as a *Software article* in *Earth Science Informatics*.

MapGIS is the dominant geographic information system in Chinese geological surveying, yet its native binary vector formats---\`.wt\` (point), \`.wl\` (line), and \`.wp\` (polygon)---are closed and undocumented. We verified that GDAL/OGR ships no MapGIS driver (the official driver index and the entire OSGeo/gdal tracker contain no mention of it), and QGIS, GRASS, SAGA, and WhiteboxTools therefore cannot open these files. Geological-survey data held in the format are consequently locked out of the open-source geospatial stack unless the proprietary software is used.

Several open-source MapGIS readers already exist, including the author's own earlier \`pymapgis\` (2022). However, **none has been independently validated against the reference implementation, none infers the coordinate reference system, and none has been peer-reviewed.** The submitted manuscript closes all three gaps:

1. **First peer-reviewed software paper** on a MapGIS 6.x/67 reader (Crossref, arXiv, and OpenAlex return no such paper).
2. **First reader independently validated against the official MapGIS export**, on two tiers: 36 real survey layers (16,874 features) with exact geometric coincidence and 99.9995% attribute equivalence; and a 400 MB file (78,873 features) with 99.73% coverage IoU.
3. **First reader that infers and attaches the CRS**---the native shapefile export silently drops the \`.prj\`, whereas the reader reconstructs the PROJ string.
4. A **reproducible, Apache-2.0 validation harness** distributed on PyPI, with a 36-file regression baseline.

A notable finding of the validation is that the reader is *more* faithful to the source binary than the official shapefile export: the native export truncates floating-point fields, reformats numeric values, and strips stored string padding, while the reader preserves all of these.

The work fits *Earth Science Informatics*' Software article type, with its required "Design and Implementation" and "Availability and Requirements" sections. The methodology---reverse-engineering a proprietary reader and quantifying fidelity against the reference implementation---generalises to other closed geoscience formats, which I hope makes it of broad interest to the journal's readership.

I confirm that this manuscript is original, has not been published elsewhere, and is not under consideration by another journal. The software is open-source under Apache-2.0; the validation layers are real geological-survey data and are not redistributed, but the validation scripts, reports, and a synthetic test suite are provided in the repository. The authors declare no competing interests. This work was supported by the National Science and Technology Major Project "Deep Earth Probe and Mineral Resources Exploration" (Program No. 2025ZD10069).

Thank you for your consideration.

Sincerely,

Shijie Li (corresponding author)
Xi'an Mineral Resources Survey, China Geological Survey, Xi'an, China
Email: 1045105061@qq.com
ORCID: [to be added]

**Software availability:** https://github.com/leecugb/mapgis2shp (PyPI: \`pip install mapgis2shp\`)
**Archived DOI:** https://doi.org/10.5281/zenodo.21487339 (v2.0.6)
