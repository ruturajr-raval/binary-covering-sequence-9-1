# arXiv Submission Metadata

## Title

A Fixed-Backbone Exclusion for Length-70 Binary (9,1) Covering Sequences

## Author

Ruturaj R Raval

Independent Researcher

ORCID: 0000-0003-4930-8981

## Categories

- Primary: math.CO
- Cross-list: cs.IT

## Abstract

A binary (n,R) covering sequence is a cyclic binary word whose length-n
windows cover the Hamming cube within radius R. The known bounds for the
minimum length at (n,R)=(9,1) are 62 <= L(9,1) <= 71. We fix an explicit
64-edge balanced covering support B in the order-8 binary de Bruijn digraph.
First, a finite graph-theoretic certificate proves that every connected
nonnegative integral circulation of total mass 70 uses at most 61 distinct
edges of B. Second, an exhaustive path-cycle decomposition classifies the
exact-overlap-61 shell. Among all 41,664 triples of omitted backbone edges,
188 residual flows survive and exactly eight produce connected 70-edge
circulations. Six leave nine binary 9-words uncovered and two leave ten, so
none is a radius-1 cover. Consequently, every length-70 binary (9,1) covering
sequence, if one exists, uses at most 60 distinct edges of B. The
overlap-61 classification is reproduced by separate Python and C++
implementations; the prerequisite overlap theorem retains all 168 boundary
residuals and a semantic validator. This result does not construct or exclude
a length-70 covering sequence and does not change the global bounds on
L(9,1).

## Comments

7 pages, 4 tables. Includes deterministic ancillary source and a complete
replay using standard-library Python and a C++20 compiler.

## License

arXiv perpetual, non-exclusive license to distribute.

## Submission Checks

- Upload `dist/arxiv/binary-covering-sequence-9-1.tar.gz`.
- Confirm that arXiv compiles `main.tex`.
- Inspect the generated PDF, especially the long table of eight completions.
- Confirm primary category `math.CO` and cross-list `cs.IT`.
- Use the abstract above without adding a global bound or impossibility claim.
- Complete the final authenticated submission and PDF certification manually.
