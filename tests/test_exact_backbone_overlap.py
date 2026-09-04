from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.analyze_exact_backbone_overlap import exact_overlap_analysis
from tools.covering import load_sequence
from tools.flow_cp_sat import sequence_window_counts
from tools.repair_support import load_support_certificate
from tools.verify_exact_backbone_overlap import flow_digest, verify_artifacts


ROOT = Path(__file__).resolve().parents[1]
RETAINED = ROOT / "evidence/exact-backbone-overlap61-20260904"


def completion_count_vectors(
    result: dict[str, object],
    *,
    support: set[int],
    word_count: int,
) -> set[tuple[int, ...]]:
    vectors: set[tuple[int, ...]] = set()
    completions = result["connected_completions"]
    assert isinstance(completions, list)
    for completion in completions:
        assert isinstance(completion, dict)
        omitted_edges = completion["omitted_edges"]
        residual_flow = completion["residual_flow"]
        assert isinstance(omitted_edges, list)
        assert isinstance(residual_flow, list)
        counts = [0] * word_count
        for edge in support - set(omitted_edges):
            counts[edge] = 1
        for entry in residual_flow:
            assert isinstance(entry, list)
            edge, multiplicity = entry
            counts[edge] += multiplicity
        vectors.add(tuple(counts))
    return vectors


def brute_force_count_vectors(
    *,
    n: int,
    length: int,
    support: set[int],
    exact_overlap: int,
) -> set[tuple[int, ...]]:
    vectors: set[tuple[int, ...]] = set()
    for bits in product((0, 1), repeat=length):
        counts = sequence_window_counts(list(bits), n)
        selected = {
            edge
            for edge, multiplicity in enumerate(counts)
            if multiplicity
        }
        if len(selected & support) == exact_overlap:
            vectors.add(tuple(counts))
    return vectors


