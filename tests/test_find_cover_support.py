from __future__ import annotations

import importlib.util
import unittest
from unittest.mock import patch

from tools.find_cover_support import find_cover_support
from tools.flow_cp_sat import build_flow_model, load_cp_model


ORTOOLS_AVAILABLE = importlib.util.find_spec("ortools") is not None


@unittest.skipUnless(ORTOOLS_AVAILABLE, "OR-Tools is not installed")
class FindCoverSupportTests(unittest.TestCase):
    def test_finds_a_balanced_tiny_cover(self) -> None:
        with patch(
            "tools.find_cover_support.build_flow_model",
            wraps=build_flow_model,
        ) as builder:
            result = find_cover_support(
                n=2,
                radius=1,
                length=2,
                anchor_edge=0,
                partition_anchor=True,
                hint_bits=None,
                time_limit=5,
                workers=1,
                seed=1,
                log_progress=False,
            )
        self.assertIn(result["status"], {"OPTIMAL", "FEASIBLE"})
        self.assertEqual(len(result["selected_edges"]), 2)
        self.assertTrue(result["support_report"]["balanced"])
        self.assertEqual(result["support_report"]["covered_words"], 4)
        self.assertFalse(
            result["autocorrelation_orbit_constraints_enabled"]
        )
        self.assertEqual(result["autocorrelation_orbit_bounds"], {})
        self.assertFalse(
            builder.call_args.kwargs[
                "add_autocorrelation_orbit_constraints"
            ]
        )

    def test_disconnected_support_requires_orbit_bounds_disabled(self) -> None:
        cp_model = load_cp_model()
        selected = {0, 1, 3, 5, 7, 8, 10, 12, 14}
        statuses = {}
        for enabled in (False, True):
            artifacts = build_flow_model(
                n=4,
                radius=1,
                length=9,
                anchor_edge=0,
                distinct_windows=True,
                connectivity_mode="none",
                add_autocorrelation_orbit_constraints=enabled,
            )
            for word in range(1 << 4):
                artifacts.model.add(
                    artifacts.count[word] == int(word in selected)
                )
            solver = cp_model.CpSolver()
            statuses[enabled] = solver.solve(artifacts.model)

        self.assertIn(
            statuses[False],
            {cp_model.OPTIMAL, cp_model.FEASIBLE},
        )
        self.assertEqual(statuses[True], cp_model.INFEASIBLE)

    def test_enforces_maximum_active_vertices(self) -> None:
        infeasible = find_cover_support(
            n=4,
            radius=1,
            length=6,
            anchor_edge=0,
            partition_anchor=True,
            hint_bits=None,
            time_limit=5,
            workers=1,
            seed=1,
            log_progress=False,
            maximum_active_vertices=4,
        )
        self.assertEqual(infeasible["status"], "INFEASIBLE")

        result = find_cover_support(
            n=4,
            radius=1,
            length=6,
            anchor_edge=0,
            partition_anchor=True,
            hint_bits=None,
            time_limit=5,
            workers=1,
            seed=1,
            log_progress=False,
            maximum_active_vertices=5,
        )
        self.assertIn(result["status"], {"OPTIMAL", "FEASIBLE"})
        self.assertLessEqual(result["active_vertex_count"], 5)
        self.assertEqual(result["maximum_active_vertices"], 5)

    def test_minimizes_active_vertices_with_optional_bound(self) -> None:
        result = find_cover_support(
            n=4,
            radius=1,
            length=6,
            anchor_edge=0,
            partition_anchor=True,
            hint_bits=None,
            time_limit=5,
            workers=1,
            seed=1,
            log_progress=False,
            maximum_active_vertices=6,
            minimize_active_vertices=True,
        )
        self.assertEqual(result["status"], "OPTIMAL")
        self.assertEqual(result["active_vertex_count"], 5)
        self.assertEqual(result["objective"], "minimize_active_vertices")
        self.assertEqual(result["objective_value"], 5)
        self.assertEqual(result["best_objective_bound"], 5)

    def test_rejects_invalid_maximum_active_vertices(self) -> None:
        for maximum in (0, 5):
            with self.subTest(maximum=maximum):
                with self.assertRaises(ValueError):
                    find_cover_support(
                        n=3,
                        radius=1,
                        length=3,
                        anchor_edge=0,
                        partition_anchor=True,
                        hint_bits=None,
                        time_limit=5,
                        workers=1,
                        seed=1,
                        log_progress=False,
                        maximum_active_vertices=maximum,
                    )


if __name__ == "__main__":
    unittest.main()
