# Exact Classification At Backbone Overlap 61

## Statement

Let `B` be the 64-edge set in
`data/candidates/l9-r1-common-backbone-64.json`.

Every connected nonnegative integral circulation of total multiplicity 70
that uses exactly 61 distinct edges of `B` has one of eight explicitly
enumerated edge-multiplicity vectors. All eight vectors have 70 distinct
edges. Six cover 503 of the 512 binary 9-bit words within radius 1, and two
cover 502.

Consequently, no 70-bit cyclic binary radius-1 covering sequence has exact
overlap 61 with `B`.

The earlier common-backbone theorem proves that every 70-bit cyclic binary
sequence has overlap at most 61 with `B`. Combining the two results gives the
stronger covering-specific conclusion:

```text
Every valid 70-bit radius-1 covering sequence has backbone overlap at most 60.
```

This closes the complete overlap-61 shell, including the nine CP-SAT cases
that previously remained `UNKNOWN`.

## Reduction To A Finite Enumeration

A cyclic binary sequence corresponds to a nonnegative integral circulation in
the order-8 binary de Bruijn graph:

1. Each 9-bit window is a directed edge from its 8-bit prefix to its 8-bit
   suffix.
2. Edge multiplicities are balanced at every vertex.
3. The positive-multiplicity support is weakly connected.
4. The total edge multiplicity is the sequence length.

Suppose a length-70 circulation uses exactly 61 distinct edges of `B`. It
omits a three-edge set `E` from `B`. Retain one copy of every edge in
`B \ E`. The retained part has mass 61, so the remaining residual flow has
mass 9.

The residual flow cannot use an edge of `E`, because that would increase the
backbone overlap above 61. Its divergence is uniquely determined by the
retained 61-edge part.

For each of the

```text
C(64, 3) = 41,664
```

omission triples, the positive and negative residual divergence has one, two,
or three units. Every nonnegative integral residual flow decomposes into:

1. one directed source-to-sink walk for each divergence unit; and
2. a balanced remainder, which decomposes into directed closed walks.

Every walk in such a decomposition has length at most 9.

## Exhaustive Construction

The retained Python analyzer performs the following complete enumeration:

1. Precompute every bit-appending directed walk of length 1 through 9 from
   every backbone vertex. This gives 65,408 walks.
2. Enumerate every balanced integral de Bruijn flow of mass 0 through 9 by
   combining cyclic-word closed walks. The counts are:

```text
1, 2, 4, 8, 16, 32, 64, 128, 256, 512
```

3. For each omission triple, pair the divergence sources and sinks in every
   possible way.
4. Combine all admissible source-to-sink walks with every balanced remainder
   of the required mass.
5. Reject residuals that use an omitted backbone edge.
6. Deduplicate the resulting edge-multiplicity vectors.
7. Check residual mass, divergence, exact overlap, weak connectedness, support
   size, and radius-1 coverage.

The path-plus-cycle decomposition is exhaustive for nonnegative integral
flows, so every length-70 circulation at exact overlap 61 appears in this
enumeration.

## Exact Counts

| Quantity | Count |
| --- | ---: |
| Omission triples checked | 41,664 |
| Triples with at least one residual flow | 88 |
| Raw exact decompositions | 192 |
| Distinct residual flows | 188 |
| Residuals with 1 component | 8 |
| Residuals with 2 components | 72 |
| Residuals with 3 components | 80 |
| Residuals with 4 components | 28 |
| Connected completions | 8 |
| Connected completions with 70 distinct windows | 8 |
| Connected completions covering all 512 words | 0 |

The connected coverage-gap histogram is:

```text
9 uncovered words: 6 completions
10 uncovered words: 2 completions
```

The retained overlap-61 witness is recovered as the first connected
completion. Its omitted backbone edges are `13`, `307`, and `409`.

## Independent Verification

Two separate implementations reproduce the same classification:

- `tools/analyze_exact_backbone_overlap.py`
- `src/exact_overlap_checker.cpp`

They agree on every aggregate count and on all eight connected completions,
including each omission triple, residual edge multiset, support size, and
uncovered-word set.

The Python implementation is also checked against direct enumeration of every
cyclic binary sequence in four complete small instances. Those tests include
zero-divergence, nonzero-divergence, full three-omission, and
residual-mass-9 three-terminal cases.

A separate validator semantically checks all 188 retained residual flows. It
recomputes mass, divergence, circulation balance, exact overlap, connected
components, support size, radius-1 coverage, every histogram, and the complete
set of eight connected completions. Mutation tests confirm that synchronized
counter changes, omitted completions, altered residual metadata, and invalid
flow mass are rejected.

## Reproduction

Run:

```bash
make build
make analyze-exact-overlap PYTHON=.venv/bin/python
.venv/bin/python -m unittest tests.test_exact_backbone_overlap -v
```

The generated files are:

```text
build/l9-r1-exact-overlap61-analysis.json
build/l9-r1-exact-overlap61-independent.json
```

## Scope

This result excludes only the exact overlap-61 shell for length 70. It does not
exclude candidates whose backbone overlap is at most 60, and it does not
establish a new upper or lower bound on `L(9,1)`.

The immediate construction and exclusion frontier is therefore the
overlap-at-most-60 region.
