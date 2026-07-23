from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import csv
from datetime import date, datetime, timezone
import hashlib
from importlib import metadata
import io
import json
from numbers import Number
import os
import socket
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile

from neurodata_security_audit.cli import main
from neurodata_security_audit.containers import inspect_archive
from neurodata_security_audit.html_report import render_html
from neurodata_security_audit.models import ManifestEntry, ScanReport
from neurodata_security_audit.readers import (
    FormatReaderUnavailable,
    inspect_eeglab_metadata,
    inspect_mne_info,
)
from neurodata_security_audit.reporting import render_json, render_markdown
from neurodata_security_audit.scanner import (
    ScanPolicy,
    _release_collision_findings,
    _tree_signature,
    scan_dataset,
)
from neurodata_security_audit.structured import inspect_delimited


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
        self.assertIn(
            "sub-01/eeg/sub-01_task-rest_eeg.eeg",
            [item.path for item in report.skipped_files],
        )

    def test_reviewer_demo_matches_the_documented_result(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        demo = project_root / "examples" / "reviewer_demo"
        policy = ScanPolicy(sensitive_terms=("Jane Doe", "SITEA-0042"))
        report = scan_dataset(demo, policy)
        self.assertEqual(
            {
                "files_inspected": 5,
                "files_skipped": 2,
                "entries_total": 9,
                "manifest_files": 7,
                "manifest_recheck_passed": True,
                "release_tree_recheck_passed": True,
                "container_members": 0,
                "references_checked": 2,
                "references_valid": 1,
                "fully_inspected_metadata": 5,
                "header_or_structure_only": 2,
                "payload_not_opened": 1,
                "unsupported_manual_review": 1,
                "not_traversed": 0,
                "findings_high": 6,
                "findings_review": 5,
                "findings_info": 0,
            },
            report.to_dict()["summary"],
        )
        rendered = render_json(report) + render_markdown(report)
        for value in (
            "Jane Doe",
            "SITEA-0042",
            "study.contact@example.org",
            "/Users/reviewer/private/SITEA-0042.csv",
            "20260722123456789012",
        ):
            self.assertNotIn(value, rendered)

    def test_direct_values_are_detected_and_masked(self) -> None:
        email = "alice.researcher@example.org"
        phone = "+1 202 555 0199"
        local_path = "/Users/alice/private/participants.csv"
        token = "ghp_" + "A" * 32
        (self.root / "notes.txt").write_text(
            f"Contact: {email}\nPhone: {phone}\nSource: {local_path}\nToken: {token}\n",
            encoding="utf-8",
        )

        report = scan_dataset(self.root)
        codes = {finding.code for finding in report.findings}
        self.assertTrue(
            {"DIRECT_EMAIL", "DIRECT_PHONE", "LOCAL_PATH", "POTENTIAL_SECRET"}
            <= codes
        )

        rendered = render_json(report) + render_markdown(report)
        for secret in (email, phone, local_path, token):
            self.assertNotIn(secret, rendered)

    def test_network_and_machine_values_are_detected_and_masked(self) -> None:
        values = (
            r"\\acquisition-server\eeg\sub-01",
            "/mnt/lab/eeg/sub-01",
            "acquisition-pc.local",
            "10.20.30.40",
            "AA:BB:CC:DD:EE:FF",
            "lab.operator",
        )
        (self.root / "runtime.log").write_text(
            "UNC path: \\\\acquisition-server\\eeg\\sub-01\n"
            "Data path: /mnt/lab/eeg/sub-01\n"
            "Hostname: acquisition-pc.local\n"
            "IP address: 10.20.30.40\n"
            "MAC address: AA:BB:CC:DD:EE:FF\n"
            "Username: lab.operator\n",
            encoding="utf-8",
        )
        report = scan_dataset(self.root)
        codes = {finding.code for finding in report.findings}
        self.assertTrue(
            {
                "NETWORK_PATH",
                "LOCAL_HOSTNAME",
                "NETWORK_ADDRESS",
                "DEVICE_ADDRESS",
                "ACCOUNT_NAME",
            }
            <= codes
        )
        rendered = render_json(report) + render_markdown(report)
        for value in values:
            self.assertNotIn(value, rendered)

    def test_credentials_and_database_url_are_detected_and_masked(self) -> None:
        database_url = "postgresql://" + "dbuser:db-password@internal-db/study"
        values = ("correct-horse-battery", database_url)
        (self.root / "settings.toml").write_text(
            'password = "correct-horse-battery"\n'
            f'database_url = "{database_url}"\n',
            encoding="utf-8",
        )
        report = scan_dataset(self.root)
        secret_findings = [
            finding for finding in report.findings if finding.code == "POTENTIAL_SECRET"
        ]
        self.assertGreaterEqual(len(secret_findings), 2)
        rendered = render_json(report) + render_markdown(report)
        for value in values:
            self.assertNotIn(value, rendered)

    def test_common_service_tokens_and_basic_auth_are_masked(self) -> None:
        values = (
            "glpat-" + "A" * 28,
            "xoxb-" + "1" * 24,
            "AIza" + "A" * 35,
            "sk-proj-" + "B" * 24,
            "eyJ" + "a" * 12 + "." + "b" * 16 + "." + "c" * 16,
            "https://" + "lab-user:private-password@internal.example.org/api",
        )
        (self.root / ".env.service").write_text(
            "\n".join(values) + "\n",
            encoding="utf-8",
        )
        report = scan_dataset(self.root)
        findings = [item for item in report.findings if item.code == "POTENTIAL_SECRET"]
        self.assertEqual(len(values), len(findings))
        rendered = render_json(report) + render_markdown(report)
        for value in values:
            self.assertNotIn(value, rendered)

    def test_short_token_examples_are_not_treated_as_credentials(self) -> None:
        (self.root / "README").write_text(
            "Examples: glpat-example, xoxb-example, sk-example and eyJ.demo.value\n",
            encoding="utf-8",
        )
        self.assertNotIn("POTENTIAL_SECRET", set(self._codes()))

    def test_source_config_and_notebook_files_are_scanned(self) -> None:
        (self.root / "pipeline.py").write_text(
            'source_path = "/data/private/eeg"\n',
            encoding="utf-8",
        )
        notebook = {
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["hostname: acquisition-pc\n"],
                    "outputs": [],
                    "metadata": {},
                    "execution_count": None,
                }
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        (self.root / "analysis.ipynb").write_text(
            json.dumps(notebook),
            encoding="utf-8",
        )
        report = scan_dataset(self.root)
        self.assertEqual(
            ["analysis.ipynb", "pipeline.py"],
            report.files_inspected,
        )
        codes = {finding.code for finding in report.findings}
        self.assertIn("NETWORK_PATH", codes)
        self.assertIn("LOCAL_HOSTNAME", codes)

    def test_sensitive_os_and_editor_files_are_visible(self) -> None:
        (self.root / ".env").write_text("EXAMPLE_MODE=true\n", encoding="utf-8")
        (self.root / ".env.production").write_text(
            "api_key=synthetic-secret-value\n",
            encoding="utf-8",
        )
        (self.root / "id_rsa").write_text(
            "-----BEGIN " + "OPENSSH PRIVATE KEY-----\nsynthetic\n",
            encoding="utf-8",
        )
        (self.root / "private.pem").write_text(
            "-----BEGIN " + "PRIVATE KEY-----\nsynthetic\n",
            encoding="utf-8",
        )
        (self.root / ".DS_Store").write_bytes(b"synthetic")
        (self.root / "notes.swp").write_bytes(b"synthetic")
        codes = set(self._codes())
        self.assertIn("SENSITIVE_CONFIG_FILE", codes)
        self.assertIn("POTENTIAL_SECRET", codes)
        self.assertIn("OS_METADATA_FILE", codes)
        self.assertIn("UNEXPECTED_FILE", codes)
        report = scan_dataset(self.root)
        self.assertIn(".env.production", report.files_inspected)
        self.assertIn("private.pem", report.files_inspected)

    def test_case_variants_of_sensitive_files_and_directories_are_visible(self) -> None:
        token = "ghp_" + "A" * 32
        (self.root / ".ENV").write_text(f"api_key={token}\n", encoding="utf-8")
        git_dir = self.root / ".GIT"
        git_dir.mkdir()
        (git_dir / "config").write_text(
            "contact = hidden@example.org\n",
            encoding="utf-8",
        )

        report = scan_dataset(self.root)
        codes = {item.code for item in report.findings}
        self.assertTrue(
            {"SENSITIVE_CONFIG_FILE", "POTENTIAL_SECRET", "UNEXPECTED_DIRECTORY"}
            <= codes
        )
        self.assertIn(".ENV", report.files_inspected)
        self.assertIn(".GIT", [item.path for item in report.skipped_files])
        rendered = render_json(report) + render_markdown(report)
        self.assertNotIn(token, rendered)
        self.assertNotIn("hidden@example.org", rendered)

    def test_patch_and_editor_backup_files_are_visible(self) -> None:
        private_path = "/Users/alice/private/subject-key.tsv"
        (self.root / "changes.patch").write_text(
            f"old_path={private_path}\n",
            encoding="utf-8",
        )
        (self.root / "notes.txt~").write_text("old copy\n", encoding="utf-8")
        report = scan_dataset(self.root)
        codes = {item.code for item in report.findings}
        self.assertIn("UNEXPECTED_FILE", codes)
        self.assertIn("LOCAL_PATH", codes)
        self.assertIn("changes.patch", report.files_inspected)
        self.assertNotIn(private_path, render_json(report) + render_markdown(report))

    def test_common_archive_and_backup_names_are_visible(self) -> None:
        for name in (
            "old-release.tar.gz",
            "old-release.tgz",
            "participants.backup",
            "notes.save",
        ):
            (self.root / name).write_bytes(b"synthetic")
        report = scan_dataset(self.root)
        unexpected = [item for item in report.findings if item.code == "UNEXPECTED_FILE"]
        self.assertEqual(4, len(unexpected))

    def test_zip_member_table_is_checked_without_opening_payloads(self) -> None:
        archive_path = self.root / "release.zip"
        secret = "ghp_" + "A" * 32
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("safe/sub-01.txt", secret)
            archive.writestr("../private/Jane Doe.txt", b"identifier")
            archive.writestr("nested/data.tar.gz", b"nested archive payload")

        with patch.object(
            zipfile.ZipFile,
            "open",
            side_effect=AssertionError("archive payload must not be opened"),
        ):
            report = scan_dataset(
                self.root,
                ScanPolicy(sensitive_terms=("Jane Doe",)),
            )

        self.assertEqual(3, len(report.container_members))
        codes = {item.code for item in report.findings}
        self.assertTrue(
            {
                "ARCHIVE_MEMBER_PATH_TRAVERSAL",
                "KNOWN_IDENTIFIER",
                "NESTED_ARCHIVE",
            }
            <= codes
        )
        self.assertNotIn("POTENTIAL_SECRET", codes)
        entry = next(item for item in report.coverage if item.path == "release.zip")
        self.assertEqual("header_or_structure_only", entry.status)
        rendered = render_json(report) + render_markdown(report)
        self.assertNotIn(secret, rendered)
        self.assertNotIn("Jane Doe", rendered)

    def test_tar_links_are_listed_but_not_followed_or_extracted(self) -> None:
        archive_path = self.root / "release.tar"
        with tarfile.open(archive_path, "w") as archive:
            directory = tarfile.TarInfo("safe")
            directory.type = tarfile.DIRTYPE
            archive.addfile(directory)
            link = tarfile.TarInfo("safe/external-link")
            link.type = tarfile.SYMTYPE
            link.linkname = "../../private/participant.tsv"
            archive.addfile(link)

        with (
            patch.object(
                tarfile.TarFile,
                "extract",
                side_effect=AssertionError("archive members must not be extracted"),
            ),
            patch.object(
                tarfile.TarFile,
                "extractall",
                side_effect=AssertionError("archive members must not be extracted"),
            ),
        ):
            report = scan_dataset(self.root)

        codes = {item.code for item in report.findings}
        self.assertIn("ARCHIVE_SPECIAL_MEMBER", codes)
        self.assertIn("ARCHIVE_LINK_PATH_TRAVERSAL", codes)
        member_type = {
            item.member_path: item.member_type for item in report.container_members
        }
        self.assertEqual("symlink", member_type["safe/external-link"])

    def test_encrypted_zip_is_an_explicit_high_severity_boundary(self) -> None:
        archive_path = self.root / "release.zip"
        archive_path.write_bytes(b"synthetic-zip-placeholder")
        info = SimpleNamespace(
            filename="data/sub-01.txt",
            flag_bits=1,
            external_attr=0,
            file_size=100,
            compress_size=80,
            is_dir=lambda: False,
        )

        class FakeZip:
            def __enter__(self):
                return self

            def __exit__(self, *args: object) -> None:
                return None

            @staticmethod
            def infolist():
                return [info]

        with patch(
            "neurodata_security_audit.containers.zipfile.ZipFile",
            return_value=FakeZip(),
        ):
            report = scan_dataset(self.root)

        self.assertIn(
            "ENCRYPTED_ARCHIVE",
            {item.code for item in report.findings},
        )
        entry = next(item for item in report.coverage if item.path == "release.zip")
        self.assertEqual("unsupported_manual_review", entry.status)
        self.assertTrue(report.container_members[0].encrypted)

    def test_zip_expansion_risk_uses_member_metadata_only(self) -> None:
        archive_path = self.root / "release.zip"
        archive_path.write_bytes(b"synthetic-zip-placeholder")
        info = SimpleNamespace(
            filename="data/large.bin",
            flag_bits=0,
            external_attr=0,
            file_size=200 * 1024 * 1024,
            compress_size=1,
            is_dir=lambda: False,
        )

        class FakeZip:
            def __enter__(self):
                return self

            def __exit__(self, *args: object) -> None:
                return None

            @staticmethod
            def infolist():
                return [info]

        with patch(
            "neurodata_security_audit.containers.zipfile.ZipFile",
            return_value=FakeZip(),
        ):
            report = scan_dataset(self.root)

        self.assertIn(
            "ARCHIVE_EXPANSION_RISK",
            {item.code for item in report.findings},
        )

    def test_archive_member_limit_fails_visibly(self) -> None:
        archive_path = self.root / "release.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("first.txt", b"one")
            archive.writestr("second.txt", b"two")

        result = inspect_archive(
            archive_path,
            "release.zip",
            max_members=1,
        )

        self.assertFalse(result.complete)
        self.assertEqual(1, len(result.members))
        self.assertIn(
            "ARCHIVE_MEMBER_LIMIT",
            {item.code for item in result.findings},
        )

    def test_corrupt_archive_fails_visibly(self) -> None:
        (self.root / "release.zip").write_bytes(b"not a zip")

        report = scan_dataset(self.root)

        self.assertIn(
            "ARCHIVE_UNREADABLE",
            {item.code for item in report.findings},
        )
        entry = next(item for item in report.coverage if item.path == "release.zip")
        self.assertEqual("unsupported_manual_review", entry.status)

    def test_sensitive_configuration_directory_is_visible_and_scanned(self) -> None:
        secret = "AKIA" + "A" * 16
        private_directory = self.root / ".aws"
        private_directory.mkdir()
        (private_directory / "credentials").write_text(
            f"aws_access_key_id={secret}\n",
            encoding="utf-8",
        )
        report = scan_dataset(self.root)
        codes = {item.code for item in report.findings}
        self.assertIn("SENSITIVE_CONFIG_DIRECTORY", codes)
        self.assertIn("SENSITIVE_CONFIG_FILE", codes)
        self.assertIn("POTENTIAL_SECRET", codes)
        self.assertIn(".aws/credentials", report.files_inspected)
        self.assertNotIn(secret, render_json(report) + render_markdown(report))

    def test_ordinary_release_paths_are_not_treated_as_remnants(self) -> None:
        github = self.root / ".github" / "workflows"
        github.mkdir(parents=True)
        (github / "checks.yml").write_text("name: checks\n", encoding="utf-8")
        (self.root / "recording.fif.gz").write_bytes(b"")
        (self.root / "participants.tsv").write_text(
            "participant_id\tage\nsub-01\t34\n",
            encoding="utf-8",
        )
        codes = set(self._codes())
        self.assertNotIn("UNEXPECTED_DIRECTORY", codes)
        self.assertNotIn("UNEXPECTED_FILE", codes)
        self.assertNotIn("SENSITIVE_CONFIG_DIRECTORY", codes)
        self.assertNotIn("SUBJECT_KEY_FILE", codes)

    def test_sensitive_config_evidence_does_not_repeat_a_known_id(self) -> None:
        known_id = "SITEA-0042"
        (self.root / f".env.{known_id}").write_text(
            "EXAMPLE_MODE=true\n",
            encoding="utf-8",
        )
        report = scan_dataset(self.root, ScanPolicy(sensitive_terms=(known_id,)))
        rendered = render_json(report) + render_markdown(report)
        self.assertIn("SENSITIVE_CONFIG_FILE", {item.code for item in report.findings})
        self.assertNotIn(known_id, rendered)

    def test_structured_technical_fields_are_detected_and_masked(self) -> None:
        values = {
            "hostname": "acquisition-pc",
            "ipAddress": "10.20.30.40",
            "macAddress": "AA:BB:CC:DD:EE:FF",
            "username": "lab.operator",
        }
        (self.root / "runtime.json").write_text(
            json.dumps({"runtime": values}),
            encoding="utf-8",
        )
        report = scan_dataset(self.root)
        codes = {finding.code for finding in report.findings}
        self.assertTrue(
            {"LOCAL_HOSTNAME", "NETWORK_ADDRESS", "DEVICE_ADDRESS", "ACCOUNT_NAME"}
            <= codes
        )
        rendered = render_json(report) + render_markdown(report)
        for value in values.values():
            self.assertNotIn(value, rendered)

    def test_public_url_and_placeholder_secret_are_not_flagged(self) -> None:
        (self.root / "README").write_text(
            "Documentation: https://example.org/data/demo\n"
            "Password: n/a\n"
            "Hostname: localhost\n"
            "IP address: 127.0.0.1\n",
            encoding="utf-8",
        )
        (self.root / "runtime.json").write_text(
            json.dumps(
                {
                    "hostname": "localhost",
                    "ipAddress": "127.0.0.1",
                    "username": "unknown",
                }
            ),
            encoding="utf-8",
        )
        codes = set(self._codes())
        self.assertNotIn("NETWORK_PATH", codes)
        self.assertNotIn("POTENTIAL_SECRET", codes)
        self.assertNotIn("LOCAL_HOSTNAME", codes)
        self.assertNotIn("NETWORK_ADDRESS", codes)
        self.assertNotIn("ACCOUNT_NAME", codes)

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

    def test_phone_personal_id_and_secret_in_filenames_are_masked(self) -> None:
        values = (
            "phone_+34600123456",
            "mrn_MRN928374",
            "ghp_" + "A" * 32,
        )
        for value in values:
            (self.root / f"{value}.txt").write_text("synthetic\n", encoding="utf-8")
        report = scan_dataset(self.root)
        codes = {finding.code for finding in report.findings}
        self.assertTrue(
            {"DIRECT_PHONE", "DIRECT_PERSONAL_ID", "POTENTIAL_SECRET"} <= codes
        )
        rendered = render_json(report) + render_markdown(report)
        for value in values:
            self.assertNotIn(value, rendered)
        self.assertIn("<redacted:sensitive-path-", rendered)

    def test_birth_and_recording_dates_in_paths_are_detected_and_masked(self) -> None:
        values = ("dob_1990-01-02", "recording_date_2026-07-22")
        for value in values:
            (self.root / f"{value}.txt").write_text("synthetic\n", encoding="utf-8")
        report = scan_dataset(self.root)
        codes = {item.code for item in report.findings}
        self.assertIn("BIRTH_DATE_FIELD", codes)
        self.assertIn("EXACT_RECORDING_DATE", codes)
        rendered = render_json(report) + render_markdown(report)
        for value in values:
            self.assertNotIn(value, rendered)

    def test_local_path_embedded_in_release_path_is_masked(self) -> None:
        private_directory = self.root / "export" / "Users" / "alice" / "private"
        private_directory.mkdir(parents=True)
        (private_directory / "notes.txt").write_text("synthetic\n", encoding="utf-8")

        report = scan_dataset(self.root)
        self.assertIn("LOCAL_PATH", {item.code for item in report.findings})
        rendered = render_json(report) + render_markdown(report)
        self.assertNotIn("/Users/alice/private", rendered)

    def test_empty_sensitive_directory_names_are_checked_and_masked(self) -> None:
        known_name = "Jane_Doe"
        (self.root / known_name).mkdir()
        (self.root / "participant_identity_mapping").mkdir()

        report = scan_dataset(
            self.root,
            ScanPolicy(sensitive_terms=(known_name,)),
        )
        codes = {item.code for item in report.findings}
        self.assertIn("KNOWN_IDENTIFIER", codes)
        self.assertIn("SUBJECT_KEY_FILE", codes)
        rendered = render_json(report) + render_markdown(report)
        self.assertNotIn(known_name, rendered)

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

    def test_brainvision_internal_references_are_checked(self) -> None:
        header = self.root / "sub-01_task-rest_eeg.vhdr"
        marker = self.root / "sub-01_task-rest_eeg.vmrk"
        signal = self.root / "sub-01_task-rest_eeg.eeg"
        header.write_text(
            "[Common Infos]\n"
            f"DataFile={signal.name}\n"
            f"MarkerFile={marker.name}\n",
            encoding="utf-8",
        )
        marker.write_text(
            "[Common Infos]\n"
            f"DataFile={signal.name}\n",
            encoding="utf-8",
        )
        signal.write_bytes(b"synthetic signal")

        report = scan_dataset(self.root)

        self.assertEqual(3, len(report.references))
        self.assertEqual(
            {"valid_internal"},
            {item.status for item in report.references},
        )
        self.assertNotIn(
            "MISSING_DATA_REFERENCE",
            {item.code for item in report.findings},
        )

    def test_brainvision_external_case_and_symlink_references_are_visible(self) -> None:
        case_target = self.root / "Signal.EEG"
        case_target.write_bytes(b"synthetic signal")
        real_target = self.root / "real.eeg"
        real_target.write_bytes(b"synthetic signal")
        symlink = self.root / "linked.eeg"
        symlink.symlink_to(real_target)
        header = self.root / "recording.vhdr"
        header.write_text(
            "[Common Infos]\n"
            "DataFile=signal.eeg\n"
            "MarkerFile=linked.eeg\n"
            "DataFile=../../private/source.eeg\n",
            encoding="utf-8",
        )

        report = scan_dataset(self.root)

        statuses = {item.status for item in report.references}
        self.assertTrue(
            {"case_mismatch", "through_symlink", "external"} <= statuses
        )
        codes = {item.code for item in report.findings}
        self.assertTrue(
            {
                "CASE_MISMATCHED_REFERENCE",
                "REFERENCE_THROUGH_SYMLINK",
                "EXTERNAL_DATA_REFERENCE",
            }
            <= codes
        )

    def test_bids_intended_for_reference_is_resolved_from_dataset_root(self) -> None:
        target = self.root / "sub-01" / "func" / "sub-01_task-rest_bold.nii.gz"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"synthetic image")
        sidecar = self.root / "sub-01" / "fmap" / "sub-01_phasediff.json"
        sidecar.parent.mkdir(parents=True)
        sidecar.write_text(
            json.dumps(
                {
                    "IntendedFor": [
                        "bids::sub-01/func/sub-01_task-rest_bold.nii.gz"
                    ]
                }
            ),
            encoding="utf-8",
        )

        with patch(
            "neurodata_security_audit.scanner.inspect_nifti_metadata",
            return_value=[],
        ):
            report = scan_dataset(self.root)

        reference = next(
            item for item in report.references if item.source_path.endswith(".json")
        )
        self.assertEqual("valid_internal", reference.status)
        self.assertEqual(
            "sub-01/func/sub-01_task-rest_bold.nii.gz",
            reference.target,
        )

    def test_missing_bids_intended_for_reference_is_visible(self) -> None:
        sidecar = self.root / "sub-01" / "fmap" / "sub-01_phasediff.json"
        sidecar.parent.mkdir(parents=True)
        sidecar.write_text(
            json.dumps({"IntendedFor": ["bids::sub-01/func/missing.nii.gz"]}),
            encoding="utf-8",
        )

        report = scan_dataset(self.root)

        self.assertIn(
            "MISSING_DATA_REFERENCE",
            {item.code for item in report.findings},
        )
        reference = report.references[0]
        self.assertEqual("missing", reference.status)
        self.assertEqual("<missing-reference>", reference.target)

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

    def test_camel_case_json_fields_are_detected_and_masked(self) -> None:
        values = {
            "DateOfBirth": "1990-01-02",
            "PhoneNumber": "+34 600 123 456",
            "PatientName": "Jane Doe",
            "AcquisitionDateTime": "2026-07-22T10:30:00",
        }
        (self.root / "sidecar.json").write_text(
            json.dumps(values),
            encoding="utf-8",
        )
        report = scan_dataset(self.root)
        codes = {finding.code for finding in report.findings}
        self.assertTrue(
            {
                "BIRTH_DATE_FIELD",
                "DIRECT_PHONE",
                "SUBJECT_NAME_FIELD",
                "EXACT_RECORDING_DATE",
            }
            <= codes
        )
        rendered = render_json(report) + render_markdown(report)
        for value in values.values():
            self.assertNotIn(value, rendered)

    def test_common_name_field_aliases_are_detected_and_masked(self) -> None:
        values = {
            "givenName": "Jane",
            "familyName": "Doe",
            "forename": "Alice",
            "surname": "Smith",
        }
        (self.root / "participants.json").write_text(
            json.dumps({"participant": values}),
            encoding="utf-8",
        )
        report = scan_dataset(self.root)
        findings = [
            item for item in report.findings if item.code == "SUBJECT_NAME_FIELD"
        ]
        self.assertEqual(len(values), len(findings))
        rendered = render_json(report) + render_markdown(report)
        for value in values.values():
            self.assertNotIn(value, rendered)

    def test_nested_participant_name_is_detected_but_author_name_is_not(self) -> None:
        document = {
            "participant": {"fullName": "Jane Doe"},
            "Authors": [{"name": "Researcher Name"}],
        }
        (self.root / "sidecar.json").write_text(
            json.dumps(document),
            encoding="utf-8",
        )
        report = scan_dataset(self.root)
        name_findings = [
            finding
            for finding in report.findings
            if finding.code == "SUBJECT_NAME_FIELD"
        ]
        self.assertEqual(1, len(name_findings))
        self.assertEqual("JSON field participant.full_name", name_findings[0].location)
        rendered = render_json(report) + render_markdown(report)
        self.assertNotIn("Jane Doe", rendered)

    def test_untrusted_json_keys_are_not_repeated_in_locations(self) -> None:
        private_key = "Jane_Doe_MRN928374"
        birth_date = "1990-01-02"
        document = {"participant": {private_key: {"dateOfBirth": birth_date}}}
        (self.root / "sidecar.json").write_text(
            json.dumps(document),
            encoding="utf-8",
        )

        report = scan_dataset(self.root)
        finding = next(
            item for item in report.findings if item.code == "BIRTH_DATE_FIELD"
        )
        self.assertEqual(
            "JSON field participant.<field>.date_of_birth",
            finding.location,
        )
        rendered = render_json(report) + render_markdown(report)
        self.assertNotIn(private_key, rendered)
        self.assertNotIn(birth_date, rendered)

    def test_structured_personal_ids_addresses_and_linked_ids_are_masked(self) -> None:
        values = {
            "medicalRecordNumber": "MRN-928374",
            "streetAddress": "12 Example Street",
            "patientId": "HOSP-0042",
        }
        document = {
            "patient": values,
            "Authors": [{"name": "Researcher Name", "address": "University Lab"}],
        }
        (self.root / "sidecar.json").write_text(
            json.dumps(document),
            encoding="utf-8",
        )
        report = scan_dataset(self.root)
        codes = {finding.code for finding in report.findings}
        self.assertIn("DIRECT_PERSONAL_ID", codes)
        self.assertIn("POSTAL_ADDRESS_FIELD", codes)
        self.assertIn("LINKED_SOURCE_ID", codes)
        address_findings = [
            finding
            for finding in report.findings
            if finding.code == "POSTAL_ADDRESS_FIELD"
        ]
        self.assertEqual(1, len(address_findings))
        rendered = render_json(report) + render_markdown(report)
        for value in values.values():
            self.assertNotIn(value, rendered)
        self.assertNotIn("University Lab", rendered)

    def test_additional_direct_id_fields_are_detected_and_masked(self) -> None:
        values = {
            "driverLicenseNumber": "D-9283746",
            "taxpayerId": "TAX-9283746",
            "healthInsuranceId": "INS-9283746",
            "personalNumber": "PN-9283746",
        }
        (self.root / "participants.json").write_text(
            json.dumps({"participant": values}),
            encoding="utf-8",
        )
        report = scan_dataset(self.root)
        findings = [
            item for item in report.findings if item.code == "DIRECT_PERSONAL_ID"
        ]
        self.assertEqual(len(values), len(findings))
        rendered = render_json(report) + render_markdown(report)
        for value in values.values():
            self.assertNotIn(value, rendered)

    def test_bids_scans_acquisition_time_is_reviewed_and_masked(self) -> None:
        acquisition_time = "2026-07-22T10:30:00"
        (self.root / "sub-01_scans.tsv").write_text(
            f"filename\tacq_time\neeg/sub-01_task-rest_eeg.edf\t{acquisition_time}\n",
            encoding="utf-8",
        )
        report = scan_dataset(self.root)
        self.assertIn("EXACT_RECORDING_DATE", {finding.code for finding in report.findings})
        rendered = render_json(report) + render_markdown(report)
        self.assertNotIn(acquisition_time, rendered)

    def test_labelled_text_personal_fields_are_detected_and_masked(self) -> None:
        values = (
            "MRN-928374",
            "12 Example Street",
            "HOSP-0042",
        )
        (self.root / "notes.txt").write_text(
            "Medical record number: MRN-928374\n"
            "Patient address: 12 Example Street\n"
            "Original subject ID: HOSP-0042\n",
            encoding="utf-8",
        )
        report = scan_dataset(self.root)
        codes = {finding.code for finding in report.findings}
        self.assertTrue(
            {"DIRECT_PERSONAL_ID", "POSTAL_ADDRESS_FIELD", "LINKED_SOURCE_ID"}
            <= codes
        )
        rendered = render_json(report) + render_markdown(report)
        for value in values:
            self.assertNotIn(value, rendered)

    def test_standard_bids_participant_id_is_not_treated_as_source_id(self) -> None:
        (self.root / "participants.tsv").write_text(
            "participant_id\tage\nsub-01\t34\n",
            encoding="utf-8",
        )
        self.assertNotIn("LINKED_SOURCE_ID", self._codes())

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
            '"Authors": [{"name": "Researcher Name", '
            '"full_name": "Researcher Name"}]}\n',
            encoding="utf-8",
        )
        self.assertNotIn("SUBJECT_NAME_FIELD", self._codes())

    def test_malformed_json_is_visible_and_scan_continues(self) -> None:
        (self.root / "broken.json").write_text('{"Name":', encoding="utf-8")
        (self.root / "README").write_text("Synthetic dataset\n", encoding="utf-8")
        report = scan_dataset(self.root)
        self.assertIn("MALFORMED_JSON", {finding.code for finding in report.findings})
        self.assertIn("README", report.files_inspected)

    def test_malformed_table_is_visible(self) -> None:
        with patch(
            "neurodata_security_audit.structured.csv.DictReader",
            side_effect=csv.Error("synthetic test error"),
        ):
            findings = inspect_delimited(
                "participant_id\tage\nsub-01\t34\n",
                "participants.tsv",
                "\t",
            )
        self.assertEqual(["MALFORMED_TABLE"], [item.code for item in findings])
        self.assertNotIn(
            "synthetic test error",
            findings[0].evidence + findings[0].message + findings[0].location,
        )

    def test_xml_personal_and_device_fields_are_detected_and_masked(self) -> None:
        values = (
            "Jane",
            "Doe",
            "HOSP-0042",
            "1990-01-02",
            "2026-07-22T10:30:00Z",
            "Acquisition Operator",
            "EGI-300-928374",
        )
        mff = self.root / "recording.mff"
        mff.mkdir()
        (mff / "subject.xml").write_text(
            "<recording><subject><firstName>Jane</firstName><lastName>Doe</lastName>"
            "<id>HOSP-0042</id><dateOfBirth>1990-01-02</dateOfBirth></subject>"
            "<recordTime>2026-07-22T10:30:00Z</recordTime>"
            "<operator>Acquisition Operator</operator>"
            "<device><serialNumber>EGI-300-928374</serialNumber></device></recording>",
            encoding="utf-8",
        )
        with patch(
            "neurodata_security_audit.scanner.inspect_mne_format",
            side_effect=FormatReaderUnavailable("synthetic"),
        ):
            report = scan_dataset(self.root)
        codes = {finding.code for finding in report.findings}
        self.assertTrue(
            {
                "SUBJECT_NAME_FIELD",
                "LINKED_SOURCE_ID",
                "BIRTH_DATE_FIELD",
                "EXACT_RECORDING_DATE",
                "PERSONNEL_FIELD",
                "DEVICE_IDENTIFIER",
                "FORMAT_READER_UNAVAILABLE",
            }
            <= codes
        )
        rendered = render_json(report) + render_markdown(report)
        for value in values:
            self.assertNotIn(value, rendered)

    def test_untrusted_xml_tags_are_not_repeated_in_locations(self) -> None:
        private_tag = "Jane_Doe_MRN928374"
        birth_date = "1990-01-02"
        mff = self.root / "recording.mff"
        mff.mkdir()
        (mff / "subject.xml").write_text(
            f"<subject><{private_tag}><dateOfBirth>{birth_date}</dateOfBirth>"
            f"</{private_tag}></subject>",
            encoding="utf-8",
        )

        with patch(
            "neurodata_security_audit.scanner.inspect_mne_format",
            side_effect=FormatReaderUnavailable("synthetic"),
        ):
            report = scan_dataset(self.root)
        finding = next(
            item for item in report.findings if item.code == "BIRTH_DATE_FIELD"
        )
        self.assertEqual(
            "XML field subject.<field>.date_of_birth",
            finding.location,
        )
        rendered = render_json(report) + render_markdown(report)
        self.assertNotIn(private_tag, rendered)
        self.assertNotIn(birth_date, rendered)

    def test_xml_document_type_is_not_parsed(self) -> None:
        (self.root / "metadata.xml").write_text(
            '<!DOCTYPE root [<!ENTITY name "Jane Doe">]><root>&name;</root>',
            encoding="utf-8",
        )
        codes = set(self._codes())
        self.assertIn("UNSAFE_XML_DECLARATION", codes)
        self.assertNotIn("MALFORMED_XML", codes)

    def test_mff_dynamic_patient_fields_use_their_labels(self) -> None:
        values = (
            "Jane",
            "Doe",
            "HOSP-0042",
            "Participant called after recording",
        )
        mff = self.root / "recording.mff"
        mff.mkdir()
        (mff / "subject.xml").write_text(
            "<patient><fields>"
            "<field><name>First (Given) Name</name><data>Jane</data></field>"
            "<field><name>Last (Family) Name</name><data>Doe</data></field>"
            "<field><name>Patient ID</name><data>HOSP-0042</data></field>"
            "<field><name>Comments</name>"
            "<data>Participant called after recording</data></field>"
            "<field><name>Age</name><data>29</data></field>"
            "<field><name>Technician</name><data></data></field>"
            "</fields></patient>",
            encoding="utf-8",
        )

        report = scan_dataset(self.root)
        codes = [finding.code for finding in report.findings]
        self.assertEqual(2, codes.count("SUBJECT_NAME_FIELD"))
        self.assertIn("LINKED_SOURCE_ID", codes)
        self.assertIn("FREE_TEXT_METADATA", codes)
        rendered = render_json(report) + render_markdown(report)
        for value in values:
            self.assertNotIn(value, rendered)

    def test_mne_info_privacy_fields_are_detected_and_masked(self) -> None:
        values = (
            "Jane",
            "Quinn",
            "Doe",
            "HOSP-0042",
            "42",
            "2026-07-22T10:30:00+00:00",
            "Acquisition Operator",
            "DEVICE-928374",
            "SITE-A",
            "/Users/operator/private/project",
            "Internal Project 42",
            "Participant was called after recording",
            "Processing Operator",
            "ORIGINAL-GUID-928374",
        )
        info = {
            "subject_info": {
                "first_name": values[0],
                "middle_name": values[1],
                "last_name": values[2],
                "birthday": date(1990, 1, 2),
                "his_id": values[3],
                "id": 42,
            },
            "meas_date": datetime(2026, 7, 22, 10, 30, tzinfo=timezone.utc),
            "experimenter": values[6],
            "device_info": {"serial": values[7], "site": values[8]},
            "working_dir": values[9],
            "file_id": {"machid": [101, 202], "secs": 0},
            "meas_id": {"machid": [101, 202], "secs": 0},
            "proj_id": 42,
            "proj_name": values[10],
            "description": values[11],
            "proc_history": [
                {
                    "experimenter": values[12],
                    "date": datetime(2026, 7, 21, tzinfo=timezone.utc),
                }
            ],
            "helium_info": {"orig_file_guid": values[13]},
        }
        findings = inspect_mne_info(info, "sub-01_task-rest_eeg.fif")
        report = scan_dataset(self.root)
        report.findings.extend(findings)
        codes = {finding.code for finding in findings}
        self.assertTrue(
            {
                "SUBJECT_NAME_FIELD",
                "BIRTH_DATE_FIELD",
                "LINKED_SOURCE_ID",
                "EXACT_RECORDING_DATE",
                "PERSONNEL_FIELD",
                "DEVICE_IDENTIFIER",
                "LOCAL_PATH",
                "ACQUISITION_SYSTEM_ID",
                "PROJECT_IDENTIFIER",
                "FREE_TEXT_METADATA",
            }
            <= codes
        )
        rendered = render_json(report) + render_markdown(report)
        for value in values:
            self.assertNotIn(value, rendered)

    def test_untrusted_mne_mapping_keys_are_not_repeated_in_locations(self) -> None:
        private_key = "Jane_Doe_MRN928374"
        findings = inspect_mne_info(
            {
                "subject_info": None,
                "proc_history": {
                    private_key: {
                        "experimenter": "Acquisition Operator",
                    }
                },
            },
            "sub-01_task-rest_eeg.fif",
        )
        personnel = next(item for item in findings if item.code == "PERSONNEL_FIELD")
        self.assertEqual("MNE Info proc_history.experimenter", personnel.location)
        report = scan_dataset(self.root)
        report.findings.extend(findings)
        self.assertNotIn(private_key, render_json(report) + render_markdown(report))

    def test_fif_and_eeglab_use_metadata_only_readers(self) -> None:
        for name in ("sub-01_task-rest_eeg.fif", "sub-01_task-rest_eeg.set"):
            (self.root / name).write_bytes(b"synthetic-format-placeholder")

        closed: list[str] = []

        class FakeRaw:
            preload = False
            info = {"meas_date": datetime(2026, 7, 22, tzinfo=timezone.utc)}

            def close(self) -> None:
                closed.append("set")

        io_module = SimpleNamespace(
            read_info=lambda path, verbose: {
                "subject_info": {"his_id": "HOSP-0042"}
            },
            read_raw_eeglab=lambda path, preload, verbose: FakeRaw(),
        )
        with (
            patch(
                "neurodata_security_audit.readers._load_mne",
                return_value=SimpleNamespace(io=io_module),
            ),
            patch(
                "neurodata_security_audit.scanner.inspect_eeglab_metadata",
                return_value=[],
            ),
        ):
            report = scan_dataset(self.root)

        self.assertEqual(
            ["sub-01_task-rest_eeg.fif", "sub-01_task-rest_eeg.set"],
            report.files_inspected,
        )
        self.assertEqual(["set"], closed)
        self.assertTrue(
            {"LINKED_SOURCE_ID", "EXACT_RECORDING_DATE"}
            <= {finding.code for finding in report.findings}
        )

    def test_nifti_reader_inspects_header_without_loading_voxels(self) -> None:
        nifti = self.root / "sub-01_T1w.nii"
        nifti.write_bytes(b"synthetic-nifti-placeholder")
        values = (
            "Jane Doe",
            "study.contact@example.org",
            "/Users/operator/private/original.nii",
            "HOSP-0042",
        )

        class FakeHeader(dict):
            extensions: tuple[object, ...] = ()

        class FakeImage:
            header = FakeHeader(
                {
                    "descrip": (
                        f"Participant {values[0]}, contact {values[1]}"
                    ).encode(),
                    "aux_file": values[2].encode(),
                    "intent_name": b"rest",
                    "db_name": values[3].encode(),
                }
            )

            @property
            def dataobj(self):
                raise AssertionError("voxel data must not be accessed")

        class FakeNibabel:
            @staticmethod
            def load(path: str, *, mmap: bool, keep_file_open: bool):
                self.assertEqual(nifti.resolve(), Path(path))
                self.assertFalse(mmap)
                self.assertFalse(keep_file_open)
                return FakeImage()

        with patch(
            "neurodata_security_audit.imaging._load_nibabel",
            return_value=FakeNibabel(),
        ):
            report = scan_dataset(
                self.root,
                ScanPolicy(sensitive_terms=("Jane Doe",)),
            )

        codes = {item.code for item in report.findings}
        self.assertTrue(
            {
                "KNOWN_IDENTIFIER",
                "DIRECT_EMAIL",
                "LOCAL_PATH",
                "FREE_TEXT_METADATA",
                "SOURCE_FILENAME",
                "LINKED_SOURCE_ID",
            }
            <= codes
        )
        coverage = next(item for item in report.coverage if item.path == nifti.name)
        self.assertEqual("header_or_structure_only", coverage.status)
        rendered = render_json(report) + render_markdown(report)
        for value in values:
            self.assertNotIn(value, rendered)

    def test_nifti_extension_is_a_visible_coverage_boundary(self) -> None:
        nifti = self.root / "sub-01_T1w.nii.gz"
        nifti.write_bytes(b"synthetic-nifti-placeholder")

        class FakeExtension:
            @staticmethod
            def get_code() -> int:
                return 6

        class FakeHeader(dict):
            extensions = (FakeExtension(),)

        image = SimpleNamespace(
            header=FakeHeader(
                {
                    "descrip": b"",
                    "aux_file": b"",
                    "intent_name": b"",
                    "db_name": b"",
                }
            )
        )
        with patch(
            "neurodata_security_audit.imaging._load_nibabel",
            return_value=SimpleNamespace(load=lambda *args, **kwargs: image),
        ):
            report = scan_dataset(self.root)
        extension = next(
            item for item in report.findings if item.code == "NIFTI_EXTENSION_PRESENT"
        )
        self.assertEqual("<nifti-extension-code:6>", extension.evidence)

    def test_missing_nifti_reader_is_visible(self) -> None:
        nifti = self.root / "sub-01_T1w.nii"
        nifti.write_bytes(b"synthetic-nifti-placeholder")
        with patch(
            "neurodata_security_audit.scanner.inspect_nifti_metadata",
            side_effect=FormatReaderUnavailable("synthetic"),
        ):
            report = scan_dataset(self.root)
        self.assertIn(
            "FORMAT_READER_UNAVAILABLE",
            {item.code for item in report.findings},
        )
        coverage = next(item for item in report.coverage if item.path == nifti.name)
        self.assertEqual("unsupported_manual_review", coverage.status)

    def test_unreadable_nifti_metadata_is_visible_without_error_details(self) -> None:
        nifti = self.root / "sub-01_T1w.nii"
        nifti.write_bytes(b"synthetic-nifti-placeholder")
        private_error = "Jane Doe at /Users/jane/private"
        with patch(
            "neurodata_security_audit.scanner.inspect_nifti_metadata",
            side_effect=ValueError(private_error),
        ):
            report = scan_dataset(self.root)
        self.assertIn(
            "FORMAT_METADATA_UNREADABLE",
            {item.code for item in report.findings},
        )
        self.assertNotIn(private_error, render_json(report) + render_markdown(report))

    def test_nifti_pair_image_is_treated_as_payload(self) -> None:
        image = self.root / "sub-01_T1w.img"
        image.write_bytes(b"synthetic image payload")

        report = scan_dataset(self.root)

        entry = next(item for item in report.coverage if item.path == image.name)
        self.assertEqual("payload_not_opened", entry.status)
        self.assertNotIn(image.name, report.files_inspected)

    def test_dicom_reader_inspects_nested_metadata_without_pixels(self) -> None:
        dicom = self.root / "sub-01_scan.dcm"
        dicom.write_bytes(b"synthetic-dicom-placeholder")
        values = (
            "Jane Doe",
            "19900102",
            "HOSP-0042",
            "Example Hospital",
            "Acquisition Operator",
            "SCANNER-928374",
            "study.contact@example.org",
            "1.2.826.0.1.3680043.8.498.1234",
            "12 Main Street",
        )

        class FakeTag:
            is_private = False
            group = 0
            element = 0

        class FakeElement:
            def __init__(self, keyword: str, vr: str, value: object):
                self.keyword = keyword
                self.VR = vr
                self.value = value
                self.tag = FakeTag()

        nested = [
            FakeElement("PatientAddress", "LO", values[8]),
        ]
        dataset = [
            FakeElement("PatientName", "PN", values[0]),
            FakeElement("PatientBirthDate", "DA", values[1]),
            FakeElement("PatientID", "LO", values[2]),
            FakeElement("InstitutionName", "LO", values[3]),
            FakeElement("OperatorsName", "PN", values[4]),
            FakeElement("DeviceSerialNumber", "LO", values[5]),
            FakeElement("StudyDescription", "LO", values[6]),
            FakeElement("StudyInstanceUID", "UI", values[7]),
            FakeElement("BurnedInAnnotation", "CS", "YES"),
            FakeElement("RecognizableVisualFeatures", "CS", "YES"),
            FakeElement("PatientIdentityRemoved", "CS", "NO"),
            FakeElement("ReferencedStudySequence", "SQ", nested),
        ]

        class FakeDataset(list):
            @property
            def pixel_array(self):
                raise AssertionError("pixel data must not be accessed")

        class FakePydicom:
            @staticmethod
            def dcmread(
                path: str,
                *,
                stop_before_pixels: bool,
                force: bool,
                defer_size: int,
            ):
                self.assertEqual(dicom.resolve(), Path(path))
                self.assertTrue(stop_before_pixels)
                self.assertFalse(force)
                self.assertEqual(1024 * 1024, defer_size)
                return FakeDataset(dataset)

        with patch(
            "neurodata_security_audit.imaging._load_pydicom",
            return_value=FakePydicom(),
        ):
            report = scan_dataset(
                self.root,
                ScanPolicy(sensitive_terms=("Jane Doe",)),
            )

        codes = {item.code for item in report.findings}
        self.assertTrue(
            {
                "SUBJECT_NAME_FIELD",
                "BIRTH_DATE_FIELD",
                "LINKED_SOURCE_ID",
                "SITE_IDENTIFIER",
                "PERSONNEL_FIELD",
                "DEVICE_IDENTIFIER",
                "DIRECT_EMAIL",
                "FREE_TEXT_METADATA",
                "DICOM_UID",
                "BURNED_IN_ANNOTATION",
                "DICOM_IDENTITY_NOT_REMOVED",
                "POSTAL_ADDRESS_FIELD",
            }
            <= codes
        )
        coverage = next(item for item in report.coverage if item.path == dicom.name)
        self.assertEqual("header_or_structure_only", coverage.status)
        rendered = render_json(report) + render_markdown(report)
        for value in values:
            self.assertNotIn(value, rendered)

    def test_dicom_private_binary_and_documents_are_not_opened(self) -> None:
        dicom = self.root / "sub-01_scan.dcm"
        dicom.write_bytes(b"synthetic-dicom-placeholder")

        class FakeTag:
            def __init__(self, private: bool, group: int, element: int):
                self.is_private = private
                self.group = group
                self.element = element

        class RefuseValue:
            def __str__(self):
                raise AssertionError("binary value must not be read")

        class FakeElement:
            def __init__(
                self,
                keyword: str,
                vr: str,
                tag: FakeTag,
            ):
                self.keyword = keyword
                self.VR = vr
                self.tag = tag

            @property
            def value(self):
                return RefuseValue()

        dataset = [
            FakeElement(
                "",
                "OB",
                FakeTag(True, 0x0019, 0x100A),
            ),
            FakeElement(
                "EncapsulatedDocument",
                "OB",
                FakeTag(False, 0x0042, 0x0011),
            ),
            FakeElement(
                "PixelData",
                "OB",
                FakeTag(False, 0x7FE0, 0x0010),
            ),
        ]
        with patch(
            "neurodata_security_audit.imaging._load_pydicom",
            return_value=SimpleNamespace(
                dcmread=lambda *args, **kwargs: dataset,
            ),
        ):
            report = scan_dataset(self.root)

        codes = {item.code for item in report.findings}
        self.assertTrue(
            {
                "DICOM_PRIVATE_TAG",
                "ENCAPSULATED_DOCUMENT_PRESENT",
                "DICOM_PIXEL_DATA_PRESENT",
            }
            <= codes
        )

    def test_dicom_nested_metadata_depth_is_bounded(self) -> None:
        dicom = self.root / "sub-01_scan.dcm"
        dicom.write_bytes(b"synthetic-dicom-placeholder")

        tag = SimpleNamespace(is_private=False, group=0, element=0)
        nested: list[object] = [
            SimpleNamespace(
                keyword="PatientID",
                VR="LO",
                value="HOSP-0042",
                tag=tag,
            )
        ]
        for _ in range(18):
            nested = [
                SimpleNamespace(
                    keyword="ReferencedStudySequence",
                    VR="SQ",
                    value=nested,
                    tag=tag,
                )
            ]

        with patch(
            "neurodata_security_audit.imaging._load_pydicom",
            return_value=SimpleNamespace(
                dcmread=lambda *args, **kwargs: nested,
            ),
        ):
            report = scan_dataset(self.root)
        self.assertIn(
            "DICOM_METADATA_LIMIT",
            {item.code for item in report.findings},
        )
        coverage = next(item for item in report.coverage if item.path == dicom.name)
        self.assertEqual("unsupported_manual_review", coverage.status)
        self.assertIn(
            dicom.name,
            {item.path for item in report.skipped_files},
        )

    def test_extensionless_dicom_preamble_is_detected(self) -> None:
        dicom = self.root / "scan0001"
        dicom.write_bytes(b"\x00" * 128 + b"DICM")
        with patch(
            "neurodata_security_audit.scanner.inspect_dicom_metadata",
            return_value=[],
        ):
            report = scan_dataset(self.root)
        self.assertIn(dicom.name, report.files_inspected)
        entry = next(item for item in report.coverage if item.path == dicom.name)
        self.assertEqual("header_or_structure_only", entry.status)

    def test_missing_dicom_reader_is_visible(self) -> None:
        dicom = self.root / "sub-01_scan.dcm"
        dicom.write_bytes(b"synthetic-dicom-placeholder")
        with patch(
            "neurodata_security_audit.scanner.inspect_dicom_metadata",
            side_effect=FormatReaderUnavailable("synthetic"),
        ):
            report = scan_dataset(self.root)
        self.assertIn(
            "FORMAT_READER_UNAVAILABLE",
            {item.code for item in report.findings},
        )
        entry = next(item for item in report.coverage if item.path == dicom.name)
        self.assertEqual("unsupported_manual_review", entry.status)

    def test_unreadable_dicom_metadata_hides_error_details(self) -> None:
        dicom = self.root / "sub-01_scan.dcm"
        dicom.write_bytes(b"synthetic-dicom-placeholder")
        private_error = "Jane Doe at /Users/jane/private"
        with patch(
            "neurodata_security_audit.scanner.inspect_dicom_metadata",
            side_effect=ValueError(private_error),
        ):
            report = scan_dataset(self.root)
        self.assertIn(
            "FORMAT_METADATA_UNREADABLE",
            {item.code for item in report.findings},
        )
        self.assertNotIn(private_error, render_json(report) + render_markdown(report))

    def test_empty_mne_identifiers_are_not_reported(self) -> None:
        findings = inspect_mne_info(
            {
                "file_id": {"machid": [0, 0], "secs": 0},
                "meas_id": None,
                "subject_info": None,
            },
            "sub-01_task-rest_eeg.fif",
        )
        self.assertNotIn(
            "ACQUISITION_SYSTEM_ID",
            {finding.code for finding in findings},
        )

    def test_numeric_mne_identifier_is_not_treated_as_an_array(self) -> None:
        class NumericScalar(Number):
            def __eq__(self, other: object) -> bool:
                return other == 1

            def reshape(self, *args: object) -> object:
                raise AssertionError("numeric scalars must not be expanded")

        findings = inspect_mne_info(
            {
                "file_id": {"machid": NumericScalar()},
                "subject_info": None,
            },
            "sub-01_task-rest_eeg.fif",
        )
        self.assertIn(
            "ACQUISITION_SYSTEM_ID",
            {finding.code for finding in findings},
        )

    def test_preloaded_eeglab_signal_fails_visibly(self) -> None:
        (self.root / "recording.set").write_bytes(b"synthetic-format-placeholder")

        class FakeRaw:
            preload = True
            info = {}

            def close(self) -> None:
                pass

        io_module = SimpleNamespace(
            read_raw_eeglab=lambda path, preload, verbose: FakeRaw(),
        )
        with patch(
            "neurodata_security_audit.readers._load_mne",
            return_value=SimpleNamespace(io=io_module),
        ):
            report = scan_dataset(self.root)
        self.assertIn(
            "FORMAT_PRELOADED_SIGNAL",
            {finding.code for finding in report.findings},
        )

    def test_eeglab_private_fields_are_detected_and_masked(self) -> None:
        values = {
            "subject": ["HOSP-0042"],
            "filename": ["Jane_Doe_original.set"],
            "filepath": ["/Users/operator/private/eeg"],
            "comments": ["Contact: eeg.operator@example.org"],
        }
        with patch(
            "neurodata_security_audit.readers._read_eeglab_metadata",
            return_value=(values, True),
        ):
            findings = inspect_eeglab_metadata(
                self.root / "sub-01_task-rest_eeg.set",
                "sub-01_task-rest_eeg.set",
                None,
            )
        codes = {finding.code for finding in findings}
        self.assertTrue(
            {
                "LINKED_SOURCE_ID",
                "SOURCE_FILENAME",
                "LOCAL_PATH",
                "DIRECT_EMAIL",
                "FREE_TEXT_METADATA",
            }
            <= codes
        )
        report = scan_dataset(self.root)
        report.findings.extend(findings)
        rendered = render_json(report) + render_markdown(report)
        for value in (
            "HOSP-0042",
            "Jane_Doe_original.set",
            "/Users/operator/private/eeg",
            "eeg.operator@example.org",
        ):
            self.assertNotIn(value, rendered)

    def test_eeglab_external_data_file_reference_is_checked(self) -> None:
        set_file = self.root / "recording.set"
        fdt_file = self.root / "recording.fdt"
        set_file.write_bytes(b"synthetic-format-placeholder")
        fdt_file.write_bytes(b"synthetic signal")
        references = []

        with patch(
            "neurodata_security_audit.readers._read_eeglab_metadata",
            return_value=({"data": [fdt_file.name]}, True),
        ):
            findings = inspect_eeglab_metadata(
                set_file,
                set_file.name,
                dataset_root=self.root,
                reference_entries=references,
            )

        self.assertEqual([], findings)
        self.assertEqual(1, len(references))
        self.assertEqual("valid_internal", references[0].status)
        self.assertEqual(fdt_file.name, references[0].target)

    def test_nested_eeglab_metadata_gap_is_visible(self) -> None:
        with patch(
            "neurodata_security_audit.readers._read_eeglab_metadata",
            return_value=({}, False),
        ):
            findings = inspect_eeglab_metadata(
                self.root / "legacy.set",
                "legacy.set",
                None,
            )
        self.assertEqual(["EEGLAB_METADATA_COVERAGE_LIMIT"], [x.code for x in findings])

    def test_nested_eeglab_structure_does_not_call_mne(self) -> None:
        (self.root / "recording.set").write_bytes(b"synthetic-format-placeholder")

        with (
            patch(
                "neurodata_security_audit.readers._read_eeglab_metadata",
                return_value=({}, False),
            ),
            patch(
                "neurodata_security_audit.readers._load_mne",
                side_effect=AssertionError("MNE reader must not be called"),
            ),
        ):
            report = scan_dataset(self.root)

        self.assertIn(
            "EEGLAB_METADATA_COVERAGE_LIMIT",
            {finding.code for finding in report.findings},
        )
        self.assertEqual(
            ["recording.set"],
            [item.path for item in report.skipped_files],
        )

    def test_external_eeglab_data_reference_does_not_call_mne(self) -> None:
        (self.root / "recording.set").write_bytes(b"synthetic-format-placeholder")
        external_path = "../../private/participant_data.fdt"

        with (
            patch(
                "neurodata_security_audit.readers._read_eeglab_metadata",
                return_value=({"data": [external_path]}, True),
            ),
            patch(
                "neurodata_security_audit.readers._load_mne",
                side_effect=AssertionError("MNE reader must not be called"),
            ),
        ):
            report = scan_dataset(self.root)

        self.assertIn(
            "EXTERNAL_DATA_REFERENCE",
            {finding.code for finding in report.findings},
        )
        self.assertNotIn(
            external_path,
            render_json(report) + render_markdown(report),
        )

    def test_missing_eeglab_metadata_reader_is_visible(self) -> None:
        (self.root / "recording.set").write_bytes(b"synthetic-format-placeholder")

        class FakeRaw:
            preload = False
            info = {}

            def close(self) -> None:
                pass

        with (
            patch(
                "neurodata_security_audit.scanner.inspect_eeglab_metadata",
                side_effect=FormatReaderUnavailable(),
            ),
            patch(
                "neurodata_security_audit.readers._load_mne",
                return_value=SimpleNamespace(
                    io=SimpleNamespace(
                        read_raw_eeglab=lambda path, preload, verbose: FakeRaw()
                    )
                ),
            ),
        ):
            report = scan_dataset(self.root)

        self.assertIn(
            "EEGLAB_METADATA_READER_UNAVAILABLE",
            {finding.code for finding in report.findings},
        )

    def test_unreadable_eeglab_private_metadata_is_visible(self) -> None:
        (self.root / "recording.set").write_bytes(b"synthetic-format-placeholder")
        private_error = "Jane Doe at /Users/jane/private"
        with (
            patch(
                "neurodata_security_audit.scanner.inspect_eeglab_metadata",
                side_effect=RuntimeError(private_error),
            ),
            patch(
                "neurodata_security_audit.scanner.inspect_mne_format",
                return_value=[],
            ),
        ):
            report = scan_dataset(self.root)
        self.assertIn(
            "EEGLAB_METADATA_UNREADABLE",
            {finding.code for finding in report.findings},
        )
        self.assertNotIn(private_error, render_json(report) + render_markdown(report))

    def test_unreadable_optional_format_metadata_is_visible(self) -> None:
        (self.root / "recording.fif").write_bytes(b"synthetic-format-placeholder")
        private_error = "Jane Doe at /Users/jane/private"
        with patch(
            "neurodata_security_audit.scanner.inspect_mne_format",
            side_effect=RuntimeError(private_error),
        ):
            report = scan_dataset(self.root)
        self.assertIn(
            "FORMAT_METADATA_UNREADABLE",
            {finding.code for finding in report.findings},
        )
        self.assertNotIn(private_error, render_json(report) + render_markdown(report))

    def test_formats_extra_includes_mff_xml_reader(self) -> None:
        try:
            requirements = metadata.requires("neurodata-release-security-audit") or []
            text = "\n".join(requirements)
        except metadata.PackageNotFoundError:
            pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
            text = pyproject.read_text(encoding="utf-8")
        self.assertIn("defusedxml>=0.7.1", text)

    def test_mff_reader_uses_preload_false_and_xml_remains_inspected(self) -> None:
        mff = self.root / "recording.mff"
        mff.mkdir()
        (mff / "info.xml").write_text(
            "<recording><recordTime>2026-07-22T10:30:00Z</recordTime></recording>",
            encoding="utf-8",
        )
        calls: list[tuple[bool, bool]] = []

        class FakeRaw:
            preload = False
            info = {"subject_info": {"his_id": "HOSP-0042"}}

            def close(self) -> None:
                pass

        def read_raw_egi(path, preload, events_as_annotations, verbose):
            calls.append((preload, events_as_annotations))
            return FakeRaw()

        io_module = SimpleNamespace(read_raw_egi=read_raw_egi)
        with patch(
            "neurodata_security_audit.readers._load_mne",
            return_value=SimpleNamespace(io=io_module),
        ):
            report = scan_dataset(self.root)
        self.assertEqual([(False, True)], calls)
        self.assertIn("recording.mff", report.files_inspected)
        self.assertIn("recording.mff/info.xml", report.files_inspected)
        self.assertTrue(
            {"LINKED_SOURCE_ID", "EXACT_RECORDING_DATE"}
            <= {finding.code for finding in report.findings}
        )
        self.assertNotIn(
            "FORMAT_READER_UNAVAILABLE",
            {finding.code for finding in report.findings},
        )

    def test_empty_and_lfs_optional_formats_are_visible_without_reader(self) -> None:
        (self.root / "empty.set").write_bytes(b"")
        (self.root / "pointer.fif").write_text(
            "version https://git-lfs.github.com/spec/v1\n"
            "oid sha256:0000000000000000000000000000000000000000000000000000000000000000\n"
            "size 123456\n",
            encoding="ascii",
        )
        report = scan_dataset(self.root)
        codes = {finding.code for finding in report.findings}
        self.assertIn("EMPTY_PLACEHOLDER", codes)
        self.assertIn("GIT_LFS_POINTER", codes)
        self.assertNotIn("FORMAT_READER_UNAVAILABLE", codes)
        coverage = {item.path: item.status for item in report.coverage}
        self.assertEqual("unsupported_manual_review", coverage["empty.set"])
        self.assertEqual("unsupported_manual_review", coverage["pointer.fif"])

    def test_empty_nifti_is_reported_as_a_placeholder(self) -> None:
        path = self.root / "sub-01_T1w.nii.gz"
        path.write_bytes(b"")

        report = scan_dataset(self.root)

        codes = {finding.code for finding in report.findings}
        self.assertIn("EMPTY_PLACEHOLDER", codes)
        self.assertNotIn("FORMAT_METADATA_UNREADABLE", codes)
        entry = next(item for item in report.coverage if item.path == path.name)
        self.assertEqual("unsupported_manual_review", entry.status)

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
            {
                "SUBJECT_FIELD_POPULATED",
                "SUBJECT_NAME_FIELD",
                "BIRTH_DATE_FIELD",
                "EXACT_RECORDING_DATE",
                "RECORDING_INFO_FIELD",
            }
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
        report = scan_dataset(self.root)
        entry = next(item for item in report.coverage if item.path == "recording.edf")
        self.assertEqual("unsupported_manual_review", entry.status)

    def test_participant_key_and_backup_are_visible(self) -> None:
        (self.root / "participant_name_key.xlsx").write_bytes(b"synthetic")
        (self.root / "notes.bak").write_text("old", encoding="utf-8")
        codes = set(self._codes())
        self.assertIn("SUBJECT_KEY_FILE", codes)
        self.assertIn("UNEXPECTED_FILE", codes)

    def test_development_directory_is_visible_but_not_traversed(self) -> None:
        git_dir = self.root / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text(
            "contact = alice@example.org\n",
            encoding="utf-8",
        )
        report = scan_dataset(self.root)
        codes = {finding.code for finding in report.findings}
        self.assertIn("UNEXPECTED_DIRECTORY", codes)
        self.assertNotIn("DIRECT_EMAIL", codes)
        self.assertIn(".git", [item.path for item in report.skipped_files])

    def test_external_symlink_is_not_followed(self) -> None:
        outside = Path(self.temp_dir.name) / "outside.txt"
        outside.write_text("alice@example.org", encoding="utf-8")
        link = self.root / "external.txt"
        os.symlink(outside, link)
        original_resolve = Path.resolve

        def controlled_resolve(path: Path, *args, **kwargs):
            if path == link:
                raise AssertionError("scanner resolved the symlink target")
            return original_resolve(path, *args, **kwargs)

        with patch.object(Path, "resolve", controlled_resolve):
            report = scan_dataset(self.root)
        codes = {finding.code for finding in report.findings}
        self.assertIn("EXTERNAL_SYMLINK", codes)
        self.assertNotIn("DIRECT_EMAIL", codes)

    def test_internal_symlink_is_visible_but_not_followed(self) -> None:
        target = self.root / "notes.txt"
        target.write_text("Synthetic dataset\n", encoding="utf-8")
        link = self.root / "linked_notes.txt"
        os.symlink(target.name, link)
        report = scan_dataset(self.root)
        self.assertIn("SYMLINK_REVIEW", {finding.code for finding in report.findings})
        self.assertIn(link.name, [item.path for item in report.skipped_files])

    def test_identifier_in_symlink_name_is_detected_and_masked(self) -> None:
        known_id = "SITEA-0042"
        target = self.root / "notes.txt"
        target.write_text("Synthetic dataset\n", encoding="utf-8")
        link = self.root / f"{known_id}_notes.txt"
        os.symlink(target.name, link)

        report = scan_dataset(
            self.root,
            ScanPolicy(sensitive_terms=(known_id,)),
        )
        codes = {item.code for item in report.findings}
        self.assertIn("KNOWN_IDENTIFIER", codes)
        self.assertIn("SYMLINK_REVIEW", codes)
        self.assertNotIn(known_id, render_json(report) + render_markdown(report))

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

    def test_unreadable_entry_does_not_stop_scan(self) -> None:
        blocked = self.root / "blocked.txt"
        blocked.write_text("synthetic", encoding="utf-8")
        readme = self.root / "README"
        readme.write_text("Synthetic dataset\n", encoding="utf-8")
        entries = iter(
            [
                ("entry_error", blocked, "blocked.txt"),
                ("file", readme, "README"),
            ]
        )
        with patch("neurodata_security_audit.scanner._walk", return_value=entries):
            report = scan_dataset(self.root)
        self.assertIn("UNREADABLE_ENTRY", {finding.code for finding in report.findings})
        self.assertIn("README", report.files_inspected)
        rendered = render_json(report) + render_markdown(report)
        self.assertNotIn(str(blocked), rendered)

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
        self.assertEqual("2", json.loads(first)["schema_version"])

    def test_every_release_entry_has_one_coverage_record(self) -> None:
        data_dir = self.root / "sub-01" / "eeg"
        data_dir.mkdir(parents=True)
        (self.root / "README").write_text("Synthetic dataset\n", encoding="utf-8")
        (data_dir / "recording.eeg").write_bytes(b"synthetic signal")
        (data_dir / "notes.unknown").write_bytes(b"opaque")

        report = scan_dataset(self.root)
        expected = {
            path.relative_to(self.root).as_posix()
            for path in self.root.rglob("*")
        }
        coverage_paths = [item.path for item in report.coverage]
        self.assertEqual(expected, set(coverage_paths))
        self.assertEqual(len(expected), len(coverage_paths))

        status = {item.path: item.status for item in report.coverage}
        self.assertEqual("fully_inspected_metadata", status["README"])
        self.assertEqual("header_or_structure_only", status["sub-01"])
        self.assertEqual("payload_not_opened", status["sub-01/eeg/recording.eeg"])
        self.assertEqual(
            "unsupported_manual_review",
            status["sub-01/eeg/notes.unknown"],
        )

    def test_manifest_hashes_every_regular_file_without_changing_it(self) -> None:
        text = self.root / "README"
        signal = self.root / "recording.eeg"
        text.write_text("Synthetic dataset\n", encoding="utf-8")
        signal.write_bytes(b"\x00\x01synthetic signal")
        before = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (text, signal)
        }

        report = scan_dataset(self.root)

        manifest = {item.path: item for item in report.manifest}
        self.assertEqual({"README", "recording.eeg"}, set(manifest))
        self.assertEqual(before["README"], manifest["README"].sha256)
        self.assertEqual(before["recording.eeg"], manifest["recording.eeg"].sha256)
        self.assertEqual(text.stat().st_size, manifest["README"].size_bytes)
        self.assertEqual(signal.stat().st_size, manifest["recording.eeg"].size_bytes)
        after = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (text, signal)
        }
        self.assertEqual(before, after)

    def test_file_change_between_manifest_passes_is_visible(self) -> None:
        source = self.root / "README"
        source.write_text("Synthetic dataset\n", encoding="utf-8")

        with patch(
            "neurodata_security_audit.scanner._sha256_file",
            side_effect=["0" * 64, "1" * 64],
        ):
            report = scan_dataset(self.root)

        self.assertFalse(report.manifest_recheck_passed)
        self.assertIn(
            "FILE_CHANGED_DURING_SCAN",
            {item.code for item in report.findings},
        )
        entry = next(item for item in report.coverage if item.path == "README")
        self.assertEqual("unsupported_manual_review", entry.status)

    def test_release_tree_change_during_scan_is_visible(self) -> None:
        source = self.root / "README"
        source.write_text("Synthetic dataset\n", encoding="utf-8")
        with patch(
            "neurodata_security_audit.scanner._tree_signature",
            side_effect=[
                {"README": ("file", "")},
                {
                    "README": ("file", ""),
                    "late-file.txt": ("file", ""),
                },
            ],
        ):
            report = scan_dataset(self.root)

        self.assertFalse(report.release_tree_recheck_passed)
        self.assertIn(
            "RELEASE_TREE_CHANGED_DURING_SCAN",
            {item.code for item in report.findings},
        )
        late = next(item for item in report.coverage if item.path == "late-file.txt")
        self.assertEqual("unsupported_manual_review", late.status)

    def test_symlink_target_change_during_scan_is_visible(self) -> None:
        link = self.root / "recording-link"
        os.symlink("first-target", link)
        with patch(
            "neurodata_security_audit.scanner._tree_signature",
            side_effect=[
                {"recording-link": ("symlink", "signature-a")},
                {"recording-link": ("symlink", "signature-b")},
            ],
        ):
            report = scan_dataset(self.root)

        self.assertFalse(report.release_tree_recheck_passed)
        finding = next(
            item
            for item in report.findings
            if item.code == "RELEASE_TREE_CHANGED_DURING_SCAN"
        )
        self.assertEqual("<tree-entry:symlink-target-changed>", finding.evidence)
        rendered = render_json(report) + render_markdown(report)
        self.assertNotIn("first-target", rendered)
        self.assertNotIn("second-target", rendered)

    def test_tree_signature_reads_symlink_target_without_opening_it(self) -> None:
        outside = Path(self.temp_dir.name) / "outside.txt"
        outside.write_text("must not be read", encoding="utf-8")
        link = self.root / "recording-link"
        os.symlink(outside, link)

        with patch.object(
            Path,
            "open",
            side_effect=AssertionError("symlink target must not be opened"),
        ):
            signature = _tree_signature(self.root)

        expected = hashlib.sha256(os.fsencode(str(outside))).hexdigest()
        self.assertEqual(("symlink", expected), signature[link.name])

    def test_ignored_directory_descendants_are_inventoried_but_not_parsed(self) -> None:
        ignored = self.root / ".git"
        nested = ignored / "objects"
        nested.mkdir(parents=True)
        secret = "ghp_" + "A" * 32
        payload = nested / "private.txt"
        payload.write_text(secret, encoding="utf-8")

        report = scan_dataset(self.root)

        coverage = {item.path: item.status for item in report.coverage}
        self.assertEqual("not_traversed", coverage[".git"])
        self.assertEqual("not_traversed", coverage[".git/objects"])
        self.assertEqual("not_traversed", coverage[".git/objects/private.txt"])
        self.assertIn(
            ".git/objects/private.txt",
            {item.path for item in report.manifest},
        )
        self.assertNotIn("POSSIBLE_CREDENTIAL", {item.code for item in report.findings})
        self.assertNotIn(secret, render_json(report) + render_markdown(report))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO fixture requires os.mkfifo")
    def test_special_filesystem_entry_is_accounted_for_without_opening_it(self) -> None:
        fifo = self.root / "acquisition.pipe"
        os.mkfifo(fifo)

        report = scan_dataset(self.root)

        entry = next(item for item in report.coverage if item.path == fifo.name)
        self.assertEqual("other", entry.entry_type)
        self.assertEqual("unsupported_manual_review", entry.status)
        self.assertIn(
            "SPECIAL_FILESYSTEM_ENTRY",
            {item.code for item in report.findings},
        )
        self.assertNotIn(fifo.name, {item.path for item in report.manifest})

    def test_release_filename_collisions_are_visible(self) -> None:
        manifest = [
            ManifestEntry("sub-01/eeg/data.edf", 1, "0" * 64),
            ManifestEntry("sub-02/eeg/data.edf", 1, "1" * 64),
            ManifestEntry("sub-03/eeg/Data.EDF", 1, "2" * 64),
            ManifestEntry("Sub-04/eeg/file.txt", 1, "3" * 64),
            ManifestEntry("sub-04/eeg/file.txt", 1, "4" * 64),
            ManifestEntry("sub-05/notes.txt", 1, "5" * 64),
            ManifestEntry("sub-06/notes.txt", 1, "6" * 64),
        ]

        codes = {
            item.code for item in _release_collision_findings(manifest)
        }

        self.assertTrue(
            {
                "CASE_COLLIDING_RELEASE_PATH",
                "DUPLICATE_BASENAME",
                "CASE_COLLIDING_BASENAME",
            }
            <= codes
        )

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

    def test_markdown_report_explains_what_to_check(self) -> None:
        (self.root / "notes.txt").write_text(
            "Contact: alice@example.org\n",
            encoding="utf-8",
        )
        rendered = render_markdown(scan_dataset(self.root))
        self.assertIn("| What to check |", rendered)
        self.assertIn(
            "Confirm this email is intentionally public; otherwise remove it.",
            rendered,
        )

    def test_html_report_is_deterministic_and_self_contained(self) -> None:
        (self.root / "notes.txt").write_text(
            "Contact: alice@example.org\n",
            encoding="utf-8",
        )
        report = scan_dataset(self.root)

        first = render_html(report)
        second = render_html(report)

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("<!doctype html>"))
        self.assertIn("<title>NeuroData release security audit</title>", first)
        self.assertIn("DIRECT_EMAIL", first)
        self.assertNotIn("alice@example.org", first)
        self.assertNotIn("<script", first.lower())
        self.assertNotIn("https://", first)

    def test_html_report_escapes_untrusted_markup(self) -> None:
        filename = 'notes"><img src=x onerror=alert(1)>.txt'
        (self.root / filename).write_text(
            "Contact: alice@example.org\n",
            encoding="utf-8",
        )

        rendered = render_html(scan_dataset(self.root))

        self.assertNotIn("<img src=x onerror=alert(1)>", rendered)
        self.assertIn(
            "notes&quot;&gt;&lt;img src=x onerror=alert(1)&gt;.txt",
            rendered,
        )

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
                    "--html",
                    str(output / "audit.html"),
                ]
            )
        self.assertEqual(1, code)
        self.assertTrue((output / "audit.json").is_file())
        self.assertTrue((output / "audit.md").is_file())
        html = (output / "audit.html").read_text(encoding="utf-8")
        self.assertIn("<!doctype html>", html)
        self.assertNotIn("alice@example.org", html)

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

    def test_cli_returns_error_when_integrity_recheck_fails(self) -> None:
        report = ScanReport(
            scanner_version="test",
            release_tree_recheck_passed=False,
        )
        stdout = io.StringIO()
        with (
            patch(
                "neurodata_security_audit.cli.scan_dataset",
                return_value=report,
            ),
            redirect_stdout(stdout),
        ):
            code = main(["scan", str(self.root)])

        self.assertEqual(2, code)
        self.assertIn("integrity=failed", stdout.getvalue())

    def test_cli_rejects_report_inside_dataset(self) -> None:
        report_path = self.root / "audit.json"
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main(["scan", str(self.root), "--json", str(report_path)])
        self.assertEqual(2, code)
        self.assertFalse(report_path.exists())
        self.assertIn("Report paths must be outside", stderr.getvalue())

    def test_cli_rejects_html_report_inside_dataset(self) -> None:
        report_path = self.root / "audit.html"
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main(["scan", str(self.root), "--html", str(report_path)])
        self.assertEqual(2, code)
        self.assertFalse(report_path.exists())
        self.assertIn("Report paths must be outside", stderr.getvalue())

    def test_cli_rejects_sensitive_terms_inside_dataset(self) -> None:
        term_file = self.root / "private_terms.txt"
        term_file.write_text("Jane Doe\n", encoding="utf-8")
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main(
                [
                    "scan",
                    str(self.root),
                    "--sensitive-terms",
                    str(term_file),
                ]
            )
        self.assertEqual(2, code)
        self.assertIn("sensitive term file must be outside", stderr.getvalue())

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
