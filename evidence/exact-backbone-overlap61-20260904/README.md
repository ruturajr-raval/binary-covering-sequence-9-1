# Exact Backbone-Overlap-61 Evidence

This directory retains the finite classification behind
`docs/EXACT_OVERLAP_61.md`.

## Certified Claim

Let `B` be the 64-edge support in
`data/candidates/l9-r1-common-backbone-64.json`. No 70-bit cyclic binary
radius-1 covering sequence uses exactly 61 distinct edges of `B`.

The earlier common-backbone theorem proves that every 70-bit cyclic binary
sequence uses at most 61 edges of `B`. Together, the two results imply that
every valid 70-bit radius-1 covering sequence uses at most 60 edges of `B`.

This is a complete exclusion of one fixed-backbone shell. It does not exclude
length-70 candidates with overlap at most 60, produce a 70-bit construction,
or change the known bounds on `L(9,1)`.

## Retained Classification

The computation checks all 41,664 triples of omitted backbone edges. Exactly
188 residual integral flows survive the mass, divergence, and omitted-edge
conditions. Eight give connected 70-edge circulations. Six leave nine words
uncovered and two leave ten words uncovered, so none is a radius-1 cover.

The retained files are:

- `analysis.json`, produced by the Python enumerator, with every active
  omission case, residual flow, and connected completion.
- `independent-check.json`, produced by the separate C++ implementation.
- `source/`, containing the exact source snapshots used for both calculations
  and the standalone artifact validator.
- `files.sha256`, authenticating every retained file except the manifest
  itself.

The Python enumerator is also tested against direct enumeration of every
cyclic sequence in four complete small instances. These include a
three-omission residual-mass-9 case with three divergence terminals. The
standalone validator semantically rechecks every retained residual, derives
all component and coverage histograms, reconstructs every connected Eulerian
circulation, and rejects altered or incomplete attestations.

## Reproduce

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-solver.txt

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  evidence/exact-backbone-overlap61-20260904/source/analyze_exact_backbone_overlap_v1.py \
  data/candidates/l9-r1-common-backbone-64.json \
  build/replay-exact-overlap61-analysis.json \
  --overlap-witness \
    data/candidates/l9-r1-70-backbone-overlap-61.txt \
  --n 9 \
  --radius 1 \
  --candidate-length 70 \
  --exact-overlap 61

c++ -std=c++20 -O3 -Wall -Wextra -Wpedantic -Werror \
  evidence/exact-backbone-overlap61-20260904/source/exact_overlap_checker_v1.cpp \
  -o build/replay-exact-overlap-checker

build/replay-exact-overlap-checker \
  data/candidates/l9-r1-common-backbone-64.json \
  > build/replay-exact-overlap61-independent.json

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  evidence/exact-backbone-overlap61-20260904/source/verify_exact_backbone_overlap_v1.py \
  build/replay-exact-overlap61-analysis.json \
  build/replay-exact-overlap61-independent.json \
  --support data/candidates/l9-r1-common-backbone-64.json \
  --analyzer \
    evidence/exact-backbone-overlap61-20260904/source/analyze_exact_backbone_overlap_v1.py \
  --witness data/candidates/l9-r1-70-backbone-overlap-61.txt

cmp build/replay-exact-overlap61-analysis.json \
  evidence/exact-backbone-overlap61-20260904/analysis.json
cmp build/replay-exact-overlap61-independent.json \
  evidence/exact-backbone-overlap61-20260904/independent-check.json
```

Check the retained manifest with:

```bash
cd evidence/exact-backbone-overlap61-20260904
shasum -a 256 -c files.sha256
```
