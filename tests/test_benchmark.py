"""Tests for the labelled benchmark."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from neurodata_security_audit.benchmark import (
    render_benchmark_markdown,
    run_benchmark,
)


class BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases_path = Path(__file__).parents[1] / "benchmark" / "cases.json"

    def test_development_pilot_is_fully_labelled(self) -> None:
        result = run_benchmark(self.cases_path)
        summary = result["summary"]

        self.assertEqual(summary["cases"], 10)
        self.assertEqual(summary["matched_findings"], 8)
        self.assertEqual(summary["expected_findings"], 8)
        self.assertEqual(summary["unexpected_findings"], 0)
        self.assertEqual(summary["clean_controls"], 2)
        self.assertEqual(summary["masking_failures"], 0)
        self.assertEqual(summary["integrity_failures"], 0)

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


if __name__ == "__main__":
    unittest.main()
