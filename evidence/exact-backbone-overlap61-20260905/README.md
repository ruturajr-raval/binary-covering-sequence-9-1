# Exact Overlap-61 Publication Evidence

This directory retains the finite classification of the maximum-overlap shell
for the fixed 64-edge backbone at length 70.

## Certified Claim

Every connected nonnegative integral circulation of total mass 70 that uses
exactly 61 distinct edges of the backbone is one of eight retained
edge-multiplicity vectors. All eight have 70 distinct edges. Six leave nine
binary 9-words uncovered within radius 1, and two leave ten. None is a
radius-1 cover.

Combined with the common-backbone overlap theorem, every valid length-70
binary radius-1 covering sequence uses at most 60 distinct backbone edges.

## Retained Classification

The computation checks all 41,664 triples of omitted backbone edges. Exactly
188 residual integral flows satisfy the mass, divergence, and omitted-edge
conditions. Their component-count distribution is:

```text
1 component: 8
2 components: 72
3 components: 80
4 components: 28
```

The retained files are:

- `analysis.json`, produced by the Python enumerator;
- `independent-check.json`, produced by a separate C++ implementation;
- `source/`, containing the exact source snapshots; and
- `files.sha256`, authenticating every retained file except the manifest.

The semantic validator checks all 188 residual flows and reconstructs every
connected completion and uncovered-word set. Four exhaustive small-instance
oracles test the enumeration, including a residual-mass-9 case with three
divergence terminals.

The Python analyzer and validator use only the standard library. The second
implementation requires a C++20 compiler.

## Reproduce

From the repository root:

```bash
mkdir -p build/publication

PYTHONDONTWRITEBYTECODE=1 python3 -B \
  evidence/exact-backbone-overlap61-20260905/source/analyze_exact_backbone_overlap_v2.py \
  data/candidates/l9-r1-common-backbone-64.json \
  build/publication/exact-overlap61-analysis.json \
  --overlap-witness \
    data/candidates/l9-r1-70-backbone-overlap-61.txt \
  --n 9 --radius 1 --candidate-length 70 --exact-overlap 61

c++ -std=c++20 -O3 -Wall -Wextra -Wpedantic -Werror \
  evidence/exact-backbone-overlap61-20260905/source/exact_overlap_checker_v1.cpp \
  -o build/publication/exact-overlap-checker

build/publication/exact-overlap-checker \
  data/candidates/l9-r1-common-backbone-64.json \
  > build/publication/exact-overlap61-independent.json

PYTHONDONTWRITEBYTECODE=1 python3 -B \
  evidence/exact-backbone-overlap61-20260905/source/verify_exact_backbone_overlap_v2.py \
  build/publication/exact-overlap61-analysis.json \
  build/publication/exact-overlap61-independent.json \
  --support data/candidates/l9-r1-common-backbone-64.json \
  --analyzer \
    evidence/exact-backbone-overlap61-20260905/source/analyze_exact_backbone_overlap_v2.py \
  --witness data/candidates/l9-r1-70-backbone-overlap-61.txt

cmp build/publication/exact-overlap61-analysis.json \
  evidence/exact-backbone-overlap61-20260905/analysis.json
cmp build/publication/exact-overlap61-independent.json \
  evidence/exact-backbone-overlap61-20260905/independent-check.json
```

Check the retained file manifest with:

```bash
cd evidence/exact-backbone-overlap61-20260905
shasum -a 256 -c files.sha256
```

## Scope

This is an exact classification of one fixed-backbone shell. It does not
exclude candidates with overlap at most 60, produce a length-70 covering
sequence, or establish a new upper or lower bound on `L(9,1)`.
