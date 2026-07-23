"""Tests for hash-pinned public format checks."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from neurodata_security_audit.external_benchmark import (
    render_external_format_markdown,
    run_external_format_checks,
)


def _edf_header() -> bytes:
    def field(value: str, width: int) -> bytes:
        return value.encode("ascii").ljust(width, b" ")

    return b"".join(
        (
            field("0", 8),
            field("X X X X", 80),
            field("Startdate X X X X", 80),
            field("01.01.85", 8),
            field("00.00.00", 8),
            field("256", 8),
            field("", 44),
            field("0", 8),
            field("1", 8),
            field("0", 4),
        )
    )


class ExternalBenchmarkTests(unittest.TestCase):
    def test_hash_pinned_edf_fixture_passes_and_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture.edf"
            fixture.write_bytes(_edf_header())

            fixture_hash = hashlib.sha256(fixture.read_bytes()).hexdigest()
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "suite_name": "test",
                        "fixtures": [
                            {
                                "fixture_id": "edf",
                                "dataset_id": "synthetic",
                                "format": "EDF",
                                "doi": "test-doi",
                                "source_url": "https://example.test/fixture",
                                "source_commit": "test-commit",
                                "source_path": "fixture.edf",
                                "sha256": fixture_hash,
                                "expected_coverage": "header_or_structure_only",
                                "forbidden_codes": ["FORMAT_METADATA_UNREADABLE"],
                            }
                        ],
                        "unscored_formats": [],
                    }
                ),
                encoding="utf-8",
            )
            first = run_external_format_checks(manifest, root)
            second = run_external_format_checks(manifest, root)

        self.assertEqual(first, second)
        self.assertEqual(first["summary"]["passed"], 1)
        self.assertEqual(first["summary"]["failed"], 0)
        self.assertEqual(
            render_external_format_markdown(first),
            render_external_format_markdown(second),
        )

    def test_hash_mismatch_fails_without_scanning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "fixture.edf").write_bytes(_edf_header())
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "suite_name": "test",
                        "fixtures": [
                            {
                                "fixture_id": "edf",
                                "dataset_id": "synthetic",
                                "format": "EDF",
                                "doi": "test-doi",
                                "source_url": "https://example.test/fixture",
                                "source_commit": "test-commit",
                                "source_path": "fixture.edf",
                                "sha256": "0" * 64,
                                "expected_coverage": "header_or_structure_only",
                                "forbidden_codes": [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = run_external_format_checks(manifest, root)

        fixture_result = result["fixtures"][0]
        self.assertFalse(fixture_result["passed"])
        self.assertEqual(fixture_result["failure"], "source_hash_mismatch")

    def test_fixture_path_cannot_escape_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "suite_name": "test",
                        "fixtures": [
                            {
                                "fixture_id": "bad",
                                "dataset_id": "synthetic",
                                "format": "EDF",
                                "doi": "test-doi",
                                "source_url": "https://example.test/fixture",
                                "source_commit": "test-commit",
                                "source_path": "../outside.edf",
                                "sha256": "0" * 64,
                                "expected_coverage": "header_or_structure_only",
                                "forbidden_codes": [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "must stay inside"):
                run_external_format_checks(manifest, root)

    def test_fixture_path_cannot_use_symlinked_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside"
            outside.mkdir()
            fixture = outside / "fixture.edf"
            fixture.write_bytes(_edf_header())
            (root / "linked").symlink_to(outside, target_is_directory=True)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "suite_name": "test",
                        "fixtures": [
                            {
                                "fixture_id": "edf",
                                "dataset_id": "synthetic",
                                "format": "EDF",
                                "doi": "test-doi",
                                "source_url": "https://example.test/fixture",
                                "source_commit": "test-commit",
                                "source_path": "linked/fixture.edf",
                                "sha256": hashlib.sha256(
                                    fixture.read_bytes()
                                ).hexdigest(),
                                "expected_coverage": "header_or_structure_only",
                                "forbidden_codes": [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = run_external_format_checks(manifest, root)

        fixture_result = result["fixtures"][0]
        self.assertFalse(fixture_result["passed"])
        self.assertEqual(
            fixture_result["failure"],
            "source_path_contains_symlink",
        )


if __name__ == "__main__":
    unittest.main()
