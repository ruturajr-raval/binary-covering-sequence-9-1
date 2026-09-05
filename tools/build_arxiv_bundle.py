"""Build the deterministic, allowlisted arXiv source archive."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
from pathlib import Path
import tarfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "dist/arxiv/binary-covering-sequence-9-1.tar.gz"
)

SOURCE_MAP = (
    ("paper/main.tex", "main.tex"),
    ("paper/ARXIV_README.txt", "README.txt"),
    ("paper/replay.py", "replay.py"),
    ("LICENSE", "LICENSE"),
    ("NOTICE", "NOTICE"),
    ("LICENSES/Apache-2.0.txt", "LICENSES/Apache-2.0.txt"),
    (
        "data/baseline/l9-r1-71.txt",
        "anc/replay/data/baseline/l9-r1-71.txt",
    ),
    (
        "data/candidates/l9-r1-common-backbone-64.json",
        "anc/replay/data/candidates/l9-r1-common-backbone-64.json",
    ),
    (
        "data/candidates/l9-r1-70-backbone-overlap-61.txt",
        "anc/replay/data/candidates/"
        "l9-r1-70-backbone-overlap-61.txt",
    ),
    (
        "evidence/common-backbone-lemma-20260905/README.md",
        "anc/replay/evidence/common-backbone-lemma-20260905/README.md",
    ),
    (
        "evidence/common-backbone-lemma-20260905/analysis.json",
        "anc/replay/evidence/common-backbone-lemma-20260905/analysis.json",
    ),
    (
        "evidence/common-backbone-lemma-20260905/files.sha256",
        "anc/replay/evidence/common-backbone-lemma-20260905/files.sha256",
    ),
    (
        "evidence/common-backbone-lemma-20260905/source/"
        "analyze_common_backbone_v2.py",
        "anc/replay/evidence/common-backbone-lemma-20260905/source/"
        "analyze_common_backbone_v2.py",
    ),
    (
        "evidence/common-backbone-lemma-20260905/source/"
        "certificate_graph.py",
        "anc/replay/evidence/common-backbone-lemma-20260905/source/"
        "certificate_graph.py",
    ),
    (
        "evidence/common-backbone-lemma-20260905/source/covering.py",
        "anc/replay/evidence/common-backbone-lemma-20260905/source/"
        "covering.py",
    ),
    (
        "evidence/common-backbone-lemma-20260905/source/"
        "verify_common_backbone_v1.py",
        "anc/replay/evidence/common-backbone-lemma-20260905/source/"
        "verify_common_backbone_v1.py",
    ),
    (
        "evidence/exact-backbone-overlap61-20260905/README.md",
        "anc/replay/evidence/exact-backbone-overlap61-20260905/README.md",
    ),
    (
        "evidence/exact-backbone-overlap61-20260905/analysis.json",
        "anc/replay/evidence/exact-backbone-overlap61-20260905/"
        "analysis.json",
    ),
    (
        "evidence/exact-backbone-overlap61-20260905/independent-check.json",
        "anc/replay/evidence/exact-backbone-overlap61-20260905/"
        "independent-check.json",
    ),
    (
        "evidence/exact-backbone-overlap61-20260905/files.sha256",
        "anc/replay/evidence/exact-backbone-overlap61-20260905/"
        "files.sha256",
    ),
    (
        "evidence/exact-backbone-overlap61-20260905/source/"
        "analyze_common_backbone.py",
        "anc/replay/evidence/exact-backbone-overlap61-20260905/source/"
        "analyze_common_backbone.py",
    ),
    (
        "evidence/exact-backbone-overlap61-20260905/source/"
        "analyze_exact_backbone_overlap_v2.py",
        "anc/replay/evidence/exact-backbone-overlap61-20260905/source/"
        "analyze_exact_backbone_overlap_v2.py",
    ),
    (
        "evidence/exact-backbone-overlap61-20260905/source/"
        "certificate_graph.py",
        "anc/replay/evidence/exact-backbone-overlap61-20260905/source/"
        "certificate_graph.py",
    ),
    (
        "evidence/exact-backbone-overlap61-20260905/source/covering.py",
        "anc/replay/evidence/exact-backbone-overlap61-20260905/source/"
        "covering.py",
    ),
    (
        "evidence/exact-backbone-overlap61-20260905/source/"
        "exact_overlap_checker_v1.cpp",
        "anc/replay/evidence/exact-backbone-overlap61-20260905/source/"
        "exact_overlap_checker_v1.cpp",
    ),
    (
        "evidence/exact-backbone-overlap61-20260905/source/"
        "verify_exact_backbone_overlap_v2.py",
        "anc/replay/evidence/exact-backbone-overlap61-20260905/source/"
        "verify_exact_backbone_overlap_v2.py",
    ),
)

DISALLOWED_PUBLICATION_BYTES = (
    b"/" + b"Users/",
    b"file" + b"://",
    bytes.fromhex("e28094"),
)


def _load_entries(root: Path) -> dict[str, bytes]:
    entries: dict[str, bytes] = {}
    for source_name, archive_name in SOURCE_MAP:
        source = root / source_name
        if source.is_symlink() or not source.is_file():
            raise ValueError(
                f"arXiv source is missing or not a regular file: {source_name}"
            )
        payload = source.read_bytes()
        for disallowed in DISALLOWED_PUBLICATION_BYTES:
            if disallowed in payload:
                raise ValueError(
                    "arXiv source contains non-public or unsupported text: "
                    f"{source_name}"
                )
        entries[archive_name] = payload
    return entries


def _manifest(entries: dict[str, bytes]) -> bytes:
    lines = [
        f"{hashlib.sha256(payload).hexdigest()}  {name}"
        for name, payload in sorted(entries.items())
    ]
    return ("\n".join(lines) + "\n").encode("ascii")


def _add_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mode = 0o644
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    archive.addfile(info, io.BytesIO(payload))


def build_arxiv_bundle(
    output: Path = DEFAULT_OUTPUT,
    root: Path = PROJECT_ROOT,
) -> Path:
    entries = _load_entries(root)
    entries["MANIFEST.sha256"] = _manifest(entries)
    output.parent.mkdir(parents=True, exist_ok=True)

    with (
        output.open("wb") as raw,
        gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed,
        tarfile.open(
            fileobj=compressed,
            mode="w",
            format=tarfile.USTAR_FORMAT,
        ) as archive,
    ):
        for name, payload in sorted(entries.items()):
            _add_bytes(archive, name, payload)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(build_arxiv_bundle(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
