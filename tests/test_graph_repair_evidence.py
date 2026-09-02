from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import unittest

from tools.analyze_support import analyze_cross_joins
from tools.repair_support import load_support_certificate


ROOT = Path(__file__).resolve().parents[1]


def file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


class GraphRepairEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        evidence = json.loads(
            (ROOT / "evidence.json").read_text(encoding="ascii")
        )
        self.manifest = evidence["graph_support_repair"]

    def test_manifest_hashes_and_cross_join_output(self) -> None:
        checks = {
            ROOT / self.manifest["base_support"]["artifact"]: self.manifest[
                "base_support"
            ]["artifact_sha256"],
            ROOT
            / self.manifest["cross_join_analysis"]["artifact"]: self.manifest[
                "cross_join_analysis"
            ]["artifact_sha256"],
            ROOT / self.manifest["evidence_log"]: self.manifest[
                "evidence_log_sha256"
            ],
        }
        for path, expected in checks.items():
            self.assertEqual(file_digest(path), expected, path)

        for source in self.manifest["source_snapshots"].values():
            path = ROOT / source["path"]
            self.assertEqual(file_digest(path), source["sha256"], path)

        support_path = ROOT / self.manifest["base_support"]["artifact"]
        support = load_support_certificate(support_path, n=9)
        retained = json.loads(
            (
                ROOT / self.manifest["cross_join_analysis"]["artifact"]
            ).read_text(encoding="ascii")
        )
        self.assertEqual(
            analyze_cross_joins(support, n=9, radius=1),
            retained,
        )

    def test_overlap_portfolio_is_complete_and_aggregates_match(self) -> None:
        summary = self.manifest["overlap_neighborhood"]
        expected_anchors = summary["partitioned_anchors"]
        expected_artifacts = summary["artifacts"]
        actual_paths = {
            str(path.relative_to(ROOT))
            for path in (
                ROOT / "evidence" / "graph-repair"
            ).glob("overlap58-anchor-*.json")
        }
        self.assertEqual(
            actual_paths,
            {
                artifact["path"]
                for artifact in expected_artifacts.values()
            },
        )
        artifacts = []
        for anchor in expected_anchors:
            retained = expected_artifacts[str(anchor)]
            path = ROOT / retained["path"]
            self.assertEqual(file_digest(path), retained["sha256"])
            result = json.loads(path.read_text(encoding="ascii"))
            self.assertEqual(result["anchor_edge"], anchor)
            self.assertEqual(result["n"], 9)
            self.assertEqual(result["radius"], 1)
            self.assertEqual(result["length"], 69)
            self.assertTrue(result["partition_anchor"])
            self.assertEqual(result["connectivity_mode"], "tree")
            self.assertEqual(result["minimum_overlap"], 58)
            self.assertEqual(result["maximum_replacements"], 11)
            self.assertEqual(result["status"], "INFEASIBLE")
            self.assertEqual(
                result["base_support_sha256"],
                self.manifest["base_support"][
                    "normalized_support_sha256"
                ],
            )
            self.assertEqual(
                result["flow_source_sha256"],
                self.manifest["flow_source_sha256"],
            )
            self.assertEqual(
                result["repair_source_sha256"],
                self.manifest["repair_source_sha256"],
            )
            artifacts.append(result)

        self.assertEqual(
            sum(result["branches"] for result in artifacts),
            summary["aggregate_branches"],
        )
        self.assertEqual(
            sum(result["conflicts"] for result in artifacts),
            summary["aggregate_conflicts"],
        )
        self.assertAlmostEqual(
            sum(result["wall_seconds"] for result in artifacts),
            summary["aggregate_solver_wall_seconds"],
        )
        self.assertAlmostEqual(
            sum(result["deterministic_time"] for result in artifacts),
            summary["aggregate_deterministic_time"],
        )

    def test_additional_anchor_zero_artifact_is_retained(self) -> None:
        retained = self.manifest["anchor_zero_additional_exclusion"]
        path = ROOT / retained["artifact"]
        self.assertEqual(file_digest(path), retained["artifact_sha256"])
        result = json.loads(path.read_text(encoding="ascii"))
        self.assertEqual(result["status"], "INFEASIBLE")
        self.assertEqual(result["anchor_edge"], 0)
        self.assertTrue(result["partition_anchor"])
        self.assertEqual(result["minimum_overlap"], 57)
        self.assertEqual(result["maximum_replacements"], 12)
        self.assertEqual(result["required_replacements_at_least"], 13)
        self.assertEqual(
            result["base_support_sha256"],
            self.manifest["base_support"]["normalized_support_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
