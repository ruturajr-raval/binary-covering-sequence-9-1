from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.analyze_common_backbone import analyze_backbone
from tools.verify_common_backbone import EXPECTED_SUMMARY, verify_artifact


ROOT = Path(__file__).resolve().parents[1]
BACKBONE = ROOT / "data/candidates/l9-r1-common-backbone-64.json"
BASELINE = ROOT / "data/baseline/l9-r1-71.txt"
WITNESS = ROOT / "data/candidates/l9-r1-70-backbone-overlap-61.txt"


class VerifyCommonBackboneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.analysis = analyze_backbone(
            BACKBONE,
            baseline_path=BASELINE,
            overlap_witness_path=WITNESS,
            n=9,
            radius=1,
            candidate_length=70,
        )

    def write_analysis(self, payload: dict[str, object]) -> Path:
        path = ROOT / "build/test-common-backbone-analysis.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="ascii",
        )
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def test_all_residual_flows_are_retained_and_verified(self) -> None:
        section = self.analysis["double_omission_residuals"]
        retained = sum(
            len(case["residual_flows"])
            for case in section["active_omission_cases"]
        )
        self.assertEqual(retained, 168)
        self.assertEqual(
            verify_artifact(
                self.write_analysis(self.analysis),
                BACKBONE,
                WITNESS,
            ),
            EXPECTED_SUMMARY,
        )

    def test_missing_residual_is_rejected(self) -> None:
        tampered = deepcopy(self.analysis)
        first_case = tampered["double_omission_residuals"][
            "active_omission_cases"
        ][0]
        first_case["residual_flows"].clear()
        with self.assertRaisesRegex(ValueError, "residuals are absent"):
            verify_artifact(
                self.write_analysis(tampered),
                BACKBONE,
                WITNESS,
            )

    def test_altered_residual_is_rejected(self) -> None:
        tampered = deepcopy(self.analysis)
        first_record = tampered["double_omission_residuals"][
            "active_omission_cases"
        ][0]["residual_flows"][0]
        first_record["flow"][0][1] += 1
        with self.assertRaisesRegex(ValueError, "digest is inconsistent"):
            verify_artifact(
                self.write_analysis(tampered),
                BACKBONE,
                WITNESS,
            )


if __name__ == "__main__":
    unittest.main()
