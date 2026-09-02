#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

try:
    from .generate_cnf import (
        at_most_cardinality_encoding,
        bit_variable,
        negated_mismatch_literal,
    )
    from .repair_support import load_support_certificate
except ImportError:
    from generate_cnf import (
        at_most_cardinality_encoding,
        bit_variable,
        negated_mismatch_literal,
    )
    from repair_support import load_support_certificate


def match_variable(
    length: int,
    support_size: int,
    support_index: int,
    start: int,
) -> int:
    if not 0 <= support_index < support_size:
        raise ValueError("support index is outside the support range")
    if not 0 <= start < length:
        raise ValueError("start is outside the sequence range")
    return length + support_index * length + start + 1


def backbone_presence_variable(
    length: int,
    support_size: int,
    support_index: int,
) -> int:
    if not 0 <= support_index < support_size:
        raise ValueError("support index is outside the support range")
    return length + length * support_size + support_index + 1


def write_backbone_overlap_cnf(
    path: Path,
    *,
    support: list[int],
    n: int,
    length: int,
    minimum_overlap: int,
    anchor_word: int | None = None,
) -> tuple[int, int]:
    if n <= 0 or length < n:
        raise ValueError("require 0 < n <= length")
    if not support or len(set(support)) != len(support):
        raise ValueError("support must contain distinct edges")
    if any(edge < 0 or edge >= 1 << n for edge in support):
        raise ValueError("support contains an out-of-range edge")
    if not 0 <= minimum_overlap <= len(support):
        raise ValueError("minimum overlap is outside the support range")
    if anchor_word is not None and not 0 <= anchor_word < 1 << n:
        raise ValueError("anchor word is outside the n-bit range")

    support = sorted(support)
    support_size = len(support)
    base_variables = (
        length + length * support_size + support_size
    )
    maximum_missing = support_size - minimum_overlap
    counter_variables, counter_clauses = at_most_cardinality_encoding(
        [
            -backbone_presence_variable(
                length,
                support_size,
                support_index,
            )
            for support_index in range(support_size)
        ],
        maximum_missing,
        base_variables=base_variables,
    )
    variable_count = base_variables + counter_variables
    clause_count = (
        length * support_size * (n + 2)
        + support_size
        + len(counter_clauses)
        + (n if anchor_word is not None else 0)
    )

    with path.open("w", encoding="ascii") as stream:
        stream.write(f"p cnf {variable_count} {clause_count}\n")
        if anchor_word is not None:
            for offset in range(n):
                variable = bit_variable(offset)
                bit = (anchor_word >> (n - 1 - offset)) & 1
                literal = variable if bit else -variable
                stream.write(f"{literal} 0\n")

        for support_index, word in enumerate(support):
            presence = backbone_presence_variable(
                length,
                support_size,
                support_index,
            )
            matches = []
            for start in range(length):
                match = match_variable(
                    length,
                    support_size,
                    support_index,
                    start,
                )
                matches.append(match)
                matching_literals = []
                for offset in range(n):
                    position = (start + offset) % length
                    variable = bit_variable(position)
                    word_bit = (word >> (n - 1 - offset)) & 1
                    literal = negated_mismatch_literal(
                        variable,
                        word_bit,
                    )
                    matching_literals.append(literal)
                    stream.write(f"-{match} {literal} 0\n")
                stream.write(
                    " ".join(
                        [
                            str(match),
                            *(
                                str(-literal)
                                for literal in matching_literals
                            ),
                        ]
                    )
                    + " 0\n"
                )
                stream.write(f"-{match} {presence} 0\n")

            stream.write(
                " ".join(
                    [
                        f"-{presence}",
                        *(str(match) for match in matches),
                    ]
                )
                + " 0\n"
            )

        for clause in counter_clauses:
            stream.write(
                " ".join(str(literal) for literal in clause) + " 0\n"
            )

    return variable_count, clause_count


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a CNF requiring a cyclic binary sequence to contain "
            "a minimum number of reference de Bruijn edges."
        )
    )
    parser.add_argument("support", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument("--minimum-overlap", type=int, required=True)
    parser.add_argument("--anchor-word", type=int)
    args = parser.parse_args()

    support = load_support_certificate(args.support, n=args.n)
    variables, clauses = write_backbone_overlap_cnf(
        args.output,
        support=support,
        n=args.n,
        length=args.length,
        minimum_overlap=args.minimum_overlap,
        anchor_word=args.anchor_word,
    )
    print(
        f"wrote {args.output} with {variables} variables and "
        f"{clauses} clauses"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
