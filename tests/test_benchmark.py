"""Tests for the labelled benchmark."""

from __future__ import annotations

import importlib.util
import json
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from benchmark.core import (
    _masking_failures_by_format,
    _score_case,
    render_benchmark_markdown,
    run_benchmark,
)
from benchmark.run_evidence import _git_identity, _recover_hidden, _runtime_identity
from benchmark.run_workflow_comparison import _write_audit
from neurodata_security_audit.models import Finding, ScanReport
from tools.check_wheel_contents import check_wheel
from tools.verify_evidence import _members, verify

_FULL_BENCHMARK_READERS_AVAILABLE = all(
    importlib.util.find_spec(name) is not None
    for name in ("mne", "nibabel", "pydicom")
)


class BenchmarkTests(unittest.TestCase):
    def test_runtime_identity_binds_current_scanner_bytes(self):
        identity = _runtime_identity(Path(__file__).resolve().parents[1])
        self.assertIn("scanner.py", identity["module_sha256"])
        self.assertNotIn(str(Path.home()), identity["import_origin"])

    def test_runtime_identity_rejects_changed_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "src/neurodata_security_audit"
            source.mkdir(parents=True)
            (source / "__init__.py").write_text("# intentionally different source\n")
            with self.assertRaisesRegex(ValueError, "differs from source"):
                _runtime_identity(root)

    def test_runtime_identity_rejects_foreign_loaded_module(self):
        foreign = SimpleNamespace(__file__=str(Path(__file__).resolve()))
        with patch.dict("sys.modules", {"neurodata_security_audit.foreign_probe": foreign}):
            with self.assertRaisesRegex(ValueError, "different runtime origin"):
                _runtime_identity(Path(__file__).resolve().parents[1])

    def test_evidence_runtime_mismatch_rejected_before_output(self):
        from benchmark.run_evidence import run
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "must-not-exist"
            with patch("benchmark.run_evidence._runtime_identity", side_effect=ValueError("runtime mismatch")):
                with self.assertRaisesRegex(ValueError, "runtime mismatch"):
                    run(output, None)
            self.assertFalse(output.exists())

    def test_workflow_checks_saved_bytes_with_single_renderer_call(self):
        report = ScanReport(scanner_version="fault-injection")
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            with patch("benchmark.run_workflow_comparison.render_json", return_value='{}') as json_render, \
                 patch("benchmark.run_workflow_comparison.render_markdown", return_value="[masked]") as md_render, \
                 patch("benchmark.run_workflow_comparison.render_html", side_effect=["<p>SYNTHETIC_LEAK</p>", "[masked]"]) as html_render:
                failures = _write_audit(report, destination, ["SYNTHETIC_LEAK"])
            for render in (json_render, md_render, html_render):
                render.assert_called_once_with(report)
            self.assertEqual(failures, {"json": [], "markdown": [], "html": ["SYNTHETIC_LEAK"]})
            self.assertEqual((destination / "audit.html").read_bytes(), b"<p>SYNTHETIC_LEAK</p>")

    def test_evidence_changed_runtime_after_run_cannot_pass(self):
        from benchmark.run_evidence import run
        summary = {f"{kind}_{metric}": 0 for kind in ("matched", "expected")
                   for metric in ("findings", "references", "container_members", "coverage")}
        summary.update({key: 0 for key in ("unexpected_findings", "unexpected_references",
                       "unexpected_container_members", "masking_failures", "integrity_failures",
                       "clean_controls", "control_cases")})
        with tempfile.TemporaryDirectory() as directory, \
             patch("benchmark.run_evidence._runtime_identity", side_effect=[{"version": "before"}, {"version": "after"}]), \
             patch("benchmark.run_evidence.run_benchmark", return_value={"summary": summary}), \
             patch("benchmark.run_evidence.render_benchmark_markdown", return_value="same"), \
             patch("benchmark.run_evidence._git_identity", return_value={}):
            result = run(Path(directory) / "result", None)
        self.assertFalse(result["runtime_unchanged"])
        self.assertFalse(result["all_gates_pass"])

    def test_workflow_saved_masked_control_preserves_exact_bytes(self):
        report = ScanReport(scanner_version="control")
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            with patch("benchmark.run_workflow_comparison.render_json", return_value='{"value":"[masked]"}\r\n'), \
                 patch("benchmark.run_workflow_comparison.render_markdown", return_value="[masked]\r\n"), \
                 patch("benchmark.run_workflow_comparison.render_html", return_value="<p>[masked]</p>\r\n"):
                self.assertEqual(_write_audit(report, destination, ["SYNTHETIC_LEAK"]),
                                 {"json": [], "markdown": [], "html": []})
            self.assertEqual((destination / "audit.html").read_bytes(), b"<p>[masked]</p>\r\n")

    def test_snapshot_without_git_does_not_discover_parent_repo(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("benchmark.run_evidence.subprocess.check_output") as command:
                result = _git_identity(Path(directory))
            command.assert_not_called()
            self.assertIsNone(result["git_head"])
            self.assertEqual(result["git_mode"], "source-snapshot")

    def test_git_identity_rejects_foreign_top_level(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").write_text("gitdir: synthetic")
            with patch("benchmark.run_evidence.subprocess.check_output", return_value=str(root.parent)) as command:
                result = _git_identity(root)
            self.assertEqual(command.call_count, 1)
            self.assertIsNone(result["git_head"])

    def test_git_identity_handles_missing_git_and_valid_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            with patch("benchmark.run_evidence.subprocess.check_output", side_effect=FileNotFoundError):
                self.assertEqual(_git_identity(root)["git_mode"], "git-metadata-unavailable")
            with patch("benchmark.run_evidence.subprocess.check_output", side_effect=[str(root), "a" * 40, b""]):
                self.assertEqual(_git_identity(root)["git_head"], "a" * 40)

    def test_hidden_recovery_rejects_altered_archive_before_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source", root / "output"
            source.mkdir()
            output.mkdir()
            (source / "neurodata-benchmark-hidden-v1-blocked-76ee38c.zip").write_bytes(b"altered")
            with self.assertRaisesRegex(ValueError, "full archive hash"):
                _recover_hidden(source, output)
            self.assertEqual(list(output.iterdir()), [])

    def test_evidence_verifier_rejects_wrong_trusted_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.zip"
            path.write_bytes(b"not the trusted bundle")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                verify(path, "0" * 64)

    def test_evidence_verifier_rejects_duplicate_or_unsafe_members(self):
        for names in (("same", "same"), ("../outside",), ("/absolute",)):
            with self.subTest(names=names):
                buffer = io.BytesIO()
                with zipfile.ZipFile(buffer, "w") as archive:
                    for name in names:
                        archive.writestr(name, b"synthetic")
                with self.assertRaises(ValueError):
                    _members(buffer.getvalue())

    def test_masking_oracle_does_not_join_json_fields(self):
        report = ScanReport(scanner_version="fault-injection")
        with patch("benchmark.core.render_json", return_value='{"first":"SYNTHETIC", "last":"VALUE"}'), \
             patch("benchmark.core.render_markdown", return_value="[masked]"), \
             patch("benchmark.core.render_html", return_value="<p>[masked]</p>"):
            self.assertEqual(_masking_failures_by_format(report, ["SYNTHETICVALUE"]),
                             {"json": [], "markdown": [], "html": []})

    def test_masking_oracle_detects_escaped_seed_with_real_renderers(self):
        label = dict(code="KNOWN_IDENTIFIER", severity="high", path="notes.txt", location="line 1")
        for seed in ('SYNTHETIC\\alpha&beta', 'SYNTHETIC"<x>|\r\né', 'SYNTHETIC&amp;',
                     'SYNTHETIC \r\nvalue\u2028end'):
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as directory:
                report = ScanReport(scanner_version="fault-injection", findings=[
                    Finding(**label, evidence=seed, message="Synthetic fault")])
                case = dict(case_id="mask_probe", split="development", format="text",
                            files={}, sensitive_terms=[], expected_findings=[label], seeded_values=[seed])
                with patch("benchmark.core.scan_dataset", return_value=report):
                    result = _score_case(case, Path(directory))
                self.assertTrue(result["expected"][0]["matched"])
                self.assertEqual(result["masking_failures"], [seed])
                self.assertEqual(result["masking_failures_by_format"],
                                 {name: [seed] for name in ("json", "markdown", "html")})

    def test_masking_oracle_attributes_each_renderer_fault(self):
        seed = 'SYNTHETIC\\é&|\nend'
        encoded = {
            "json": json.dumps({"nested": [{seed: "value"}]}),
            "markdown": "| SYNTHETIC\\é&amp;\\|\\nend |",
            "html": '<p title="SYNTHETIC&#92;é&#38;|&#10;end">masked</p>',
        }
        case = dict(case_id="mask_probe", split="development", format="text",
                    files={}, sensitive_terms=[], expected_findings=[], seeded_values=[seed])
        for faulty in (None, "json", "markdown", "html"):
            with self.subTest(faulty=faulty), tempfile.TemporaryDirectory() as directory:
                with patch("benchmark.core.scan_dataset", return_value=ScanReport(scanner_version="fault-injection")), \
                     patch("benchmark.core.render_json", return_value=encoded["json"] if faulty == "json" else '{"safe": "[masked]"}'), \
                     patch("benchmark.core.render_markdown", return_value=encoded["markdown"] if faulty == "markdown" else "[masked]"), \
                     patch("benchmark.core.render_html", return_value=encoded["html"] if faulty == "html" else "<p>[masked]</p>"):
                    result = _score_case(case, Path(directory))
                self.assertEqual(result["masking_failures"], [seed] if faulty else [])
                self.assertEqual(result["masking_failures_by_format"],
                                 {name: [seed] if name == faulty else [] for name in encoded})

    def test_public_wheel_rejects_source_only_benchmark_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            wheel = Path(directory) / "candidate.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("neurodata_security_audit/cli.py", "")
                archive.writestr("benchmark/core.py", "")
                archive.writestr(
                    "candidate.dist-info/entry_points.txt",
                    "neurodata-security-audit = neurodata_security_audit.cli:main\n",
                )
            with self.assertRaisesRegex(SystemExit, "source-only"):
                check_wheel(wheel)

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
        self.assertEqual(summary["duplicate_findings"], 0)
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
