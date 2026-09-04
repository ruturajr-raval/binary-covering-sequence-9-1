# Research Log

## 2026-09-01

- Selected the `(9,1)` cyclic binary covering-sequence problem after
  comparing current candidates in extremal combinatorics, coding theory,
  Ramsey theory, and validated dynamics.
- Confirmed the reported interval `62 <= L(9,1) <= 71`.
- Retrieved the 71-bit certificate from the pinned CPro1 release.
- Independently verified all 512 target words in Python and C++.
- Recorded the normalized certificate SHA-256 digest
  `40c757662f703fc481883fddb8d359f8e0fe685207ac4cba1685a205a2208608`.
- Checked every one-position deletion of the certificate.
- Best 70-bit descendants leave 13 of the 512 words uncovered.
- Built an incremental C++ local search with full-state cross-checks.
- Improved the best incomplete 70-bit sequence from 13 to 9 uncovered
  words. Broader runs remained at 9, so this is evidence of a search
  plateau, not a mathematical result.
- Deterministically replayed the Apache-licensed CPro1 search at seed 4000
  and iteration 1530000, recovering a 70-bit state with six uncovered words.
- Independently checked that state in Python and C++. It covers 506 words,
  has 70 distinct windows, and is retained only as a search seed.
- Generated a direct length-70 SAT instance with 35,910 variables and
  1,290,754 clauses.
- Ran a 14-seed Kissat 4.0.4 portfolio with a 300 wall-second limit per
  seed. All 14 runs returned `UNKNOWN`.
- Recorded Kissat source commit
  `8af8e56f174b778aef3aa45af9f739b2a5f492c2` and CNF SHA-256 digest
  `2ac305140a1c8bce497fe8d1e82b04a2f373d3e714af1917f4261b3bb1981ed6`.
- The SAT portfolio produced neither a construction nor an impossibility
  proof.

## 2026-09-02

- Added a pattern-variable exact encoding with 36,422 variables and 359,461
  clauses, reducing the clause count by more than a factor of three.
- Verified the pattern encoder end to end by fixing the known 71-bit baseline,
  solving the formula as satisfiable, decoding the model, and recovering the
  exact certificate in both independent verifiers.
- Ran eight unrestricted 300-second Kissat seeds on the length-70 pattern
  formula. All returned `UNKNOWN`.
- Added a symmetry-free fixed-seed Hamming counter. Global rotation and
  reflection constraints are deliberately disabled because they do not
  preserve distance from a fixed seed.
- Generated independent fixed-seed formulas through distance 4. Kissat
  reported each formula unsatisfiable.
- Built a separate parallel enumerator that visits each sorted flip set once
  and recomputes coverage directly from the definition.
- Cross-checked the direct enumerator against an independent Python
  implementation through distance 3 and against the SAT formulas through
  distance 4.
- Exhaustively evaluated all 10,783,318,760 sequences within Hamming distance
  8 of the retained six-gap seed.
- No valid sequence was found, and no state improved the seed's six uncovered
  words. The result applies only to this Hamming ball and changes no global
  bound.
- Added adaptive breakout weighting as the next route for escaping this deep
  local basin. Weighted scoring remains separate from final raw validity.
- Ran three independently seeded breakout schedules across 14 workers for
  600,000 total worker-iterations.
- The first breakout portfolio found no valid sequence and no raw improvement
  below six uncovered words. This is negative heuristic evidence only.
- Built an exact de Bruijn edge-multiplicity model. Length, balance, coverage,
  support, and connectivity are expressed independently of bit positions.
- Implemented single-commodity flow, rooted-arborescence, and iterative-cut
  connectivity formulations.
- Exhaustively matched feasibility of all three formulations against direct
  sequence enumeration on small instances and tested disconnected loops,
  repeated edges, and full order-9 Euler extraction.
- Recovered valid 71-bit certificates through each graph formulation and
  rechecked every decoded candidate with the independent verifier.
- Ran diagnostic flow, tree, and iterative-cut searches while developing the
  model. These used intermediate source snapshots and are not part of the
  final evidence set.
- Added disjoint anchor cases, exact support-size stages, at-most-length
  constructive search, and the radius-1 Van Wee inequalities.
- Added the established minimum-support bound, Hamming-weight layer
  inequalities, and a repeat-defect constraint that limits support imbalance
  by the available duplicate-edge budget.
