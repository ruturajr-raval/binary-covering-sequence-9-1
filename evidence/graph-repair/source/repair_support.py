#!/usr/bin/env python3
from __future__ import annotations

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from typing import Any

try:
    from .covering import verify_sequence
    from .flow_cp_sat import (
        build_flow_model,
        de_bruijn_incidence,
        edge_prefix,
        edge_suffix,
        extract_euler_sequence,
        hamming_ball,
        load_cp_model,
        write_sequence,
    )
except ImportError:
    from covering import verify_sequence
    from flow_cp_sat import (
        build_flow_model,
        de_bruijn_incidence,
        edge_prefix,
        edge_suffix,
        extract_euler_sequence,
        hamming_ball,
        load_cp_model,
        write_sequence,
    )


def load_support_certificate(path: Path, *, n: int) -> list[int]:
    payload = json.loads(path.read_text(encoding="ascii"))
    values = payload.get("selected_edges") if isinstance(payload, dict) else payload
    if not isinstance(values, list) or not all(
        isinstance(value, int) for value in values
    ):
        raise ValueError(
            "support certificate must be a list or contain selected_edges"
        )
    if len(set(values)) != len(values):
        raise ValueError("support certificate contains duplicate edges")
    if any(value < 0 or value >= 1 << n for value in values):
        raise ValueError("support certificate contains an out-of-range edge")
    return sorted(values)


def support_digest(support: list[int]) -> str:
    normalized = " ".join(str(word) for word in sorted(support)) + "\n"
    return sha256(normalized.encode("ascii")).hexdigest()


def file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def analyze_support(
    support: list[int],
    *,
    n: int,
    radius: int,
) -> dict[str, Any]:
    support_set = set(support)
    outgoing, incoming = de_bruijn_incidence(n)
    balanced = all(
        sum(word in support_set for word in outgoing[vertex])
        == sum(word in support_set for word in incoming[vertex])
        for vertex in range(len(outgoing))
    )
    uncovered = [
        target
        for target in range(1 << n)
        if not any(
            word in support_set for word in hamming_ball(target, n, radius)
        )
    ]

    active: set[int] = set()
    adjacency = [set() for _ in range(len(outgoing))]
    for word in support:
        prefix = edge_prefix(word, n)
        suffix = edge_suffix(word, n)
        active.add(prefix)
        active.add(suffix)
        adjacency[prefix].add(suffix)
        adjacency[suffix].add(prefix)

    component_vertex_sets: list[set[int]] = []
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
        component_vertex_sets.append(component)

    component_edge_counts = sorted(
        sum(
            edge_prefix(word, n) in component
            for word in support
        )
        for component in component_vertex_sets
    )
    return {
        "distinct_edges": len(support_set),
        "balanced": balanced,
        "covered_words": (1 << n) - len(uncovered),
        "uncovered_words": uncovered,
        "component_count": len(component_vertex_sets),
        "component_edge_counts": component_edge_counts,
    }


