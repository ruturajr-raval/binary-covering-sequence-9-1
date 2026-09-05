# Common-Backbone Exclusion

## Statement

Let `B` be the 64-edge set in
`data/candidates/l9-r1-common-backbone-64.json`. It is a balanced binary
de Bruijn support with two directed-cycle components containing 4 and 60
edges.

Every connected nonnegative integral circulation of total multiplicity 70
uses at most 61 distinct edges of `B`.

Equivalently, no 70-bit cyclic binary sequence can contain 62 or more
distinct backbone windows. This conclusion is graph-theoretic. It does not
use the radius-1 covering constraints.

The bound is tight. The retained 70-bit witness

```text
0010010111010100111000010000001100110000110110100010101100011110111111
```

has 70 distinct cyclic windows and contains exactly 61 edges of `B`. It
omits backbone edges `13`, `307`, and `409`. It covers 503 of the 512 target
words, so it is not a radius-1 covering certificate.

## Sequence-To-Graph Translation

Use the order-8 binary de Bruijn digraph. Its vertices are the 8-bit words,
and each 9-bit word is a directed edge from its 8-bit prefix to its 8-bit
suffix.

A cyclic binary sequence gives a nonnegative integer edge-multiplicity
vector `m` with three properties:

1. `m` is balanced at every vertex.
2. The positive-multiplicity support is weakly connected.
3. The total multiplicity is the sequence length.

Conversely, these properties permit an Euler circuit and therefore recover a
cyclic sequence.

## Finite Facts

The retained analyzer checks the following facts directly.

### Connector Cost

Any directed closed walk that starts in the 4-edge component, touches the
60-edge component, and returns to its starting vertex has length at least 7.
Backbone edges are allowed in this statement, so it also covers repeated
backbone windows.

There are exactly

```text
4 * (2^1 + 2^2 + ... + 2^6) = 504
```

candidate appended-bit walks of lengths 1 through 6 from the four vertices
of the small component. Exhaustive enumeration rejects all 504.

The bound is tight. The two 7-edge connector walks are complementary. Their
edge lists are

```text
205, 411, 310, 108, 217, 435, 358
306, 100, 201, 403, 294, 76, 153
```

The first has vertex sequence

```text
102, 205, 155, 54, 108, 217, 179, 102.
```

All fourteen listed edge occurrences are outside `B`. Each connector joined
to `B` gives a valid 71-edge support. The first gives the retained baseline,
and the second gives its bitwise complement.

### One-Omission Detours

Fix an omitted backbone edge `e = u -> v`. Any directed `u`-to-`v` walk that
avoids `e` and touches the other backbone component has length at least 10.

The analyzer checks every one of the 64 choices of `e` and every appended-bit
walk through length 7:

```text
64 * (2^1 + 2^2 + ... + 2^7) = 16,256.
```

None is a valid detour. Separate breadth-first searches find exact minimum
detour lengths from 10 through 16, with histogram

```text
10: 2
11: 12
12: 10
13: 8
14: 18
15: 10
16: 4
```

The complete per-edge witnesses are stored in the retained JSON analysis.

### Two-Omission Residuals

Fix two omitted backbone edges and retain one copy of each of the other 62
edges. A total-multiplicity-70 completion has an eight-edge residual.

The analyzer checks all

```text
C(64, 2) = 2,016
```

omitted-edge pairs. For 64 adjacent pairs, the residual divergence has one
source and one sink. For the other 1,952 pairs, it has two sources and two
sinks, counted with multiplicity.

Every nonnegative integral residual with this divergence decomposes into one
or two directed source-to-sink walks and a balanced remainder. The balanced
remainder decomposes into directed closed walks. Since the total residual
mass is eight, every walk involved has length at most eight.

For fixed endpoints, the analyzer enumerates every appended-bit word of
length 1 through 8 and rejects walks using an omitted edge. For each possible
remaining mass, it independently enumerates all aggregate balanced flows by
combining closed walks encoded by cyclic binary words. The numbers of
distinct balanced flows at masses 0 through 8 are

```text
1, 2, 4, 8, 16, 32, 64, 128, 256.
```

Only 44 distinct endpoint-compatible path flows survive. Combining them with
all balanced remainders of the required mass gives 208 raw decompositions
and 168 distinct eight-edge residual flows. None makes the retained
62-edge support weakly connected. Their combined support component counts
are

```text
2 components: 36
3 components: 76
4 components: 50
5 components: 6
```

The complete active-case counts are stored in the retained JSON analysis.

### Exact-Length Positive Control

The same enumerator finds two connected residuals at mass 7:

```text
omit 102, 204: 103, 206, 412, 313, 115, 230, 460
omit 307, 409: 408, 305, 99, 198, 396, 281, 51
```

Each produces a connected circulation of total multiplicity 69 with backbone
overlap 62. This positive control shows that the enumeration is not merely
rejecting every two-omission instance. It also shows that the theorem is
specific to total multiplicity 70. The property is not monotone in the cycle
length.

