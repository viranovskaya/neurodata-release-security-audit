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
        cls.locked_v1_path = (
            Path(__file__).parents[1] / "benchmark" / "locked.json"
        )
        cls.locked_v2_path = (
            Path(__file__).parents[1] / "benchmark" / "locked_v2.json"
        )
        cls.privacy_adversarial_path = (
            Path(__file__).parents[1]
            / "benchmark"
            / "cases"
            / "development_privacy_adversarial.json"
        )

    @unittest.skipUnless(
        _FULL_BENCHMARK_READERS_AVAILABLE,
        "Full benchmark needs the formats and imaging extras",
    )
    def test_development_pilot_is_fully_labelled(self) -> None:
        result = run_benchmark(self.cases_path)
        summary = result["summary"]

        self.assertEqual(result["suite_name"], "development")
        self.assertFalse(result["locked"])
        self.assertEqual(len(result["case_files"]), 7)
        self.assertEqual(summary["cases"], 50)
        self.assertEqual(summary["matched_findings"], 103)
        self.assertEqual(summary["expected_findings"], 103)
        self.assertEqual(summary["unexpected_findings"], 0)
        self.assertEqual(summary["duplicate_findings"], 1)
        self.assertEqual(summary["clean_controls"], 12)
        self.assertEqual(summary["control_cases"], 12)
        self.assertEqual(summary["matched_references"], 10)
        self.assertEqual(summary["expected_references"], 10)
        self.assertEqual(summary["unexpected_references"], 0)
        self.assertEqual(summary["matched_container_members"], 4)
        self.assertEqual(summary["expected_container_members"], 4)
        self.assertEqual(summary["unexpected_container_members"], 0)
        self.assertEqual(summary["matched_coverage"], 22)
        self.assertEqual(summary["expected_coverage"], 22)
        self.assertEqual(summary["masking_failures"], 0)
        self.assertEqual(summary["integrity_failures"], 0)
        self.assertEqual(
            summary["expected_findings"],
            sum(
                group["expected_findings"]
                for group in result["by_finding_class"].values()
            ),
        )

    def test_privacy_adversarial_layer_is_fully_labelled(self) -> None:
        result = run_benchmark(self.privacy_adversarial_path)
        summary = result["summary"]

        self.assertEqual(summary["cases"], 10)
        self.assertEqual(summary["matched_findings"], 32)
        self.assertEqual(summary["expected_findings"], 32)
        self.assertEqual(summary["unexpected_findings"], 0)
        self.assertEqual(summary["duplicate_findings"], 0)
        self.assertEqual(summary["clean_controls"], 2)
        self.assertEqual(summary["control_cases"], 2)
        self.assertEqual(summary["masking_failures"], 0)
        self.assertEqual(summary["integrity_failures"], 0)
        self.assertNotIn("coverage_or_other", result["by_finding_class"])
        self.assertEqual(
            {
                "dates_and_demographics": 1,
                "free_text_and_sources": 1,
                "linked_identity": 3,
                "operational_metadata": 4,
                "personal_identity": 11,
                "release_structure": 1,
                "secrets_and_paths": 9,
                "site_device_and_staff": 2,
            },
            {
                name: metrics["expected_findings"]
                for name, metrics in result["by_finding_class"].items()
            },
        )

    def test_markdown_identifies_locked_manifest_and_case_hashes(self) -> None:
        result = run_benchmark(self.privacy_adversarial_path)
        unlocked_markdown = render_benchmark_markdown(result)
        locked_result = {
            **result,
            "suite_name": "locked-test",
            "locked": True,
            "case_files": [
                {"path": "cases/example.json", "sha256": "a" * 64}
            ],
        }
        locked_markdown = render_benchmark_markdown(locked_result)

        self.assertIn("- Suite: locked-test", locked_markdown)
        self.assertIn("- Locked manifest: yes", locked_markdown)
        self.assertIn("cases/example.json=" + "a" * 64, locked_markdown)
        self.assertIn("- Locked manifest: no", unlocked_markdown)
        self.assertNotEqual(unlocked_markdown, locked_markdown)

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

    def test_legacy_weak_locked_suite_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "must contain exactly"):
            run_benchmark(self.locked_v1_path)

    @unittest.skipUnless(
        _FULL_BENCHMARK_READERS_AVAILABLE,
        "Full benchmark needs the formats and imaging extras",
    )
    def test_strict_locked_v2_is_fully_labelled(self) -> None:
        result = run_benchmark(self.locked_v2_path)
        summary = result["summary"]

        self.assertEqual(result["suite_name"], "locked-v2")
        self.assertTrue(result["locked"])
        self.assertEqual(summary["cases"], 10)
        self.assertEqual(summary["matched_findings"], 21)
        self.assertEqual(summary["expected_findings"], 21)
        self.assertEqual(summary["unexpected_findings"], 0)
        self.assertEqual(summary["duplicate_findings"], 0)
        self.assertEqual(summary["clean_controls"], 2)
        self.assertEqual(summary["control_cases"], 2)
        self.assertEqual(summary["matched_references"], 2)
        self.assertEqual(summary["expected_references"], 2)
        self.assertEqual(summary["matched_container_members"], 1)
        self.assertEqual(summary["expected_container_members"], 1)
        self.assertEqual(summary["matched_coverage"], 8)
        self.assertEqual(summary["expected_coverage"], 8)
        self.assertEqual(summary["masking_failures"], 0)
        self.assertEqual(summary["integrity_failures"], 0)

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

    def test_multiple_builder_output_cannot_escape_release(self) -> None:
        specification = {
            "schema_version": "1",
            "cases": [
                {
                    "case_id": "bad_builder_list_path",
                    "split": "development",
                    "format": "zip",
                    "files": {},
                    "builders": [
                        {
                            "name": "zip",
                            "path": "inside.zip",
                            "members": [],
                        },
                        {
                            "name": "zip",
                            "path": "../outside.zip",
                            "members": [],
                        },
                    ],
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

    def test_builder_forms_cannot_be_mixed(self) -> None:
        specification = {
            "schema_version": "1",
            "cases": [
                {
                    "case_id": "mixed_builder_forms",
                    "split": "development",
                    "format": "zip",
                    "files": {},
                    "builder": {
                        "name": "zip",
                        "path": "one.zip",
                        "members": [],
                    },
                    "builders": [
                        {
                            "name": "zip",
                            "path": "two.zip",
                            "members": [],
                        }
                    ],
                    "sensitive_terms": [],
                    "seeded_values": [],
                    "expected_findings": [],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            cases_path = Path(directory) / "cases.json"
            cases_path.write_text(json.dumps(specification), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cannot use both"):
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

    def test_finding_labels_require_all_exact_identity_fields(self) -> None:
        specification = {
            "schema_version": "1",
            "cases": [
                {
                    "case_id": "missing_path",
                    "split": "development",
                    "format": "text",
                    "files": {"notes.txt": "Contact: person@example.invalid\n"},
                    "sensitive_terms": [],
                    "seeded_values": ["person@example.invalid"],
                    "expected_findings": [
                        {
                            "code": "DIRECT_EMAIL",
                            "severity": "high",
                            "location": "line 1",
                        }
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            cases_path = Path(directory) / "cases.json"
            cases_path.write_text(json.dumps(specification), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must contain exactly"):
                run_benchmark(cases_path)

    def test_wrong_file_does_not_match_a_finding_label(self) -> None:
        specification = {
            "schema_version": "1",
            "cases": [
                {
                    "case_id": "wrong_file",
                    "split": "development",
                    "format": "text",
                    "files": {"notes.txt": "Contact: person@example.invalid\n"},
                    "sensitive_terms": [],
                    "seeded_values": ["person@example.invalid"],
                    "expected_findings": [
                        {
                            "code": "DIRECT_EMAIL",
                            "severity": "high",
                            "path": "other.txt",
                            "location": "line 1",
                        }
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            cases_path = Path(directory) / "cases.json"
            cases_path.write_text(json.dumps(specification), encoding="utf-8")
            summary = run_benchmark(cases_path)["summary"]
        self.assertEqual(summary["matched_findings"], 0)
        self.assertEqual(summary["unexpected_findings"], 1)

    def test_partial_location_does_not_match_a_finding_label(self) -> None:
        specification = {
            "schema_version": "1",
            "cases": [
                {
                    "case_id": "partial_location",
                    "split": "development",
                    "format": "text",
                    "files": {"notes.txt": "Contact: person@example.invalid\n"},
                    "sensitive_terms": [],
                    "seeded_values": ["person@example.invalid"],
                    "expected_findings": [
                        {
                            "code": "DIRECT_EMAIL",
                            "severity": "high",
                            "path": "notes.txt",
                            "location": "line",
                        }
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            cases_path = Path(directory) / "cases.json"
            cases_path.write_text(json.dumps(specification), encoding="utf-8")
            summary = run_benchmark(cases_path)["summary"]
        self.assertEqual(summary["matched_findings"], 0)
        self.assertEqual(summary["unexpected_findings"], 1)


if __name__ == "__main__":
    unittest.main()
