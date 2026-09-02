#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, deque
from hashlib import sha256
from itertools import combinations, permutations, product
import json
from pathlib import Path
from typing import Any

try:
    from .covering import load_sequence, verify_sequence
    from .flow_cp_sat import (
        edge_prefix,
        edge_suffix,
        extract_euler_sequence,
    )
    from .repair_support import (
        analyze_support,
        load_support_certificate,
        support_digest,
    )
except ImportError:
    from covering import load_sequence, verify_sequence
    from flow_cp_sat import edge_prefix, edge_suffix, extract_euler_sequence
    from repair_support import (
        analyze_support,
        load_support_certificate,
        support_digest,
    )


def file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def sequence_support(bits: list[int], n: int) -> set[int]:
    return {
        sum(
            bits[(start + offset) % len(bits)] << (n - 1 - offset)
            for offset in range(n)
        )
        for start in range(len(bits))
    }


Flow = tuple[tuple[int, int], ...]


def normalize_flow(edges: list[int] | tuple[int, ...]) -> Flow:
    return tuple(sorted(Counter(edges).items()))


def add_flows(first: Flow, second: Flow) -> Flow:
    counts = Counter(dict(first))
    counts.update(dict(second))
    return tuple(sorted(counts.items()))


def flow_mass(flow: Flow) -> int:
    return sum(multiplicity for _, multiplicity in flow)


def flow_support(flow: Flow) -> set[int]:
    return {edge for edge, multiplicity in flow if multiplicity > 0}


def flow_divergence(flow: Flow, *, n: int) -> dict[int, int]:
    divergence: Counter[int] = Counter()
    for edge, multiplicity in flow:
        divergence[edge_prefix(edge, n)] += multiplicity
        divergence[edge_suffix(edge, n)] -= multiplicity
    return {
        vertex: value
        for vertex, value in divergence.items()
        if value
    }


def cyclic_word_edges(value: int, *, length: int, n: int) -> list[int]:
    if length <= 0 or value < 0 or value >= 1 << length:
        raise ValueError("cyclic word is outside its positive-length range")
    bits = [
        (value >> (length - 1 - index)) & 1
        for index in range(length)
    ]
    edges: list[int] = []
    for start in range(length):
        edge = 0
        for offset in range(n):
            edge = (edge << 1) | bits[(start + offset) % length]
        edges.append(edge)
    return edges


def balanced_cycle_flows(
    *,
    n: int,
    maximum_mass: int,
) -> list[set[Flow]]:
    if n <= 0 or maximum_mass < 0:
        raise ValueError("require positive n and nonnegative mass")

    closed_walks: list[set[Flow]] = [set()]
    for length in range(1, maximum_mass + 1):
        closed_walks.append(
            {
                normalize_flow(
                    cyclic_word_edges(value, length=length, n=n)
                )
                for value in range(1 << length)
            }
        )

    balanced: list[set[Flow]] = [set() for _ in range(maximum_mass + 1)]
    balanced[0].add(())
    for total in range(1, maximum_mass + 1):
        for length in range(1, total + 1):
            for prior in balanced[total - length]:
                for closed_walk in closed_walks[length]:
                    balanced[total].add(
                        add_flows(prior, closed_walk)
                    )
        for flow in balanced[total]:
            if flow_mass(flow) != total or flow_divergence(flow, n=n):
                raise RuntimeError(
                    "closed-walk decomposition produced an invalid flow"
                )
    return balanced


def directed_walks(
    source: int,
    target: int,
    *,
    n: int,
    maximum_length: int,
    forbidden_edges: set[int],
) -> list[tuple[int, ...]]:
    if maximum_length <= 0:
        raise ValueError("maximum walk length must be positive")

    walks: list[tuple[int, ...]] = []
    for length in range(1, maximum_length + 1):
        for appended_bits in product((0, 1), repeat=length):
            vertex = source
            edges: list[int] = []
            for bit in appended_bits:
                edge = (vertex << 1) | bit
                edges.append(edge)
                vertex = edge_suffix(edge, n)
            if (
                vertex == target
                and forbidden_edges.isdisjoint(edges)
            ):
                walks.append(tuple(edges))
    return walks


