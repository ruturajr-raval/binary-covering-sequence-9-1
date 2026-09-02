#!/usr/bin/env python3
from __future__ import annotations

import argparse
from math import comb
from pathlib import Path


def bit_variable(position: int) -> int:
    return position + 1


def selector_variable(length: int, target: int, start: int) -> int:
    return length + target * length + start + 1


def pattern_variable(length: int, total_words: int, start: int, word: int) -> int:
    return length + start * total_words + word + 1


def presence_variable(length: int, total_words: int, word: int) -> int:
    return length + length * total_words + word + 1


def distance_counter_variable(
    base_variables: int,
    width: int,
    position: int,
    threshold: int,
) -> int:
    return base_variables + position * width + threshold


def exact_cardinality_encoding(
    literals: list[int],
    target: int,
    *,
    base_variables: int,
) -> tuple[int, list[tuple[int, ...]]]:
    """Encode an exact count through equivalent unary prefix thresholds."""
    if not literals:
        raise ValueError("exact cardinality requires at least one literal")
    if target < 0 or target > len(literals):
        raise ValueError("exact cardinality target is outside the literal range")

    if target > len(literals) - target:
        literals = [-literal for literal in literals]
        target = len(literals) - target

    width = target + 1

    def counter(position: int, threshold: int) -> int:
        return distance_counter_variable(
            base_variables,
            width,
            position,
            threshold,
        )

    clauses: list[tuple[int, ...]] = []
    first_literal = literals[0]
    first_counter = counter(0, 1)
    clauses.append((-first_counter, first_literal))
    clauses.append((first_counter, -first_literal))
    for threshold in range(2, width + 1):
        clauses.append((-counter(0, threshold),))

    for position, literal in enumerate(literals[1:], start=1):
        for threshold in range(1, width + 1):
            current = counter(position, threshold)
            previous = counter(position - 1, threshold)
            clauses.append((-previous, current))
            clauses.append((-current, previous, literal))
            if threshold == 1:
                clauses.append((-literal, current))
                continue

            previous_lower = counter(position - 1, threshold - 1)
            clauses.append((-literal, -previous_lower, current))
            clauses.append((-current, previous, previous_lower))

    final_position = len(literals) - 1
    if target > 0:
        clauses.append((counter(final_position, target),))
    clauses.append((-counter(final_position, target + 1),))
    return len(literals) * width, clauses


def negated_mismatch_literal(variable: int, target_bit: int) -> int:
    return variable if target_bit == 1 else -variable


def write_cnf(path: Path, *, n: int, radius: int, length: int) -> tuple[int, int]:
    if radius != 1:
        raise ValueError("the exact encoder currently supports radius 1")
    if n <= 0 or length < n:
        raise ValueError("require 0 < n <= length")

    total_words = 1 << n
    variable_count = length + total_words * length
    clause_count = 2 + total_words * (1 + length * comb(n, 2))

    with path.open("w", encoding="ascii") as stream:
        stream.write(f"p cnf {variable_count} {clause_count}\n")

        # Every valid sequence contains a zero, so rotate one zero to position 0.
        stream.write(f"-{bit_variable(0)} 0\n")

        # Reflect around position 0 if needed so x[1] <= x[L-1].
        stream.write(f"-{bit_variable(1)} {bit_variable(length - 1)} 0\n")

        for target in range(total_words):
            selectors = [
                selector_variable(length, target, start) for start in range(length)
            ]
            stream.write(" ".join(str(value) for value in selectors) + " 0\n")

            for start, selector in enumerate(selectors):
                for first in range(n):
                    first_position = (start + first) % length
                    first_variable = bit_variable(first_position)
                    first_target_bit = (target >> (n - 1 - first)) & 1
                    first_literal = negated_mismatch_literal(
                        first_variable, first_target_bit
                    )

                    for second in range(first + 1, n):
                        second_position = (start + second) % length
                        second_variable = bit_variable(second_position)
                        second_target_bit = (target >> (n - 1 - second)) & 1
                        second_literal = negated_mismatch_literal(
                            second_variable, second_target_bit
                        )
                        stream.write(
                            f"-{selector} {first_literal} {second_literal} 0\n"
                        )

    return variable_count, clause_count


