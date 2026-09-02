#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .flow_cp_sat import edge_prefix, edge_suffix, hamming_ball
    from .repair_support import (
        analyze_support,
        load_support_certificate,
        support_digest,
    )
except ImportError:
    from flow_cp_sat import edge_prefix, edge_suffix, hamming_ball
    from repair_support import (
        analyze_support,
        load_support_certificate,
        support_digest,
    )


def directed_cycle_lengths(support: set[int], *, n: int) -> list[int]:
    outgoing: dict[int, int] = {}
    incoming_count: dict[int, int] = {}
    for word in support:
        prefix = edge_prefix(word, n)
        suffix = edge_suffix(word, n)
        if prefix in outgoing:
            raise ValueError("support is not a directed cycle cover")
        outgoing[prefix] = suffix
        incoming_count[suffix] = incoming_count.get(suffix, 0) + 1
    if set(outgoing) != set(incoming_count) or any(
        count != 1 for count in incoming_count.values()
    ):
        raise ValueError("support is not a directed cycle cover")

    lengths: list[int] = []
    unseen = set(outgoing)
    while unseen:
        start = min(unseen)
        current = start
        length = 0
        while current in unseen:
            unseen.remove(current)
            current = outgoing[current]
            length += 1
        if current != start:
            raise ValueError("support is not a disjoint union of cycles")
        lengths.append(length)
    return sorted(lengths)


def analyze_cross_joins(
    support: list[int],
    *,
    n: int,
    radius: int,
) -> dict[str, Any]:
    support_set = set(support)
    cycle_lengths = directed_cycle_lengths(support_set, n=n)
    selected_outgoing = {
        edge_prefix(word, n): word for word in support_set
    }
    conjugate_mask = 1 << (n - 2)
    candidates = []

    for prefix in range(conjugate_mask):
        conjugate = prefix ^ conjugate_mask
        if (
            prefix not in selected_outgoing
            or conjugate not in selected_outgoing
        ):
            continue
        first_edge = selected_outgoing[prefix]
        second_edge = selected_outgoing[conjugate]
        first_bit = first_edge & 1
        second_bit = second_edge & 1
        if first_bit == second_bit:
            continue

        added = {
            (prefix << 1) | second_bit,
            (conjugate << 1) | first_bit,
        }
        switched = (
            support_set - {first_edge, second_edge}
        ) | added
        uncovered = [
            target
            for target in range(1 << n)
            if not any(
                word in switched
                for word in hamming_ball(target, n, radius)
            )
        ]
        candidates.append(
            {
                "conjugate_vertices": [prefix, conjugate],
                "removed_edges": sorted([first_edge, second_edge]),
                "added_edges": sorted(added),
                "cycle_lengths_after": directed_cycle_lengths(
                    switched,
                    n=n,
                ),
                "uncovered_words": uncovered,
                "valid_cover": not uncovered,
            }
        )

    return {
        "n": n,
        "radius": radius,
        "support_sha256": support_digest(support),
        "support_report": analyze_support(
            support,
            n=n,
            radius=radius,
        ),
        "cycle_lengths_before": cycle_lengths,
        "cross_join_candidate_count": len(candidates),
        "valid_cross_join_count": sum(
            candidate["valid_cover"] for candidate in candidates
        ),
        "candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze cycle components and conjugate cross-joins."
    )
    parser.add_argument("support", type=Path)
    parser.add_argument("result", type=Path)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--radius", type=int, required=True)
    args = parser.parse_args()

    try:
        support = load_support_certificate(args.support, n=args.n)
        result = analyze_cross_joins(
            support,
            n=args.n,
            radius=args.radius,
        )
        args.result.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="ascii",
        )
        print(json.dumps(result, indent=2, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
