#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

try:
    from .covering import load_sequence, verify_sequence
    from .repair_support import load_support_certificate, support_digest
except ImportError:
    from covering import load_sequence, verify_sequence
    from repair_support import load_support_certificate, support_digest


def zero_ball_anchors(n: int, radius: int = 1) -> list[int]:
    if n <= 0:
        raise ValueError("n must be positive")
    if radius != 1:
        raise ValueError("the backbone portfolio supports radius 1")
    return [0, *(1 << bit for bit in range(n))]


def sequence_support(bits: list[int], n: int) -> set[int]:
    return {
        sum(
            bits[(start + offset) % len(bits)] << (n - 1 - offset)
            for offset in range(n)
        )
        for start in range(len(bits))
    }


def file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json_atomic(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    temporary.replace(path)


def git_revision(repository: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def run_case(
    *,
    python: Path,
    repair_script: Path,
    support: Path,
    support_edges: frozenset[int],
    support_sha256: str,
    output_dir: Path,
    n: int,
    radius: int,
    length: int,
    exact_overlap: int,
    connectivity: str,
    time_limit: float,
    deterministic_limit: float | None,
    solver_workers: int,
    seed: int,
    anchor: int,
    distinct_windows: bool,
) -> dict[str, Any]:
    name = f"anchor-{anchor:03d}"
    result_path = output_dir / f"{name}.json"
    sequence_path = output_dir / f"{name}.sequence.txt"
    log_path = output_dir / f"{name}.log"
    command = [
        str(python),
        str(repair_script),
        str(support),
        str(result_path),
        "--sequence-output",
        str(sequence_path),
        "--n",
        str(n),
        "--radius",
        str(radius),
        "--length",
        str(length),
        "--anchor-edge",
        str(anchor),
        "--partition-anchor",
        "--connectivity",
        connectivity,
        "--exact-overlap",
        str(exact_overlap),
        "--time-limit",
        str(time_limit),
        "--workers",
        str(solver_workers),
        "--seed",
        str(seed),
    ]
    if deterministic_limit is not None:
        command.extend(
            ["--deterministic-limit", str(deterministic_limit)]
        )
    if not distinct_windows:
        command.append("--allow-repeated-windows")

    result_path.unlink(missing_ok=True)
    sequence_path.unlink(missing_ok=True)
    started_at = utc_timestamp()
    try:
        with log_path.open("w", encoding="ascii") as log_stream:
            completed = subprocess.run(
                command,
                check=False,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
                text=True,
            )
    except OSError as exc:
        return {
            "anchor_edge": anchor,
            "case": name,
            "command": command,
            "error": f"could not run repair process: {exc}",
            "finished_at": utc_timestamp(),
            "log": log_path.name,
            "result": result_path.name,
            "started_at": started_at,
            "status": "ERROR",
        }

    record: dict[str, Any] = {
        "anchor_edge": anchor,
        "case": name,
        "command": command,
        "finished_at": utc_timestamp(),
        "log": log_path.name,
        "result": result_path.name,
        "return_code": completed.returncode,
        "started_at": started_at,
    }
    if completed.returncode not in {0, 3}:
        record["status"] = "ERROR"
        record["error"] = (
            f"repair process returned unexpected code "
            f"{completed.returncode}"
        )
        return record
    if not result_path.is_file():
        record["status"] = "ERROR"
        record["error"] = "repair process did not write a result"
        return record

    try:
        case_result = json.loads(result_path.read_text(encoding="ascii"))
    except (OSError, json.JSONDecodeError) as exc:
        record["status"] = "ERROR"
        record["error"] = f"could not parse repair result: {exc}"
        return record
    if not isinstance(case_result, dict):
        record["status"] = "ERROR"
        record["error"] = "repair result is not a JSON object"
        return record

    expected_fields = {
        "anchor_edge": anchor,
        "base_support_sha256": support_sha256,
        "connectivity_mode": connectivity,
        "distinct_windows": distinct_windows,
        "exact_overlap": exact_overlap,
        "length": length,
        "n": n,
        "partition_anchor": True,
        "radius": radius,
    }
    mismatches = {
        key: {"actual": case_result.get(key), "expected": expected}
        for key, expected in expected_fields.items()
        if case_result.get(key) != expected
    }
    if mismatches:
        record["status"] = "ERROR"
        record["error"] = "repair result parameters do not match the case"
        record["parameter_mismatches"] = mismatches
        return record

    status = case_result.get("status")
    if status not in {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN"}:
        record["status"] = "ERROR"
        record["error"] = f"unexpected repair status: {status!r}"
        return record
    expected_return_code = 3 if status == "UNKNOWN" else 0
    if completed.returncode != expected_return_code:
        record["status"] = "ERROR"
        record["error"] = (
            f"repair status {status} is inconsistent with return code "
            f"{completed.returncode}"
        )
        return record

    record["status"] = status
    record["wall_seconds"] = case_result.get("wall_seconds")
    record["branches"] = case_result.get("branches")
    record["conflicts"] = case_result.get("conflicts")
    if status in {"OPTIMAL", "FEASIBLE"}:
        if not case_result.get("valid"):
            record["status"] = "ERROR"
            record["error"] = "feasible repair result is not marked valid"
            return record
        if not sequence_path.is_file():
            record["status"] = "ERROR"
            record["error"] = "feasible repair result has no sequence"
            return record
        try:
            bits = load_sequence(sequence_path)
            report = verify_sequence(
                bits,
                n=n,
                radius=radius,
                expected_length=length,
            )
        except (OSError, ValueError) as exc:
            record["status"] = "ERROR"
            record["error"] = f"could not verify repair sequence: {exc}"
            return record
        selected = sequence_support(bits, n)
        anchors = zero_ball_anchors(n, radius)
        anchor_index = anchors.index(anchor)
        checks = {
            "anchor_present": anchor in selected,
            "window_class": (
                len(selected) == length
                if distinct_windows
                else len(selected) <= length
            ),
            "exact_overlap": (
                len(selected & support_edges) == exact_overlap
            ),
            "partition_anchor": not (
                selected & set(anchors[:anchor_index])
            ),
            "reported_overlap": (
                case_result.get("overlap") == exact_overlap
            ),
            "verified_cover": report.valid,
        }
        if not all(checks.values()):
            record["status"] = "ERROR"
            record["error"] = "independent sequence checks failed"
            record["sequence_checks"] = checks
            return record
        record["valid"] = True
        record["overlap"] = exact_overlap
        record["sequence"] = sequence_path.name
        record["sequence_checks"] = checks
    elif case_result.get("valid") or sequence_path.exists():
        record["status"] = "ERROR"
        record["error"] = "non-feasible repair result retained a sequence"
    return record


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run all zero-ball anchor cases for an exact support-backbone "
            "overlap shell."
        )
    )
    parser.add_argument("support", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--radius", type=int, required=True)
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument("--exact-overlap", type=int, required=True)
    parser.add_argument("--allow-repeated-windows", action="store_true")
    parser.add_argument(
        "--connectivity",
        choices=("flow", "tree"),
        default="tree",
    )
    parser.add_argument("--time-limit", type=float, default=600.0)
    parser.add_argument("--deterministic-limit", type=float)
    parser.add_argument("--solver-workers", type=int, default=1)
    parser.add_argument(
        "--parallel-cases",
        type=int,
        default=max(1, os.cpu_count() or 1),
    )
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--python",
        type=Path,
        default=Path(sys.executable),
    )
    args = parser.parse_args()

    if args.time_limit <= 0:
        parser.error("--time-limit must be positive")
    if args.radius != 1:
        parser.error("the backbone portfolio currently supports radius 1")
    if args.solver_workers <= 0 or args.parallel_cases <= 0:
        parser.error("worker counts must be positive")
    if args.seed < 0:
        parser.error("--seed must be nonnegative")

    source_path = Path(__file__).resolve()
    repository = source_path.parent.parent
    repair_script = source_path.with_name("repair_support.py")
    support = load_support_certificate(args.support, n=args.n)
    support_sha256 = support_digest(support)
    if not 0 <= args.exact_overlap <= len(support):
        parser.error("--exact-overlap is outside the reference support")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.output_dir / "summary.json"
    anchors = zero_ball_anchors(args.n, args.radius)
    summary: dict[str, Any] = {
        "cases": [],
        "connectivity": args.connectivity,
        "distinct_windows": not args.allow_repeated_windows,
        "exact_overlap": args.exact_overlap,
        "git_revision": git_revision(repository),
        "length": args.length,
        "n": args.n,
        "parallel_cases": args.parallel_cases,
        "portfolio_case_count": len(anchors),
        "portfolio_kind": "disjoint minimum zero-ball anchor partition",
        "radius": args.radius,
        "repeated_windows_allowed": args.allow_repeated_windows,
        "repair_source_sha256": file_digest(repair_script),
        "runner_source_sha256": file_digest(source_path),
        "seed": args.seed,
        "solver_workers_per_case": args.solver_workers,
        "started_at": utc_timestamp(),
        "support": str(args.support),
        "support_file_sha256": file_digest(args.support),
        "support_sha256": support_sha256,
        "support_size": len(support),
        "time_limit_seconds_per_case": args.time_limit,
    }
    write_json_atomic(summary_path, summary)

    with ThreadPoolExecutor(max_workers=args.parallel_cases) as executor:
        futures = {
            executor.submit(
                run_case,
                python=args.python,
                repair_script=repair_script,
                support=args.support.resolve(),
                support_edges=frozenset(support),
                support_sha256=support_sha256,
                output_dir=args.output_dir,
                n=args.n,
                radius=args.radius,
                length=args.length,
                exact_overlap=args.exact_overlap,
                connectivity=args.connectivity,
                time_limit=args.time_limit,
                deterministic_limit=args.deterministic_limit,
                solver_workers=args.solver_workers,
                seed=args.seed,
                anchor=anchor,
                distinct_windows=not args.allow_repeated_windows,
            ): anchor
            for anchor in anchors
        }
        for future in as_completed(futures):
            anchor = futures[future]
            try:
                record = future.result()
            except Exception as exc:
                record = {
                    "anchor_edge": anchor,
                    "case": f"anchor-{anchor:03d}",
                    "error": (
                        f"unexpected case failure: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                    "finished_at": utc_timestamp(),
                    "status": "ERROR",
                }
            summary["cases"].append(record)
            summary["cases"].sort(key=lambda item: item["anchor_edge"])
            write_json_atomic(summary_path, summary)
            print(f"{record['case']}: {record['status']}", flush=True)

    counts: dict[str, int] = {}
    for record in summary["cases"]:
        status = record["status"]
        counts[status] = counts.get(status, 0) + 1
    summary["finished_at"] = utc_timestamp()
    summary["status_counts"] = counts
    write_json_atomic(summary_path, summary)
    print(json.dumps(counts, sort_keys=True))
    return int("ERROR" in counts)


if __name__ == "__main__":
    raise SystemExit(main())
