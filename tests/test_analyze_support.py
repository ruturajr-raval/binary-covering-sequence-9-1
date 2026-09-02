from __future__ import annotations

import unittest

from tools.analyze_support import (
    analyze_cross_joins,
    directed_cycle_lengths,
)


class AnalyzeSupportTests(unittest.TestCase):
    def test_two_loops_have_one_valid_cross_join(self) -> None:
        result = analyze_cross_joins([0, 3], n=2, radius=1)
        self.assertEqual(result["cycle_lengths_before"], [1, 1])
        self.assertEqual(result["cross_join_candidate_count"], 1)
        self.assertEqual(result["valid_cross_join_count"], 1)
        self.assertEqual(
            result["candidates"][0]["cycle_lengths_after"],
            [2],
        )
        self.assertEqual(result["candidates"][0]["uncovered_words"], [])

    def test_rejects_non_cycle_cover(self) -> None:
        with self.assertRaisesRegex(ValueError, "cycle cover"):
            directed_cycle_lengths({0, 1}, n=2)


if __name__ == "__main__":
    unittest.main()
