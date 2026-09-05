# Binary Covering Sequence 9-1

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22260691.svg)](https://doi.org/10.5281/zenodo.22260691)

An independent verification and exact-search toolkit for finding or excluding
a 70-bit cyclic binary radius-1 covering sequence.

As of the literature and repository audit dated 2026-09-04, this repository
reproduces the reported 71-bit construction, provides independent verifiers,
proves that every 70-bit cyclic sequence uses at most 61 distinct edges of one
retained 64-edge common backbone, and proves that no valid 70-bit radius-1
cover can attain overlap 61. Therefore every valid 70-bit cover has backbone
overlap at most 60.

The supported scoped result concerns one fixed backbone. This project does not
claim a new construction, a new bound on `L(9,1)`, or a global impossibility
result.

The self-contained preprint is in `paper/main.tex`. Its deterministic arXiv
source archive includes the focused certificate sources, retained evidence,
and a clean standalone replay.

## The Problem

Let

```text
x_0, x_1, ..., x_(L-1)
```

be a cyclic binary sequence. Each starting position gives a cyclic 9-bit
window

```text
W_i = x_i x_(i+1) ... x_(i+8),
```

where indices are taken modulo `L`.

The sequence is a radius-1 covering sequence when every one of the 512 binary
9-bit words differs from at least one window `W_i` in at most one bit. The
minimum possible length is denoted `L(9,1)`.

In plain language: the sequence must expose a collection of overlapping cyclic
windows such that every possible 9-bit pattern is either present or is one bit
away from a present window.

## Origin And Duration

Chung and Cooper introduced covering de Bruijn sequences in 2004 as a
generalization of ordinary de Bruijn sequences. An ordinary de Bruijn sequence
contains every word exactly, while a covering sequence permits a bounded
Hamming error and can therefore be shorter.

Chee, Etzion, Ta, and Vu renewed the systematic construction problem in 2025.
Their table gave

```text
62 <= L(9,1) <= 93.
```

The lower bound `62` comes from the corresponding binary radius-1 covering-code
number: the cyclic windows of any valid sequence form a covering code.

Rosin then reported a 71-bit construction in a May 2025 preprint, improving
the upper bound by 22 symbols. The public frontier checked on 2026-09-04 was

```text
62 <= L(9,1) <= 71.
```

No public 70-bit construction was located in the dated literature and
repository audit. The nine-symbol gap had remained open for more than 15
months after the 71-bit construction appeared. This is a dated search result,
not a guarantee about unpublished work.

## Project Target

The immediate goal is a valid 70-bit sequence. One such certificate would
immediately improve the public upper bound to

```text
L(9,1) <= 70.
```

A lower bound of 71 would be substantially harder. Covering-sequence existence
is not monotone in the sequence length, so it is not enough to exclude exactly
70 bits. A complete result must exclude every still-admissible length from 62
through 70, or first prove a separate monotonicity result that closes that gap.
Each exclusion would require proof-producing exact search or a mathematical
proof checked independently.

## What This Project Did

1. Retrieved the 71-bit certificate from a pinned upstream commit and retained
   its license and provenance.
2. Implemented an independent Python verifier directly from the covering
   definition.
3. Implemented a separate C++ verifier and incremental search state.
4. Verified all 512 target words and recorded the certificate digest and exact
   coverage multiplicities.
5. Checked every one-position deletion of the 71-bit certificate. The best
   70-bit deletion leaves 13 words uncovered.
6. Built a deterministic multi-worker local search with one-bit, pair,
   triple, targeted repair, tabu, restart, and distance-deficit moves.
7. Improved the best project-local 70-bit state from 13 to 9 uncovered words.
8. Deterministically replayed the Apache-licensed CPro1 search and recovered a
   70-bit state with only six uncovered words.
9. Independently verified that incomplete state in Python and C++ and retained
   it as a search seed.
10. Built selector and pattern-variable exact SAT encodings with exhaustive
    tiny-instance projection tests against the independent verifier.
11. Reduced the unrestricted length-70 formula from 1,290,754 clauses to
    359,461 clauses with the pattern encoding.
12. Validated the exact pipeline end to end by constraining the known 71-bit
    certificate, solving it, decoding the model, and recovering the exact file.
13. Ran 14 selector-formula and eight pattern-formula Kissat seeds for 300 wall
    seconds each. Every run returned `UNKNOWN`.
14. Added an independently verified DIMACS model decoder and a symmetry-free
    fixed-seed Hamming-distance encoding.
15. Built a separate parallel enumerator and exhaustively evaluated all
    10,783,318,760 sequences within distance 8 of the retained six-gap seed.
16. Established by exhaustive computation that this ball contains no valid
    sequence and no state with fewer than six uncovered words.
17. Added adaptive breakout weighting to escape persistent local minima while
    retaining raw coverage as the only validity test.
18. Ran a 14-worker, 600,000-iteration breakout portfolio over three parameter
    schedules. It found no valid sequence and no raw improvement below six.
19. Hardened certificate writes, worker error propagation, parser boundaries,
    short-sequence moves, wide-window state handling, and arithmetic overflow
    checks.
20. Built an exact de Bruijn edge-multiplicity model with three independently
    tested connectivity formulations: flow, rooted arborescence, and iterative
    component cuts.
21. Proved the model-to-sequence equivalence and exhaustively matched
    feasibility of all three formulations against direct enumeration on small
    instances.
22. Added disjoint anchor cases, support-size stages, at-most-length search, and
    the radius-1 Van Wee inequalities.
23. Recovered and independently verified the 71-bit baseline through the new
    graph model before using it at length 70.
24. Executed all ten scheduled final-source bounded anchor runs for partitioned
    distinct support at every length up to 70.
25. Excluded the final partitioned distinct anchor by a direct balance
    contradiction; the other bounded cases returned `UNKNOWN`.
26. Added exact stationarity-marginal constraints for repeated-window stages.
27. Added autocorrelation parity, radius-1 covering, and exact odd-orbit
    constraints.
28. Derived and tested optional Walsh-transform aggregates, but left them off
    by default pending retained evidence that their dense rows improve search.
29. Added exhaustive identity checks and coefficient-level encoding tests for
    each new constraint family.
30. Ran every disjoint anchor in the one-duplicate stage at exact length 70
    with the strengthened final source. Nine cases returned `UNKNOWN`; the
    final partitioned anchor is infeasible by the same balance contradiction.
31. Replaced the scalar one-duplicate relaxation with an exact extended
    formulation that identifies the unique duplicated edge, its endpoint
    imbalance, loop status, and forced local support degrees.
32. Replaced weakened multiplicity half-cube rows with exact support
    aggregates and added optional pair-projection cover rows.
33. Found and independently checked a balanced 69-edge radius-1 cover whose
    directed support has four components of sizes 1, 4, 4, and 60.
34. Enumerated its immediate de Bruijn cross-joins. The two component-merging
    switches each leave four target words uncovered.
35. Added an exact connected-support repair tool with disjoint anchor cases,
    overlap neighborhoods, deterministic-work limits, and independent model
    decoding.
36. CP-SAT returned `INFEASIBLE` for every overlap-at-least-58 repair case
    across all ten disjoint anchors. Under the tested exact formulation, any
    connected distinct-window 69-edge covering cycle would need to replace at
    least 12 edges of this retained disconnected cover.
37. Added reverse pattern channeling and an exact unary cardinality encoding
    for the number of distinct cyclic windows.
38. Generated unrestricted exact-support formulas for support sizes 69 and 70.
    CaDiCaL 3.0.1 ran each for 300 seconds; both returned `UNKNOWN`.
39. Generated, trimmed, retained, and independently checked a binary DRAT
    proof that the distance-4 Hamming neighborhood of the six-gap seed contains
    no valid length-70 sequence.
40. Added beam ejection-chain search with bounded temporary damage, distant
    state archiving, actionable-target fallback, and overflow-safe option
    handling.
41. Added the radius-1 active-vertex inequality and connected cyclic
    weight-layer path cuts to the graph model, with exhaustive small-cycle and
    coefficient-level tests.
42. Corrected disconnected support sampling by disabling a
    connected-cycle-only orbit bound and added active-vertex cap and
    minimization options.
43. Found and independently checked a balanced 70-edge covering support with
    five components of sizes 1, 1, 4, 4, and 60.
44. Enumerated its two immediate cross-joins. Each merges the 4-edge and
    60-edge components but leaves four target words uncovered.
45. Ran all ten exact connected-support repair anchors at overlap at least 53.
    Three returned `INFEASIBLE` and seven returned `UNKNOWN`; no construction
    or complete neighborhood exclusion resulted.
46. Added fixed zero-ball anchors, predecessor and successor transition cases,
    complement symmetry, and a tested 22-case reflection-reduced SAT cover.
    The runner independently decodes and verifies every satisfiable model.
47. Replaced the support-70 unary cardinality counter with lag-XOR
    window-distinctness and de Bruijn balance clauses. With anchor and
    complement constraints, a production case has 41,357 variables and
    414,868 clauses instead of 72,774 variables and 539,988 clauses in the
    previous unrestricted formula.
48. Ran and retained the complete 22-case length-70 portfolio for 300 seconds
    per case. Every unrestricted case returned `UNKNOWN`.
49. Ran the corresponding all-distinct support-70 portfolio. Two zero-anchor
    cases were proof-checked `UNSATISFIABLE`, and the other 20 returned
    `UNKNOWN`. The solved cases express the elementary fact that an all-zero
    window in an all-distinct cycle must be flanked by one bits.
50. Derived a 64-edge common backbone shared by the valid 71-edge cycle and
    the retained complete disconnected 70-edge support. Added a hardened
    ten-anchor runner for exact overlap shells, with stale-result rejection,
    parameter checks, and independent sequence verification.
51. Proved that every 70-bit cyclic sequence contains at most 61 of the 64
    backbone edges. The finite proof checks all 2,016 two-edge omissions and
    all 168 surviving exact residual flows. A retained non-covering 70-bit
    witness attains overlap 61, so the structural bound is exact.
52. Corrected the first overlap-61 CP-SAT campaign scope: it covered only
    cycles with 70 distinct windows. Added explicit multiplicity and support
    size controls to the exact repair model and portfolio runner.
53. Ran the complete multiplicity-aware overlap-61 anchor partition. Eight
    anchors returned `INFEASIBLE`; anchors 0 and 16 returned `UNKNOWN`.
54. Split the two hard anchors by support size and one-repeat type. Support
    sizes 61 through 65 are computationally infeasible. Nine exact cases
    remain `UNKNOWN`: both anchors at sizes 66 through 68 and three nonloop
    support-69 repeat partitions. No proof trace was emitted.
55. Replaced those unresolved solver cases with a complete finite
    classification of the entire exact-overlap-61 shell, including repeated
    windows and every support size.
56. Checked all 41,664 three-edge omissions. Exactly 188 residual integral
    flows survive; eight produce connected 70-edge circulations, and none
    covers all 512 words within radius 1.
57. Reproduced the classification with a separate C++ implementation and a
    semantic validator that rechecks every residual, histogram, connected
    completion, and retained witness.
58. Combined the classification with the earlier common-backbone theorem to
    prove that every valid 70-bit radius-1 covering sequence has backbone
    overlap at most 60.

## What Was Achieved

This project established a reproducible search and verification baseline, an
independently checked SAT proof for one finite Hamming neighborhood, an exact
common-backbone theorem, and a complete exact classification of its
overlap-61 covering shell. It did not establish a new upper or lower bound on
`L(9,1)`.

| Question | Outcome |
| --- | --- |
| Is the reported 71-bit certificate valid? | Yes, independently in Python and C++. |
| Are any direct one-bit deletions valid at length 70? | No. |
| What is the best direct deletion? | 13 uncovered words. |
| What is the best retained incomplete state? | 6 uncovered words, from a deterministic CPro1 replay. |
| Did either unrestricted SAT portfolio find a model? | No. |
| Did either unrestricted SAT portfolio prove unsatisfiability? | No. |
| What happened in the complete 22-case SAT cover? | All 22 bounded cases returned `UNKNOWN`. |
| What happened in the all-distinct support-70 cover? | Two elementary zero-anchor transition cases have checked UNSAT proofs; 20 cases remain `UNKNOWN`. |
| What do those two UNSAT cases establish? | Only that an occurrence of `0^9` in an all-distinct cyclic window sequence must have a one on each side. |
| Is there a valid sequence within distance 8 of the retained seed? | No, after exhaustive evaluation of 10,783,318,760 states. |
| Is the distance-4 exclusion proof checked independently? | Yes. CaDiCaL emitted binary DRAT, and DRAT-trim verified the retained core. |
| Does the distance-8 result exclude distant constructions? | No. |
| Did the first adaptive-breakout portfolio improve the seed? | No, after 600,000 worker-iterations. |
| Did the retained ejection-chain run improve the seed? | No. A 500-chain run evaluated 110,835,857 actions. Its archived file is the original seed rotated by 9 positions, with raw Hamming distance 44 and cyclic-orbit distance 0. |
| Does the graph model reproduce the known 71-bit result? | Yes, in all three connectivity modes. |
| Did the bounded graph search cover every possible improvement shorter than 70? | No. It covered distinct-window candidates; repeated-window stages remain. |
| Did the bounded at-most-70 graph portfolio find a sequence? | No. |
| Did it prove all lengths through 70 impossible? | No. Nine distinct-support cases timed out, and repeated-support stages remain. |
| Were all scheduled one-duplicate, support-69 anchor runs executed? | Yes. All ten anchors received a bounded run. |
| Was support size 69 proved impossible? | No. Nine anchors returned `UNKNOWN`; one partitioned anchor was infeasible. |
| Did unrestricted exact-support SAT settle support sizes 69 or 70? | No. Both 300-second CaDiCaL runs returned `UNKNOWN`. |
| Was a balanced 69-edge covering support found? | Yes, with component edge counts 1, 4, 4, and 60. |
| Can that support be repaired into a distinct-window cycle by replacing at most 11 edges? | CP-SAT reported `INFEASIBLE` for all ten disjoint anchor models at overlap at least 58. No proof trace was emitted. |
| Does that CP-SAT neighborhood result rule out all 69-bit cycles? | No. More distant supports remain possible. |
| Was a balanced 70-edge covering support found? | Yes, with component edge counts 1, 1, 4, 4, and 60. It is disconnected and is not a sequence certificate. |
| Did exact repair within 17 replacements settle that length-70 neighborhood? | No. Three anchors returned `INFEASIBLE`, seven returned `UNKNOWN`, and no proof trace was emitted. |
| What is the maximum common-backbone overlap of any 70-bit cyclic sequence? | Exactly 61. A finite residual-flow proof gives the upper bound, and a retained 70-bit witness attains it. |
| Does the common-backbone theorem use the covering constraints? | No. It is a de Bruijn graph statement applying to every 70-bit cyclic binary sequence. |
| Does the common-backbone theorem settle the 70-bit covering problem? | No. The exact classification excludes overlap 61 for covers, but candidates with overlap at most 60 remain possible. |
| What did the first exact overlap-61 CP-SAT campaign cover? | Only the all-distinct class with 70 distinct windows. It was a historical discovery campaign without proof traces. |
| What happened when repeated windows were first allowed? | Eight anchors returned `INFEASIBLE`; anchors 0 and 16 returned `UNKNOWN`. Those statuses are now superseded by the complete finite classification. |
| How were the nine former overlap-61 timeouts resolved? | The shell was reformulated as 41,664 omission triples with residual mass 9 and exhaustively enumerated without solver time limits. |
| How many exact residual flows survive? | 188 across 88 omission triples. Only eight are connected, and all eight fail radius-1 coverage. |
| Is the exact-overlap-61 exclusion checked independently? | Yes. Separate Python and C++ implementations agree, and a semantic validator rechecks every retained residual and completion. |
| What covering-specific theorem follows? | Every valid 70-bit radius-1 covering sequence uses at most 60 edges of the retained 64-edge backbone. |
| Are the historical overlap-61 solver exclusions themselves theorems? | No. The theorem comes from the separate finite enumeration, not from untraced solver statuses. |
| Is a new upper or lower bound claimed? | No. |

The unrestricted timeouts are method evidence only. The Hamming-ball result is
an exact finite exclusion, but only for one seed neighborhood. Neither result
can be interpreted as evidence that no 70-bit sequence exists globally.
The two fixed-transition proofs are end-to-end checks of the optimized
proof-producing pipeline for an elementary adjacent-window contradiction, not
a new bound or a resolution of a difficult subcase.

This is enough for a reproducible fixed-backbone theorem, exact-overlap
classification, methods, and benchmark artifact. It is not enough for a new
construction, a new bound on `L(9,1)`, or a global resolution announcement.

## Why It Matters

A 70-bit result would be a compact, immediately checkable improvement to a
current extremal construction. The certificate itself would contain only 70
bits, and anyone could verify all 512 target words directly.

The problem connects:

- covering codes, because the windows must form a Hamming cover;
- de Bruijn graphs, because consecutive windows overlap in eight positions;
- extremal combinatorics, through the shortest possible cyclic representation;
- SAT and constraint programming, through exact finite encodings;
- local search, through a rugged landscape with many nearly covering states.

Covering sequences are relevant whenever a cyclic stream must expose
representatives near every fixed-length word. More broadly, this instance is a
clean benchmark for combining heuristic discovery with independently
checkable certificates.

## What Remains

- Find and independently verify a 70-bit certificate.
- Refresh the prior-art audit immediately before any record claim.
- Obtain independent review of the certificate and both verifiers.
- Resolve the 22 complete-cover SAT cases that remain `UNKNOWN`.
- Resolve the 20 nontrivial all-distinct support-70 SAT cases that remain
  `UNKNOWN`.
- Search structurally different shells with overlap at most 60.
- Develop exact omission-flow classifications or proof-producing partitions
  for selected overlap-at-most-60 shells.
- Search outside the tested 11-replacement neighborhood of the retained
  disconnected 69-edge cover, including diversified support certificates.
- Diversify the retained 70-edge disconnected support and resolve the seven
  overlap-53 repair anchors that remain `UNKNOWN`.
- For a lower bound of 71, settle every length from 62 through 70 and retain
  independently checkable proof evidence for every excluded case.
- Develop stronger lower-bound arguments beyond the covering-code bound `62`.

## Limitations

- This repository has not found a valid 70-bit sequence and has not proved that
  no such sequence exists.
- Local-search failures exclude only the states actually evaluated. They do
  not imply any global lower bound on `L(9,1)`.
- A SAT timeout or `UNKNOWN` result is not evidence of unsatisfiability.
- Completing a disjoint case partition with finite time limits is not the same
  as settling that partition when any case remains `UNKNOWN`.
- The historical multiplicity-aware common-backbone campaign left nine exact
  cases `UNKNOWN`. The later finite enumeration supersedes those timeouts and
  excludes the complete overlap-61 shell without relying on their solver
  statuses.
- Excluding exactly length 70 would not exclude shorter lengths. Covering
  sequence existence is not monotone in length.
- Fixed-seed Hamming-ball searches describe only the neighborhood of that seed.
  They do not exclude distant 70-bit constructions.
- The independently checked DRAT proof covers distance 4 around one seed only.
  It is not a global length-70 impossibility proof.
- The optimized exact-support-70 SAT encoding covers only sequences whose 70
  cyclic windows are all distinct. An unsatisfiable result for that subcase
  would not exclude repeated-window candidates.
- The 22 fixed-transition SAT cases form a complete reflection-reduced cover,
  not a disjoint partition. Bounded `UNKNOWN` cases do not settle that cover.
- The two checked fixed-transition proofs encode an immediate duplicate-window
  contradiction at `0^9`. They validate proof production and checking but do
  not resolve any of the remaining 20 all-distinct cases.
- The connected-support repair computation addresses only distinct-window
  69-edge supports sharing at least 58 edges with one retained disconnected
  cover. It does not address repeated-window sequences or connected supports
  at overlap 57 or below.
- The length-70 support-repair portfolio leaves seven of ten overlap-53 anchor
  cases `UNKNOWN`. It neither excludes that neighborhood nor establishes a
  replacement lower bound across the complete anchor partition.
- The exact encodings have exhaustive small-instance tests, but a global
  impossibility claim would still require a complete proof trace checked by an
  independent proof checker.
- The exact overlap-61 classification has separate Python and C++
  implementations, a semantic artifact validator, direct small-instance
  oracles, and retained source snapshots. It remains specific to one fixed
  backbone and says nothing about overlap at most 60.
- The novelty audit is dated 2026-09-04 and must be repeated before any record
  claim.
- Independent external mathematical review of the fixed-backbone results is
  invited; no external mathematical review is claimed.
- The common-backbone overlap bound is specific to 70-bit cycles. The retained
  positive control has connected 69-bit cycles at overlap 62, so the theorem
  cannot be extrapolated monotonically to other lengths.

As of the dated 2026-09-04 audit, the mathematical interval remains
`62 <= L(9,1) <= 71`.

## Current Result Status

The supported claims are a reproducible verification and exact-search
artifact plus a scoped graph-theoretic theorem: the 71-bit certificate is
independently checked, one finite Hamming neighborhood has a checked proof,
the exact maximum 70-bit common-backbone overlap is 61, no valid 70-bit cover
attains overlap 61, and every valid 70-bit cover therefore has overlap at most
60. No new bound on `L(9,1)` and no global impossibility result are claimed.

A new construction, global bound, or resolution requires one of these
additional gates:

1. A valid 70-bit certificate is independently accepted by both verifiers,
   mutation tests, a refreshed prior-art audit, and external review.
2. A global lower bound is established for every admissible length from 62
   through 70, or by a separate monotonicity theorem, with every proof trace
   independently checked and the argument externally reviewed.

For a genuine result, the record should include a versioned release, durable
archive, dated preprint, exact certificate or proof digest, verification
commands, prior-art comparison, and external review.

## Future Directions

The highest-value next routes are:

1. Search diversified overlap-at-most-60 supports and identify the next shell
   that admits a compact finite classification or proof-producing partition.
2. Resolve the 22 unrestricted and 20 nontrivial all-distinct SAT cases with
   stronger structural partitions rather than only extending time limits.
3. Keep distant archive identity dihedral-canonical while preserving oriented
   beam states, then replace three-bit moves with SAT-completed 12-to-24-bit
   blocks around fragile coverage regions.
4. Continue the exact order-8 de Bruijn graph search with disjoint anchors,
   support-size stages, stationarity marginals, autocorrelation constraints,
   Van Wee inequalities, and generated connectivity cuts.
5. Generate additional balanced disconnected 69-edge covers and run exact
   connected-support repair neighborhoods around each one.
6. Translate the strongest graph formulation to proof-producing incremental
   SAT after the discovery model stabilizes.
7. Partition exact-support SAT by duplicate structure, active-vertex count,
   and weight-layer signatures.
8. If global exact cases become unsatisfiable, emit FRAT or DRAT, convert to
   LRAT, and verify every proof independently.

Detailed phases and acceptance rules are in
[`docs/SEARCH_PLAN.md`](docs/SEARCH_PLAN.md).

## Verification Status

| Item | Status |
| --- | --- |
| 71-bit provenance | Pinned |
| Python verification | Passed |
| C++ verification | Passed |
| Mutation and deletion tests | Passed |
| Incremental-state self-test | Passed |
| Selector and pattern exact-encoding tests | Passed |
| Length-71 SAT and decoder positive control | Passed |
| Fixed-seed SAT cross-check through distance 4 | Passed |
| Distance-4 binary DRAT proof | Independently verified |
| Direct Hamming-ball check through distance 8 | Passed, 10,783,318,760 states |
| Connected de Bruijn model equivalence tests | Passed |
| Length-71 graph-model positive controls | Passed |
| Partitioned distinct at-most-70 portfolio | 9 `UNKNOWN`, 1 scoped `INFEASIBLE` |
| Partitioned exact-length-70 support-69 portfolio | 9 `UNKNOWN`, 1 scoped `INFEASIBLE` |
| Stationarity, Walsh, and autocorrelation encoding tests | Passed |
| Active-vertex and cyclic weight-layer cuts | Passed exhaustive and coefficient checks |
| Exact-support pattern encoding | Passed exhaustive projection checks |
| Canonical fixed-transition SAT cover | 22 retained bounded cases, all `UNKNOWN` |
| Optimized all-distinct support-70 portfolio | 2 elementary proof-checked `UNSATISFIABLE`, 20 `UNKNOWN` |
| Canonical SAT evidence integrity | Sources, summaries, formulas, proofs, and logs authenticated and tested |
| Common-backbone shell runner | Stale-result, parameter, radius, and independent-solution checks passed |
| Common-backbone structural theorem | Exact maximum overlap 61; all 2,016 omission pairs and 168 retained residual flows semantically checked |
| Common-backbone tight witness | 70 bits, 70 distinct windows, overlap 61, independently verified as a non-cover |
| Historical exact-overlap-61 CP-SAT portfolios | Superseded discovery evidence; their untraced statuses are not used as proofs |
| Exact-overlap-61 finite classification | 41,664 omissions, 188 residual flows, 8 connected non-covers, 0 covering completions |
| Independent exact-overlap-61 implementation | Separate C++ enumeration agrees on every aggregate and connected completion |
| Exact-overlap-61 semantic validator | Rechecks every residual, histogram, completion, witness, and source-bound artifact |
| Covering-specific backbone consequence | Every valid 70-bit cover has overlap at most 60 |
| Exact-support 69 and 70 CaDiCaL runs | Both `UNKNOWN` after 300 seconds |
| Retained ejection-chain run | 500 chains, no raw improvement; archived file is a rotation of the seed |
| Exact unique-duplicate and support-repair tests | Passed |
| Balanced disconnected 69-edge cover | Verified, components 1, 4, 4, 60 |
| Connected distinct-window 69-edge repair through 11 replacements | CP-SAT `INFEASIBLE` across all 10 anchors; no proof trace |
| Balanced disconnected 70-edge cover | Verified, components 1, 1, 4, 4, 60 |
| Connected distinct-window 70-edge repair through 17 replacements | 3 `INFEASIBLE`, 7 `UNKNOWN`; no proof trace |
| Best retained incomplete 70-bit state | 6 uncovered words |
| 70-bit certificate | Not found |
| New upper or lower bound | None |
| Current claim | Complete fixed-backbone overlap-61 exclusion and reproducible benchmark artifact; no new bound on `L(9,1)` |

The retained strengthening evidence is recorded in
[`evidence/graph-strengthening-20260902.log`](evidence/graph-strengthening-20260902.log).
The connected-support repair evidence is recorded in
[`evidence/graph-repair-20260902.log`](evidence/graph-repair-20260902.log).
Its exact production sources are retained and hash-checked under
`evidence/graph-repair/source/`; later interface hardening does not alter the
retained solver artifacts.
The length-70 support portfolio and its exact scope are recorded in
[`evidence/graph-repair70/README.md`](evidence/graph-repair70/README.md).
The complete SAT cover, exact-support cover, and checked transition proofs are
recorded in
[`evidence/sat-anchor-cover-20260902/README.md`](evidence/sat-anchor-cover-20260902/README.md).
The exact common-backbone theorem and retained finite analysis are documented
in [`docs/COMMON_BACKBONE_LEMMA.md`](docs/COMMON_BACKBONE_LEMMA.md) and
[`evidence/common-backbone-lemma-20260905/README.md`](evidence/common-backbone-lemma-20260905/README.md).
The complete exact-overlap-61 classification is documented in
[`docs/EXACT_OVERLAP_61.md`](docs/EXACT_OVERLAP_61.md) and authenticated under
[`evidence/exact-backbone-overlap61-20260905/README.md`](evidence/exact-backbone-overlap61-20260905/README.md).
The separate no-proof CP-SAT campaign for the all-distinct overlap-61
covering subcase is retained under
[`evidence/common-backbone-cover61-20260902/README.md`](evidence/common-backbone-cover61-20260902/README.md).
The multiplicity-aware campaign and exact support reductions are retained
under
[`evidence/common-backbone-cover61-repeated-20260902/README.md`](evidence/common-backbone-cover61-repeated-20260902/README.md),
[`evidence/common-backbone-cover61-support-stages-20260902/README.md`](evidence/common-backbone-cover61-support-stages-20260902/README.md),
and
[`evidence/common-backbone-cover61-support69-partitions-20260902/README.md`](evidence/common-backbone-cover61-support69-partitions-20260902/README.md).

## Licensing

Original code, documentation, generated logs, proofs, and project evidence are
MIT licensed. The retained CPro1 baseline and incomplete search seed are
covered by Apache-2.0. See `NOTICE` and `LICENSES/Apache-2.0.txt` for the exact
boundary.

Retained solver logs are normalized only to remove trailing formatting and
replace the local runner hostname and absolute solver path with stable labels.
Solver results, statistics, and proof content are unchanged.

## Commands

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-solver.txt
make build
make test PYTHON=.venv/bin/python
make solver-test PYTHON=.venv/bin/python
make verify-baseline PYTHON=.venv/bin/python
make analyze-baseline PYTHON=.venv/bin/python
make analyze-backbone PYTHON=.venv/bin/python
make analyze-exact-overlap PYTHON=.venv/bin/python
make verify-publication PYTHON=.venv/bin/python
make paper-bundle PYTHON=.venv/bin/python
make paper-replay PYTHON=.venv/bin/python CXX=c++
make search-smoke
make breakout-smoke
make ejection-smoke
make cnf
make pattern-cnf
make pattern-neighborhood-cnf
make exact-support-cnf
make backbone-overlap-cnf
```

Run the complete reflection-reduced length-70 SAT cover with:

```bash
python3 tools/run_cadical_portfolio.py \
  search-results/cadical-complete-cover \
  --solver /path/to/cadical \
  --n 9 \
  --radius 1 \
  --length 70 \
  --time-limit 300 \
  --workers 14
```

Add `--exact-support 70` to search only the all-distinct support-70 subcase.
That subcase is constructive and useful, but it is not a complete
length-70 impossibility test.

Run the ten disjoint exact common-backbone anchor cases with:

```bash
python3 tools/run_backbone_portfolio.py \
  data/candidates/l9-r1-common-backbone-64.json \
  search-results/common-backbone61 \
  --n 9 \
  --radius 1 \
  --length 70 \
  --exact-overlap 61 \
  --connectivity tree \
  --time-limit 600 \
  --parallel-cases 10 \
  --solver-workers 1
```

Regenerate the distance-4 CNF and independently check the retained proof with
an installed DRAT-trim binary:

```bash
make distance4-proof-check DRAT_TRIM=/path/to/drat-trim
```

Run a longer parallel search with:

```bash
mkdir -p search-results
./build/cover-search \
  --length 70 \
  --baseline data/baseline/l9-r1-71.txt \
  --workers 14 \
  --iterations 500000 \
  --seed 1 \
  --output search-results/l9-r1-70.txt
```

Enable adaptive breakout weighting with:

```bash
./build/cover-search \
  --length 70 \
  --baseline data/candidates/l9-r1-70-uncovered-6.txt \
  --workers 14 \
  --iterations 50000 \
  --seed 1 \
  --breakout \
  --breakout-stagnation 250 \
  --breakout-increment 5 \
  --output search-results/l9-r1-70-breakout.txt
```

Run beam ejection-chain search with:

```bash
./build/cover-search \
  --length 70 \
  --baseline data/candidates/l9-r1-70-uncovered-6.txt \
  --workers 8 \
  --iterations 100 \
  --seed 1 \
  --ejection \
  --ejection-beam-width 256 \
  --ejection-depth 16 \
  --ejection-damage 20 \
  --ejection-endpoint-damage 6 \
  --output search-results/l9-r1-70-ejection.txt
```

Any candidate must pass the independent Python verifier:

```bash
python3 tools/verify.py search-results/l9-r1-70.txt \
  --n 9 \
  --radius 1 \
  --expected-length 70
```

Decode a satisfiable DIMACS solver model with:

```bash
python3 tools/decode_model.py solver.log data/candidates/l9-r1-70.txt \
  --n 9 \
  --radius 1 \
  --length 70
```

Independently enumerate a Hamming neighborhood around the retained seed with:

```bash
./build/cover-neighborhood \
  --seed data/candidates/l9-r1-70-uncovered-6.txt \
  --n 9 \
  --radius 1 \
  --max-distance 8 \
  --workers 14
```

Run one partitioned graph-model anchor case over every distinct-window length
up to 70 with:

```bash
python3 tools/flow_cp_sat.py \
  --n 9 \
  --radius 1 \
  --length 70 \
  --at-most-length \
  --minimum-support 62 \
  --anchor-edge 64 \
  --distinct-windows \
  --partition-anchor \
  --connectivity cuts \
  --hint-sequence data/candidates/l9-r1-70-uncovered-6.txt \
  --time-limit 300 \
  --workers 1
```

All ten anchors in `B_1(0^9)` and every repeated-window support-size stage
must be terminally settled. Executing a bounded run that returns `UNKNOWN`
does not complete the search.

Run one exact one-duplicate anchor case with the default stationarity and
autocorrelation strengthening:

```bash
python3 tools/flow_cp_sat.py \
  --n 9 \
  --radius 1 \
  --length 70 \
  --support-size 69 \
  --minimum-support 62 \
  --anchor-edge 64 \
  --partition-anchor \
  --connectivity cuts \
  --hint-sequence data/candidates/l9-r1-70-uncovered-6.txt \
  --time-limit 300 \
  --workers 1
```

Walsh aggregates are disabled by default. Use `--walsh` only for controlled
comparisons.

Reproduce one exact connected-support repair case with:

```bash
mkdir -p search-results
python3 tools/repair_support.py \
  evidence/graph-repair/disconnected-support-anchor-0.json \
  search-results/overlap58-anchor-16.json \
  --n 9 \
  --radius 1 \
  --length 69 \
  --anchor-edge 16 \
  --partition-anchor \
  --connectivity tree \
  --minimum-overlap 58 \
  --time-limit 300 \
  --workers 2 \
  --seed 1
```

Every anchor in `B_1(0^9)` must report `INFEASIBLE` before the CP-SAT
portfolio covers the full overlap neighborhood. A feasible result must be
decoded and verified; `UNKNOWN` leaves that anchor unresolved. An
independently checked proof trace would still be required for a formal
infeasibility claim.

## Result Policy

A construction is not treated as a new mathematical result until all of the
following are complete:

1. The Python verifier accepts the certificate.
2. The C++ verifier independently accepts the certificate.
3. Mutation tests reject altered certificates.
4. A fresh literature and repository search finds no earlier 70-bit result.
5. The certificate and verification steps are reviewed independently.

An impossibility claim additionally requires complete coverage of all lengths
from 62 through 70, proof traces or mathematical proofs for every case, and
independent checking of those proofs.

A scoped theorem is treated separately from either global route. Its statement
must identify the fixed object and exact parameter range, the proof and finite
checks must be reproducible from retained sources, tightness claims must have
an independently verified witness, and all remaining global cases must be
stated explicitly. The common-backbone theorem meets these standards;
independent external mathematical review is invited and remains pending.

`release.json` records publication status, reproducibility, claim scope, and
the remaining review status.

## References

- [F. Chung and J. Cooper, arXiv:math/0310385](https://arxiv.org/abs/math/0310385).
- [Y. M. Chee, T. Etzion, H. Ta, and V. K. Vu, arXiv:2502.08424](https://arxiv.org/abs/2502.08424).
- [C. D. Rosin, arXiv:2505.23881](https://arxiv.org/abs/2505.23881).
- [D. Gijswijt and S. Polak, arXiv:2504.01932](https://arxiv.org/abs/2504.01932).
- [Constructive-Codes/CPro1](https://github.com/Constructive-Codes/CPro1),
  pinned in `NOTICE`.
