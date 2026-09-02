#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from itertools import combinations
import json
from math import comb, gcd
from pathlib import Path
import sys
import time
from typing import Any

if __package__:
    from .covering import load_sequence, verify_sequence
else:
    from covering import load_sequence, verify_sequence


@dataclass
class ModelArtifacts:
    model: Any
    use: list[Any]
    count: list[Any]
    extra: list[Any] | None
    vertex_used: list[Any]
    flow: list[Any] | None
    parent: list[Any | None] | None
    depth: list[Any] | None
    stationarity_maxima: dict[tuple[int, int], Any]
    autocorrelation_half: dict[int, Any]
    walsh_constraint_count: int
    autocorrelation_cover_shifts: tuple[int, ...]
    autocorrelation_orbit_bounds: dict[int, int]
    pair_projection_pairs: tuple[tuple[int, int], ...]
    active_vertex_constraint: bool
    cyclic_weight_layer_constraint_count: int
    single_repeat_local_degree_constraints: int
    single_repeat_pair_balance_constraints: int
    fixed_duplicate_edge: int | None
    duplicate_kind: str
    root: int
    hint_applied: bool
    connectivity_mode: str


def hamming_ball(word: int, n: int, radius: int) -> tuple[int, ...]:
    if n <= 0 or radius < 0 or radius > n:
        raise ValueError("require n > 0 and 0 <= radius <= n")
    if word < 0 or word >= 1 << n:
        raise ValueError("word is outside the n-bit range")

    values = {word}
    for distance in range(1, radius + 1):
        for positions in combinations(range(n), distance):
            neighbor = word
            for position in positions:
                neighbor ^= 1 << position
            values.add(neighbor)
    return tuple(sorted(values))


def edge_prefix(word: int, n: int) -> int:
    if n <= 1:
        return 0
    return word >> 1


def edge_suffix(word: int, n: int) -> int:
    if n <= 1:
        return 0
    return word & ((1 << (n - 1)) - 1)


def word_substring(word: int, n: int, start: int, width: int) -> int:
    if n <= 0 or width <= 0 or start < 0 or start + width > n:
        raise ValueError("substring must lie inside a positive-width n-bit word")
    if word < 0 or word >= 1 << n:
        raise ValueError("word is outside the n-bit range")
    return (word >> (n - start - width)) & ((1 << width) - 1)


def word_projection(
    word: int,
    n: int,
    coordinates: tuple[int, ...],
) -> int:
    if n <= 0 or word < 0 or word >= 1 << n:
        raise ValueError("word must lie inside a positive-width n-bit range")
    if (
        not coordinates
        or len(set(coordinates)) != len(coordinates)
        or any(coordinate < 0 or coordinate >= n for coordinate in coordinates)
    ):
        raise ValueError("projection coordinates must be distinct and in range")

    projection = 0
    for coordinate in coordinates:
        projection = (projection << 1) | (
            (word >> (n - 1 - coordinate)) & 1
        )
    return projection


def sequence_window_counts(bits: list[int], n: int) -> list[int]:
    if n <= 0 or len(bits) < n:
        raise ValueError("require 0 < n <= sequence length")
    if any(bit not in (0, 1) for bit in bits):
        raise ValueError("sequence must contain only binary digits")

    counts = [0] * (1 << n)
    length = len(bits)
    for start in range(length):
        word = 0
        for offset in range(n):
            word = (word << 1) | bits[(start + offset) % length]
        counts[word] += 1
    return counts


def shift_distance_from_counts(
    counts: list[int],
    *,
    n: int,
    shift: int,
) -> int:
    if len(counts) != 1 << n:
        raise ValueError("edge count vector has the wrong length")
    if any(value < 0 for value in counts):
        raise ValueError("edge counts must be nonnegative")
    if shift <= 0 or shift >= n:
        raise ValueError("shift must satisfy 0 < shift < n")

    first_bit_position = n - 1
    shifted_bit_position = n - 1 - shift
    return sum(
        multiplicity
        for word, multiplicity in enumerate(counts)
        if ((word >> first_bit_position) & 1)
        != ((word >> shifted_bit_position) & 1)
    )


def de_bruijn_incidence(n: int) -> tuple[list[list[int]], list[list[int]]]:
    if n <= 0:
        raise ValueError("n must be positive")
    vertex_count = 1 << max(0, n - 1)
    outgoing = [[] for _ in range(vertex_count)]
    incoming = [[] for _ in range(vertex_count)]
    for word in range(1 << n):
        outgoing[edge_prefix(word, n)].append(word)
        incoming[edge_suffix(word, n)].append(word)
    return outgoing, incoming


def load_cp_model() -> Any:
    try:
        from ortools.sat.python import cp_model
    except ImportError as exc:
        raise RuntimeError(
            "OR-Tools is required; install requirements-solver.txt"
        ) from exc
    return cp_model