class ExactBackboneOverlapTests(unittest.TestCase):
    def test_zero_divergence_case_matches_every_small_cycle(self) -> None:
        support = {0, 7}
        result = exact_overlap_analysis(
            support,
            n=3,
            radius=1,
            candidate_length=4,
            exact_overlap=1,
        )

        self.assertEqual(
            completion_count_vectors(
                result,
                support=support,
                word_count=8,
            ),
            brute_force_count_vectors(
                n=3,
                length=4,
                support=support,
                exact_overlap=1,
            ),
        )

    def test_nonzero_divergence_case_matches_every_small_cycle(self) -> None:
        support = {1, 2, 3, 4, 5, 6}
        result = exact_overlap_analysis(
            support,
            n=3,
            radius=1,
            candidate_length=8,
            exact_overlap=4,
        )

        self.assertEqual(
            completion_count_vectors(
                result,
                support=support,
                word_count=8,
            ),
            brute_force_count_vectors(
                n=3,
                length=8,
                support=support,
                exact_overlap=4,
            ),
        )

    def test_three_omission_case_matches_every_small_cycle(self) -> None:
        support = set(range(8))
        result = exact_overlap_analysis(
            support,
            n=3,
            radius=1,
            candidate_length=7,
            exact_overlap=5,
        )

        self.assertEqual(result["enumeration"]["omission_sets_checked"], 56)
        self.assertEqual(
            completion_count_vectors(
                result,
                support=support,
                word_count=8,
            ),
            brute_force_count_vectors(
                n=3,
                length=7,
                support=support,
                exact_overlap=5,
            ),
        )

    def test_mass9_three_terminal_case_matches_every_small_cycle(self) -> None:
        support = {1, 2, 4, 5, 8, 10}
        result = exact_overlap_analysis(
            support,
            n=4,
            radius=1,
            candidate_length=12,
            exact_overlap=3,
        )

        self.assertEqual(result["parameters"]["residual_mass"], 9)
        self.assertEqual(
            result["enumeration"]["source_count_histogram"]["3"],
            2,
        )
        self.assertEqual(
            completion_count_vectors(
                result,
                support=support,
                word_count=16,
            ),
            brute_force_count_vectors(
                n=4,
                length=12,
                support=support,
                exact_overlap=3,
            ),
        )

    def test_retained_overlap61_shell_is_completely_classified(self) -> None:
        support_path = (
            ROOT / "data/candidates/l9-r1-common-backbone-64.json"
        )
        witness_path = (
            ROOT / "data/candidates/l9-r1-70-backbone-overlap-61.txt"
        )
        support = set(load_support_certificate(support_path, n=9))
        result = exact_overlap_analysis(
            support,
            n=9,
            radius=1,
            candidate_length=70,
            exact_overlap=61,
            overlap_witness=load_sequence(witness_path),
        )

        self.assertEqual(
            result["enumeration"],
            {
                "omission_sets_checked": 41664,
                "precomputed_directed_walks": 65408,
                "balanced_flow_counts_by_mass": [
                    1,
                    2,
                    4,
                    8,
                    16,
                    32,
                    64,
                    128,
                    256,
                    512,
                ],
                "source_count_histogram": {
                    "1": 64,
                    "2": 3840,
                    "3": 37760,
                },
                "active_omission_sets": 88,
                "distinct_path_flows": 112,
                "raw_exact_decompositions": 192,
                "distinct_residual_flows": 188,
                "residual_flow_count_histogram": {
                    "0": 41576,
                    "1": 50,
                    "2": 12,
                    "3": 14,
                    "4": 4,
                    "5": 2,
                    "7": 2,
                    "8": 4,
                },
                "component_count_histogram": {
                    "1": 8,
                    "2": 72,
                    "3": 80,
                    "4": 28,
                },
                "connected_support_size_histogram": {"70": 8},
                "connected_coverage_gap_histogram": {
                    "9": 6,
                    "10": 2,
                },
                "connected_completion_count": 8,
                "covering_completion_count": 0,
            },
        )
        self.assertEqual(
            len(result["connected_completions"]),
            8,
        )
        self.assertTrue(
            all(
                completion["combined_support_size"] == 70
                and completion["verification"]["distinct_windows"] == 70
                and not completion["verification"]["valid"]
                for completion in result["connected_completions"]
            )
        )
        self.assertEqual(
            result["overlap_witness"]["matching_completion_indices"],
            [0],
        )
        self.assertIn("No length-70", result["consequence"])

        checker = ROOT / "build/exact-overlap-checker"
        self.assertTrue(
            checker.is_file(),
            "run `make build` before the independent checker test",
        )
        completed = subprocess.run(
            [str(checker), str(support_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        independent = json.loads(completed.stdout)
        expected_enumeration = dict(result["enumeration"])
        self.assertEqual(
            {
                key: independent[key]
                for key in expected_enumeration
            },
            expected_enumeration,
        )
        expected_completions = [
            {
                "omitted_edges": completion["omitted_edges"],
                "residual_flow": completion["residual_flow"],
                "combined_support_size": completion[
                    "combined_support_size"
                ],
                "uncovered_words": list(
                    completion["verification"]["uncovered_words"]
                ),
            }
            for completion in result["connected_completions"]
        ]
        self.assertEqual(
            independent["connected_completions"],
            expected_completions,
        )

    def test_retained_artifacts_pass_and_detect_tampering(self) -> None:
        analysis = json.loads(
            (RETAINED / "analysis.json").read_text(encoding="ascii")
        )
        independent = json.loads(
            (RETAINED / "independent-check.json").read_text(
                encoding="ascii"
            )
        )
        summary = verify_artifacts(
            analysis,
            independent,
            support_path=(
                ROOT / "data/candidates/l9-r1-common-backbone-64.json"
            ),
            analyzer_path=(
                RETAINED / "source/analyze_exact_backbone_overlap_v1.py"
            ),
            witness_path=(
                ROOT
                / "data/candidates/l9-r1-70-backbone-overlap-61.txt"
            ),
        )
        self.assertEqual(
            summary,
            {
                "omission_sets_checked": 41664,
                "distinct_residual_flows": 188,
                "connected_completion_count": 8,
                "covering_completion_count": 0,
            },
        )

        tampered = deepcopy(independent)
        tampered["distinct_residual_flows"] += 1
        with self.assertRaisesRegex(
            ValueError,
            "independent checker disagrees",
        ):
            verify_artifacts(
                analysis,
                tampered,
                support_path=(
                    ROOT / "data/candidates/l9-r1-common-backbone-64.json"
                ),
                analyzer_path=(
                    RETAINED
                    / "source/analyze_exact_backbone_overlap_v1.py"
                ),
                witness_path=(
                    ROOT
                    / "data/candidates/l9-r1-70-backbone-overlap-61.txt"
                ),
            )

        synchronized_analysis = deepcopy(analysis)
        synchronized_independent = deepcopy(independent)
        synchronized_analysis["enumeration"]["omission_sets_checked"] = 1
        synchronized_independent["omission_sets_checked"] = 1
        with self.assertRaisesRegex(ValueError, "summary changed"):
            verify_artifacts(
                synchronized_analysis,
                synchronized_independent,
                support_path=(
                    ROOT / "data/candidates/l9-r1-common-backbone-64.json"
                ),
                analyzer_path=(
                    RETAINED
                    / "source/analyze_exact_backbone_overlap_v1.py"
                ),
                witness_path=(
                    ROOT
                    / "data/candidates/l9-r1-70-backbone-overlap-61.txt"
                ),
            )

        missing_completions = deepcopy(analysis)
        missing_independent = deepcopy(independent)
        missing_completions["connected_completions"] = []
        missing_independent["connected_completions"] = []
        with self.assertRaisesRegex(ValueError, "omit or add"):
            verify_artifacts(
                missing_completions,
                missing_independent,
                support_path=(
                    ROOT / "data/candidates/l9-r1-common-backbone-64.json"
                ),
                analyzer_path=(
                    RETAINED
                    / "source/analyze_exact_backbone_overlap_v1.py"
                ),
                witness_path=(
                    ROOT
                    / "data/candidates/l9-r1-70-backbone-overlap-61.txt"
                ),
            )

        bad_metadata = deepcopy(analysis)
        bad_metadata["active_cases"][0]["residuals"][0][
            "combined_component_count"
        ] += 1
        with self.assertRaisesRegex(ValueError, "component count"):
            verify_artifacts(
                bad_metadata,
                independent,
                support_path=(
                    ROOT / "data/candidates/l9-r1-common-backbone-64.json"
                ),
                analyzer_path=(
                    RETAINED
                    / "source/analyze_exact_backbone_overlap_v1.py"
                ),
                witness_path=(
                    ROOT
                    / "data/candidates/l9-r1-70-backbone-overlap-61.txt"
                ),
            )

        bad_mass = deepcopy(analysis)
        bad_flow = bad_mass["active_cases"][0]["residuals"][0]["flow"]
        bad_flow[0][1] += 1
        bad_mass["active_cases"][0]["residuals"][0]["flow_sha256"] = (
            flow_digest(
                tuple(
                    (edge, multiplicity)
                    for edge, multiplicity in bad_flow
                )
            )
        )
        with self.assertRaisesRegex(ValueError, "wrong mass"):
            verify_artifacts(
                bad_mass,
                independent,
                support_path=(
                    ROOT / "data/candidates/l9-r1-common-backbone-64.json"
                ),
                analyzer_path=(
                    RETAINED
                    / "source/analyze_exact_backbone_overlap_v1.py"
                ),
                witness_path=(
                    ROOT
                    / "data/candidates/l9-r1-70-backbone-overlap-61.txt"
                ),
            )

        bad_completion_digest = deepcopy(analysis)
        bad_completion_digest["connected_completions"][0][
            "residual_flow_sha256"
        ] = "0" * 64
        with self.assertRaisesRegex(ValueError, "flow digest"):
            verify_artifacts(
                bad_completion_digest,
                independent,
                support_path=(
                    ROOT / "data/candidates/l9-r1-common-backbone-64.json"
                ),
                analyzer_path=(
                    RETAINED
                    / "source/analyze_exact_backbone_overlap_v1.py"
                ),
                witness_path=(
                    ROOT
                    / "data/candidates/l9-r1-70-backbone-overlap-61.txt"
                ),
            )

    def test_retained_analysis_reproduces_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "analysis.json"
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(
                        RETAINED
                        / "source/analyze_exact_backbone_overlap_v1.py"
                    ),
                    "data/candidates/l9-r1-common-backbone-64.json",
                    str(output),
                    "--overlap-witness",
                    (
                        "data/candidates/"
                        "l9-r1-70-backbone-overlap-61.txt"
                    ),
                    "--n",
                    "9",
                    "--radius",
                    "1",
                    "--candidate-length",
                    "70",
                    "--exact-overlap",
                    "61",
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                output.read_bytes(),
                (RETAINED / "analysis.json").read_bytes(),
            )

    def test_retained_cpp_reproduces_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checker = Path(directory) / "exact-overlap-checker"
            subprocess.run(
                [
                    os.environ.get("CXX", "c++"),
                    "-std=c++20",
                    "-O3",
                    "-Wall",
                    "-Wextra",
                    "-Wpedantic",
                    "-Werror",
                    str(RETAINED / "source/exact_overlap_checker_v1.cpp"),
                    "-o",
                    str(checker),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            completed = subprocess.run(
                [
                    str(checker),
                    "data/candidates/l9-r1-common-backbone-64.json",
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
            )
            self.assertEqual(
                completed.stdout,
                (RETAINED / "independent-check.json").read_bytes(),
            )

    def test_retained_manifest_authenticates_every_file(self) -> None:
        manifest = RETAINED / "files.sha256"
        listed = {}
        for line in manifest.read_text(encoding="ascii").splitlines():
            digest, relative_path = line.split("  ", maxsplit=1)
            listed[relative_path] = digest

        retained_files = {
            str(path.relative_to(RETAINED))
            for path in RETAINED.rglob("*")
            if path.is_file() and path != manifest
        }
        self.assertEqual(set(listed), retained_files)
        for relative_path, expected_digest in listed.items():
            self.assertEqual(
                sha256((RETAINED / relative_path).read_bytes()).hexdigest(),
                expected_digest,
                relative_path,
            )

    def test_rejects_unsupported_enumeration_size(self) -> None:
        with self.assertRaisesRegex(ValueError, "at most three omissions"):
            exact_overlap_analysis(
                {0, 1, 2, 3, 4},
                n=3,
                radius=1,
                candidate_length=7,
                exact_overlap=1,
            )


if __name__ == "__main__":
    unittest.main()
