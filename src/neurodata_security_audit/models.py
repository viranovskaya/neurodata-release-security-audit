"""Data stored in an audit report."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["high", "review", "info"]
EntryType = Literal[
    "file",
    "directory",
    "format_directory",
    "symlink",
    "other",
    "unreadable",
]
CoverageStatus = Literal[
    "fully_inspected_metadata",
    "header_or_structure_only",
    "payload_not_opened",
    "unsupported_manual_review",
    "not_traversed",
]

_SEVERITY_ORDER = {"high": 0, "review": 1, "info": 2}
_COVERAGE_ORDER = {
    "fully_inspected_metadata": 0,
    "header_or_structure_only": 1,
    "payload_not_opened": 2,
    "unsupported_manual_review": 3,
    "not_traversed": 4,
}


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    path: str
    location: str
    evidence: str
    message: str

    def sort_key(self) -> tuple[int, str, str, str]:
        return (_SEVERITY_ORDER[self.severity], self.path, self.location, self.code)

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "location": self.location,
            "evidence": self.evidence,
            "message": self.message,
        }


@dataclass(frozen=True)
class SkippedFile:
    path: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "reason": self.reason}


@dataclass(frozen=True)
class CoverageEntry:
    path: str
    entry_type: EntryType
    status: CoverageStatus
    reason: str

    def sort_key(self) -> tuple[str, int, str]:
        return (self.path, _COVERAGE_ORDER[self.status], self.entry_type)

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "entry_type": self.entry_type,
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ManifestEntry:
    path: str
    size_bytes: int
    sha256: str

    def to_dict(self) -> dict[str, str | int]:
        return {
            "path": self.path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass
class ScanReport:
    scanner_version: str
    files_inspected: list[str] = field(default_factory=list)
    skipped_files: list[SkippedFile] = field(default_factory=list)
    coverage: list[CoverageEntry] = field(default_factory=list)
    manifest: list[ManifestEntry] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    manifest_recheck_passed: bool = True
    schema_version: str = "2"

    def normalized(self) -> "ScanReport":
        findings = sorted(set(self.findings), key=Finding.sort_key)
        skipped = sorted(set(self.skipped_files), key=lambda item: (item.path, item.reason))
        coverage = sorted(set(self.coverage), key=CoverageEntry.sort_key)
        manifest = sorted(set(self.manifest), key=lambda item: item.path)
        return ScanReport(
            scanner_version=self.scanner_version,
            files_inspected=sorted(set(self.files_inspected)),
            skipped_files=skipped,
            coverage=coverage,
            manifest=manifest,
            findings=findings,
            manifest_recheck_passed=self.manifest_recheck_passed,
            schema_version=self.schema_version,
        )

    def to_dict(self) -> dict[str, object]:
        report = self.normalized()
        counts = {severity: 0 for severity in ("high", "review", "info")}
        for finding in report.findings:
            counts[finding.severity] += 1
        coverage_counts = {status: 0 for status in _COVERAGE_ORDER}
        for entry in report.coverage:
            coverage_counts[entry.status] += 1
        return {
            "schema_version": report.schema_version,
            "scanner_version": report.scanner_version,
            "summary": {
                "files_inspected": len(report.files_inspected),
                "files_skipped": len(report.skipped_files),
                "entries_total": len(report.coverage),
                "manifest_files": len(report.manifest),
                "manifest_recheck_passed": report.manifest_recheck_passed,
                "fully_inspected_metadata": coverage_counts[
                    "fully_inspected_metadata"
                ],
                "header_or_structure_only": coverage_counts[
                    "header_or_structure_only"
                ],
                "payload_not_opened": coverage_counts["payload_not_opened"],
                "unsupported_manual_review": coverage_counts[
                    "unsupported_manual_review"
                ],
                "not_traversed": coverage_counts["not_traversed"],
                "findings_high": counts["high"],
                "findings_review": counts["review"],
                "findings_info": counts["info"],
            },
            "files_inspected": report.files_inspected,
            "skipped_files": [item.to_dict() for item in report.skipped_files],
            "coverage": [item.to_dict() for item in report.coverage],
            "manifest": [item.to_dict() for item in report.manifest],
            "findings": [item.to_dict() for item in report.findings],
        }
