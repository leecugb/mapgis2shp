# Contributing to mapgis2shp

Thank you for contributing to **mapgis2shp** (the Python import name is
`pymapgis`). Bug reports, format evidence, documentation, tests, and focused
code changes are all welcome. Participation is subject to the
[Code of Conduct](CODE_OF_CONDUCT.md).

## Project scope

The published package covers:

- Reading, writing, and converting MapGIS 6.x/67 `.wt`, `.wl`, and `.wp` files
- Attribute and coordinate-reference-system decoding
- Polygon-topology reconstruction and regeneration
- Point, line, and polygon graphic-parameter decoding
- Structural parsers for `Subgraph.lib` and `LINESTY.lib`
- Documentation, tests, validation tools, and interoperability fixes for these
  capabilities

Geological semantic calibration, map-specific adjudication, and cartographic
rendering are outside the published package. Do not make release modules or the
wheel/sdist depend on those concerns. Support for a different format family,
such as MapGIS K9/10, should begin with a design discussion rather than being
combined with a focused bug fix.

## Collaborate in public

Use [GitHub Issues](https://github.com/leecugb/mapgis2shp/issues) for bug reports,
design proposals, and questions, and use pull requests for proposed changes.
Public threads provide the collaboration and decision record needed for an open,
auditable project.

For a substantial change, open an issue before implementation. Describe the
problem, the proposed scope, the evidence needed to evaluate success, and any
compatibility risks. Keep important decisions and their reasons in the issue or
pull-request thread rather than only in private conversation.

## Report a useful bug

Include, where applicable:

1. `pymapgis.__version__`, the Python version, and the operating system
2. The input format and a minimal reproduction
3. The expected and actual behaviour, including the complete traceback
4. Whether the problem concerns geometry, attributes, CRS, graphic parameters,
   a graphic library, the CLI, or native-format writing
5. Reference evidence, such as an official MapGIS export or plain-text pair,
   if available

Attach a sample only when you have the right to redistribute it. Do not upload
confidential survey data, credentials, or licensed symbol libraries. A small
synthetic fixture that reproduces the problem is usually more useful than a
large restricted dataset.

## Set up a development environment

The package supports Python 3.9 and later.

```bash
git clone https://github.com/leecugb/mapgis2shp.git
cd mapgis2shp
python -m pip install -e ".[dev]"
```

Useful checks are:

```bash
python -m pytest
python -m ruff check .
python verify_pymapgis.py
python verify_pymapgis.py --roundtrip
```

The last two commands inspect compatible MapGIS files in the current directory.
Tests that require unavailable real-data fixtures may skip; this is expected.
Never replace a skipped or unavailable validation with a fabricated pass. In a
pull request, state clearly which checks you ran and which you could not run.

## Evidence rules for format work

MapGIS binary interpretation must remain evidence-led:

- Give byte offsets, record layouts, representative values, and sample counts
  when proposing a format change.
- Distinguish a verified layout from a candidate interpretation and from an
  unknown field. Do not turn a plausible-looking value into a confirmed meaning.
- Prefer independent evidence, such as paired binary and official plain-text
  exports (`.wal`, `.wat`, or `.wap`), native MapGIS display/export behaviour,
  or multiple independent datasets.
- Preserve contradictions and edge cases in the issue record. Do not silently
  change source codes or select only examples that support a hypothesis.
- Unknown CRS codes must remain unresolved rather than being guessed. Likewise,
  unsupported symbol or library records must not be replaced with invented
  geometry.
- Symbol, style, colour, and pattern numbers are library-local. Evaluate them
  against the originating library and version, not against an assumed universal
  mapping.

A Reader–Writer–Reader round trip establishes internal consistency only. It is
not equivalent to opening the written file successfully in MapGIS, matching an
official export, or reproducing vendor rendering. Report these as different
validation categories.

## Tests and implementation expectations

For a code change:

- Add or update tests that would fail without the change.
- Cover both Reader and Writer when a shared layout or graphic parameter is
  affected.
- Retain Python 3.9 compatibility and the Ruff configuration in
  `pyproject.toml` (100-character line limit).
- Preserve GBK text handling, typed attributes, missing values, CRS behaviour,
  and polygon shell/hole/shared-boundary topology where relevant.
- Avoid new runtime dependencies unless their need has been discussed first.
- Update `README.md`, `docs/MapGIS_Vector_Format.md`, or other affected
  documentation when behaviour or a documented layout changes.

For a performance change, report the hardware, software versions, input sizes,
repeat count, timing scope, and raw before/after results. State whether package
imports are included and how peak memory was measured. A median alone is not a
reproducible benchmark protocol.

## Pull-request checklist

Keep each pull request focused and reviewable. Before requesting review, check
that you have:

- [ ] Explained the problem, behaviour change, and evidence
- [ ] Linked the relevant issue and kept the public decision record complete
- [ ] Added or updated appropriate tests and documentation
- [ ] Run the available tests and Ruff checks, or disclosed anything not run
- [ ] Distinguished round-trip, native-export, native-application, and rendering
      validation where relevant
- [ ] Avoided unrelated version bumps, release actions, and generated artifacts
- [ ] Confirmed that code, data, fixtures, and third-party material may be shared

Reviewers may ask for a smaller change, additional counterexamples, or clearer
evidence before merging. A request for more evidence is not a rejection of the
contribution; it protects the reliability of the format implementation.

## Licensing and provenance

Contributions are accepted under the project's
[Apache License 2.0](LICENSE). By submitting a contribution, you confirm that
you have the right to submit it under those terms.

Preserve existing copyright and licence notices. For third-party code, data, or
documentation, provide the source, licence, and any required attribution so its
provenance can be reviewed. Do not copy material with an incompatible licence or
unclear redistribution rights. Follow the repository's existing notice practice
when adding files; maintainers may request additional provenance information
during licence or OSGeo review.

## Questions and conduct

Use a public issue for technical questions so that the answer can help others.
Use the private contact in the [Code of Conduct](CODE_OF_CONDUCT.md) only for
conduct-related reports or matters that genuinely cannot be discussed publicly.
