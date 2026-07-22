"""Build JSON and Markdown reports."""

from __future__ import annotations

import json
from html import escape

from .models import ScanReport


def render_json(report: ScanReport) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _markdown_text(value: object) -> str:
    return (
        escape(str(value), quote=False)
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("|", "\\|")
    )


def render_markdown(report: ScanReport) -> str:
    data = report.to_dict()
    summary = data["summary"]
    lines = [
        "# NeuroData release security audit",
        "",
        (
            "This report identifies items that need review. It does not certify "
            "that the dataset is anonymous or compliant."
        ),
        (
            "Matched emails and private terms are masked in filenames. "
            "Review the report before sharing it."
        ),
        "",
        "## Summary",
        "",
        f"- Files inspected: {summary['files_inspected']}",
        f"- Files skipped: {summary['files_skipped']}",
        f"- High-severity findings: {summary['findings_high']}",
        f"- Review findings: {summary['findings_review']}",
        f"- Informational findings: {summary['findings_info']}",
        "",
        "## Findings",
        "",
    ]
    findings = data["findings"]
    if findings:
        lines.extend(
            [
                "| Severity | Code | File | Location | Evidence | What to check |",
                "|---|---|---|---|---|---|",
            ]
        )
        for finding in findings:
            values = [
                finding["severity"],
                finding["code"],
                finding["path"],
                finding["location"],
                finding["evidence"],
                finding["message"],
            ]
            safe = [_markdown_text(value) for value in values]
            lines.append("| " + " | ".join(safe) + " |")
    else:
        lines.append("No findings.")

    lines.extend(["", "## Skipped files", ""])
    skipped = data["skipped_files"]
    if skipped:
        for item in skipped:
            path = _markdown_text(item["path"])
            reason = _markdown_text(item["reason"])
            lines.append(f"- {path} — {reason}")
    else:
        lines.append("No skipped files.")
    return "\n".join(lines) + "\n"
