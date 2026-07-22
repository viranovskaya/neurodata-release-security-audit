"""Small immutable objects used in audit reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["high", "review", "info"]

_SEVERITY_ORDER = {"high": 0, "review": 1, "info": 2}


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


@dataclass
class ScanReport:
    scanner_version: str
    files_inspected: list[str] = field(default_factory=list)
    skipped_files: list[SkippedFile] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    schema_version: str = "1"

    def normalized(self) -> "ScanReport":
        findings = sorted(set(self.findings), key=Finding.sort_key)
        skipped = sorted(set(self.skipped_files), key=lambda item: (item.path, item.reason))
        return ScanReport(
            scanner_version=self.scanner_version,
            files_inspected=sorted(set(self.files_inspected)),
            skipped_files=skipped,
            findings=findings,
            schema_version=self.schema_version,
        )

    def to_dict(self) -> dict[str, object]:
        report = self.normalized()
        counts = {severity: 0 for severity in ("high", "review", "info")}
        for finding in report.findings:
            counts[finding.severity] += 1
        return {
            "schema_version": report.schema_version,
            "scanner_version": report.scanner_version,
            "summary": {
                "files_inspected": len(report.files_inspected),
                "files_skipped": len(report.skipped_files),
                "findings_high": counts["high"],
                "findings_review": counts["review"],
                "findings_info": counts["info"],
            },
            "files_inspected": report.files_inspected,
            "skipped_files": [item.to_dict() for item in report.skipped_files],
            "findings": [item.to_dict() for item in report.findings],
        }
