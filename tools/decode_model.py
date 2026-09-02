#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .covering import verify_sequence
except ImportError:
    from covering import verify_sequence


def parse_dimacs_model(text: str, length: int) -> list[int]:
    if length <= 0:
        raise ValueError("length must be positive")

    status: str | None = None
    assignment: dict[int, bool] = {}
    for line in text.splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] == "s":
            status = " ".join(fields[1:])
            continue
        if fields[0] != "v":
            continue
        for token in fields[1:]:
            literal = int(token)
            if literal == 0:
                continue
            variable = abs(literal)
            if variable > length:
                continue
            value = literal > 0
            if variable in assignment and assignment[variable] != value:
                raise ValueError(f"contradictory assignment for variable {variable}")
            assignment[variable] = value

    if status != "SATISFIABLE":
        raise ValueError(f"solver status is {status or 'missing'}")

    missing = [
        variable
        for variable in range(1, length + 1)
        if variable not in assignment
    ]
    if missing:
        raise ValueError(
            "model omits sequence variables: "
            + ", ".join(str(variable) for variable in missing)
        )

    return [int(assignment[variable]) for variable in range(1, length + 1)]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Decode and verify sequence bits from a DIMACS solver model."
    )
    parser.add_argument("model", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--radius", type=int, required=True)
    parser.add_argument("--length", type=int, required=True)
    args = parser.parse_args()

    try:
        bits = parse_dimacs_model(
            args.model.read_text(encoding="ascii"),
            args.length,
        )
        report = verify_sequence(
            bits,
            n=args.n,
            radius=args.radius,
            expected_length=args.length,
        )
    except (OSError, ValueError, NotImplementedError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, sort_keys=True))
        return 2

    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    if not report.valid:
        return 1

    args.output.write_text(
        " ".join(str(bit) for bit in bits) + "\n",
        encoding="ascii",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
