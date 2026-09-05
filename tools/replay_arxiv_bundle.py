"""Validate, extract, and replay the deterministic arXiv source archive."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = (
    PROJECT_ROOT / "dist/arxiv/binary-covering-sequence-9-1.tar.gz"
)
MAX_ARCHIVE_MEMBERS = 128
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
EVIDENCE_MANIFESTS = (
    PurePosixPath(
        "anc/replay/evidence/common-backbone-lemma-20260905/files.sha256"
    ),
    PurePosixPath(
        "anc/replay/evidence/exact-backbone-overlap61-20260905/files.sha256"
    ),
)


def _safe_relative_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (
        not path.parts
        or path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != name
    ):
        raise ValueError(f"unsafe archive path: {name}")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_entries(manifest: Path) -> dict[str, str]:
    try:
        lines = manifest.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError(f"cannot read manifest: {manifest}") from error

    entries: dict[str, str] = {}
    for line in lines:
        try:
            digest, name = line.split("  ", maxsplit=1)
        except ValueError as error:
            raise ValueError(f"malformed manifest line: {line!r}") from error
        _safe_relative_path(name)
        if (
            len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or name in entries
        ):
            raise ValueError(f"invalid manifest entry: {line!r}")
        entries[name] = digest
    return entries


def _verify_manifest(
    root: Path,
    manifest: Path,
    expected_names: set[str],
) -> None:
    entries = _manifest_entries(manifest)
    if set(entries) != expected_names:
        raise ValueError(f"manifest file set mismatch: {manifest}")
    for name, expected_digest in entries.items():
        target = root.joinpath(*PurePosixPath(name).parts)
        if target.is_symlink() or not target.is_file():
            raise ValueError(f"manifest target is missing or invalid: {name}")
        if _sha256(target) != expected_digest:
            raise ValueError(f"manifest digest mismatch: {name}")


def _directory_files(root: Path, excluded: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != excluded
    }


def replay_bundle(
    bundle: Path = DEFAULT_BUNDLE,
    *,
    max_members: int = MAX_ARCHIVE_MEMBERS,
    max_member_bytes: int = MAX_MEMBER_BYTES,
    max_total_bytes: int = MAX_TOTAL_BYTES,
) -> None:
    with tempfile.TemporaryDirectory(
        prefix="binary-covering-sequence-arxiv-"
    ) as directory:
        root = Path(directory)
        with tarfile.open(bundle, "r:gz") as archive:
            members = archive.getmembers()
            if len(members) > max_members:
                raise ValueError("arXiv archive has too many members")

            names: set[str] = set()
            total_bytes = 0
            for member in members:
                path = _safe_relative_path(member.name)
                canonical_name = path.as_posix()
                if not member.isfile() or canonical_name in names:
                    raise ValueError(
                        f"unsafe arXiv archive member: {member.name}"
                    )
                if member.size < 0 or member.size > max_member_bytes:
                    raise ValueError(
                        f"arXiv archive member exceeds size limit: {member.name}"
                    )
                total_bytes += member.size
                if total_bytes > max_total_bytes:
                    raise ValueError("arXiv archive exceeds total size limit")
                names.add(canonical_name)

                source = archive.extractfile(member)
                if source is None:
                    raise ValueError(
                        f"cannot read arXiv archive member: {member.name}"
                    )
                destination = root.joinpath(*path.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                with destination.open("wb") as target:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        written += len(chunk)
                        if written > member.size:
                            raise ValueError(
                                "arXiv archive member exceeds declared size: "
                                f"{member.name}"
                            )
                        target.write(chunk)
                if written != member.size:
                    raise ValueError(
                        f"truncated arXiv archive member: {member.name}"
                    )

        root_manifest = root / "MANIFEST.sha256"
        _verify_manifest(
            root,
            root_manifest,
            names - {"MANIFEST.sha256"},
        )
        for relative_manifest in EVIDENCE_MANIFESTS:
            manifest = root.joinpath(*relative_manifest.parts)
            evidence_root = manifest.parent
            _verify_manifest(
                evidence_root,
                manifest,
                _directory_files(evidence_root, manifest),
            )

        subprocess.run(
            [sys.executable, "replay.py"],
            cwd=root,
            check=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "bundle",
        type=Path,
        nargs="?",
        default=DEFAULT_BUNDLE,
        help="trusted archive from the project release or a local build",
    )
    args = parser.parse_args()
    replay_bundle(args.bundle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
