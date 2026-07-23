"""Tests for the report-usability scoring gate."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from neurodata_security_audit.usability import (
    render_reviewer_packet,
    render_usability_markdown,
    score_usability,
)
from usability.build_reports import build_reports


def _task(task_id: str, capability: str, *, critical: bool) -> dict[str, object]:
    return {
        "task_id": task_id,
        "report": "reports/example.html",
        "capability": capability,
        "prompt": "Choose the correct next step.",
        "choices": [
            {"value": "correct", "label": "Correct"},
            {"value": "wrong", "label": "Wrong"},
        ],
        "expected": "correct",
        "critical": critical,
    }


class UsabilityBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).parents[1]

    def _write_spec(self, root: Path) -> Path:
        path = root / "spec.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "suite_name": "test-suite",
                    "thresholds": {
                        "minimum_participants": 2,
                        "overall_accuracy": 0.8,
                        "capability_accuracy": 0.75,
                        "critical_accuracy": 1.0,
                    },
                    "tasks": [
                        _task("release", "release_decision", critical=True),
                        _task("location", "finding_location", critical=False),
                    ],
                }
            ),
            encoding="utf-8",
        )
        return path

    def _write_response(
        self,
        root: Path,
        participant: str,
        release_answer: str,
        location_answer: str,
    ) -> Path:
        path = root / f"{participant}.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "participant_id": participant,
                    "responses": [
                        {
                            "task_id": "release",
                            "answer": release_answer,
                            "elapsed_seconds": 12.5,
                            "confidence": 4,
                        },
                        {
                            "task_id": "location",
                            "answer": location_answer,
                            "elapsed_seconds": 20,
                            "confidence": 3,
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_complete_result_passes_precommitted_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._write_spec(root)
            responses = [
                self._write_response(root, "reviewer-01", "correct", "correct"),
                self._write_response(root, "reviewer-02", "correct", "correct"),
            ]
            result = score_usability(spec, responses)

        summary = result["summary"]
        self.assertEqual(summary["participants"], 2)
        self.assertEqual(summary["overall_accuracy"], 1.0)
        self.assertEqual(summary["critical_accuracy"], 1.0)
        self.assertTrue(summary["thresholds_met"])
        self.assertEqual(summary["status"], "complete")
        self.assertIn("Thresholds met: yes", render_usability_markdown(result))

    def test_critical_error_fails_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._write_spec(root)
            responses = [
                self._write_response(root, "reviewer-01", "wrong", "correct"),
                self._write_response(root, "reviewer-02", "correct", "correct"),
            ]
            result = score_usability(spec, responses)

        self.assertEqual(result["summary"]["critical_accuracy"], 0.5)
        self.assertFalse(result["summary"]["thresholds_met"])

    def test_incomplete_pilot_is_not_a_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._write_spec(root)
            response = self._write_response(
                root,
                "reviewer-01",
                "correct",
                "correct",
            )
            result = score_usability(spec, [response])

        self.assertEqual(result["summary"]["status"], "pilot_incomplete")
        self.assertFalse(result["summary"]["thresholds_met"])

    def test_missing_task_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._write_spec(root)
            response = root / "reviewer.json"
            response.write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "participant_id": "reviewer-01",
                        "responses": [
                            {
                                "task_id": "release",
                                "answer": "correct",
                                "elapsed_seconds": 10,
                                "confidence": 4,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "missing responses"):
                score_usability(spec, [response])

    def test_duplicate_participant_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._write_spec(root)
            first = self._write_response(
                root,
                "reviewer-01",
                "correct",
                "correct",
            )
            duplicate = root / "duplicate.json"
            duplicate.write_bytes(first.read_bytes())
            with self.assertRaisesRegex(ValueError, "Duplicate participant_id"):
                score_usability(spec, [first, duplicate])

    def test_invalid_thresholds_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._write_spec(root)
            data = json.loads(spec.read_text(encoding="utf-8"))
            data["thresholds"]["overall_accuracy"] = 1.1
            spec.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "overall_accuracy"):
                score_usability(spec, [])

    def test_boolean_time_and_confidence_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._write_spec(root)
            response = self._write_response(
                root,
                "reviewer-01",
                "correct",
                "correct",
            )
            data = json.loads(response.read_text(encoding="utf-8"))
            data["responses"][0]["elapsed_seconds"] = False
            data["responses"][1]["confidence"] = True
            response.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "non-negative time"):
                score_usability(spec, [response])

    def test_response_template_matches_precommitted_tasks(self) -> None:
        spec = json.loads(
            (self.project_root / "usability" / "spec.json").read_text(encoding="utf-8")
        )
        template = json.loads(
            (self.project_root / "usability" / "response_template.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(
            [task["task_id"] for task in spec["tasks"]],
            [response["task_id"] for response in template["responses"]],
        )
        self.assertEqual(
            len(template["responses"]),
            len({response["task_id"] for response in template["responses"]}),
        )

    def test_precommitted_spec_and_reports_are_deterministic(self) -> None:
        spec = json.loads(
            (self.project_root / "usability" / "spec.json").read_text(encoding="utf-8")
        )
        with (
            tempfile.TemporaryDirectory() as first_dir,
            tempfile.TemporaryDirectory() as second_dir,
        ):
            first = build_reports(Path(first_dir))
            second = build_reports(Path(second_dir))

            self.assertEqual(set(first), set(second))
            for name in first:
                self.assertEqual(
                    first[name].read_bytes(),
                    second[name].read_bytes(),
                )

            response_path = Path(first_dir) / "reviewer.json"
            response_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "participant_id": "synthetic-control",
                        "responses": [
                            {
                                "task_id": task["task_id"],
                                "answer": task["expected"],
                                "elapsed_seconds": 1,
                                "confidence": 5,
                            }
                            for task in spec["tasks"]
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = score_usability(
                self.project_root / "usability" / "spec.json",
                [response_path],
            )

        self.assertEqual(result["summary"]["tasks_per_participant"], 10)
        self.assertEqual(result["summary"]["overall_accuracy"], 1.0)
        self.assertEqual(result["summary"]["status"], "pilot_incomplete")
        self.assertFalse(result["summary"]["thresholds_met"])

    def test_large_report_groups_actions_and_keeps_individual_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            reports = build_reports(Path(directory))
            rendered = reports["large_review"].read_text(encoding="utf-8")

        self.assertIn(
            "121 individual items are summarized in 5 action groups",
            rendered,
        )
        self.assertIn('aria-label="Filter findings"', rendered)
        self.assertIn("Review 121", rendered)
        self.assertIn("Recording.TechnicianContact", rendered)
        self.assertEqual(121, rendered.count('class="finding-row finding-review"'))
        self.assertNotIn("<script", rendered.lower())

    def test_reviewer_packet_does_not_contain_the_answer_key(self) -> None:
        rendered = render_reviewer_packet(self.project_root / "usability" / "spec.json")

        self.assertIn("clean_release_decision", rendered)
        self.assertIn("[clean](reports/clean.html)", rendered)
        self.assertNotIn('"expected"', rendered)
        self.assertNotIn("Expected answer", rendered)
