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


def _task(task_id: str, expected: str) -> dict[str, object]:
    report_code = "a" if task_id == "task_01" else "b"
    return {
        "task_id": task_id,
        "report": f"reports/report-{report_code}.html",
        "capability": "release_decision",
        "prompt": "Choose the correct next step.",
        "choices": [
            {"value": "correct", "label": "Correct"},
            {"value": "wrong", "label": "Wrong"},
        ],
        "expected": expected,
        "critical": True,
        "choice_group": "decision",
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
                        _task("task_01", "correct"),
                        _task("task_02", "wrong"),
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
        first_answer: str,
        second_answer: str,
    ) -> Path:
        path = root / f"{participant}.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "participant_id": participant,
                    "responses": [
                        {
                            "task_id": "task_01",
                            "answer": first_answer,
                            "elapsed_seconds": 12.5,
                            "confidence": 4,
                        },
                        {
                            "task_id": "task_02",
                            "answer": second_answer,
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
                self._write_response(root, "reviewer-01", "correct", "wrong"),
                self._write_response(root, "reviewer-02", "correct", "wrong"),
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
                self._write_response(root, "reviewer-01", "wrong", "wrong"),
                self._write_response(root, "reviewer-02", "correct", "wrong"),
            ]
            result = score_usability(spec, responses)

        self.assertEqual(result["summary"]["critical_accuracy"], 0.75)
        self.assertFalse(result["summary"]["thresholds_met"])

    def test_incomplete_pilot_is_not_a_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._write_spec(root)
            response = self._write_response(
                root,
                "reviewer-01",
                "correct",
                "wrong",
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
                                "task_id": "task_01",
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
                "wrong",
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
                "wrong",
            )
            data = json.loads(response.read_text(encoding="utf-8"))
            data["responses"][0]["elapsed_seconds"] = False
            data["responses"][1]["confidence"] = True
            response.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "non-negative time"):
                score_usability(spec, [response])

    def test_nonfinite_time_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._write_spec(root)
            for value in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(value=value):
                    response = self._write_response(
                        root,
                        "reviewer-01",
                        "correct",
                        "wrong",
                    )
                    data = json.loads(response.read_text(encoding="utf-8"))
                    data["responses"][0]["elapsed_seconds"] = value
                    response.write_text(json.dumps(data), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "non-negative time"):
                        score_usability(spec, [response])

    def test_personal_id_and_extra_fields_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._write_spec(root)

            response = self._write_response(
                root,
                "reviewer-01",
                "correct",
                "wrong",
            )
            data = json.loads(response.read_text(encoding="utf-8"))
            data["participant_id"] = "person@example.com"
            response.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "administrator-assigned"):
                score_usability(spec, [response])

            data["participant_id"] = "reviewer-01"
            data["email"] = "person@example.com"
            response.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unexpected fields"):
                score_usability(spec, [response])

            data.pop("email")
            data["responses"][0]["free_text"] = "Jane Doe"
            response.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unexpected fields"):
                score_usability(spec, [response])

    def test_critical_choice_group_must_be_balanced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._write_spec(root)
            data = json.loads(spec.read_text(encoding="utf-8"))
            data["tasks"][1]["expected"] = "correct"
            spec.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "must use every choice"):
                score_usability(spec, [])

    def test_task_and_report_names_must_be_opaque(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._write_spec(root)
            data = json.loads(spec.read_text(encoding="utf-8"))
            data["tasks"][0]["report"] = "reports/high.html"
            spec.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "opaque"):
                score_usability(spec, [])

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
            self.assertEqual(
                {Path(task["report"]).name for task in spec["tasks"]},
                {path.name for path in first.values()},
            )
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
                        "participant_id": "reviewer-99",
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

        self.assertEqual(result["summary"]["tasks_per_participant"], 12)
        self.assertEqual(result["summary"]["overall_accuracy"], 1.0)
        self.assertEqual(result["summary"]["status"], "pilot_incomplete")
        self.assertFalse(result["summary"]["thresholds_met"])

    def test_report_builder_rejects_stale_html(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "high.html").write_text("stale", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "unexpected HTML"):
                build_reports(root)

    def test_large_report_groups_actions_and_keeps_individual_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            reports = build_reports(Path(directory))
            rendered = reports["report-e"].read_text(encoding="utf-8")

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

        self.assertIn("task_01", rendered)
        self.assertIn("[Report A](reports/report-a.html)", rendered)
        self.assertNotRegex(
            rendered,
            r"\[(clean|high|coverage|integrity)",
        )
        self.assertNotIn('"expected"', rendered)
        self.assertNotIn("Expected answer", rendered)
