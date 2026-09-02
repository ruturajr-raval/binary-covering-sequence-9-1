from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import tempfile
import unittest
from itertools import product
from math import comb
from pathlib import Path
from unittest.mock import patch

from tools.covering import verify_sequence
from tools.generate_cnf import at_most_cardinality_encoding
from tools.generate_cnf import distinct_cyclic_windows_encoding
from tools.generate_cnf import distinct_support_balance_clauses
from tools.generate_cnf import exact_cardinality_encoding
from tools.generate_cnf import main as generate_cnf_main
from tools.generate_cnf import write_cnf, write_pattern_cnf


def formula_is_satisfiable(
    clauses: list[list[int]],
    fixed: dict[int, bool],
) -> bool:
    def solve(
        remaining: list[list[int]],
        assignment: dict[int, bool],
    ) -> bool:
        while True:
            simplified: list[list[int]] = []
            unit: int | None = None
            for clause in remaining:
                unresolved: list[int] = []
                satisfied = False
                for literal in clause:
                    variable = abs(literal)
                    if variable in assignment:
                        if assignment[variable] == (literal > 0):
                            satisfied = True
                            break
                    else:
                        unresolved.append(literal)
                if satisfied:
                    continue
                if not unresolved:
                    return False
                if len(unresolved) == 1:
                    unit = unresolved[0]
                simplified.append(unresolved)

            if not simplified:
                return True
            if unit is None:
                remaining = simplified
                break

            variable = abs(unit)
            value = unit > 0
            if variable in assignment and assignment[variable] != value:
                return False
            assignment[variable] = value
            remaining = simplified

        decision = min(remaining, key=len)[0]
        variable = abs(decision)
        for value in (decision > 0, decision < 0):
            branch = assignment.copy()
            branch[variable] = value
            if solve(remaining, branch):
                return True
        return False

    return solve(clauses, fixed.copy())


def cyclic_window_support_size(bits: tuple[int, ...], n: int) -> int:
    return len(
        {
            tuple(bits[(start + offset) % len(bits)] for offset in range(n))
            for start in range(len(bits))
        }
    )


