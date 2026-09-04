from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class VerificationReport:
    valid: bool
    n: int
    radius: int
    length: int
    expected_length: int | None
    covered_words: int
    total_words: int
    uncovered_words: tuple[int, ...]
    distinct_windows: int
    coverage_histogram: dict[int, int]
    normalized_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def parse_sequence_text(text: str) -> list[int]:
    tokens = text.split()
    if len(tokens) == 1 and set(tokens[0]) <= {"0", "1"}:
        tokens = list(tokens[0])
    if not tokens:
        raise ValueError("sequence is empty")
    if any(token not in {"0", "1"} for token in tokens):
        raise ValueError("sequence must contain only binary digits")
    return [int(token) for token in tokens]


def load_sequence(path: str | Path) -> list[int]:
    return parse_sequence_text(Path(path).read_text(encoding="ascii"))


def cyclic_windows(bits: list[int], n: int) -> list[int]:
    if n <= 0:
        raise ValueError("n must be positive")
    if len(bits) < n:
        raise ValueError("sequence length must be at least n")

    windows: list[int] = []
    length = len(bits)
    for start in range(length):
        word = 0
        for offset in range(n):
            word = (word << 1) | bits[(start + offset) % length]
        windows.append(word)
    return windows


def hamming_ball(word: int, n: int, radius: int) -> Iterable[int]:
    if radius < 0:
        raise ValueError("radius must be nonnegative")
    if radius > 1:
        raise NotImplementedError("the trust-anchor verifier currently supports radius 0 or 1")

    yield word
    if radius == 1:
        for bit in range(n):
            yield word ^ (1 << bit)


def coverage_counts(bits: list[int], n: int, radius: int) -> tuple[list[int], list[int]]:
    windows = cyclic_windows(bits, n)
    counts = [0] * (1 << n)
    for window in windows:
        for word in hamming_ball(window, n, radius):
            counts[word] += 1
    return windows, counts


def normalized_digest(bits: list[int]) -> str:
    payload = (" ".join(str(bit) for bit in bits) + "\n").encode("ascii")
    return sha256(payload).hexdigest()


def verify_sequence(
    bits: list[int],
    *,
    n: int,
    radius: int,
    expected_length: int | None = None,
) -> VerificationReport:
    windows, counts = coverage_counts(bits, n, radius)
    uncovered = tuple(index for index, count in enumerate(counts) if count == 0)
    histogram = dict(sorted(Counter(counts).items()))
    length_matches = expected_length is None or len(bits) == expected_length

    return VerificationReport(
        valid=not uncovered and length_matches,
        n=n,
        radius=radius,
        length=len(bits),
        expected_length=expected_length,
        covered_words=(1 << n) - len(uncovered),
        total_words=1 << n,
        uncovered_words=uncovered,
        distinct_windows=len(set(windows)),
        coverage_histogram=histogram,
        normalized_sha256=normalized_digest(bits),
    )