def support_components(support: set[int], n: int) -> list[set[int]]:
    vertex_count = 1 << max(0, n - 1)
    adjacency = [set() for _ in range(vertex_count)]
    active: set[int] = set()
    for edge in support:
        prefix = edge_prefix(edge, n)
        suffix = edge_suffix(edge, n)
        active.add(prefix)
        active.add(suffix)
        adjacency[prefix].add(suffix)
        adjacency[suffix].add(prefix)

    components: list[set[int]] = []
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
        components.append(component)
    components.sort(key=lambda component: (len(component), min(component)))
    return components


def exact_two_omission_analysis(
    support: set[int],
    *,
    n: int,
    residual_mass: int,
) -> dict[str, Any]:
    if residual_mass <= 0:
        raise ValueError("two-omission residual mass must be positive")
    if residual_mass > 8:
        raise ValueError(
            "two-omission enumeration supports residual mass at most 8"
        )

    balanced_flows = balanced_cycle_flows(
        n=n,
        maximum_mass=residual_mass,
    )
    source_count_histogram: Counter[int] = Counter()
    residual_flow_count_histogram: Counter[int] = Counter()
    active_cases: list[dict[str, Any]] = []
    total_path_flows = 0
    total_raw_decompositions = 0
    total_residual_flows = 0
    connected_completions: list[dict[str, Any]] = []

    for omitted_edges in combinations(sorted(support), 2):
        forbidden = set(omitted_edges)
        required = support - forbidden
        residual_divergence: Counter[int] = Counter()
        for edge in required:
            residual_divergence[edge_prefix(edge, n)] -= 1
            residual_divergence[edge_suffix(edge, n)] += 1

        sources: list[int] = []
        sinks: list[int] = []
        for vertex in sorted(residual_divergence):
            value = residual_divergence[vertex]
            if value > 0:
                sources.extend([vertex] * value)
            elif value < 0:
                sinks.extend([vertex] * (-value))
        if not 1 <= len(sources) == len(sinks) <= 2:
            raise RuntimeError(
                "two omissions produced an unsupported divergence pattern"
            )
        source_count_histogram[len(sources)] += 1

        path_flows: set[Flow] = set()
        raw_decompositions: list[tuple[Flow, Flow]] = []
        for sink_order in sorted(set(permutations(sinks))):
            walk_options = [
                directed_walks(
                    source,
                    sink,
                    n=n,
                    maximum_length=residual_mass,
                    forbidden_edges=forbidden,
                )
                for source, sink in zip(sources, sink_order)
            ]
            for paths in product(*walk_options):
                path_length = sum(len(path) for path in paths)
                if path_length > residual_mass:
                    continue
                path_flow = normalize_flow(
                    [
                        edge
                        for path in paths
                        for edge in path
                    ]
                )
                path_flows.add(path_flow)
                for cycle_flow in balanced_flows[
                    residual_mass - path_length
                ]:
                    if forbidden & flow_support(cycle_flow):
                        continue
                    raw_decompositions.append(
                        (path_flow, cycle_flow)
                    )

        residual_flows = {
            add_flows(path_flow, cycle_flow)
            for path_flow, cycle_flow in raw_decompositions
        }
        expected_divergence = {
            vertex: value
            for vertex, value in residual_divergence.items()
            if value
        }
        component_histogram: Counter[int] = Counter()
        for residual_flow in residual_flows:
            if flow_mass(residual_flow) != residual_mass:
                raise RuntimeError("residual flow has the wrong mass")
            if forbidden & flow_support(residual_flow):
                raise RuntimeError("residual flow uses an omitted edge")
            if flow_divergence(residual_flow, n=n) != expected_divergence:
                raise RuntimeError(
                    "residual flow has the wrong divergence"
                )

            combined_support = required | flow_support(residual_flow)
            component_count = len(
                support_components(combined_support, n)
            )
            component_histogram[component_count] += 1
            if component_count == 1:
                connected_completions.append(
                    {
                        "omitted_edges": list(omitted_edges),
                        "residual_flow": [
                            [edge, multiplicity]
                            for edge, multiplicity in residual_flow
                        ],
                    }
                )

        total_path_flows += len(path_flows)
        total_raw_decompositions += len(raw_decompositions)
        total_residual_flows += len(residual_flows)
        residual_flow_count_histogram[len(residual_flows)] += 1
        if residual_flows:
            active_cases.append(
                {
                    "omitted_edges": list(omitted_edges),
                    "source_vertices": sources,
                    "sink_vertices": sinks,
                    "distinct_path_flows": len(path_flows),
                    "raw_exact_decompositions": len(
                        raw_decompositions
                    ),
                    "distinct_residual_flows": len(residual_flows),
                    "combined_component_count_histogram": {
                        str(count): component_histogram[count]
                        for count in sorted(component_histogram)
                    },
                }
            )

    return {
        "residual_mass": residual_mass,
        "omission_pairs_checked": len(support) * (len(support) - 1) // 2,
        "source_count_histogram": {
            str(count): source_count_histogram[count]
            for count in sorted(source_count_histogram)
        },
        "balanced_cycle_flow_counts_by_mass": [
            len(flows) for flows in balanced_flows
        ],
        "distinct_path_flows": total_path_flows,
        "raw_exact_decompositions": total_raw_decompositions,
        "distinct_residual_flows": total_residual_flows,
        "residual_flow_count_histogram": {
            str(count): residual_flow_count_histogram[count]
            for count in sorted(residual_flow_count_histogram)
        },
        "active_omission_cases": active_cases,
        "connected_completion_count": len(connected_completions),
        "connected_completions": connected_completions,
    }


