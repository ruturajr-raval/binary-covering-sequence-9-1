from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
import unittest

from tools.covering import load_sequence, verify_sequence


ROOT = Path(__file__).resolve().parents[1]


def file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


class EjectionEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        manifest = json.loads(
            (ROOT / "evidence.json").read_text(encoding="ascii")
        )
        cls.retained = manifest["ejection_chain_search"]

    def test_artifacts_and_metrics_match(self) -> None:
        self.assertEqual(
            file_digest(ROOT / self.retained["source"]),
            self.retained["source_sha256"],
        )
        artifacts = self.retained["artifacts"]
        for artifact in artifacts.values():
            path = ROOT / artifact["path"]
            self.assertEqual(file_digest(path), artifact["sha256"])

        log = (ROOT / artifacts["log"]["path"]).read_text(encoding="ascii")
        metrics_line = next(
            line for line in log.splitlines()
            if line.startswith("ejection worker=")
        )
        parsed = {
            key: int(value)
            for key, value in re.findall(r"([a-z_]+)=(-?\d+)", metrics_line)
        }
        metrics = self.retained["metrics"]
        expected = {
            "chains": self.retained["parameters"]["chains"],
            "evaluations": metrics["candidate_evaluations"],
            "beam_states": metrics["beam_states"],
            "accepted_endpoints": metrics["accepted_endpoints"],
            "exploration_chains": metrics["exploration_chains"],
            "max_origin_distance": metrics["maximum_origin_distance"],
            "distant_six_gap_visits": metrics["distant_six_gap_visits"],
            "distinct_distant_six_gap_states": (
                metrics["distinct_archived_distant_six_gap_states"]
            ),
            "distant_archive_capped": int(metrics["archive_capped"]),
            "best_distant_distance": metrics["best_distant_distance"],
        }
        for key, value in expected.items():
            self.assertEqual(parsed[key], value, key)
        self.assertIn("found=false best_uncovered=6", log)

    def test_retained_states_verify_independently(self) -> None:
        artifacts = self.retained["artifacts"]
        reports = {}
        sequences = {}
        for name in ("best_state", "distant_state"):
            artifact = artifacts[name]
            bits = load_sequence(ROOT / artifact["path"])
            report = verify_sequence(
                bits,
                n=9,
                radius=1,
                expected_length=70,
            )
            sequences[name] = bits
            reports[name] = report
            self.assertFalse(report.valid)
            self.assertEqual(report.covered_words, artifact["covered_words"])
            self.assertEqual(
                list(report.uncovered_words),
                artifact["uncovered_words"],
            )
            self.assertEqual(
                report.distinct_windows,
                artifact["distinct_windows"],
            )
            self.assertEqual(report.normalized_sha256, artifact["sha256"])

        raw_distance = sum(
            left != right
            for left, right in zip(
                sequences["best_state"],
                sequences["distant_state"],
            )
        )
        self.assertEqual(
            raw_distance,
            artifacts["distant_state"][
                "raw_hamming_distance_from_best_state"
            ],
        )
        best = sequences["best_state"]
        distant = sequences["distant_state"]
        shift = artifacts["distant_state"][
            "cyclic_rotation_from_best_state"
        ]
        self.assertEqual(best[shift:] + best[:shift], distant)
        self.assertEqual(
            artifacts["distant_state"][
                "cyclic_orbit_distance_from_best_state"
            ],
            0,
        )
        self.assertFalse(
            artifacts["distant_state"]["orbit_distinct_from_best_state"]
        )


if __name__ == "__main__":
    unittest.main()
