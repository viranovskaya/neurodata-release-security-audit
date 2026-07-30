"""Tests for the report-usability scoring gate."""

from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import usability
from neurodata_security_audit.usability import (
    build_response_template,
    render_reviewer_packet,
    render_usability_markdown,
    score_usability,
)
from usability._io import packaged_specification, write_text_new, write_text_new_owned
from usability.build_participant_bundle import build_participant_bundle
from usability.build_response import build_response_file
from usability.build_reports import build_reports
from usability.score_responses import (
    _build_parser,
    write_score_outputs,
)


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

    def test_critical_report_cannot_be_reused_by_auxiliary_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self._write_spec(root)
            data = json.loads(spec.read_text(encoding="utf-8"))
            auxiliary = dict(data["tasks"][0])
            auxiliary.update(
                {
                    "task_id": "task_03",
                    "critical": False,
                    "choice_group": None,
                }
            )
            data["tasks"].append(auxiliary)
            spec.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "cannot be reused"):
                score_usability(spec, [])

    def test_response_template_matches_precommitted_tasks(self) -> None:
        with packaged_specification() as specification:
            spec = json.loads(specification.read_text(encoding="utf-8"))
            template = build_response_template(specification, "reviewer-07")

        self.assertEqual("reviewer-07", template["participant_id"])
        self.assertEqual(
            [task["task_id"] for task in spec["tasks"]],
            [response["task_id"] for response in template["responses"]],
        )
        self.assertEqual(
            len(template["responses"]),
            len({response["task_id"] for response in template["responses"]}),
        )

    def test_installed_usability_package_contains_admin_materials(self) -> None:
        package_root = Path(usability.__file__).resolve().parent
        required = ("README.md", "prolific_pilot1_results.md", "spec.json")

        for relative_path in required:
            with self.subTest(relative_path=relative_path):
                self.assertTrue((package_root / relative_path).is_file())

        if package_root != self.project_root / "usability":
            excluded = (
                "response_template.json",
                "reviewer_packet.md",
                "reports/report-a.html",
                "results/README.md",
            )
            for relative_path in excluded:
                with self.subTest(excluded=relative_path):
                    self.assertFalse((package_root / relative_path).exists())

    def test_precommitted_spec_and_reports_are_deterministic(self) -> None:
        with packaged_specification() as specification:
            spec = json.loads(specification.read_text(encoding="utf-8"))
            with (
                tempfile.TemporaryDirectory() as first_dir,
                tempfile.TemporaryDirectory() as second_dir,
            ):
                first = build_reports(Path(first_dir))
                second = build_reports(Path(second_dir))

                self.assertEqual(
                    set(first),
                    set(second),
                )
                self.assertEqual(
                    {Path(task["report"]).name for task in spec["tasks"]},
                    {path.name for path in first.values()},
                )
                for name in first:
                    self.assertEqual(
                        first[name].read_bytes(),
                        second[name].read_bytes(),
                    )
                    report_letter = name.removeprefix("report-").upper()
                    rendered = first[name].read_text(encoding="utf-8")
                    self.assertIn(
                        "NeuroData release security audit"
                        f" — Report {report_letter} of {len(first)}",
                        rendered,
                    )
                self.assertEqual(
                    len(first),
                    len({path.read_bytes() for path in first.values()}),
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
                result = score_usability(specification, [response_path])

        self.assertEqual(result["summary"]["tasks_per_participant"], 13)
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
            rendered = reports["report-i"].read_text(encoding="utf-8")

        self.assertIn(
            "124 individual items are summarized in 4 action groups",
            rendered,
        )
        self.assertIn('aria-label="Filter findings"', rendered)
        self.assertIn("Find a file, field or value:", rendered)
        self.assertIn("Distinct evidence", rendered)
        self.assertIn("finding-code-", rendered)
        self.assertIn("Review 124", rendered)
        self.assertNotIn('id="findings-high"', rendered)
        self.assertNotIn('id="findings-info"', rendered)
        self.assertIn('role="status" aria-live="polite"', rendered)
        self.assertIn('role="region" tabindex="0"', rendered)
        self.assertIn('<caption class="sr-only">All findings</caption>', rendered)
        self.assertIn(
            ".finding-row:not(.finding-code-0) { display: none; }",
            rendered,
        )
        self.assertNotIn("display: none; }}", rendered)
        self.assertIn(".finding-row { display: table-row !important; }", rendered)
        self.assertIn(
            ".provisional-section details > * { display: block !important; }",
            rendered,
        )
        self.assertEqual(124, rendered.count('class="finding-row finding-review '))
        action_summary, individual_findings = rendered.split(
            '<section id="all-findings">',
            maxsplit=1,
        )
        self.assertNotIn("&lt;masked-review:length=17&gt;", action_summary)
        self.assertIn("&lt;masked-review:length=17&gt;", individual_findings)
        self.assertNotIn("<script", rendered.lower())

    def test_single_finding_uses_singular_grammar(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            reports = build_reports(Path(directory))
            rendered = reports["report-b"].read_text(encoding="utf-8")

        self.assertIn("1 individual item is summarized", rendered)
        self.assertNotIn("1 individual item are summarized", rendered)
        self.assertIn("1 finding\n           shown.", rendered)
        self.assertNotIn("1 findings shown.", rendered)

    def test_summary_points_partial_checks_to_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            reports = build_reports(Path(directory))
            rendered = reports["report-c"].read_text(encoding="utf-8")
        normalized = " ".join(rendered.split())

        self.assertNotIn("skipped or partially covered", normalized)
        self.assertIn(
            "This count excludes folders and differs from the inventory total.",
            normalized,
        )
        self.assertIn('href="#coverage"', rendered)

    def test_inventory_report_explains_files_and_folders_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            reports = build_reports(Path(directory))
            rendered = reports["report-j"].read_text(encoding="utf-8")
        normalized = " ".join(rendered.split())

        self.assertIn("Files and folders accounted for", rendered)
        self.assertIn(
            "3 total entries = 1 regular file + 2 folders.",
            normalized,
        )
        self.assertIn('<div class="value">3</div>', rendered)

    def test_reviewer_packet_does_not_contain_the_answer_key(self) -> None:
        with packaged_specification() as specification:
            rendered = render_reviewer_packet(specification)

        self.assertIn("task_01", rendered)
        self.assertIn("[Report C](reports/report-c.html)", rendered)
        self.assertIn(
            "keep this file inside the supplied participant folder",
            rendered,
        )
        self.assertIn("Markdown editor with clickable links", rendered)
        self.assertIn("Do not move this file", rendered)
        self.assertIn("return the completed Markdown packet", rendered)
        self.assertNotRegex(
            rendered,
            r"\[(clean|high|coverage|integrity)",
        )
        self.assertNotIn('"expected"', rendered)
        self.assertNotIn("Expected answer", rendered)

    def test_participant_bundle_is_separate_and_has_no_answer_key(self) -> None:
        package_root = Path(usability.__file__).resolve().parent
        before = sorted(
            (path.relative_to(package_root).as_posix(), path.read_bytes())
            for path in package_root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        )
        with tempfile.TemporaryDirectory() as directory:
            destination = (Path(directory) / "participant").resolve()
            paths = build_participant_bundle(destination)
            self.assertTrue(all(path.is_absolute() for path in paths))
            self.assertTrue(all(destination in path.parents for path in paths))
            combined = "\n".join(
                path.read_text(encoding="utf-8") for path in paths
            )
            names = {path.relative_to(destination).as_posix() for path in paths}

            self.assertEqual(len(paths), 11)
            self.assertIn("reviewer_packet.md", names)
            self.assertNotIn("response_template.json", names)
            self.assertNotIn("spec.json", names)
            self.assertNotIn('"expected"', combined)
            self.assertNotIn("spec.json", combined)
            with packaged_specification() as specification:
                private_spec = json.loads(
                    specification.read_text(encoding="utf-8")
                )
            answer_key = {
                str(task["task_id"]): str(task["expected"])
                for task in private_spec["tasks"]
            }
            serialized = json.dumps(
                answer_key,
                sort_keys=True,
                separators=(",", ":"),
            )
            fingerprint = hashlib.sha256(serialized.encode()).hexdigest()
            self.assertNotIn(serialized, combined)
            self.assertNotIn(fingerprint, combined)
            with self.assertRaises(FileExistsError):
                build_participant_bundle(destination)

        after = sorted(
            (path.relative_to(package_root).as_posix(), path.read_bytes())
            for path in package_root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        )
        self.assertEqual(before, after)

    def test_administrator_builds_response_outside_participant_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "responses" / "reviewer-01.json"
            created = build_response_file("reviewer-01", output)
            response = json.loads(created.read_text(encoding="utf-8"))

            self.assertEqual(output.resolve(), created)
            self.assertEqual("reviewer-01", response["participant_id"])
            self.assertNotIn("expected", created.read_text(encoding="utf-8"))
            with self.assertRaises(FileExistsError):
                build_response_file("reviewer-01", output)

    def test_administrator_response_rejects_bad_id_and_package_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "reviewer-XX"):
                build_response_file(
                    "daria@example.org",
                    Path(directory) / "response.json",
                )

        package_root = Path(usability.__file__).resolve().parent
        package_output = package_root / "response.json"
        with self.assertRaisesRegex(ValueError, "outside the installed package"):
            build_response_file("reviewer-01", package_output)
        self.assertFalse(package_output.exists())

    def test_participant_bundle_refuses_existing_foreign_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = (Path(directory) / "participant").resolve()
            destination.mkdir()
            foreign = destination / "keep.txt"
            foreign.write_text("do not replace\n", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                build_participant_bundle(destination)
            self.assertEqual("do not replace\n", foreign.read_text(encoding="utf-8"))
            self.assertEqual([foreign], list(destination.iterdir()))

    def test_scorer_outputs_are_no_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with packaged_specification() as specification:
                spec = json.loads(specification.read_text(encoding="utf-8"))
                response = root / "reviewer-01.json"
                response.write_text(
                    json.dumps(
                        {
                            "schema_version": "1",
                            "participant_id": "reviewer-01",
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
            json_output = root / "result.json"
            markdown_output = root / "result.md"
            write_score_outputs([response], json_output, markdown_output)
            first_json = json_output.read_bytes()
            first_markdown = markdown_output.read_bytes()
            self.assertEqual(
                sorted([json_output, markdown_output, response]),
                sorted(root.iterdir()),
            )

            with self.assertRaises(FileExistsError):
                write_score_outputs([response], json_output, markdown_output)
            self.assertEqual(first_json, json_output.read_bytes())
            self.assertEqual(first_markdown, markdown_output.read_bytes())

    def test_scorer_rejects_outputs_inside_installed_package(self) -> None:
        package_root = Path(usability.__file__).resolve().parent
        with self.assertRaisesRegex(ValueError, "outside the installed package"):
            write_score_outputs(
                [],
                package_root / "result.json",
                package_root / "result.md",
            )
        self.assertFalse((package_root / "result.json").exists())
        self.assertFalse((package_root / "result.md").exists())

    def test_scorer_cli_has_no_specification_override(self) -> None:
        parser = _build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "reviewer-01.json",
                    "--specification",
                    "other.json",
                    "--json",
                    "result.json",
                    "--markdown",
                    "result.md",
                ]
            )

    def test_scorer_rollback_preserves_substituted_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with packaged_specification() as specification:
                spec = json.loads(specification.read_text(encoding="utf-8"))
            response = root / "reviewer-01.json"
            response.write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "participant_id": "reviewer-01",
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
            json_output = root / "result.json"
            markdown_output = root / "result.md"
            original_owned_write = write_text_new_owned

            def replace_json_output(path: Path, text: str):
                identity = original_owned_write(path, text)
                path.unlink()
                path.write_text("foreign object\n", encoding="utf-8")
                return identity

            with (
                mock.patch(
                    "usability.score_responses.write_text_new_owned",
                    side_effect=replace_json_output,
                ),
                mock.patch(
                    "usability.score_responses.write_text_new",
                    side_effect=OSError("simulated Markdown failure"),
                ),
                self.assertRaisesRegex(OSError, "simulated Markdown failure"),
            ):
                write_score_outputs([response], json_output, markdown_output)

            self.assertEqual(
                "foreign object\n",
                json_output.read_text(encoding="utf-8"),
            )
            self.assertFalse(markdown_output.exists())
