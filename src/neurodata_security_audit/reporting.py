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
        f"- Entries skipped: {summary['files_skipped']}",
        f"- Release entries accounted for: {summary['entries_total']}",
        f"- Files in the SHA-256 manifest: {summary['manifest_files']}",
        f"- Archive members inventoried: {summary['container_members']}",
        (
            f"- Internal references valid: {summary['references_valid']} / "
            f"{summary['references_checked']}"
        ),
        (
            "- Manifest recheck passed: "
            f"{'yes' if summary['manifest_recheck_passed'] else 'no'}"
        ),
        f"- High-severity findings: {summary['findings_high']}",
        f"- Review findings: {summary['findings_review']}",
        f"- Informational findings: {summary['findings_info']}",
        "",
        "## Coverage",
        "",
        (
            "- Fully inspected metadata: "
            f"{summary['fully_inspected_metadata']}"
        ),
        (
            "- Header or structure only: "
            f"{summary['header_or_structure_only']}"
        ),
        f"- Signal or image payload not opened: {summary['payload_not_opened']}",
        (
            "- Unsupported and needs manual review: "
            f"{summary['unsupported_manual_review']}"
        ),
        f"- Inventoried but not parsed: {summary['not_traversed']}",
        "",
        (
            "Coverage describes what the scanner read. It is separate from the "
            "privacy findings below."
        ),
        "",
        "| Status | Type | Entry | Reason |",
        "|---|---|---|---|",
    ]
    for entry in data["coverage"]:
        values = [
            entry["status"],
            entry["entry_type"],
            entry["path"],
            entry["reason"],
        ]
        safe = [_markdown_text(value) for value in values]
        lines.append("| " + " | ".join(safe) + " |")

    lines.extend(["", "## Archive members", ""])
    container_members = data["container_members"]
    if container_members:
        lines.extend(
            [
                "| Archive | Member | Type | Bytes | Compressed bytes | Encrypted |",
                "|---|---|---|---:|---:|---|",
            ]
        )
        for item in container_members:
            values = [
                item["container_path"],
                item["member_path"],
                item["member_type"],
                item["size_bytes"],
                item["compressed_bytes"],
                "yes" if item["encrypted"] else "no",
            ]
            safe = [_markdown_text(value) for value in values]
            lines.append("| " + " | ".join(safe) + " |")
    else:
        lines.append("No supported archive members were inventoried.")

    lines.extend(["", "## Cross-file references", ""])
    references = data["references"]
    if references:
        lines.extend(
            [
                "| Source | Location | Target | Status | Reason |",
                "|---|---|---|---|---|",
            ]
        )
        for item in references:
            values = [
                item["source_path"],
                item["location"],
                item["target"],
                item["status"],
                item["reason"],
            ]
            safe = [_markdown_text(value) for value in values]
            lines.append("| " + " | ".join(safe) + " |")
    else:
        lines.append("No supported cross-file references were found.")

    lines.extend(
        [
            "",
            "## Findings",
            "",
        ]
    )
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

    lines.extend(["", "## Skipped files and directories", ""])
    skipped = data["skipped_files"]
    if skipped:
        for item in skipped:
            path = _markdown_text(item["path"])
            reason = _markdown_text(item["reason"])
            lines.append(f"- {path} — {reason}")
    else:
        lines.append("No skipped files.")

    lines.extend(
        [
            "",
            "## SHA-256 manifest",
            "",
            (
                "The manifest records regular files as they were read during this "
                "scan. Hashing is a streaming integrity check; it does not inspect "
                "EEG samples, image voxels or DICOM pixels."
            ),
            "",
        ]
    )
    manifest = data["manifest"]
    if manifest:
        lines.extend(
            [
                "| File | Bytes | SHA-256 |",
                "|---|---:|---|",
            ]
        )
        for item in manifest:
            path = _markdown_text(item["path"])
            size = _markdown_text(item["size_bytes"])
            digest = _markdown_text(item["sha256"])
            lines.append(f"| {path} | {size} | {digest} |")
    else:
        lines.append("No regular files were added to the manifest.")
    return "\n".join(lines) + "\n"
