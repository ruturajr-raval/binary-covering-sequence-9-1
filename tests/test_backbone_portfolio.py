from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

from tools.repair_support import support_digest
from tools.run_backbone_portfolio import run_case, zero_ball_anchors


ORTOOLS_AVAILABLE = importlib.util.find_spec("ortools") is not None
ROOT = Path(__file__).resolve().parents[1]
RETAINED = ROOT / "evidence/common-backbone-cover61-20260902"
REPEATED = (
    ROOT / "evidence/common-backbone-cover61-repeated-20260902"
)
SUPPORT69 = (
    ROOT / "evidence/common-backbone-cover61-support69-20260902"
)
SUPPORT_STAGES = (
    ROOT / "evidence/common-backbone-cover61-support-stages-20260902"
)
SUPPORT69_PARTITIONS = (
    ROOT
    / "evidence/common-backbone-cover61-support69-partitions-20260902"
)


class BackbonePortfolioTests(unittest.TestCase):
    def test_order_nine_zero_ball_anchors(self) -> None:
        self.assertEqual(
            zero_ball_anchors(9),
            [0, 1, 2, 4, 8, 16, 32, 64, 128, 256],
        )

    def test_invalid_order_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            zero_ball_anchors(0)

    def test_non_radius_one_partition_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "radius 1"):
            zero_ball_anchors(3, radius=2)

    def test_failed_child_cannot_reuse_stale_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            support_path = root / "support.json"
            support_path.write_text("[0, 1, 2]\n", encoding="ascii")
            script = root / "fail.py"
            script.write_text(
                "raise SystemExit(2)\n",
                encoding="ascii",
            )
            stale_result = root / "anchor-000.json"
            stale_result.write_text(
                json.dumps({"status": "OPTIMAL", "valid": True}) + "\n",
                encoding="ascii",
            )
            (root / "anchor-000.sequence.txt").write_text(
                "0 0 1\n",
                encoding="ascii",
            )

            record = run_case(
                python=Path(sys.executable),
                repair_script=script,
                support=support_path,
                support_edges=frozenset({0, 1, 2}),
                support_sha256=support_digest([0, 1, 2]),
                output_dir=root,
                n=2,
                radius=1,
                length=3,
                exact_overlap=3,
                connectivity="tree",
                time_limit=5,
                deterministic_limit=None,
                solver_workers=1,
                seed=1,
                anchor=0,
                distinct_windows=True,
            )
            self.assertEqual(record["status"], "ERROR")
            self.assertIn("unexpected code 2", record["error"])
            self.assertFalse(stale_result.exists())
            self.assertFalse((root / "anchor-000.sequence.txt").exists())

    def test_malformed_child_result_is_reported_as_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            support_path = root / "support.json"
            support_path.write_text("[0, 1, 2]\n", encoding="ascii")
            script = root / "malformed.py"
            script.write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "Path(sys.argv[2]).write_text('{', encoding='ascii')\n",
                encoding="ascii",
            )

            record = run_case(
                python=Path(sys.executable),
                repair_script=script,
                support=support_path,
                support_edges=frozenset({0, 1, 2}),
                support_sha256=support_digest([0, 1, 2]),
                output_dir=root,
                n=2,
                radius=1,
                length=3,
                exact_overlap=3,
                connectivity="tree",
                time_limit=5,
                deterministic_limit=None,
                solver_workers=1,
                seed=1,
                anchor=0,
                distinct_windows=True,
            )
            self.assertEqual(record["status"], "ERROR")
            self.assertIn("could not parse", record["error"])

    def test_retained_overlap61_portfolio_is_complete(self) -> None:
        summary = json.loads(
            (RETAINED / "summary.json").read_text(encoding="ascii")
        )
        self.assertEqual(summary["exact_overlap"], 61)
        self.assertTrue(summary["distinct_windows"])
        self.assertFalse(summary["repeated_windows_modeled"])
        self.assertEqual(summary["portfolio_case_count"], 10)
        self.assertEqual(summary["status_counts"], {"INFEASIBLE": 10})
        self.assertEqual(
            [case["anchor_edge"] for case in summary["cases"]],
            zero_ball_anchors(9),
        )
        self.assertNotIn("/Users/", json.dumps(summary))

        for case in summary["cases"]:
            result = json.loads(
                (RETAINED / case["result"]).read_text(encoding="ascii")
            )
            self.assertEqual(result["status"], "INFEASIBLE")
            self.assertEqual(result["exact_overlap"], 61)
            self.assertEqual(result["length"], 70)
            self.assertEqual(result["radius"], 1)

    def test_retained_overlap61_sources_match_recorded_hashes(
        self,
    ) -> None:
        summary = json.loads(
            (RETAINED / "summary.json").read_text(encoding="ascii")
        )

        def digest(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest()

        self.assertEqual(
            digest(RETAINED / "source/run_backbone_portfolio_v1.py"),
            summary["runner_source_sha256"],
        )
        self.assertEqual(
            digest(RETAINED / "source/repair_support.py"),
            summary["repair_source_sha256"],
        )
        first_result = json.loads(
            (RETAINED / summary["cases"][0]["result"]).read_text(
                encoding="ascii"
            )
        )
        self.assertEqual(
            digest(RETAINED / "source/flow_cp_sat.py"),
            first_result["flow_source_sha256"],
        )

    def test_retained_repeated_window_reduction_is_scoped(self) -> None:
        repeated = json.loads(
            (REPEATED / "summary.json").read_text(encoding="ascii")
        )
        self.assertFalse(repeated["distinct_windows"])
        self.assertTrue(repeated["repeated_windows_allowed"])
        self.assertEqual(
            repeated["status_counts"],
            {"INFEASIBLE": 8, "UNKNOWN": 2},
        )
        self.assertEqual(
            [
                case["anchor_edge"]
                for case in repeated["cases"]
                if case["status"] == "UNKNOWN"
            ],
            [0, 16],
        )

        support69 = json.loads(
            (SUPPORT69 / "summary.json").read_text(encoding="ascii")
        )
        self.assertEqual(support69["candidate_support_size"], 69)
        self.assertEqual(
            support69["status_counts"],
            {"INFEASIBLE": 8, "UNKNOWN": 2},
        )

        stages = json.loads(
            (SUPPORT_STAGES / "summary.json").read_text(
                encoding="ascii"
            )
        )
        for support_size in range(61, 66):
            self.assertEqual(
                stages["results"][str(support_size)],
                {"0": "INFEASIBLE", "16": "INFEASIBLE"},
            )
        for support_size in range(66, 69):
            self.assertEqual(
                stages["results"][str(support_size)],
                {"0": "UNKNOWN", "16": "UNKNOWN"},
            )

        partitions = json.loads(
            (SUPPORT69_PARTITIONS / "summary.json").read_text(
                encoding="ascii"
            )
        )
        self.assertEqual(
            partitions["status_counts_for_leaf_cases"],
            {"INFEASIBLE": 4, "UNKNOWN": 3},
        )
        self.assertEqual(len(partitions["remaining_cases"]), 3)
        self.assertTrue(
            all(
                case["duplicate_kind"] == "nonloop"
                for case in partitions["remaining_cases"]
            )
        )

    def test_retained_repeated_window_sources_match_hashes(self) -> None:
        for directory in (REPEATED, SUPPORT69):
            summary = json.loads(
                (directory / "summary.json").read_text(encoding="ascii")
            )
            self.assertEqual(
                hashlib.sha256(
                    (directory / "source/repair_support.py").read_bytes()
                ).hexdigest(),
                summary["repair_source_sha256"],
            )
            self.assertEqual(
                hashlib.sha256(
                    (
                        directory / "source/run_backbone_portfolio.py"
                    ).read_bytes()
                ).hexdigest(),
                summary["runner_source_sha256"],
            )

        for directory in (SUPPORT_STAGES, SUPPORT69_PARTITIONS):
            summary = json.loads(
                (directory / "summary.json").read_text(encoding="ascii")
            )
            self.assertEqual(
                hashlib.sha256(
                    (directory / "source/repair_support.py").read_bytes()
                ).hexdigest(),
                summary["repair_source_sha256"],
            )

    def test_retained_overlap61_manifest_is_complete(self) -> None:
        for directory in (
            RETAINED,
            REPEATED,
            SUPPORT69,
            SUPPORT_STAGES,
            SUPPORT69_PARTITIONS,
        ):
            manifest = directory / "files.sha256"
            listed = {}
            for line in manifest.read_text(encoding="ascii").splitlines():
                digest, relative_path = line.split("  ", maxsplit=1)
                listed[relative_path] = digest

            retained_files = {
                str(path.relative_to(directory))
                for path in directory.rglob("*")
                if path.is_file() and path != manifest
            }
            self.assertEqual(set(listed), retained_files, directory)
            for relative_path, expected_digest in listed.items():
                self.assertEqual(
                    hashlib.sha256(
                        (directory / relative_path).read_bytes()
                    ).hexdigest(),
                    expected_digest,
                    relative_path,
                )


@unittest.skipUnless(ORTOOLS_AVAILABLE, "OR-Tools is not installed")
class BackbonePortfolioSolverTests(unittest.TestCase):
    def test_run_case_independently_checks_a_solution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            support_path = root / "support.json"
            support_path.write_text("[0, 1, 2]\n", encoding="ascii")
            record = run_case(
                python=Path(sys.executable),
                repair_script=ROOT / "tools/repair_support.py",
                support=support_path,
                support_edges=frozenset({0, 1, 2}),
                support_sha256=support_digest([0, 1, 2]),
                output_dir=root,
                n=2,
                radius=1,
                length=3,
                exact_overlap=3,
                connectivity="tree",
                time_limit=5,
                deterministic_limit=None,
                solver_workers=1,
                seed=1,
                anchor=0,
                distinct_windows=True,
            )
            self.assertIn(record["status"], {"OPTIMAL", "FEASIBLE"})
            self.assertTrue(record["valid"])
            self.assertTrue(all(record["sequence_checks"].values()))

    def test_run_case_checks_the_repeated_edge_partition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            support_path = root / "support.json"
            support_path.write_text("[0, 1]\n", encoding="ascii")
            record = run_case(
                python=Path(sys.executable),
                repair_script=ROOT / "tools/repair_support.py",
                support=support_path,
                support_edges=frozenset({0, 1}),
                support_sha256=support_digest([0, 1]),
                output_dir=root,
                n=2,
                radius=1,
                length=4,
                exact_overlap=2,
                connectivity="tree",
                time_limit=5,
                deterministic_limit=None,
                solver_workers=1,
                seed=1,
                anchor=0,
                distinct_windows=False,
                support_size=3,
                duplicate_edge=0,
                duplicate_kind="loop",
                duplicate_scope="reference",
            )
            self.assertIn(record["status"], {"OPTIMAL", "FEASIBLE"})
            self.assertTrue(record["valid"])
            self.assertTrue(all(record["sequence_checks"].values()))


if __name__ == "__main__":
    unittest.main()