def reconstruct_walk(
    parent: dict[
        tuple[int, bool],
        tuple[tuple[int, bool], int],
    ],
    state: tuple[int, bool],
) -> list[int]:
    walk: list[int] = []
    while state in parent:
        state, edge = parent[state]
        walk.append(edge)
    walk.reverse()
    return walk


def shortest_connector_walk(
    support: set[int],
    *,
    n: int,
    forbidden_edges: set[int],
) -> list[int]:
    components = support_components(support, n)
    if len(components) != 2:
        raise ValueError("connector analysis requires exactly two components")
    first, second = components

    best: list[int] | None = None
    for start in sorted(first):
        initial = (start, False)
        queue = deque([initial])
        distance = {initial: 0}
        parent: dict[
            tuple[int, bool],
            tuple[tuple[int, bool], int],
        ] = {}
        while queue:
            state = queue.popleft()
            vertex, touched_second = state
            if state == (start, True):
                walk = reconstruct_walk(parent, state)
                if best is None or (len(walk), walk) < (len(best), best):
                    best = walk
                break
            for bit in (0, 1):
                edge = (vertex << 1) | bit
                if edge in forbidden_edges:
                    continue
                suffix = edge_suffix(edge, n)
                next_state = (
                    suffix,
                    touched_second or suffix in second,
                )
                if next_state in distance:
                    continue
                distance[next_state] = distance[state] + 1
                parent[next_state] = (state, edge)
                queue.append(next_state)

    if best is None:
        raise ValueError("no outside connector walk exists")
    return best


def shortest_outside_connector_walk(
    support: set[int],
    *,
    n: int,
) -> list[int]:
    return shortest_connector_walk(
        support,
        n=n,
        forbidden_edges=support,
    )


def exhaustive_connector_walk(
    support: set[int],
    *,
    n: int,
    maximum_length: int,
    forbidden_edges: set[int],
) -> tuple[list[int] | None, int]:
    if maximum_length <= 0:
        raise ValueError("maximum length must be positive")
    components = support_components(support, n)
    if len(components) != 2:
        raise ValueError("connector analysis requires exactly two components")
    first, second = components

    candidates = 0
    for length in range(1, maximum_length + 1):
        for start in sorted(first):
            for appended_bits in product((0, 1), repeat=length):
                candidates += 1
                vertex = start
                touched_second = False
                walk: list[int] = []
                for bit in appended_bits:
                    edge = (vertex << 1) | bit
                    if edge in forbidden_edges:
                        break
                    walk.append(edge)
                    vertex = edge_suffix(edge, n)
                    touched_second = touched_second or vertex in second
                else:
                    if vertex == start and touched_second:
                        return walk, candidates
    return None, candidates


def exhaustive_outside_connector_walk(
    support: set[int],
    *,
    n: int,
    maximum_length: int,
) -> tuple[list[int] | None, int]:
    return exhaustive_connector_walk(
        support,
        n=n,
        maximum_length=maximum_length,
        forbidden_edges=support,
    )


