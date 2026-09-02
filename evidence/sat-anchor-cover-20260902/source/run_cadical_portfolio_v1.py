#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import threading
from typing import Any

try:
    from .covering import verify_sequence
    from .decode_model import parse_dimacs_model
    from .generate_cnf import write_pattern_cnf
except ImportError:
    from covering import verify_sequence
    from decode_model import parse_dimacs_model
    from generate_cnf import write_pattern_cnf


def reverse_word(word: int, n: int) -> int:
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= word < (1 << n):
        raise ValueError("word is outside the word range")

    reversed_word = 0
    for _ in range(n):
        reversed_word = (reversed_word << 1) | (word & 1)
        word >>= 1
    return reversed_word


def canonical_zero_anchor_cases(n: int) -> list[tuple[int, int, int]]:
    """Return one transition case from each reflection orbit."""
    if n <= 0:
        raise ValueError("n must be positive")

    cases: list[tuple[int, int, int]] = []
    for word in (0, *(1 << bit for bit in range(n))):
        reflected_word = reverse_word(word, n)
        if word > reflected_word:
            continue
        for predecessor in (0, 1):
            for successor in (0, 1):
                if (
                    word == reflected_word
                    and successor > predecessor
                ):
                    continue
                cases.append((word, predecessor, successor))
    return cases


