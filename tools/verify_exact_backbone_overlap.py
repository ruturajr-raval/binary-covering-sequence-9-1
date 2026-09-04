#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

try:
    from .analyze_common_backbone import (
        Flow,
        flow_divergence,
        flow_mass,
        flow_support,
        support_components,
    )
    from .covering import load_sequence, verify_sequence
    from .flow_cp_sat import (
        edge_prefix,
        extract_euler_sequence,
        sequence_window_counts,
    )
    from .repair_support import (
        analyze_support,
        load_support_certificate,
        support_digest,
    )
except ImportError:
    from analyze_common_backbone import (
        Flow,
        flow_divergence,
        flow_mass,
        flow_support,
        support_components,
    )
    from covering import load_sequence, verify_sequence
    from flow_cp_sat import (
        edge_prefix,
        extract_euler_sequence,
        sequence_window_counts,
    )
    from repair_support import (
        analyze_support,
        load_support_certificate,
        support_digest,
    )


SHARED_ENUMERATION_KEYS = (
    "omission_sets_checked",
    "precomputed_directed_walks",
    "balanced_flow_counts_by_mass",
    "source_count_histogram",
    "active_omission_sets",
    "distinct_path_flows",
    "raw_exact_decompositions",
    "distinct_residual_flows",
    "residual_flow_count_histogram",
    "component_count_histogram",
    "connected_support_size_histogram",
    "connected_coverage_gap_histogram",
    "connected_completion_count",
    "covering_completion_count",
)

EXPECTED_PARAMETERS = {
    "n": 9,
    "radius": 1,
    "candidate_length": 70,
    "reference_support_size": 64,
    "exact_overlap": 61,
    "omitted_support_edges": 3,
    "residual_mass": 9,
}

EXPECTED_ENUMERATION = {
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
}


def file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def parse_flow(value: Any) -> Flow:
    require(isinstance(value, list), "flow must be a list")
    flow: list[tuple[int, int]] = []
    prior_edge = -1
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
        require(edge > prior_edge, "flow edges must be strictly increasing")
        require(multiplicity > 0, "flow multiplicities must be positive")
        flow.append((edge, multiplicity))
        prior_edge = edge
    return tuple(flow)


def json_normalize(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True))


def expected_residual_divergence(
    required: set[int],
    *,
    n: int,
) -> dict[int, int]:
    divergence: Counter[int] = Counter()
    for edge in required:
        divergence[edge >> 1] -= 1
        divergence[edge & ((1 << (n - 1)) - 1)] += 1
    return {
        vertex: value
        for vertex, value in divergence.items()
        if value
    }


def flow_payload(flow: Flow) -> list[list[int]]:
    return [[edge, multiplicity] for edge, multiplicity in flow]


def flow_digest(flow: Flow) -> str:
    payload = json.dumps(
        flow_payload(flow),
        separators=(",", ":"),
    ).encode("ascii")
    return sha256(payload).hexdigest()


def divergence_terminals(
    divergence: dict[int, int],
) -> tuple[list[int], list[int]]:
    sources: list[int] = []
    sinks: list[int] = []
    for vertex in sorted(divergence):
        value = divergence[vertex]
        if value > 0:
            sources.extend([vertex] * value)
        elif value < 0:
            sinks.extend([vertex] * (-value))
    require(
        len(sources) == len(sinks),
        "residual divergence terminals are unbalanced",
    )
    return sources, sinks


def coverage_gap(
    selected: set[int],
    *,
    n: int,
    radius: int,
) -> list[int]:
    require(radius == 1, "retained classification requires radius 1")
    covered: set[int] = set()
    for edge in selected:
        covered.add(edge)
        covered.update(edge ^ (1 << bit) for bit in range(n))
    return [
        word
        for word in range(1 << n)
        if word not in covered
    ]


