# Research Workbench

This directory records the search for a 70-bit cyclic binary radius-1 covering
sequence and the exact exclusions developed around that search.

The retained 71-bit sequence remains the verified public construction. No
70-bit sequence has yet passed the independent verifiers, and no retained proof
excludes every admissible 70-bit sequence.

## Active Target

The primary target is a valid 70-bit sequence. The exact 61-edge overlap shell
of the retained 64-edge common backbone is now completely classified and
contains no valid cover. The finite proof lane therefore moves to selected
overlap-at-most-60 shells, while the construction lane performs support
surgery and exact repair around the six-gap seed.

An exclusion of one restricted shell is useful research evidence but is not a
global lower bound for `L(9,1)`.

## Records

- `claim.yaml` defines the exact scope of the candidate result.
- `release-gate.json` records which promotion requirements have been met.
- `run.schema.json` defines the minimum metadata for retained computations.
- `/.research-artifacts/` holds local exploratory outputs and is not tracked.

Every claimed sequence must pass the independent Python and C++ verifiers.
Every impossibility claim must retain a replayable proof or a finite
certificate accepted by a separately implemented checker.

The exact-overlap-61 result meets this standard through two full
implementations, semantic validation of every retained residual, direct
small-instance oracles, and byte-for-byte evidence replay.

## Promotion Standard

A result is ready for promotion only when it provides at least one of:

1. A valid 70-bit sequence accepted by both independent verifiers.
2. A complete checked exact-length theorem with clearly stated scope.
3. A broader structural theorem that materially changes the search frontier.

In every case, prior art must be refreshed, evidence must replay from a clean
checkout, claim boundaries must be explicit, and independent review must be
requested before a theorem announcement.
