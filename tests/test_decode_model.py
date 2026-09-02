from __future__ import annotations

import unittest

from tools.decode_model import parse_dimacs_model


class DecodeModelTests(unittest.TestCase):
    def test_parses_sequence_prefix_and_ignores_auxiliary_variables(self) -> None:
        model = "\n".join(
            [
                "s SATISFIABLE",
                "v -1 2 -3 4 5 -6 0",
            ]
        )
        self.assertEqual(parse_dimacs_model(model, 4), [0, 1, 0, 1])

    def test_rejects_non_sat_status(self) -> None:
        with self.assertRaisesRegex(ValueError, "UNKNOWN"):
            parse_dimacs_model("s UNKNOWN\n", 2)

    def test_rejects_missing_sequence_variable(self) -> None:
        with self.assertRaisesRegex(ValueError, "omits sequence variables"):
            parse_dimacs_model("s SATISFIABLE\nv 1 0\n", 2)

    def test_rejects_contradictory_assignment(self) -> None:
        with self.assertRaisesRegex(ValueError, "contradictory"):
            parse_dimacs_model("s SATISFIABLE\nv 1 -1 2 0\n", 2)


if __name__ == "__main__":
    unittest.main()
