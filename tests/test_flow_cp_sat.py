from __future__ import annotations

from collections import Counter
import importlib.util
from itertools import combinations, product
from math import comb, gcd
from pathlib import Path
import unittest

from tools.covering import load_sequence, verify_sequence
from tools.flow_cp_sat import (
    build_flow_model,
    de_bruijn_incidence,
    disconnected_components,
    extract_euler_sequence,
    hamming_ball,
    load_cp_model,
    sequence_window_counts,
    shift_distance_from_counts,
    solve_anchor,
    word_substring,
    word_projection,
)


ORTOOLS_AVAILABLE = importlib.util.find_spec("ortools") is not None
ROOT = Path(__file__).resolve().parents[1]


class FlowHelperTests(unittest.TestCase):
    def test_hamming_ball(self) -> None:
        self.assertEqual(hamming_ball(0, 3, 1), (0, 1, 2, 4))
        self.assertEqual(hamming_ball(5, 3, 0), (5,))
        self.assertEqual(len(hamming_ball(0, 4, 2)), 11)

    def test_word_substring_uses_sequence_bit_order(self) -> None:
        word = 0b10110
        self.assertEqual(word_substring(word, 5, 0, 3), 0b101)
        self.assertEqual(word_substring(word, 5, 1, 3), 0b011)
        self.assertEqual(word_substring(word, 5, 2, 3), 0b110)
        self.assertEqual(word_substring(word, 5, 4, 1), 0)

    def test_word_projection_uses_requested_coordinate_order(self) -> None:
        word = 0b10110
        self.assertEqual(word_projection(word, 5, (0, 3)), 0b11)
        self.assertEqual(word_projection(word, 5, (0, 1)), 0b10)
        self.assertEqual(word_projection(word, 5, (1, 0)), 0b01)
        self.assertEqual(word_projection(word, 5, (1, 4)), 0b00)
        self.assertEqual(word_projection(word, 5, (2, 0, 4)), 0b110)
        with self.assertRaisesRegex(ValueError, "distinct and in range"):
            word_projection(word, 5, (0, 0))

    def test_stationarity_bound_holds_for_small_cycles(self) -> None:
        for n in range(2, 5):
            for length in range(n, n + 3):
                for bits in product((0, 1), repeat=length):
                    counts = sequence_window_counts(list(bits), n)
                    support = [int(value > 0) for value in counts]
                    for width in range(1, n):
                        maximum_sum = sum(
                            max(
                                sum(
                                    support[word]
                                    for word in range(1 << n)
                                    if word_substring(
                                        word,
                                        n,
                                        start,
                                        width,
                                    )
                                    == pattern
                                )
                                for start in range(n - width + 1)
                            )
                            for pattern in range(1 << width)
                        )
                        self.assertLessEqual(
                            maximum_sum,
                            length,
                            (n, length, bits, width),
                        )

        unbalanced_support = [1, 1, 0, 0]
        maximum_sum = sum(
            max(
                sum(
                    unbalanced_support[word]
                    for word in range(4)
                    if word_substring(word, 2, start, 1) == pattern
                )
                for start in range(2)
            )
            for pattern in range(2)
        )
        self.assertEqual(maximum_sum, 3)

    def test_walsh_bound_holds_for_small_covering_supports(self) -> None:
        for n in range(1, 4):
            words = range(1 << n)
            for support_mask in range(1, 1 << (1 << n)):
                support = [
                    word
                    for word in words
                    if support_mask & (1 << word)
                ]
                if not all(
                    any(
                        bin(word ^ target).count("1") <= 1
                        for word in support
                    )
                    for target in words
                ):
                    continue
                support_size = len(support)
                excess = (n + 1) * support_size - (1 << n)
                for coordinate_mask in range(1, 1 << n):
                    order = bin(coordinate_mask).count("1")
                    transform = sum(
                        -1
                        if bin(word & coordinate_mask).count("1") % 2
                        else 1
                        for word in support
                    )
                    self.assertLessEqual(
                        abs((n + 1 - 2 * order) * transform),
                        excess,
                    )
                if n >= 2:
                    for first, second in combinations(range(n), 2):
                        projections = [
                            sum(
                                word_projection(
                                    word,
                                    n,
                                    (first, second),
                                )
                                == pattern
                                for word in support
                            )
                            for pattern in range(4)
                        ]
                        for pattern in range(4):
                            self.assertGreaterEqual(
                                (n - 1) * projections[pattern]
                                + projections[pattern ^ 0b10]
                                + projections[pattern ^ 0b01],
                                1 << (n - 2),
                            )

    def test_single_repeat_identities_hold_for_small_cycles(self) -> None:
        checked = 0
        for n in range(2, 6):
            outgoing, incoming = de_bruijn_incidence(n)
            for length in range(n, n + 3):
                for bits in product((0, 1), repeat=length):
                    counts = sequence_window_counts(list(bits), n)
                    support = [int(value > 0) for value in counts]
                    if sum(support) != length - 1:
                        continue
                    checked += 1
                    extra = [
                        multiplicity - selected
                        for multiplicity, selected in zip(counts, support)
                    ]
                    self.assertTrue(all(value in (0, 1) for value in extra))
                    self.assertEqual(sum(extra), 1)
                    duplicate = extra.index(1)
                    prefix = duplicate >> 1
                    suffix = duplicate & ((1 << (n - 1)) - 1)

                    defects = []
                    for vertex in range(1 << (n - 1)):
                        support_out = sum(
                            support[word] for word in outgoing[vertex]
                        )
                        support_in = sum(
                            support[word] for word in incoming[vertex]
                        )
                        extra_out = sum(
                            extra[word] for word in outgoing[vertex]
                        )
                        extra_in = sum(
                            extra[word] for word in incoming[vertex]
                        )
                        self.assertEqual(
                            support_out - support_in,
                            extra_in - extra_out,
                        )
                        defects.append(abs(support_out - support_in))

                    self.assertEqual(
                        sum(defects),
                        2 * int(prefix != suffix),
                    )
                    if prefix != suffix:
                        self.assertEqual(
                            sum(support[word] for word in outgoing[prefix]),
                            1,
                        )
                        self.assertEqual(
                            sum(support[word] for word in incoming[prefix]),
                            2,
                        )
                        self.assertEqual(
                            sum(support[word] for word in incoming[suffix]),
                            1,
                        )
                        self.assertEqual(
                            sum(support[word] for word in outgoing[suffix]),
                            2,
                        )

                    for width in range(1, n):
                        maximum_sum = sum(
                            max(
                                sum(
                                    support[word]
                                    for word in range(1 << n)
                                    if word_substring(
                                        word,
                                        n,
                                        start,
                                        width,
                                    )
                                    == pattern
                                )
                                for start in range(n - width + 1)
                            )
                            for pattern in range(1 << width)
                        )
                        self.assertEqual(
                            maximum_sum,
                            length - int(prefix == suffix),
                        )
        self.assertGreater(checked, 0)

    def test_shift_distance_is_direct_and_even(self) -> None:
        for n in range(2, 5):
            for length in range(n, n + 3):
                for bits in product((0, 1), repeat=length):
                    counts = sequence_window_counts(list(bits), n)
                    for shift in range(1, n):
                        distance = shift_distance_from_counts(
                            counts,
                            n=n,
                            shift=shift,
                        )
                        direct = sum(
                            bits[index]
                            != bits[(index + shift) % length]
                            for index in range(length)
                        )
                        self.assertEqual(distance, direct)
                        self.assertEqual(distance % 2, 0)

    def test_autocorrelation_bounds_hold_for_small_covering_cycles(self) -> None:
        checked = 0
        for n in (4, 5):
            for length in range(n, n + 3):
                for bits in product((0, 1), repeat=length):
                    counts = sequence_window_counts(list(bits), n)
                    support = [int(value > 0) for value in counts]
                    if not all(
                        any(support[word] for word in hamming_ball(target, n, 1))
                        for target in range(1 << n)
                    ):
                        continue
                    checked += 1
                    support_size = sum(support)
                    for shift in range(1, n):
                        distance = shift_distance_from_counts(
                            counts,
                            n=n,
                            shift=shift,
                        )
                        support_distance = sum(
                            support[word]
                            for word in range(1 << n)
                            if ((word >> (n - 1)) & 1)
                            != ((word >> (n - 1 - shift)) & 1)
                        )
                        self.assertGreaterEqual(
                            (n - 3) * support_distance
                            + 2 * support_size,
                            1 << (n - 1),
                        )
                        self.assertGreaterEqual(
                            (n - 3)
                            * (support_size - support_distance)
                            + 2 * support_size,
                            1 << (n - 1),
                        )
                        orbit_count = gcd(length, shift)
                        if (length // orbit_count) % 2:
                            self.assertLessEqual(
                                distance,
                                length - orbit_count,
                            )
        self.assertGreater(checked, 0)

    def test_structural_cut_bounds_hold_for_small_covering_cycles(self) -> None:
        checked_by_order = Counter()
        for n in range(2, 6):
            vertex_mask = (1 << (n - 1)) - 1
            for length in range(n, n + 5):
                for bits in product((0, 1), repeat=length):
                    if not verify_sequence(
                        list(bits),
                        n=n,
                        radius=1,
                        expected_length=length,
                    ).valid:
                        continue

                    checked_by_order[n] += 1
                    counts = sequence_window_counts(list(bits), n)
                    support = [int(value > 0) for value in counts]
                    support_size = sum(support)
                    active_vertices = {
                        endpoint
                        for word, selected in enumerate(support)
                        if selected
                        for endpoint in (word >> 1, word & vertex_mask)
                    }
                    self.assertGreaterEqual(
                        4 * len(active_vertices)
                        + (n - 3) * support_size,
                        1 << n,
                        (n, length, bits),
                    )

                    if n < 3:
                        continue
                    support_layers = [
                        sum(
                            support[word]
                            for word in range(1 << n)
                            if bin(word).count("1") == weight
                        )
                        for weight in range(n + 1)
                    ]
                    multiplicity_layers = [
                        sum(
                            counts[word]
                            for word in range(1 << n)
                            if bin(word).count("1") == weight
                        )
                        for weight in range(n + 1)
                    ]
                    for weight in range(1, n):
                        self.assertGreaterEqual(
                            support_layers[weight],
                            1,
                            (n, length, bits, weight),
                        )
                    for weight in range(2, n - 1):
                        self.assertGreaterEqual(
                            multiplicity_layers[weight],
                            2,
                            (n, length, bits, weight),
                        )
                    self.assertGreaterEqual(
                        multiplicity_layers[1],
                        1 + support[0],
                        (n, length, bits),
                    )
                    self.assertGreaterEqual(
                        multiplicity_layers[n - 1],
                        1 + support[-1],
                        (n, length, bits),
                    )

        self.assertEqual(set(checked_by_order), set(range(2, 6)))

    def test_active_vertex_cut_holds_for_disconnected_balanced_covers(
        self,
    ) -> None:
        checked_by_order = Counter()
        disconnected_by_order = Counter()
        for n in range(2, 5):
            word_count = 1 << n
            vertex_mask = (1 << (n - 1)) - 1
            outgoing, incoming = de_bruijn_incidence(n)
            for support_mask in range(1, 1 << word_count):
                support = [
                    (support_mask >> word) & 1
                    for word in range(word_count)
                ]
                if any(
                    sum(support[word] for word in outgoing[vertex])
                    != sum(support[word] for word in incoming[vertex])
                    for vertex in range(len(outgoing))
                ):
                    continue
                if any(
                    not any(
                        support[word]
                        for word in hamming_ball(target, n, 1)
                    )
                    for target in range(word_count)
                ):
                    continue

                checked_by_order[n] += 1
                support_size = sum(support)
                active_vertices = {
                    endpoint
                    for word, selected in enumerate(support)
                    if selected
                    for endpoint in (word >> 1, word & vertex_mask)
                }
                self.assertGreaterEqual(
                    4 * len(active_vertices)
                    + (n - 3) * support_size,
                    word_count,
                    (n, support_mask),
                )
                root = min(active_vertices)
                if disconnected_components(
                    support,
                    n=n,
                    root=root,
                ):
                    disconnected_by_order[n] += 1

        self.assertEqual(set(checked_by_order), set(range(2, 5)))
        self.assertGreater(disconnected_by_order[4], 0)

    def test_euler_extraction_reproduces_window_counts(self) -> None:
        bits = [0, 0, 0, 1, 0, 1, 1, 1]
        counts = sequence_window_counts(bits, 3)
        extracted = extract_euler_sequence(counts, n=3, root=0)
        self.assertEqual(sequence_window_counts(extracted, 3), counts)
        self.assertTrue(verify_sequence(extracted, n=3, radius=0).valid)

    def test_disconnected_balanced_counts_are_rejected(self) -> None:
        counts = [1, 0, 0, 1]
        self.assertEqual(
            disconnected_components(counts, n=2, root=0),
            [(1,)],
        )
        with self.assertRaisesRegex(ValueError, "one Eulerian component"):
            extract_euler_sequence(counts, n=2, root=0)

    def test_all_order_nine_edges_extract_to_a_de_bruijn_cycle(self) -> None:
        counts = [1] * (1 << 9)
        extracted = extract_euler_sequence(counts, n=9, root=0)
        report = verify_sequence(extracted, n=9, radius=0)
        self.assertTrue(report.valid)
        self.assertEqual(len(extracted), 512)
        self.assertEqual(report.distinct_windows, 512)

    def test_repeated_baseline_edges_preserve_multiplicity(self) -> None:
        baseline = load_sequence(ROOT / "data/baseline/l9-r1-71.txt")
        counts = [
            2 * value for value in sequence_window_counts(baseline, 9)
        ]
        extracted = extract_euler_sequence(counts, n=9, root=8)
        report = verify_sequence(extracted, n=9, radius=1)
        self.assertTrue(report.valid)
        self.assertEqual(len(extracted), 142)
        self.assertEqual(report.distinct_windows, 71)
        self.assertEqual(
            report.coverage_histogram,
            {2: 391, 4: 51, 6: 63, 8: 7},
        )

    def test_incomplete_seed_extracts_with_the_same_six_gaps(self) -> None:
        seed = load_sequence(
            ROOT / "data/candidates/l9-r1-70-uncovered-6.txt"
        )
        counts = sequence_window_counts(seed, 9)
        extracted = extract_euler_sequence(counts, n=9, root=32)
        report = verify_sequence(extracted, n=9, radius=1)
        self.assertFalse(report.valid)
        self.assertEqual(
            report.uncovered_words,
            (30, 60, 61, 156, 206, 286),
        )


@unittest.skipUnless(ORTOOLS_AVAILABLE, "OR-Tools is not installed")
class FlowCpSatTests(unittest.TestCase):
    def test_tiny_instance_feasibility_matches_direct_enumeration(self) -> None:
        for connectivity_mode in ("flow", "tree", "cuts"):
            for n in (1, 2, 3):
                for length in range(n, min(n + 3, 6)):
                    direct_exists = any(
                        verify_sequence(
                            list(bits),
                            n=n,
                            radius=1,
                            expected_length=length,
                        ).valid
                        for bits in product((0, 1), repeat=length)
                    )
                    model_exists = False
                    for anchor in hamming_ball(0, n, 1):
                        summary, bits = solve_anchor(
                            n=n,
                            radius=1,
                            length=length,
                            anchor_edge=anchor,
                            distinct_windows=False,
                            hint_bits=None,
                            time_limit=5,
                            workers=1,
                            seed=1,
                            log_progress=False,
                            connectivity_mode=connectivity_mode,
                            partition_anchor=True,
                        )
                        self.assertNotEqual(summary["status"], "UNKNOWN")
                        model_exists |= bits is not None
                    self.assertEqual(
                        model_exists,
                        direct_exists,
                        (connectivity_mode, n, length),
                    )

    def test_minimum_support_is_enforced(self) -> None:
        cp_model = load_cp_model()
        common = {
            "n": 2,
            "radius": 1,
            "length": 3,
            "anchor_edge": 1,
            "distinct_windows": True,
            "connectivity_mode": "flow",
            "at_most_length": True,
            "partition_anchor": True,
        }
        relaxed = build_flow_model(**common)
        relaxed.model.add(sum(relaxed.count) == 2)
        relaxed_solver = cp_model.CpSolver()
        self.assertIn(
            relaxed_solver.solve(relaxed.model),
            {cp_model.OPTIMAL, cp_model.FEASIBLE},
        )

        constrained = build_flow_model(**common, minimum_support=3)
        constrained.model.add(sum(constrained.count) == 2)
        constrained_solver = cp_model.CpSolver()
        self.assertEqual(
            constrained_solver.solve(constrained.model),
            cp_model.INFEASIBLE,
        )

    def test_tight_repeat_defect_candidate_is_accepted(self) -> None:
        hint = [0, 0, 1, 0, 1]
        summary, bits = solve_anchor(
            n=3,
            radius=1,
            length=5,
            anchor_edge=1,
            distinct_windows=False,
            hint_bits=hint,
            time_limit=5,
            workers=1,
            seed=1,
            log_progress=False,
            maximize_hint_overlap=True,
            connectivity_mode="cuts",
            support_size=4,
            minimum_support=4,
            partition_anchor=True,
        )
        self.assertIn(summary["status"], {"OPTIMAL", "FEASIBLE"})
        self.assertIsNotNone(bits)
        assert bits is not None

        counts = sequence_window_counts(bits, 3)
        support = [int(value > 0) for value in counts]
        outgoing, incoming = de_bruijn_incidence(3)
        defect = sum(
            abs(
                sum(support[word] for word in outgoing[vertex])
                - sum(support[word] for word in incoming[vertex])
            )
            for vertex in range(len(outgoing))
        )
        repeat_budget = sum(counts) - sum(support)
        self.assertEqual(defect, 2)
        self.assertEqual(repeat_budget, 1)
        self.assertEqual(defect, 2 * repeat_budget)

    def test_layer_strengthening_encodes_expected_inequalities(self) -> None:
        n = 3
        common = {
            "n": n,
            "radius": 1,
            "length": 5,
            "anchor_edge": 1,
            "distinct_windows": False,
            "connectivity_mode": "none",
            "support_size": 4,
            "minimum_support": 4,
            "partition_anchor": True,
        }
        with_layers = build_flow_model(**common, add_layer_constraints=True)
        without_layers = build_flow_model(
            **common,
            add_layer_constraints=False,
        )

        def linear_signature(constraint: object) -> tuple[object, ...]:
            return (
                tuple(constraint.enforcement_literal),
                tuple(constraint.linear.vars),
                tuple(constraint.linear.coeffs),
                tuple(constraint.linear.domain),
            )

        with_signatures = Counter(
            linear_signature(constraint)
            for constraint in with_layers.model.proto.constraints
            if constraint.has_linear()
        )
        without_signatures = Counter(
            linear_signature(constraint)
            for constraint in without_layers.model.proto.constraints
            if constraint.has_linear()
        )

        expected = Counter()
        cp_model = load_cp_model()
        for weight in range(n + 1):
            coefficients: dict[int, int] = {}
            for word, variable in enumerate(with_layers.use):
                word_weight = bin(word).count("1")
                coefficient = 0
                if word_weight == weight:
                    coefficient += 1
                if weight > 0 and word_weight == weight - 1:
                    coefficient += n + 1 - weight
                if weight < n and word_weight == weight + 1:
                    coefficient += weight + 1
                if coefficient:
                    coefficients[variable.index] = coefficient
            ordered = sorted(coefficients.items())
            expected[
                (
                    (),
                    tuple(index for index, _ in ordered),
                    tuple(coefficient for _, coefficient in ordered),
                    (comb(n, weight), cp_model.INT_MAX),
                )
            ] += 1

        self.assertEqual(with_signatures - without_signatures, expected)

    def test_active_vertex_constraint_has_expected_coefficients(self) -> None:
        n = 9
        artifacts = build_flow_model(
            n=n,
            radius=1,
            length=70,
            anchor_edge=0,
            distinct_windows=False,
            connectivity_mode="none",
            add_van_wee_constraints=False,
            add_layer_constraints=False,
            add_repeat_defect_constraints=False,
            add_stationarity_constraints=False,
            add_autocorrelation_constraints=False,
        )
        self.assertTrue(artifacts.active_vertex_constraint)

        divisor = gcd(4, n - 3, 1 << n)
        coefficients = {
            variable.index: (n - 3) // divisor
            for variable in artifacts.use
        }
        coefficients.update(
            {
                variable.index: 4 // divisor
                for variable in artifacts.vertex_used
            }
        )
        ordered = sorted(coefficients.items())
        expected = (
            (),
            tuple(index for index, _ in ordered),
            tuple(coefficient for _, coefficient in ordered),
            ((1 << n) // divisor, load_cp_model().INT_MAX),
        )
        signatures = Counter(
            (
                tuple(constraint.enforcement_literal),
                tuple(constraint.linear.vars),
                tuple(constraint.linear.coeffs),
                tuple(constraint.linear.domain),
            )
            for constraint in artifacts.model.proto.constraints
            if constraint.has_linear()
        )
        self.assertEqual(signatures[expected], 1)

        order_one = build_flow_model(
            n=1,
            radius=1,
            length=1,
            anchor_edge=0,
            distinct_windows=False,
            connectivity_mode="none",
        )
        radius_two = build_flow_model(
            n=3,
            radius=2,
            length=3,
            anchor_edge=0,
            distinct_windows=False,
            connectivity_mode="none",
        )
        self.assertFalse(order_one.active_vertex_constraint)
        self.assertFalse(radius_two.active_vertex_constraint)

    def test_cyclic_weight_layer_path_coefficients_and_gates(self) -> None:
        n = 4
        common = {
            "n": n,
            "radius": 1,
            "length": 6,
            "anchor_edge": 0,
            "distinct_windows": False,
            "connectivity_mode": "none",
            "add_van_wee_constraints": False,
            "add_layer_constraints": True,
            "add_repeat_defect_constraints": False,
            "add_stationarity_constraints": False,
            "add_autocorrelation_constraints": False,
        }
        disconnected = build_flow_model(**common)
        connected = build_flow_model(
            **common,
            add_cyclic_weight_path_constraints=True,
        )

        def linear_signature(constraint: object) -> tuple[object, ...]:
            return (
                tuple(constraint.enforcement_literal),
                tuple(constraint.linear.vars),
                tuple(constraint.linear.coeffs),
                tuple(constraint.linear.domain),
            )

        connected_signatures = Counter(
            linear_signature(constraint)
            for constraint in connected.model.proto.constraints
            if constraint.has_linear()
        )
        disconnected_signatures = Counter(
            linear_signature(constraint)
            for constraint in disconnected.model.proto.constraints
            if constraint.has_linear()
        )

        cp_model = load_cp_model()
        expected = Counter()

        def add_expected(
            coefficients: dict[int, int],
            lower_bound: int,
        ) -> None:
            ordered = sorted(coefficients.items())
            expected[
                (
                    (),
                    tuple(index for index, _ in ordered),
                    tuple(coefficient for _, coefficient in ordered),
                    (lower_bound, cp_model.INT_MAX),
                )
            ] += 1

        for weight in range(1, n):
            add_expected(
                {
                    variable.index: 1
                    for word, variable in enumerate(connected.use)
                    if bin(word).count("1") == weight
                },
                1,
            )
        for weight in range(2, n - 1):
            add_expected(
                {
                    variable.index: 1
                    for word, variable in enumerate(connected.count)
                    if bin(word).count("1") == weight
                },
                2,
            )
        add_expected(
            {
                **{
                    variable.index: 1
                    for word, variable in enumerate(connected.count)
                    if bin(word).count("1") == 1
                },
                connected.use[0].index: -1,
            },
            1,
        )
        add_expected(
            {
                **{
                    variable.index: 1
                    for word, variable in enumerate(connected.count)
                    if bin(word).count("1") == n - 1
                },
                connected.use[-1].index: -1,
            },
            1,
        )

        self.assertEqual(
            connected_signatures - disconnected_signatures,
            expected,
        )
        self.assertEqual(
            connected.cyclic_weight_layer_constraint_count,
            2 * n - 2,
        )
        self.assertEqual(
            disconnected.cyclic_weight_layer_constraint_count,
            0,
        )

        without_layers = build_flow_model(
            **{**common, "add_layer_constraints": False},
            add_cyclic_weight_path_constraints=True,
        )
        order_two = build_flow_model(
            n=2,
            radius=1,
            length=2,
            anchor_edge=0,
            distinct_windows=False,
            connectivity_mode="flow",
        )
        radius_two = build_flow_model(
            n=4,
            radius=2,
            length=6,
            anchor_edge=0,
            distinct_windows=False,
            connectivity_mode="flow",
        )
        self.assertEqual(
            without_layers.cyclic_weight_layer_constraint_count,
            0,
        )
        self.assertEqual(
            order_two.cyclic_weight_layer_constraint_count,
            0,
        )
        self.assertEqual(
            radius_two.cyclic_weight_layer_constraint_count,
            0,
        )

    def test_stationarity_and_autocorrelation_match_fixed_cycle(self) -> None:
        cp_model = load_cp_model()
        bits = [0, 0, 1, 0, 1]
        counts = sequence_window_counts(bits, 3)
        artifacts = build_flow_model(
            n=3,
            radius=1,
            length=5,
            anchor_edge=1,
            distinct_windows=False,
            connectivity_mode="none",
            support_size=4,
            minimum_support=4,
            partition_anchor=True,
            add_walsh_constraints=False,
        )
        for index, variable in enumerate(artifacts.count):
            artifacts.model.add(variable == counts[index])

        solver = cp_model.CpSolver()
        status = solver.solve(artifacts.model)
        self.assertIn(status, {cp_model.OPTIMAL, cp_model.FEASIBLE})

        support = [int(value > 0) for value in counts]
        self.assertIsNotNone(artifacts.extra)
        assert artifacts.extra is not None
        extra = [solver.value(variable) for variable in artifacts.extra]
        self.assertEqual(
            extra,
            [max(0, multiplicity - 1) for multiplicity in counts],
        )
        loop_extra = sum(
            extra[word]
            for word in range(1 << 3)
            if (word >> 1) == (word & 0b11)
        )
        self.assertEqual(
            set(artifacts.stationarity_maxima),
            {(1, 0), (1, 1)},
        )
        for (width, pattern), variable in (
            artifacts.stationarity_maxima.items()
        ):
            self.assertEqual(
                list(
                    artifacts.model.proto.variables[
                        variable.index
                    ].domain
                ),
                [0, 1 << (3 - width)],
            )
            expected = max(
                sum(
                    support[word]
                    for word in range(1 << 3)
                    if word_substring(word, 3, start, width) == pattern
                )
                for start in range(3 - width + 1)
            )
            self.assertEqual(solver.value(variable), expected)
        self.assertEqual(
            sum(
                solver.value(variable)
                for variable in artifacts.stationarity_maxima.values()
            ),
            len(bits) - loop_extra,
        )

        for shift, variable in artifacts.autocorrelation_half.items():
            self.assertEqual(
                2 * solver.value(variable),
                shift_distance_from_counts(counts, n=3, shift=shift),
            )

    def test_stationarity_skip_cases_and_at_most_rhs(self) -> None:
        cp_model = load_cp_model()
        common = {
            "n": 3,
            "radius": 1,
            "length": 5,
            "anchor_edge": 1,
            "connectivity_mode": "none",
            "partition_anchor": True,
            "add_walsh_constraints": False,
            "add_autocorrelation_constraints": False,
        }
        default = build_flow_model(
            **common,
            distinct_windows=False,
        )
        self.assertEqual(
            set(default.stationarity_maxima),
            {(1, 0), (1, 1)},
        )

        without_repeat_defect = build_flow_model(
            **common,
            distinct_windows=False,
            add_repeat_defect_constraints=False,
        )
        self.assertEqual(
            set(without_repeat_defect.stationarity_maxima),
            {
                (1, 0),
                (1, 1),
                (2, 0),
                (2, 1),
                (2, 2),
                (2, 3),
            },
        )
        for (width, _), variable in (
            without_repeat_defect.stationarity_maxima.items()
        ):
            self.assertEqual(
                list(
                    without_repeat_defect.model.proto.variables[
                        variable.index
                    ].domain
                ),
                [0, 1 << (3 - width)],
            )

        distinct = build_flow_model(
            **common,
            distinct_windows=True,
        )
        self.assertFalse(distinct.stationarity_maxima)

        disabled = build_flow_model(
            **common,
            distinct_windows=False,
            add_stationarity_constraints=False,
        )
        self.assertFalse(disabled.stationarity_maxima)

        order_one = build_flow_model(
            n=1,
            radius=1,
            length=1,
            anchor_edge=0,
            distinct_windows=False,
            connectivity_mode="none",
        )
        self.assertFalse(order_one.stationarity_maxima)

        at_most = build_flow_model(
            **common,
            distinct_windows=False,
            at_most_length=True,
        )
        maximum_indices = {
            variable.index
            for variable in at_most.stationarity_maxima.values()
        }
        count_indices = {
            variable.index
            for variable in at_most.count
        }
        matching_constraints = []
        for constraint in at_most.model.proto.constraints:
            if not constraint.has_linear():
                continue
            coefficients = dict(
                zip(
                    constraint.linear.vars,
                    constraint.linear.coeffs,
                )
            )
            if (
                set(coefficients) == maximum_indices | count_indices
                and all(
                    coefficients[index] == 1
                    for index in maximum_indices
                )
                and all(
                    coefficients[index] == -1
                    for index in count_indices
                )
                and list(constraint.linear.domain)
                == [cp_model.INT_MIN, 0]
            ):
                matching_constraints.append(constraint)
        self.assertEqual(len(matching_constraints), 1)

    def test_summary_reports_effective_strengthening(self) -> None:
        summary, bits = solve_anchor(
            n=3,
            radius=1,
            length=5,
            anchor_edge=1,
            distinct_windows=False,
            hint_bits=[0, 0, 1, 0, 1],
            time_limit=5,
            workers=1,
            seed=1,
            log_progress=False,
            connectivity_mode="cuts",
            support_size=4,
            minimum_support=4,
            partition_anchor=True,
        )
        self.assertIsNotNone(bits)
        self.assertTrue(summary["stationarity_requested"])
        self.assertTrue(summary["stationarity_constraints"])
        self.assertTrue(summary["active_vertex_constraint"])
        self.assertEqual(
            summary["cyclic_weight_layer_constraint_count"],
            4,
        )
        self.assertEqual(summary["stationarity_widths"], [1])
        self.assertEqual(summary["stationarity_maxima"], 2)
        self.assertFalse(summary["walsh_constraints"])
        self.assertEqual(summary["walsh_max_order"], 0)
        self.assertEqual(summary["walsh_constraint_count"], 0)
        self.assertTrue(summary["autocorrelation_constraints"])
        self.assertEqual(
            summary["autocorrelation_cover_shifts"],
            [],
        )
        self.assertEqual(
            summary["autocorrelation_orbit_bounds"],
            {1: 4, 2: 4},
        )
        self.assertEqual(summary["pair_projection_scope"], "none")
        self.assertEqual(summary["pair_projection_cover_row_count"], 0)
        self.assertEqual(summary["pair_projection_total_constraint_count"], 0)
        self.assertTrue(summary["single_repeat_constraints"])
        self.assertEqual(
            summary["single_repeat_local_degree_constraints"],
            24,
        )
        self.assertEqual(
            summary["single_repeat_pair_balance_constraints"],
            0,
        )
        self.assertIsNone(summary["fixed_duplicate_edge"])
        self.assertEqual(summary["duplicate_kind"], "any")
        self.assertEqual(
            summary["single_repeat_stationarity_constraint_count"],
            1,
        )

        order_one_summary, order_one_bits = solve_anchor(
            n=1,
            radius=1,
            length=1,
            anchor_edge=0,
            distinct_windows=False,
            hint_bits=None,
            time_limit=5,
            workers=1,
            seed=1,
            log_progress=False,
            add_walsh_constraints=True,
        )
        self.assertIsNotNone(order_one_bits)
        self.assertFalse(order_one_summary["active_vertex_constraint"])
        self.assertEqual(
            order_one_summary["cyclic_weight_layer_constraint_count"],
            0,
        )
        self.assertFalse(order_one_summary["walsh_constraints"])
        self.assertEqual(order_one_summary["walsh_max_order"], 0)
        self.assertEqual(order_one_summary["walsh_constraint_count"], 0)
        self.assertEqual(
            order_one_summary["pair_projection_cover_row_count"],
            0,
        )

    def test_walsh_strengthening_encodes_expected_inequalities(self) -> None:
        n = 3
        common = {
            "n": n,
            "radius": 1,
            "length": 5,
            "anchor_edge": 1,
            "distinct_windows": False,
            "connectivity_mode": "none",
            "support_size": 4,
            "minimum_support": 4,
            "partition_anchor": True,
            "add_stationarity_constraints": False,
            "add_autocorrelation_constraints": False,
        }
        with_walsh = build_flow_model(
            **common,
            add_walsh_constraints=True,
        )
        without_walsh = build_flow_model(
            **common,
            add_walsh_constraints=False,
        )

        def linear_signature(constraint: object) -> tuple[object, ...]:
            return (
                tuple(constraint.enforcement_literal),
                tuple(constraint.linear.vars),
                tuple(constraint.linear.coeffs),
                tuple(constraint.linear.domain),
            )

        with_signatures = Counter(
            linear_signature(constraint)
            for constraint in with_walsh.model.proto.constraints
            if constraint.has_linear()
        )
        without_signatures = Counter(
            linear_signature(constraint)
            for constraint in without_walsh.model.proto.constraints
            if constraint.has_linear()
        )

        cp_model = load_cp_model()
        expected = Counter()
        for coordinate_mask in range(1, 1 << n):
            order = bin(coordinate_mask).count("1")
            eigenvalue = abs(n + 1 - 2 * order)
            if eigenvalue == 0:
                continue
            for direction in (-1, 1):
                coefficients = {}
                for word, variable in enumerate(with_walsh.use):
                    character = (
                        -1
                        if bin(word & coordinate_mask).count("1") % 2
                        else 1
                    )
                    coefficients[variable.index] = (
                        n + 1
                        + direction * eigenvalue * character
                    )
                ordered = sorted(
                    (index, coefficient)
                    for index, coefficient in coefficients.items()
                    if coefficient
                )
                expected[
                    (
                        (),
                        tuple(index for index, _ in ordered),
                        tuple(coefficient for _, coefficient in ordered),
                        (1 << n, cp_model.INT_MAX),
                    )
                ] += 1

        self.assertEqual(with_signatures - without_signatures, expected)

    def test_invalid_walsh_max_order_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Walsh maximum order"):
            build_flow_model(
                n=3,
                radius=1,
                length=5,
                anchor_edge=1,
                distinct_windows=False,
                walsh_max_order=4,
            )
        with self.assertRaisesRegex(
            ValueError,
            "requires Walsh constraints",
        ):
            build_flow_model(
                n=3,
                radius=1,
                length=5,
                anchor_edge=1,
                distinct_windows=False,
                walsh_max_order=2,
            )

    def test_walsh_max_order_filters_masks(self) -> None:
        common = {
            "n": 3,
            "radius": 1,
            "length": 5,
            "anchor_edge": 1,
            "distinct_windows": False,
            "connectivity_mode": "none",
            "add_stationarity_constraints": False,
            "add_autocorrelation_constraints": False,
            "add_walsh_constraints": True,
        }
        order_one = build_flow_model(
            **common,
            walsh_max_order=1,
        )
        all_orders = build_flow_model(**common)

        self.assertEqual(order_one.walsh_constraint_count, 6)
        self.assertEqual(all_orders.walsh_constraint_count, 8)

    def test_autocorrelation_cover_and_orbit_encodings(self) -> None:
        n = 4
        common = {
            "n": n,
            "radius": 1,
            "length": 6,
            "anchor_edge": 1,
            "distinct_windows": False,
            "connectivity_mode": "none",
            "add_stationarity_constraints": False,
            "add_walsh_constraints": False,
            "add_autocorrelation_constraints": True,
        }
        full = build_flow_model(**common)
        without_cover = build_flow_model(
            **common,
            add_autocorrelation_cover_constraints=False,
        )
        without_orbit = build_flow_model(
            **common,
            add_autocorrelation_orbit_constraints=False,
        )
        at_most = build_flow_model(
            **common,
            at_most_length=True,
        )

        self.assertEqual(
            full.autocorrelation_cover_shifts,
            (1, 2, 3),
        )
        self.assertEqual(
            full.autocorrelation_orbit_bounds,
            {2: 4},
        )
        self.assertFalse(without_cover.autocorrelation_cover_shifts)
        self.assertFalse(without_orbit.autocorrelation_orbit_bounds)
        self.assertFalse(at_most.autocorrelation_orbit_bounds)

        def linear_signature(constraint: object) -> tuple[object, ...]:
            return (
                tuple(constraint.enforcement_literal),
                tuple(constraint.linear.vars),
                tuple(constraint.linear.coeffs),
                tuple(constraint.linear.domain),
            )

        full_signatures = Counter(
            linear_signature(constraint)
            for constraint in full.model.proto.constraints
            if constraint.has_linear()
        )
        no_cover_signatures = Counter(
            linear_signature(constraint)
            for constraint in without_cover.model.proto.constraints
            if constraint.has_linear()
        )
        no_orbit_signatures = Counter(
            linear_signature(constraint)
            for constraint in without_orbit.model.proto.constraints
            if constraint.has_linear()
        )

        cp_model = load_cp_model()
        expected_cover = Counter()
        support_indices = {
            variable.index
            for variable in full.use
        }
        for shift in range(1, n):
            differing_words = {
                word
                for word in range(1 << n)
                if ((word >> (n - 1)) & 1)
                != ((word >> (n - 1 - shift)) & 1)
            }
            agreeing_words = set(range(1 << n)) - differing_words
            for selected_words in (differing_words, agreeing_words):
                coefficients = {
                    variable.index: (
                        2 + (n - 3 if word in selected_words else 0)
                    )
                    for word, variable in enumerate(full.use)
                }
                ordered = sorted(coefficients.items())
                expected_cover[
                    (
                        (),
                        tuple(index for index, _ in ordered),
                        tuple(
                            coefficient
                            for _, coefficient in ordered
                        ),
                        (1 << (n - 1), cp_model.INT_MAX),
                    )
                ] += 1
        self.assertEqual(
            full_signatures - no_cover_signatures,
            expected_cover,
        )

        shift_two_indices = tuple(
            full.count[word].index
            for word in range(1 << n)
            if ((word >> (n - 1)) & 1)
            != ((word >> (n - 3)) & 1)
        )
        expected_orbit = Counter(
            {
                (
                    (),
                    shift_two_indices,
                    (1,) * len(shift_two_indices),
                    (cp_model.INT_MIN, 4),
                ): 1
            }
        )
        self.assertEqual(
            full_signatures - no_orbit_signatures,
            expected_orbit,
        )

    def test_autocorrelation_cover_coefficients_scale_with_n(self) -> None:
        common = {
            "n": 5,
            "radius": 1,
            "length": 6,
            "anchor_edge": 1,
            "distinct_windows": False,
            "connectivity_mode": "none",
            "add_stationarity_constraints": False,
            "add_walsh_constraints": False,
            "add_autocorrelation_constraints": True,
            "add_autocorrelation_orbit_constraints": False,
        }
        with_cover = build_flow_model(**common)
        without_cover = build_flow_model(
            **common,
            add_autocorrelation_cover_constraints=False,
        )

        def signatures(artifacts: object) -> Counter:
            return Counter(
                (
                    tuple(constraint.enforcement_literal),
                    tuple(constraint.linear.vars),
                    tuple(constraint.linear.coeffs),
                    tuple(constraint.linear.domain),
                )
                for constraint in artifacts.model.proto.constraints
                if constraint.has_linear()
            )

        extra = signatures(with_cover) - signatures(without_cover)
        self.assertEqual(sum(extra.values()), 8)
        for signature, multiplicity in extra.items():
            _, variables, coefficients, domain = signature
            self.assertEqual(multiplicity, 1)
            self.assertEqual(len(variables), 32)
            self.assertEqual(set(coefficients), {2, 4})
            self.assertEqual(
                domain,
                (1 << 4, load_cp_model().INT_MAX),
            )

    def test_pair_projection_scope_controls_exact_cover_rows(self) -> None:
        common = {
            "n": 4,
            "radius": 1,
            "length": 6,
            "anchor_edge": 1,
            "distinct_windows": False,
            "connectivity_mode": "none",
            "add_stationarity_constraints": False,
            "add_walsh_constraints": False,
            "add_autocorrelation_constraints": False,
        }
        none = build_flow_model(**common, pair_projection_scope="none")
        first = build_flow_model(**common, pair_projection_scope="first")
        all_pairs = build_flow_model(**common, pair_projection_scope="all")

        self.assertEqual(none.pair_projection_pairs, ())
        self.assertEqual(
            first.pair_projection_pairs,
            ((0, 1), (0, 2), (0, 3)),
        )
        self.assertEqual(len(all_pairs.pair_projection_pairs), comb(4, 2))
        self.assertEqual(
            len(first.model.proto.variables)
            - len(none.model.proto.variables),
            4 * 3,
        )
        self.assertEqual(
            len(first.model.proto.constraints)
            - len(none.model.proto.constraints),
            8 * 3,
        )
        self.assertEqual(
            len(all_pairs.model.proto.variables)
            - len(none.model.proto.variables),
            4 * comb(4, 2),
        )
        self.assertEqual(
            len(all_pairs.model.proto.constraints)
            - len(none.model.proto.constraints),
            8 * comb(4, 2),
        )

        exact_common = {
            **common,
            "length": 5,
            "support_size": 4,
            "minimum_support": 4,
        }
        exact_none = build_flow_model(
            **exact_common,
            pair_projection_scope="none",
        )
        exact_first = build_flow_model(
            **exact_common,
            pair_projection_scope="first",
        )
        self.assertEqual(
            len(exact_first.model.proto.variables)
            - len(exact_none.model.proto.variables),
            4 * 3,
        )
        self.assertEqual(
            len(exact_first.model.proto.constraints)
            - len(exact_none.model.proto.constraints),
            9 * 3,
        )

    def test_single_repeat_extension_is_exact_and_optional(self) -> None:
        common = {
            "n": 3,
            "radius": 1,
            "length": 5,
            "anchor_edge": 1,
            "distinct_windows": False,
            "connectivity_mode": "none",
            "support_size": 4,
            "minimum_support": 4,
            "partition_anchor": True,
            "pair_projection_scope": "first",
        }
        exact = build_flow_model(**common)
        generic = build_flow_model(
            **common,
            add_single_repeat_constraints=False,
        )

        self.assertIsNotNone(exact.extra)
        self.assertIsNone(generic.extra)
        self.assertEqual(
            exact.single_repeat_local_degree_constraints,
            24,
        )
        self.assertEqual(
            exact.single_repeat_pair_balance_constraints,
            2,
        )
        self.assertEqual(generic.single_repeat_local_degree_constraints, 0)
        self.assertEqual(generic.single_repeat_pair_balance_constraints, 0)

    def test_invalid_pair_projection_scope_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "pair projection scope"):
            build_flow_model(
                n=3,
                radius=1,
                length=5,
                anchor_edge=1,
                distinct_windows=False,
                pair_projection_scope="cyclic",
            )

    def test_duplicate_restrictions_are_enforced_and_reported(self) -> None:
        bits = [0, 0, 1, 0, 1]
        counts = sequence_window_counts(bits, 3)
        duplicate = next(
            word
            for word, multiplicity in enumerate(counts)
            if multiplicity == 2
        )
        artifacts = build_flow_model(
            n=3,
            radius=1,
            length=5,
            anchor_edge=1,
            distinct_windows=False,
            connectivity_mode="none",
            support_size=4,
            minimum_support=4,
            partition_anchor=True,
            duplicate_edge=duplicate,
            duplicate_kind="nonloop",
        )
        assert artifacts.extra is not None
        for word, variable in enumerate(artifacts.count):
            artifacts.model.add(variable == counts[word])

        solver = load_cp_model().CpSolver()
        self.assertIn(
            solver.solve(artifacts.model),
            {load_cp_model().OPTIMAL, load_cp_model().FEASIBLE},
        )
        self.assertEqual(solver.value(artifacts.extra[duplicate]), 1)
        self.assertEqual(artifacts.fixed_duplicate_edge, duplicate)
        self.assertEqual(artifacts.duplicate_kind, "nonloop")

        summary, solved_bits = solve_anchor(
            n=3,
            radius=1,
            length=5,
            anchor_edge=1,
            distinct_windows=False,
            hint_bits=bits,
            time_limit=5,
            workers=1,
            seed=1,
            log_progress=False,
            connectivity_mode="cuts",
            support_size=4,
            minimum_support=4,
            partition_anchor=True,
            duplicate_edge=duplicate,
            duplicate_kind="nonloop",
        )
        self.assertIsNotNone(solved_bits)
        self.assertEqual(summary["fixed_duplicate_edge"], duplicate)
        self.assertEqual(summary["duplicate_kind"], "nonloop")

        loop_bits = [0, 0, 0, 1]
        loop_counts = sequence_window_counts(loop_bits, 2)
        loop_artifacts = build_flow_model(
            n=2,
            radius=1,
            length=4,
            anchor_edge=0,
            distinct_windows=False,
            connectivity_mode="none",
            support_size=3,
            minimum_support=3,
            partition_anchor=True,
            duplicate_edge=0,
            duplicate_kind="loop",
        )
        assert loop_artifacts.extra is not None
        for word, variable in enumerate(loop_artifacts.count):
            loop_artifacts.model.add(variable == loop_counts[word])
        loop_solver = load_cp_model().CpSolver()
        self.assertIn(
            loop_solver.solve(loop_artifacts.model),
            {load_cp_model().OPTIMAL, load_cp_model().FEASIBLE},
        )
        self.assertEqual(loop_solver.value(loop_artifacts.extra[0]), 1)
        self.assertEqual(loop_artifacts.duplicate_kind, "loop")

    def test_invalid_duplicate_restrictions_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate kind"):
            build_flow_model(
                n=3,
                radius=1,
                length=5,
                anchor_edge=1,
                distinct_windows=False,
                duplicate_kind="diagonal",
            )
        with self.assertRaisesRegex(ValueError, "outside"):
            build_flow_model(
                n=3,
                radius=1,
                length=5,
                anchor_edge=1,
                distinct_windows=False,
                support_size=4,
                duplicate_edge=8,
            )
        with self.assertRaisesRegex(ValueError, "one-repeat"):
            build_flow_model(
                n=3,
                radius=1,
                length=5,
                anchor_edge=1,
                distinct_windows=False,
                duplicate_kind="loop",
            )

    def test_connectivity_rejects_two_disconnected_loops(self) -> None:
        for connectivity_mode in ("flow", "tree", "cuts"):
            summary, bits = solve_anchor(
                n=2,
                radius=1,
                length=2,
                anchor_edge=0,
                distinct_windows=True,
                hint_bits=None,
                time_limit=5,
                workers=1,
                seed=1,
                log_progress=False,
                connectivity_mode=connectivity_mode,
            )
            self.assertEqual(summary["status"], "INFEASIBLE")
            self.assertIsNone(bits)

    def test_disconnected_sampling_omits_cyclic_weight_layer_paths(self) -> None:
        cp_model = load_cp_model()
        common = {
            "n": 3,
            "radius": 1,
            "length": 4,
            "anchor_edge": 0,
            "distinct_windows": False,
            "connectivity_mode": "none",
            "support_size": 2,
            "add_stationarity_constraints": False,
        }
        disconnected = build_flow_model(**common)
        connected_only = build_flow_model(
            **common,
            add_cyclic_weight_path_constraints=True,
        )
        counts = [2, 0, 0, 0, 0, 0, 0, 2]
        for word, multiplicity in enumerate(counts):
            disconnected.model.add(
                disconnected.count[word] == multiplicity
            )
            connected_only.model.add(
                connected_only.count[word] == multiplicity
            )

        disconnected_solver = cp_model.CpSolver()
        self.assertIn(
            disconnected_solver.solve(disconnected.model),
            {cp_model.OPTIMAL, cp_model.FEASIBLE},
        )
        connected_solver = cp_model.CpSolver()
        self.assertEqual(
            connected_solver.solve(connected_only.model),
            cp_model.INFEASIBLE,
        )
        self.assertTrue(disconnected.active_vertex_constraint)
        self.assertEqual(
            disconnected.cyclic_weight_layer_constraint_count,
            0,
        )
        self.assertEqual(
            connected_only.cyclic_weight_layer_constraint_count,
            4,
        )

    def test_support_stage_accepts_repeated_edges(self) -> None:
        hint = [0, 0, 1, 0, 1]
        for connectivity_mode in ("flow", "tree", "cuts"):
            summary, bits = solve_anchor(
                n=2,
                radius=1,
                length=5,
                anchor_edge=0,
                distinct_windows=False,
                hint_bits=hint,
                time_limit=5,
                workers=1,
                seed=1,
                log_progress=False,
                connectivity_mode=connectivity_mode,
                support_size=3,
                partition_anchor=True,
            )
            self.assertIn(summary["status"], {"OPTIMAL", "FEASIBLE"})
            self.assertIsNotNone(bits)
            assert bits is not None
            self.assertEqual(len(bits), 5)
            self.assertEqual(summary["distinct_window_count"], 3)
            self.assertLessEqual(summary["maximum_edge_multiplicity"], 3)
            self.assertTrue(
                verify_sequence(
                    bits,
                    n=2,
                    radius=1,
                    expected_length=5,
                ).valid
            )

    def test_at_most_mode_respects_the_length_bound(self) -> None:
        found: list[int] | None = None
        for anchor in hamming_ball(0, 2, 1):
            _, bits = solve_anchor(
                n=2,
                radius=1,
                length=3,
                anchor_edge=anchor,
                distinct_windows=True,
                hint_bits=None,
                time_limit=5,
                workers=1,
                seed=1,
                log_progress=False,
                connectivity_mode="cuts",
                at_most_length=True,
                partition_anchor=True,
            )
            if bits is not None:
                found = bits
                break
        self.assertIsNotNone(found)
        assert found is not None
        self.assertGreaterEqual(len(found), 2)
        self.assertLessEqual(len(found), 3)
        self.assertTrue(verify_sequence(found, n=2, radius=1).valid)

    def test_incompatible_exact_distinct_support_size_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "support size equal to length"):
            solve_anchor(
                n=2,
                radius=1,
                length=3,
                anchor_edge=0,
                distinct_windows=True,
                hint_bits=None,
                time_limit=5,
                workers=1,
                seed=1,
                log_progress=False,
                support_size=2,
            )

    def test_known_length_71_certificate_is_a_positive_control(self) -> None:
        baseline = load_sequence(ROOT / "data/baseline/l9-r1-71.txt")
        summary, bits = solve_anchor(
            n=9,
            radius=1,
            length=71,
            anchor_edge=16,
            distinct_windows=True,
            hint_bits=baseline,
            time_limit=10,
            workers=1,
            seed=1,
            log_progress=False,
        )
        self.assertIn(summary["status"], {"OPTIMAL", "FEASIBLE"})
        self.assertTrue(summary["hint_applied"])
        self.assertIsNotNone(bits)
        assert bits is not None
        self.assertTrue(
            verify_sequence(
                bits,
                n=9,
                radius=1,
                expected_length=71,
            ).valid
        )


if __name__ == "__main__":
    unittest.main()