def enumerate_connector_walks(
    support: set[int],
    *,
    n: int,
    length: int,
    forbidden_edges: set[int],
) -> list[list[int]]:
    if length <= 0:
        raise ValueError("connector length must be positive")
    components = support_components(support, n)
    if len(components) != 2:
        raise ValueError("connector analysis requires exactly two components")
    first, second = components

    connectors: list[list[int]] = []
    for start in sorted(first):
        for appended_bits in product((0, 1), repeat=length):
            vertex = start
            touched_second = False
            walk: list[int] = []
            for bit in appended_bits:
                edge = (vertex << 1) | bit
                if edge in forbidden_edges:
                    break
                walk.append(edge)
                vertex = edge_suffix(edge, n)
                touched_second = (
                    touched_second or vertex in second
                )
            else:
                if vertex == start and touched_second:
                    connectors.append(walk)
    return connectors


def omission_endpoints(
    support: set[int],
    omitted_edge: int,
    *,
    n: int,
) -> tuple[int, int, set[int]]:
    if omitted_edge not in support:
        raise ValueError("omitted edge is not in the backbone")
    components = support_components(support, n)
    if len(components) != 2:
        raise ValueError("omission analysis requires exactly two components")

    source = edge_prefix(omitted_edge, n)
    target = edge_suffix(omitted_edge, n)
    component_index = next(
        index
        for index, component in enumerate(components)
        if source in component
    )
    if target not in components[component_index]:
        raise ValueError("backbone edge crosses its own weak components")
    return source, target, components[1 - component_index]


def shortest_omission_detour(
    support: set[int],
    omitted_edge: int,
    *,
    n: int,
) -> list[int]:
    source, target, other_component = omission_endpoints(
        support,
        omitted_edge,
        n=n,
    )
    initial = (source, False)
    queue = deque([initial])
    distance = {initial: 0}
    parent: dict[
        tuple[int, bool],
        tuple[tuple[int, bool], int],
    ] = {}
    while queue:
        state = queue.popleft()
        vertex, touched_other = state
        if vertex == target and touched_other:
            return reconstruct_walk(parent, state)
        for bit in (0, 1):
            edge = (vertex << 1) | bit
            if edge == omitted_edge:
                continue
            suffix = edge_suffix(edge, n)
            next_state = (
                suffix,
                touched_other or suffix in other_component,
            )
            if next_state in distance:
                continue
            distance[next_state] = distance[state] + 1
            parent[next_state] = (state, edge)
            queue.append(next_state)
    raise ValueError("no omission detour exists")


def exhaustive_omission_detours(
    support: set[int],
    *,
    n: int,
    maximum_length: int,
) -> tuple[dict[str, Any] | None, int]:
    if maximum_length <= 0:
        raise ValueError("maximum length must be positive")

    candidates = 0
    for omitted_edge in sorted(support):
        source, target, other_component = omission_endpoints(
            support,
            omitted_edge,
            n=n,
        )
        for length in range(1, maximum_length + 1):
            for appended_bits in product((0, 1), repeat=length):
                candidates += 1
                vertex = source
                touched_other = False
                walk: list[int] = []
                for bit in appended_bits:
                    edge = (vertex << 1) | bit
                    if edge == omitted_edge:
                        break
                    walk.append(edge)
                    vertex = edge_suffix(edge, n)
                    touched_other = (
                        touched_other or vertex in other_component
                    )
                else:
                    if vertex == target and touched_other:
                        return (
                            {
                                "omitted_edge": omitted_edge,
                                "walk": walk,
                            },
                            candidates,
                        )
    return None, candidates


