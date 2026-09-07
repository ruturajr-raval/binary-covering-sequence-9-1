from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.build_release_assets import (
    CHECKSUMS_NAME,
    DEFAULT_OUTPUT_DIR,
    PDF_NAME,
    RELEASE_METADATA,
    SOURCE_NAME,
    VERSION,
    build_release_assets,
    verify_release_assets,
)


FAKE_PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


def snapshot(directory: Path) -> dict[str, bytes]:
    return {
        path.name: path.read_bytes()
        for path in sorted(directory.iterdir())
        if path.is_file()
    }


class ReleaseAssetTests(unittest.TestCase):
    def test_release_assets_are_exact_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "paper.pdf"
            output = root / "release"
            pdf.write_bytes(FAKE_PDF)

            build_release_assets(pdf, output, metadata_path=None)
            first = snapshot(output)
            build_release_assets(pdf, output, metadata_path=None)
            second = snapshot(output)

            self.assertEqual(first, second)
            self.assertEqual(
                set(first),
                {PDF_NAME, SOURCE_NAME, CHECKSUMS_NAME},
            )
            recorded = {
                line.split("  ", maxsplit=1)[1]: line.split(
                    "  ", maxsplit=1
                )[0]
                for line in first[CHECKSUMS_NAME]
                .decode("ascii")
                .splitlines()
            }
            self.assertEqual(
                verify_release_assets(output, metadata_path=None),
                recorded,
            )

    def test_release_asset_verification_rejects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "paper.pdf"
            output = root / "release"
            pdf.write_bytes(FAKE_PDF)
            build_release_assets(pdf, output, metadata_path=None)

            with (output / PDF_NAME).open("ab") as target:
                target.write(b"tampered")

            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                verify_release_assets(output, metadata_path=None)

    def test_release_asset_verification_rejects_unexpected_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "paper.pdf"
            output = root / "release"
            pdf.write_bytes(FAKE_PDF)
            build_release_assets(pdf, output, metadata_path=None)
            (output / "unexpected.txt").write_text(
                "unexpected\n",
                encoding="ascii",
            )

            with self.assertRaisesRegex(ValueError, "exact expected set"):
                verify_release_assets(output, metadata_path=None)

    def test_release_asset_verification_rejects_reordered_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "paper.pdf"
            output = root / "release"
            pdf.write_bytes(FAKE_PDF)
            build_release_assets(pdf, output, metadata_path=None)
            manifest = output / CHECKSUMS_NAME
            lines = manifest.read_text(encoding="ascii").splitlines()
            manifest.write_text(
                "\n".join(reversed(lines)) + "\n",
                encoding="ascii",
            )

            with self.assertRaisesRegex(ValueError, "not canonical"):
                verify_release_assets(output, metadata_path=None)

    def test_release_metadata_matches_archival_assets(self) -> None:
        root = Path(__file__).resolve().parents[1]
        metadata = json.loads(
            (root / "release.json").read_text(encoding="ascii")
        )

        self.assertEqual(metadata["version"], VERSION)
        self.assertEqual(metadata["release_tag"], "v0.3.1")
        self.assertEqual(
            metadata["release_version_doi"],
            "10.5281/zenodo.22647756",
        )
        self.assertEqual(
            metadata["release_concept_doi"],
            "10.5281/zenodo.22260691",
        )
        self.assertEqual(metadata["pdf_name"], PDF_NAME)
        self.assertEqual(metadata["pdf_size_bytes"], 67128)
        self.assertEqual(metadata["source_archive_name"], SOURCE_NAME)
        self.assertEqual(metadata["source_archive_size_bytes"], 92036)
        self.assertEqual(metadata["checksums_name"], CHECKSUMS_NAME)
        self.assertEqual(metadata["checksums_size_bytes"], 234)
        self.assertEqual(
            metadata["pdf_sha256"],
            "7757034a04177ab4b42f8ad0f651fecc"
            "1b11b50dad27570d06f8bf9d9e6b5872",
        )
        self.assertEqual(
            metadata["source_archive_sha256"],
            "e578decc5cea739c9783f8238a12a73f"
            "f5bd462b15474340589b62d61330aab0",
        )
        self.assertEqual(
            metadata["checksums_sha256"],
            "5972bb79e1a86fd756358c45a12910a6"
            "07533227001035176496ac0aa1659ccb",
        )
        self.assertEqual(
            verify_release_assets(DEFAULT_OUTPUT_DIR),
            {
                PDF_NAME: metadata["pdf_sha256"],
                SOURCE_NAME: metadata["source_archive_sha256"],
            },
        )

    def test_release_asset_verification_rejects_metadata_hash_mismatch(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            metadata_path = Path(directory) / "release.json"
            metadata = json.loads(
                RELEASE_METADATA.read_text(encoding="ascii")
            )
            metadata["pdf_sha256"] = "0" * 64
            metadata_path.write_text(
                json.dumps(metadata, indent=2) + "\n",
                encoding="ascii",
            )
            with self.assertRaisesRegex(
                ValueError,
                "metadata hash mismatch",
            ):
                verify_release_assets(DEFAULT_OUTPUT_DIR, metadata_path)


if __name__ == "__main__":
    unittest.main()
