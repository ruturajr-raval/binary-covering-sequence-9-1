# Common-Backbone Overlap-61 Support-69 Partitions

This directory retains exact partitions of the support-size-69 cases left
unresolved at anchors 0 and 16.

At anchor 0:

- a repeated backbone edge is infeasible;
- a repeated outside loop is infeasible;
- a repeated outside nonloop remains `UNKNOWN`.

At anchor 16:

- repeated loops are infeasible both inside and outside the backbone;
- a repeated backbone nonloop remains `UNKNOWN`;
- a repeated outside nonloop remains `UNKNOWN`.

These are exhaustive scope and loop-status partitions of the one-repeat
class. Three nonloop cases remain unresolved. No independently checkable proof
trace was emitted.

## Retained Files

- `summary.json` records the partition tree and exact remaining cases.
- `*.json` records each model result and solver statistics.
- `source/` contains the exact repair model, graph model, and verifier used by
  the partitions.
- `files.sha256` authenticates every retained file except the manifest itself.

## Reproduce

From the repository root:

```bash
mkdir -p /tmp/common-backbone61-support69-partitions
run_case() {
  name="$1"
  anchor="$2"
  scope="$3"
  kind="$4"
  PYTHONDONTWRITEBYTECODE=1 python3 \
    evidence/common-backbone-cover61-support69-partitions-20260902/source/repair_support.py \
    data/candidates/l9-r1-common-backbone-64.json \
    "/tmp/common-backbone61-support69-partitions/${name}.json" \
    --n 9 --radius 1 --length 70 \
    --anchor-edge "$anchor" --partition-anchor \
    --connectivity tree --exact-overlap 61 \
    --support-size 69 --allow-repeated-windows \
    --duplicate-scope "$scope" --duplicate-kind "$kind" \
    --time-limit 180 --workers 1 --seed 1
}
run_case reference-anchor000 0 reference any
run_case outside-anchor000 0 outside any
run_case outside-loop-anchor000 0 outside loop
run_case outside-nonloop-anchor000 0 outside nonloop
run_case reference-anchor016 16 reference any
run_case outside-anchor016 16 outside any
run_case reference-loop-anchor016 16 reference loop
run_case reference-nonloop-anchor016 16 reference nonloop
run_case outside-loop-anchor016 16 outside loop
run_case outside-nonloop-anchor016 16 outside nonloop
```

To check the retained manifest:

```bash
cd evidence/common-backbone-cover61-support69-partitions-20260902
shasum -a 256 -c files.sha256
```
