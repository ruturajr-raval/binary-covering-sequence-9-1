# Common-Backbone Overlap-61 Support Stages

Historical campaign notice: the status below records the 2026-09-02 CP-SAT
stages. The complete finite classification in
`evidence/exact-backbone-overlap61-20260904/` now resolves every support size
at exact overlap 61. The untraced solver statuses here are not used as proof
evidence.

This directory retains exact support-size stages for the two anchor cases
left unresolved by the unrestricted repeated-window campaign.

For both anchors 0 and 16:

- support sizes 61 through 65 returned `INFEASIBLE`;
- support sizes 66 through 68 returned `UNKNOWN` after 180 seconds.

The other eight anchors were already infeasible without fixing support size.
Support size 69 is retained in a separate complete ten-anchor campaign, and
support size 70 is the all-distinct campaign.

No independently checkable proof trace was emitted. These statuses reduce the
computational frontier but do not constitute a mathematical exclusion.

## Retained Files

- `summary.json` records the exact stage matrix and remaining cases.
- `support*-anchor*.json` records each model result and solver statistics.
- `source/` contains the exact repair model, graph model, and verifier used by
  the stages.
- `files.sha256` authenticates every retained file except the manifest itself.

## Reproduce

From the repository root:

```bash
mkdir -p /tmp/common-backbone61-support-stages
for support_size in 61 62 63 64; do
  for anchor in 0 16; do
    PYTHONDONTWRITEBYTECODE=1 python3 \
      evidence/common-backbone-cover61-support-stages-20260902/source/repair_support.py \
      data/candidates/l9-r1-common-backbone-64.json \
      "/tmp/common-backbone61-support-stages/support${support_size}-anchor${anchor}.json" \
      --n 9 --radius 1 --length 70 \
      --anchor-edge "$anchor" --partition-anchor \
      --connectivity tree --exact-overlap 61 \
      --support-size "$support_size" --allow-repeated-windows \
      --time-limit 120 --workers 1 --seed 1
  done
done
for support_size in 65 66 67 68; do
  for anchor in 0 16; do
    PYTHONDONTWRITEBYTECODE=1 python3 \
      evidence/common-backbone-cover61-support-stages-20260902/source/repair_support.py \
      data/candidates/l9-r1-common-backbone-64.json \
      "/tmp/common-backbone61-support-stages/support${support_size}-anchor${anchor}.json" \
      --n 9 --radius 1 --length 70 \
      --anchor-edge "$anchor" --partition-anchor \
      --connectivity tree --exact-overlap 61 \
      --support-size "$support_size" --allow-repeated-windows \
      --time-limit 180 --workers 1 --seed 1
  done
done
```

To check the retained manifest:

```bash
cd evidence/common-backbone-cover61-support-stages-20260902
shasum -a 256 -c files.sha256
```
