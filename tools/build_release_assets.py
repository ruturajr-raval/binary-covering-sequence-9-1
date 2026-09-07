"""Build and verify the deterministic paper-inclusive release assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile

from tools.build_arxiv_bundle import SOURCE_MAP, build_arxiv_bundle


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.3.1"
ASSET_STEM = "binary-covering-sequence-9-1"
PDF_NAME = f"{ASSET_STEM}-v{VERSION}-paper.pdf"
SOURCE_NAME = f"{ASSET_STEM}-v{VERSION}-paper-source.tar.gz"
CHECKSUMS_NAME = "SHA256SUMS"
DEFAULT_PDF = PROJECT_ROOT / "build/paper/main.pdf"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / f"dist/release/v{VERSION}"
RELEASE_METADATA = PROJECT_ROOT / "release.json"
EXPECTED_SOURCE_MEMBERS = {
    archive_name for _, archive_name in SOURCE_MAP
} | {"MANIFEST.sha256"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_regular_file(path: Path, description: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{description} is missing or not a regular file: {path}")


def _validate_pdf(path: Path) -> None:
    _require_regular_file(path, "compiled paper")
    payload = path.read_bytes()
    if not payload.startswith(b"%PDF-") or not payload.rstrip().endswith(b"%%EOF"):
        raise ValueError(f"compiled paper is not a complete PDF: {path}")


def _safe_archive_name(name: str) -> None:
    path = PurePosixPath(name)
    if (
        not path.parts
        or path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != name
    ):
        raise ValueError(f"unsafe source archive member: {name}")


def _validate_source_archive(path: Path) -> None:
    _require_regular_file(path, "paper source archive")
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            raise ValueError("paper source archive contains duplicate members")
        if set(names) != EXPECTED_SOURCE_MEMBERS:
            raise ValueError("paper source archive member set does not match the allowlist")
        for member in members:
            _safe_archive_name(member.name)
            if (
                not member.isfile()
                or member.mtime != 0
                or member.uid != 0
                or member.gid != 0
            ):
                raise ValueError(
                    f"paper source archive member is not deterministic: {member.name}"
                )


def _read_checksums(path: Path) -> dict[str, str]:
    _require_regular_file(path, "release checksum manifest")
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("release checksum manifest is not ASCII") from error

    entries: dict[str, str] = {}
    for line in lines:
        try:
            digest, name = line.split("  ", maxsplit=1)
        except ValueError as error:
            raise ValueError(f"malformed release checksum line: {line!r}") from error
        if (
            len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or name in entries
        ):
            raise ValueError(f"invalid release checksum line: {line!r}")
        entries[name] = digest
    return entries


def _verify_release_metadata(paths: dict[str, Path], metadata_path: Path) -> None:
    _require_regular_file(metadata_path, "release metadata")
    metadata = json.loads(metadata_path.read_text(encoding="ascii"))
    if metadata.get("version") != VERSION:
        raise ValueError("release metadata version mismatch")
    expected = {
        "pdf": (
            metadata.get("pdf_name"),
            metadata.get("pdf_size_bytes"),
            metadata.get("pdf_sha256"),
        ),
        "source": (
            metadata.get("source_archive_name"),
            metadata.get("source_archive_size_bytes"),
            metadata.get("source_archive_sha256"),
        ),
        "checksums": (
            metadata.get("checksums_name"),
            metadata.get("checksums_size_bytes"),
            metadata.get("checksums_sha256"),
        ),
    }
    for role, path in paths.items():
        name, size, digest = expected[role]
        if name != path.name:
            raise ValueError(f"release metadata name mismatch for {role}")
        if size != path.stat().st_size:
            raise ValueError(f"release metadata size mismatch for {role}")
        if digest != _sha256(path):
            raise ValueError(f"release metadata hash mismatch for {role}")


def verify_release_assets(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    metadata_path: Path | None = RELEASE_METADATA,
) -> dict[str, str]:
    """Verify the exact release asset set and return its recorded hashes."""

    if output_dir.is_symlink() or not output_dir.is_dir():
        raise ValueError(f"release asset directory is missing or invalid: {output_dir}")

    expected_files = {PDF_NAME, SOURCE_NAME, CHECKSUMS_NAME}
    actual_files = {
        path.name
        for path in output_dir.iterdir()
        if path.is_file() and not path.is_symlink()
    }
    all_entries = {path.name for path in output_dir.iterdir()}
    if actual_files != expected_files or all_entries != expected_files:
        raise ValueError("release asset directory does not contain the exact expected set")

    pdf = output_dir / PDF_NAME
    source = output_dir / SOURCE_NAME
    checksums = _read_checksums(output_dir / CHECKSUMS_NAME)
    expected_checksums = {
        PDF_NAME: _sha256(pdf),
        SOURCE_NAME: _sha256(source),
    }
    if checksums != expected_checksums:
        raise ValueError("release asset checksum mismatch")
    expected_manifest = "".join(
        f"{digest}  {name}\n"
        for name, digest in sorted(expected_checksums.items())
    )
    if (output_dir / CHECKSUMS_NAME).read_text(encoding="ascii") != expected_manifest:
        raise ValueError("release checksum manifest is not canonical")

    _validate_pdf(pdf)
    _validate_source_archive(source)
    if metadata_path is not None:
        _verify_release_metadata(
            {
                "pdf": pdf,
                "source": source,
                "checksums": output_dir / CHECKSUMS_NAME,
            },
            metadata_path,
        )
    return checksums


def build_release_assets(
    pdf: Path = DEFAULT_PDF,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    metadata_path: Path | None = RELEASE_METADATA,
) -> Path:
    """Create the exact release asset set transactionally."""

    _validate_pdf(pdf)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}-",
            dir=output_dir.parent,
        )
    )
    try:
        release_pdf = stage / PDF_NAME
        source_archive = stage / SOURCE_NAME
        shutil.copyfile(pdf, release_pdf)
        build_arxiv_bundle(source_archive)

        checksums = {
            PDF_NAME: _sha256(release_pdf),
            SOURCE_NAME: _sha256(source_archive),
        }
        manifest = "".join(
            f"{digest}  {name}\n" for name, digest in sorted(checksums.items())
        )
        (stage / CHECKSUMS_NAME).write_text(manifest, encoding="ascii")
        verify_release_assets(stage, metadata_path)

        if output_dir.exists():
            if output_dir.is_symlink() or not output_dir.is_dir():
                raise ValueError(
                    f"release output exists and is not a directory: {output_dir}"
                )
            shutil.rmtree(output_dir)
        os.replace(stage, output_dir)
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    if args.verify_only:
        checksums = verify_release_assets(args.output_dir)
    else:
        build_release_assets(args.pdf, args.output_dir)
        checksums = verify_release_assets(args.output_dir)

    for name, digest in sorted(checksums.items()):
        print(f"{digest}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
