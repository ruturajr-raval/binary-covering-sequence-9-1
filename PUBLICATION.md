# Release Dossier v0.3.0

## Release Identity

| Field | Value |
| --- | --- |
| Title | A Fixed-Backbone Exclusion for Length-70 Binary (9,1) Covering Sequences |
| Author | Ruturaj R Raval |
| Affiliation | Independent Researcher |
| ORCID | [0000-0003-4930-8981](https://orcid.org/0000-0003-4930-8981) |
| Tagged release | [`v0.3.0`](https://github.com/ruturajr-raval/binary-covering-sequence-9-1/releases/tag/v0.3.0) |
| Release date | 2026-09-05 |
| Audited release commit | `23563e82bc2466cbc88177c6c0a7d830061d687c` |
| Version DOI | [`10.5281/zenodo.22313901`](https://doi.org/10.5281/zenodo.22313901) |
| Concept DOI | [`10.5281/zenodo.22260691`](https://doi.org/10.5281/zenodo.22260691) |
| Archive status | Published Zenodo record with source and PDF asset hashes in `release.json` |
| License | MIT for project-original material |

## Claim-Safe Public Summary

For one explicit 64-edge backbone, every length-70 cyclic binary sequence has
backbone overlap at most 61. A complete classification proves that none of the
eight connected exact-overlap-61 completions is a radius-1 cover. Consequently,
every valid length-70 cover, if one exists, has backbone overlap at most 60.
This does not construct or globally exclude a 70-bit covering sequence and
does not change `62 <= L(9,1) <= 71`.

## Supported Result

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

## Verification And Evidence

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

## Manifest And Asset Verification

Use `release-manifest.sha256` from a clean checkout of tag `v0.3.0` to verify
the tracked release files. `release.json` records the audited release commit
and the SHA-256 values for the deterministic source archive and generated PDF.
The retained classification snapshots and their own manifests are under:

- `evidence/common-backbone-lemma-20260905/`; and
- `evidence/exact-backbone-overlap61-20260905/`.

The local release record does not contain a separate digest for the
Zenodo-generated `v0.3.0` repository ZIP, so no such digest is asserted here.

## Claim Boundary

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

## Provenance Boundary

The reported 71-bit baseline was published by Christopher D. Rosin and is
retained from CPro1 under Apache-2.0, as documented in `NOTICE`. The project
verification, search code, fixed-backbone theorem, finite classifications, and
documentation are independently developed and MIT licensed. No CPro1 program
source is copied.

## Review Status

Independent mathematical review is invited for the path-cycle
decomposition, the completeness of the two finite enumerations, and the
combination of their conclusions. No external mathematical review is claimed
in this release.

## Archive And Citation

The self-contained manuscript is in `paper/main.tex`. The deterministic arXiv
source archive is built at
`dist/arxiv/binary-covering-sequence-9-1.tar.gz`.

Citation metadata is in `CITATION.cff`. The exact v0.3.0 release is archived
at version DOI
[10.5281/zenodo.22313901](https://doi.org/10.5281/zenodo.22313901).
All repository versions are collected under the concept DOI
[10.5281/zenodo.22260691](https://doi.org/10.5281/zenodo.22260691).

Historical release scope is summarized in `RELEASE_NOTES.md`.

## Next Acceptance Gate

A global improvement requires one of two outcomes:

1. A valid 70-bit certificate accepted by both independent verifiers after a
   refreshed prior-art audit and external review.
2. Independently checked exclusions for every admissible length from 62
   through 70, unless a separate monotonicity theorem closes that requirement.
