from __future__ import annotations

from itertools import product
import unittest

from tools.covering import verify_sequence
from tools.run_cadical_portfolio import canonical_zero_anchor_cases
from tools.run_cadical_portfolio import reverse_word, sequence_support_size


def reflect_around_first_window(
    bits: tuple[int, ...],
    n: int,
) -> tuple[int, ...]:
    return tuple(
        bits[(n - 1 - index) % len(bits)]
        for index in range(len(bits))
    )


class CadicalPortfolioTests(unittest.TestCase):
    def test_reverse_word(self) -> None:
        self.assertEqual(reverse_word(0b00101, 5), 0b10100)
        self.assertEqual(reverse_word(0, 9), 0)
        self.assertEqual(reverse_word(16, 9), 16)
        self.assertEqual(reverse_word(1, 9), 256)

    def test_order_nine_has_22_canonical_cases(self) -> None:
        cases = canonical_zero_anchor_cases(9)
        self.assertEqual(len(cases), 22)
        self.assertEqual(
            {case[0] for case in cases},
            {0, 1, 2, 4, 8, 16},
        )
        self.assertEqual(
            {
                (predecessor, successor)
                for anchor, predecessor, successor in cases
                if anchor in (0, 16)
            },
            {(0, 0), (1, 0), (1, 1)},
        )

    def test_order_nine_cases_are_exact_reflection_orbit_leaders(self) -> None:
        n = 9
        raw = {
            (word, predecessor, successor)
            for word in (0, *(1 << bit for bit in range(n)))
            for predecessor in (0, 1)
            for successor in (0, 1)
        }
        self.assertEqual(len(raw), 40)

        orbits = {
            frozenset(
                {
                    case,
                    (
                        reverse_word(case[0], n),
                        case[2],
                        case[1],
                    ),
                }
            )
            for case in raw
        }
        representatives = set(canonical_zero_anchor_cases(n))
        self.assertEqual(len(orbits), 22)
        for orbit in orbits:
            self.assertEqual(len(orbit & representatives), 1)

    def test_reduced_cases_cover_every_valid_tiny_orbit(self) -> None:
        n = 2
        length = 5
        cases = set(canonical_zero_anchor_cases(n))

        for original in product((0, 1), repeat=length):
            if not verify_sequence(list(original), n=n, radius=1).valid:
                continue

            complement = tuple(1 - bit for bit in original)
            candidate = (
                original
                if sum(original) <= length // 2
                else complement
            )
            representatives: list[tuple[int, ...]] = []
            for shift in range(length):
                rotated = candidate[shift:] + candidate[:shift]
                representatives.extend(
                    (rotated, reflect_around_first_window(rotated, n))
                )

            self.assertTrue(
                any(
                    (
                        int("".join(str(bit) for bit in bits[:n]), 2),
                        bits[-1],
                        bits[n],
                    )
                    in cases
                    for bits in representatives
                ),
                original,
            )

    def test_support_size_counts_distinct_cyclic_windows(self) -> None:
        self.assertEqual(sequence_support_size([0, 0, 0, 0], 2), 1)
        self.assertEqual(sequence_support_size([0, 0, 1, 1], 2), 4)


if __name__ == "__main__":
    unittest.main()
