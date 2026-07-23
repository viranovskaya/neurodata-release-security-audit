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
        (
            "- Release-tree recheck passed: "
            f"{'yes' if summary['release_tree_recheck_passed'] else 'no'}"
        ),
        f"- High-severity findings: {summary['findings_high']}",
        f"- Review findings: {summary['findings_review']}",
        f"- Informational findings: {summary['findings_info']}",
        "",
        "## What to do next",
        "",
    ]
    findings = data["findings"]
    integrity_ok = (
        summary["manifest_recheck_passed"]
        and summary["release_tree_recheck_passed"]
    )
    if not integrity_ok:
        manifest_status = (
            "passed" if summary["manifest_recheck_passed"] else "failed"
        )
        tree_status = (
            "passed" if summary["release_tree_recheck_passed"] else "failed"
        )
        lines.extend(
            [
                (
                    "**Do not release or rely on this report yet.** The release "
                    "changed during the scan or could not be rechecked "
                    "consistently. Restore or stabilize the working copy and "
                    "rerun the audit before using the individual findings."
                ),
                "",
                f"- Manifest recheck: {manifest_status}",
                f"- Release-tree recheck: {tree_status}",
                "",
            ]
        )
        remediation = []
    elif summary["findings_high"]:
        lines.extend(
            [
                (
                    "**Do not release this copy yet.** Resolve the "
                    f"{summary['findings_high']} high-priority finding"
                    f"{'s' if summary['findings_high'] != 1 else ''} below first."
                ),
                "",
            ]
        )
        remediation = [
            item for item in findings if item["severity"] == "high"
        ]
    elif summary["findings_review"]:
        lines.extend(
            [
                (
                    "**Review before release.** The scanner found "
                    f"{summary['findings_review']} item"
                    f"{'s' if summary['findings_review'] != 1 else ''} "
                    "that need a curator decision."
                ),
                "",
            ]
        )
        remediation = [
            item for item in findings if item["severity"] == "review"
        ]
    elif integrity_ok:
        lines.extend(
            [
                (
                    "**No high or review findings in the areas checked.** "
                    "This is not proof of anonymity. Check the coverage gaps "
                    "and format limits before release."
                ),
                "",
            ]
        )
        remediation = []

    if remediation:
        lines.extend(
            [
                "| Priority | File | Field or location | What to do |",
                "|---|---|---|---|",
            ]
        )
        for finding in remediation:
            values = [
                finding["severity"],
                finding["path"],
                finding["location"],
                finding["message"],
            ]
            lines.append(
                "| "
                + " | ".join(_markdown_text(value) for value in values)
                + " |"
            )
    else:
        lines.append(
            "Individual remediation is deferred until integrity passes."
            if not integrity_ok
            else "No immediate remediation tasks."
        )

    if integrity_ok:
        lines.extend(
            [
                "",
                "After each correction:",
                "",
                "1. Work on a private copy and keep the original dataset unchanged.",
                (
                    "2. Use a format-aware tool for FIF, EDF/BDF, DICOM, NIfTI "
                    "and EEGLAB files."
                ),
                (
                    "3. Run the audit again and confirm the item is gone and "
                    "both integrity checks pass."
                ),
                (
                    "4. Verify that channels, sampling, annotations, duration "
                    "and other scientific properties did not change unexpectedly."
                ),
            ]
        )
    else:
        lines.extend(
            [
                "",
                "Restore a reliable scan:",
                "",
                "1. Stop any process that is writing to the release candidate.",
                (
                    "2. Restore the candidate from a known source or recreate it "
                    "in a stable private working directory."
                ),
                "3. Run the audit again without changing files during the scan.",
                (
                    "4. Continue to the finding list only after both integrity "
                    "checks pass."
                ),
            ]
        )

    lines.extend(
        [
            "",
            "The audit never deletes or rewrites research data automatically.",
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
            (
                "- Signal or image payload not opened: "
                f"{summary['payload_not_opened']}"
            ),
            (
                "- Unsupported and needs manual review: "
                f"{summary['unsupported_manual_review']}"
            ),
            f"- Inventoried but not parsed: {summary['not_traversed']}",
            "",
            (
                "Coverage describes what the scanner read. It is separate from "
                "the privacy findings below."
            ),
            "",
            "| Status | Type | Entry | Reason |",
            "|---|---|---|---|",
        ]
    )
    for entry in data["coverage"]:
        values = [
            entry["status"],
            entry["entry_type"],
            entry["path"],
            entry["reason"],
        ]
        safe = [_markdown_text(value) for value in values]
        lines.append("| " + " | ".join(safe) + " |")

    lines.extend(["", "## Places needing manual review", ""])
    coverage_gaps = [
        entry
        for entry in data["coverage"]
        if entry["status"] in {"unsupported_manual_review", "not_traversed"}
    ]
    if coverage_gaps:
        lines.extend(
            [
                "| Status | Entry | Why manual review is needed |",
                "|---|---|---|",
            ]
        )
        for entry in coverage_gaps:
            values = [entry["status"], entry["path"], entry["reason"]]
            lines.append(
                "| "
                + " | ".join(_markdown_text(value) for value in values)
                + " |"
            )
    else:
        lines.append("No unsupported or untraversed release entries.")

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
