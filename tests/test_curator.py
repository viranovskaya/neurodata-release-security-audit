from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import csv
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from neurodata_security_audit.cli import main
from neurodata_security_audit.curator import (
    compare_reports,
    render_checklist_tsv,
    render_comparison_json,
    render_comparison_markdown,
    report_sha256,
    write_text_new,
    write_texts_new,
)
from neurodata_security_audit.models import CoverageEntry, Finding, ScanReport
from neurodata_security_audit.reporting import render_json


def _coverage(
    path: str,
    status: str = "fully_inspected_metadata",
) -> CoverageEntry:
    return CoverageEntry(
        path=path,
        entry_type="file",
        status=status,
        reason="Synthetic coverage state",
    )


def _finding(
    code: str,
    severity: str,
    path: str,
    evidence: str,
) -> Finding:
    return Finding(
        code=code,
        severity=severity,
        path=path,
        location="JSON field <key>",
        evidence=evidence,
        message="Review this field before release.",
    )


class CuratorWorkflowTests(unittest.TestCase):
    def test_checklist_is_deterministic_redacted_and_spreadsheet_safe(self) -> None:
        report = ScanReport(
            scanner_version="test",
            findings=[
                _finding(
                    "DIRECT_EMAIL",
                    "high",
                    "=cmd|' /C calc'!A0",
                    "private.person@example.org",
                ),
                _finding(
                    "FREE_TEXT_METADATA",
                    "review",
                    "notes.json",
                    "<redacted:free-text,length=14>",
                ),
                _finding(
                    "PUBLIC_CONTACT",
                    "info",
                    "README",
                    "<redacted:email,length=18>",
                ),
            ],
            coverage=[
                _coverage("notes.json"),
                _coverage(
                    "@legacy.bin",
                    status="unsupported_manual_review",
                ),
            ],
        ).to_dict()

        first = render_checklist_tsv(report)
        second = render_checklist_tsv(report)
        rows = list(csv.DictReader(io.StringIO(first), delimiter="\t"))

        self.assertEqual(first, second)
        self.assertEqual(3, len(rows))
        self.assertNotIn("private.person@example.org", first)
        self.assertNotIn("PUBLIC_CONTACT", first)
        self.assertTrue(
            all(
                not value.lstrip().startswith(("=", "+", "-", "@"))
                for row in rows
                for value in row.values()
            )
        )
        self.assertTrue(all(len(row["item_id"]) == 64 for row in rows))
        self.assertTrue(
            all(row["source_report_sha256"] == report_sha256(report) for row in rows)
        )
        self.assertTrue(all(row["curator_decision"] == "" for row in rows))
        self.assertTrue(all(row["completed"] == "" for row in rows))

    def test_checklist_rejects_failed_integrity(self) -> None:
        report = ScanReport(
            scanner_version="test",
            manifest_recheck_passed=False,
        ).to_dict()

        with self.assertRaisesRegex(ValueError, "integrity"):
            render_checklist_tsv(report)

    def test_comparison_classifies_new_remaining_and_resolved(self) -> None:
        remaining = _finding(
            "FREE_TEXT_METADATA",
            "review",
            "notes.json",
            "<redacted:free-text,length=14>",
        )
        baseline = ScanReport(
            scanner_version="old",
            findings=[
                remaining,
                _finding(
                    "DIRECT_EMAIL",
                    "high",
                    "participants.tsv",
                    "<redacted:email,length=18>",
                ),
            ],
            coverage=[
                _coverage("README"),
                _coverage("old.bin", "unsupported_manual_review"),
            ],
        ).to_dict()
        current = ScanReport(
            scanner_version="new",
            findings=[
                remaining,
                _finding(
                    "PUBLIC_CONTACT",
                    "info",
                    (
                        "<img src=x onerror=alert(1)> "
                        "![remote](https://attacker.invalid/pixel)"
                    ),
                    "<redacted:email,length=22>",
                ),
            ],
            coverage=[
                _coverage("README"),
                _coverage("new.bin", "not_traversed"),
            ],
        ).to_dict()

        comparison = compare_reports(
            baseline,
            current,
            same_dataset_confirmed=True,
        )
        rendered_json = render_comparison_json(comparison)
        rendered_markdown = render_comparison_markdown(comparison)

        self.assertEqual(
            {"new": 2, "remaining": 1, "resolved": 2},
            comparison["summary"],
        )
        self.assertEqual(
            ["new", "new", "remaining", "resolved", "resolved"],
            [item["state"] for item in comparison["items"]],
        )
        self.assertNotIn("<redacted:email", rendered_json)
        self.assertNotIn("<redacted:email", rendered_markdown)
        self.assertIn("not proof of anonymity", rendered_markdown)
        self.assertIn("Current release state: `hold_review`", rendered_markdown)
        self.assertIn(
            r"&lt;img src=x onerror=alert\(1\)&gt;",
            rendered_markdown,
        )
        self.assertNotIn("<img src=x", rendered_markdown)
        self.assertNotIn("![remote]", rendered_markdown)
        self.assertIn(r"!\[remote\]\(https://attacker.invalid/pixel\)", rendered_markdown)
        self.assertIn(
            r"| resolved | high | finding | DIRECT\_EMAIL |",
            rendered_markdown,
        )
        self.assertEqual(
            {
                "curator_confirmed_same_dataset": True,
                "baseline_entries": 2,
                "current_entries": 2,
                "shared_entries": 1,
            },
            comparison["dataset_identity"],
        )
        self.assertEqual(
            report_sha256(baseline),
            comparison["baseline"]["report_sha256"],
        )
        self.assertEqual(
            report_sha256(current),
            comparison["current"]["report_sha256"],
        )

    def test_comparison_rejects_failed_integrity_schema_and_unrelated_reports(
        self,
    ) -> None:
        good = ScanReport(
            scanner_version="test",
            coverage=[_coverage("README")],
        ).to_dict()
        failed = ScanReport(
            scanner_version="test",
            coverage=[_coverage("README")],
            manifest_recheck_passed=False,
        ).to_dict()
        wrong_schema = json.loads(json.dumps(good))
        wrong_schema["schema_version"] = "other"
        unrelated = ScanReport(
            scanner_version="test",
            coverage=[_coverage("different.txt")],
        ).to_dict()

        with self.assertRaisesRegex(ValueError, "integrity"):
            compare_reports(good, failed, same_dataset_confirmed=True)
        with self.assertRaisesRegex(ValueError, "schema"):
            compare_reports(good, wrong_schema, same_dataset_confirmed=True)
        with self.assertRaisesRegex(ValueError, "no shared"):
            compare_reports(good, unrelated, same_dataset_confirmed=True)
        with self.assertRaisesRegex(ValueError, "confirm"):
            compare_reports(good, good, same_dataset_confirmed=False)

        empty = ScanReport(scanner_version="test").to_dict()
        with self.assertRaisesRegex(ValueError, "no shared"):
            compare_reports(good, empty, same_dataset_confirmed=True)

    def test_inconsistent_summary_is_rejected(self) -> None:
        report = ScanReport(
            scanner_version="test",
            findings=[
                _finding(
                    "DIRECT_EMAIL",
                    "high",
                    "participants.tsv",
                    "<redacted:email,length=18>",
                )
            ],
            coverage=[_coverage("README")],
        ).to_dict()
        report["summary"]["findings_high"] = 0

        with self.assertRaisesRegex(ValueError, "summary.findings_high"):
            render_checklist_tsv(report)
        with self.assertRaisesRegex(ValueError, "summary.findings_high"):
            compare_reports(
                report,
                report,
                same_dataset_confirmed=True,
            )

        coverage_report = ScanReport(
            scanner_version="test",
            coverage=[
                _coverage("README", "unsupported_manual_review"),
            ],
        ).to_dict()
        coverage_report["summary"]["unsupported_manual_review"] = 0
        with self.assertRaisesRegex(
            ValueError,
            "summary.unsupported_manual_review",
        ):
            render_checklist_tsv(coverage_report)

    def test_new_output_never_replaces_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "checklist.tsv"
            output.write_text("existing\n", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                write_text_new(output, "replacement\n")

            self.assertEqual("existing\n", output.read_text(encoding="utf-8"))

    def test_multi_output_rollback_preserves_substituted_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "comparison.json"
            second = root / "comparison.md"
            original_link = os.link
            calls = 0

            def fail_second(source: Path, destination: Path, *args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    first.unlink()
                    descriptor = os.open(
                        first,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o600,
                    )
                    try:
                        os.write(descriptor, b"foreign object\n")
                    finally:
                        os.close(descriptor)
                    raise OSError("simulated second output failure")
                return original_link(source, destination, *args, **kwargs)

            with (
                mock.patch("neurodata_security_audit.curator.os.link", new=fail_second),
                self.assertRaisesRegex(OSError, "second output failure"),
            ):
                write_texts_new(
                    {
                        first: '{"temporary": true}\n',
                        second: "# Temporary\n",
                    }
                )

            self.assertEqual(
                "foreign object\n",
                first.read_text(encoding="utf-8"),
            )
            self.assertFalse(second.exists())

    def test_multi_output_failure_removes_only_owned_publications(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "comparison.json"
            second = root / "comparison.md"
            original_link = os.link
            calls = 0

            def fail_second(source: Path, destination: Path, *args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated second output failure")
                return original_link(source, destination, *args, **kwargs)

            with (
                mock.patch("neurodata_security_audit.curator.os.link", new=fail_second),
                self.assertRaisesRegex(OSError, "second output failure"),
            ):
                write_texts_new(
                    {
                        first: '{"temporary": true}\n',
                        second: "# Temporary\n",
                    }
                )

            self.assertFalse(first.exists())
            self.assertFalse(second.exists())

    def test_new_output_is_private_regular_file_with_one_link(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "checklist.tsv"
            write_text_new(output, "header\n")

            metadata = output.lstat()
            self.assertEqual(0o600, metadata.st_mode & 0o777)
            self.assertEqual(1, metadata.st_nlink)

    def test_cli_builds_checklist_and_comparison_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = ScanReport(
                scanner_version="old",
                findings=[
                    _finding(
                        "DIRECT_EMAIL",
                        "high",
                        "participants.tsv",
                        "<redacted:email,length=18>",
                    )
                ],
                coverage=[_coverage("README")],
            )
            current = ScanReport(
                scanner_version="new",
                coverage=[_coverage("README")],
            )
            baseline_path = root / "baseline.json"
            current_path = root / "current.json"
            baseline_path.write_text(render_json(baseline), encoding="utf-8")
            current_path.write_text(render_json(current), encoding="utf-8")
            checklist_path = root / "review" / "checklist.tsv"
            comparison_json = root / "review" / "comparison.json"
            comparison_markdown = root / "review" / "comparison.md"

            with redirect_stdout(io.StringIO()):
                checklist_status = main(
                    [
                        "checklist",
                        str(baseline_path),
                        "--tsv",
                        str(checklist_path),
                    ]
                )
                compare_status = main(
                    [
                        "compare",
                        str(baseline_path),
                        str(current_path),
                        "--confirm-same-dataset",
                        "--json",
                        str(comparison_json),
                        "--markdown",
                        str(comparison_markdown),
                    ]
                )

            self.assertEqual(0, checklist_status)
            self.assertEqual(0, compare_status)
            self.assertTrue(checklist_path.is_file())
            self.assertTrue(comparison_json.is_file())
            self.assertTrue(comparison_markdown.is_file())
            self.assertEqual(
                {"new": 0, "remaining": 0, "resolved": 1},
                json.loads(comparison_json.read_text(encoding="utf-8"))["summary"],
            )

            with redirect_stderr(io.StringIO()):
                repeated = main(
                    [
                        "checklist",
                        str(baseline_path),
                        "--tsv",
                        str(checklist_path),
                    ]
                )
                same_output = main(
                    [
                        "compare",
                        str(baseline_path),
                        str(current_path),
                        "--confirm-same-dataset",
                        "--json",
                        str(root / "same.txt"),
                        "--markdown",
                        str(root / "same.txt"),
                    ]
                )

            self.assertEqual(2, repeated)
            self.assertEqual(2, same_output)

            with (
                redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                main(
                    [
                        "compare",
                        str(baseline_path),
                        str(current_path),
                        "--json",
                        str(root / "missing-confirmation.json"),
                        "--markdown",
                        str(root / "missing-confirmation.md"),
                    ]
                )


if __name__ == "__main__":
    unittest.main()
