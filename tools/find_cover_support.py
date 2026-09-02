#!/usr/bin/env python3
from __future__ import annotations

import argparse
from importlib.metadata import version
import json
from pathlib import Path
from typing import Any

try:
    from .covering import load_sequence
    from .flow_cp_sat import build_flow_model, load_cp_model
    from .repair_support import analyze_support, file_digest, support_digest
except ImportError:
    from covering import load_sequence
    from flow_cp_sat import build_flow_model, load_cp_model
    from repair_support import analyze_support, file_digest, support_digest


def find_cover_support(
    *,
    n: int,
    radius: int,
    length: int,
    anchor_edge: int,
    partition_anchor: bool,
    hint_bits: list[int] | None,
    time_limit: float,
    workers: int,
    seed: int,
    log_progress: bool,
    maximum_active_vertices: int | None = None,
    minimize_active_vertices: bool = False,
) -> dict[str, Any]:
    if time_limit <= 0 or workers <= 0 or seed < 0:
        raise ValueError(
            "time limit and workers must be positive; seed is nonnegative"
        )
    if not isinstance(minimize_active_vertices, bool):
        raise ValueError("minimize active vertices must be a Boolean")
    if maximum_active_vertices is not None:
        if (
            isinstance(maximum_active_vertices, bool)
            or not isinstance(maximum_active_vertices, int)
        ):
            raise ValueError("maximum active vertices must be an integer")
        if n <= 0:
            raise ValueError("n must be positive")
        vertex_count = 1 << max(0, n - 1)
        if not 1 <= maximum_active_vertices <= vertex_count:
            raise ValueError(
                "maximum active vertices must be between one and "
                f"{vertex_count}"
            )

    cp_model = load_cp_model()
    artifacts = build_flow_model(
        n=n,
        radius=radius,
        length=length,
        anchor_edge=anchor_edge,
        distinct_windows=True,
        hint_bits=hint_bits,
        connectivity_mode="none",
        partition_anchor=partition_anchor,
        add_autocorrelation_orbit_constraints=False,
    )
    active_vertex_count = sum(artifacts.vertex_used)
    if maximum_active_vertices is not None:
        artifacts.model.add(
            active_vertex_count <= maximum_active_vertices
        )
    if minimize_active_vertices:
        artifacts.model.minimize(active_vertex_count)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = seed
    solver.parameters.log_search_progress = log_progress
    status = solver.solve(artifacts.model)
    response = solver.response_proto
    result: dict[str, Any] = {
        "status": solver.status_name(status),
        "n": n,
        "radius": radius,
        "length": length,
        "anchor_edge": anchor_edge,
        "partition_anchor": partition_anchor,
        "connectivity_mode": "none",
        "distinct_windows": True,
        "hint_applied": hint_bits is not None,
        "maximum_active_vertices": maximum_active_vertices,
        "minimize_active_vertices": minimize_active_vertices,
        "autocorrelation_orbit_constraints_enabled": False,
        "autocorrelation_orbit_bounds": (
            artifacts.autocorrelation_orbit_bounds
        ),
        "workers": workers,
        "seed": seed,
        "time_limit": time_limit,
        "solver": "OR-Tools CP-SAT",
        "solver_version": version("ortools"),
        "flow_source_sha256": file_digest(
            Path(__file__).with_name("flow_cp_sat.py")
        ),
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
    if minimize_active_vertices:
        result.update(
            {
                "objective": "minimize_active_vertices",
                "best_objective_bound": solver.best_objective_bound,
            }
        )
    if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
        return result

    selected_edges = [
        word
        for word, variable in enumerate(artifacts.use)
        if solver.value(variable)
    ]
    result.update(
        {
            "active_vertex_count": sum(
                solver.value(variable)
                for variable in artifacts.vertex_used
            ),
            "selected_edges": selected_edges,
            "support_sha256": support_digest(selected_edges),
            "support_report": analyze_support(
                selected_edges,
                n=n,
                radius=radius,
            ),
        }
    )
    if minimize_active_vertices:
        result["objective_value"] = solver.objective_value
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find a balanced covering support without connectivity."
    )
    parser.add_argument("output", type=Path)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--radius", type=int, required=True)
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument("--anchor-edge", type=int, required=True)
    parser.add_argument("--partition-anchor", action="store_true")
    parser.add_argument("--hint-sequence", type=Path)
    parser.add_argument("--time-limit", type=float, default=300.0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--log-progress", action="store_true")
    parser.add_argument("--maximum-active-vertices", type=int)
    parser.add_argument("--minimize-active-vertices", action="store_true")
    args = parser.parse_args()

    try:
        hint_bits = (
            load_sequence(args.hint_sequence)
            if args.hint_sequence is not None
            else None
        )
        result = find_cover_support(
            n=args.n,
            radius=args.radius,
            length=args.length,
            anchor_edge=args.anchor_edge,
            partition_anchor=args.partition_anchor,
            hint_bits=hint_bits,
            time_limit=args.time_limit,
            workers=args.workers,
            seed=args.seed,
            log_progress=args.log_progress,
            maximum_active_vertices=args.maximum_active_vertices,
            minimize_active_vertices=args.minimize_active_vertices,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="ascii",
        )
        print(json.dumps(result, indent=2, sort_keys=True))
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2
    return 0 if "selected_edges" in result else 3


if __name__ == "__main__":
    raise SystemExit(main())
