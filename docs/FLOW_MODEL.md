# Connected De Bruijn Flow Model

## Purpose

The bit-level SAT encodings describe every sequence position directly. The flow
model instead describes the multiset of cyclic windows and enforces that those
windows can be ordered as one closed de Bruijn walk.

For parameters `(n,R,L)`, each binary `n`-word is a directed edge in the
order-`n-1` binary de Bruijn graph:

```text
prefix(w) -> suffix(w).
```

The prefix drops the final bit. The suffix drops the first bit.

## Variables

For every `n`-word `w`:

- `use[w]` is true exactly when the edge is present;
- `count[w]` is its nonnegative multiplicity;
- `flow[w]` is auxiliary connectivity flow.

For every `(n-1)`-word `v`, `vertex[v]` records whether any selected edge is
incident to that vertex.

## Core Constraints

The multiplicity and support variables are channeled by

```text
use[w] <= count[w] <= L * use[w].
```

The walk has exactly `L` edges:

```text
sum_w count[w] = L.
```

For constructive search, the optional at-most mode replaces equality by

```text
n <= sum_w count[w] <= L.
```

This searches all admissible shorter lengths in one model. It is necessary
because covering-sequence existence is not monotone in length.

Every vertex is balanced:

```text
sum_{w entering v} count[w]
    = sum_{w leaving v} count[w].
```

Every target word is covered:

```text
sum_{d_H(w,target) <= R} use[w] >= 1.
```

For radius 1, the model also adds the Van Wee inequalities. When `n=9`, each
target `t` satisfies

```text
5 * use[t]
  + sum_{d_H(w,t)=1} use[w]
  + sum_{d_H(w,t)=2} use[w] >= 5.
```

This follows by summing the ten radius-1 covering inequalities centered at
the words in `B_1(t)`. A selected copy of `t` contributes ten, and a selected
word at distance 1 or 2 contributes two. Dividing by two gives the stated
valid inequality.

## Support-Size Stages

For exact length 70, the known covering-code lower bound implies at least 62
distinct windows. The unrestricted model can therefore be divided into nine
support stages:

```text
sum_w use[w] = 70 - d,    d in {0,1,...,8}.
```

Only `d` duplicate copies remain. Consequently every multiplicity is at most
`d+1`, replacing the weak generic upper bound of 70. Stage `d=0` is the
distinct-window model.

Let the support imbalance at a vertex be

```text
delta(v) = support_outdegree(v) - support_indegree(v).
```

The duplicate copies must repair every support imbalance. One duplicate edge
contributes one outgoing and one incoming unit, so

```text
sum_v |delta(v)| <= 2d.
```

The model enforces this repeat-defect inequality for repeated-window stages.

At exact length 70 and support size 69, there is exactly one extra copy. The
model exposes Boolean variables

```text
extra[w] = count[w] - use[w],
sum_w extra[w] = 1.
```

If `q` is the unique edge with `extra[q]=1`, multiplicity balance gives the
exact support identity

```text
support_out(v) - support_in(v)
  = extra_in(v) - extra_out(v).
```

For a nonloop duplicate `q:p->s`, the support has imbalance `-1` at `p`,
`+1` at `s`, and zero elsewhere. Its local degrees are forced:

```text
out_support(p)=1, in_support(p)=2,
in_support(s)=1, out_support(s)=2.
```

For a loop duplicate, the support is balanced. The exact total defect is

```text
sum_v |delta(v)| = 2 * (1 - loop_extra).
```

The duplicate can be left free, restricted to loop or nonloop edges, or fixed
to one edge for a disjoint fine-grained search.

For each Hamming-weight layer `j`, aggregating all covering constraints in
that layer also gives

```text
c_j + (10-j)c_(j-1) + (j+1)c_(j+1) >= binom(9,j),
```

where `c_j` counts selected support words of weight `j`.

Each used edge activates both endpoints, and each active vertex must have an
incident used edge. Thus `vertex[v]` is the exact OR of the incident support
variables.

