"""Build deterministic synthetic reports for the usability pilot."""

from __future__ import annotations

import hashlib
from pathlib import Path

from neurodata_security_audit.html_report import render_html
from neurodata_security_audit.models import (
    CoverageEntry,
    Finding,
    ManifestEntry,
    ScanReport,
)

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"


def _manifest(path: str) -> ManifestEntry:
    digest = hashlib.sha256(f"synthetic:{path}".encode()).hexdigest()
    return ManifestEntry(path=path, size_bytes=512, sha256=digest)


def _clean_report() -> ScanReport:
    path = "dataset_description.json"
    return ScanReport(
        scanner_version="0.2.0.dev0",
        files_inspected=[path],
        coverage=[
            CoverageEntry(
                path=path,
                entry_type="file",
                status="fully_inspected_metadata",
                reason="JSON metadata parsed",
            )
        ],
        manifest=[_manifest(path)],
    )


def _high_report() -> ScanReport:
    path = "sub-01/eeg/sub-01_task-rest_eeg.fif"
    return ScanReport(
        scanner_version="0.2.0.dev0",
        files_inspected=[path],
        coverage=[
            CoverageEntry(
                path=path,
                entry_type="file",
                status="header_or_structure_only",
                reason="FIF header inspected without loading signal samples",
            )
        ],
        manifest=[_manifest(path)],
        findings=[
            Finding(
                code="BIRTH_DATE_FIELD",
                severity="high",
                path=path,
                location="subject_info.birthday",
                evidence="<masked-date>",
                message=(
                    "Remove the birth date from a private working copy with a "
                    "format-aware FIF tool, then rerun the audit."
                ),
            )
        ],
    )


def _coverage_report() -> ScanReport:
    path = "sub-01/eeg/sub-01_task-rest_eeg.xyz"
    return ScanReport(
        scanner_version="0.2.0.dev0",
        coverage=[
            CoverageEntry(
                path=path,
                entry_type="file",
                status="unsupported_manual_review",
                reason="The .xyz payload is not parsed by this scanner",
            )
        ],
        manifest=[_manifest(path)],
    )


def _integrity_report() -> ScanReport:
    path = "participants.tsv"
    return ScanReport(
        scanner_version="0.2.0.dev0",
        files_inspected=[path],
        coverage=[
            CoverageEntry(
                path=path,
                entry_type="file",
                status="fully_inspected_metadata",
                reason="TSV metadata parsed",
            )
        ],
        manifest=[_manifest(path)],
        findings=[
            Finding(
                code="DIRECT_EMAIL",
                severity="high",
                path=path,
                location="row 3, column contact",
                evidence="<masked-email>",
                message="Remove the direct email before release.",
            )
        ],
        manifest_recheck_passed=False,
        release_tree_recheck_passed=True,
    )


def _large_report() -> ScanReport:
    findings = []
    coverage = []
    manifest = []
    files = []
    locations = (
        ("DATE_FIELD_REVIEW", "measurement_date", "Confirm that this date is safe."),
        (
            "DEVICE_ID_REVIEW",
            "device.serial_number",
            "Confirm that this device identifier may be shared.",
        ),
        (
            "FREE_TEXT_REVIEW",
            "experimenter_comment",
            "Review this free-text field for identifying details.",
        ),
        (
            "REFERENCE_REVIEW",
            "external_reference",
            "Confirm that this reference does not expose a private location.",
        ),
    )
    for subject in range(1, 31):
        path = f"sub-{subject:02d}/eeg/sub-{subject:02d}_task-rest_eeg.vhdr"
        files.append(path)
        coverage.append(
            CoverageEntry(
                path=path,
                entry_type="file",
                status="header_or_structure_only",
                reason="BrainVision header and linked metadata inspected",
            )
        )
        manifest.append(_manifest(path))
        for code, location, message in locations:
            findings.append(
                Finding(
                    code=code,
                    severity="review",
                    path=path,
                    location=location,
                    evidence="<review>",
                    message=message,
                )
            )
    findings.append(
        Finding(
            code="UNIQUE_CONTACT_REVIEW",
            severity="review",
            path="sub-17/eeg/sub-17_task-rest_eeg.vhdr",
            location="Recording.TechnicianContact",
            evidence="<masked-contact>",
            message=("Check whether the technician contact is needed in the release."),
        )
    )
    return ScanReport(
        scanner_version="0.2.0.dev0",
        files_inspected=files,
        coverage=coverage,
        manifest=manifest,
        findings=findings,
    )


def build_reports(output_dir: Path = REPORTS) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    reports = {
        "report-a": _clean_report(),
        "report-b": _high_report(),
        "report-c": _coverage_report(),
        "report-d": _integrity_report(),
        "report-e": _high_report(),
        "report-f": _coverage_report(),
        "report-g": _clean_report(),
        "report-h": _integrity_report(),
        "report-i": _large_report(),
    }
    expected_names = {f"{name}.html" for name in reports}
    unexpected = sorted(
        path.name
        for path in output_dir.glob("*.html")
        if path.name not in expected_names
    )
    if unexpected:
        raise ValueError(
            "Report directory contains unexpected HTML files: " + ", ".join(unexpected)
        )
    paths = {}
    for name, report in reports.items():
        path = output_dir / f"{name}.html"
        path.write_text(render_html(report), encoding="utf-8")
        paths[name] = path
    return paths


if __name__ == "__main__":
    for report_path in build_reports().values():
        print(report_path)
