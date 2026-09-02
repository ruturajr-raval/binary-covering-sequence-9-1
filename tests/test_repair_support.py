from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from tools.covering import cyclic_windows, load_sequence
from tools.repair_support import (
    analyze_support,
    file_digest,
    load_support_certificate,
    main,
    solve_support_repair,
    support_digest,
)


ORTOOLS_AVAILABLE = importlib.util.find_spec("ortools") is not None
ROOT = Path(__file__).resolve().parents[1]


class RepairSupportHelperTests(unittest.TestCase):
    def test_loads_list_and_object_certificates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            list_path = root / "list.json"
            object_path = root / "object.json"
            list_path.write_text("[2, 0, 1]\n", encoding="ascii")
            object_path.write_text(
                json.dumps({"selected_edges": [3, 1]}) + "\n",
                encoding="ascii",
            )
            self.assertEqual(
                load_support_certificate(list_path, n=2),
                [0, 1, 2],
            )
            self.assertEqual(
                load_support_certificate(object_path, n=2),
                [1, 3],
            )

    def test_rejects_duplicate_and_out_of_range_edges(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "support.json"
            path.write_text("[0, 0]\n", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_support_certificate(path, n=2)
            path.write_text("[4]\n", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "out-of-range"):
                load_support_certificate(path, n=2)

    def test_digest_is_order_independent(self) -> None:
        self.assertEqual(support_digest([2, 0, 1]), support_digest([1, 2, 0]))

    def test_analyzes_connected_and_disconnected_supports(self) -> None:
        connected = analyze_support([0, 1, 2], n=2, radius=1)
        self.assertTrue(connected["balanced"])
        self.assertEqual(connected["covered_words"], 4)
        self.assertEqual(connected["component_edge_counts"], [3])

        disconnected = analyze_support([0, 3], n=2, radius=1)
        self.assertTrue(disconnected["balanced"])
        self.assertEqual(disconnected["covered_words"], 4)
        self.assertEqual(disconnected["component_edge_counts"], [1, 1])

    def test_common_backbone_certificate_matches_sources(self) -> None:
        certificate_path = (
            ROOT / "data/candidates/l9-r1-common-backbone-64.json"
        )
        payload = json.loads(certificate_path.read_text(encoding="ascii"))
        common = load_support_certificate(certificate_path, n=9)

        bits = load_sequence(ROOT / "data/baseline/l9-r1-71.txt")
        baseline_support = {
            sum(
                bits[(start + offset) % len(bits)]
                << (8 - offset)
                for offset in range(9)
            )
            for start in range(len(bits))
        }
        disconnected_payload = json.loads(
            (
                ROOT
                / "evidence/graph-repair70/anchor-0-seed-1.json"
            ).read_text(encoding="ascii")
        )
        disconnected_support = set(
            disconnected_payload["selected_edges"]
        )
        self.assertEqual(set(common), baseline_support & disconnected_support)
        self.assertEqual(len(common), 64)
        self.assertEqual(
            support_digest(common),
            payload["support_sha256"],
        )
        baseline_source, disconnected_source = payload["source_supports"]
        self.assertEqual(
            file_digest(ROOT / baseline_source["file"]),
            baseline_source["file_sha256"],
        )
        self.assertEqual(
            support_digest(sorted(baseline_support)),
            baseline_source["support_sha256"],
        )
        self.assertEqual(
            file_digest(ROOT / disconnected_source["file"]),
            disconnected_source["file_sha256"],
        )
        self.assertEqual(
            support_digest(sorted(disconnected_support)),
            disconnected_source["support_sha256"],
        )


@unittest.skipUnless(ORTOOLS_AVAILABLE, "OR-Tools is not installed")
class RepairSupportSolverTests(unittest.TestCase):
    def test_programmatic_api_rejects_invalid_support(self) -> None:
        common = {
            "n": 2,
            "radius": 1,
            "length": 2,
            "anchor_edge": 0,
            "partition_anchor": True,
            "connectivity_mode": "tree",
            "minimum_overlap": 2,
            "maximize_overlap": False,
            "time_limit": 5,
            "deterministic_limit": None,
            "workers": 1,
            "seed": 1,
            "log_progress": False,
        }
        with self.assertRaisesRegex(ValueError, "duplicate"):
            solve_support_repair(support=[0, 0], **common)
        with self.assertRaisesRegex(ValueError, "out-of-range"):
            solve_support_repair(support=[0, 4], **common)
        with self.assertRaisesRegex(ValueError, "exclusive"):
            solve_support_repair(
                support=[0, 1],
                exact_overlap=1,
                **common,
            )

    def test_cli_creates_output_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            support_path = root / "support.json"
            result_path = root / "results" / "repair.json"
            sequence_path = root / "sequences" / "repair.txt"
            support_path.write_text("[0, 1, 2]\n", encoding="ascii")
            argv = [
                "repair_support.py",
                str(support_path),
                str(result_path),
                "--sequence-output",
                str(sequence_path),
                "--n",
                "2",
                "--radius",
                "1",
                "--length",
                "3",
                "--anchor-edge",
                "0",
                "--partition-anchor",
                "--connectivity",
                "tree",
                "--minimum-overlap",
                "3",
                "--time-limit",
                "5",
                "--workers",
                "1",
                "--seed",
                "1",
            ]
            with patch("sys.argv", argv), redirect_stdout(StringIO()):
                self.assertEqual(main(), 0)
            self.assertTrue(result_path.is_file())
            self.assertTrue(sequence_path.is_file())
            result = json.loads(result_path.read_text(encoding="ascii"))
            self.assertTrue(result["valid"])
            self.assertEqual(result["sequence_output"], str(sequence_path))

    def test_recovers_connected_support_at_full_overlap(self) -> None:
        summary, bits = solve_support_repair(
            support=[0, 1, 2],
            n=2,
            radius=1,
            length=3,
            anchor_edge=0,
            partition_anchor=True,
            connectivity_mode="tree",
            minimum_overlap=3,
            maximize_overlap=False,
            time_limit=5,
            deterministic_limit=None,
            workers=1,
            seed=1,
            log_progress=False,
        )
        self.assertIn(summary["status"], {"OPTIMAL", "FEASIBLE"})
        self.assertIsNotNone(bits)
        self.assertEqual(summary["overlap"], 3)
        self.assertEqual(summary["replacements"], 0)

    def test_excludes_disconnected_full_overlap_support(self) -> None:
        summary, bits = solve_support_repair(
            support=[0, 3],
            n=2,
            radius=1,
            length=2,
            anchor_edge=0,
            partition_anchor=True,
            connectivity_mode="tree",
            minimum_overlap=2,
            maximize_overlap=False,
            time_limit=5,
            deterministic_limit=None,
            workers=1,
            seed=1,
            log_progress=False,
        )
        self.assertEqual(summary["status"], "INFEASIBLE")
        self.assertIsNone(bits)
        self.assertEqual(
            summary["required_reference_omissions_at_least"],
            1,
        )
        self.assertEqual(summary["required_replacements_at_least"], 1)

    def test_partial_reference_exclusion_uses_omission_language(self) -> None:
        summary, bits = solve_support_repair(
            support=[3],
            n=2,
            radius=1,
            length=2,
            anchor_edge=0,
            partition_anchor=True,
            connectivity_mode="tree",
            minimum_overlap=1,
            maximize_overlap=False,
            time_limit=5,
            deterministic_limit=None,
            workers=1,
            seed=1,
            log_progress=False,
        )
        self.assertEqual(summary["status"], "INFEASIBLE")
        self.assertIsNone(bits)
        self.assertEqual(
            summary["required_reference_omissions_at_least"],
            1,
        )
        self.assertNotIn("required_replacements_at_least", summary)

    def test_accepts_a_shorter_reference_backbone(self) -> None:
        summary, bits = solve_support_repair(
            support=[0, 1],
            n=2,
            radius=1,
            length=4,
            anchor_edge=0,
            partition_anchor=False,
            connectivity_mode="tree",
            minimum_overlap=None,
            maximize_overlap=False,
            time_limit=5,
            deterministic_limit=None,
            workers=1,
            seed=1,
            log_progress=False,
            exact_overlap=2,
        )
        self.assertIn(summary["status"], {"OPTIMAL", "FEASIBLE"})
        self.assertIsNotNone(bits)
        self.assertEqual(summary["base_support_size"], 2)
        self.assertEqual(summary["overlap"], 2)
        self.assertEqual(summary["reference_edges_omitted"], 0)
        self.assertEqual(summary["selected_outside_reference"], 2)
        self.assertNotIn("replacements", summary)

    def test_repeated_window_mode_reports_distinct_overlap(self) -> None:
        summary, bits = solve_support_repair(
            support=[0, 1],
            n=2,
            radius=1,
            length=4,
            anchor_edge=0,
            partition_anchor=False,
            connectivity_mode="tree",
            minimum_overlap=None,
            maximize_overlap=False,
            time_limit=5,
            deterministic_limit=None,
            workers=1,
            seed=1,
            log_progress=False,
            exact_overlap=2,
            distinct_windows=False,
            support_size=3,
            duplicate_edge=0,
            duplicate_kind="loop",
            duplicate_scope="reference",
        )
        self.assertIn(summary["status"], {"OPTIMAL", "FEASIBLE"})
        self.assertIsNotNone(bits)
        self.assertFalse(summary["distinct_windows"])
        self.assertTrue(summary["repeated_windows_allowed"])
        self.assertEqual(summary["candidate_support_size"], 3)
        self.assertEqual(summary["duplicate_edge"], 0)
        self.assertEqual(summary["duplicate_kind"], "loop")
        self.assertEqual(summary["duplicate_scope"], "reference")
        self.assertEqual(len(set(cyclic_windows(bits, 2))), 3)
        self.assertEqual(summary["overlap"], 2)
        self.assertEqual(summary["reference_edges_omitted"], 0)
        self.assertGreaterEqual(summary["reference_edge_occurrences"], 2)
        self.assertEqual(
            summary["reference_edge_occurrences"]
            + summary["outside_reference_occurrences"],
            4,
        )


if __name__ == "__main__":
    unittest.main()
