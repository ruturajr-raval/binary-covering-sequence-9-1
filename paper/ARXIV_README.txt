FIXED-BACKBONE COVERING-SEQUENCE CERTIFICATE
============================================

This source archive accompanies:

  A Fixed-Backbone Exclusion for Length-70 Binary (9,1)
  Covering Sequences

Author: Ruturaj R Raval
ORCID: 0000-0003-4930-8981

CONTENTS
--------

main.tex
  Manuscript source.

replay.py
  Complete certificate replay using standard-library Python and a C++20
  compiler.

anc/replay/
  An allowlisted replay tree preserving the repository-relative `data/` and
  `evidence/` paths. It contains the explicit inputs, all 168 overlap-62
  residual flows, all 188 overlap-61 residual flows, exact source snapshots,
  the separate C++ output, semantic validators, and SHA-256 manifests.

LICENSE, NOTICE, LICENSES/Apache-2.0.txt
  File-level licensing and provenance. Original project code is MIT licensed.
  The retained upstream 71-bit certificate is covered by Apache-2.0.

MANIFEST.sha256
  SHA-256 digest for every other file in this archive.

REPLAY
------

From the extracted archive:

  python3 replay.py

The command:

1. authenticates the archive and both nested evidence manifests;
2. regenerates the common-backbone analysis and compares it byte-for-byte;
3. reruns the common-backbone semantic validator;
4. regenerates the exact-overlap-61 Python analysis and compares it;
5. compiles and runs the separate C++20 implementation and compares it; and
6. reruns the exact-overlap semantic validator.

No network access or third-party Python package is required. Set CXX to choose
a compiler other than the default `c++`. The replay is tested in CI with
Python 3.10, 3.12, and 3.14, using both g++ and clang++.

CLAIM SCOPE
-----------

The certificate proves that every length-70 binary radius-1 covering sequence,
if one exists, uses at most 60 distinct edges of the explicit backbone.

It does not:

- construct a valid 70-bit covering sequence;
- prove that no such sequence exists;
- improve either global bound on L(9,1); or
- exclude candidates with backbone overlap at most 60.

ARCHIVE
-------

Repository:
https://github.com/ruturajr-raval/binary-covering-sequence-9-1

Concept DOI:
https://doi.org/10.5281/zenodo.22260691

Release: v0.3.0