## Proof

### All 64 Backbone Edges

Let `m` be a connected nonnegative integral circulation that contains at
least one copy of every edge in `B`. Define

```text
a = m - 1_B.
```

Because both `m` and `1_B` are balanced, `a` is a nonnegative integral
circulation. Since `m` is connected while `B` has two components, some weak
component of the positive support of `a` touches both components of `B`.
That component is balanced, so it has an Euler circuit. Rotating the circuit
to start at its contact with the 4-edge component gives a closed connector
walk whose length is at most the total multiplicity of `a`.

The connector cost is 7, hence

```text
|m| - 64 = |a| >= 7.
```

Therefore `|m| >= 71`.

### Exactly 63 Backbone Edges

Now let `m` have total multiplicity 70 and contain exactly 63 distinct edges
of `B`. Let `e = u -> v` be the omitted edge, and define

```text
r = 1_B - 1_e
a = m - r.
```

The residual `a` is nonnegative and has total multiplicity

```text
70 - 63 = 7.
```

Using outdegree minus indegree as divergence, `a` has divergence `+1` at
`u`, `-1` at `v`, and zero elsewhere. The weak component `H` of `a`
containing `u` must also contain `v`; otherwise the divergences in that weak
component would not sum to zero. The directed multigraph `H` therefore has
an Euler trail from `u` to `v`. Since `e` is omitted from `m`, its
multiplicity in `a` is zero, so this trail avoids `e`.

Removing one edge from either directed-cycle component of `B` leaves two
weak components. Connectivity of `m = r + a` implies that some weak
component `K` of `a` touches both. One way to see this is to form the
bipartite incidence graph whose nodes are the weak components of `r` and
`a`, joining two nodes when their vertex sets meet. The incidence graph is
connected and has only two `r` nodes, so some `a` node is adjacent to both.

If `K = H`, its Euler trail is a `u`-to-`v` detour through the other
backbone component using at most 7 edges. The one-omission enumeration shows
that every such detour needs at least 10 edges, a contradiction.

If `K` is not `H`, then `K` is balanced and has a closed Euler circuit
touching both backbone components. The component `H` uses at least one edge,
so `K` uses at most 6 of the 7 residual edges. The connector enumeration
shows that every such closed walk needs at least 7 edges, again a
contradiction.

Thus total multiplicity 70 is impossible at backbone overlap 63. Combined
with the all-64 case, overlap at least 63 is impossible.

### Exactly 62 Backbone Edges

Let `m` have total multiplicity 70 and contain exactly 62 distinct edges of
`B`. Let `E` be the two omitted edges, and define

```text
r = 1_B - 1_E
a = m - r.
```

Then `a` is a nonnegative integral edge flow of total mass 8, it uses neither
edge in `E`, and its divergence is the negative of the divergence of `r`.
The total positive divergence of `a` is either one or two.

The standard integral-flow decomposition removes a directed walk from a
positive-divergence vertex to a negative-divergence vertex until all
divergence is discharged. What remains is balanced and therefore decomposes
into directed closed walks. Consequently every possible `a` appears in the
finite two-omission enumeration above: one or two endpoint-compatible walks,
plus a collection of closed walks, with total mass exactly 8.

The enumeration checks all 2,016 choices of `E` and all 168 distinct residual
flows that satisfy the edge, mass, and divergence conditions. In every case,
the positive support of `m = r + a` has at least two weak components. This
contradicts the connectedness required of a cyclic sequence.

Thus overlap 62 is impossible. Every 70-bit cyclic binary sequence has
backbone overlap at most 61, and the retained witness shows that 61 is
attained.

## Scope

This result does not prove that a 70-bit covering sequence is impossible.
The separate exact-overlap-61 classification proves that no valid cover
attains the boundary value. Candidates with backbone overlap at most 60
remain possible.

The overlap bound is specific to 70-bit cycles. It must not be extrapolated
to length 69 or to other lengths.

The earlier all-distinct and multiplicity-aware CP-SAT campaigns emitted no
independently checkable proof traces and are retained only as historical
discovery evidence. The complete finite classification in
`docs/EXACT_OVERLAP_61.md` supersedes their nine timeouts. It is a separate
covering-specific theorem that combines with the graph-theoretic result above
to give the overlap-at-most-60 conclusion.

## Reproduction

Run

```bash
make analyze-backbone PYTHON=.venv/bin/python
python3 -m unittest tests.test_common_backbone -v
```

The first command writes `build/l9-r1-common-backbone-analysis.json`. The
strengthened publication analysis, all 168 residual vectors, semantic
validator, exact source snapshots, and SHA-256 manifest are under
`evidence/common-backbone-lemma-20260905`. The earlier
`evidence/common-backbone-lemma-20260902` directory is retained as the
original discovery snapshot.
