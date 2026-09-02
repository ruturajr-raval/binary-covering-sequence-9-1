# Common-Backbone Overlap-61 Support-69 Search

This directory retains the complete ten-anchor CP-SAT campaign for 70-bit
radius-1 covering cycles with exact common-backbone overlap 61 and exactly 69
distinct cyclic windows.

An exact support size of 69 means that one window occurrence is repeated.
Eight anchor cases returned `INFEASIBLE`. Anchors 0 and 16 returned `UNKNOWN`
after 300 seconds each.

No independently checkable proof trace was emitted. This campaign narrows the
one-repeat class but does not exclude it mathematically.

## Retained Files

- `summary.json` records the complete anchor partition, exact support size,
  parameters, source hashes, and status counts.
- `anchor-*.json` records each exact model result and solver statistics.
- `anchor-*.log` contains the corresponding solver output.
- `source/` contains the exact runner, repair model, graph model, and verifier
  used by the campaign.
- `files.sha256` authenticates every retained file except the manifest itself.

Absolute local command prefixes in `summary.json` were normalized to
repository-relative commands. Solver results and statistics were not changed.

## Reproduce

From the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 \
  evidence/common-backbone-cover61-support69-20260902/source/run_backbone_portfolio.py \
  data/candidates/l9-r1-common-backbone-64.json \
  /tmp/common-backbone61-support69 \
  --n 9 \
  --radius 1 \
  --length 70 \
  --exact-overlap 61 \
  --support-size 69 \
  --connectivity tree \
  --allow-repeated-windows \
  --time-limit 300 \
  --parallel-cases 10 \
  --solver-workers 1 \
  --seed 1
```

To check the retained manifest:

```bash
cd evidence/common-backbone-cover61-support69-20260902
shasum -a 256 -c files.sha256
```
