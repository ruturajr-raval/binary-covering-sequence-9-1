#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
from typing import Any


Flow = tuple[tuple[int, int], ...]

EXPECTED_SUMMARY = {
    "omission_pairs_checked": 2016,
    "distinct_residual_flows": 168,
    "connected_completion_count": 0,
    "component_count_histogram": {
        "2": 36,
        "3": 76,
        "4": 50,
        "5": 6,
    },
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def edge_prefix(edge: int, n: int) -> int:
    return edge >> 1


def edge_suffix(edge: int, n: int) -> int:
    return edge & ((1 << (n - 1)) - 1)


def parse_flow(value: Any) -> Flow:
    require(isinstance(value, list), "flow must be a list")
    flow: list[tuple[int, int]] = []
    previous = -1
    for entry in value:
        require(
            isinstance(entry, list) and len(entry) == 2,
            "flow entries must be [edge, multiplicity] pairs",
        )
        edge, multiplicity = entry
        require(
            isinstance(edge, int) and isinstance(multiplicity, int),
            "flow entries must contain integers",
        )
        require(edge > previous, "flow edges must be strictly increasing")
        require(multiplicity > 0, "flow multiplicities must be positive")
        flow.append((edge, multiplicity))
        previous = edge
    return tuple(flow)


def flow_payload(flow: Flow) -> list[list[int]]:
    return [[edge, multiplicity] for edge, multiplicity in flow]


def flow_digest(flow: Flow) -> str:
    payload = json.dumps(
        flow_payload(flow),
        separators=(",", ":"),
    ).encode("ascii")
    return sha256(payload).hexdigest()


def flow_mass(flow: Flow) -> int:
    return sum(multiplicity for _, multiplicity in flow)


def flow_support(flow: Flow) -> set[int]:
    return {edge for edge, multiplicity in flow if multiplicity}


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


def required_residual_divergence(
    support: set[int],
    omitted: set[int],
    *,
    n: int,
) -> dict[int, int]:
    divergence: Counter[int] = Counter()
    for edge in support - omitted:
        divergence[edge_prefix(edge, n)] -= 1
        divergence[edge_suffix(edge, n)] += 1
    return {
        vertex: value
        for vertex, value in divergence.items()
        if value
    }


def support_components(support: set[int], *, n: int) -> list[set[int]]:
    adjacency: dict[int, set[int]] = {}
    for edge in support:
        prefix = edge_prefix(edge, n)
        suffix = edge_suffix(edge, n)
        adjacency.setdefault(prefix, set()).add(suffix)
        adjacency.setdefault(suffix, set()).add(prefix)

    components: list[set[int]] = []
    unseen = set(adjacency)
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
    components.sort(key=lambda item: (len(item), min(item)))
    return components


def covered_words(support: set[int], *, n: int) -> set[int]:
    covered: set[int] = set()
    for edge in support:
        covered.add(edge)
        covered.update(edge ^ (1 << bit) for bit in range(n))
    return covered


def sequence_windows(bits: list[int], *, n: int) -> list[int]:
    return [
        sum(
            bits[(start + offset) % len(bits)] << (n - 1 - offset)
            for offset in range(n)
        )
        for start in range(len(bits))
    ]


def load_bits(path: Path) -> list[int]:
    bits = [
        int(character)
        for character in path.read_text(encoding="ascii")
        if character in {"0", "1"}
    ]
    require(bits, "sequence file contains no bits")
    return bits


def verify_backbone(
    support: set[int],
    analysis: dict[str, Any],
    *,
    n: int,
) -> list[set[int]]:
    require(len(support) == 64, "backbone must contain 64 edges")
    require(
        all(0 <= edge < 1 << n for edge in support),
        "backbone contains an out-of-range edge",
    )
    require(
        all(
            sum(edge_prefix(edge, n) == vertex for edge in support)
            == sum(edge_suffix(edge, n) == vertex for edge in support)
            for vertex in range(1 << (n - 1))
        ),
        "backbone is not balanced",
    )
    require(
        len(covered_words(support, n=n)) == 1 << n,
        "backbone does not cover the Hamming cube",
    )
    components = support_components(support, n=n)
    component_edge_counts = sorted(
        sum(edge_prefix(edge, n) in component for edge in support)
        for component in components
    )
    require(
        component_edge_counts == [4, 60],
        "backbone components do not have sizes 4 and 60",
    )
    require(
        analysis["backbone"]["report"]["component_edge_counts"] == [4, 60],
        "analysis component sizes changed",
    )
    return components


def verify_short_walk_exclusions(
    support: set[int],
    components: list[set[int]],
    analysis: dict[str, Any],
    *,
    n: int,
) -> None:
    small, large = components
    connector_candidates = 0
    for length in range(1, 7):
        for start in sorted(small):
            for appended in product((0, 1), repeat=length):
                connector_candidates += 1
                vertex = start
                touched_large = False
                for bit in appended:
                    edge = (vertex << 1) | bit
                    vertex = edge_suffix(edge, n)
                    touched_large = touched_large or vertex in large
                require(
                    not (vertex == start and touched_large),
                    "short connector walk found",
                )
    require(connector_candidates == 504, "connector count changed")

    detour_candidates = 0
    component_by_vertex = {
        vertex: index
        for index, component in enumerate(components)
        for vertex in component
    }
    for omitted_edge in sorted(support):
        source = edge_prefix(omitted_edge, n)
        target = edge_suffix(omitted_edge, n)
        other = components[1 - component_by_vertex[source]]
        require(
            component_by_vertex[source] == component_by_vertex[target],
            "backbone edge crosses components",
        )
        for length in range(1, 8):
            for appended in product((0, 1), repeat=length):
                detour_candidates += 1
                vertex = source
                touched_other = False
                valid = True
                for bit in appended:
                    edge = (vertex << 1) | bit
                    if edge == omitted_edge:
                        valid = False
                        break
                    vertex = edge_suffix(edge, n)
                    touched_other = touched_other or vertex in other
                require(
                    not (
                        valid
                        and vertex == target
                        and touched_other
                    ),
                    "short one-omission detour found",
                )
    require(detour_candidates == 16_256, "detour count changed")
    require(
        analysis["multiset_connector"]["minimum_closed_walk_length"] == 7,
        "recorded connector minimum changed",
    )
    require(
        analysis["single_omission_detours"][
            "minimum_detour_length_over_all_cases"
        ]
        >= 10,
        "recorded detour minimum changed",
    )


def verify_residual_records(
    support: set[int],
    analysis: dict[str, Any],
    *,
    n: int,
) -> dict[str, Any]:
    section = analysis["double_omission_residuals"]
    require(section["residual_mass"] == 8, "residual mass changed")
    require(
        section["omission_pairs_checked"]
        == EXPECTED_SUMMARY["omission_pairs_checked"],
        "omission-pair count changed",
    )

    pair_records: set[tuple[int, int]] = set()
    residual_keys: set[tuple[tuple[int, int], Flow]] = set()
    component_histogram: Counter[int] = Counter()
    residual_count_histogram: Counter[int] = Counter()

    for case in section["active_omission_cases"]:
        omitted_value = case["omitted_edges"]
        require(
            isinstance(omitted_value, list)
            and len(omitted_value) == 2
            and omitted_value == sorted(omitted_value),
            "omission pair is invalid",
        )
        omitted_pair = tuple(omitted_value)
        omitted = set(omitted_value)
        require(
            len(omitted) == 2 and omitted <= support,
            "omission pair is not a support subset",
        )
        require(omitted_pair not in pair_records, "duplicate omission pair")
        pair_records.add(omitted_pair)

        expected_divergence = required_residual_divergence(
            support,
            omitted,
            n=n,
        )
        records = case.get("residual_flows")
        require(isinstance(records, list) and records, "residuals are absent")
        case_component_histogram: Counter[int] = Counter()
        case_flows: set[Flow] = set()
        for record in records:
            require(isinstance(record, dict), "residual record is invalid")
            flow = parse_flow(record.get("flow"))
            require(
                record.get("flow_sha256") == flow_digest(flow),
                "residual flow digest is inconsistent",
            )
            require(flow_mass(flow) == 8, "residual flow has wrong mass")
            require(
                omitted.isdisjoint(flow_support(flow)),
                "residual flow uses an omitted edge",
            )
            require(
                flow_divergence(flow, n=n) == expected_divergence,
                "residual flow has wrong divergence",
            )
            combined = (support - omitted) | flow_support(flow)
            component_count = len(support_components(combined, n=n))
            require(
                record.get("combined_component_count") == component_count,
                "residual component count is inconsistent",
            )
            require(flow not in case_flows, "duplicate residual flow")
            case_flows.add(flow)
            residual_keys.add((omitted_pair, flow))
            case_component_histogram[component_count] += 1
            component_histogram[component_count] += 1

        require(
            len(records) == case["distinct_residual_flows"],
            "case residual count is inconsistent",
        )
        require(
            {
                str(key): value
                for key, value in sorted(case_component_histogram.items())
            }
            == case["combined_component_count_histogram"],
            "case component histogram is inconsistent",
        )
        residual_count_histogram[len(records)] += 1

    inactive_pairs = (
        EXPECTED_SUMMARY["omission_pairs_checked"] - len(pair_records)
    )
    residual_count_histogram[0] = inactive_pairs
    require(
        len(residual_keys) == EXPECTED_SUMMARY["distinct_residual_flows"],
        "global residual count changed",
    )
    require(
        {
            str(key): value
            for key, value in sorted(component_histogram.items())
        }
        == EXPECTED_SUMMARY["component_count_histogram"],
        "global component histogram changed",
    )
    require(
        {
            str(key): value
            for key, value in sorted(residual_count_histogram.items())
        }
        == section["residual_flow_count_histogram"],
        "residual-count histogram is inconsistent",
    )
    require(
        not section["connected_completions"],
        "unexpected connected completion retained",
    )
    require(
        not any(count == 1 for count in component_histogram),
        "connected residual completion found",
    )
    return {
        "omission_pairs_checked": section["omission_pairs_checked"],
        "distinct_residual_flows": len(residual_keys),
        "connected_completion_count": 0,
        "component_count_histogram": {
            str(key): value
            for key, value in sorted(component_histogram.items())
        },
    }


def verify_witness(
    path: Path,
    support: set[int],
    analysis: dict[str, Any],
    *,
    n: int,
) -> None:
    bits = load_bits(path)
    require(len(bits) == 70, "overlap witness has wrong length")
    windows = sequence_windows(bits, n=n)
    selected = set(windows)
    require(
        len(selected & support) == 61,
        "overlap witness does not attain 61",
    )
    require(
        len(covered_words(selected, n=n)) < 1 << n,
        "overlap witness unexpectedly covers",
    )
    require(
        analysis["tight_overlap_witness"]["backbone_overlap"] == 61,
        "recorded witness overlap changed",
    )


def verify_artifact(
    analysis_path: Path,
    support_path: Path,
    witness_path: Path,
) -> dict[str, Any]:
    analysis = json.loads(analysis_path.read_text(encoding="ascii"))
    support_payload = json.loads(support_path.read_text(encoding="ascii"))
    support_value = support_payload.get("selected_edges")
    require(isinstance(support_value, list), "support payload is invalid")
    require(
        all(isinstance(edge, int) for edge in support_value),
        "support edges must be integers",
    )
    support = set(support_value)
    require(
        len(support) == len(support_value),
        "support contains duplicate edges",
    )
    require(analysis.get("n") == 9, "analysis order changed")
    require(analysis.get("radius") == 1, "analysis radius changed")

    components = verify_backbone(support, analysis, n=9)
    verify_short_walk_exclusions(
        support,
        components,
        analysis,
        n=9,
    )
    summary = verify_residual_records(support, analysis, n=9)
    verify_witness(witness_path, support, analysis, n=9)
    require(summary == EXPECTED_SUMMARY, "publication summary changed")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Semantically verify the common-backbone certificate."
    )
    parser.add_argument("analysis", type=Path)
    parser.add_argument("--support", type=Path, required=True)
    parser.add_argument("--witness", type=Path, required=True)
    args = parser.parse_args()

    try:
        summary = verify_artifact(
            args.analysis,
            args.support,
            args.witness,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
