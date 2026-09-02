from __future__ import annotations

import gzip
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest

from tools.covering import load_sequence


ROOT = Path(__file__).resolve().parents[1]


def file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def load_write_pattern_cnf(path: Path):
    spec = importlib.util.spec_from_file_location(
        "retained_generate_cnf",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load retained generator from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.write_pattern_cnf


class SatEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (ROOT / "evidence.json").read_text(encoding="ascii")
        )
        retained = cls.manifest["exact_support_sat_search"]
        cls.generator_path = ROOT / retained["generator_source"]
        cls.write_pattern_cnf = staticmethod(
            load_write_pattern_cnf(cls.generator_path)
        )

    def test_distance_four_proof_artifact_and_formula(self) -> None:
        retained = self.manifest["proof_checked_hamming_neighborhood"]
        self.assertEqual(
            file_digest(ROOT / retained["seed"]),
            retained["seed_file_sha256"],
        )
        proof = retained["retained_proof_core"]
        proof_path = ROOT / proof["artifact"]
        self.assertEqual(proof_path.stat().st_size, proof["compressed_bytes"])
        self.assertEqual(file_digest(proof_path), proof["compressed_sha256"])
        raw_proof = gzip.decompress(proof_path.read_bytes())
        self.assertEqual(len(raw_proof), proof["raw_bytes"])
        self.assertEqual(sha256(raw_proof).hexdigest(), proof["raw_sha256"])
        self.assertEqual(
            file_digest(
                ROOT / retained["formula"]["generator_source"]
            ),
            retained["formula"]["generator_source_sha256"],
        )

        for key in ("solver_log", "checker_log"):
            artifact = retained[key]
            path = ROOT / artifact["artifact"]
            self.assertEqual(file_digest(path), artifact["sha256"])
        solver_log = (
            ROOT / retained["solver_log"]["artifact"]
        ).read_text(encoding="ascii")
        self.assertIn(
            "Version "
            + retained["solver"]["version"]
            + " "
            + retained["solver"]["commit"],
            solver_log,
        )
        self.assertIn("writing binary proof trace", solver_log)
        self.assertIn(
            "s UNSATISFIABLE",
            solver_log,
        )
        self.assertIn(
            "s VERIFIED",
            (ROOT / retained["checker_log"]["artifact"]).read_text(
                encoding="ascii"
            ),
        )

        formula = retained["formula"]
        seed = load_sequence(ROOT / retained["seed"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "distance4.cnf"
            variables, clauses = self.write_pattern_cnf(
                path,
                n=9,
                radius=1,
                length=70,
                symmetry=False,
                seed_bits=seed,
                max_distance=retained["maximum_distance"],
            )
            self.assertEqual(variables, formula["variables"])
            self.assertEqual(clauses, formula["clauses"])
            self.assertEqual(file_digest(path), formula["sha256"])

    def test_exact_support_timeout_artifacts_and_formulas(self) -> None:
        retained = self.manifest["exact_support_sat_search"]
        self.assertEqual(
            file_digest(ROOT / retained["generator_source"]),
            retained["generator_source_sha256"],
        )
        for support, case in retained["cases"].items():
            with self.subTest(support=support):
                log_path = ROOT / case["solver_log"]
                self.assertEqual(
                    file_digest(log_path),
                    case["solver_log_sha256"],
                )
                self.assertIn(
                    "c UNKNOWN",
                    log := log_path.read_text(encoding="ascii"),
                )
                self.assertIn(
                    "Version "
                    + retained["solver"]["version"]
                    + " "
                    + retained["solver"]["commit"],
                    log,
                )
                for statistic in ("conflicts", "decisions"):
                    match = re.search(
                        rf"^c {statistic}:\s+(\d+)",
                        log,
                        flags=re.MULTILINE,
                    )
                    self.assertIsNotNone(match)
                    self.assertEqual(
                        int(match.group(1)),
                        case[statistic],
                    )
                wall_match = re.search(
                    r"^c total real time since initialization:\s+"
                    r"([0-9.]+)",
                    log,
                    flags=re.MULTILINE,
                )
                self.assertIsNotNone(wall_match)
                self.assertAlmostEqual(
                    float(wall_match.group(1)),
                    case["wall_seconds"],
                    places=2,
                )

                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / f"support{support}.cnf"
                    variables, clauses = self.write_pattern_cnf(
                        path,
                        n=9,
                        radius=1,
                        length=70,
                        exact_support=int(support),
                    )
                    self.assertEqual(variables, case["variables"])
                    self.assertEqual(clauses, case["clauses"])
                    self.assertEqual(file_digest(path), case["cnf_sha256"])


if __name__ == "__main__":
    unittest.main()
