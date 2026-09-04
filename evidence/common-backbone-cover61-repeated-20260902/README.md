# Common-Backbone Overlap-61 Repeated-Window Search

Historical campaign notice: the status below records the 2026-09-02 CP-SAT
run. The complete finite classification in
`evidence/exact-backbone-overlap61-20260904/` now resolves the full
exact-overlap-61 shell. The untraced solver statuses here are not used as
proof evidence.

This directory retains the complete ten-anchor CP-SAT campaign for 70-bit
radius-1 covering cycles with exact common-backbone overlap 61 and arbitrary
window multiplicities.

The model permits both all-distinct and repeated-window candidates. Eight
anchor cases returned `INFEASIBLE`. Anchors 0 and 16 returned `UNKNOWN` after
300 seconds each.

No independently checkable proof trace was emitted. At the time of this
campaign, the eight infeasibility statuses were computational evidence and
the two timeouts left the shell unresolved. The later finite classification
supersedes that frontier.

## Retained Files

- `summary.json` records the complete anchor partition, parameters, source
  hashes, and status counts.
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
  evidence/common-backbone-cover61-repeated-20260902/source/run_backbone_portfolio.py \
  data/candidates/l9-r1-common-backbone-64.json \
  /tmp/common-backbone61-repeated \
  --n 9 \
  --radius 1 \
  --length 70 \
  --exact-overlap 61 \
  --connectivity tree \
  --allow-repeated-windows \
  --time-limit 300 \
  --parallel-cases 10 \
  --solver-workers 1 \
  --seed 1
```

To check the retained manifest:

```bash
cd evidence/common-backbone-cover61-repeated-20260902
shasum -a 256 -c files.sha256
```
