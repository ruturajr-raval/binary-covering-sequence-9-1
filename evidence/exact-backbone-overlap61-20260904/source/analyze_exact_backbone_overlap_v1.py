#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
from itertools import combinations, permutations, product
import json
from math import comb
from pathlib import Path
from typing import Any, Iterable

try:
    from .analyze_common_backbone import (
        Flow,
        add_flows,
        balanced_cycle_flows,
        flow_divergence,
        flow_mass,
        flow_support,
        normalize_flow,
        sequence_support,
        support_components,
    )
    from .covering import load_sequence, verify_sequence
    from .flow_cp_sat import edge_prefix, edge_suffix, extract_euler_sequence
    from .repair_support import (
        analyze_support,
        load_support_certificate,
        support_digest,
    )
except ImportError:
    from analyze_common_backbone import (
        Flow,
        add_flows,
        balanced_cycle_flows,
        flow_divergence,
        flow_mass,
        flow_support,
        normalize_flow,
        sequence_support,
        support_components,
    )
    from covering import load_sequence, verify_sequence
    from flow_cp_sat import edge_prefix, edge_suffix, extract_euler_sequence
    from repair_support import (
        analyze_support,
        load_support_certificate,
        support_digest,
    )


def file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def flow_payload(flow: Flow) -> list[list[int]]:
    return [[edge, multiplicity] for edge, multiplicity in flow]


def flow_digest(flow: Flow) -> str:
    payload = json.dumps(
        flow_payload(flow),
        separators=(",", ":"),
    ).encode("ascii")
    return sha256(payload).hexdigest()


def coverage_masks(*, n: int, radius: int) -> list[int]:
    if radius != 1:
        raise ValueError("the exact-overlap analyzer currently supports radius 1")
    masks: list[int] = []
    for edge in range(1 << n):
        mask = 1 << edge
        for bit in range(n):
            mask |= 1 << (edge ^ (1 << bit))
        masks.append(mask)
    return masks


def support_coverage_mask(
    support: Iterable[int],
    *,
    masks: list[int],
) -> int:
    result = 0
    for edge in support:
        result |= masks[edge]
    return result


def precompute_directed_walks(
    start_vertices: Iterable[int],
    *,
    n: int,
    maximum_length: int,
) -> dict[tuple[int, int], tuple[tuple[int, ...], ...]]:
    if n <= 0 or maximum_length <= 0:
        raise ValueError("require positive n and maximum walk length")

    walks: dict[tuple[int, int], list[tuple[int, ...]]] = defaultdict(list)
    for source in sorted(set(start_vertices)):
        frontier = [(source, ())]
        for _ in range(maximum_length):
            next_frontier: list[tuple[int, tuple[int, ...]]] = []
            for vertex, path in frontier:
                for bit in (0, 1):
                    edge = (vertex << 1) | bit
                    target = edge_suffix(edge, n)
                    extended = (*path, edge)
                    walks[(source, target)].append(extended)
                    next_frontier.append((target, extended))
            frontier = next_frontier
    return {
        endpoints: tuple(paths)
        for endpoints, paths in walks.items()
    }


def residual_divergence(
    required: set[int],
    *,
    n: int,
) -> Counter[int]:
    divergence: Counter[int] = Counter()
    for edge in required:
        divergence[edge_prefix(edge, n)] -= 1
        divergence[edge_suffix(edge, n)] += 1
    return divergence


def divergence_terminals(
    divergence: Counter[int],
) -> tuple[list[int], list[int]]:
    sources: list[int] = []
    sinks: list[int] = []
    for vertex in sorted(divergence):
        value = divergence[vertex]
        if value > 0:
            sources.extend([vertex] * value)
        elif value < 0:
            sinks.extend([vertex] * (-value))
    if len(sources) != len(sinks):
        raise RuntimeError("residual divergence is not balanced")
    return sources, sinks


