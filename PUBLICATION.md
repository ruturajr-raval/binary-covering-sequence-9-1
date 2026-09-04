# Release v0.2.0

## What Was Done

This release closes the complete exact-overlap-61 shell for the retained
64-edge common backbone at length 70.

Every candidate in this shell omits exactly three backbone edges and has a
residual integral flow of mass 9. The finite classification checks all 41,664
omission triples, retains 188 admissible residual flows, and reconstructs all
eight connected 70-edge circulations. Six leave nine words uncovered and two
leave ten, so none is a radius-1 cover.

## Supported Claim

Every 70-bit cyclic binary sequence contains at most 61 distinct edges of the
retained 64-edge backbone. No valid 70-bit radius-1 covering sequence attains
overlap 61. Therefore every valid 70-bit cover has backbone overlap at most
60.

The first statement is graph-theoretic and applies to every 70-bit cyclic
binary sequence. The second uses the radius-1 covering condition.

## Verification

The classification is reproduced by separate Python and C++ implementations.
They agree on every aggregate count and every connected completion.

A standalone semantic validator rechecks all 188 retained residuals, derives
the component and coverage histograms, reconstructs every connected Eulerian
circulation, verifies the retained witness, and rejects altered or incomplete
attestations. Four complete small-instance oracles include a
residual-mass-9, three-terminal case.

The exact source snapshots, both output artifacts, and their SHA-256 manifest
are retained under `evidence/exact-backbone-overlap61-20260904/`.

## Not Claimed

- No valid 70-bit covering sequence has been found.
- Candidates with backbone overlap at most 60 remain open.
- No new upper or lower bound on `L(9,1)` is claimed.
- No global length-70 impossibility result is claimed.
- Historical solver statuses without proof traces are not used as theorem
  evidence.
- No priority claim is made before independent external mathematical review.

## Reproduction

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-solver.txt
make build
make test PYTHON=.venv/bin/python
make solver-test PYTHON=.venv/bin/python
make verify-baseline PYTHON=.venv/bin/python
make analyze-baseline PYTHON=.venv/bin/python
make analyze-backbone PYTHON=.venv/bin/python
make analyze-exact-overlap PYTHON=.venv/bin/python
```

The focused evidence replay is documented in
`evidence/exact-backbone-overlap61-20260904/README.md`.

## Remaining Work

The immediate frontier is the overlap-at-most-60 region. A complete solution
still requires either an independently verified 70-bit construction or
checked exclusions strong enough to settle every admissible length relevant
to a new lower bound.

## Review Request

Independent mathematical review is requested for the finite-flow reduction,
the completeness of the residual enumeration, and the combination with the
prior maximum-overlap theorem. The repository provides byte-reproducible
artifacts and does not make a priority claim before that review.

## Citation

Citation metadata is provided in `CITATION.cff`, and `.zenodo.json` supplies
the archival metadata. The stable concept DOI for all versions is
[10.5281/zenodo.22260691](https://doi.org/10.5281/zenodo.22260691).
