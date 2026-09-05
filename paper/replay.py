#!/usr/bin/env python3
"""Replay every certificate shipped with the arXiv source archive."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
REPLAY_ROOT = ROOT / "anc/replay"
COMMON = REPLAY_ROOT / "evidence/common-backbone-lemma-20260905"
EXACT = REPLAY_ROOT / "evidence/exact-backbone-overlap61-20260905"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(root: Path, manifest: Path) -> None:
    expected_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != manifest
    }
    entries: dict[str, str] = {}
    for line in manifest.read_text(encoding="ascii").splitlines():
        try:
            digest, name = line.split("  ", maxsplit=1)
        except ValueError as error:
            raise RuntimeError(f"malformed manifest line: {line!r}") from error
        path = PurePosixPath(name)
        if (
            not path.parts
            or path.is_absolute()
            or ".." in path.parts
            or path.as_posix() != name
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or name in entries
        ):
            raise RuntimeError(f"invalid manifest entry: {line!r}")
        entries[name] = digest
    if set(entries) != expected_files:
        raise RuntimeError(f"manifest file set mismatch: {manifest}")
    for name, expected_digest in entries.items():
        target = root.joinpath(*PurePosixPath(name).parts)
        if target.is_symlink() or not target.is_file():
            raise RuntimeError(f"manifest target is missing or invalid: {name}")
        if sha256(target) != expected_digest:
            raise RuntimeError(f"manifest digest mismatch: {name}")


def run(
    command: list[str],
    *,
    stdout: int | None = None,
) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        command,
        cwd=REPLAY_ROOT,
        env=environment,
        check=True,
        stdout=stdout,
        stderr=None,
    )


def require_equal(actual: Path, expected: Path) -> None:
    if actual.read_bytes() != expected.read_bytes():
        raise RuntimeError(
            f"replayed artifact differs from retained file: {expected}"
        )


def main() -> int:
    verify_manifest(ROOT, ROOT / "MANIFEST.sha256")
    verify_manifest(COMMON, COMMON / "files.sha256")
    verify_manifest(EXACT, EXACT / "files.sha256")

    python = sys.executable
    compiler = os.environ.get("CXX", "c++")
    with tempfile.TemporaryDirectory(prefix="covering-sequence-replay-") as tmp:
        work = Path(tmp)
        common_output = work / "common-analysis.json"
        exact_output = work / "exact-analysis.json"
        cpp_output = work / "exact-independent.json"
        checker = work / "exact-overlap-checker"

        run(
            [
                python,
                "-B",
                "evidence/common-backbone-lemma-20260905/source/"
                "analyze_common_backbone_v2.py",
                "data/candidates/l9-r1-common-backbone-64.json",
                str(common_output),
                "--baseline",
                "data/baseline/l9-r1-71.txt",
                "--overlap-witness",
                "data/candidates/l9-r1-70-backbone-overlap-61.txt",
                "--n",
                "9",
                "--radius",
                "1",
                "--candidate-length",
                "70",
            ],
            stdout=subprocess.DEVNULL,
        )
        require_equal(common_output, COMMON / "analysis.json")
        run(
            [
                python,
                "-B",
                "evidence/common-backbone-lemma-20260905/source/"
                "verify_common_backbone_v1.py",
                str(common_output),
                "--support",
                "data/candidates/l9-r1-common-backbone-64.json",
                "--witness",
                "data/candidates/l9-r1-70-backbone-overlap-61.txt",
            ],
            stdout=subprocess.DEVNULL,
        )

        run(
            [
                python,
                "-B",
                "evidence/exact-backbone-overlap61-20260905/source/"
                "analyze_exact_backbone_overlap_v2.py",
                "data/candidates/l9-r1-common-backbone-64.json",
                str(exact_output),
                "--overlap-witness",
                "data/candidates/l9-r1-70-backbone-overlap-61.txt",
                "--n",
                "9",
                "--radius",
                "1",
                "--candidate-length",
                "70",
                "--exact-overlap",
                "61",
            ],
            stdout=subprocess.DEVNULL,
        )
        require_equal(exact_output, EXACT / "analysis.json")

        run(
            [
                compiler,
                "-std=c++20",
                "-O3",
                "-Wall",
                "-Wextra",
                "-Wpedantic",
                "evidence/exact-backbone-overlap61-20260905/source/"
                "exact_overlap_checker_v1.cpp",
                "-o",
                str(checker),
            ]
        )
        completed = run(
            [
                str(checker),
                "data/candidates/l9-r1-common-backbone-64.json",
            ],
            stdout=subprocess.PIPE,
        )
        cpp_output.write_bytes(completed.stdout)
        require_equal(cpp_output, EXACT / "independent-check.json")

        run(
            [
                python,
                "-B",
                "evidence/exact-backbone-overlap61-20260905/source/"
                "verify_exact_backbone_overlap_v2.py",
                str(exact_output),
                str(cpp_output),
                "--support",
                "data/candidates/l9-r1-common-backbone-64.json",
                "--analyzer",
                "evidence/exact-backbone-overlap61-20260905/source/"
                "analyze_exact_backbone_overlap_v2.py",
                "--witness",
                "data/candidates/l9-r1-70-backbone-overlap-61.txt",
            ],
            stdout=subprocess.DEVNULL,
        )

    print(
        json.dumps(
            {
                "common_residual_flows": 168,
                "exact_residual_flows": 188,
                "connected_boundary_completions": 8,
                "covering_boundary_completions": 0,
                "status": "pass",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