def build_flow_model(
    *,
    n: int,
    radius: int,
    length: int,
    anchor_edge: int,
    distinct_windows: bool,
    hint_bits: list[int] | None = None,
    maximize_hint_overlap: bool = False,
    connectivity_mode: str = "flow",
    connected_cycle_required: bool = False,
    at_most_length: bool = False,
    support_size: int | None = None,
    minimum_support: int | None = None,
    partition_anchor: bool = False,
    add_van_wee_constraints: bool = True,
    add_layer_constraints: bool = True,
    add_repeat_defect_constraints: bool = True,
    add_stationarity_constraints: bool = True,
    add_walsh_constraints: bool = False,
    walsh_max_order: int | None = None,
    add_autocorrelation_constraints: bool = True,
    add_autocorrelation_cover_constraints: bool = True,
    add_autocorrelation_orbit_constraints: bool = True,
    pair_projection_scope: str = "none",
    add_single_repeat_constraints: bool = True,
    duplicate_edge: int | None = None,
    duplicate_kind: str = "any",
) -> ModelArtifacts:
    if n <= 0 or length < n:
        raise ValueError("require 0 < n <= length")
    if radius < 0 or radius > n:
        raise ValueError("require 0 <= radius <= n")
    if anchor_edge not in hamming_ball(0, n, radius):
        raise ValueError("anchor edge must cover the all-zero target")
    if maximize_hint_overlap and hint_bits is None:
        raise ValueError("maximizing hint overlap requires a hint sequence")
    if connectivity_mode not in {"flow", "tree", "none"}:
        raise ValueError("connectivity mode must be flow, tree, or none")
    if not isinstance(connected_cycle_required, bool):
        raise ValueError("connected cycle requirement must be a Boolean")
    if support_size is not None and not 1 <= support_size <= length:
        raise ValueError("support size must be between 1 and length")
    if minimum_support is not None and not 1 <= minimum_support <= length:
        raise ValueError("minimum support must be between 1 and length")
    if (
        support_size is not None
        and minimum_support is not None
        and support_size < minimum_support
    ):
        raise ValueError("support size is below the minimum support")
    if (
        distinct_windows
        and support_size is not None
        and not at_most_length
        and support_size != length
    ):
        raise ValueError(
            "an exact-length distinct model has support size equal to length"
        )
    if walsh_max_order is not None and not 1 <= walsh_max_order <= n:
        raise ValueError("Walsh maximum order must be between 1 and n")
    if walsh_max_order is not None and not add_walsh_constraints:
        raise ValueError(
            "Walsh maximum order requires Walsh constraints to be enabled"
        )
    if pair_projection_scope not in {"none", "first", "all"}:
        raise ValueError(
            "pair projection scope must be none, first, or all"
        )
    if duplicate_kind not in {"any", "loop", "nonloop"}:
        raise ValueError("duplicate kind must be any, loop, or nonloop")
    if duplicate_edge is not None and not 0 <= duplicate_edge < 1 << n:
        raise ValueError("duplicate edge is outside the n-bit range")
    if duplicate_edge is not None and duplicate_kind != "any":
        duplicate_is_loop = (
            edge_prefix(duplicate_edge, n)
            == edge_suffix(duplicate_edge, n)
        )
        if duplicate_is_loop != (duplicate_kind == "loop"):
            raise ValueError(
                "duplicate edge does not match the requested duplicate kind"
            )

    cp_model = load_cp_model()
    model = cp_model.CpModel()
    word_count = 1 << n
    vertex_count = 1 << max(0, n - 1)
    outgoing, incoming = de_bruijn_incidence(n)
    maximum_multiplicity = (
        length - support_size + 1
        if support_size is not None
        else length
    )

    use = [model.new_bool_var(f"use_{word}") for word in range(word_count)]
    count = [
        model.new_int_var(0, maximum_multiplicity, f"count_{word}")
        for word in range(word_count)
    ]
    exact_single_repeat = (
        add_single_repeat_constraints
        and not distinct_windows
        and not at_most_length
        and support_size is not None
        and length - support_size == 1
    )
    if (
        (duplicate_edge is not None or duplicate_kind != "any")
        and not exact_single_repeat
    ):
        raise ValueError(
            "duplicate restrictions require an exact one-repeat stage"
        )
    extra = (
        [
            model.new_bool_var(f"extra_{word}")
            for word in range(word_count)
        ]
        if exact_single_repeat
        else None
    )
    vertex_used = [
        model.new_bool_var(f"vertex_{vertex}")
        for vertex in range(vertex_count)
    ]
    flow: list[Any] | None = None
    parent: list[Any | None] | None = None
    depth: list[Any] | None = None
    stationarity_maxima: dict[tuple[int, int], Any] = {}
    autocorrelation_half: dict[int, Any] = {}
    walsh_constraint_count = 0
    autocorrelation_cover_shifts: list[int] = []
    autocorrelation_orbit_bounds: dict[int, int] = {}
    pair_projection_counts: dict[tuple[int, int, int], Any] = {}
    pair_projection_pairs: list[tuple[int, int]] = []
    active_vertex_constraint = False
    cyclic_weight_layer_constraint_count = 0
    single_repeat_local_degree_constraints = 0
    single_repeat_pair_balance_constraints = 0
    loop_words = [
        word
        for word in range(word_count)
        if edge_prefix(word, n) == edge_suffix(word, n)
    ]
    loop_extra = (
        sum(extra[word] for word in loop_words)
        if extra is not None
        else None
    )
    total_length = sum(count)
    support_count = sum(use)

    for word in range(word_count):
        if distinct_windows:
            model.add(count[word] == use[word])
        elif extra is not None:
            model.add(count[word] == use[word] + extra[word])
            model.add(extra[word] <= use[word])
        else:
            model.add(count[word] >= use[word])
            model.add(count[word] <= maximum_multiplicity * use[word])

        prefix = edge_prefix(word, n)
        suffix = edge_suffix(word, n)
        model.add(use[word] <= vertex_used[prefix])
        model.add(use[word] <= vertex_used[suffix])

    if at_most_length:
        model.add(total_length >= n)
        model.add(total_length <= length)
    else:
        model.add(total_length == length)
    if support_size is not None:
        model.add(support_count == support_size)
    if minimum_support is not None:
        model.add(support_count >= minimum_support)
    if extra is not None:
        model.add(sum(extra) == 1)
        if duplicate_edge is not None:
            model.add(extra[duplicate_edge] == 1)
        if duplicate_kind == "loop":
            model.add(loop_extra == 1)
        elif duplicate_kind == "nonloop":
            model.add(loop_extra == 0)

    support_defects: list[Any] = []
    for vertex in range(vertex_count):
        support_out = sum(use[word] for word in outgoing[vertex])
        support_in = sum(use[word] for word in incoming[vertex])
        model.add(
            sum(count[word] for word in incoming[vertex])
            == sum(count[word] for word in outgoing[vertex])
        )
        if extra is not None:
            model.add(
                support_out - support_in
                == sum(extra[word] for word in incoming[vertex])
                - sum(extra[word] for word in outgoing[vertex])
            )
        incident = sorted(set(incoming[vertex]) | set(outgoing[vertex]))
        model.add(vertex_used[vertex] <= sum(use[word] for word in incident))
        if not distinct_windows and add_repeat_defect_constraints:
            defect = model.new_int_var(0, 2, f"support_defect_{vertex}")
            model.add_abs_equality(
                defect,
                support_out - support_in,
            )
            support_defects.append(defect)

    if support_defects:
        repeat_budget = total_length - support_count
        if extra is None:
            model.add(sum(support_defects) <= 2 * repeat_budget)
        else:
            assert loop_extra is not None
            model.add(sum(support_defects) == 2 * (1 - loop_extra))

    if extra is not None:
        for word in range(word_count):
            prefix = edge_prefix(word, n)
            suffix = edge_suffix(word, n)
            if prefix == suffix:
                continue
            model.add(
                sum(use[edge] for edge in outgoing[prefix]) == 1
            ).only_enforce_if(extra[word])
            model.add(
                sum(use[edge] for edge in incoming[prefix]) == 2
            ).only_enforce_if(extra[word])
            model.add(
                sum(use[edge] for edge in incoming[suffix]) == 1
            ).only_enforce_if(extra[word])
            model.add(
                sum(use[edge] for edge in outgoing[suffix]) == 2
            ).only_enforce_if(extra[word])
            single_repeat_local_degree_constraints += 4

    for target in range(word_count):
        model.add(sum(use[word] for word in hamming_ball(target, n, radius)) >= 1)
        if radius == 1 and add_van_wee_constraints:
            distance_one = [target ^ (1 << bit) for bit in range(n)]
            distance_two = [
                target ^ (1 << first) ^ (1 << second)
                for first, second in combinations(range(n), 2)
            ]
            threshold = (n + 2) // 2
            model.add(
                threshold * use[target]
                + sum(use[word] for word in distance_one)
                + sum(use[word] for word in distance_two)
                >= threshold
            )

    if radius == 1 and n >= 2 and pair_projection_scope != "none":
        if pair_projection_scope == "first":
            projection_pairs = [(0, second) for second in range(1, n)]
        else:
            projection_pairs = list(combinations(range(n), 2))
        pair_projection_pairs.extend(projection_pairs)
        projection_upper_bound = 1 << (n - 2)
        if support_size is not None:
            projection_upper_bound = min(
                projection_upper_bound,
                support_size,
            )

        for first, second in projection_pairs:
            for pattern in range(4):
                cell_count = model.new_int_var(
                    0,
                    projection_upper_bound,
                    f"pair_projection_{first}_{second}_{pattern}",
                )
                model.add(
                    cell_count
                    == sum(
                        use[word]
                        for word in range(word_count)
                        if word_projection(
                            word,
                            n,
                            (first, second),
                        )
                        == pattern
                    )
                )
                pair_projection_counts[(first, second, pattern)] = (
                    cell_count
                )

            for pattern in range(4):
                model.add(
                    (n - 1)
                    * pair_projection_counts[(first, second, pattern)]
                    + pair_projection_counts[
                        (first, second, pattern ^ 0b10)
                    ]
                    + pair_projection_counts[
                        (first, second, pattern ^ 0b01)
                    ]
                    >= 1 << (n - 2)
                )

            if extra is not None:
                model.add(
                    pair_projection_counts[(first, second, 0b01)]
                    + sum(
                        extra[word]
                        for word in range(word_count)
                        if word_projection(
                            word,
                            n,
                            (first, second),
                        )
                        == 0b01
                    )
                    == pair_projection_counts[
                        (first, second, 0b10)
                    ]
                    + sum(
                        extra[word]
                        for word in range(word_count)
                        if word_projection(
                            word,
                            n,
                            (first, second),
                        )
                        == 0b10
                    )
                )
                single_repeat_pair_balance_constraints += 1

    # Radius-one coverage excess bounds support pairs that share an endpoint.
    if radius == 1 and n >= 2:
        active_vertex_divisor = gcd(4, n - 3, word_count)
        model.add(
            (4 // active_vertex_divisor) * sum(vertex_used)
            + ((n - 3) // active_vertex_divisor) * support_count
            >= word_count // active_vertex_divisor
        )
        active_vertex_constraint = True

    if radius == 1 and add_layer_constraints:
        support_layers = [
            sum(
                use[word]
                for word in range(word_count)
                if bin(word).count("1") == weight
            )
            for weight in range(n + 1)
        ]
        for weight in range(n + 1):
            terms = [support_layers[weight]]
            if weight > 0:
                terms.append(
                    (n + 1 - weight) * support_layers[weight - 1]
                )
            if weight < n:
                terms.append((weight + 1) * support_layers[weight + 1])
            model.add(sum(terms) >= comb(n, weight))

        connected_cycle_guaranteed = (
            connectivity_mode != "none" or connected_cycle_required
        )
        # One cyclic component gives a closed nearest-neighbor weight walk.
        if n >= 3 and connected_cycle_guaranteed:
            multiplicity_layers = [
                sum(
                    count[word]
                    for word in range(word_count)
                    if bin(word).count("1") == weight
                )
                for weight in range(n + 1)
            ]
            for weight in range(1, n):
                model.add(support_layers[weight] >= 1)
                cyclic_weight_layer_constraint_count += 1
            for weight in range(2, n - 1):
                model.add(multiplicity_layers[weight] >= 2)
                cyclic_weight_layer_constraint_count += 1
            model.add(multiplicity_layers[1] >= 1 + use[0])
            model.add(
                multiplicity_layers[n - 1] >= 1 + use[word_count - 1]
            )
            cyclic_weight_layer_constraint_count += 2

    if not distinct_windows and add_stationarity_constraints:
        maximum_width = n - 1
        if add_repeat_defect_constraints:
            maximum_width -= 1
        for width in range(1, maximum_width + 1):
            maxima = []
            for pattern in range(1 << width):
                support_counts = [
                    sum(
                        use[word]
                        for word in range(word_count)
                        if word_substring(word, n, start, width) == pattern
                    )
                    for start in range(n - width + 1)
                ]
                maximum = model.new_int_var(
                    0,
                    1 << (n - width),
                    f"stationarity_max_{width}_{pattern}",
                )
                model.add_max_equality(maximum, support_counts)
                stationarity_maxima[(width, pattern)] = maximum
                maxima.append(maximum)
            if extra is not None:
                assert loop_extra is not None
                model.add(sum(maxima) == total_length - loop_extra)
            else:
                model.add(sum(maxima) <= total_length)

    effective_walsh_order = n if walsh_max_order is None else walsh_max_order
    if radius == 1 and add_walsh_constraints:
        for coordinate_mask in range(1, word_count):
            order = bin(coordinate_mask).count("1")
            if order > effective_walsh_order:
                continue
            eigenvalue = abs(n + 1 - 2 * order)
            if eigenvalue == 0:
                continue
            transform = sum(
                (
                    -1
                    if bin(word & coordinate_mask).count("1") % 2
                    else 1
                )
                * use[word]
                for word in range(word_count)
            )
            model.add(
                (n + 1) * support_count + eigenvalue * transform
                >= word_count
            )
            model.add(
                (n + 1) * support_count - eigenvalue * transform
                >= word_count
            )
            walsh_constraint_count += 2

    if add_autocorrelation_constraints:
        for shift in range(1, n):
            differing_words = [
                word
                for word in range(word_count)
                if ((word >> (n - 1)) & 1)
                != ((word >> (n - 1 - shift)) & 1)
            ]
            differing_word_set = set(differing_words)
            agreeing_words = [
                word
                for word in range(word_count)
                if word not in differing_word_set
            ]
            distance = sum(count[word] for word in differing_words)
            half_distance = model.new_int_var(
                0,
                length // 2,
                f"autocorrelation_half_{shift}",
            )
            model.add(distance == 2 * half_distance)
            autocorrelation_half[shift] = half_distance

            if (
                add_autocorrelation_cover_constraints
                and radius == 1
                and n >= 4
            ):
                threshold = 1 << (n - 1)
                model.add(
                    (n - 3)
                    * sum(use[word] for word in differing_words)
                    + 2 * support_count
                    >= threshold
                )
                model.add(
                    (n - 3)
                    * sum(use[word] for word in agreeing_words)
                    + 2 * support_count
                    >= threshold
                )
                autocorrelation_cover_shifts.append(shift)

            if (
                add_autocorrelation_orbit_constraints
                and not at_most_length
            ):
                orbit_count = gcd(length, shift)
                orbit_length = length // orbit_count
                if orbit_length % 2:
                    upper_bound = length - orbit_count
                    model.add(distance <= upper_bound)
                    autocorrelation_orbit_bounds[shift] = upper_bound

    anchors = hamming_ball(0, n, radius)
    anchor_index = anchors.index(anchor_edge)
    model.add(use[anchor_edge] == 1)
    if partition_anchor:
        for earlier_anchor in anchors[:anchor_index]:
            model.add(use[earlier_anchor] == 0)
    root = edge_prefix(anchor_edge, n)
    model.add(vertex_used[root] == 1)

    other_vertices = [vertex for vertex in range(vertex_count) if vertex != root]
    if connectivity_mode == "flow":
        flow_capacity = max(0, vertex_count - 1)
        flow = [
            model.new_int_var(0, flow_capacity, f"flow_{word}")
            for word in range(word_count)
        ]
        for word in range(word_count):
            model.add(flow[word] <= flow_capacity * use[word])
        for vertex in other_vertices:
            model.add(
                sum(flow[word] for word in incoming[vertex])
                - sum(flow[word] for word in outgoing[vertex])
                == vertex_used[vertex]
            )
        model.add(
            sum(flow[word] for word in outgoing[root])
            - sum(flow[word] for word in incoming[root])
            == sum(vertex_used[vertex] for vertex in other_vertices)
        )
    elif connectivity_mode == "tree":
        maximum_depth = max(0, vertex_count - 1)
        depth = [
            model.new_int_var(0, maximum_depth, f"depth_{vertex}")
            for vertex in range(vertex_count)
        ]
        model.add(depth[root] == 0)
        for vertex in other_vertices:
            model.add(depth[vertex] >= vertex_used[vertex])
            model.add(depth[vertex] <= maximum_depth * vertex_used[vertex])

        parent = [None] * word_count
        for word in range(word_count):
            prefix = edge_prefix(word, n)
            suffix = edge_suffix(word, n)
            if suffix == root or prefix == suffix:
                continue
            parent[word] = model.new_bool_var(f"parent_{word}")
            model.add(parent[word] <= use[word])
            model.add(depth[suffix] == depth[prefix] + 1).only_enforce_if(
                parent[word]
            )
        for vertex in other_vertices:
            model.add(
                sum(
                    parent[word]
                    for word in incoming[vertex]
                    if parent[word] is not None
                )
                == vertex_used[vertex]
            )

    hint_applied = False
    if hint_bits is not None:
        hint_counts = sequence_window_counts(hint_bits, n)
        hint_applied = True
        fixed_anchor_edges = set(anchors[: anchor_index + 1]) if partition_anchor else {
            anchor_edge
        }
        for word, multiplicity in enumerate(hint_counts):
            if word not in fixed_anchor_edges:
                if multiplicity <= maximum_multiplicity:
                    model.add_hint(count[word], multiplicity)
                model.add_hint(use[word], int(multiplicity > 0))
        for vertex in range(vertex_count):
            if vertex != root:
                incident = set(incoming[vertex]) | set(outgoing[vertex])
                model.add_hint(
                    vertex_used[vertex],
                    int(any(hint_counts[word] > 0 for word in incident)),
                )
        if maximize_hint_overlap:
            model.maximize(
                sum(
                    use[word]
                    for word, multiplicity in enumerate(hint_counts)
                    if multiplicity > 0
                )
            )

    return ModelArtifacts(
        model=model,
        use=use,
        count=count,
        extra=extra,
        vertex_used=vertex_used,
        flow=flow,
        parent=parent,
        depth=depth,
        stationarity_maxima=stationarity_maxima,
        autocorrelation_half=autocorrelation_half,
        walsh_constraint_count=walsh_constraint_count,
        autocorrelation_cover_shifts=tuple(
            autocorrelation_cover_shifts
        ),
        autocorrelation_orbit_bounds=autocorrelation_orbit_bounds,
        pair_projection_pairs=tuple(pair_projection_pairs),
        active_vertex_constraint=active_vertex_constraint,
        cyclic_weight_layer_constraint_count=(
            cyclic_weight_layer_constraint_count
        ),
        single_repeat_local_degree_constraints=(
            single_repeat_local_degree_constraints
        ),
        single_repeat_pair_balance_constraints=(
            single_repeat_pair_balance_constraints
        ),
        fixed_duplicate_edge=duplicate_edge,
        duplicate_kind=duplicate_kind if extra is not None else "none",
        root=root,
        hint_applied=hint_applied,
        connectivity_mode=connectivity_mode,
    )


def disconnected_components(
    counts: list[int],
    *,
    n: int,
    root: int,
) -> list[tuple[int, ...]]:
    if len(counts) != 1 << n:
        raise ValueError("edge count vector has the wrong length")
    if any(value < 0 for value in counts):
        raise ValueError("edge counts must be nonnegative")

    vertex_count = 1 << max(0, n - 1)
    adjacency = [set() for _ in range(vertex_count)]
    active: set[int] = set()
    for word, multiplicity in enumerate(counts):
        if multiplicity == 0:
            continue
        prefix = edge_prefix(word, n)
        suffix = edge_suffix(word, n)
        active.add(prefix)
        active.add(suffix)
        adjacency[prefix].add(suffix)
        adjacency[suffix].add(prefix)

    if root not in active:
        raise ValueError("root is not incident to a selected edge")

    components: list[tuple[int, ...]] = []
    unseen = set(active)
    while unseen:
        start = min(unseen)
        stack = [start]
        component: set[int] = set()
        while stack:
            vertex = stack.pop()
            if vertex in component:
                continue
            component.add(vertex)
            stack.extend(adjacency[vertex] - component)
        unseen -= component
        if root not in component:
            components.append(tuple(sorted(component)))
    return components


def add_connectivity_cuts(
    artifacts: ModelArtifacts,
    *,
    n: int,
    components: list[tuple[int, ...]],
) -> int:
    cuts_added = 0
    for component in components:
        vertices = set(component)
        entering = [
            word
            for word in range(1 << n)
            if edge_prefix(word, n) not in vertices
            and edge_suffix(word, n) in vertices
        ]
        entering_sum = sum(artifacts.use[word] for word in entering)
        for vertex in component:
            artifacts.model.add(
                artifacts.vertex_used[vertex] <= entering_sum
            )
            cuts_added += 1
    return cuts_added


def extract_euler_sequence(
    counts: list[int],
    *,
    n: int,
    root: int,
) -> list[int]:
    if len(counts) != 1 << n:
        raise ValueError("edge count vector has the wrong length")
    if any(value < 0 for value in counts):
        raise ValueError("edge counts must be nonnegative")

    remaining = counts.copy()
    outgoing, _ = de_bruijn_incidence(n)
    adjacency = [sorted(edges, reverse=True) for edges in outgoing]
    vertex_stack = [root]
    edge_stack: list[int] = []
    circuit: list[int] = []

    while vertex_stack:
        vertex = vertex_stack[-1]
        while adjacency[vertex] and remaining[adjacency[vertex][-1]] == 0:
            adjacency[vertex].pop()
        if adjacency[vertex]:
            word = adjacency[vertex][-1]
            remaining[word] -= 1
            vertex_stack.append(edge_suffix(word, n))
            edge_stack.append(word)
        else:
            vertex_stack.pop()
            if edge_stack:
                circuit.append(edge_stack.pop())

    circuit.reverse()
    expected_length = sum(counts)
    if len(circuit) != expected_length or any(remaining):
        raise ValueError("selected edge multigraph is not one Eulerian component")

    vertex = root
    for word in circuit:
        if edge_prefix(word, n) != vertex:
            raise ValueError("extracted edge order is not a directed walk")
        vertex = edge_suffix(word, n)
    if vertex != root:
        raise ValueError("extracted directed walk is not closed")

    bits = [word & 1 for word in circuit]
    if sequence_window_counts(bits, n) != counts:
        raise ValueError("extracted sequence does not reproduce model counts")
    return bits


def write_sequence(path: Path, bits: list[int]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(" ".join(str(bit) for bit in bits) + "\n", encoding="ascii")
    temporary.replace(path)


def solve_anchor(
    *,
    n: int,
    radius: int,
    length: int,
    anchor_edge: int,
    distinct_windows: bool,
    hint_bits: list[int] | None,
    time_limit: float,
    workers: int,
    seed: int,
    log_progress: bool,
    maximize_hint_overlap: bool = False,
    connectivity_mode: str = "flow",
    at_most_length: bool = False,
    support_size: int | None = None,
    minimum_support: int | None = None,
    partition_anchor: bool = False,
    add_van_wee_constraints: bool = True,
    add_layer_constraints: bool = True,
    add_repeat_defect_constraints: bool = True,
    add_stationarity_constraints: bool = True,
    add_walsh_constraints: bool = False,
    walsh_max_order: int | None = None,
    add_autocorrelation_constraints: bool = True,
    add_autocorrelation_cover_constraints: bool = True,
    add_autocorrelation_orbit_constraints: bool = True,
    pair_projection_scope: str = "none",
    add_single_repeat_constraints: bool = True,
    duplicate_edge: int | None = None,
    duplicate_kind: str = "any",
    deterministic_limit: float | None = None,
) -> tuple[dict[str, Any], list[int] | None]:
    if time_limit <= 0 or workers <= 0 or seed < 0:
        raise ValueError("time limit and workers must be positive; seed is nonnegative")
    if deterministic_limit is not None and deterministic_limit <= 0:
        raise ValueError("deterministic limit must be positive")
    if connectivity_mode not in {"flow", "tree", "cuts"}:
        raise ValueError("connectivity mode must be flow, tree, or cuts")

    cp_model = load_cp_model()
    artifacts = build_flow_model(
        n=n,
        radius=radius,
        length=length,
        anchor_edge=anchor_edge,
        distinct_windows=distinct_windows,
        hint_bits=hint_bits,
        maximize_hint_overlap=maximize_hint_overlap,
        connectivity_mode="none" if connectivity_mode == "cuts" else connectivity_mode,
        connected_cycle_required=True,
        at_most_length=at_most_length,
        support_size=support_size,
        minimum_support=minimum_support,
        partition_anchor=partition_anchor,
        add_van_wee_constraints=add_van_wee_constraints,
        add_layer_constraints=add_layer_constraints,
        add_repeat_defect_constraints=add_repeat_defect_constraints,
        add_stationarity_constraints=add_stationarity_constraints,
        add_walsh_constraints=add_walsh_constraints,
        walsh_max_order=walsh_max_order,
        add_autocorrelation_constraints=add_autocorrelation_constraints,
        add_autocorrelation_cover_constraints=(
            add_autocorrelation_cover_constraints
        ),
        add_autocorrelation_orbit_constraints=(
            add_autocorrelation_orbit_constraints
        ),
        pair_projection_scope=pair_projection_scope,
        add_single_repeat_constraints=add_single_repeat_constraints,
        duplicate_edge=duplicate_edge,
        duplicate_kind=duplicate_kind,
    )
    deadline = time.monotonic() + time_limit
    solver_calls = 0
    cut_rounds = 0
    connectivity_cuts = 0
    total_solver_wall = 0.0
    total_deterministic_time = 0.0
    total_conflicts = 0
    total_branches = 0
    total_binary_propagations = 0
    total_integer_propagations = 0
    total_restarts = 0
    total_lp_iterations = 0

    while True:
        remaining = deadline - time.monotonic()
        deterministic_remaining = (
            None
            if deterministic_limit is None
            else deterministic_limit - total_deterministic_time
        )
        if remaining <= 0 or (
            deterministic_remaining is not None
            and deterministic_remaining <= 0
        ):
            summary = {
                "anchor_edge": anchor_edge,
                "root_vertex": artifacts.root,
                "status": "UNKNOWN",
                "distinct_windows": distinct_windows,
                "hint_applied": artifacts.hint_applied,
                "maximize_hint_overlap": maximize_hint_overlap,
                "connectivity_mode": connectivity_mode,
                "length_mode": "at_most" if at_most_length else "exact",
                "length_bound": length,
                "support_size": support_size,
                "minimum_support": minimum_support,
                "partition_anchor": partition_anchor,
                "van_wee_constraints": (
                    radius == 1 and add_van_wee_constraints
                ),
                "layer_constraints": radius == 1 and add_layer_constraints,
                "active_vertex_constraint": (
                    artifacts.active_vertex_constraint
                ),
                "cyclic_weight_layer_constraint_count": (
                    artifacts.cyclic_weight_layer_constraint_count
                ),
                "repeat_defect_constraints": (
                    not distinct_windows and add_repeat_defect_constraints
                ),
                "stationarity_constraints": bool(
                    artifacts.stationarity_maxima
                ),
                "stationarity_requested": add_stationarity_constraints,
                "stationarity_widths": sorted(
                    {
                        width
                        for width, _ in artifacts.stationarity_maxima
                    }
                ),
                "stationarity_maxima": len(
                    artifacts.stationarity_maxima
                ),
                "walsh_constraints": (
                    artifacts.walsh_constraint_count > 0
                ),
                "walsh_max_order": (
                    0
                    if artifacts.walsh_constraint_count == 0
                    else n if walsh_max_order is None else walsh_max_order
                ),
                "walsh_constraint_count": (
                    artifacts.walsh_constraint_count
                ),
                "autocorrelation_constraints": bool(
                    artifacts.autocorrelation_half
                ),
                "autocorrelation_cover_shifts": list(
                    artifacts.autocorrelation_cover_shifts
                ),
                "autocorrelation_orbit_bounds": (
                    artifacts.autocorrelation_orbit_bounds
                ),
                "pair_projection_scope": (
                    "none"
                    if not artifacts.pair_projection_pairs
                    else pair_projection_scope
                ),
                "pair_projection_pairs": [
                    list(pair)
                    for pair in artifacts.pair_projection_pairs
                ],
                "pair_projection_cover_row_count": (
                    4 * len(artifacts.pair_projection_pairs)
                ),
                "pair_projection_total_constraint_count": (
                    8 * len(artifacts.pair_projection_pairs)
                    + artifacts.single_repeat_pair_balance_constraints
                ),
                "single_repeat_constraints": (
                    artifacts.extra is not None
                ),
                "single_repeat_local_degree_constraints": (
                    artifacts.single_repeat_local_degree_constraints
                ),
                "single_repeat_pair_balance_constraints": (
                    artifacts.single_repeat_pair_balance_constraints
                ),
                "fixed_duplicate_edge": artifacts.fixed_duplicate_edge,
                "duplicate_kind": artifacts.duplicate_kind,
                "single_repeat_stationarity_constraint_count": (
                    len(
                        {
                            width
                            for width, _ in artifacts.stationarity_maxima
                        }
                    )
                    if artifacts.extra is not None
                    else 0
                ),
                "wall_seconds": total_solver_wall,
                "deterministic_time": total_deterministic_time,
                "deterministic_limit": deterministic_limit,
                "conflicts": total_conflicts,
                "branches": total_branches,
                "binary_propagations": total_binary_propagations,
                "integer_propagations": total_integer_propagations,
                "restarts": total_restarts,
                "lp_iterations": total_lp_iterations,
                "solver_calls": solver_calls,
                "cut_rounds": cut_rounds,
                "connectivity_cuts": connectivity_cuts,
                "model_variables": len(artifacts.model.proto.variables),
                "model_constraints": len(artifacts.model.proto.constraints),
            }
            return summary, None

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = remaining
        if deterministic_remaining is not None:
            solver.parameters.max_deterministic_time = (
                deterministic_remaining
            )
        solver.parameters.num_search_workers = workers
        solver.parameters.random_seed = seed + solver_calls
        solver.parameters.log_search_progress = log_progress
        status = solver.solve(artifacts.model)
        solver_calls += 1
        total_solver_wall += solver.wall_time
        total_conflicts += solver.num_conflicts
        total_branches += solver.num_branches
        response = solver.response_proto
        total_deterministic_time += response.deterministic_time
        total_binary_propagations += response.num_binary_propagations
        total_integer_propagations += response.num_integer_propagations
        total_restarts += response.num_restarts
        total_lp_iterations += response.num_lp_iterations
        status_name = solver.status_name(status)

        summary = {
            "anchor_edge": anchor_edge,
            "root_vertex": artifacts.root,
            "status": status_name,
            "distinct_windows": distinct_windows,
            "hint_applied": artifacts.hint_applied,
            "maximize_hint_overlap": maximize_hint_overlap,
            "connectivity_mode": connectivity_mode,
            "length_mode": "at_most" if at_most_length else "exact",
            "length_bound": length,
            "support_size": support_size,
            "minimum_support": minimum_support,
            "partition_anchor": partition_anchor,
            "van_wee_constraints": radius == 1 and add_van_wee_constraints,
            "layer_constraints": radius == 1 and add_layer_constraints,
            "active_vertex_constraint": (
                artifacts.active_vertex_constraint
            ),
            "cyclic_weight_layer_constraint_count": (
                artifacts.cyclic_weight_layer_constraint_count
            ),
            "repeat_defect_constraints": (
                not distinct_windows and add_repeat_defect_constraints
            ),
            "stationarity_constraints": bool(
                artifacts.stationarity_maxima
            ),
            "stationarity_requested": add_stationarity_constraints,
            "stationarity_widths": sorted(
                {
                    width
                    for width, _ in artifacts.stationarity_maxima
                }
            ),
            "stationarity_maxima": len(
                artifacts.stationarity_maxima
            ),
            "walsh_constraints": (
                artifacts.walsh_constraint_count > 0
            ),
            "walsh_max_order": (
                0
                if artifacts.walsh_constraint_count == 0
                else n if walsh_max_order is None else walsh_max_order
            ),
            "walsh_constraint_count": artifacts.walsh_constraint_count,
            "autocorrelation_constraints": bool(
                artifacts.autocorrelation_half
            ),
            "autocorrelation_cover_shifts": list(
                artifacts.autocorrelation_cover_shifts
            ),
            "autocorrelation_orbit_bounds": (
                artifacts.autocorrelation_orbit_bounds
            ),
            "pair_projection_scope": (
                "none"
                if not artifacts.pair_projection_pairs
                else pair_projection_scope
            ),
            "pair_projection_pairs": [
                list(pair)
                for pair in artifacts.pair_projection_pairs
            ],
            "pair_projection_cover_row_count": (
                4 * len(artifacts.pair_projection_pairs)
            ),
            "pair_projection_total_constraint_count": (
                8 * len(artifacts.pair_projection_pairs)
                + artifacts.single_repeat_pair_balance_constraints
            ),
            "single_repeat_constraints": artifacts.extra is not None,
            "single_repeat_local_degree_constraints": (
                artifacts.single_repeat_local_degree_constraints
            ),
            "single_repeat_pair_balance_constraints": (
                artifacts.single_repeat_pair_balance_constraints
            ),
            "fixed_duplicate_edge": artifacts.fixed_duplicate_edge,
            "duplicate_kind": artifacts.duplicate_kind,
            "single_repeat_stationarity_constraint_count": (
                len(
                    {
                        width
                        for width, _ in artifacts.stationarity_maxima
                    }
                )
                if artifacts.extra is not None
                else 0
            ),
            "wall_seconds": total_solver_wall,
            "deterministic_time": total_deterministic_time,
            "deterministic_limit": deterministic_limit,
            "conflicts": total_conflicts,
            "branches": total_branches,
            "binary_propagations": total_binary_propagations,
            "integer_propagations": total_integer_propagations,
            "restarts": total_restarts,
            "lp_iterations": total_lp_iterations,
            "solver_calls": solver_calls,
            "cut_rounds": cut_rounds,
            "connectivity_cuts": connectivity_cuts,
            "model_variables": len(artifacts.model.proto.variables),
            "model_constraints": len(artifacts.model.proto.constraints),
        }

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return summary, None

        counts = [solver.value(variable) for variable in artifacts.count]
        if connectivity_mode == "cuts":
            components = disconnected_components(
                counts,
                n=n,
                root=artifacts.root,
            )
            if components:
                connectivity_cuts += add_connectivity_cuts(
                    artifacts,
                    n=n,
                    components=components,
                )
                cut_rounds += 1
                continue

        bits = extract_euler_sequence(counts, n=n, root=artifacts.root)
        sequence_length = sum(counts)
        report = verify_sequence(
            bits,
            n=n,
            radius=radius,
            expected_length=sequence_length,
        )
        summary.update(
            {
                "valid": report.valid,
                "covered_words": report.covered_words,
                "uncovered_words": list(report.uncovered_words),
                "sequence_length": sequence_length,
                "distinct_window_count": sum(value > 0 for value in counts),
                "maximum_edge_multiplicity": max(counts),
            }
        )
        if not report.valid:
            raise RuntimeError("CP-SAT model decoded to an invalid sequence")
        return summary, bits


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Solve a covering-sequence instance as a connected de Bruijn flow."
    )
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--radius", type=int, required=True)
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument("--anchor-edge", type=int, required=True)
    parser.add_argument("--time-limit", type=float, default=300.0)
    parser.add_argument("--deterministic-limit", type=float)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--hint-sequence", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--distinct-windows", action="store_true")
    parser.add_argument("--at-most-length", action="store_true")
    parser.add_argument("--support-size", type=int)
    parser.add_argument("--minimum-support", type=int)
    parser.add_argument("--partition-anchor", action="store_true")
    parser.add_argument("--no-van-wee", action="store_true")
    parser.add_argument("--no-layer-cuts", action="store_true")
    parser.add_argument("--no-repeat-defect", action="store_true")
    parser.add_argument("--no-stationarity", action="store_true")
    parser.add_argument("--walsh", action="store_true")
    parser.add_argument("--walsh-max-order", type=int)
    parser.add_argument("--no-autocorrelation", action="store_true")
    parser.add_argument("--no-autocorrelation-cover", action="store_true")
    parser.add_argument("--no-autocorrelation-orbit", action="store_true")
    parser.add_argument(
        "--pair-projection-scope",
        choices=("none", "first", "all"),
        default="none",
    )
    parser.add_argument("--no-single-repeat", action="store_true")
    parser.add_argument("--duplicate-edge", type=int)
    parser.add_argument(
        "--duplicate-kind",
        choices=("any", "loop", "nonloop"),
        default="any",
    )
    parser.add_argument("--maximize-hint-overlap", action="store_true")
    parser.add_argument(
        "--connectivity",
        choices=("flow", "tree", "cuts"),
        default="flow",
    )
    parser.add_argument("--log-progress", action="store_true")
    args = parser.parse_args()

    try:
        hint_bits = (
            load_sequence(args.hint_sequence)
            if args.hint_sequence is not None
            else None
        )
        summary, bits = solve_anchor(
            n=args.n,
            radius=args.radius,
            length=args.length,
            anchor_edge=args.anchor_edge,
            distinct_windows=args.distinct_windows,
            hint_bits=hint_bits,
            maximize_hint_overlap=args.maximize_hint_overlap,
            time_limit=args.time_limit,
            workers=args.workers,
            seed=args.seed,
            log_progress=args.log_progress,
            connectivity_mode=args.connectivity,
            at_most_length=args.at_most_length,
            support_size=args.support_size,
            minimum_support=args.minimum_support,
            partition_anchor=args.partition_anchor,
            add_van_wee_constraints=not args.no_van_wee,
            add_layer_constraints=not args.no_layer_cuts,
            add_repeat_defect_constraints=not args.no_repeat_defect,
            add_stationarity_constraints=not args.no_stationarity,
            add_walsh_constraints=(
                args.walsh or args.walsh_max_order is not None
            ),
            walsh_max_order=args.walsh_max_order,
            add_autocorrelation_constraints=not args.no_autocorrelation,
            add_autocorrelation_cover_constraints=(
                not args.no_autocorrelation_cover
            ),
            add_autocorrelation_orbit_constraints=(
                not args.no_autocorrelation_orbit
            ),
            pair_projection_scope=args.pair_projection_scope,
            add_single_repeat_constraints=not args.no_single_repeat,
            duplicate_edge=args.duplicate_edge,
            duplicate_kind=args.duplicate_kind,
            deterministic_limit=args.deterministic_limit,
        )
        if bits is not None and args.output is not None:
            write_sequence(args.output, bits)
            summary["output"] = str(args.output)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if bits is not None else 3
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
