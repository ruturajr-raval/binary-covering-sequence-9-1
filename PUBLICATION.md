# Release v0.3.0

## Result

This release provides the preprint and reproducible certificate for a
fixed-backbone exclusion at length 70.

Let `B` be the explicit 64-edge support retained in the repository. Every
connected nonnegative integral circulation of total mass 70 uses at most 61
distinct edges of `B`. The bound is tight for cyclic words. A complete
classification of the overlap-61 shell checks all 41,664 omission triples,
retains 188 residual flows, and finds exactly eight connected completions.
Six leave nine binary 9-words uncovered within radius 1, and two leave ten.
None is a covering sequence.

It follows that every valid length-70 binary radius-1 covering sequence, if
one exists, uses at most 60 distinct edges of `B`.

## Evidence

The common-backbone certificate retains all 168 overlap-62 residual vectors.
A semantic validator checks every vector and reruns the connector and detour
exclusions used by the proof.

The overlap-61 classification is reproduced by separate Python and C++
implementations. A semantic validator checks all 188 residual flows, all
eight connected completions, and their uncovered-word sets. Four exhaustive
small-instance oracles test the finite decomposition, including a
residual-mass-9 case.

The focused replay uses only the Python standard library and a C++20 compiler:

```bash
make paper-replay PYTHON=python3 CXX=c++
```

The command builds the deterministic arXiv source archive, extracts it into a
clean temporary directory, authenticates its manifest, reruns both finite
classifications, and compares the two overlap-61 implementations.

## Claims

This release claims:

- the exact overlap ceiling `61` for the stated backbone at total mass 70;
- the complete classification of the overlap-61 shell; and
- the covering-specific consequence that every valid length-70 cover has
  backbone overlap at most `60`.

This release does not claim:

- a valid length-70 covering sequence;
- nonexistence of a length-70 covering sequence;
- a new upper or lower bound on `L(9,1)`;
- that the chosen backbone is canonical or optimal; or
- conclusions for lengths other than 70.

The known interval remains `62 <= L(9,1) <= 71`.

## Review

Independent mathematical review is invited for the path-cycle
decomposition, the completeness of the two finite enumerations, and the
combination of their conclusions. No external mathematical review is claimed
in this release.

## Preprint And Archive

The self-contained manuscript is in `paper/main.tex`. The deterministic arXiv
source archive is built at
`dist/arxiv/binary-covering-sequence-9-1.tar.gz`.

Citation metadata is in `CITATION.cff`. The exact v0.3.0 release is archived
at version DOI
[10.5281/zenodo.22313901](https://doi.org/10.5281/zenodo.22313901).
All repository versions are collected under the concept DOI
[10.5281/zenodo.22260691](https://doi.org/10.5281/zenodo.22260691).