def enumerate_residual_flows(
    *,
    sources: list[int],
    sinks: list[int],
    residual_mass: int,
    forbidden_edges: set[int],
    directed_walks: dict[
        tuple[int, int],
        tuple[tuple[int, ...], ...],
    ],
    balanced_flows: list[set[Flow]],
) -> tuple[set[Flow], int, int]:
    if len(sources) != len(sinks):
        raise ValueError("source and sink multiplicities do not match")

    sink_orders = (
        [()]
        if not sinks
        else sorted(set(permutations(sinks)))
    )
    path_flows: set[Flow] = set()
    raw_decompositions = 0
    residual_flows: set[Flow] = set()

    for sink_order in sink_orders:
        walk_options: list[list[tuple[int, ...]]] = []
        for source, sink in zip(sources, sink_order):
            options = [
                walk
                for walk in directed_walks.get((source, sink), ())
                if forbidden_edges.isdisjoint(walk)
            ]
            if not options:
                walk_options = []
                break
            walk_options.append(options)
        if sources and not walk_options:
            continue

        path_products = product(*walk_options) if walk_options else [()]
        for paths in path_products:
            path_length = sum(len(path) for path in paths)
            if path_length > residual_mass:
                continue
            path_flow = normalize_flow(
                tuple(
                    edge
                    for path in paths
                    for edge in path
                )
            )
            path_flows.add(path_flow)
            for cycle_flow in balanced_flows[residual_mass - path_length]:
                if forbidden_edges & flow_support(cycle_flow):
                    continue
                raw_decompositions += 1
                residual_flows.add(add_flows(path_flow, cycle_flow))

    return residual_flows, len(path_flows), raw_decompositions


