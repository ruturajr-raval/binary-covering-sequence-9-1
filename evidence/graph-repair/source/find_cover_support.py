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
) -> dict[str, Any]:
    if time_limit <= 0 or workers <= 0 or seed < 0:
        raise ValueError(
            "time limit and workers must be positive; seed is nonnegative"
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
    )
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
    if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
        return result

    selected_edges = [
        word
        for word, variable in enumerate(artifacts.use)
        if solver.value(variable)
    ]
    result.update(
        {
            "selected_edges": selected_edges,
            "support_sha256": support_digest(selected_edges),
            "support_report": analyze_support(
                selected_edges,
                n=n,
                radius=radius,
            ),
        }
    )
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