def verify_residual_record(
    record: dict[str, Any],
    *,
    omitted_value: list[int],
    support: set[int],
    n: int,
    radius: int,
    candidate_length: int,
    exact_overlap: int,
) -> tuple[Flow, dict[str, Any] | None, int, int]:
    omitted = set(omitted_value)
    required = support - omitted
    residual = parse_flow(record.get("flow"))
    require(
        record.get("flow_sha256") == flow_digest(residual),
        "residual flow digest is inconsistent",
    )
    require(
        flow_mass(residual) == candidate_length - exact_overlap,
        "residual flow has the wrong mass",
    )
    require(
        omitted.isdisjoint(flow_support(residual)),
        "residual flow uses an omitted support edge",
    )
    require(
        flow_divergence(residual, n=n)
        == expected_residual_divergence(required, n=n),
        "residual flow has the wrong divergence",
    )

    counts = [0] * (1 << n)
    for edge in required:
        counts[edge] = 1
    for edge, multiplicity in residual:
        counts[edge] += multiplicity
    require(sum(counts) == candidate_length, "residual has the wrong length")

    combined_divergence: Counter[int] = Counter()
    for edge, multiplicity in enumerate(counts):
        if not multiplicity:
            continue
        combined_divergence[edge >> 1] += multiplicity
        combined_divergence[
            edge & ((1 << (n - 1)) - 1)
        ] -= multiplicity
    require(
        not any(combined_divergence.values()),
        "residual does not produce a circulation",
    )

    selected = {
        edge
        for edge, multiplicity in enumerate(counts)
        if multiplicity
    }
    require(
        len(selected & support) == exact_overlap,
        "residual has the wrong exact overlap",
    )
    component_count = len(support_components(selected, n))
    uncovered = coverage_gap(selected, n=n, radius=radius)
    require(
        record.get("combined_component_count") == component_count,
        "residual component count is inconsistent",
    )
    require(
        record.get("combined_support_size") == len(selected),
        "residual support size is inconsistent",
    )
    require(
        record.get("covered_words") == (1 << n) - len(uncovered),
        "residual covered-word count is inconsistent",
    )
    require(
        record.get("uncovered_words") == uncovered,
        "residual uncovered-word set is inconsistent",
    )

    projection = None
    if component_count == 1:
        projection = {
            "omitted_edges": omitted_value,
            "residual_flow": flow_payload(residual),
            "combined_support_size": len(selected),
            "uncovered_words": uncovered,
        }
    return residual, projection, component_count, len(uncovered)


def verify_completion(
    completion: dict[str, Any],
    *,
    support: set[int],
    n: int,
    radius: int,
    candidate_length: int,
    exact_overlap: int,
) -> dict[str, Any]:
    omitted_value = completion.get("omitted_edges")
    require(
        isinstance(omitted_value, list)
        and len(omitted_value) == len(support) - exact_overlap
        and all(isinstance(edge, int) for edge in omitted_value),
        "completion has invalid omitted edges",
    )
    omitted = set(omitted_value)
    require(
        len(omitted) == len(omitted_value) and omitted <= support,
        "completion omissions are not a distinct support subset",
    )
    required = support - omitted
    residual = parse_flow(completion.get("residual_flow"))
    require(
        completion.get("residual_flow_sha256") == flow_digest(residual),
        "completion residual flow digest is inconsistent",
    )
    require(
        flow_mass(residual) == candidate_length - exact_overlap,
        "completion residual has the wrong mass",
    )
    require(
        omitted.isdisjoint(flow_support(residual)),
        "completion residual uses an omitted support edge",
    )
    require(
        flow_divergence(residual, n=n)
        == expected_residual_divergence(required, n=n),
        "completion residual has the wrong divergence",
    )

    counts = [0] * (1 << n)
    for edge in required:
        counts[edge] = 1
    for edge, multiplicity in residual:
        counts[edge] += multiplicity
    selected = {
        edge
        for edge, multiplicity in enumerate(counts)
        if multiplicity
    }
    require(sum(counts) == candidate_length, "completion has the wrong length")
    require(
        len(selected & support) == exact_overlap,
        "completion has the wrong exact overlap",
    )
    require(
        len(support_components(selected, n)) == 1,
        "completion support is disconnected",
    )
    require(
        completion.get("combined_support_size") == len(selected),
        "completion support size is inconsistent",
    )
    require(
        completion.get("combined_support_sha256")
        == support_digest(sorted(selected)),
        "completion support digest is inconsistent",
    )

    root = min(edge_prefix(edge, n) for edge in selected)
    bits = extract_euler_sequence(counts, n=n, root=root)
    require(
        completion.get("sequence") == "".join(str(bit) for bit in bits),
        "completion sequence is inconsistent",
    )
    require(
        sequence_window_counts(bits, n) == counts,
        "completion sequence does not reproduce the edge counts",
    )
    report = verify_sequence(
        bits,
        n=n,
        radius=radius,
        expected_length=candidate_length,
    )
    require(
        completion.get("verification") == json_normalize(report.to_dict()),
        "completion verification report is inconsistent",
    )
    return {
        "omitted_edges": omitted_value,
        "residual_flow": completion["residual_flow"],
        "combined_support_size": len(selected),
        "uncovered_words": list(report.uncovered_words),
    }


