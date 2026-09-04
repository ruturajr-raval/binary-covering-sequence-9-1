# Literature Check

## Definition

Chee, Etzion, Ta, and Vu define an `(n,R)` covering sequence as a cyclic
binary sequence whose length-`n` windows have covering radius at most `R`.

Primary source:

- Y. M. Chee, T. Etzion, H. Ta, and V. K. Vu, "Constructions of Covering
  Sequences and Arrays", arXiv:2502.08424.
- F. Chung and J. Cooper, "De Bruijn Cycles for Covering Codes",
  arXiv:math/0310385.

Their February 2025 table records:

```text
62 <= L(9,1) <= 93
```

## Current Upper Bound

Christopher D. Rosin reported a 71-bit construction in a May 2025 preprint.
The certificate is distributed through CPro1:

- C. D. Rosin, arXiv:2505.23881.
- Constructive-Codes/CPro1,
  commit `827f02b4048fc96a6b79f0970c87ca5a54f31f40`.

The certificate is retained in `data/baseline/l9-r1-71.txt` and is checked
from the definition by this repository.

## Novelty Audit

Searches refreshed on 2026-09-04:

- arXiv title, abstract, and full-text searches for covering sequences and
  `(9,1,70)`;
- GitHub code and repository searches for `L(9,1)`, `(9,1,70)`,
  `result-9-1-70`, and related filenames;
- direct inspection of CPro1 commit
  `827f02b4048fc96a6b79f0970c87ca5a54f31f40`, whose covering-sequence results
  include `result-9-1-71-seed1000.txt` but no length-70 result;
- inspection of H. Ta and V. K. Vu, "Near-Optimal Covering Sequences",
  arXiv:2606.29236;
- inspection of T. Etzion and E. Yaakobi, "Covering Sequence Codes for Cyclic
  Codes", arXiv:2607.14840.

No 70-bit construction was located. This is a dated search result, not a
guarantee that no unpublished or unindexed construction exists. The audit
must be repeated before any record, priority, construction, or new-bound
claim.

## Exact-Search Strengthening

D. Gijswijt and S. Polak derive the strengthened covering-code inequalities
used here:

- D. Gijswijt and S. Polak, "Semidefinite lower bounds for covering codes",
  arXiv:2504.01932.

For binary radius-1 covers at length 9, summing the ten sphere inequalities
around a target gives

```text
5 * A_0 + A_1 + A_2 >= 5,
```

where `A_i` is the number of selected support words at Hamming distance `i`
from that target.

Chung and Cooper also explicitly note that existence is not monotone in the
sequence length. Therefore an impossibility result at exactly 70 would not by
itself establish a lower bound of 71.
