# Common-Backbone Exclusion Evidence

This directory retains the exact finite computation behind the
common-backbone theorem in `docs/COMMON_BACKBONE_LEMMA.md`.

## Certified Claim

For the retained 64-edge de Bruijn backbone, every connected nonnegative
integral circulation of total multiplicity 70 uses at most 61 distinct
backbone edges. Equivalently, a 70-bit cyclic binary sequence cannot contain
62 or more distinct backbone windows.

The bound is exact. The retained 70-bit witness contains 61 backbone windows,
has 70 distinct cyclic windows, and is not a radius-1 covering sequence.

The result is graph-theoretic and does not use the radius-1 covering
constraints. It therefore does not prove that a 70-bit covering sequence is
impossible and does not change the known bounds on `L(9,1)`.

The retained analysis also includes two connected residuals at mass 7 as a
positive control. They show that the overlap theorem is specific to total
multiplicity 70 and is not monotone in cycle length.

## Retained Files

- `analysis.json` records the two backbone components, exhaustive connector
  counts, all 64 one-omission detour minima, all 2,016 two-omission cases,
  aggregate counts and component histograms for the 168 surviving residual
  flows, tight witnesses, and derived bounds.
- `source/analyze_common_backbone_v1.py` is the exact analyzer that generated
  `analysis.json`.
- `source/covering.py`, `source/flow_cp_sat.py`, and
  `source/repair_support.py` are the exact imported source snapshots needed
  by the analyzer.
- `files.sha256` authenticates every retained file except the manifest itself.

The analysis also authenticates the backbone and baseline input files by
SHA-256 digest.

## Reproduce

From the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 \
  evidence/common-backbone-lemma-20260902/source/analyze_common_backbone_v1.py \
  data/candidates/l9-r1-common-backbone-64.json \
  /tmp/common-backbone-analysis.json \
  --baseline data/baseline/l9-r1-71.txt \
  --overlap-witness \
    data/candidates/l9-r1-70-backbone-overlap-61.txt \
  --n 9 \
  --radius 1 \
  --candidate-length 70
cmp /tmp/common-backbone-analysis.json \
  evidence/common-backbone-lemma-20260902/analysis.json
```

To check the retained file manifest:

```bash
cd evidence/common-backbone-lemma-20260902
shasum -a 256 -c files.sha256
```