- Corrected the impossibility target: because existence is not monotone in
  length, excluding exactly 70 would not establish a lower bound of 71.
  Every length from 62 through 70 must be covered by a complete lower-bound
  argument.
- Reran all ten disjoint distinct-support anchor cases with source SHA-256
  `21490b3a8cf0d43d0579a3f879c7482f415edc7fd779a1a227361ed4b2e06f54`,
  sequence length at most 70, and all then-implemented strengthening enabled.
- Nine cases returned `UNKNOWN` after 300 solver seconds. The final anchor
  case was infeasible because its selected edge enters vertex zero while both
  outgoing edges are excluded by the anchor partition.
- Reran the support-size-69 exact-length-70 stage near the six-gap seed with
  the final source. It returned `UNKNOWN` without a feasible incumbent.
- Retained each final-source JSON output and every decoded positive-control
  sequence under `evidence/graph-cp-sat`.
- The graph-model portfolios found no certificate and produced no global
  impossibility proof.
- Derived stationarity inequalities from equality of cyclic window
  multiplicity marginals. For each substring pattern, its maximum support
  count over window offsets is bounded by its common multiplicity marginal.
- Added exact maximum constraints for substring widths through `n-2`.
  Width `n-1` is omitted when the equivalent repeat-defect inequality is
  already active.
- Derived Walsh-transform aggregate inequalities from the nonnegative excess
  in the radius-1 covering rows. They remain opt-in pending retained evidence
  that the dense rows improve search.
- Added shift-autocorrelation parity constraints, radius-1 half-cube covering
  inequalities, and odd shift-orbit upper bounds for exact lengths.
- Added exhaustive small-cycle identity checks and coefficient-level
  model-proto tests. The graph-model test count increased from 15 to 28.
- Performed separate mathematical and code reviews before retaining production
  evidence.
- Ran a final-source, one-worker, 300-second portfolio for all ten disjoint
  anchors at exact length 70 and support size 69.
- Nine support-69 anchors returned `UNKNOWN`. The final partitioned anchor was
  infeasible by the existing balance contradiction. No valid sequence or
  global impossibility proof was produced.
- Exposed the unique duplicated edge in the exact length-70, support-69 stage
  and added exact support imbalance, loop-defect, stationarity, and local
  endpoint degree constraints.
- Replaced the weakened multiplicity autocorrelation cover rows with exact
  support aggregates. Added optional pair-projection rows, but retained
  `none` as the default after controlled runs did not show a decisive benefit.
- Added deterministic-work limits and detailed propagation counters so future
  formulation comparisons need not rely on fixed wall time alone.
- Found a balanced 69-edge radius-1 covering support with four directed
  components containing 1, 4, 4, and 60 edges.
- Checked its immediate balance-preserving cross-joins. Each available
  component merge leaves four target words uncovered.
- Added `tools/repair_support.py` to search exact connected support
  neighborhoods with disjoint anchors and independently decoded outputs.
- Every exact distinct-window length-69 anchor model returned infeasible at
  overlap at least 58 with the retained support. Within the tested
  formulation, these solver statuses imply that a connected distinct-window
  69-edge covering cycle must replace at least 12 of its edges.
- CP-SAT emitted no independently checkable proof trace, so the retained
  neighborhood result is computational evidence rather than a formal
  infeasibility proof.
- The repair result is local to one support certificate. It does not settle
  length 69 and does not change `62 <= L(9,1) <= 71`.
- Added reverse pattern channeling and an exact unary support-cardinality
  encoding. Exhaustive projections verify that the counted presence variables
  are exactly the distinct cyclic windows, including combined fixed-seed
  Hamming constraints.
- Generated unrestricted exact-support formulas for support sizes 69 and 70.
  CaDiCaL 3.0.1 ran each case for 300 seconds; both returned `UNKNOWN`, with no
  model and no proof.
- Generated a binary DRAT proof for the distance-4 fixed-seed formula, trimmed
  it to a 22,414,378-byte core, and independently checked that core with
  DRAT-trim. The compressed retained proof is 7,925,261 bytes.
- The checked proof establishes only that no valid length-70 sequence is
  within Hamming distance 4 of the retained six-gap seed. It does not improve
  the global bound.
