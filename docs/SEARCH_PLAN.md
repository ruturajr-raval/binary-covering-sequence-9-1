# Search Plan

## Phase 1 - Trust Anchor

- Independently verify the reported 71-bit certificate.
- Reject malformed, truncated, and mutated certificates.
- Record exact coverage histograms and certificate hashes.

## Phase 2 - Local Improvement

- Delete each position of the 71-bit certificate.
- Rank all 70-bit descendants by uncovered words and singleton coverage.
- Use targeted repair moves, one-bit flips, short multi-bit moves, tabu
  tenures, and deterministic restarts.
- Save every strict improvement with its seed and search parameters.
- Exhaust exact Hamming shells around unusually strong incomplete states.
- When a seed is a deep strict local optimum, use adaptive breakout weights
  rather than interpreting the plateau as impossibility evidence.
- Use beam ejection chains to repair one uncovered target while permitting a
  bounded set of newly uncovered targets. Preserve oriented beam states for
  root-relative heuristics, but canonicalize rotations and reflections for
  archive identity and orbit-distance reporting.

## Phase 3 - Exact Search

- Generate a direct SAT instance for length 70.
- Maintain both selector and pattern-variable encodings.
- Reverse-channel pattern variables when an exact distinct-window support size
  is requested. Use lag-XOR pairwise window distinctness when support equals
  sequence length, and the unary support counter for smaller support sizes.
- Maintain a de Bruijn edge-multiplicity formulation with independently
  checked flow, rooted-tree, and iterative-cut connectivity.
- Partition the ten zero-covering anchor cases to avoid duplicated search.
- For bit-level SAT, use the tested 22-case reflection-reduced cover over exact
  zero-ball anchor words and predecessor/successor transition bits.
- Add the radius-1 Van Wee inequalities.
- Split exact length 70 into support sizes 62 through 70 so duplicate
  multiplicities have tight domains.
- Enforce weight-layer cover inequalities and the repeat-defect budget in
  repeated-window stages.
- Enforce the active-vertex inequality in every radius-1 support stage and the
  cyclic weight-layer path cuts only when one connected cycle is required.
- Enforce stationarity marginals and autocorrelation parity, cover, and
  exact-length orbit constraints in repeated-window stages.
- Keep Walsh aggregates optional unless controlled benchmarks show a net
  solver benefit.
- Expose the exact unique duplicate in support-size-69 models and partition by
  duplicate class or fixed duplicate edge when aggregate cases stall.
- Generate balanced disconnected covering supports and search exact connected
  neighborhoods by support overlap.
- Apply the exact common-backbone theorem to exclude overlap 62 through 64
  before invoking a solver.
- Partition every support-repair neighborhood across all ten zero-ball anchors
  before treating it as a completed CP-SAT portfolio.
- Search all distinct-window lengths up to 70 in one at-most-length model.
- Use only sound rotation and reflection symmetry breaking.
- Disable global symmetry constraints inside fixed-seed Hamming balls.
- Add complement symmetry only with a separately tested cardinality encoding.
- If satisfiable, independently decode and verify the sequence.
- If unsatisfiable, retain a proof trace and verify it with an independent
  proof checker before making a lower-bound claim.
- Use proof-producing local exclusions to validate the SAT pipeline, while
  labeling their finite scope separately from any global impossibility claim.
- A lower bound of 71 requires excluding every length from 62 through 70,
  because existence is not monotone in sequence length.

## Current Exact Frontier

- All ten scheduled partitioned distinct-window at-most-70 bounded runs were
  executed: nine anchors are `UNKNOWN`, and one anchor is infeasible by a
  direct balance contradiction.
- All ten scheduled exact-length-70 support-69 bounded runs were executed:
  nine anchors are `UNKNOWN`, and the same final anchor is infeasible.
- No support-size stage is globally settled while any anchor remains
  `UNKNOWN`.
- A balanced disconnected 69-edge cover with component sizes 1, 4, 4, and 60
  is retained.
- CP-SAT reported all ten disjoint anchor models infeasible for connected
  distinct-window 69-edge covers sharing at least 58 edges with that support.
  Repeated-window sequences and more distant supports remain open, and no
  proof trace has independently certified the infeasibility result.
- Exact-support pattern formulas for support sizes 69 and 70 were each run
  with CaDiCaL 3.0.1 for 300 seconds. Both returned `UNKNOWN`.
- A binary DRAT proof now independently certifies that the retained six-gap
  seed has no valid length-70 sequence within Hamming distance 4. This is only
  a local exclusion; the direct enumerator already reaches distance 8.
- A balanced disconnected 70-edge cover with component sizes 1, 1, 4, 4, and
  60 is retained. Its two direct cross-joins each lose four covered targets.
- Exact connected-support repair at overlap at least 53 returned three
  `INFEASIBLE` and seven `UNKNOWN` anchor cases. The unresolved cases prevent
  a complete neighborhood exclusion, and no proof trace was emitted.
- The current graph model includes the active-vertex inequality and connected
  cyclic weight-layer path cuts, with exhaustive small-cycle and
  coefficient-level tests.
- The bit-level SAT model now has a complete 22-case reflection-reduced
  transition cover, complement symmetry, and an optimized all-distinct
  support-70 encoding.
- The complete bounded portfolio returned 22 `UNKNOWN` cases.
- The all-distinct portfolio returned two proof-checked elementary
  `UNSATISFIABLE` zero-anchor transitions and 20 `UNKNOWN` cases. The remaining
  20 cases are the nontrivial exact-support frontier.
- A 64-edge common backbone is retained. The next constructive shell fixes
  exact overlap 61 with this backbone across ten disjoint zero-ball anchors.
- A finite residual-flow proof establishes that every 70-bit cyclic sequence
  uses at most 61 backbone edges. The bound is tight for arbitrary cycles.
- The all-distinct exact-overlap-61 covering portfolio reported all ten
  anchors `INFEASIBLE`, but no proof trace was emitted. Repeated-window
  candidates were not modeled in that campaign.
- A separate multiplicity-aware portfolio reported eight anchors
  `INFEASIBLE` and anchors 0 and 16 `UNKNOWN`.
- Exact support staging closed sizes 61 through 65 computationally for the two
  hard anchors. Sizes 66 through 68 remain `UNKNOWN`.
- At support size 69, only three nonloop one-repeat partitions remain
  `UNKNOWN`: anchor 0 outside the backbone, and anchor 16 inside and outside
  the backbone.
- Overlaps 62 through 64 are closed by the graph-theoretic theorem. Future
  common-backbone searches should target the nine exact overlap-61 cases,
  certify any computational exclusions, or diversify to overlap at most 60.
- A proof-producing translation should replace indefinitely longer CP-SAT
  timeouts once the strongest discovery formulation is stable.

## Acceptance Threshold

A 70-bit sequence is a publishable construction only after independent
verification and a refreshed prior-art audit. Failed searches and solver
timeouts are evidence about methods, not mathematical results.