Let `S` be the support size, `V` the number of active order-`n-1` vertices,
and `P_1` the number of support pairs at Hamming distance one. Counting
coverage incidences on selected target words gives

```text
2P_1 <= (n+1)S - 2^n.
```

Every support vertex has indegree and outdegree one or two. Exactly `S-V`
vertices have support outdegree two, and the same number have support
indegree two. Their outgoing and incoming edge pairs are distinct
distance-one pairs, so

```text
2(S-V) <= P_1.
```

Combining the inequalities yields the active-vertex cut

```text
4V + (n-3)S >= 2^n.
```

For `(n,R)=(9,1)`, this reduces to

```text
2V + 3S >= 256.
```

This cut remains valid for disconnected balanced supports and is therefore
enabled in the support sampler.

When one connected cyclic sequence is required, consecutive window weights
differ by at most one. Radius-1 coverage forces the closed weight walk to
reach a level at most one and a level at least `n-1`. If `C_j` is the support
count and `M_j` is the multiplicity count in weight layer `j`, the model adds

```text
C_j >= 1                 for 1 <= j <= n-1,
M_j >= 2                 for 2 <= j <= n-2,
M_1 >= 1 + use[0^n],
M_(n-1) >= 1 + use[1^n].
```

The multiplicity rows account correctly for repeated windows. These cyclic
path cuts are omitted from deliberately disconnected support sampling because
a union of components need not have one weight walk spanning both extremes.

## Stationarity Marginals

The multiplicity vector of a cyclic sequence is stationary under movement
inside a window. Fix a width `k`, a binary pattern `a`, and a starting offset
`j`. Define

```text
A_(j,a) = sum use[w]
```

over all selected words whose width-`k` substring at offset `j` is `a`.
Define the analogous multiplicity marginal

```text
C_(j,a) = sum count[w].
```

Balance of the de Bruijn flow implies that `C_(j,a)` is independent of `j`;
write its common value as `C_a`. Since `use[w] <= count[w]`,

```text
max_j A_(j,a) <= C_a.
```

Summing over every width-`k` pattern gives the valid inequality

```text
sum_a max_j A_(j,a) <= sum_a C_a = L.
```

In at-most mode, the right side is the modeled total multiplicity rather than
the upper length bound.

In the exact one-duplicate stage, the maxima satisfy the sharper equality

```text
sum_a max_j A_(j,a) = L - loop_extra.
```

The implementation adds exact maximum variables for widths `1` through
`n-2` in repeated-window stages. Width `n-1` is equivalent to the
repeat-defect inequality:

```text
sum_v max(support_outdegree(v), support_indegree(v))
  = support_size + (1/2) * sum_v |delta(v)|.
```

It is therefore omitted when repeat-defect strengthening is active. All
stationarity inequalities are redundant in the distinct-window model, where
support and multiplicity coincide.

## Walsh Aggregates

For radius 1, let `u` be the support indicator and let `A` be the adjacency
operator that sums `u` over a closed Hamming radius-1 ball. Coverage says

```text
A u >= 1.
```

Write the nonnegative excess as `e = A u - 1`. Its total mass is

```text
E = (n+1) * support_size - 2^n.
```

For a nonempty coordinate mask of order `k`, the corresponding Walsh
character is an eigenvector of `A` with eigenvalue `n+1-2k`. Nonnegativity of
`e` gives

```text
|(n+1-2k) * sum_w character(w) * use[w]| <= E.
```

The model can add both linear signs of this inequality. Masks with zero
eigenvalue add no constraint.

These inequalities are aggregates of the existing covering constraints, not
new mathematical information. They remain optional pending retained evidence
that the dense rows improve search enough to justify enabling them by default.

## Autocorrelation Constraints

For a cyclic sequence `x` and shift `d`, define

```text
D_d = |{i : x_i != x_(i+d)}|.
```

The edge-multiplicity model computes this value directly:

```text
D_d = sum count[w]
```

over words whose first bit differs from their bit at offset `d`.