class CnfGeneratorTests(unittest.TestCase):
    def test_header_counts_match_emitted_clauses(self) -> None:
        n = 4
        length = 8
        expected_variables = length + (1 << n) * length
        expected_clauses = 2 + (1 << n) * (1 + length * comb(n, 2))

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.cnf"
            variables, clauses = write_cnf(path, n=n, radius=1, length=length)
            lines = path.read_text(encoding="ascii").splitlines()

        self.assertEqual(variables, expected_variables)
        self.assertEqual(clauses, expected_clauses)
        self.assertEqual(lines[0], f"p cnf {expected_variables} {expected_clauses}")
        self.assertEqual(len(lines) - 1, expected_clauses)
        self.assertTrue(all(line.endswith(" 0") for line in lines[1:]))

    def test_non_radius_one_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.cnf"
            with self.assertRaises(ValueError):
                write_cnf(path, n=4, radius=2, length=8)

    def test_pattern_header_counts_match_emitted_clauses(self) -> None:
        n = 4
        length = 8
        total_words = 1 << n
        expected_variables = length + length * total_words + total_words
        expected_clauses = (
            comb(n, 2)
            + 1
            + length * total_words * (n + 1)
            + total_words
            + total_words
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.cnf"
            variables, clauses = write_pattern_cnf(
                path,
                n=n,
                radius=1,
                length=length,
            )
            lines = path.read_text(encoding="ascii").splitlines()

        self.assertEqual(variables, expected_variables)
        self.assertEqual(clauses, expected_clauses)
        self.assertEqual(lines[0], f"p cnf {expected_variables} {expected_clauses}")
        self.assertEqual(len(lines) - 1, expected_clauses)

    def test_exact_support_header_counts_match_emitted_clauses(self) -> None:
        n = 2
        length = 4
        total_words = 1 << n

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.cnf"
            for exact_support in (0, 2, 3, 4):
                with self.subTest(exact_support=exact_support):
                    if exact_support == length:
                        distinct_variables = comb(length, 2)
                        distinct_clauses = 5 * distinct_variables
                        balance_clauses = len(
                            distinct_support_balance_clauses(
                                length=length,
                                total_words=total_words,
                            )
                        )
                        counter_variables = distinct_variables
                        counter_clauses = (
                            distinct_clauses + balance_clauses
                        )
                    else:
                        normalized_target = min(
                            exact_support,
                            total_words - exact_support,
                        )
                        counter_width = normalized_target + 1
                        counter_variables = total_words * counter_width
                        final_clauses = (
                            1 if normalized_target == 0 else 2
                        )
                        counter_clauses = (
                            counter_width
                            + 1
                            + (total_words - 1)
                            * (4 * counter_width - 1)
                            + final_clauses
                        )
                    expected_variables = (
                        length
                        + length * total_words
                        + total_words
                        + counter_variables
                    )
                    expected_clauses = (
                        length * total_words * (n + 1)
                        + length * total_words
                        + 2 * total_words
                        + counter_clauses
                    )

                    variables, clauses = write_pattern_cnf(
                        path,
                        n=n,
                        radius=1,
                        length=length,
                        symmetry=False,
                        exact_support=exact_support,
                    )
                    lines = path.read_text(encoding="ascii").splitlines()

                    self.assertEqual(variables, expected_variables)
                    self.assertEqual(clauses, expected_clauses)
                    self.assertEqual(
                        lines[0],
                        f"p cnf {expected_variables} {expected_clauses}",
                    )
                    self.assertEqual(len(lines) - 1, expected_clauses)
                    self.assertTrue(
                        all(line.endswith(" 0") for line in lines[1:])
                    )
                    literals = [
                        abs(int(literal))
                        for line in lines[1:]
                        for literal in line.split()[:-1]
                    ]
                    self.assertLessEqual(max(literals), variables)
                    self.assertEqual(max(literals), variables)

    def test_distinct_window_encoding_matches_all_small_sequences(self) -> None:
        n = 2
        length = 4
        auxiliary_count, clauses = distinct_cyclic_windows_encoding(
            n=n,
            length=length,
            base_variables=length,
        )
        self.assertEqual(auxiliary_count, comb(length, 2))
        self.assertEqual(len(clauses), 5 * comb(length, 2))

        for bits in product((0, 1), repeat=length):
            fixed = {
                position + 1: bool(bit)
                for position, bit in enumerate(bits)
            }
            expected = cyclic_window_support_size(bits, n) == length
            self.assertEqual(
                formula_is_satisfiable(
                    [list(clause) for clause in clauses],
                    fixed,
                ),
                expected,
                bits,
            )

    def test_distinct_support_balance_is_valid_for_full_support(self) -> None:
        n = 2
        length = 4
        total_words = 1 << n
        clauses = distinct_support_balance_clauses(
            length=length,
            total_words=total_words,
        )

        for bits in product((0, 1), repeat=length):
            if cyclic_window_support_size(bits, n) != length:
                continue
            present_words = {
                sum(
                    bits[(start + offset) % length]
                    << (n - 1 - offset)
                    for offset in range(n)
                )
                for start in range(length)
            }
            fixed = {
                length + length * total_words + word + 1:
                word in present_words
                for word in range(total_words)
            }
            self.assertTrue(
                formula_is_satisfiable(
                    [list(clause) for clause in clauses],
                    fixed,
                ),
                bits,
            )

    def test_exact_cardinality_matches_all_small_assignments(self) -> None:
        for size in range(1, 8):
            literals = list(range(1, size + 1))
            for target in range(size + 1):
                with self.subTest(size=size, target=target):
                    auxiliary_count, clauses = exact_cardinality_encoding(
                        literals,
                        target,
                        base_variables=size,
                    )
                    maximum_variable = max(
                        abs(literal)
                        for clause in clauses
                        for literal in clause
                    )
                    self.assertEqual(
                        maximum_variable,
                        size + auxiliary_count,
                    )
                    for bits in product((0, 1), repeat=size):
                        fixed = {
                            position + 1: bool(bit)
                            for position, bit in enumerate(bits)
                        }
                        self.assertEqual(
                            formula_is_satisfiable(
                                [list(clause) for clause in clauses],
                                fixed,
                            ),
                            sum(bits) == target,
                            (size, target, bits),
                        )

    def test_at_most_cardinality_matches_all_small_assignments(self) -> None:
        for size in range(1, 8):
            literals = list(range(1, size + 1))
            for limit in range(size + 1):
                with self.subTest(size=size, limit=limit):
                    auxiliary_count, clauses = (
                        at_most_cardinality_encoding(
                            literals,
                            limit,
                            base_variables=size,
                        )
                    )
                    if limit == size:
                        self.assertEqual(auxiliary_count, 0)
                        self.assertEqual(clauses, [])
                    else:
                        maximum_variable = max(
                            abs(literal)
                            for clause in clauses
                            for literal in clause
                        )
                        self.assertEqual(
                            maximum_variable,
                            size + auxiliary_count,
                        )
                    for bits in product((0, 1), repeat=size):
                        fixed = {
                            position + 1: bool(bit)
                            for position, bit in enumerate(bits)
                        }
                        self.assertEqual(
                            formula_is_satisfiable(
                                [list(clause) for clause in clauses],
                                fixed,
                            ),
                            sum(bits) <= limit,
                            (size, limit, bits),
                        )

    def test_tiny_formula_matches_independent_verifier(self) -> None:
        n = 3
        length = 4

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.cnf"
            write_cnf(path, n=n, radius=1, length=length)
            lines = path.read_text(encoding="ascii").splitlines()

        clauses = [
            [int(literal) for literal in line.split()[:-1]]
            for line in lines[1:]
        ]
        projected_models: set[tuple[int, ...]] = set()
        pair_clauses = comb(n, 2)
        for bits in product((0, 1), repeat=length):
            bit_clauses_hold = all(
                any(bits[abs(literal) - 1] == int(literal > 0) for literal in clause)
                for clause in clauses[:2]
            )
            if not bit_clauses_hold:
                continue

            cursor = 2
            formula_has_extension = True
            for _target in range(1 << n):
                cursor += 1
                target_has_window = False
                for _start in range(length):
                    constraints = clauses[cursor : cursor + pair_clauses]
                    cursor += pair_clauses
                    selector_can_be_true = all(
                        any(
                            abs(literal) <= length
                            and bits[abs(literal) - 1] == int(literal > 0)
                            for literal in clause
                        )
                        for clause in constraints
                    )
                    target_has_window |= selector_can_be_true
                if not target_has_window:
                    formula_has_extension = False
                    break

            if formula_has_extension:
                projected_models.add(bits)

        expected_models: set[tuple[int, ...]] = set()
        for bits in product((0, 1), repeat=length):
            if bits[0] != 0 or bits[1] > bits[-1]:
                continue
            report = verify_sequence(list(bits), n=n, radius=1)
            if report.valid:
                expected_models.add(bits)

        self.assertEqual(projected_models, expected_models)
        self.assertNotIn((0, 1, 1, 1), projected_models)

    def test_pattern_formula_matches_independent_verifier(self) -> None:
        n = 2
        length = 4

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.cnf"
            write_pattern_cnf(path, n=n, radius=1, length=length)
            lines = path.read_text(encoding="ascii").splitlines()

        clauses = [
            [int(literal) for literal in line.split()[:-1]]
            for line in lines[1:]
        ]
        for bits in product((0, 1), repeat=length):
            fixed = {
                position + 1: bool(bit)
                for position, bit in enumerate(bits)
            }
            formula_accepts = formula_is_satisfiable(clauses, fixed)
            symmetry_accepts = (
                sum(bits[:n]) <= 1
                and bits[n] <= bits[-1]
            )
            expected = (
                symmetry_accepts
                and verify_sequence(list(bits), n=n, radius=1).valid
            )
            self.assertEqual(formula_accepts, expected, bits)

    def test_anchored_pattern_matches_independent_verifier(self) -> None:
        n = 2
        length = 5
        total_words = 1 << n
        base_clauses = length * total_words * (n + 1) + 2 * total_words

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.cnf"
            for anchor_word in (0, 1, 2):
                anchor_bits = tuple(
                    (anchor_word >> (n - 1 - offset)) & 1
                    for offset in range(n)
                )
                for predecessor, successor in product((0, 1), repeat=2):
                    with self.subTest(
                        anchor_word=anchor_word,
                        predecessor=predecessor,
                        successor=successor,
                    ):
                        _, clause_count = write_pattern_cnf(
                            path,
                            n=n,
                            radius=1,
                            length=length,
                            symmetry=False,
                            anchor_word=anchor_word,
                            anchor_predecessor_bit=predecessor,
                            anchor_successor_bit=successor,
                        )
                        lines = path.read_text(
                            encoding="ascii"
                        ).splitlines()
                        clauses = [
                            [int(literal) for literal in line.split()[:-1]]
                            for line in lines[1:]
                        ]
                        self.assertEqual(
                            clause_count,
                            base_clauses + n + 2,
                        )
                        self.assertEqual(len(clauses), clause_count)

                        for bits in product((0, 1), repeat=length):
                            fixed = {
                                position + 1: bool(bit)
                                for position, bit in enumerate(bits)
                            }
                            formula_accepts = formula_is_satisfiable(
                                clauses,
                                fixed,
                            )
                            expected = (
                                bits[:n] == anchor_bits
                                and bits[-1] == predecessor
                                and bits[n] == successor
                                and verify_sequence(
                                    list(bits),
                                    n=n,
                                    radius=1,
                                ).valid
                            )
                            self.assertEqual(
                                formula_accepts,
                                expected,
                                (
                                    anchor_word,
                                    predecessor,
                                    successor,
                                    bits,
                                ),
                            )

    def test_anchor_partition_covers_every_valid_tiny_sequence(self) -> None:
        n = 2
        length = 5

        for bits in product((0, 1), repeat=length):
            if not verify_sequence(list(bits), n=n, radius=1).valid:
                continue

            cases: set[tuple[int, int, int]] = set()
            for shift in range(length):
                rotated = bits[shift:] + bits[:shift]
                anchor_word = 0
                for bit in rotated[:n]:
                    anchor_word = (anchor_word << 1) | bit
                if bin(anchor_word).count("1") <= 1:
                    cases.add(
                        (
                            anchor_word,
                            rotated[-1],
                            rotated[n],
                        )
                    )

            self.assertTrue(cases, bits)
            self.assertTrue(
                all(case[0] in (0, 1, 2) for case in cases),
                (bits, cases),
            )

    def test_exact_support_projection_matches_every_tiny_sequence(self) -> None:
        n = 2
        length = 5
        maximum_support = min(length, 1 << n)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.cnf"
            for exact_support in range(maximum_support + 1):
                write_pattern_cnf(
                    path,
                    n=n,
                    radius=1,
                    length=length,
                    symmetry=False,
                    exact_support=exact_support,
                )
                lines = path.read_text(encoding="ascii").splitlines()
                clauses = [
                    [int(literal) for literal in line.split()[:-1]]
                    for line in lines[1:]
                ]

                for bits in product((0, 1), repeat=length):
                    fixed = {
                        position + 1: bool(bit)
                        for position, bit in enumerate(bits)
                    }
                    formula_accepts = formula_is_satisfiable(clauses, fixed)
                    expected = (
                        cyclic_window_support_size(bits, n) == exact_support
                        and verify_sequence(
                            list(bits),
                            n=n,
                            radius=1,
                        ).valid
                    )
                    self.assertEqual(
                        formula_accepts,
                        expected,
                        (exact_support, bits),
                    )

    def test_exact_support_combines_with_hamming_distance(self) -> None:
        n = 2
        length = 4
        seed = [1, 1, 0, 0]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.cnf"
            for max_distance in (0, 2, 3):
                for exact_support in range(length + 1):
                    with self.subTest(
                        max_distance=max_distance,
                        exact_support=exact_support,
                    ):
                        write_pattern_cnf(
                            path,
                            n=n,
                            radius=1,
                            length=length,
                            symmetry=False,
                            seed_bits=seed,
                            max_distance=max_distance,
                            exact_support=exact_support,
                        )
                        lines = path.read_text(
                            encoding="ascii"
                        ).splitlines()
                        variables = int(lines[0].split()[2])
                        clauses = [
                            [int(literal) for literal in line.split()[:-1]]
                            for line in lines[1:]
                        ]
                        self.assertLessEqual(
                            max(
                                abs(literal)
                                for clause in clauses
                                for literal in clause
                            ),
                            variables,
                        )

                        for bits in product((0, 1), repeat=length):
                            fixed = {
                                position + 1: bool(bit)
                                for position, bit in enumerate(bits)
                            }
                            formula_accepts = formula_is_satisfiable(
                                clauses,
                                fixed,
                            )
                            expected = (
                                sum(
                                    left != right
                                    for left, right in zip(bits, seed)
                                )
                                <= max_distance
                                and cyclic_window_support_size(bits, n)
                                == exact_support
                                and verify_sequence(
                                    list(bits),
                                    n=n,
                                    radius=1,
                                ).valid
                            )
                            self.assertEqual(
                                formula_accepts,
                                expected,
                                (
                                    max_distance,
                                    exact_support,
                                    bits,
                                ),
                            )

    def test_pattern_symmetry_has_a_representative_in_each_valid_orbit(self) -> None:
        n = 2
        length = 4
        for bits in product((0, 1), repeat=length):
            if not verify_sequence(list(bits), n=n, radius=1).valid:
                continue

            representatives: list[tuple[int, ...]] = []
            for shift in range(length):
                rotated = bits[shift:] + bits[:shift]
                reflected = tuple(
                    rotated[(n - 1 - index) % length]
                    for index in range(length)
                )
                representatives.extend((rotated, reflected))

            self.assertTrue(
                any(
                    sum(candidate[:n]) <= 1
                    and candidate[n] <= candidate[-1]
                    for candidate in representatives
                ),
                bits,
            )

    def test_pattern_neighborhood_matches_hamming_bound(self) -> None:
        n = 2
        length = 4
        seed = [1, 1, 0, 0]
        total_words = 1 << n
        base_variables = length + length * total_words + total_words
        base_clauses = length * total_words * (n + 1) + 2 * total_words

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.cnf"
            for max_distance in range(length):
                variables, clauses_count = write_pattern_cnf(
                    path,
                    n=n,
                    radius=1,
                    length=length,
                    symmetry=False,
                    seed_bits=seed,
                    max_distance=max_distance,
                )
                lines = path.read_text(encoding="ascii").splitlines()
                counter_width = max_distance + 1
                self.assertEqual(
                    variables,
                    base_variables + length * counter_width,
                )
                self.assertEqual(
                    clauses_count,
                    base_clauses
                    + 2
                    + 2 * counter_width * (length - 1),
                )
                clauses = [
                    [int(literal) for literal in line.split()[:-1]]
                    for line in lines[1:]
                ]
                for bits in product((0, 1), repeat=length):
                    fixed = {
                        position + 1: bool(bit)
                        for position, bit in enumerate(bits)
                    }
                    formula_accepts = formula_is_satisfiable(clauses, fixed)
                    distance = sum(
                        left != right for left, right in zip(bits, seed)
                    )
                    expected = (
                        distance <= max_distance
                        and verify_sequence(
                            list(bits),
                            n=n,
                            radius=1,
                        ).valid
                    )
                    self.assertEqual(
                        formula_accepts,
                        expected,
                        (max_distance, bits),
                    )

    def test_pattern_neighborhood_rejects_symmetry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.cnf"
            with self.assertRaisesRegex(ValueError, "symmetry=False"):
                write_pattern_cnf(
                    path,
                    n=2,
                    radius=1,
                    length=4,
                    seed_bits=[1, 1, 0, 0],
                    max_distance=0,
                )

    def test_pattern_distance_at_least_length_adds_no_counter(self) -> None:
        n = 2
        length = 4
        total_words = 1 << n
        base_variables = length + length * total_words + total_words
        base_clauses = length * total_words * (n + 1) + 2 * total_words

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.cnf"
            variables, clauses = write_pattern_cnf(
                path,
                n=n,
                radius=1,
                length=length,
                symmetry=False,
                seed_bits=[1, 0, 1, 0],
                max_distance=length,
            )

        self.assertEqual(variables, base_variables)
        self.assertEqual(clauses, base_clauses)

    def test_invalid_exact_support_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.cnf"
            for exact_support in (-1, 5):
                with self.subTest(exact_support=exact_support):
                    with self.assertRaisesRegex(ValueError, "exact support"):
                        write_pattern_cnf(
                            path,
                            n=2,
                            radius=1,
                            length=4,
                            exact_support=exact_support,
                        )

    def test_invalid_anchor_options_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.cnf"
            invalid_arguments = (
                {"anchor_word": -1, "symmetry": False},
                {"anchor_word": 4, "symmetry": False},
                {"anchor_word": 3, "symmetry": False},
                {"anchor_word": 0},
                {
                    "anchor_word": 0,
                    "anchor_predecessor_bit": 2,
                    "symmetry": False,
                },
                {"anchor_predecessor_bit": 0, "symmetry": False},
            )
            for arguments in invalid_arguments:
                with self.subTest(arguments=arguments):
                    with self.assertRaises(ValueError):
                        write_pattern_cnf(
                            path,
                            n=2,
                            radius=1,
                            length=5,
                            **arguments,
                        )

    def test_exact_support_cli_option_is_pattern_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.cnf"
            selector_argv = [
                "generate_cnf.py",
                str(path),
                "--n",
                "2",
                "--radius",
                "1",
                "--length",
                "4",
                "--exact-support",
                "2",
            ]
            with (
                patch("sys.argv", selector_argv),
                redirect_stderr(StringIO()),
                self.assertRaises(SystemExit) as raised,
            ):
                generate_cnf_main()
            self.assertEqual(raised.exception.code, 2)
            self.assertFalse(path.exists())

            pattern_argv = [
                *selector_argv,
                "--encoding",
                "pattern",
                "--no-symmetry",
            ]
            output = StringIO()
            with patch("sys.argv", pattern_argv), redirect_stdout(output):
                self.assertEqual(generate_cnf_main(), 0)
            self.assertTrue(path.exists())
            self.assertIn("using the pattern encoding", output.getvalue())

    def test_anchor_cli_options_require_pattern_and_no_symmetry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.cnf"
            base_argv = [
                "generate_cnf.py",
                str(path),
                "--n",
                "2",
                "--radius",
                "1",
                "--length",
                "5",
                "--anchor-word",
                "0b01",
                "--anchor-predecessor-bit",
                "1",
                "--anchor-successor-bit",
                "0",
            ]
            for extra_arguments in ([], ["--encoding", "pattern"]):
                with (
                    self.subTest(extra_arguments=extra_arguments),
                    patch("sys.argv", [*base_argv, *extra_arguments]),
                    redirect_stderr(StringIO()),
                    self.assertRaises(SystemExit) as raised,
                ):
                    generate_cnf_main()
                self.assertEqual(raised.exception.code, 2)
                self.assertFalse(path.exists())

            argv = [
                *base_argv,
                "--encoding",
                "pattern",
                "--no-symmetry",
            ]
            output = StringIO()
            with patch("sys.argv", argv), redirect_stdout(output):
                self.assertEqual(generate_cnf_main(), 0)
            self.assertTrue(path.exists())
            self.assertIn("using the pattern encoding", output.getvalue())


if __name__ == "__main__":
    unittest.main()