def analyze_backbone(
    support_path: Path,
    *,
    baseline_path: Path,
    overlap_witness_path: Path | None = None,
    n: int,
    radius: int,
    candidate_length: int,
) -> dict[str, Any]:
    if n <= 0:
        raise ValueError("n must be positive")
    if radius not in {0, 1}:
        raise ValueError("backbone analysis supports radius 0 or 1")
    if candidate_length <= 0:
        raise ValueError("candidate length must be positive")

    support_list = load_support_certificate(support_path, n=n)
    support = set(support_list)
    report = analyze_support(support_list, n=n, radius=radius)
    if not report["balanced"]:
        raise ValueError("backbone support is not balanced")
    if report["covered_words"] != 1 << n:
        raise ValueError("backbone support is not a complete cover")
    if report["component_count"] != 2:
        raise ValueError("backbone support does not have two components")

    components = support_components(support, n)
    component_edges = [
        sorted(
            edge
            for edge in support
            if edge_prefix(edge, n) in component
        )
        for component in components
    ]
    components_are_directed_cycles = all(
        len(edges) == len(component)
        and all(
            sum(edge_prefix(edge, n) == vertex for edge in edges) == 1
            and sum(edge_suffix(edge, n) == vertex for edge in edges) == 1
            for vertex in component
        )
        for component, edges in zip(components, component_edges)
    )
    if not components_are_directed_cycles:
        raise ValueError("backbone components are not directed cycles")
    if any(
        edge_prefix(edge, n) == edge_suffix(edge, n)
        for edge in support
    ):
        raise ValueError("backbone omission argument requires no loops")

    shortest_simple = shortest_outside_connector_walk(support, n=n)
    simple_short, checked_simple_short = exhaustive_outside_connector_walk(
        support,
        n=n,
        maximum_length=len(shortest_simple) - 1,
    )
    if simple_short is not None:
        raise RuntimeError("exhaustive check found a shorter connector walk")
    simple_tight_connectors = enumerate_connector_walks(
        support,
        n=n,
        length=len(shortest_simple),
        forbidden_edges=support,
    )
    if shortest_simple not in simple_tight_connectors:
        raise RuntimeError("exhaustive check did not recover the tight length")

    shortest_multiset = shortest_connector_walk(
        support,
        n=n,
        forbidden_edges=set(),
    )
    multiset_short, checked_multiset_short = exhaustive_connector_walk(
        support,
        n=n,
        maximum_length=len(shortest_multiset) - 1,
        forbidden_edges=set(),
    )
    if multiset_short is not None:
        raise RuntimeError(
            "unrestricted enumeration found a shorter connector walk"
        )
    multiset_tight_connectors = enumerate_connector_walks(
        support,
        n=n,
        length=len(shortest_multiset),
        forbidden_edges=set(),
    )
    if shortest_multiset not in multiset_tight_connectors:
        raise RuntimeError(
            "unrestricted enumeration did not recover the tight length"
        )

    simple_support_lower_bound = (
        len(support) + len(shortest_simple)
    )
    multiset_lower_bound = (
        len(support) + len(shortest_multiset)
    )
    residual_budget = candidate_length - (len(support) - 1)
    if residual_budget <= 0:
        raise ValueError(
            "candidate length is too short for a single omission"
        )
    short_detour, checked_detours = exhaustive_omission_detours(
        support,
        n=n,
        maximum_length=residual_budget,
    )
    omission_cases: list[dict[str, Any]] = []
    detour_histogram: dict[str, int] = {}
    for omitted_edge in sorted(support):
        detour = shortest_omission_detour(
            support,
            omitted_edge,
            n=n,
        )
        length_key = str(len(detour))
        detour_histogram[length_key] = (
            detour_histogram.get(length_key, 0) + 1
        )
        omission_cases.append(
            {
                "omitted_edge": omitted_edge,
                "source": edge_prefix(omitted_edge, n),
                "target": edge_suffix(omitted_edge, n),
                "minimum_detour_length": len(detour),
                "witness_edges": detour,
            }
        )

    baseline_bits = load_sequence(baseline_path)
    baseline_support = sequence_support(baseline_bits, n)
    baseline_report = verify_sequence(
        baseline_bits,
        n=n,
        radius=radius,
        expected_length=len(baseline_bits),
    )
    if not baseline_report.valid:
        raise ValueError("baseline sequence is invalid")

    tight_super_supports: list[dict[str, Any]] = []
    for connector in simple_tight_connectors:
        witness = set(connector)
        if len(witness) != len(connector):
            raise RuntimeError("minimum connector walk repeats an edge")
        super_support = support | witness
        super_report = analyze_support(
            sorted(super_support),
            n=n,
            radius=radius,
        )
        if not (
            super_report["balanced"]
            and super_report["covered_words"] == 1 << n
            and super_report["component_count"] == 1
        ):
            raise RuntimeError(
                "minimum connector does not form a connected cover"
            )

        counts = [
            int(edge in super_support)
            for edge in range(1 << n)
        ]
        root = edge_prefix(min(super_support), n)
        sequence = extract_euler_sequence(counts, n=n, root=root)
        sequence_report = verify_sequence(
            sequence,
            n=n,
            radius=radius,
            expected_length=len(super_support),
        )
        if not sequence_report.valid:
            raise RuntimeError(
                "minimum connector did not decode to a valid cycle"
            )
        tight_super_supports.append(
            {
                "connector_edges": connector,
                "size": len(super_support),
                "support_sha256": support_digest(
                    sorted(super_support)
                ),
                "report": super_report,
                "decoded_sequence_valid": sequence_report.valid,
                "matches_baseline_support": (
                    baseline_support == super_support
                ),
            }
        )

    if not any(
        item["matches_baseline_support"]
        for item in tight_super_supports
    ):
        raise RuntimeError(
            "no minimum connector super-support matches the baseline"
        )

    vertices = [
        edge_prefix(shortest_simple[0], n),
        *(edge_suffix(edge, n) for edge in shortest_simple),
    ]
    minimum_detour = min(
        case["minimum_detour_length"]
        for case in omission_cases
    )
    all_backbone_edges_excluded = (
        candidate_length < multiset_lower_bound
    )
    single_omission_excluded = (
        residual_budget < minimum_detour
        and residual_budget - 1 < len(shortest_multiset)
    )
    two_omission_budget = candidate_length - (len(support) - 2)
    two_omission_analysis = exact_two_omission_analysis(
        support,
        n=n,
        residual_mass=two_omission_budget,
    )
    if two_omission_budget > 1:
        lower_mass_analysis = exact_two_omission_analysis(
            support,
            n=n,
            residual_mass=two_omission_budget - 1,
        )
        two_omission_analysis["lower_mass_positive_control"] = {
            "residual_mass": lower_mass_analysis["residual_mass"],
            "distinct_residual_flows": lower_mass_analysis[
                "distinct_residual_flows"
            ],
            "connected_completion_count": lower_mass_analysis[
                "connected_completion_count"
            ],
            "connected_completions": lower_mass_analysis[
                "connected_completions"
            ],
        }
    double_omission_excluded = (
        two_omission_analysis["connected_completion_count"] == 0
    )
    maximum_backbone_overlap = (
        len(support) - 3
        if (
            all_backbone_edges_excluded
            and single_omission_excluded
            and double_omission_excluded
        )
        else None
    )
    consequences = [
        (
            "Every connected balanced distinct-edge support containing "
            f"the {len(support)}-edge backbone has at least "
            f"{simple_support_lower_bound} edges."
        ),
        (
            "Every connected nonnegative integral circulation "
            f"dominating the {len(support)}-edge backbone has total "
            f"multiplicity at least {multiset_lower_bound}."
        ),
    ]
    if maximum_backbone_overlap is not None:
        consequences.append(
            (
                "Every connected nonnegative integral circulation of total "
                f"multiplicity {candidate_length} uses at most "
                f"{maximum_backbone_overlap} distinct backbone edges."
            )
        )
    overlap_witness: dict[str, Any] | None = None
    if overlap_witness_path is not None:
        witness_bits = load_sequence(overlap_witness_path)
        witness_report = verify_sequence(
            witness_bits,
            n=n,
            radius=radius,
            expected_length=candidate_length,
        )
        witness_support = sequence_support(witness_bits, n)
        witness_overlap = len(support & witness_support)
        if witness_overlap != maximum_backbone_overlap:
            raise ValueError(
                "overlap witness does not attain the derived maximum"
            )
        overlap_witness = {
            "path": str(overlap_witness_path),
            "file_sha256": file_digest(overlap_witness_path),
            "normalized_sha256": witness_report.normalized_sha256,
            "length": len(witness_bits),
            "distinct_windows": len(witness_support),
            "backbone_overlap": witness_overlap,
            "omitted_backbone_edges": sorted(
                support - witness_support
            ),
            "covered_words": witness_report.covered_words,
            "valid_cover": witness_report.valid,
        }
        consequences.append(
            (
                f"The overlap bound {maximum_backbone_overlap} is attained "
                "by the retained cyclic witness."
            )
        )
    source_path = Path(__file__).resolve()
    return {
        "n": n,
        "radius": radius,
        "backbone": {
            "path": str(support_path),
            "file_sha256": file_digest(support_path),
            "support_sha256": support_digest(support_list),
            "size": len(support),
            "report": report,
            "component_vertices": [
                sorted(component) for component in components
            ],
            "component_edges": component_edges,
            "components_are_directed_cycles": True,
            "contains_loops": False,
        },
        "simple_support_connector": {
            "allowed_edges": "edges outside the backbone",
            "minimum_closed_walk_length": len(shortest_simple),
            "minimum_connector_count": len(
                simple_tight_connectors
            ),
            "minimum_connectors": simple_tight_connectors,
            "primary_witness_edges": shortest_simple,
            "primary_witness_vertices": vertices,
            "minimum_connector_edges_are_distinct": all(
                len(set(connector)) == len(connector)
                for connector in simple_tight_connectors
            ),
            "exhaustive_exclusion_through": len(shortest_simple) - 1,
            "raw_start_bitstring_candidates_checked_through_exclusion": (
                checked_simple_short
            ),
            "raw_start_bitstring_candidates_at_tight_length": (
                len(components[0]) * (1 << len(shortest_simple))
            ),
        },
        "multiset_connector": {
            "allowed_edges": (
                "all de Bruijn edges, including repeated backbone edges"
            ),
            "minimum_closed_walk_length": len(shortest_multiset),
            "minimum_connector_count": len(
                multiset_tight_connectors
            ),
            "minimum_connectors": multiset_tight_connectors,
            "primary_witness_edges": shortest_multiset,
            "exhaustive_exclusion_through": len(shortest_multiset) - 1,
            "raw_start_bitstring_candidates_checked_through_exclusion": (
                checked_multiset_short
            ),
            "raw_start_bitstring_candidates_at_tight_length": (
                len(components[0]) * (1 << len(shortest_multiset))
            ),
        },
        "single_omission_detours": {
            "candidate_length": candidate_length,
            "exact_backbone_overlap": len(support) - 1,
            "residual_edge_budget": residual_budget,
            "omitted_edge_cases": len(omission_cases),
            "exhaustive_exclusion_through": residual_budget,
            "raw_start_bitstring_candidates_checked": checked_detours,
            "minimum_detour_length_over_all_cases": minimum_detour,
            "maximum_detour_length_over_all_cases": max(
                case["minimum_detour_length"]
                for case in omission_cases
            ),
            "short_detour_found": short_detour,
            "minimum_detour_length_histogram": detour_histogram,
            "cases": omission_cases,
        },
        "double_omission_residuals": two_omission_analysis,
        "tight_overlap_witness": overlap_witness,
        "tight_super_supports": tight_super_supports,
        "baseline": {
            "path": str(baseline_path),
            "file_sha256": file_digest(baseline_path),
            "length": len(baseline_bits),
            "support_sha256": support_digest(sorted(baseline_support)),
        },
        "derived_bounds": {
            "minimum_distinct_support_size_when_containing_backbone": (
                simple_support_lower_bound
            ),
            "minimum_total_multiplicity_when_dominating_backbone": (
                multiset_lower_bound
            ),
            "candidate_length": candidate_length,
            "all_backbone_edges_excluded": (
                all_backbone_edges_excluded
            ),
            "single_omission_excluded": single_omission_excluded,
            "double_omission_excluded": double_omission_excluded,
            "maximum_backbone_overlap_for_candidate": (
                maximum_backbone_overlap
            ),
        },
        "consequences": consequences,
        "source_sha256": file_digest(source_path),
    }


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Certify the shortest outside connector for a two-component "
            "balanced covering support."
        )
    )
    parser.add_argument("support", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--overlap-witness", type=Path)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--radius", type=int, required=True)
    parser.add_argument("--candidate-length", type=int, required=True)
    args = parser.parse_args()

    try:
        result = analyze_backbone(
            args.support,
            baseline_path=args.baseline,
            overlap_witness_path=args.overlap_witness,
            n=args.n,
            radius=args.radius,
            candidate_length=args.candidate_length,
        )
        write_json_atomic(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