def write_pattern_cnf(
    path: Path,
    *,
    n: int,
    radius: int,
    length: int,
    symmetry: bool = True,
    seed_bits: list[int] | None = None,
    max_distance: int | None = None,
    exact_support: int | None = None,
) -> tuple[int, int]:
    if radius != 1:
        raise ValueError("the exact encoder currently supports radius 1")
    if n <= 0 or length < n:
        raise ValueError("require 0 < n <= length")
    if (seed_bits is None) != (max_distance is None):
        raise ValueError("seed_bits and max_distance must be supplied together")
    total_words = 1 << n
    if exact_support is not None and not 0 <= exact_support <= min(
        length,
        total_words,
    ):
        raise ValueError(
            "exact support must be between 0 and the maximum possible support"
        )
    if seed_bits is not None:
        if symmetry:
            raise ValueError(
                "fixed-seed neighborhoods require symmetry=False"
            )
        if len(seed_bits) != length:
            raise ValueError("seed sequence length does not match length")
        if any(bit not in (0, 1) for bit in seed_bits):
            raise ValueError("seed sequence must contain only binary digits")
        if max_distance is None or max_distance < 0:
            raise ValueError("max_distance must be nonnegative")

    anchor_clauses = comb(n, 2) if symmetry else 0
    reflection_clauses = int(symmetry and length > n)
    base_variables = length + length * total_words + total_words
    constrained_distance = (
        max_distance
        if max_distance is not None and max_distance < length
        else None
    )
    counter_width = (
        constrained_distance + 1
        if constrained_distance is not None
        else 0
    )
    counter_variables = length * counter_width
    counter_clauses = (
        2 + 2 * counter_width * (length - 1)
        if counter_width > 0
        else 0
    )
    support_counter_variables = 0
    support_counter_clauses: list[tuple[int, ...]] = []
    if exact_support is not None:
        support_counter_variables, support_counter_clauses = (
            exact_cardinality_encoding(
                [
                    presence_variable(length, total_words, word)
                    for word in range(total_words)
                ],
                exact_support,
                base_variables=base_variables + counter_variables,
            )
        )
    reverse_channel_clauses = (
        length * total_words if exact_support is not None else 0
    )
    variable_count = (
        base_variables + counter_variables + support_counter_variables
    )
    clause_count = (
        anchor_clauses
        + reflection_clauses
        + length * total_words * (n + 1)
        + reverse_channel_clauses
        + total_words
        + total_words
        + counter_clauses
        + len(support_counter_clauses)
    )

    with path.open("w", encoding="ascii") as stream:
        stream.write(f"p cnf {variable_count} {clause_count}\n")

        if symmetry:
            # Rotate a window covering the all-zero target to position 0.
            for first in range(n):
                for second in range(first + 1, n):
                    stream.write(
                        f"-{bit_variable(first)} -{bit_variable(second)} 0\n"
                    )

            # Reverse around the anchored window if needed.
            if length > n:
                stream.write(
                    f"-{bit_variable(n)} {bit_variable(length - 1)} 0\n"
                )

        for start in range(length):
            for word in range(total_words):
                pattern = pattern_variable(length, total_words, start, word)
                presence = presence_variable(length, total_words, word)
                matching_literals = []
                for offset in range(n):
                    position = (start + offset) % length
                    variable = bit_variable(position)
                    word_bit = (word >> (n - 1 - offset)) & 1
                    literal = negated_mismatch_literal(variable, word_bit)
                    matching_literals.append(literal)
                    stream.write(f"-{pattern} {literal} 0\n")
                if exact_support is not None:
                    stream.write(
                        " ".join(
                            [
                                str(pattern),
                                *(
                                    str(-literal)
                                    for literal in matching_literals
                                ),
                            ]
                        )
                        + " 0\n"
                    )
                stream.write(f"-{pattern} {presence} 0\n")

        for word in range(total_words):
            presence = presence_variable(length, total_words, word)
            patterns = [
                pattern_variable(length, total_words, start, word)
                for start in range(length)
            ]
            stream.write(
                " ".join([f"-{presence}", *(str(value) for value in patterns)])
                + " 0\n"
            )

        for target in range(total_words):
            ball = [
                target,
                *(target ^ (1 << bit) for bit in range(n)),
            ]
            presences = [
                presence_variable(length, total_words, word) for word in ball
            ]
            stream.write(" ".join(str(value) for value in presences) + " 0\n")

        if seed_bits is not None and constrained_distance is not None:
            for position, seed_bit in enumerate(seed_bits):
                mismatch = (
                    bit_variable(position)
                    if seed_bit == 0
                    else -bit_variable(position)
                )
                for threshold in range(1, counter_width + 1):
                    current = distance_counter_variable(
                        base_variables,
                        counter_width,
                        position,
                        threshold,
                    )
                    if position == 0:
                        if threshold == 1:
                            stream.write(f"{-mismatch} {current} 0\n")
                        continue

                    previous = distance_counter_variable(
                        base_variables,
                        counter_width,
                        position - 1,
                        threshold,
                    )
                    stream.write(f"-{previous} {current} 0\n")
                    if threshold == 1:
                        stream.write(f"{-mismatch} {current} 0\n")
                    else:
                        previous_lower = distance_counter_variable(
                            base_variables,
                            counter_width,
                            position - 1,
                            threshold - 1,
                        )
                        stream.write(
                            f"{-mismatch} -{previous_lower} {current} 0\n"
                        )

            overflow = distance_counter_variable(
                base_variables,
                counter_width,
                length - 1,
                counter_width,
            )
            stream.write(f"-{overflow} 0\n")

        for clause in support_counter_clauses:
            stream.write(" ".join(str(literal) for literal in clause) + " 0\n")

    return variable_count, clause_count


