from __future__ import annotations

import unittest
from pathlib import Path

from tools.covering import parse_sequence_text, verify_sequence


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "data" / "baseline" / "l9-r1-71.txt"
INCOMPLETE_SIX = ROOT / "data" / "candidates" / "l9-r1-70-uncovered-6.txt"


class CoveringVerifierTests(unittest.TestCase):
    def test_published_baseline_is_valid(self) -> None:
        bits = parse_sequence_text(BASELINE.read_text(encoding="ascii"))
        report = verify_sequence(bits, n=9, radius=1, expected_length=71)
        self.assertTrue(report.valid)
        self.assertEqual(report.covered_words, 512)
        self.assertEqual(report.length, 71)

    def test_wrong_expected_length_is_rejected(self) -> None:
        bits = parse_sequence_text(BASELINE.read_text(encoding="ascii"))
        report = verify_sequence(bits, n=9, radius=1, expected_length=70)
        self.assertFalse(report.valid)

    def test_retained_incomplete_seed_has_six_expected_gaps(self) -> None:
        bits = parse_sequence_text(INCOMPLETE_SIX.read_text(encoding="ascii"))
        report = verify_sequence(bits, n=9, radius=1, expected_length=70)
        self.assertFalse(report.valid)
        self.assertEqual(report.covered_words, 506)
        self.assertEqual(report.distinct_windows, 70)
        self.assertEqual(
            report.uncovered_words,
            (30, 60, 61, 156, 206, 286),
        )

    def test_each_single_deletion_is_invalid(self) -> None:
        bits = parse_sequence_text(BASELINE.read_text(encoding="ascii"))
        best_uncovered = 512
        for deleted in range(len(bits)):
            candidate = bits[:deleted] + bits[deleted + 1 :]
            report = verify_sequence(candidate, n=9, radius=1, expected_length=70)
            self.assertFalse(report.valid)
            best_uncovered = min(best_uncovered, len(report.uncovered_words))
        self.assertEqual(best_uncovered, 13)

    def test_each_single_bit_mutation_is_invalid(self) -> None:
        bits = parse_sequence_text(BASELINE.read_text(encoding="ascii"))
        for position in range(len(bits)):
            candidate = bits.copy()
            candidate[position] ^= 1
            report = verify_sequence(candidate, n=9, radius=1, expected_length=71)
            self.assertFalse(report.valid, f"mutation at position {position} passed")

    def test_parser_accepts_compact_and_spaced_forms(self) -> None:
        self.assertEqual(parse_sequence_text("0101"), [0, 1, 0, 1])
        self.assertEqual(parse_sequence_text("0 1 0 1\n"), [0, 1, 0, 1])

    def test_parser_rejects_nonbinary_input(self) -> None:
        with self.assertRaises(ValueError):
            parse_sequence_text("0 1 2")


if __name__ == "__main__":
    unittest.main()
