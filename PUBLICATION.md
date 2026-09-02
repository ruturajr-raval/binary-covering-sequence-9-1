# Release v0.1.0

## What Was Done

This release independently verifies the reported 71-bit `(9,1)` covering
sequence, retains exact and heuristic search evidence for length 70, and
establishes an exact finite overlap result for one fixed 64-edge backbone.

## Supported Claim

Every 70-bit cyclic binary sequence contains at most 61 distinct edges of the
retained 64-edge backbone, and a retained 70-bit witness attains overlap 61.
The repository also contains independently checked local DRAT exclusions and
clearly separated solver results without proof traces.

## Not Claimed

- No valid 70-bit covering sequence has been found.
- No new upper or lower bound on `L(9,1)` is claimed.
- No global length-70 impossibility result is claimed.
- Solver `INFEASIBLE`, `UNKNOWN`, and timeout results without proof traces are
  not promoted to mathematical exclusions.
- No theorem-priority claim is made before focused novelty review and
  independent external mathematical review.

## Evidence

`evidence.json` provides the machine-readable evidence map. The fixed-backbone
result is documented in `docs/COMMON_BACKBONE_LEMMA.md` and authenticated
under `evidence/common-backbone-lemma-20260902/`. The complete claim boundary
is recorded in `release.json`. `release-manifest.sha256` authenticates the
principal release files.

## Reproduction

```bash
make build
make test
python3 -m pip install -r requirements-solver.txt
make solver-test
make verify-baseline
make analyze-baseline
make analyze-backbone
```

## Limitations And Remaining Work

Nine multiplicity-aware overlap-61 cases remain unresolved, along with the
broader search outside the retained backbone shell. The full common-backbone
calculation has one production implementation and independent small-instance
oracles, but not yet a second full-scale implementation.

## Citation

Citation metadata is provided in `CITATION.cff`. The release metadata in
`.zenodo.json` is prepared for durable archival.
