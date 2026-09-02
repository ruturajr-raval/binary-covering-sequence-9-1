from __future__ import annotations

from collections import Counter
from contextlib import redirect_stdout
import hashlib
import io
from itertools import combinations, combinations_with_replacement
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.analyze_common_backbone import (
    analyze_backbone,
    balanced_cycle_flows,
    enumerate_connector_walks,
    exact_two_omission_analysis,
    exhaustive_connector_walk,
    exhaustive_omission_detours,
    exhaustive_outside_connector_walk,
    flow_divergence,
    shortest_connector_walk,
    shortest_omission_detour,
    shortest_outside_connector_walk,
    main,
    normalize_flow,
)
from tools.covering import cyclic_windows
from tools.flow_cp_sat import edge_prefix, extract_euler_sequence
from tools.repair_support import load_support_certificate


ROOT = Path(__file__).resolve().parents[1]
BACKBONE = ROOT / "data/candidates/l9-r1-common-backbone-64.json"
BASELINE = ROOT / "data/baseline/l9-r1-71.txt"
OVERLAP_WITNESS = (
    ROOT / "data/candidates/l9-r1-70-backbone-overlap-61.txt"
)
RETAINED = ROOT / "evidence/common-backbone-lemma-20260902"


class CommonBackboneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.support = set(load_support_certificate(BACKBONE, n=9))

    def test_bfs_and_exhaustive_connector_checks_agree(self) -> None:
        shortest = shortest_outside_connector_walk(self.support, n=9)
        self.assertEqual(
            shortest,
            [205, 411, 310, 108, 217, 435, 358],
        )
        excluded, checked = exhaustive_outside_connector_walk(
            self.support,
            n=9,
            maximum_length=6,
        )
        self.assertIsNone(excluded)
        self.assertEqual(checked, 504)
        tight = enumerate_connector_walks(
            self.support,
            n=9,
            length=7,
            forbidden_edges=self.support,
        )
        self.assertEqual(
            tight,
            [
                [205, 411, 310, 108, 217, 435, 358],
                [306, 100, 201, 403, 294, 76, 153],
            ],
        )

    def test_repeated_backbone_edges_do_not_shorten_connector(self) -> None:
        shortest = shortest_connector_walk(
            self.support,
            n=9,
            forbidden_edges=set(),
        )
        self.assertEqual(
            shortest,
            [205, 411, 310, 108, 217, 435, 358],
        )
        excluded, checked = exhaustive_connector_walk(
            self.support,
            n=9,
            maximum_length=6,
            forbidden_edges=set(),
        )
        self.assertIsNone(excluded)
        self.assertEqual(checked, 504)

    def test_all_single_omission_detours_exceed_length_70_budget(self) -> None:
        counterexample, checked = exhaustive_omission_detours(
            self.support,
            n=9,
            maximum_length=7,
        )
        self.assertIsNone(counterexample)
        self.assertEqual(checked, 16_256)

        lengths = [
            len(shortest_omission_detour(self.support, edge, n=9))
            for edge in sorted(self.support)
        ]
        self.assertEqual(min(lengths), 10)
        self.assertEqual(max(lengths), 16)
        self.assertEqual(
            {length: lengths.count(length) for length in sorted(set(lengths))},
            {10: 2, 11: 12, 12: 10, 13: 8, 14: 18, 15: 10, 16: 4},
        )

    def test_analysis_recovers_the_published_support(self) -> None:
        result = analyze_backbone(
            BACKBONE,
            baseline_path=BASELINE,
            overlap_witness_path=OVERLAP_WITNESS,
            n=9,
            radius=1,
            candidate_length=70,
        )
        self.assertEqual(
            result["backbone"]["report"]["component_edge_counts"],
            [4, 60],
        )
        self.assertEqual(
            result["simple_support_connector"][
                "minimum_closed_walk_length"
            ],
            7,
        )
        self.assertEqual(
            result["multiset_connector"]["minimum_closed_walk_length"],
            7,
        )
        self.assertEqual(
            result["single_omission_detours"][
                "minimum_detour_length_over_all_cases"
            ],
            10,
        )
        self.assertEqual(
            result["single_omission_detours"][
                "raw_start_bitstring_candidates_checked"
            ],
            16_256,
        )
        self.assertTrue(
            any(
                item["matches_baseline_support"]
                for item in result["tight_super_supports"]
            )
        )
        self.assertEqual(
            len(result["tight_super_supports"]),
            2,
        )
        self.assertEqual(
            {
                item["size"]
                for item in result["tight_super_supports"]
            },
            {71},
        )
        self.assertEqual(
            result["derived_bounds"][
                "maximum_backbone_overlap_for_candidate"
            ],
            61,
        )
        self.assertEqual(
            result["double_omission_residuals"][
                "omission_pairs_checked"
            ],
            2_016,
        )
        self.assertEqual(
            result["double_omission_residuals"][
                "distinct_residual_flows"
            ],
            168,
        )
        self.assertEqual(
            result["double_omission_residuals"][
                "connected_completion_count"
            ],
            0,
        )
        self.assertEqual(
            result["double_omission_residuals"][
                "lower_mass_positive_control"
            ]["connected_completion_count"],
            2,
        )
        self.assertEqual(
            {
                tuple(item["omitted_edges"])
                for item in result["double_omission_residuals"][
                    "lower_mass_positive_control"
                ]["connected_completions"]
            },
            {(102, 204), (307, 409)},
        )
        for completion in result["double_omission_residuals"][
            "lower_mass_positive_control"
        ]["connected_completions"]:
            omitted = set(completion["omitted_edges"])
            counts = [0] * (1 << 9)
            for edge in self.support - omitted:
                counts[edge] += 1
            for edge, multiplicity in completion["residual_flow"]:
                counts[edge] += multiplicity
            selected = {
                edge
                for edge, multiplicity in enumerate(counts)
                if multiplicity
            }
            sequence = extract_euler_sequence(
                counts,
                n=9,
                root=edge_prefix(min(selected), 9),
            )
            self.assertEqual(len(sequence), 69)
            self.assertEqual(
                len(set(cyclic_windows(sequence, 9)) & self.support),
                62,
            )
        self.assertEqual(
            result["tight_overlap_witness"]["backbone_overlap"],
            61,
        )
        self.assertFalse(
            result["tight_overlap_witness"]["valid_cover"]
        )

    def test_balanced_cycle_flow_enumeration_matches_small_multisets(
        self,
    ) -> None:
        n = 3
        maximum_mass = 4
        generated = balanced_cycle_flows(
            n=n,
            maximum_mass=maximum_mass,
        )
        for mass in range(maximum_mass + 1):
            direct = {
                normalize_flow(list(edges))
                for edges in combinations_with_replacement(
                    range(1 << n),
                    mass,
                )
                if not flow_divergence(
                    normalize_flow(list(edges)),
                    n=n,
                )
            }
            self.assertEqual(generated[mass], direct, mass)

    def test_two_omission_enumerator_matches_independent_small_oracle(
        self,
    ) -> None:
        n = 3
        support = {1, 3, 4, 6}
        vertex_mask = (1 << (n - 1)) - 1

        def divergence(edges: list[int]) -> dict[int, int]:
            values: Counter[int] = Counter()
            for edge in edges:
                values[edge >> 1] += 1
                values[edge & vertex_mask] -= 1
            return {
                vertex: value
                for vertex, value in values.items()
                if value
            }

        def connected(edges: set[int]) -> bool:
            adjacency: dict[int, set[int]] = {}
            for edge in edges:
                prefix = edge >> 1
                suffix = edge & vertex_mask
                adjacency.setdefault(prefix, set()).add(suffix)
                adjacency.setdefault(suffix, set()).add(prefix)
            if not adjacency:
                return False
            seen: set[int] = set()
            stack = [min(adjacency)]
            while stack:
                vertex = stack.pop()
                if vertex in seen:
                    continue
                seen.add(vertex)
                stack.extend(adjacency[vertex] - seen)
            return seen == set(adjacency)

        for residual_mass in range(2, 5):
            expected_flow_count = 0
            expected_connected: set[
                tuple[tuple[int, int], tuple[tuple[int, int], ...]]
            ] = set()
            for omitted_edges in combinations(sorted(support), 2):
                forbidden = set(omitted_edges)
                required = support - forbidden
                required_divergence = divergence(sorted(required))
                expected_divergence = {
                    vertex: -value
                    for vertex, value in required_divergence.items()
                }
                valid_flows: set[tuple[tuple[int, int], ...]] = set()
                for residual_edges in combinations_with_replacement(
                    range(1 << n),
                    residual_mass,
                ):
                    if forbidden.intersection(residual_edges):
                        continue
                    if divergence(list(residual_edges)) != expected_divergence:
                        continue
                    flow = tuple(sorted(Counter(residual_edges).items()))
                    valid_flows.add(flow)
                    if connected(required | set(residual_edges)):
                        expected_connected.add((omitted_edges, flow))
                expected_flow_count += len(valid_flows)

            actual = exact_two_omission_analysis(
                support,
                n=n,
                residual_mass=residual_mass,
            )
            actual_connected = {
                (
                    tuple(item["omitted_edges"]),
                    tuple(
                        tuple(pair)
                        for pair in item["residual_flow"]
                    ),
                )
                for item in actual["connected_completions"]
            }
            self.assertEqual(
                actual["distinct_residual_flows"],
                expected_flow_count,
                residual_mass,
            )
            self.assertEqual(
                actual_connected,
                expected_connected,
                residual_mass,
            )

    def test_complementary_tight_baseline_is_accepted(self) -> None:
        bits = [
            1 - int(character)
            for character in BASELINE.read_text(encoding="ascii")
            if character in {"0", "1"}
        ]
        with tempfile.TemporaryDirectory() as directory:
            complement = Path(directory) / "complement.txt"
            complement.write_text(
                "".join(str(bit) for bit in bits) + "\n",
                encoding="ascii",
            )
            result = analyze_backbone(
                BACKBONE,
                baseline_path=complement,
                n=9,
                radius=1,
                candidate_length=70,
            )
        self.assertEqual(
            sum(
                item["matches_baseline_support"]
                for item in result["tight_super_supports"]
            ),
            1,
        )

    def test_unsupported_radius_is_rejected_early(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "supports radius 0 or 1",
        ):
            analyze_backbone(
                BACKBONE,
                baseline_path=BASELINE,
                n=9,
                radius=2,
                candidate_length=70,
            )

    def test_cli_payload_is_ascii_json_compatible(self) -> None:
        result = analyze_backbone(
            BACKBONE,
            baseline_path=BASELINE,
            n=9,
            radius=1,
            candidate_length=70,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "analysis.json"
            path.write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="ascii",
            )
            self.assertEqual(
                json.loads(path.read_text(encoding="ascii")),
                result,
            )

    def test_cli_writes_the_retained_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "analysis.json"
            arguments = [
                "analyze_common_backbone.py",
                str(BACKBONE),
                str(output),
                "--baseline",
                str(BASELINE),
                "--overlap-witness",
                str(OVERLAP_WITNESS),
                "--n",
                "9",
                "--radius",
                "1",
                "--candidate-length",
                "70",
            ]
            with patch.object(sys, "argv", arguments):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(), 0)
            payload = json.loads(output.read_text(encoding="ascii"))
        self.assertEqual(
            payload["derived_bounds"][
                "maximum_backbone_overlap_for_candidate"
            ],
            61,
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
                        / "source/analyze_common_backbone_v1.py"
                    ),
                    "data/candidates/l9-r1-common-backbone-64.json",
                    str(output),
                    "--baseline",
                    "data/baseline/l9-r1-71.txt",
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

    def test_retained_manifest_authenticates_every_evidence_file(
        self,
    ) -> None:
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
                hashlib.sha256(
                    (RETAINED / relative_path).read_bytes()
                ).hexdigest(),
                expected_digest,
                relative_path,
            )


if __name__ == "__main__":
    unittest.main()