def sequence_support_size(bits: list[int], n: int) -> int:
    length = len(bits)
    return len(
        {
            tuple(bits[(start + offset) % length] for offset in range(n))
            for start in range(length)
        }
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def solver_version(solver: Path) -> str:
    result = subprocess.run(
        [str(solver), "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    output = (result.stdout + result.stderr).strip()
    return output or f"exit {result.returncode}"


def case_name(anchor: int, predecessor: int, successor: int) -> str:
    return f"anchor-{anchor:03d}-p{predecessor}-s{successor}"


def run_case(
    *,
    solver: Path,
    output_dir: Path,
    cnf_dir: Path,
    n: int,
    radius: int,
    length: int,
    exact_support: int | None,
    complement_leader: bool,
    time_limit: int,
    solver_options: list[str],
    keep_cnf: bool,
    anchor: int,
    predecessor: int,
    successor: int,
    stop_event: threading.Event,
) -> dict[str, Any]:
    name = case_name(anchor, predecessor, successor)
    if stop_event.is_set():
        return {
            "anchor_word": anchor,
            "case": name,
            "predecessor_bit": predecessor,
            "status": "SKIPPED",
            "successor_bit": successor,
        }

    cnf_path = cnf_dir / f"{name}.cnf"
    log_path = output_dir / f"{name}.log"
    result_path = output_dir / f"{name}.result"
    sequence_path = output_dir / f"{name}.sequence.txt"
    started_at = utc_timestamp()

    seed_bits = [0] * length if complement_leader else None
    max_distance = length // 2 if complement_leader else None
    variables, clauses = write_pattern_cnf(
        cnf_path,
        n=n,
        radius=radius,
        length=length,
        symmetry=False,
        seed_bits=seed_bits,
        max_distance=max_distance,
        exact_support=exact_support,
        anchor_word=anchor,
        anchor_predecessor_bit=predecessor,
        anchor_successor_bit=successor,
    )
    cnf_sha256 = sha256_file(cnf_path)
    command = [
        str(solver),
        "--sat",
        *solver_options,
        "-t",
        str(time_limit),
        "-w",
        str(result_path),
        str(cnf_path),
    ]
    with log_path.open("w", encoding="ascii") as log_stream:
        completed = subprocess.run(
            command,
            check=False,
            stdout=log_stream,
            stderr=subprocess.STDOUT,
            text=True,
        )

    status = {
        10: "SATISFIABLE",
        20: "UNSATISFIABLE",
    }.get(completed.returncode, "UNKNOWN")
    record: dict[str, Any] = {
        "anchor_word": anchor,
        "case": name,
        "clauses": clauses,
        "cnf_sha256": cnf_sha256,
        "command": command,
        "finished_at": utc_timestamp(),
        "log": log_path.name,
        "predecessor_bit": predecessor,
        "return_code": completed.returncode,
        "started_at": started_at,
        "status": status,
        "successor_bit": successor,
        "variables": variables,
    }

    if status == "SATISFIABLE":
        try:
            bits = parse_dimacs_model(
                result_path.read_text(encoding="ascii"),
                length,
            )
            report = verify_sequence(
                bits,
                n=n,
                radius=radius,
                expected_length=length,
            )
            anchored_word = 0
            for bit in bits[:n]:
                anchored_word = (anchored_word << 1) | bit
            support_size = sequence_support_size(bits, n)
            model_checks = {
                "anchor_word": anchored_word == anchor,
                "complement_leader": (
                    not complement_leader
                    or sum(bits) <= length // 2
                ),
                "exact_support": (
                    exact_support is None
                    or support_size == exact_support
                ),
                "predecessor_bit": bits[-1] == predecessor,
                "successor_bit": bits[n % length] == successor,
                "verified_cover": report.valid,
            }
            if not all(model_checks.values()):
                raise ValueError(f"model checks failed: {model_checks}")

            sequence_path.write_text(
                " ".join(str(bit) for bit in bits) + "\n",
                encoding="ascii",
            )
            record["model_checks"] = model_checks
            record["ones"] = sum(bits)
            record["sequence"] = sequence_path.name
            record["support_size"] = support_size
            record["verification"] = report.to_dict()
            stop_event.set()
        except (OSError, ValueError, NotImplementedError) as exc:
            record["error"] = str(exc)
            record["status"] = "ERROR"

    if not keep_cnf:
        cnf_path.unlink(missing_ok=True)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run reflection-reduced zero-anchor CaDiCaL cases for a "
            "binary cyclic covering sequence."
        )
    )
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--solver", type=Path, required=True)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--radius", type=int, required=True)
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument("--exact-support", type=int)
    parser.add_argument(
        "--time-limit",
        type=int,
        default=300,
        help="wall-clock seconds per case",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, os.cpu_count() or 1),
    )
    parser.add_argument(
        "--solver-option",
        action="append",
        default=[],
        help="additional CaDiCaL option, repeat as needed",
    )
    parser.add_argument(
        "--no-complement-leader",
        action="store_true",
        help="do not constrain sequence weight to at most floor(length/2)",
    )
    parser.add_argument("--keep-cnf", action="store_true")
    args = parser.parse_args()

    if args.radius != 1:
        parser.error("the portfolio currently supports radius 1")
    if args.n <= 0 or args.length < args.n:
        parser.error("require 0 < n <= length")
    if args.time_limit <= 0:
        parser.error("--time-limit must be positive")
    if args.workers <= 0:
        parser.error("--workers must be positive")
    if not args.solver.is_file():
        parser.error("--solver must name an executable file")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    cnf_dir = args.output_dir / "cnf"
    cnf_dir.mkdir(exist_ok=True)
    cases = canonical_zero_anchor_cases(args.n)
    source_path = Path(__file__).resolve()
    generator_path = source_path.with_name("generate_cnf.py")
    repository = source_path.parent.parent
    summary_path = args.output_dir / "summary.json"
    summary: dict[str, Any] = {
        "cases": [],
        "complement_leader": not args.no_complement_leader,
        "exact_support": args.exact_support,
        "generator_sha256": sha256_file(generator_path),
        "git_revision": git_revision(repository),
        "host": {
            "logical_cpus": os.cpu_count(),
            "machine": platform.machine(),
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "length": args.length,
        "n": args.n,
        "portfolio_case_count": len(cases),
        "portfolio_kind": "reflection-reduced zero-anchor transition cover",
        "radius": args.radius,
        "runner_sha256": sha256_file(source_path),
        "solver": str(args.solver.resolve()),
        "solver_options": args.solver_option,
        "solver_sha256": sha256_file(args.solver),
        "solver_version": solver_version(args.solver),
        "started_at": utc_timestamp(),
        "time_limit_seconds_per_case": args.time_limit,
        "workers": args.workers,
    }
    write_json_atomic(summary_path, summary)

    stop_event = threading.Event()
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(
                run_case,
                solver=args.solver.resolve(),
                output_dir=args.output_dir,
                cnf_dir=cnf_dir,
                n=args.n,
                radius=args.radius,
                length=args.length,
                exact_support=args.exact_support,
                complement_leader=not args.no_complement_leader,
                time_limit=args.time_limit,
                solver_options=args.solver_option,
                keep_cnf=args.keep_cnf,
                anchor=anchor,
                predecessor=predecessor,
                successor=successor,
                stop_event=stop_event,
            )
            for anchor, predecessor, successor in cases
        ]
        for future in as_completed(futures):
            record = future.result()
            summary["cases"].append(record)
            summary["cases"].sort(key=lambda item: item["case"])
            write_json_atomic(summary_path, summary)
            print(f"{record['case']}: {record['status']}", flush=True)

    summary["finished_at"] = utc_timestamp()
    counts: dict[str, int] = {}
    for record in summary["cases"]:
        status = record["status"]
        counts[status] = counts.get(status, 0) + 1
    summary["status_counts"] = counts
    write_json_atomic(summary_path, summary)

    if not args.keep_cnf:
        try:
            cnf_dir.rmdir()
        except OSError:
            pass
    print(json.dumps(counts, sort_keys=True))
    return int("ERROR" in counts)


if __name__ == "__main__":
    raise SystemExit(main())
