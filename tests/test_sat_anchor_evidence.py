from __future__ import annotations

import gzip
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/sat-anchor-cover-20260902"


def file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def canonical_case_names(n: int) -> list[str]:
    def reverse_word(word: int) -> int:
        result = 0
        for _ in range(n):
            result = (result << 1) | (word & 1)
            word >>= 1
        return result

    names: list[str] = []
    for word in (0, *(1 << bit for bit in range(n))):
        reflected = reverse_word(word)
        if word > reflected:
            continue
        for predecessor in (0, 1):
            for successor in (0, 1):
                if word == reflected and successor > predecessor:
                    continue
                names.append(
                    f"anchor-{word:03d}-p{predecessor}-s{successor}"
                )
    return names


def load_retained_generator(path: Path):
    spec = importlib.util.spec_from_file_location(
        "retained_generate_cnf_v2",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load retained generator from {path}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


class SatAnchorEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        manifest = json.loads(
            (ROOT / "evidence.json").read_text(encoding="ascii")
        )
        cls.retained = manifest["canonical_sat_anchor_cover"]
        cls.generator = load_retained_generator(
            ROOT / cls.retained["generator_source"]
        )

    def test_file_manifest_authenticates_retained_artifacts(self) -> None:
        listed: set[str] = set()
        for line in (EVIDENCE / "files.sha256").read_text(
            encoding="ascii"
        ).splitlines():
            expected, relative = line.split(maxsplit=1)
            listed.add(relative)
            self.assertEqual(file_digest(EVIDENCE / relative), expected)

        actual = {
            str(path.relative_to(EVIDENCE))
            for directory in ("complete", "support70", "proofs", "source")
            for path in (EVIDENCE / directory).rglob("*")
            if path.is_file()
        }
        self.assertEqual(listed, actual)

    def test_portfolio_summaries_have_the_complete_case_cover(self) -> None:
        expected_names = canonical_case_names(9)
        self.assertEqual(len(expected_names), 22)

        for key, expected_support, expected_counts in (
            ("complete_portfolio", None, {"UNKNOWN": 22}),
            (
                "exact_support_70_portfolio",
                70,
                {"UNKNOWN": 20, "UNSATISFIABLE": 2},
            ),
        ):
            with self.subTest(portfolio=key):
                retained = self.retained[key]
                summary_path = ROOT / retained["summary"]
                self.assertEqual(
                    file_digest(summary_path),
                    retained["summary_sha256"],
                )
                summary = json.loads(summary_path.read_text(encoding="ascii"))
                self.assertEqual(
                    summary["production_run"],
                    retained["production_run"],
                )
                self.assertEqual(summary["exact_support"], expected_support)
                self.assertEqual(summary["status_counts"], expected_counts)
                self.assertEqual(
                    [case["case"] for case in summary["cases"]],
                    expected_names,
                )
                self.assertEqual(summary["portfolio_case_count"], 22)
                for case in summary["cases"]:
                    self.assertTrue(
                        (summary_path.parent / case["log"]).is_file()
                    )
                    self.assertTrue(
                        (summary_path.parent / f"{case['case']}.result").is_file()
                    )

    def test_unsat_proofs_match_regenerated_formulas(self) -> None:
        portfolio = json.loads(
            (
                ROOT
                / self.retained["exact_support_70_portfolio"]["summary"]
            ).read_text(encoding="ascii")
        )
        cases = {case["case"]: case for case in portfolio["cases"]}

        for name, retained in self.retained["proof_cases"].items():
            with self.subTest(case=name):
                raw_cnf = gzip.decompress(
                    (ROOT / retained["cnf"]["artifact"]).read_bytes()
                )
                self.assertEqual(len(raw_cnf), retained["cnf"]["raw_bytes"])
                self.assertEqual(
                    sha256(raw_cnf).hexdigest(),
                    retained["cnf"]["raw_sha256"],
                )
                self.assertEqual(
                    cases[name]["cnf_sha256"],
                    retained["cnf"]["raw_sha256"],
                )

                raw_proof = gzip.decompress(
                    (ROOT / retained["proof"]["artifact"]).read_bytes()
                )
                self.assertEqual(
                    len(raw_proof),
                    retained["proof"]["raw_bytes"],
                )
                self.assertEqual(
                    sha256(raw_proof).hexdigest(),
                    retained["proof"]["raw_sha256"],
                )

                solver_log = (
                    ROOT / retained["solver_log"]["artifact"]
                ).read_text(encoding="ascii")
                checker_log = (
                    ROOT / retained["checker_log"]["artifact"]
                ).read_text(encoding="ascii")
                self.assertEqual(
                    file_digest(ROOT / retained["solver_log"]["artifact"]),
                    retained["solver_log"]["sha256"],
                )
                self.assertEqual(
                    file_digest(ROOT / retained["checker_log"]["artifact"]),
                    retained["checker_log"]["sha256"],
                )
                self.assertIn("s UNSATISFIABLE", solver_log)
                self.assertIn("s VERIFIED", checker_log)

                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / f"{name}.cnf"
                    variables, clauses = self.generator.write_pattern_cnf(
                        path,
                        n=9,
                        radius=1,
                        length=70,
                        symmetry=False,
                        seed_bits=[0] * 70,
                        max_distance=35,
                        exact_support=70,
                        anchor_word=retained["anchor_word"],
                        anchor_predecessor_bit=retained[
                            "predecessor_bit"
                        ],
                        anchor_successor_bit=retained["successor_bit"],
                    )
                    self.assertEqual(variables, 41357)
                    self.assertEqual(clauses, 414868)
                    self.assertEqual(
                        file_digest(path),
                        retained["cnf"]["raw_sha256"],
                    )


if __name__ == "__main__":
    unittest.main()