def solve_support_repair(
    *,
    support: list[int],
    n: int,
    radius: int,
    length: int,
    anchor_edge: int,
    partition_anchor: bool,
    connectivity_mode: str,
    minimum_overlap: int | None,
    maximize_overlap: bool,
    time_limit: float,
    deterministic_limit: float | None,
    workers: int,
    seed: int,
    log_progress: bool,
) -> tuple[dict[str, Any], list[int] | None]:
    if len(support) != length:
        raise ValueError("support certificate size must equal the target length")
    if minimum_overlap is not None and not 0 <= minimum_overlap <= length:
        raise ValueError("minimum overlap must be between zero and length")
    if time_limit <= 0 or workers <= 0 or seed < 0:
        raise ValueError(
            "time limit and workers must be positive; seed is nonnegative"
        )
    if deterministic_limit is not None and deterministic_limit <= 0:
        raise ValueError("deterministic limit must be positive")
    if connectivity_mode not in {"flow", "tree"}:
        raise ValueError("repair connectivity mode must be flow or tree")

    cp_model = load_cp_model()
    base_report = analyze_support(support, n=n, radius=radius)
    artifacts = build_flow_model(
        n=n,
        radius=radius,
        length=length,
        anchor_edge=anchor_edge,
        distinct_windows=True,
        connectivity_mode=connectivity_mode,
        partition_anchor=partition_anchor,
    )
    support_set = set(support)
    for word in range(1 << n):
        selected = int(word in support_set)
        artifacts.model.add_hint(artifacts.use[word], selected)
        artifacts.model.add_hint(artifacts.count[word], selected)

    overlap = sum(artifacts.use[word] for word in support)
    if minimum_overlap is not None:
        artifacts.model.add(overlap >= minimum_overlap)
    if maximize_overlap:
        artifacts.model.maximize(overlap)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    if deterministic_limit is not None:
        solver.parameters.max_deterministic_time = deterministic_limit
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = seed
    solver.parameters.log_search_progress = log_progress
    status = solver.solve(artifacts.model)
    response = solver.response_proto
    status_name = solver.status_name(status)

    summary: dict[str, Any] = {
        "status": status_name,
        "n": n,
        "radius": radius,
        "length": length,
        "anchor_edge": anchor_edge,
        "partition_anchor": partition_anchor,
        "connectivity_mode": connectivity_mode,
        "base_support_size": len(support),
        "base_support_sha256": support_digest(support),
        "base_support_report": base_report,
        "solver": "OR-Tools CP-SAT",
        "solver_version": version("ortools"),
        "flow_source_sha256": file_digest(
            Path(__file__).with_name("flow_cp_sat.py")
        ),
        "repair_source_sha256": file_digest(Path(__file__)),
        "minimum_overlap": minimum_overlap,
        "maximum_replacements": (
            None
            if minimum_overlap is None
            else length - minimum_overlap
        ),
        "maximize_overlap": maximize_overlap,
        "workers": workers,
        "seed": seed,
        "time_limit": time_limit,
        "deterministic_limit": deterministic_limit,
        "wall_seconds": response.wall_time,
        "deterministic_time": response.deterministic_time,
        "branches": response.num_branches,
        "conflicts": response.num_conflicts,
        "binary_propagations": response.num_binary_propagations,
        "integer_propagations": response.num_integer_propagations,
        "restarts": response.num_restarts,
        "lp_iterations": response.num_lp_iterations,
        "model_variables": len(artifacts.model.proto.variables),
        "model_constraints": len(artifacts.model.proto.constraints),
    }
    if maximize_overlap:
        summary["best_objective_bound"] = solver.best_objective_bound
    if status == cp_model.INFEASIBLE and minimum_overlap is not None:
        summary["excluded_overlap_at_least"] = minimum_overlap
        summary["required_replacements_at_least"] = (
            length - minimum_overlap + 1
        )

    if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
        return summary, None

    counts = [solver.value(variable) for variable in artifacts.count]
    bits = extract_euler_sequence(counts, n=n, root=artifacts.root)
    report = verify_sequence(
        bits,
        n=n,
        radius=radius,
        expected_length=length,
    )
    if not report.valid:
        raise RuntimeError("repair model decoded to an invalid sequence")
    summary.update(
        {
            "valid": True,
            "overlap": sum(counts[word] for word in support),
            "replacements": length
            - sum(counts[word] for word in support),
            "selected_edges": [
                word for word, multiplicity in enumerate(counts) if multiplicity
            ],
        }
    )
    return summary, bits


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Search for a connected covering cycle near a support certificate."
        )
    )
    parser.add_argument("support", type=Path)
    parser.add_argument("result", type=Path)
    parser.add_argument("--sequence-output", type=Path)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--radius", type=int, required=True)
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument("--anchor-edge", type=int, required=True)
    parser.add_argument("--partition-anchor", action="store_true")
    parser.add_argument(
        "--connectivity",
        choices=("flow", "tree"),
        default="tree",
    )
    parser.add_argument("--minimum-overlap", type=int)
    parser.add_argument("--maximize-overlap", action="store_true")
    parser.add_argument("--time-limit", type=float, default=300.0)
    parser.add_argument("--deterministic-limit", type=float)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--log-progress", action="store_true")
    args = parser.parse_args()

    try:
        support = load_support_certificate(args.support, n=args.n)
        summary, bits = solve_support_repair(
            support=support,
            n=args.n,
            radius=args.radius,
            length=args.length,
            anchor_edge=args.anchor_edge,
            partition_anchor=args.partition_anchor,
            connectivity_mode=args.connectivity,
            minimum_overlap=args.minimum_overlap,
            maximize_overlap=args.maximize_overlap,
            time_limit=args.time_limit,
            deterministic_limit=args.deterministic_limit,
            workers=args.workers,
            seed=args.seed,
            log_progress=args.log_progress,
        )
        if bits is not None and args.sequence_output is not None:
            write_sequence(args.sequence_output, bits)
            summary["sequence_output"] = str(args.sequence_output)
        args.result.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="ascii",
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2

    if summary["status"] == "UNKNOWN":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
