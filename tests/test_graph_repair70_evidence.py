from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import unittest

from tools.analyze_support import analyze_cross_joins
from tools.repair_support import (
    analyze_support,
    load_support_certificate,
    support_digest,
)


ROOT = Path(__file__).resolve().parents[1]


def file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


class GraphRepair70EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        evidence = json.loads(
            (ROOT / "evidence.json").read_text(encoding="ascii")
        )
        cls.manifest = evidence["graph_support70_repair"]

    def test_base_support_and_cross_joins(self) -> None:
        base = self.manifest["base_support"]
        base_path = ROOT / base["artifact"]
        self.assertEqual(file_digest(base_path), base["artifact_sha256"])
        support = load_support_certificate(base_path, n=9)
        self.assertEqual(support_digest(support), base["normalized_support_sha256"])

        report = analyze_support(support, n=9, radius=1)
        self.assertTrue(report["balanced"])
        self.assertEqual(report["covered_words"], base["covered_words"])
        self.assertEqual(report["distinct_edges"], base["distinct_edges"])
        self.assertEqual(
            report["component_edge_counts"],
            base["component_edge_counts"],
        )
        vertex_mask = (1 << 8) - 1
        active_vertices = {
            endpoint
            for word in support
            for endpoint in (word >> 1, word & vertex_mask)
        }
        self.assertEqual(len(active_vertices), base["active_vertices"])

        cross_join = self.manifest["cross_join_analysis"]
        cross_path = ROOT / cross_join["artifact"]
        self.assertEqual(
            file_digest(cross_path),
            cross_join["artifact_sha256"],
        )
        self.assertEqual(
            file_digest(ROOT / cross_join["log"]),
            cross_join["log_sha256"],
        )
        retained = json.loads(cross_path.read_text(encoding="ascii"))
        self.assertEqual(
            analyze_cross_joins(support, n=9, radius=1),
            retained,
        )
        self.assertEqual(
            retained["cross_join_candidate_count"],
            cross_join["candidate_count"],
        )
        self.assertEqual(
            retained["valid_cross_join_count"],
            cross_join["valid_cover_count"],
        )

    def test_production_sources_match_retained_hashes(self) -> None:
        for source in self.manifest["source_snapshots"].values():
            path = ROOT / source["path"]
            self.assertEqual(file_digest(path), source["sha256"], path)

    def test_overlap_portfolio_hashes_and_aggregates(self) -> None:
        summary = self.manifest["overlap_neighborhood"]
        expected_artifacts = summary["artifacts"]
        actual_paths = {
            str(path.relative_to(ROOT))
            for path in (
                ROOT / self.manifest["raw_artifacts_directory"]
            ).glob("repair-overlap53-*.json")
        }
        self.assertEqual(
            actual_paths,
            {
                artifact["path"]
                for artifact in expected_artifacts.values()
            },
        )

        results = []
        statuses = Counter()
        for anchor in summary["partitioned_anchors"]:
            retained = expected_artifacts[str(anchor)]
            path = ROOT / retained["path"]
            self.assertEqual(file_digest(path), retained["sha256"])
            self.assertEqual(
                file_digest(ROOT / retained["log"]),
                retained["log_sha256"],
            )
            result = json.loads(path.read_text(encoding="ascii"))
            self.assertEqual(result["anchor_edge"], anchor)
            self.assertEqual(result["status"], retained["status"])
            self.assertEqual(result["n"], 9)
            self.assertEqual(result["radius"], 1)
            self.assertEqual(result["length"], summary["length"])
            self.assertTrue(result["partition_anchor"])
            self.assertEqual(result["connectivity_mode"], "tree")
            self.assertEqual(
                result["minimum_overlap"],
                summary["minimum_overlap"],
            )
            self.assertEqual(
                result["maximum_replacements"],
                summary["maximum_replacements"],
            )
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
            if result["status"] == "INFEASIBLE":
                self.assertEqual(result["required_replacements_at_least"], 18)
            else:
                self.assertNotIn("required_replacements_at_least", result)
            statuses[result["status"]] += 1
            results.append(result)

        self.assertEqual(dict(statuses), summary["status_counts"])
        self.assertEqual(
            sorted(
                result["anchor_edge"]
                for result in results
                if result["status"] == "INFEASIBLE"
            ),
            summary["scoped_infeasible_anchors"],
        )
        self.assertEqual(
            sorted(
                result["anchor_edge"]
                for result in results
                if result["status"] == "UNKNOWN"
            ),
            summary["unresolved_anchors"],
        )
        self.assertEqual(
            sum(result["branches"] for result in results),
            summary["aggregate_branches"],
        )
        self.assertEqual(
            sum(result["conflicts"] for result in results),
            summary["aggregate_conflicts"],
        )
        self.assertAlmostEqual(
            sum(result["wall_seconds"] for result in results),
            summary["aggregate_solver_wall_seconds"],
        )
        self.assertAlmostEqual(
            sum(result["deterministic_time"] for result in results),
            summary["aggregate_deterministic_time"],
        )


if __name__ == "__main__":
    unittest.main()