- Added a beam ejection-chain search that allows bounded temporary coverage
  damage and archives distant intermediate states.
- Hardened ejection search after independent review: radius-0 use is rejected,
  damage arithmetic is overflow-safe, target selection skips damage-inadmissible
  gaps, radius-1 repair actions are complete for each examined window, state
  deduplication spans the full chain, and intermediate endpoints remain
  eligible.
- Ran the corrected one-worker ejection search for 500 chains. It evaluated
  110,835,857 candidate actions, accepted 278 endpoints, and reached origin
  distance 49.
- The run found no valid sequence and no raw improvement below six gaps. It
  archived the original seed rotated by 9 positions. The raw aligned Hamming
  distance is 44, but the cyclic-orbit distance is zero. Both files were
  checked in Python and C++, and this exposed the need for orbit-canonical
  ejection state identity.
- Corrected disconnected support sampling by disabling a connected-cycle-only
  odd-orbit autocorrelation bound. Added optional active-vertex caps and an
  active-vertex minimization objective.
- Added the valid radius-1 active-vertex inequality
  `4V + (n-3)S >= 2^n` and connected cyclic weight-layer path cuts to the graph
  model. The path cuts are deliberately omitted for disconnected sampling.
- Expanded the repository suite with exhaustive
  small-cycle, coefficient-level, proof-artifact, support-cardinality, and
  combined support-distance checks.
- Found and independently checked a balanced 70-edge radius-1 covering
  support with five directed components containing 1, 1, 4, 4, and 60 edges.
- Its two immediate cross-joins each merge the 4-edge and 60-edge components
  but leave four target words uncovered.
- Ran all ten disjoint exact connected-support repair anchors at overlap at
  least 53, permitting at most 17 replacements. Anchors 0, 128, and 256
  returned `INFEASIBLE`; the other seven returned `UNKNOWN`.
- The length-70 repair campaign found no sequence and did not exclude the
  complete overlap neighborhood. CP-SAT emitted no proof trace, so no new
  mathematical bound follows.
- Added exact fixed zero-ball anchor words and predecessor/successor transition
  bits to the pattern CNF. Exhaustive small-instance tests match the
  independent verifier.
- Reduced the complete bit-level portfolio from 40 raw transition cases to 22
  reflection representatives and added complement symmetry through the tested
  Hamming counter.
- Replaced the support-70 presence-cardinality counter with lag-XOR
  pairwise-window distinctness and exact support-balance clauses. A production
  anchored case with complement symmetry has 41,357 variables and 414,868
  clauses.
- Added a parallel CaDiCaL runner that writes atomic summaries and
  independently decodes and verifies every satisfiable model.
- Ran the complete 22-case length-70 bit-level portfolio for 300 seconds per
  case. Every case returned `UNKNOWN`; no model or impossibility proof was
  produced.
- Ran the 22-case exact-support-70 portfolio. Two cases returned
  `UNSATISFIABLE`, and 20 returned `UNKNOWN`.
- Regenerated the two solved formulas byte for byte, retained their binary
  DRAT traces, and independently checked both traces with DRAT-trim.
- The two solved cases are elementary: fixing `W_0 = 0^9` and a zero
  successor forces `W_1 = W_0`, contradicting 70 distinct windows. Reflection
  gives the corresponding predecessor condition. The proofs validate the
  pipeline but do not settle a nontrivial support-70 case.
- Retained all summaries, logs, result files, exact sources, formulas, proofs,
  checker logs, binary hashes, and a complete file manifest under
  `evidence/sat-anchor-cover-20260902`.
- Rechecked the 40 raw anchor transitions directly: reflection has exactly 22
  orbits, and the runner retains exactly one representative from each orbit.
- Replaced ejection beam deduplication by exact oriented-state identity while
  keeping distant archive identity dihedral-canonical. This avoids suppressing
  useful orientations under root-relative heuristics.
- Derived the exact 64-edge intersection of the valid 71-edge cycle support
  and the retained complete disconnected 70-edge support.
- Generalized support repair to exact overlap with a partial reference
  backbone and added a ten-anchor shell runner.
- Independent review exposed stale-result reuse, radius overclaiming, and
  misleading replacement language in the first runner version. The runner now
  deletes prior case outputs, validates return codes and parameters, rejects
  unsupported radii, independently checks feasible sequences, and reports
  reference omissions separately from replacements.
