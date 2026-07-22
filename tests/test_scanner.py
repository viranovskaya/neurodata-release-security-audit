from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from neurodata_security_audit.cli import main
from neurodata_security_audit.reporting import render_json, render_markdown
from neurodata_security_audit.scanner import ScanPolicy, scan_dataset


def _write_edf(path: Path, patient: str, recording: str, start_date: str) -> None:
    header = bytearray(b" " * 256)
    header[0:8] = b"0       "
    header[8:88] = patient.encode("ascii").ljust(80)[:80]
    header[88:168] = recording.encode("ascii").ljust(80)[:80]
    header[168:176] = start_date.encode("ascii").ljust(8)[:8]
    header[176:184] = b"12000000"
    header[184:192] = b"256     "
    path.write_bytes(header)


class ScannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "dataset"
        self.root.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _codes(self) -> list[str]:
        return [finding.code for finding in scan_dataset(self.root).findings]

    def test_clean_bids_and_brainvision(self) -> None:
        (self.root / "dataset_description.json").write_text(
            '{"Name": "Synthetic EEG", "BIDSVersion": "1.10.1"}\n',
            encoding="utf-8",
        )
        eeg_dir = self.root / "sub-01" / "eeg"
        eeg_dir.mkdir(parents=True)
        (eeg_dir / "sub-01_task-rest_eeg.vhdr").write_text(
            "Brain Vision Data Exchange Header File Version 1.0\n"
            "[Common Infos]\n"
            "DataFile=sub-01_task-rest_eeg.eeg\n"
            "MarkerFile=sub-01_task-rest_eeg.vmrk\n",
            encoding="utf-8",
        )
        (eeg_dir / "sub-01_task-rest_eeg.vmrk").write_text(
            "Brain Vision Data Exchange Marker File, Version 1.0\n"
            "[Marker Infos]\n"
            "Mk1=Stimulus,S 1,10,1,0\n",
            encoding="utf-8",
        )
        (eeg_dir / "sub-01_task-rest_eeg.eeg").write_bytes(b"synthetic")

        report = scan_dataset(self.root)
        self.assertEqual([], [item for item in report.findings if item.severity == "high"])
        self.assertIn("sub-01/eeg/sub-01_task-rest_eeg.eeg", [item.path for item in report.skipped_files])

    def test_direct_values_are_detected_and_masked(self) -> None:
        email = "alice.researcher@example.org"
        phone = "+1 202 555 0199"
        local_path = "/Users/alice/private/participants.csv"
        token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"
        (self.root / "notes.txt").write_text(
            f"Contact: {email}\nPhone: {phone}\nSource: {local_path}\nToken: {token}\n",
            encoding="utf-8",
        )

        report = scan_dataset(self.root)
        codes = {finding.code for finding in report.findings}
        self.assertTrue({"DIRECT_EMAIL", "DIRECT_PHONE", "LOCAL_PATH", "POTENTIAL_SECRET"} <= codes)

        rendered = render_json(report) + render_markdown(report)
        for secret in (email, phone, local_path, token):
            self.assertNotIn(secret, rendered)

    def test_home_paths_for_supported_platforms_are_masked(self) -> None:
        paths = (
            "/Users/alice/private/participants.csv",
            "/home/alice/private/participants.csv",
            r"C:\Users\alice\private\participants.csv",
        )
        (self.root / "paths.txt").write_text("\n".join(paths), encoding="utf-8")
        report = scan_dataset(self.root)
        local_paths = [finding for finding in report.findings if finding.code == "LOCAL_PATH"]
        self.assertEqual(3, len(local_paths))
        rendered = render_json(report) + render_markdown(report)
        for path in paths:
            self.assertNotIn(path, rendered)

    def test_private_term_finds_known_name_in_text(self) -> None:
        known_name = "Jane Doe"
        (self.root / "notes.txt").write_text(
            f"Participant: {known_name}\n",
            encoding="utf-8",
        )
        report = scan_dataset(self.root, ScanPolicy(sensitive_terms=(known_name,)))
        self.assertIn("KNOWN_IDENTIFIER", {finding.code for finding in report.findings})
        self.assertNotIn(known_name, render_json(report) + render_markdown(report))

    def test_private_term_is_masked_in_report_paths(self) -> None:
        known_id = "Jane_Doe"
        (self.root / f"{known_id}_notes.txt").write_text("synthetic\n", encoding="utf-8")
        report = scan_dataset(self.root, ScanPolicy(sensitive_terms=(known_id,)))
        rendered = render_json(report) + render_markdown(report)
        self.assertIn("KNOWN_IDENTIFIER", {finding.code for finding in report.findings})
        self.assertNotIn(known_id, rendered)
        self.assertIn("<redacted:known-identifier-001>_notes.txt", rendered)

    def test_private_term_does_not_match_inside_another_word(self) -> None:
        (self.root / "notes.txt").write_text(
            "The annotations were checked.\n",
            encoding="utf-8",
        )
        report = scan_dataset(self.root, ScanPolicy(sensitive_terms=("Ann",)))
        self.assertNotIn("KNOWN_IDENTIFIER", {finding.code for finding in report.findings})

    def test_masked_identifiers_keep_report_paths_distinct(self) -> None:
        known_ids = ("SC4001_01", "SC4002_01")
        for known_id in known_ids:
            (self.root / f"{known_id}_notes.txt").write_text("synthetic\n", encoding="utf-8")
        report = scan_dataset(self.root, ScanPolicy(sensitive_terms=known_ids))
        self.assertEqual(
            [
                "<redacted:known-identifier-001>_notes.txt",
                "<redacted:known-identifier-002>_notes.txt",
            ],
            report.files_inspected,
        )

    def test_email_in_filename_is_detected_and_masked(self) -> None:
        emails = ("alice.researcher@example.org", "bob.researcher@example.org")
        for email in emails:
            (self.root / email).write_text("synthetic\n", encoding="utf-8")
        report = scan_dataset(self.root)
        rendered = render_json(report) + render_markdown(report)
        self.assertIn("DIRECT_EMAIL", {finding.code for finding in report.findings})
        for email in emails:
            self.assertNotIn(email, rendered)
        self.assertEqual(
            ["<redacted:email-001>", "<redacted:email-002>"],
            [item.path for item in report.skipped_files],
        )

    def test_private_terms_are_deduplicated_case_insensitively(self) -> None:
        policy = ScanPolicy(sensitive_terms=("Jane Doe", "jane doe", "JANE DOE"))
        self.assertEqual(("Jane Doe",), policy.sensitive_terms)

    def test_private_term_can_match_edf_subject_code(self) -> None:
        known_id = "SC4001_01"
        _write_edf(
            self.root / "coded.edf",
            f"X X X {known_id}",
            "Startdate X X X X",
            "01.01.85",
        )
        report = scan_dataset(self.root, ScanPolicy(sensitive_terms=(known_id,)))
        self.assertIn("KNOWN_IDENTIFIER", {finding.code for finding in report.findings})
        self.assertNotIn(known_id, render_json(report))

    def test_private_terms_reject_values_that_are_too_short(self) -> None:
        with self.assertRaises(ValueError):
            ScanPolicy(sensitive_terms=("ab",))

    def test_brainvision_exact_timestamp(self) -> None:
        (self.root / "recording.vmrk").write_text(
            "[Marker Infos]\nMk1=New Segment,,1,1,0,20260722123456789012\n",
            encoding="utf-8",
        )
        self.assertIn("EXACT_RECORDING_DATE", self._codes())

    def test_brainvision_source_filename_is_masked(self) -> None:
        source_name = "Jane_Doe_original_recording.eeg"
        (self.root / "sub-01_task-rest_eeg.vhdr").write_text(
            "[Common Infos]\n"
            f"DataFile={source_name}\n"
            "MarkerFile=sub-01_task-rest_eeg.vmrk\n",
            encoding="utf-8",
        )
        report = scan_dataset(self.root)
        self.assertIn("SOURCE_FILENAME", {finding.code for finding in report.findings})
        self.assertNotIn(source_name, render_json(report) + render_markdown(report))

    def test_structured_json_fields_are_detected_and_masked(self) -> None:
        values = {
            "date_of_birth": "1990-01-02",
            "phone": "+34 600 123 456",
            "participant_name": "Jane Doe",
            "recording_date": "2026-07-22",
        }
        (self.root / "sidecar.json").write_text(json.dumps(values), encoding="utf-8")
        report = scan_dataset(self.root)
        codes = {finding.code for finding in report.findings}
        self.assertTrue(
            {"BIRTH_DATE_FIELD", "DIRECT_PHONE", "SUBJECT_NAME_FIELD", "EXACT_RECORDING_DATE"}
            <= codes
        )
        rendered = render_json(report) + render_markdown(report)
        for value in values.values():
            self.assertNotIn(value, rendered)

    def test_participants_table_fields_are_detected_and_masked(self) -> None:
        values = ("1990-01-02", "Jane Doe", "+34 600 123 456")
        (self.root / "participants.tsv").write_text(
            "participant_id\tdate_of_birth\tname\tphone\n"
            f"sub-01\t{values[0]}\t{values[1]}\t{values[2]}\n",
            encoding="utf-8",
        )
        report = scan_dataset(self.root)
        codes = {finding.code for finding in report.findings}
        self.assertTrue({"BIRTH_DATE_FIELD", "SUBJECT_NAME_FIELD", "DIRECT_PHONE"} <= codes)
        rendered = render_json(report) + render_markdown(report)
        for value in values:
            self.assertNotIn(value, rendered)

    def test_dataset_name_is_not_treated_as_participant_name(self) -> None:
        (self.root / "dataset_description.json").write_text(
            '{"Name": "Synthetic EEG", "BIDSVersion": "1.10.1", '
            '"Authors": [{"full_name": "Researcher Name"}]}\n',
            encoding="utf-8",
        )
        self.assertNotIn("SUBJECT_NAME_FIELD", self._codes())

    def test_malformed_json_is_visible_and_scan_continues(self) -> None:
        (self.root / "broken.json").write_text('{"Name":', encoding="utf-8")
        (self.root / "README").write_text("Synthetic dataset\n", encoding="utf-8")
        report = scan_dataset(self.root)
        self.assertIn("MALFORMED_JSON", {finding.code for finding in report.findings})
        self.assertIn("README", report.files_inspected)

    def test_clean_and_leaky_edf_headers(self) -> None:
        _write_edf(self.root / "clean.edf", "X X X X", "Startdate X X X X", "01.01.85")
        clean_report = scan_dataset(self.root)
        clean_high = [item for item in clean_report.findings if item.severity == "high"]
        self.assertEqual([], clean_high)

        _write_edf(
            self.root / "leaky.edf",
            "P001 F 01-JAN-1990 Jane_Doe",
            "Startdate 22-JUL-2026 Hospital X",
            "22.07.26",
        )
        report = scan_dataset(self.root)
        codes = {finding.code for finding in report.findings if finding.path == "leaky.edf"}
        self.assertTrue(
            {"SUBJECT_FIELD_POPULATED", "SUBJECT_NAME_FIELD", "BIRTH_DATE_FIELD", "EXACT_RECORDING_DATE"}
            <= codes
        )
        rendered = render_json(report)
        self.assertNotIn("Jane_Doe", rendered)
        self.assertNotIn("01-JAN-1990", rendered)

    def test_alphanumeric_edf_subject_code_is_not_treated_as_name(self) -> None:
        _write_edf(
            self.root / "coded.edf",
            "X X X SC4001_01",
            "Startdate X X X X",
            "01.01.85",
        )
        report = scan_dataset(self.root)
        codes = {finding.code for finding in report.findings}
        self.assertIn("SUBJECT_FIELD_POPULATED", codes)
        self.assertNotIn("SUBJECT_NAME_FIELD", codes)

    def test_malformed_edf_does_not_stop_scan(self) -> None:
        (self.root / "broken.edf").write_bytes(b"short")
        (self.root / "README").write_text("Synthetic dataset\n", encoding="utf-8")
        report = scan_dataset(self.root)
        self.assertIn("MALFORMED_HEADER", {finding.code for finding in report.findings})
        self.assertIn("README", report.files_inspected)

    def test_git_lfs_pointer_is_not_reported_as_malformed_edf(self) -> None:
        (self.root / "recording.edf").write_text(
            "version https://git-lfs.github.com/spec/v1\n"
            "oid sha256:0000000000000000000000000000000000000000000000000000000000000000\n"
            "size 123456\n",
            encoding="ascii",
        )
        codes = set(self._codes())
        self.assertIn("GIT_LFS_POINTER", codes)
        self.assertNotIn("MALFORMED_HEADER", codes)

    def test_empty_edf_fixture_is_not_reported_as_malformed(self) -> None:
        (self.root / "recording.edf").write_bytes(b"")
        codes = set(self._codes())
        self.assertIn("EMPTY_PLACEHOLDER", codes)
        self.assertNotIn("MALFORMED_HEADER", codes)

    def test_participant_key_and_backup_are_visible(self) -> None:
        (self.root / "participant_name_key.xlsx").write_bytes(b"synthetic")
        (self.root / "notes.bak").write_text("old", encoding="utf-8")
        codes = set(self._codes())
        self.assertIn("SUBJECT_KEY_FILE", codes)
        self.assertIn("UNEXPECTED_FILE", codes)

    def test_external_symlink_is_not_followed(self) -> None:
        outside = Path(self.temp_dir.name) / "outside.txt"
        outside.write_text("alice@example.org", encoding="utf-8")
        os.symlink(outside, self.root / "external.txt")
        report = scan_dataset(self.root)
        codes = {finding.code for finding in report.findings}
        self.assertIn("EXTERNAL_SYMLINK", codes)
        self.assertNotIn("DIRECT_EMAIL", codes)

    def test_symlink_loop_does_not_stop_scan(self) -> None:
        os.symlink("loop", self.root / "loop")
        (self.root / "README").write_text("Synthetic dataset\n", encoding="utf-8")
        report = scan_dataset(self.root)
        self.assertIn("UNRESOLVED_SYMLINK", {finding.code for finding in report.findings})
        self.assertIn("README", report.files_inspected)

    def test_unreadable_directory_does_not_stop_scan(self) -> None:
        locked = self.root / "locked"
        locked.mkdir()
        (self.root / "README").write_text("Synthetic dataset\n", encoding="utf-8")
        original_iterdir = Path.iterdir

        def controlled_iterdir(path: Path):
            if path.name == locked.name:
                raise PermissionError("synthetic test error")
            return original_iterdir(path)

        with patch.object(Path, "iterdir", controlled_iterdir):
            report = scan_dataset(self.root)
        self.assertIn("UNREADABLE_DIRECTORY", {finding.code for finding in report.findings})
        self.assertIn("README", report.files_inspected)

    def test_unreadable_file_does_not_stop_scan(self) -> None:
        blocked = self.root / "blocked.txt"
        blocked.write_text("synthetic", encoding="utf-8")
        (self.root / "README").write_text("Synthetic dataset\n", encoding="utf-8")
        original_read_bytes = Path.read_bytes

        def controlled_read_bytes(path: Path):
            if path.name == blocked.name:
                raise PermissionError("synthetic test error")
            return original_read_bytes(path)

        with patch.object(Path, "read_bytes", controlled_read_bytes):
            report = scan_dataset(self.root)
        self.assertIn("UNREADABLE_FILE", {finding.code for finding in report.findings})
        self.assertIn("README", report.files_inspected)

    def test_oversized_text_is_reported_and_skipped(self) -> None:
        (self.root / "large.txt").write_text("a" * 20, encoding="utf-8")
        report = scan_dataset(self.root, ScanPolicy(max_text_bytes=10))
        self.assertIn("TEXT_FILE_TOO_LARGE", {finding.code for finding in report.findings})
        self.assertEqual([], report.files_inspected)
        self.assertEqual(["large.txt"], [item.path for item in report.skipped_files])

    def test_output_is_deterministic_and_source_is_unchanged(self) -> None:
        source = self.root / "notes.txt"
        source.write_text("Contact: alice@example.org\n", encoding="utf-8")
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        first = render_json(scan_dataset(self.root))
        second = render_json(scan_dataset(self.root))
        after = hashlib.sha256(source.read_bytes()).hexdigest()
        self.assertEqual(first, second)
        self.assertEqual(before, after)
        self.assertEqual("1", json.loads(first)["schema_version"])

    def test_scan_does_not_open_network_connections(self) -> None:
        (self.root / "dataset_description.json").write_text(
            '{"Name": "Synthetic EEG", "BIDSVersion": "1.10.1"}\n',
            encoding="utf-8",
        )
        with patch.object(socket, "socket", side_effect=AssertionError("network access")):
            report = scan_dataset(self.root)
        self.assertEqual(["dataset_description.json"], report.files_inspected)

    def test_markdown_report_escapes_filename_markup(self) -> None:
        filename = "notes|<script>.txt"
        (self.root / filename).write_text("Contact: alice@example.org\n", encoding="utf-8")
        rendered = render_markdown(scan_dataset(self.root))
        self.assertNotIn("<script>", rendered)
        self.assertIn("notes\\|&lt;script&gt;.txt", rendered)

    def test_cli_writes_reports_and_returns_finding_status(self) -> None:
        (self.root / "notes.txt").write_text("Contact: alice@example.org\n", encoding="utf-8")
        output = Path(self.temp_dir.name) / "reports"
        with redirect_stdout(io.StringIO()):
            code = main(
                [
                    "scan",
                    str(self.root),
                    "--json",
                    str(output / "audit.json"),
                    "--markdown",
                    str(output / "audit.md"),
                ]
            )
        self.assertEqual(1, code)
        self.assertTrue((output / "audit.json").is_file())
        self.assertTrue((output / "audit.md").is_file())

    def test_cli_handles_report_write_error(self) -> None:
        (self.root / "README").write_text("Synthetic dataset\n", encoding="utf-8")
        stderr = io.StringIO()
        with (
            patch.object(Path, "write_text", side_effect=PermissionError("synthetic")),
            redirect_stdout(io.StringIO()),
            redirect_stderr(stderr),
        ):
            code = main(["scan", str(self.root), "--json", "audit.json"])
        self.assertEqual(2, code)
        self.assertIn("could not write report (PermissionError)", stderr.getvalue())

    def test_cli_reads_private_term_file(self) -> None:
        known_name = "Jane Doe"
        (self.root / "notes.txt").write_text(known_name, encoding="utf-8")
        term_file = Path(self.temp_dir.name) / "private_terms.txt"
        term_file.write_text(f"# one value per line\n{known_name}\n", encoding="utf-8")
        report_path = Path(self.temp_dir.name) / "audit.json"
        with redirect_stdout(io.StringIO()):
            code = main(
                [
                    "scan",
                    str(self.root),
                    "--sensitive-terms",
                    str(term_file),
                    "--json",
                    str(report_path),
                ]
            )
        self.assertEqual(1, code)
        rendered = report_path.read_text(encoding="utf-8")
        self.assertIn("KNOWN_IDENTIFIER", rendered)
        self.assertNotIn(known_name, rendered)


if __name__ == "__main__":
    unittest.main()
