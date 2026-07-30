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
from usability._io import write_text_new


def _manifest(path: str) -> ManifestEntry:
    digest = hashlib.sha256(f"synthetic:{path}".encode()).hexdigest()
    return ManifestEntry(path=path, size_bytes=512, sha256=digest)


def _clean_report(path: str, reason: str) -> ScanReport:
    return ScanReport(
        scanner_version="0.2.0.dev0",
        files_inspected=[path],
        coverage=[
            CoverageEntry(
                path=path,
                entry_type="file",
                status="fully_inspected_metadata",
                reason=reason,
            )
        ],
        manifest=[_manifest(path)],
    )


def _high_fif_report() -> ScanReport:
    path = "sub-02/eeg/sub-02_task-rest_eeg.fif"
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


def _high_table_report() -> ScanReport:
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
                location="row 4, column contact",
                evidence="<masked-email>",
                message="Remove the direct email before release.",
            )
        ],
    )


def _coverage_report(path: str, reason: str) -> ScanReport:
    return ScanReport(
        scanner_version="0.2.0.dev0",
        coverage=[
            CoverageEntry(
                path=path,
                entry_type="file",
                status="unsupported_manual_review",
                reason=reason,
            )
        ],
        manifest=[_manifest(path)],
    )


def _manifest_integrity_report() -> ScanReport:
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


def _tree_integrity_report() -> ScanReport:
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
        findings=[
            Finding(
                code="FREE_TEXT_METADATA",
                severity="review",
                path=path,
                location="DatasetDescription",
                evidence="<masked-free-text>",
                message="Review this description for identifying details.",
            )
        ],
        manifest_recheck_passed=True,
        release_tree_recheck_passed=False,
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
    for subject in range(1, 32):
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
            evidence = (
                "<masked-review:length=17>"
                if subject == 17 and code == "FREE_TEXT_REVIEW"
                else "<review>"
            )
            findings.append(
                Finding(
                    code=code,
                    severity="review",
                    path=path,
                    location=location,
                    evidence=evidence,
                    message=message,
                )
            )
    return ScanReport(
        scanner_version="0.2.0.dev0",
        files_inspected=files,
        coverage=coverage,
        manifest=manifest,
        findings=findings,
    )


def _inventory_report() -> ScanReport:
    path = "sub-01/eeg/sub-01_task-rest_eeg.vhdr"
    return ScanReport(
        scanner_version="0.2.0.dev0",
        files_inspected=[path],
        coverage=[
            CoverageEntry(
                path="sub-01",
                entry_type="directory",
                status="header_or_structure_only",
                reason="Directory name and release-tree position were inspected",
            ),
            CoverageEntry(
                path="sub-01/eeg",
                entry_type="directory",
                status="header_or_structure_only",
                reason="Directory name and release-tree position were inspected",
            ),
            CoverageEntry(
                path=path,
                entry_type="file",
                status="fully_inspected_metadata",
                reason="BrainVision metadata was inspected",
            ),
        ],
        manifest=[_manifest(path)],
    )


def build_reports(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    reports = {
        "report-a": _clean_report(
            "dataset_description.json",
            "JSON metadata parsed",
        ),
        "report-b": _high_table_report(),
        "report-c": _coverage_report(
            "sub-01/eeg/sub-01_task-rest_eeg.vendor",
            "The .vendor payload is not parsed by this scanner",
        ),
        "report-d": _manifest_integrity_report(),
        "report-e": _high_fif_report(),
        "report-f": _coverage_report(
            "sub-01/eeg/sub-01_task-rest_eeg.xyz",
            "The .xyz payload is not parsed by this scanner",
        ),
        "report-g": _clean_report(
            "participants.tsv",
            "TSV metadata parsed",
        ),
        "report-h": _tree_integrity_report(),
        "report-i": _large_report(),
        "report-j": _inventory_report(),
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
    report_count = len(reports)
    rendered = {
        name: render_html(
            report,
            report_label=(
                f"Report {name.removeprefix('report-').upper()} of {report_count}"
            ),
        )
        for name, report in reports.items()
    }
    fingerprints: dict[str, str] = {}
    for name, content in rendered.items():
        fingerprint = hashlib.sha256(content.encode()).hexdigest()
        if fingerprint in fingerprints:
            raise ValueError(
                "Usability reports must be byte-distinct: "
                f"{fingerprints[fingerprint]} and {name}"
            )
        fingerprints[fingerprint] = name

    paths = {}
    for name, content in rendered.items():
        path = output_dir / f"{name}.html"
        write_text_new(path, content)
        paths[name] = path
    return paths


def main() -> None:
    """Build reports in an explicit directory without replacing existing files."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for report_path in build_reports(args.output_dir).values():
        print(report_path)


if __name__ == "__main__":
    main()
