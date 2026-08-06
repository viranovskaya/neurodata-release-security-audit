"""Build JSON and Markdown reports."""

from __future__ import annotations

import json
from collections.abc import Iterable
from html import escape

from .models import ScanReport, classify_release


def render_json(report: ScanReport) -> str:
    return (
        json.dumps(report.to_dict(), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    )


def _markdown_text(value: object) -> str:
    return (
        escape(str(value), quote=False)
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("|", "\\|")
    )


def _append_table(
    lines: list[str],
    headers: tuple[str, ...],
    separators: tuple[str, ...],
    rows: Iterable[tuple[object, ...]],
) -> None:
    lines.extend(
        [
            "| " + " | ".join(headers) + " |",
            "|" + "|".join(separators) + "|",
        ]
    )
    for row in rows:
        lines.append("| " + " | ".join(_markdown_text(value) for value in row) + " |")


def _append_detail_sections(lines: list[str], data: dict, findings: list[dict]) -> None:
    lines.extend(["", "## Archive members", ""])
    container_members = data["container_members"]
    if container_members:
        _append_table(
            lines,
            ("Archive", "Member", "Type", "Bytes", "Compressed bytes", "Encrypted"),
            ("---", "---", "---", "---:", "---:", "---"),
            (
                (
                    item["container_path"],
                    item["member_path"],
                    item["member_type"],
                    item["size_bytes"],
                    item["compressed_bytes"],
                    "yes" if item["encrypted"] else "no",
                )
                for item in container_members
            ),
        )
    else:
        lines.append("No supported archive members were inventoried.")

    lines.extend(["", "## Cross-file references", ""])
    references = data["references"]
    if references:
        _append_table(
            lines,
            ("Source", "Location", "Target", "Status", "Reason"),
            ("---", "---", "---", "---", "---"),
            (
                (
                    item["source_path"],
                    item["location"],
                    item["target"],
                    item["status"],
                    item["reason"],
                )
                for item in references
            ),
        )
    else:
        lines.append("No supported cross-file references were found.")

    lines.extend(["", "## Findings", ""])
    if findings:
        _append_table(
            lines,
            ("Severity", "Code", "File", "Location", "Evidence", "What to check"),
            ("---", "---", "---", "---", "---", "---"),
            (
                (
                    finding["severity"],
                    finding["code"],
                    finding["path"],
                    finding["location"],
                    finding["evidence"],
                    finding["message"],
                )
                for finding in findings
            ),
        )
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
        _append_table(
            lines,
            ("File", "Bytes", "SHA-256"),
            ("---", "---:", "---"),
            ((item["path"], item["size_bytes"], item["sha256"]) for item in manifest),
        )
    else:
        lines.append("No regular files were added to the manifest.")


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
        f"- Files and folders accounted for: {summary['entries_total']}",
        f"- Files in the SHA-256 manifest: {summary['manifest_files']}",
        (
            "- The accounted total includes files, folders, symlinks and "
            "unsupported filesystem entries. The manifest contains regular "
            "files only."
        ),
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
    release_state, coverage_gap_count = classify_release(summary)
    integrity_ok = release_state != "integrity_failed"
    if release_state == "integrity_failed":
        manifest_status = "passed" if summary["manifest_recheck_passed"] else "failed"
        tree_status = "passed" if summary["release_tree_recheck_passed"] else "failed"
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
    elif release_state in {"high_findings", "review_findings"}:
        severity = "high" if release_state == "high_findings" else "review"
        count = summary[f"findings_{severity}"]
        if severity == "high":
            decision = (
                "**Do not release this copy yet.** Resolve the "
                f"{count} high-priority finding"
                f"{'s' if count != 1 else ''} below first."
            )
        else:
            decision = (
                "**Review before release.** The scanner found "
                f"{count} item{'s' if count != 1 else ''} "
                "that need a curator decision."
            )
        lines.extend([decision, ""])
        remediation = [item for item in findings if item["severity"] == severity]
    elif release_state == "coverage_gaps":
        lines.extend(
            [
                (
                    "**No automated findings, but release remains on hold.** "
                    f"{coverage_gap_count} unsupported or untraversed "
                    f"{'entry' if coverage_gap_count == 1 else 'entries'} "
                    f"{'needs' if coverage_gap_count == 1 else 'need'} "
                    "a documented manual review."
                ),
                "",
            ]
        )
        remediation = []
    else:
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
        _append_table(
            lines,
            ("Priority", "File", "Field or location", "What to do"),
            ("---", "---", "---", "---"),
            (
                (
                    finding["severity"],
                    finding["path"],
                    finding["location"],
                    finding["message"],
                )
                for finding in remediation
            ),
        )
    else:
        if not integrity_ok:
            lines.append("Individual remediation is deferred until integrity passes.")
        elif coverage_gap_count:
            lines.append(
                "No automated remediation tasks. Review every coverage gap "
                "before making the release decision."
            )
        else:
            lines.append("No immediate remediation tasks.")

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
            f"- Fully inspected metadata: {summary['fully_inspected_metadata']}",
            f"- Header or structure only: {summary['header_or_structure_only']}",
            f"- Signal or image payload not opened: {summary['payload_not_opened']}",
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
        ]
    )
    _append_table(
        lines,
        ("Status", "Type", "Entry", "Reason"),
        ("---", "---", "---", "---"),
        (
            (entry["status"], entry["entry_type"], entry["path"], entry["reason"])
            for entry in data["coverage"]
        ),
    )

    lines.extend(["", "## Places needing manual review", ""])
    coverage_gaps = [
        entry
        for entry in data["coverage"]
        if entry["status"] in {"unsupported_manual_review", "not_traversed"}
    ]
    if coverage_gaps:
        _append_table(
            lines,
            ("Status", "Entry", "Why manual review is needed"),
            ("---", "---", "---"),
            (
                (entry["status"], entry["path"], entry["reason"])
                for entry in coverage_gaps
            ),
        )
    else:
        lines.append("No unsupported or untraversed files or folders.")

    _append_detail_sections(lines, data, findings)
    return "\n".join(lines) + "\n"