def load_binary_sequence(path: Path) -> list[int]:
    tokens = path.read_text(encoding="ascii").split()
    if len(tokens) == 1 and set(tokens[0]) <= {"0", "1"}:
        tokens = list(tokens[0])
    if not tokens or any(token not in {"0", "1"} for token in tokens):
        raise ValueError("seed sequence must contain only binary digits")
    return [int(token) for token in tokens]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a covering-sequence CNF.")
    parser.add_argument("output", type=Path)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--radius", type=int, required=True)
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument(
        "--encoding",
        choices=("selector", "pattern"),
        default="selector",
    )
    parser.add_argument("--seed-sequence", type=Path)
    parser.add_argument("--max-distance", type=int)
    parser.add_argument("--exact-support", type=int)
    parser.add_argument("--no-symmetry", action="store_true")
    args = parser.parse_args()

    if args.encoding != "pattern" and args.exact_support is not None:
        parser.error("--exact-support requires pattern encoding")
    if args.encoding != "pattern" and (
        args.seed_sequence is not None
        or args.max_distance is not None
        or args.no_symmetry
    ):
        parser.error("neighborhood and symmetry options require pattern encoding")
    if args.seed_sequence is not None and not args.no_symmetry:
        parser.error("fixed-seed neighborhoods require --no-symmetry")

    writer = write_cnf if args.encoding == "selector" else write_pattern_cnf
    if args.encoding == "selector":
        variables, clauses = writer(
            args.output,
            n=args.n,
            radius=args.radius,
            length=args.length,
        )
    else:
        seed_bits = (
            load_binary_sequence(args.seed_sequence)
            if args.seed_sequence is not None
            else None
        )
        variables, clauses = writer(
            args.output,
            n=args.n,
            radius=args.radius,
            length=args.length,
            symmetry=not args.no_symmetry,
            seed_bits=seed_bits,
            max_distance=args.max_distance,
            exact_support=args.exact_support,
        )
    print(
        f"wrote {args.output} with {variables} variables and {clauses} clauses "
        f"using the {args.encoding} encoding"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