Every shift orbit has an even number of bit transitions, so

```text
D_d = 2 q_d
```

for an integer variable `q_d`.

There are also radius-1 covering consequences. Let `S` be the support size and
let `H_d` count support words whose selected coordinates differ.
Among the `n+1` words in the radius-1 ball around a support word, `n-1` have
the same agree-or-differ relation at the two selected coordinates and two
have the opposite relation. Summing coverage over either half of the cube
gives, for `n >= 4`,

```text
(n-3) * H_d + 2S >= 2^(n-1)
(n-3) * (S-H_d) + 2S >= 2^(n-1).
```

These support rows strictly dominate the earlier multiplicity relaxation in
repeated-window stages.

For any coordinate pair, the model can additionally aggregate coverage over
each of the four projection cells. If `U_ab` is the support count in cell
`ab`, then

```text
(n-1)U_ab + U_(a xor 1,b) + U_(a,b xor 1) >= 2^(n-2).
```

The optional `first` scope adds all pairs involving coordinate zero. The
optional `all` scope adds all coordinate pairs. Controlled runs did not
justify enabling these denser rows by default.

For exact length `L`, the shift permutation has `gcd(L,d)` orbits, each of
length `L/gcd(L,d)`. If that orbit length is odd, each orbit must contain at
least one agreement, so

```text
D_d <= L - gcd(L,d).
```

This bound uses the fact that the final edge multiset decodes to one connected
cyclic sequence. It need not hold for an arbitrary disconnected union of
balanced walks, but it remains a valid necessary constraint in every
connectivity formulation.

The orbit upper bound is not added in at-most mode because the actual length
is then a decision variable.

## Anchor Cases

Every valid covering sequence covers the all-zero target. It therefore uses at
least one edge in the Hamming ball

```text
B_R(0^n).
```

The exact search enumerates one case for every possible anchor edge `a` in that
ball and requires `use[a] = 1`. The connectivity root is `prefix(a)`, which is
an endpoint of a selected edge.

The anchor cases can be partitioned. For anchors `a_0,...,a_9` in fixed order,
case `i` requires `use[a_i]=1` and `use[a_j]=0` for every `j<i`. Every cover
belongs to exactly one case. An anchor is a root choice, not an extra rotation
constraint.

## Connectivity

Three exact connectivity modes are implemented.

### Single-Commodity Flow

Let `r` be the fixed root and let `V'` be the active vertices other than `r`.
Auxiliary flow is bounded by selected support:

```text
0 <= flow[w] <= (|V| - 1) * use[w].
```

Every non-root active vertex consumes one unit:

```text
in_flow(v) - out_flow(v) = vertex[v].
```

The root supplies all demand:

```text
out_flow(r) - in_flow(r) = sum_{v != r} vertex[v].
```

Suppose an active vertex were unreachable from the root through selected
edges. Let `S` be all such vertices. No enabled edge enters `S`, but summing
the flow equations over `S` requires positive net inflow equal to the number
of active vertices in `S`. This is a contradiction. Every active vertex is
therefore reachable from the root.

### Rooted Arborescence

The tree mode chooses one selected incoming parent edge for every active
non-root vertex. Integer depths start at zero at the root and increase by one
along each parent edge. Active non-root vertices have positive depth.

The strict depth increase prevents a parent cycle. Following parent edges
backward from any active vertex must therefore terminate at the root, the only
active vertex allowed to have no parent. The selected support contains a
directed path from the root to every active vertex.

### Iterative Connectivity Cuts

The cut mode first solves length, balance, support, and coverage without
auxiliary connectivity variables. If a solution has a non-root connected
component `C`, it adds the valid inequalities

```text
vertex[v] <= sum_{w entering C} use[w]    for every v in C.
```

Any connected support containing an active vertex in `C` must select an edge
entering `C`. The current disconnected solution selects none and is removed.
The model is solved again until it produces one connected component, proves
the accumulated relaxation infeasible, or reaches the total time limit.