def verify_artifacts(
    analysis: dict[str, Any],
    independent: dict[str, Any],
    *,
    support_path: Path,
    analyzer_path: Path,
    witness_path: Path,
) -> dict[str, Any]:
    require(analysis.get("schema_version") == 1, "unsupported analysis schema")
    parameters = analysis.get("parameters")
    require(isinstance(parameters, dict), "analysis has no parameters")
    require(parameters == EXPECTED_PARAMETERS, "analysis parameters changed")

    support = set(load_support_certificate(support_path, n=9))
    reference = analysis.get("reference_support")
    require(isinstance(reference, dict), "analysis has no reference support")
    require(
        reference.get("file_sha256") == file_digest(support_path),
        "reference support file digest is inconsistent",
    )
    require(
        reference.get("support_sha256") == support_digest(sorted(support)),
        "reference support digest is inconsistent",
    )
    require(
        reference.get("report")
        == json_normalize(analyze_support(sorted(support), n=9, radius=1)),
        "reference support report is inconsistent",
    )
    require(
        analysis.get("source_sha256") == file_digest(analyzer_path),
        "analyzer source digest is inconsistent",
    )
    require(
        independent.get("schema_version") == 1,
        "unsupported independent-check schema",
    )
    require(
        independent.get("implementation")
        == "independent-cpp-exact-overlap61-v1",
        "independent checker identity changed",
    )
    require(
        independent.get("parameters") == EXPECTED_PARAMETERS,
        "independent checker parameters changed",
    )
    require(
        independent.get("support_edges") == sorted(support),
        "independent checker used a different support",
    )

    enumeration = analysis.get("enumeration")
    require(isinstance(enumeration, dict), "analysis has no enumeration summary")
    require(
        enumeration == EXPECTED_ENUMERATION,
        "analysis enumeration summary changed",
    )
    for key in SHARED_ENUMERATION_KEYS:
        require(
            independent.get(key) == EXPECTED_ENUMERATION[key],
            f"independent checker disagrees on {key}",
        )

    active_cases = analysis.get("active_cases")
    require(isinstance(active_cases, list), "active cases must be a list")
    require(
        len(active_cases) == EXPECTED_ENUMERATION["active_omission_sets"],
        "active omission count is inconsistent",
    )

    residual_count_histogram: Counter[int] = Counter(
        {
            0: (
                EXPECTED_ENUMERATION["omission_sets_checked"]
                - len(active_cases)
            )
        }
    )
    component_count_histogram: Counter[int] = Counter()
    connected_support_size_histogram: Counter[int] = Counter()
    connected_coverage_gap_histogram: Counter[int] = Counter()
    connected_projection: list[dict[str, Any]] = []
    seen_cases: set[tuple[int, ...]] = set()
    seen_residuals: set[tuple[tuple[int, ...], Flow]] = set()
    prior_case: tuple[int, ...] | None = None
    for case in active_cases:
        require(isinstance(case, dict), "active case must be an object")
        omitted_value = case.get("omitted_edges")
        require(
            isinstance(omitted_value, list)
            and len(omitted_value) == 3
            and all(isinstance(edge, int) for edge in omitted_value),
            "active case has invalid omissions",
        )
        omitted_key = tuple(omitted_value)
        require(
            list(omitted_key) == sorted(set(omitted_key))
            and set(omitted_key) <= support,
            "active case omissions are not a sorted support subset",
        )
        require(omitted_key not in seen_cases, "active case is duplicated")
        require(
            prior_case is None or omitted_key > prior_case,
            "active cases are not strictly ordered",
        )
        prior_case = omitted_key
        seen_cases.add(omitted_key)

        divergence = expected_residual_divergence(
            support - set(omitted_key),
            n=9,
        )
        sources, sinks = divergence_terminals(divergence)
        require(
            case.get("source_vertices") == sources,
            "active case source vertices are inconsistent",
        )
        require(
            case.get("sink_vertices") == sinks,
            "active case sink vertices are inconsistent",
        )

        residuals = case.get("residuals")
        require(
            isinstance(residuals, list) and residuals,
            "active case residuals must be a nonempty list",
        )
        require(
            len(residuals) == case.get("distinct_residual_flows"),
            "case residual count is inconsistent",
        )
        residual_count_histogram[len(residuals)] += 1
        prior_flow: Flow | None = None
        for residual_record in residuals:
            require(
                isinstance(residual_record, dict),
                "residual record must be an object",
            )
            flow, projection, component_count, coverage_gap_size = (
                verify_residual_record(
                    residual_record,
                    omitted_value=omitted_value,
                    support=support,
                    n=9,
                    radius=1,
                    candidate_length=70,
                    exact_overlap=61,
                )
            )
            require(
                prior_flow is None or flow > prior_flow,
                "case residual flows are not strictly ordered",
            )
            prior_flow = flow
            residual_key = (omitted_key, flow)
            require(
                residual_key not in seen_residuals,
                "residual record is duplicated",
            )
            seen_residuals.add(residual_key)
            component_count_histogram[component_count] += 1
            if projection is not None:
                connected_projection.append(projection)
                connected_support_size_histogram[
                    projection["combined_support_size"]
                ] += 1
                connected_coverage_gap_histogram[coverage_gap_size] += 1

    def counter_payload(counter: Counter[int]) -> dict[str, int]:
        return {
            str(key): counter[key]
            for key in sorted(counter)
        }

    derived_enumeration = {
        "active_omission_sets": len(active_cases),
        "distinct_residual_flows": len(seen_residuals),
        "residual_flow_count_histogram": counter_payload(
            residual_count_histogram
        ),
        "component_count_histogram": counter_payload(
            component_count_histogram
        ),
        "connected_support_size_histogram": counter_payload(
            connected_support_size_histogram
        ),
        "connected_coverage_gap_histogram": counter_payload(
            connected_coverage_gap_histogram
        ),
        "connected_completion_count": len(connected_projection),
        "covering_completion_count": sum(
            not completion["uncovered_words"]
            for completion in connected_projection
        ),
    }
    for key, derived_value in derived_enumeration.items():
        require(
            derived_value == EXPECTED_ENUMERATION[key],
            f"semantic validation disagrees on {key}",
        )

    completions_value = analysis.get("connected_completions")
    require(
        isinstance(completions_value, list),
        "analysis connected completions must be a list",
    )
    completion_projection = [
        verify_completion(
            completion,
            support=support,
            n=9,
            radius=1,
            candidate_length=70,
            exact_overlap=61,
        )
        for completion in completions_value
    ]
    require(
        completion_projection == connected_projection,
        "analysis connected completions omit or add a residual",
    )
    require(
        independent.get("connected_completions") == connected_projection,
        "independent checker disagrees on connected completions",
    )

    witness = analysis.get("overlap_witness")
    require(isinstance(witness, dict), "analysis has no overlap witness")
    witness_bits = load_sequence(witness_path)
    witness_report = verify_sequence(
        witness_bits,
        n=9,
        radius=1,
        expected_length=70,
    )
    witness_counts = sequence_window_counts(witness_bits, 9)
    witness_support = {
        edge
        for edge, multiplicity in enumerate(witness_counts)
        if multiplicity
    }
    witness_support_sha256 = support_digest(sorted(witness_support))
    matching_indices = [
        index
        for index, completion in enumerate(completions_value)
        if completion.get("combined_support_sha256")
        == witness_support_sha256
    ]
    expected_witness = {
        "backbone_overlap": len(witness_support & support),
        "distinct_windows": len(witness_support),
        "matching_completion_indices": matching_indices,
        "normalized_sha256": witness_report.normalized_sha256,
        "omitted_edges": sorted(support - witness_support),
        "valid_cover": witness_report.valid,
        "file_sha256": file_digest(witness_path),
    }
    for key, expected_value in expected_witness.items():
        require(
            witness.get(key) == expected_value,
            f"overlap witness {key} is inconsistent",
        )
    require(
        expected_witness["backbone_overlap"] == 61
        and expected_witness["distinct_windows"] == 70
        and expected_witness["matching_completion_indices"]
        and not expected_witness["valid_cover"],
        "overlap witness does not certify the retained boundary case",
    )
    require(
        analysis.get("consequence")
        == (
            "No length-70 radius-1 covering sequence has exact overlap 61 "
            "with the retained support."
        ),
        "analysis consequence is inconsistent",
    )

    return {
        "omission_sets_checked": EXPECTED_ENUMERATION[
            "omission_sets_checked"
        ],
        "distinct_residual_flows": len(seen_residuals),
        "connected_completion_count": len(completion_projection),
        "covering_completion_count": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate exact-overlap analysis and independent checker artifacts."
        )
    )
    parser.add_argument("analysis", type=Path)
    parser.add_argument("independent", type=Path)
    parser.add_argument("--support", type=Path, required=True)
    parser.add_argument("--analyzer", type=Path, required=True)
    parser.add_argument("--witness", type=Path, required=True)
    args = parser.parse_args()

    try:
        analysis = json.loads(args.analysis.read_text(encoding="ascii"))
        independent = json.loads(args.independent.read_text(encoding="ascii"))
        require(isinstance(analysis, dict), "analysis must be a JSON object")
        require(
            isinstance(independent, dict),
            "independent result must be a JSON object",
        )
        result = verify_artifacts(
            analysis,
            independent,
            support_path=args.support,
            analyzer_path=args.analyzer,
            witness_path=args.witness,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 1

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
