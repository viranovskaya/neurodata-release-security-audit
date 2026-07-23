"""Tests for the labelled benchmark."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from neurodata_security_audit.benchmark import (
    render_benchmark_markdown,
    run_benchmark,
)

_FULL_BENCHMARK_READERS_AVAILABLE = all(
    importlib.util.find_spec(name) is not None
    for name in ("mne", "nibabel", "pydicom")
)


class BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases_path = Path(__file__).parents[1] / "benchmark" / "cases.json"

    @unittest.skipUnless(
        _FULL_BENCHMARK_READERS_AVAILABLE,
        "Full benchmark needs the formats and imaging extras",
    )
    def test_development_pilot_is_fully_labelled(self) -> None:
        result = run_benchmark(self.cases_path)
        summary = result["summary"]

        self.assertEqual(result["suite_name"], "development")
        self.assertFalse(result["locked"])
        self.assertEqual(len(result["case_files"]), 5)
        self.assertEqual(summary["cases"], 36)
        self.assertEqual(summary["matched_findings"], 50)
        self.assertEqual(summary["expected_findings"], 50)
        self.assertEqual(summary["unexpected_findings"], 0)
        self.assertEqual(summary["duplicate_findings"], 1)
        self.assertEqual(summary["clean_controls"], 9)
        self.assertEqual(summary["control_cases"], 9)
        self.assertEqual(summary["matched_references"], 7)
        self.assertEqual(summary["expected_references"], 7)
        self.assertEqual(summary["unexpected_references"], 0)
        self.assertEqual(summary["matched_container_members"], 4)
        self.assertEqual(summary["expected_container_members"], 4)
        self.assertEqual(summary["unexpected_container_members"], 0)
        self.assertEqual(summary["matched_coverage"], 16)
        self.assertEqual(summary["expected_coverage"], 16)
        self.assertEqual(summary["masking_failures"], 0)
        self.assertEqual(summary["integrity_failures"], 0)
        self.assertEqual(
            summary["expected_findings"],
            sum(
                group["expected_findings"]
                for group in result["by_finding_class"].values()
            ),
        )

    @unittest.skipUnless(
        _FULL_BENCHMARK_READERS_AVAILABLE,
        "Full benchmark needs the formats and imaging extras",
    )
    def test_result_is_deterministic(self) -> None:
        first = run_benchmark(self.cases_path)
        second = run_benchmark(self.cases_path)

        self.assertEqual(
            json.dumps(first, sort_keys=True),
            json.dumps(second, sort_keys=True),
        )
        self.assertEqual(
            render_benchmark_markdown(first),
            render_benchmark_markdown(second),
        )

    def test_case_files_cannot_escape_the_temporary_release(self) -> None:
        specification = {
            "schema_version": "1",
            "cases": [
                {
                    "case_id": "bad_path",
                    "split": "development",
                    "format": "text",
                    "files": {"../outside.txt": "not written"},
                    "sensitive_terms": [],
                    "seeded_values": [],
                    "expected_findings": [],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            cases_path = Path(directory) / "cases.json"
            cases_path.write_text(json.dumps(specification), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must stay inside"):
                run_benchmark(cases_path)

    def test_builder_output_cannot_escape_the_temporary_release(self) -> None:
        specification = {
            "schema_version": "1",
            "cases": [
                {
                    "case_id": "bad_builder_path",
                    "split": "development",
                    "format": "zip",
                    "files": {},
                    "builder": {
                        "name": "zip",
                        "path": "../outside.zip",
                        "members": [],
                    },
                    "sensitive_terms": [],
                    "seeded_values": [],
                    "expected_findings": [],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            cases_path = Path(directory) / "cases.json"
            cases_path.write_text(json.dumps(specification), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must stay inside"):
                run_benchmark(cases_path)

    def test_duplicate_case_ids_are_rejected(self) -> None:
        case = {
            "case_id": "repeated",
            "split": "development",
            "format": "text",
            "files": {"notes.txt": "synthetic\n"},
            "sensitive_terms": [],
            "seeded_values": [],
            "expected_findings": [],
        }
        specification = {
            "schema_version": "1",
            "cases": [case, case],
        }
        with tempfile.TemporaryDirectory() as directory:
            cases_path = Path(directory) / "cases.json"
            cases_path.write_text(json.dumps(specification), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate benchmark case ID"):
                run_benchmark(cases_path)

    def test_case_file_schema_must_match_suite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases_path = root / "cases.json"
            included_path = root / "included.json"
            cases_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "case_files": ["included.json"],
                    }
                ),
                encoding="utf-8",
            )
            included_path.write_text(
                json.dumps({"schema_version": "2", "cases": []}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "suite schema version"):
                run_benchmark(cases_path)

    def test_locked_case_file_hash_is_checked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases_path = root / "cases.json"
            included_path = root / "included.json"
            cases_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "case_files": [
                            {
                                "path": "included.json",
                                "sha256": "0" * 64,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            included_path.write_text(
                json.dumps({"schema_version": "1", "cases": []}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "hash does not match"):
                run_benchmark(cases_path)


if __name__ == "__main__":
    unittest.main()
