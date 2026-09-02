# Common-Backbone Overlap-61 All-Distinct Covering Search

This directory retains the complete ten-case CP-SAT campaign for a 70-bit
radius-1 covering sequence with 70 distinct cyclic windows and exactly 61
edges of the retained 64-edge common backbone.

All ten disjoint zero-ball anchor cases in this all-distinct class returned
`INFEASIBLE`. Repeated-window candidates were not modeled. The campaign
emitted no independently checkable proof trace, so these statuses are
computational evidence rather than a mathematical exclusion. They are not
used in the common-backbone theorem and do not change the known bounds on
`L(9,1)`.

The separate graph-theoretic theorem proves that every 70-bit cyclic sequence
has backbone overlap at most 61. It does not exclude covering sequences at
overlap 61, including the repeated-window class left open here.

## Retained Files

- `summary.json` records the complete anchor partition, parameters, source
  hashes, and aggregate status counts.
- `anchor-*.json` contains the exact result and solver statistics for each
  anchor.
- `anchor-*.log` contains the corresponding solver output.
- `source/` contains the exact portfolio runner, support-repair model, and
  graph model used by the campaign.
- `files.sha256` authenticates every retained file except the manifest itself.

Absolute local command prefixes in `summary.json` were normalized to
repository-relative commands. Solver results and statistics were not changed.

## Reproduce

From the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 \
  evidence/common-backbone-cover61-20260902/source/run_backbone_portfolio_v1.py \
  data/candidates/l9-r1-common-backbone-64.json \
  /tmp/common-backbone61 \
  --n 9 \
  --radius 1 \
  --length 70 \
  --exact-overlap 61 \
  --connectivity tree \
  --time-limit 600 \
  --parallel-cases 10 \
  --solver-workers 1 \
  --seed 1
```

The solver version and machine scheduling can change detailed counters while
preserving the mathematical model.

To check the retained manifest:

```bash
cd evidence/common-backbone-cover61-20260902
shasum -a 256 -c files.sha256
```
