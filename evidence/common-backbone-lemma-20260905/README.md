# Common-Backbone Publication Evidence

This directory retains the strengthened finite certificate behind the
common-backbone overlap theorem.

## Certified Claim

For the explicit 64-edge support in
`data/candidates/l9-r1-common-backbone-64.json`, every connected
nonnegative integral circulation of total mass 70 uses at most 61 distinct
backbone edges.

The overlap-62 stage checks all 2,016 omitted-edge pairs and retains all 168
admissible residual flows. Every resulting support has at least two weak
components. The component-count histogram is:

```text
2 components: 36
3 components: 76
4 components: 50
5 components: 6
```

The retained 70-bit witness attains overlap 61, so the graph-theoretic bound
is exact. The witness is not a radius-1 cover.

## Verification

`analysis.json` records:

- the fixed backbone and its two directed-cycle components of sizes 4 and 60;
- the exhaustive connector and one-omission detour checks;
- every overlap-62 residual flow, with a SHA-256 digest and component count;
- two lower-mass connected positive controls; and
- the tight overlap-61 witness.

`source/verify_common_backbone_v1.py` independently checks the backbone
structure and coverage, directly reruns the short connector and detour
exclusions, semantically validates every retained residual, reconstructs all
histograms, and checks the tight witness. Mutation tests in the repository
confirm that missing or altered residuals are rejected.

The analyzer and validator use only the Python standard library.

## Reproduce

From the repository root:

```bash
mkdir -p build/publication

PYTHONDONTWRITEBYTECODE=1 python3 -B \
  evidence/common-backbone-lemma-20260905/source/analyze_common_backbone_v2.py \
  data/candidates/l9-r1-common-backbone-64.json \
  build/publication/common-backbone-analysis.json \
  --baseline data/baseline/l9-r1-71.txt \
  --overlap-witness \
    data/candidates/l9-r1-70-backbone-overlap-61.txt \
  --n 9 --radius 1 --candidate-length 70

cmp build/publication/common-backbone-analysis.json \
  evidence/common-backbone-lemma-20260905/analysis.json

PYTHONDONTWRITEBYTECODE=1 python3 -B \
  evidence/common-backbone-lemma-20260905/source/verify_common_backbone_v1.py \
  evidence/common-backbone-lemma-20260905/analysis.json \
  --support data/candidates/l9-r1-common-backbone-64.json \
  --witness data/candidates/l9-r1-70-backbone-overlap-61.txt
```

Check the retained file manifest with:

```bash
cd evidence/common-backbone-lemma-20260905
shasum -a 256 -c files.sha256
```

## Scope

This certificate is specific to the stated backbone and total mass 70. It
does not exclude a length-70 covering sequence with backbone overlap at most
60 and does not change the known global bounds on `L(9,1)`.
