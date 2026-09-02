#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from covering import coverage_counts, load_sequence, verify_sequence


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze all one-bit deletions of a baseline.")
    parser.add_argument("sequence")
    parser.add_argument("--n", type=int, default=9)
    parser.add_argument("--radius", type=int, default=1)
    args = parser.parse_args()

    baseline = load_sequence(args.sequence)
    baseline_report = verify_sequence(
        baseline,
        n=args.n,
        radius=args.radius,
        expected_length=len(baseline),
    )
    if not baseline_report.valid:
        raise SystemExit("baseline certificate is invalid")

    rows: list[dict[str, object]] = []
    for deleted in range(len(baseline)):
        candidate = baseline[:deleted] + baseline[deleted + 1 :]
        _, counts = coverage_counts(candidate, args.n, args.radius)
        uncovered = [word for word, count in enumerate(counts) if count == 0]
        rows.append(
            {
                "deleted_index": deleted,
                "deleted_bit": baseline[deleted],
                "uncovered_count": len(uncovered),
                "singleton_count": sum(count == 1 for count in counts),
                "uncovered_words": uncovered,
            }
        )

    rows.sort(key=lambda row: (row["uncovered_count"], row["singleton_count"]))
    print(
        json.dumps(
            {
                "baseline_length": len(baseline),
                "candidate_length": len(baseline) - 1,
                "best": rows[0],
                "all_deletions": rows,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
