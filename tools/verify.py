#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from covering import load_sequence, verify_sequence


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a cyclic binary covering sequence.")
    parser.add_argument("sequence")
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--radius", type=int, required=True)
    parser.add_argument("--expected-length", type=int)
    args = parser.parse_args()

    try:
        bits = load_sequence(args.sequence)
        report = verify_sequence(
            bits,
            n=args.n,
            radius=args.radius,
            expected_length=args.expected_length,
        )
    except (OSError, ValueError, NotImplementedError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, sort_keys=True))
        return 2

    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.valid else 1


if __name__ == "__main__":
    sys.exit(main())