Every added inequality is necessary for a connected solution. Consequently,
an infeasible cut-augmented relaxation is a sound infeasibility result for
that anchor case. A timeout remains `UNKNOWN`.

## Connected-Support Repair

A balanced covering support can still be disconnected. The repair tool takes
one retained support `S_0`, requires a connected distinct-window cycle `S`,
and imposes

```text
|S intersect S_0| >= h.
```

Both supports have the same size, so this permits at most `L-h` edge
replacements. The ten partitioned zero-ball anchors are disjoint and complete.
Only when every anchor reports infeasible has the CP-SAT portfolio evaluated
the full overlap neighborhood without an unresolved anchor.

The retained 69-edge support has four components with edge counts
`1,4,4,60`. CP-SAT reported every anchor case with overlap at least 58 as
infeasible. Within the tested exact formulation, these solver statuses imply
that a connected distinct-window 69-edge covering cycle would need to replace
at least 12 edges of that support. No independently checkable proof trace was
emitted, so this remains exact-model computational evidence rather than a
formal theorem or a lower bound on `L(9,1)`.

## Equivalence

A valid cyclic sequence gives a closed de Bruijn walk. Its window
multiplicities satisfy length, balance, support, coverage, and connectivity.
Because it covers `0^n`, at least one anchor case accepts it.

Conversely, replace every selected edge `w` by `count[w]` parallel copies. The
resulting directed multigraph is balanced and connected on its nonisolated
vertices, so it has an Euler circuit. Consecutive edges overlap in `n-1` bits.
Reading the appended bit of each circuit edge gives a cyclic binary sequence
whose window multiset is exactly the modeled count vector. The coverage
constraints therefore hold for the decoded sequence.

Thus the union of all anchor models is feasible exactly when a valid cyclic
covering sequence exists. The correspondence is not one-to-one because a
sequence may admit several anchors and a count vector may admit several Euler
circuits.

## Search Modes

The unrestricted model allows repeated windows. The optional
`--distinct-windows` mode imposes

```text
count[w] = use[w].
```

This mode searches only sequences with `L` distinct windows. A failure in this
subclass is not a global impossibility result.

The optional hint-overlap objective guides the solver toward a supplied edge
support. It changes search order, not feasibility or final verification.

A repeated-window search enables stationarity and autocorrelation constraints
by default. Walsh aggregates are opt-in through `--walsh` or
`--walsh-max-order`. Pair-projection rows are opt-in through
`--pair-projection-scope`. Each family can be disabled independently for
controlled benchmarks.

The disconnected support sampler disables connected-cycle-only
autocorrelation orbit bounds. It can optionally cap or minimize the number of
active vertices while retaining the globally valid active-vertex inequality.

Wall time and deterministic-work limits can both be recorded. Formulation
comparisons should use matched deterministic budgets or repeated
time-to-result runs rather than branch counts from unmatched wall-time runs.

A global lower-bound claim cannot come from one exact length. To prove
`L(9,1) >= 71`, every still-admissible length from 62 through 70 must be
excluded unless a separate monotonicity result is established.

## Independent Validation

The implementation is checked by:

- exhaustive feasibility comparison with direct sequence enumeration on small
  instances;
- agreement of flow, tree, and iterative-cut connectivity on those instances;
- disconnected balanced-support counterexamples;
- repeated-edge and loop extraction tests;
- a full 512-edge order-9 de Bruijn cycle;
- doubled multiplicities of the verified 71-bit baseline;
- exact reconstruction of the retained six-gap seed;
- exhaustive small-cycle checks of the stationarity and shift-distance
  identities;
- coefficient-level model-proto checks for stationarity, Walsh, and
  autocorrelation inequalities;
- exhaustive small-cycle and coefficient-level checks for the active-vertex
  and cyclic weight-layer path cuts;
- exhaustive small-instance checks of unique-duplicate identities and support
  projection rows;
- positive and negative connected-support repair controls;
- a length-71 CP-SAT positive control;
- final verification through `tools/covering.py`, independently of solver
  auxiliary variables.