def exact_overlap_analysis(
    support: set[int],
    *,
    n: int,
    radius: int,
    candidate_length: int,
    exact_overlap: int,
    overlap_witness: list[int] | None = None,
) -> dict[str, Any]:
    if n <= 0 or candidate_length < n:
        raise ValueError("require 0 < n <= candidate length")
    if radius != 1:
        raise ValueError("the exact-overlap analyzer currently supports radius 1")
    if not support:
        raise ValueError("support must be nonempty")
    if any(edge < 0 or edge >= 1 << n for edge in support):
        raise ValueError("support contains an out-of-range edge")
    if not 0 <= exact_overlap < len(support):
        raise ValueError("exact overlap must omit at least one support edge")

    omitted_count = len(support) - exact_overlap
    residual_mass = candidate_length - exact_overlap
    if omitted_count > 3:
        raise ValueError("the retained enumerator supports at most three omissions")
    if not 0 < residual_mass <= 9:
        raise ValueError("the retained enumerator supports residual mass 1 through 9")

    support_report = analyze_support(sorted(support), n=n, radius=radius)
    if not support_report["balanced"]:
        raise ValueError("reference support must be balanced")

    start_vertices = {
        edge_prefix(edge, n)
        for edge in support
    } | {
        edge_suffix(edge, n)
        for edge in support
    }
    directed_walks = precompute_directed_walks(
        start_vertices,
        n=n,
        maximum_length=residual_mass,
    )
    balanced_flows = balanced_cycle_flows(
        n=n,
        maximum_mass=residual_mass,
    )
    masks = coverage_masks(n=n, radius=radius)
    all_targets = (1 << (1 << n)) - 1

    source_count_histogram: Counter[int] = Counter()
    residual_flow_count_histogram: Counter[int] = Counter()
    component_count_histogram: Counter[int] = Counter()
    connected_support_size_histogram: Counter[int] = Counter()
    connected_coverage_gap_histogram: Counter[int] = Counter()
    total_path_flows = 0
    total_raw_decompositions = 0
    total_residual_flows = 0
    active_cases: list[dict[str, Any]] = []
    connected_completions: list[dict[str, Any]] = []

    for omitted_edges in combinations(sorted(support), omitted_count):
        forbidden = set(omitted_edges)
        required = support - forbidden
        divergence = residual_divergence(required, n=n)
        sources, sinks = divergence_terminals(divergence)
        if len(sources) > omitted_count:
            raise RuntimeError("omissions produced too many divergence terminals")
        source_count_histogram[len(sources)] += 1

        residual_flows, path_flow_count, raw_decompositions = (
            enumerate_residual_flows(
                sources=sources,
                sinks=sinks,
                residual_mass=residual_mass,
                forbidden_edges=forbidden,
                directed_walks=directed_walks,
                balanced_flows=balanced_flows,
            )
        )
        total_path_flows += path_flow_count
        total_raw_decompositions += raw_decompositions
        total_residual_flows += len(residual_flows)
        residual_flow_count_histogram[len(residual_flows)] += 1
        if not residual_flows:
            continue

        required_coverage = support_coverage_mask(required, masks=masks)
        residual_records: list[dict[str, Any]] = []
        expected_divergence = {
            vertex: value
            for vertex, value in divergence.items()
            if value
        }
        for residual_flow in sorted(residual_flows):
            if flow_mass(residual_flow) != residual_mass:
                raise RuntimeError("residual flow has the wrong mass")
            if forbidden & flow_support(residual_flow):
                raise RuntimeError("residual flow uses an omitted support edge")
            if flow_divergence(residual_flow, n=n) != expected_divergence:
                raise RuntimeError("residual flow has the wrong divergence")

            combined_support = required | flow_support(residual_flow)
            component_count = len(support_components(combined_support, n))
            component_count_histogram[component_count] += 1
            coverage = required_coverage | support_coverage_mask(
                flow_support(residual_flow),
                masks=masks,
            )
            uncovered_words = [
                word
                for word in range(1 << n)
                if not coverage & (1 << word)
            ]
            support_size = len(combined_support)
            residual_record: dict[str, Any] = {
                "flow": flow_payload(residual_flow),
                "flow_sha256": flow_digest(residual_flow),
                "combined_component_count": component_count,
                "combined_support_size": support_size,
                "covered_words": (1 << n) - len(uncovered_words),
                "uncovered_words": uncovered_words,
            }
            residual_records.append(residual_record)
            if component_count != 1:
                continue

            connected_support_size_histogram[support_size] += 1
            connected_coverage_gap_histogram[len(uncovered_words)] += 1
            counts = [0] * (1 << n)
            for edge in required:
                counts[edge] = 1
            for edge, multiplicity in residual_flow:
                counts[edge] += multiplicity
            root = min(
                edge_prefix(edge, n)
                for edge, multiplicity in enumerate(counts)
                if multiplicity
            )
            bits = extract_euler_sequence(counts, n=n, root=root)
            report = verify_sequence(
                bits,
                n=n,
                radius=radius,
                expected_length=candidate_length,
            )
            if report.uncovered_words != tuple(uncovered_words):
                raise RuntimeError("support and sequence coverage reports disagree")
            connected_completions.append(
                {
                    "omitted_edges": list(omitted_edges),
                    "residual_flow": flow_payload(residual_flow),
                    "residual_flow_sha256": flow_digest(residual_flow),
                    "combined_support_size": support_size,
                    "combined_support_sha256": support_digest(
                        sorted(combined_support)
                    ),
                    "sequence": "".join(str(bit) for bit in bits),
                    "verification": report.to_dict(),
                }
            )

        active_cases.append(
            {
                "omitted_edges": list(omitted_edges),
                "source_vertices": sources,
                "sink_vertices": sinks,
                "distinct_residual_flows": len(residual_flows),
                "residuals": residual_records,
            }
        )

    witness_record: dict[str, Any] | None = None
    if overlap_witness is not None:
        witness_report = verify_sequence(
            overlap_witness,
            n=n,
            radius=radius,
            expected_length=candidate_length,
        )
        witness_support = sequence_support(overlap_witness, n)
        witness_overlap = len(witness_support & support)
        if witness_overlap != exact_overlap:
            raise ValueError("overlap witness does not attain the exact overlap")
        witness_omissions = sorted(support - witness_support)
        witness_matches = [
            index
            for index, completion in enumerate(connected_completions)
            if completion["combined_support_sha256"]
            == support_digest(sorted(witness_support))
        ]
        if not witness_matches:
            raise RuntimeError("overlap witness was not recovered by enumeration")
        witness_record = {
            "backbone_overlap": witness_overlap,
            "distinct_windows": len(witness_support),
            "matching_completion_indices": witness_matches,
            "normalized_sha256": witness_report.normalized_sha256,
            "omitted_edges": witness_omissions,
            "valid_cover": witness_report.valid,
        }

    covering_completions = [
        completion
        for completion in connected_completions
        if completion["verification"]["valid"]
    ]
    return {
        "schema_version": 1,
        "parameters": {
            "n": n,
            "radius": radius,
            "candidate_length": candidate_length,
            "reference_support_size": len(support),
            "exact_overlap": exact_overlap,
            "omitted_support_edges": omitted_count,
            "residual_mass": residual_mass,
        },
        "reference_support": {
            "support_sha256": support_digest(sorted(support)),
            "report": support_report,
        },
        "enumeration": {
            "omission_sets_checked": comb(len(support), omitted_count),
            "precomputed_directed_walks": sum(
                len(paths) for paths in directed_walks.values()
            ),
            "balanced_flow_counts_by_mass": [
                len(flows) for flows in balanced_flows
            ],
            "source_count_histogram": {
                str(count): source_count_histogram[count]
                for count in sorted(source_count_histogram)
            },
            "active_omission_sets": len(active_cases),
            "distinct_path_flows": total_path_flows,
            "raw_exact_decompositions": total_raw_decompositions,
            "distinct_residual_flows": total_residual_flows,
            "residual_flow_count_histogram": {
                str(count): residual_flow_count_histogram[count]
                for count in sorted(residual_flow_count_histogram)
            },
            "component_count_histogram": {
                str(count): component_count_histogram[count]
                for count in sorted(component_count_histogram)
            },
            "connected_support_size_histogram": {
                str(count): connected_support_size_histogram[count]
                for count in sorted(connected_support_size_histogram)
            },
            "connected_coverage_gap_histogram": {
                str(count): connected_coverage_gap_histogram[count]
                for count in sorted(connected_coverage_gap_histogram)
            },
            "connected_completion_count": len(connected_completions),
            "covering_completion_count": len(covering_completions),
        },
        "active_cases": active_cases,
        "connected_completions": connected_completions,
        "overlap_witness": witness_record,
        "consequence": (
            f"No length-{candidate_length} radius-{radius} covering sequence "
            f"has exact overlap {exact_overlap} with the retained support."
            if not covering_completions
            else (
                f"The enumeration found {len(covering_completions)} covering "
                "completion(s)."
            )
        ),
    }


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Enumerate every bounded residual circulation at an exact "
            "reference-support overlap."
        )
    )
    parser.add_argument("support", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--radius", type=int, required=True)
    parser.add_argument("--candidate-length", type=int, required=True)
    parser.add_argument("--exact-overlap", type=int, required=True)
    parser.add_argument("--overlap-witness", type=Path)
    args = parser.parse_args()

    try:
        support = set(load_support_certificate(args.support, n=args.n))
        witness = (
            load_sequence(args.overlap_witness)
            if args.overlap_witness is not None
            else None
        )
        result = exact_overlap_analysis(
            support,
            n=args.n,
            radius=args.radius,
            candidate_length=args.candidate_length,
            exact_overlap=args.exact_overlap,
            overlap_witness=witness,
        )
        result["reference_support"]["path"] = str(args.support)
        result["reference_support"]["file_sha256"] = file_digest(args.support)
        if args.overlap_witness is not None:
            assert result["overlap_witness"] is not None
            result["overlap_witness"]["path"] = str(args.overlap_witness)
            result["overlap_witness"]["file_sha256"] = file_digest(
                args.overlap_witness
            )
        result["source_sha256"] = file_digest(Path(__file__))
        write_json_atomic(args.output, result)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2

    print(
        json.dumps(
            {
                "output": str(args.output),
                "omission_sets_checked": result["enumeration"][
                    "omission_sets_checked"
                ],
                "distinct_residual_flows": result["enumeration"][
                    "distinct_residual_flows"
                ],
                "connected_completion_count": result["enumeration"][
                    "connected_completion_count"
                ],
                "covering_completion_count": result["enumeration"][
                    "covering_completion_count"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
