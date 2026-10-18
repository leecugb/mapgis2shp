# GitHub issue draft: Subgraph.lib tail region (#1996+) record structure

> Posted 2026-10-18 as https://github.com/leecugb/mapgis2shp/issues/1
> Scope: format support only — not geological semantic adjudication.

## Title

Subgraph.lib tail region (#1996+): integrate probe-level record model into slib decode()

## Body

### Summary

`pymapgis.slib` currently decodes `Subgraph.lib` symbols #0–#1995 (indexed
region #0–#1839 plus an adjudicated tail chain to #1995). The remaining
7,803,626 bytes (~85% of the file) start at symbol #1996 and use record
structures that the tail walk does not accept. `SubgraphLib.decode()` returns
`None` for every symbol beyond #1995 — an honest stop, but library coverage
is incomplete: real sheets reference high-numbered symbols from this region
(e.g. #7331), so the region must be parsed before those symbols can be read
or rendered.

### Root cause (identified 2026-10-18)

The adjudicated tail walk scans header lengths up to 512 bytes. The first
record of the new region (#1996) has a 748-byte header, so the walk rejects
it and stops. Beyond that, the region is structurally heterogeneous: at
least three descriptor-layout variants have been observed so far.

### What has been established so far (probe evidence, updated 2026-10-18)

A validation-gated structural walk — (u16 type, u16 n) + uninterpreted
descriptor area (enumerated per 10-byte block) + subpath point-count table
(entries ≥ 2 summing to `n//2`) + `n×4` f32 payload — now chains **all 5,364
records of the region (#1996–#7359, 100% byte coverage to EOF)**:

- every record's payload sanity holds (≥90% of values within |v| ≤ 3);
- a whole-chain geometry audit shows all 5,364 records' coordinates within
  [-1.375, +1.485] mm — zero records outside ±2 mm;
- spot decodes are coherent glyphs (e.g. #7331 = two r≈0.5 mm circles,
  two r≈0.18 circles, two closed 32-point loops);
- descriptor-block semantics (the field values inside the 10-byte blocks)
  remain uninterpreted — the walk treats them as opaque header bytes.

Relaxations used by the probe, pending adjudication: type cap raised from
255 to 0x7FFF (types 397/413 observed), `n` cap raised from 4000 to 16000
(n=4300+ observed), count-table entries ≥ 2.

### Requested outcome

1. Integrate the new-region record model into `pymapgis.slib` so that
   `decode()` covers #1996–#7359 with the same honest-stop guarantee as the
   current region (validation failures must still return `None`, never
   invented geometry).
2. Document where decoding stops and why, per structural variant.
3. Add redistributable fixtures (small synthetic records, one per variant)
   and regression tests asserting that invalid records decode to `None`.
4. Keep the scope strictly to format support.

### Notes

- Probe script kept in-repo as `_slib_tail7331_probe.py` (v8).
- Ground-truth confirmation from the MapGIS symbol editor (export of a
  #1996+ symbol, e.g. #7331) would pin the descriptor semantics directly
  and is welcome.
