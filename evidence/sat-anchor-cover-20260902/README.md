# Canonical SAT Anchor Cover

This directory retains two 22-case CaDiCaL portfolios for length 70, together
with independently checked proof traces for the two cases that were solved.
The portfolios use one anchored transition case from every reflection orbit
after rotation, complement, and zero-ball normalization.

## Retained Campaigns

- `complete/` covers every length-70 binary cyclic candidate. All 22 cases
  reached their 300-second limits and returned `UNKNOWN`.
- `support70/` adds the condition that all 70 cyclic windows are distinct.
  Twenty cases returned `UNKNOWN`. Cases `anchor-000-p0-s0` and
  `anchor-000-p1-s0` returned `UNSATISFIABLE`.
- `proofs/` contains the exact compressed CNFs, binary DRAT traces, CaDiCaL
  logs, and DRAT-trim logs for the two unsatisfiable cases.
- `source/` contains the exact CNF generator and portfolio runner used for the
  retained campaigns.
- `files.sha256` authenticates every retained campaign, proof, and source file.

The two solved cases express an elementary adjacency condition. With
`W_0 = 0^9` and successor bit zero, `W_1 = W_0`, contradicting the requirement
that all 70 windows be distinct. Reflection gives the predecessor condition.
Thus an occurrence of `0^9` in an all-distinct cyclic window sequence must be
flanked by one bits.

The complete campaign produced no construction and no impossibility proof.
Twenty all-distinct cases and every repeated-window case remain unresolved.
The checked traces validate the optimized proof pipeline, but these results do
not change the known bound on `L(9,1)`.

## Regenerate A Proof Formula

For `anchor-000-p0-s0`:

```bash
python3 source/generate_cnf_v2.py /tmp/anchor-000-p0-s0.cnf \
  --encoding pattern \
  --n 9 \
  --radius 1 \
  --length 70 \
  --exact-support 70 \
  --anchor-word 0 \
  --anchor-predecessor-bit 0 \
  --anchor-successor-bit 0 \
  --seed-sequence /tmp/zeros-70.txt \
  --max-distance 35 \
  --no-symmetry
```

The seed file is 70 zero bits separated by spaces. Change
`--anchor-predecessor-bit` to `1` to regenerate `anchor-000-p1-s0`.
The expected uncompressed CNF digests are recorded in `evidence.json`.

## Check A Retained Proof

```bash
gzip -dc proofs/anchor-000-p0-s0.cnf.gz > /tmp/case.cnf
gzip -dc proofs/anchor-000-p0-s0.drat.gz > /tmp/case.drat
drat-trim /tmp/case.cnf /tmp/case.drat -i
```

The checker must finish with `s VERIFIED`. The retained checker logs record
that both formulas were verified.
