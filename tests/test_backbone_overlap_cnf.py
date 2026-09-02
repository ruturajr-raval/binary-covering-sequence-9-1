from __future__ import annotations

from itertools import product
from pathlib import Path
import tempfile
import unittest

from tests.test_cnf import formula_is_satisfiable
from tools.generate_backbone_overlap_cnf import (
    write_backbone_overlap_cnf,
)


def cyclic_support(bits: tuple[int, ...], n: int) -> set[int]:
    return {
        sum(
            bits[(start + offset) % len(bits)] << (n - 1 - offset)
            for offset in range(n)
        )
        for start in range(len(bits))
    }


class BackboneOverlapCnfTests(unittest.TestCase):
    def test_tiny_formula_matches_direct_overlap(self) -> None:
        n = 2
        length = 4
        support = [0, 1, 2, 3]
        minimum_overlap = 3

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overlap.cnf"
            write_backbone_overlap_cnf(
                path,
                support=support,
                n=n,
                length=length,
                minimum_overlap=minimum_overlap,
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
            expected = (
                len(cyclic_support(bits, n) & set(support))
                >= minimum_overlap
            )
            self.assertEqual(
                formula_is_satisfiable(clauses, fixed),
                expected,
                bits,
            )

    def test_header_and_literal_bounds_match(self) -> None:
        n = 3
        length = 5
        support = [0, 1, 3, 6]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overlap.cnf"
            variables, clauses = write_backbone_overlap_cnf(
                path,
                support=support,
                n=n,
                length=length,
                minimum_overlap=2,
            )
            lines = path.read_text(encoding="ascii").splitlines()

        self.assertEqual(lines[0], f"p cnf {variables} {clauses}")
        self.assertEqual(len(lines) - 1, clauses)
        literals = [
            abs(int(literal))
            for line in lines[1:]
            for literal in line.split()[:-1]
        ]
        self.assertEqual(max(literals), variables)

    def test_anchor_word_fixes_the_first_window(self) -> None:
        n = 2
        length = 4
        support = [0, 1, 2, 3]
        anchor_word = 1

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "anchored.cnf"
            write_backbone_overlap_cnf(
                path,
                support=support,
                n=n,
                length=length,
                minimum_overlap=3,
                anchor_word=anchor_word,
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
            expected = (
                bits[:n] == (0, 1)
                and len(cyclic_support(bits, n) & set(support)) >= 3
            )
            self.assertEqual(
                formula_is_satisfiable(clauses, fixed),
                expected,
                bits,
            )

    def test_invalid_support_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overlap.cnf"
            with self.assertRaisesRegex(ValueError, "distinct edges"):
                write_backbone_overlap_cnf(
                    path,
                    support=[0, 0],
                    n=2,
                    length=4,
                    minimum_overlap=1,
                )

    def test_invalid_anchor_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overlap.cnf"
            with self.assertRaisesRegex(ValueError, "anchor word"):
                write_backbone_overlap_cnf(
                    path,
                    support=[0, 1],
                    n=2,
                    length=4,
                    minimum_overlap=1,
                    anchor_word=4,
                )


if __name__ == "__main__":
    unittest.main()
