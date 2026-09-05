from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from tools.verify_common_backbone import (
    EXPECTED_SUMMARY as COMMON_SUMMARY,
    verify_artifact as verify_common_artifact,
)
from tools.verify_exact_backbone_overlap import verify_artifacts


ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "evidence/common-backbone-lemma-20260905"
EXACT = ROOT / "evidence/exact-backbone-overlap61-20260905"
BACKBONE = ROOT / "data/candidates/l9-r1-common-backbone-64.json"
WITNESS = ROOT / "data/candidates/l9-r1-70-backbone-overlap-61.txt"


class PublicationEvidenceTests(unittest.TestCase):
    def assert_manifest(self, root: Path) -> None:
        manifest = root / "files.sha256"
        listed: dict[str, str] = {}
        for line in manifest.read_text(encoding="ascii").splitlines():
            digest, relative_path = line.split("  ", maxsplit=1)
            listed[relative_path] = digest

        files = {
            str(path.relative_to(root))
            for path in root.rglob("*")
            if path.is_file() and path != manifest
        }
        self.assertEqual(set(listed), files)
        for relative_path, expected in listed.items():
            actual = hashlib.sha256(
                (root / relative_path).read_bytes()
            ).hexdigest()
            self.assertEqual(actual, expected, relative_path)

    def test_publication_manifests_authenticate_every_file(self) -> None:
        self.assert_manifest(COMMON)
        self.assert_manifest(EXACT)

    def test_publication_common_certificate_passes(self) -> None:
        self.assertEqual(
            verify_common_artifact(
                COMMON / "analysis.json",
                BACKBONE,
                WITNESS,
            ),
            COMMON_SUMMARY,
        )

    def test_publication_exact_certificate_passes(self) -> None:
        analysis = json.loads(
            (EXACT / "analysis.json").read_text(encoding="ascii")
        )
        independent = json.loads(
            (EXACT / "independent-check.json").read_text(
                encoding="ascii"
            )
        )
        self.assertEqual(
            verify_artifacts(
                analysis,
                independent,
                support_path=BACKBONE,
                analyzer_path=(
                    EXACT
                    / "source/analyze_exact_backbone_overlap_v2.py"
                ),
                witness_path=WITNESS,
            ),
            {
                "omission_sets_checked": 41_664,
                "distinct_residual_flows": 188,
                "connected_completion_count": 8,
                "covering_completion_count": 0,
            },
        )

    def test_publication_python_sources_do_not_require_ortools(self) -> None:
        sources = [
            *COMMON.glob("source/*.py"),
            *EXACT.glob("source/*.py"),
        ]
        self.assertTrue(sources)
        for source in sources:
            self.assertNotIn(
                "ortools",
                source.read_text(encoding="ascii").lower(),
                source,
            )


if __name__ == "__main__":
    unittest.main()
