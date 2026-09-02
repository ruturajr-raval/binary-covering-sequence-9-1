# Length-70 Disconnected-Support Repair Evidence

This directory retains one balanced radius-1 covering support with 70 distinct
order-9 edges and an exact connected-support repair portfolio around it.

The retained support covers all 512 target words, but its directed support has
five components with edge counts

```text
1, 1, 4, 4, 60.
```

It is therefore not a cyclic covering-sequence certificate.

The two immediate de Bruijn cross-joins each merge the 4-edge and 60-edge
components, but each modified support leaves four target words uncovered. The
two loop components also remain separate.

## Exact Repair Portfolio

Each repair model requires:

- exactly 70 distinct selected edges;
- de Bruijn balance and one connected Eulerian support;
- radius-1 coverage of all 512 words;
- at least 53 edges shared with the retained support;
- one case from the disjoint zero-ball anchor partition.

The overlap requirement permits at most 17 edge replacements.

| Anchor | Workers | Limit | Status |
| ---: | ---: | ---: | --- |
| 0 | 8 | 300 seconds | `INFEASIBLE` |
| 1 | 2 | 600 seconds | `UNKNOWN` |
| 2 | 2 | 600 seconds | `UNKNOWN` |
| 4 | 2 | 600 seconds | `UNKNOWN` |
| 8 | 2 | 600 seconds | `UNKNOWN` |
| 16 | 2 | 600 seconds | `UNKNOWN` |
| 32 | 2 | 600 seconds | `UNKNOWN` |
| 64 | 2 | 600 seconds | `UNKNOWN` |
| 128 | 1 | 300 seconds | `INFEASIBLE` |
| 256 | 1 | 30 seconds | `INFEASIBLE` |

The seven `UNKNOWN` cases prevent any exclusion of the complete overlap
neighborhood. No model produced a valid sequence, and CP-SAT emitted no proof
trace for the three infeasible cases.

These artifacts establish no new upper or lower bound on `L(9,1)`.

## Reproduction

One partition can be rerun with:

```bash
python3 tools/repair_support.py \
  evidence/graph-repair70/anchor-0-seed-1.json \
  repair.json \
  --n 9 \
  --radius 1 \
  --length 70 \
  --anchor-edge 1 \
  --partition-anchor \
  --connectivity tree \
  --minimum-overlap 53 \
  --time-limit 600 \
  --workers 2 \
  --seed 51
```

The JSON artifacts record the source hashes, solver version, parameters,
status, propagation counters, branch counts, and deterministic time for each
case.
