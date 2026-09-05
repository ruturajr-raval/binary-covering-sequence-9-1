"""Standard-library graph helpers for retained theorem certificates."""

from __future__ import annotations

from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
from typing import Any


def hamming_ball(word: int, n: int, radius: int) -> tuple[int, ...]:
    if n <= 0 or radius < 0 or radius > n:
        raise ValueError("require n > 0 and 0 <= radius <= n")
    if word < 0 or word >= 1 << n:
        raise ValueError("word is outside the n-bit range")

    values = {word}
    for distance in range(1, radius + 1):
        for positions in combinations(range(n), distance):
            neighbor = word
            for position in positions:
                neighbor ^= 1 << position
            values.add(neighbor)
    return tuple(sorted(values))


def edge_prefix(word: int, n: int) -> int:
    if n <= 1:
        return 0
    return word >> 1


def edge_suffix(word: int, n: int) -> int:
    if n <= 1:
        return 0
    return word & ((1 << (n - 1)) - 1)


def sequence_window_counts(bits: list[int], n: int) -> list[int]:
    if n <= 0 or len(bits) < n:
        raise ValueError("require 0 < n <= sequence length")
    if any(bit not in (0, 1) for bit in bits):
        raise ValueError("sequence must contain only binary digits")

    counts = [0] * (1 << n)
    for start in range(len(bits)):
        word = 0
        for offset in range(n):
            word = (word << 1) | bits[(start + offset) % len(bits)]
        counts[word] += 1
    return counts


def de_bruijn_incidence(n: int) -> tuple[list[list[int]], list[list[int]]]:
    if n <= 0:
        raise ValueError("n must be positive")
    vertex_count = 1 << max(0, n - 1)
    outgoing = [[] for _ in range(vertex_count)]
    incoming = [[] for _ in range(vertex_count)]
    for word in range(1 << n):
        outgoing[edge_prefix(word, n)].append(word)
        incoming[edge_suffix(word, n)].append(word)
    return outgoing, incoming


def extract_euler_sequence(
    counts: list[int],
    *,
    n: int,
    root: int,
) -> list[int]:
    if len(counts) != 1 << n:
        raise ValueError("edge count vector has the wrong length")
    if any(value < 0 for value in counts):
        raise ValueError("edge counts must be nonnegative")

    remaining = counts.copy()
    outgoing, _ = de_bruijn_incidence(n)
    adjacency = [sorted(edges, reverse=True) for edges in outgoing]
    vertex_stack = [root]
    edge_stack: list[int] = []
    circuit: list[int] = []

    while vertex_stack:
        vertex = vertex_stack[-1]
        while adjacency[vertex] and remaining[adjacency[vertex][-1]] == 0:
            adjacency[vertex].pop()
        if adjacency[vertex]:
            word = adjacency[vertex][-1]
            remaining[word] -= 1
            vertex_stack.append(edge_suffix(word, n))
            edge_stack.append(word)
        else:
            vertex_stack.pop()
            if edge_stack:
                circuit.append(edge_stack.pop())

    circuit.reverse()
    if len(circuit) != sum(counts) or any(remaining):
        raise ValueError("selected edge multigraph is not one Eulerian component")

    vertex = root
    for word in circuit:
        if edge_prefix(word, n) != vertex:
            raise ValueError("extracted edge order is not a directed walk")
        vertex = edge_suffix(word, n)
    if vertex != root:
        raise ValueError("extracted directed walk is not closed")

    bits = [word & 1 for word in circuit]
    if sequence_window_counts(bits, n) != counts:
        raise ValueError("extracted sequence does not reproduce edge counts")
    return bits


def validate_support(support: list[int], *, n: int) -> list[int]:
    if n <= 0:
        raise ValueError("n must be positive")
    if not isinstance(support, list) or not all(
        isinstance(value, int) for value in support
    ):
        raise ValueError("support certificate must contain integer edges")
    if len(set(support)) != len(support):
        raise ValueError("support certificate contains duplicate edges")
    if any(value < 0 or value >= 1 << n for value in support):
        raise ValueError("support certificate contains an out-of-range edge")
    return sorted(support)


def load_support_certificate(path: Path, *, n: int) -> list[int]:
    payload = json.loads(path.read_text(encoding="ascii"))
    values = payload.get("selected_edges") if isinstance(payload, dict) else payload
    if not isinstance(values, list) or not all(
        isinstance(value, int) for value in values
    ):
        raise ValueError(
            "support certificate must be a list or contain selected_edges"
        )
    return validate_support(values, n=n)


def support_digest(support: list[int]) -> str:
    normalized = " ".join(str(word) for word in sorted(support)) + "\n"
    return sha256(normalized.encode("ascii")).hexdigest()


def analyze_support(
    support: list[int],
    *,
    n: int,
    radius: int,
) -> dict[str, Any]:
    support = validate_support(support, n=n)
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

    components: list[set[int]] = []
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
        components.append(component)

    component_edge_counts = sorted(
        sum(edge_prefix(word, n) in component for word in support)
        for component in components
    )
    return {
        "distinct_edges": len(support),
        "balanced": balanced,
        "covered_words": (1 << n) - len(uncovered),
        "uncovered_words": uncovered,
        "component_count": len(components),
        "component_edge_counts": component_edge_counts,
    }