- Proved that the 64-edge common backbone has two directed-cycle components
  with 4 and 60 edges and that every closed walk joining the components has
  length at least 7.
- Enumerated all 504 appended-bit walks through length 6 and recovered the two
  complementary length-7 connectors. Adding either connector to the backbone
  gives a valid 71-edge covering support.
- For each of the 64 possible single omitted backbone edges, proved that a
  compensating directed detour through the other component needs at least 10
  edges. This excludes backbone overlap 63 at total multiplicity 70.
- Extended the argument to every pair of omitted edges. Any eight-edge
  residual decomposes into one or two source-to-sink walks plus balanced
  closed-walk flow.
- Checked all 2,016 omission pairs. Only 44 distinct path flows and 168 exact
  residual flows survive the mass, endpoint, and omitted-edge conditions.
  None connects the retained 62-edge support.
- Concluded that every 70-bit cyclic binary sequence uses at most 61 of the
  64 backbone edges. This theorem is independent of the radius-1 covering
  constraints.
- Retained and independently checked a 70-bit non-covering witness with 70
  distinct windows and backbone overlap 61, proving that the structural bound
  is exact.
- Verified the exact-length boundary by finding two connected mass-7
  residuals at overlap 62. These give 69-bit circulations and show that the
  70-bit theorem is not monotone in sequence length.
- The all-distinct exact-overlap-61 covering CP-SAT portfolio reported all
  ten disjoint anchor cases infeasible, but no proof trace was emitted.
  Repeated-window candidates were not modeled. It remains computational
  evidence and does not strengthen the theorem or change
  `62 <= L(9,1) <= 71`.
- Added explicit repeated-window, support-size, duplicate-edge, duplicate-kind,
  and duplicate-scope controls to the support repair model and portfolio
  runner.
- Ran the complete multiplicity-aware exact-overlap-61 anchor partition.
  Eight anchors returned `INFEASIBLE`; anchors 0 and 16 returned `UNKNOWN`.
- Split the two hard anchors by exact support size. Sizes 61 through 65
  returned `INFEASIBLE` for both anchors. Sizes 66 through 68 returned
  `UNKNOWN`.
- Ran the complete support-size-69 portfolio. Eight anchors returned
  `INFEASIBLE`; anchors 0 and 16 returned `UNKNOWN`.
- Split those two one-repeat cases by whether the repeated edge lies inside or
  outside the backbone and whether it is a loop. All loop cases were
  infeasible, as was the complete anchor-0 reference-repeat case.
- The exact computational residue is nine cases: anchors 0 and 16 at support
  sizes 66, 67, and 68, plus three nonloop support-69 cases. No proof trace
  was emitted, so none of the solver infeasibility statuses is promoted to a
  theorem.

## 2026-09-04

- Replaced the nine unresolved exact-overlap-61 solver leaves with a direct
  finite flow classification of the entire shell.
- Enumerated all `C(64,3) = 41,664` triples of omitted backbone edges. The
  retained 61-edge part leaves residual mass 9 with uniquely determined
  divergence.
- Found 188 distinct admissible residual flows across 88 omission triples.
  Their support-component histogram is 8 connected, 72 with two components,
  80 with three components, and 28 with four components.
- Reconstructed the eight connected Eulerian circulations. All have 70
  distinct windows. Six leave nine words uncovered and two leave ten, so none
  is a radius-1 cover.
- Implemented a separate C++ enumeration. It agrees with the Python analyzer
  on every aggregate count and every connected completion.
- Added a semantic artifact validator that independently rechecks all 188
  residuals, derives every histogram and connected completion, verifies the
  retained witness, and rejects incomplete or altered attestations.
- Added direct small-instance oracles, including a residual-mass-9,
  three-omission case with three divergence terminals.
- Retained exact source snapshots, both output artifacts, and a complete
  SHA-256 manifest under
  `evidence/exact-backbone-overlap61-20260904/`.
- Combined this exclusion with the earlier maximum-overlap theorem. Every
  valid 70-bit radius-1 covering sequence now has overlap at most 60 with the
  retained 64-edge backbone.
- This closes one fixed-backbone shell. It does not produce a 70-bit
  construction, exclude overlap at most 60, or change
  `62 <= L(9,1) <= 71`.
