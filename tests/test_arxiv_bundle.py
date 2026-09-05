from __future__ import annotations

import gzip
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

from tools.build_arxiv_bundle import SOURCE_MAP, build_arxiv_bundle
from tools.replay_arxiv_bundle import replay_bundle


def read_archive(path: Path) -> list[tuple[str, bytes]]:
    with tarfile.open(path, "r:gz") as archive:
        entries: list[tuple[str, bytes]] = []
        for member in archive.getmembers():
            source = archive.extractfile(member)
            if source is None:
                raise AssertionError(f"cannot read test archive member: {member.name}")
            entries.append((member.name, source.read()))
        return entries


def write_archive(path: Path, entries: list[tuple[str, bytes]]) -> None:
    with (
        path.open("wb") as raw,
        gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed,
        tarfile.open(
            fileobj=compressed,
            mode="w",
            format=tarfile.USTAR_FORMAT,
        ) as archive,
    ):
        for name, payload in entries:
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o644
            info.mtime = 0
            archive.addfile(info, io.BytesIO(payload))


def root_manifest(entries: list[tuple[str, bytes]]) -> bytes:
    lines = [
        f"{hashlib.sha256(payload).hexdigest()}  {name}"
        for name, payload in sorted(entries)
        if name != "MANIFEST.sha256"
    ]
    return ("\n".join(lines) + "\n").encode("ascii")


class ArxivBundleTests(unittest.TestCase):
    def test_bundle_is_deterministic_and_allowlisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.tar.gz"
            second = Path(directory) / "second.tar.gz"
            build_arxiv_bundle(first)
            build_arxiv_bundle(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())

            with tarfile.open(first, "r:gz") as archive:
                names = archive.getnames()
                expected = sorted(
                    [archive_name for _, archive_name in SOURCE_MAP]
                    + ["MANIFEST.sha256"]
                )
                self.assertEqual(names, expected)
                self.assertTrue(all(member.isfile() for member in archive))
                self.assertNotIn("research/release-gate.json", names)
                self.assertNotIn("release.json", names)
                self.assertNotIn("evidence.json", names)

    def test_archive_manifest_authenticates_every_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle.tar.gz"
            build_arxiv_bundle(output)
            with tarfile.open(output, "r:gz") as archive:
                manifest = archive.extractfile("MANIFEST.sha256")
                self.assertIsNotNone(manifest)
                expected: dict[str, str] = {}
                for line in manifest.read().decode("ascii").splitlines():
                    digest, name = line.split("  ", maxsplit=1)
                    expected[name] = digest
                self.assertEqual(
                    set(expected),
                    set(archive.getnames()) - {"MANIFEST.sha256"},
                )
                for name, digest in expected.items():
                    source = archive.extractfile(name)
                    self.assertIsNotNone(source)
                    self.assertEqual(
                        hashlib.sha256(source.read()).hexdigest(),
                        digest,
                        name,
                    )

    def test_bundle_replays_from_clean_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle.tar.gz"
            build_arxiv_bundle(output)
            replay_bundle(output)

    def test_replay_rejects_root_manifest_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "original.tar.gz"
            corrupted = Path(directory) / "corrupted.tar.gz"
            build_arxiv_bundle(original)
            entries = read_archive(original)
            entries = [
                (name, payload + b"\ncorrupted\n")
                if name == "README.txt"
                else (name, payload)
                for name, payload in entries
            ]
            write_archive(corrupted, entries)
            with self.assertRaisesRegex(ValueError, "manifest digest mismatch"):
                replay_bundle(corrupted)

    def test_replay_rejects_nested_manifest_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "original.tar.gz"
            corrupted = Path(directory) / "corrupted.tar.gz"
            build_arxiv_bundle(original)
            entries = read_archive(original)
            target = (
                "anc/replay/evidence/common-backbone-lemma-20260905/"
                "analysis.json"
            )
            entries = [
                (name, payload + b"\n")
                if name == target
                else (name, payload)
                for name, payload in entries
            ]
            updated_manifest = root_manifest(entries)
            entries = [
                (name, updated_manifest)
                if name == "MANIFEST.sha256"
                else (name, payload)
                for name, payload in entries
            ]
            write_archive(corrupted, entries)
            with self.assertRaisesRegex(ValueError, "manifest digest mismatch"):
                replay_bundle(corrupted)

    def test_replay_rejects_duplicate_members(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "original.tar.gz"
            duplicated = Path(directory) / "duplicated.tar.gz"
            build_arxiv_bundle(original)
            entries = read_archive(original)
            readme = next(
                payload for name, payload in entries if name == "README.txt"
            )
            write_archive(duplicated, entries + [("README.txt", readme)])
            with self.assertRaisesRegex(ValueError, "unsafe arXiv archive member"):
                replay_bundle(duplicated)

    def test_replay_enforces_resource_limits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle.tar.gz"
            build_arxiv_bundle(output)
            with self.assertRaisesRegex(ValueError, "too many members"):
                replay_bundle(output, max_members=1)
            with self.assertRaisesRegex(ValueError, "member exceeds size limit"):
                replay_bundle(output, max_member_bytes=1)
            with self.assertRaisesRegex(ValueError, "total size limit"):
                replay_bundle(output, max_total_bytes=1)


if __name__ == "__main__":
    unittest.main()
