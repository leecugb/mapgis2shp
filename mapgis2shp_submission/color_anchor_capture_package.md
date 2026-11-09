# Native MapGIS colour-anchor capture and provenance package

Status: existing computational evidence assembled; native capture metadata remains incomplete.

## 1. Existing evidence

The current repository already contains the following verifiable artifacts:

- `output/color_truth_audit.json`, generated at `2026-11-07T03:24:54.056081+08:00`.
- `docs/color_parsing_logic.md`, section 4.1, recording the 14 native-dialogue reference values.
- `tests/test_pure.py`, including `test_extended_dialog_anchors` and `test_native_node_layout_and_white`.
- The original `Colorlib.lib` and `Pcolor.lib` supplied for regression, with SHA-256 recorded in `tests/fixtures/jwd_slib_manifest.json`.
- Git commit `db6de75be16078f746d31e00df7c1b57a1a09e64`, recording four WP-dialogue observations on 2026-10-22: 1046, 914, 1226 and 1239.
- Git commit `82dfe3a038630c0f8f5cdff39220048e9cab4dee`, showing that the full 14-anchor table was present in the repository on 2026-10-23.
- The 2026-11-07 full-table internal consistency audit. Its `match=true` results are project-generated comparisons, not independent native evidence.

Indirect evidence associates the native work with MapGIS 6.7 through `docs/osgeo_application_checklist.md` and the 2026-10-18 native acceptance session. This does not establish the exact application build used for every colour-dialogue observation and still requires the capture operator's confirmation.

Original library paths recorded by `output/color_truth_audit.json`:

- `D:\SLIB\SLIB\Colorlib.lib`, SHA-256 `ee7d841116835b2b01236c178a8d657d5e31733d2782c3673415451ee3eee6d4`.
- `D:\SLIB\SLIB\Pcolor.lib`, SHA-256 `7911bc7ae16a72d2d19372ef710754bc24145b2ebb0234c874abb72776c84fd3`.

These artifacts establish the recorded RGB values, the 32-byte node model, the `N + 3` node mapping and the channel offset `+28`. They do not by themselves establish the MapGIS application version used for the native dialogue observations or provide the corresponding screenshots.

## 2. Required capture metadata

Complete every field before marking this gate closed.

| Field | Current status | Required completion |
|---|---|---|
| MapGIS application name and exact version/build | Indirect evidence for MapGIS 6.7; exact build not recorded | Confirm and enter the value shown by the application About dialog |
| Operating system and architecture | Not recorded | Record the capture environment |
| Capture operator | Not recorded | Record the person performing the observation |
| Capture date and time zone | Four anchors on 2026-10-22; full table present on 2026-10-23; internal audit on 2026-11-07 | Confirm the actual native-dialogue capture chronology and time zone |
| Library path used by MapGIS | Historical paths are recorded | Confirm that MapGIS opened the same files identified by the hashes above |
| Capture procedure | Not recorded | Follow section 3 |
| Screenshots or native logs | Not found | Supply at least one readable screenshot per anchor or an equivalent native export log |
| English evidence summary | Draft in section 5 | Finalize only after all fields are complete |

## 3. Capture protocol

1. Work on copies of the two libraries and never edit the original SLIB files.
2. Record the MapGIS application name, exact version/build, operating system and library paths before opening the colour dialogue.
3. Compute and record the SHA-256 of the libraries actually opened by MapGIS. Confirm that they match the values in section 1.
4. Open each colour number in the native colour dialogue and record the displayed RGB values.
5. Save a legible screenshot for each anchor. Use the file naming convention `mapgis_<version>_colour_<number>.png`.
6. If screenshots are unavailable, provide a native export log containing equivalent values and explain why it is an equivalent native observation.
7. Do not adjust the displayed values to match the expected table. Record any discrepancy exactly and retain the evidence.
8. Compare the native observations with `output/color_truth_audit.json` and the automated tests.
9. Compute SHA-256 for every screenshot or log and add the files to the evidence manifest.
10. Prepare the final English summary only after all native evidence has been archived.

## 4. Anchor checklist

The RGB values below are existing recorded expectations, not substitutes for native screenshots.

| Colour number | Recorded RGB | Screenshot or log | Verified version/build |
|---:|---|---|---|
| 881 | 242, 255, 102 | [pending] | [pending] |
| 882 | 229, 255, 76 | [pending] | [pending] |
| 903 | 242, 178, 76 | [pending] | [pending] |
| 904 | 242, 153, 51 | [pending] | [pending] |
| 914 | 217, 255, 25 | [pending] | [pending] |
| 923 | 178, 255, 0 | [pending] | [pending] |
| 1045 | 255, 255, 215 | [pending] | [pending] |
| 1046 | 255, 255, 215 | [pending] | [pending] |
| 1051 | 255, 255, 255 | [pending] | [pending] |
| 1096 | 229, 229, 229 | [pending] | [pending] |
| 1224 | 255, 76, 215 | [pending] | [pending] |
| 1226 | 255, 127, 229 | [pending] | [pending] |
| 1239 | 242, 242, 242 | [pending] | [pending] |
| 1465 | 167, 222, 98 | [pending] | [pending] |

## 5. English evidence-summary draft

Do not paste this summary into the manuscript until the bracketed fields have been completed and the evidence files exist.

> Fourteen RGB reference values were recorded from the MapGIS colour dialogue using MapGIS `[exact version/build]` on `[operating system]`. The observations were made by `[operator]` on `[capture date and time zone]` using `Colorlib.lib` and `Pcolor.lib` whose SHA-256 values matched the external regression libraries. Screenshots or equivalent native logs for all fourteen observations, together with their hashes, accompany the manuscript as `color_anchor_evidence/`. The values are author-recorded native-dialogue observations rather than an independent MapGIS certification. Automated tests compare these recorded values with the decoded library nodes.

## 6. Closure rule

This gate may be marked closed only when:

- the exact MapGIS version/build and capture environment are documented;
- all fourteen anchors have corresponding native screenshots or equivalent native logs;
- the opened libraries match the recorded SHA-256 values;
- the evidence files and their hashes are included in the submission materials;
- the final English summary is supported by those files.

Until then, describe the existing values as recorded reference anchors with incomplete capture provenance. Do not describe them as a completed native visual acceptance procedure.
