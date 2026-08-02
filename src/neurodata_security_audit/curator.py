"""Build curator checklists and compare two redacted audit reports."""

from __future__ import annotations

import csv
import hashlib
from html import escape
import io
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

_MAX_REPORT_BYTES = 64 * 1024 * 1024
_SUMMARY_COUNT_KEYS = (
    "files_inspected",
    "files_skipped",
    "entries_total",
    "manifest_files",
    "container_members",
    "references_checked",
    "references_valid",
    "fully_inspected_metadata",
    "header_or_structure_only",
    "payload_not_opened",
    "unsupported_manual_review",
    "not_traversed",
    "findings_high",
    "findings_review",
    "findings_info",
)
_SUMMARY_BOOL_KEYS = (
    "manifest_recheck_passed",
    "release_tree_recheck_passed",
)
_COVERAGE_STATUSES = {
    "fully_inspected_metadata",
    "header_or_structure_only",
    "payload_not_opened",
    "unsupported_manual_review",
    "not_traversed",
}
_ENTRY_TYPES = {
    "file",
    "directory",
    "format_directory",
    "symlink",
    "other",
    "unreadable",
}
_MEMBER_TYPES = {
    "file",
    "directory",
    "symlink",
    "hardlink",
    "special",
    "unknown",
}
_REFERENCE_STATUSES = {
    "valid_internal",
    "missing",
    "external",
    "through_symlink",
    "case_mismatch",
    "not_regular_file",
}
_SEVERITIES = {"high", "review", "info"}
_CHECKLIST_COLUMNS = (
    "source_report_sha256",
    "item_id",
    "kind",
    "priority",
    "code_or_status",
    "path",
    "location",
    "required_action",
    "curator_decision",
    "decision_note",
    "tool_used",
    "scientific_check",
    "completed",
)
_STATE_ORDER = {"new": 0, "remaining": 1, "resolved": 2}
_PRIORITY_ORDER = {"high": 0, "review": 1, "info": 2}


def _require_exact_keys(
    value: object,
    expected: set[str],
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    if set(value) != expected:
        raise ValueError(f"{label} has missing or unexpected fields")
    return value


def _require_string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    return value


def _require_count(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _require_records(
    value: object,
    fields: set[str],
    label: str,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return [
        _require_exact_keys(record, fields, f"{label} item")
        for record in value
    ]


def _validate_report(data: object) -> dict[str, Any]:
    report = _require_exact_keys(
        data,
        {
            "schema_version",
            "scanner_version",
            "summary",
            "files_inspected",
            "skipped_files",
            "coverage",
            "manifest",
            "container_members",
            "references",
            "findings",
        },
        "Audit report",
    )
    if report["schema_version"] != "2":
        raise ValueError("Audit report schema_version must be 2")
    _require_string(report["scanner_version"], "scanner_version")

    summary = _require_exact_keys(
        report["summary"],
        set(_SUMMARY_COUNT_KEYS) | set(_SUMMARY_BOOL_KEYS),
        "Audit report summary",
    )
    for key in _SUMMARY_COUNT_KEYS:
        _require_count(summary[key], f"summary.{key}")
    for key in _SUMMARY_BOOL_KEYS:
        if not isinstance(summary[key], bool):
            raise ValueError(f"summary.{key} must be a boolean")

    if not isinstance(report["files_inspected"], list) or not all(
        isinstance(path, str) for path in report["files_inspected"]
    ):
        raise ValueError("files_inspected must be an array of strings")

    skipped = _require_records(
        report["skipped_files"],
        {"path", "reason"},
        "skipped_files",
    )
    for record in skipped:
        _require_string(record["path"], "skipped_files.path")
        _require_string(record["reason"], "skipped_files.reason")

    coverage = _require_records(
        report["coverage"],
        {"path", "entry_type", "status", "reason"},
        "coverage",
    )
    for record in coverage:
        _require_string(record["path"], "coverage.path")
        _require_string(record["reason"], "coverage.reason")
        if record["entry_type"] not in _ENTRY_TYPES:
            raise ValueError("coverage.entry_type is invalid")
        if record["status"] not in _COVERAGE_STATUSES:
            raise ValueError("coverage.status is invalid")

    manifest = _require_records(
        report["manifest"],
        {"path", "size_bytes", "sha256"},
        "manifest",
    )
    for record in manifest:
        _require_string(record["path"], "manifest.path")
        _require_count(record["size_bytes"], "manifest.size_bytes")
        digest = _require_string(record["sha256"], "manifest.sha256")
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("manifest.sha256 is invalid")

    members = _require_records(
        report["container_members"],
        {
            "container_path",
            "member_path",
            "member_type",
            "size_bytes",
            "compressed_bytes",
            "encrypted",
        },
        "container_members",
    )
    for record in members:
        _require_string(record["container_path"], "container_members.container_path")
        _require_string(record["member_path"], "container_members.member_path")
        if record["member_type"] not in _MEMBER_TYPES:
            raise ValueError("container_members.member_type is invalid")
        _require_count(record["size_bytes"], "container_members.size_bytes")
        _require_count(record["compressed_bytes"], "container_members.compressed_bytes")
        if not isinstance(record["encrypted"], bool):
            raise ValueError("container_members.encrypted must be a boolean")

    references = _require_records(
        report["references"],
        {"source_path", "location", "target", "status", "reason"},
        "references",
    )
    for record in references:
        for key in ("source_path", "location", "target", "reason"):
            _require_string(record[key], f"references.{key}")
        if record["status"] not in _REFERENCE_STATUSES:
            raise ValueError("references.status is invalid")

    findings = _require_records(
        report["findings"],
        {"code", "severity", "path", "location", "evidence", "message"},
        "findings",
    )
    for record in findings:
        for key in ("code", "path", "location", "evidence", "message"):
            _require_string(record[key], f"findings.{key}")
        if record["severity"] not in _SEVERITIES:
            raise ValueError("findings.severity is invalid")

    expected_counts = {
        "files_inspected": len(report["files_inspected"]),
        "files_skipped": len(skipped),
        "entries_total": len(coverage),
        "manifest_files": len(manifest),
        "container_members": len(members),
        "references_checked": len(references),
        "references_valid": sum(
            record["status"] == "valid_internal" for record in references
        ),
    }
    expected_counts.update(
        {
            status: sum(record["status"] == status for record in coverage)
            for status in _COVERAGE_STATUSES
        }
    )
    expected_counts.update(
        {
            f"findings_{severity}": sum(
                record["severity"] == severity for record in findings
            )
            for severity in _SEVERITIES
        }
    )
    for key, expected in expected_counts.items():
        if summary[key] != expected:
            raise ValueError(f"summary.{key} does not match report records")
    return report


def load_report(path: Path) -> dict[str, Any]:
    """Load one bounded JSON report and validate its complete contract."""
    with path.open("rb") as stream:
        payload = stream.read(_MAX_REPORT_BYTES + 1)
    if len(payload) > _MAX_REPORT_BYTES:
        raise ValueError("Audit report is larger than 64 MiB")
    return _validate_report(json.loads(payload.decode("utf-8")))


def _item_id(kind: str, record: dict[str, object]) -> str:
    payload = json.dumps(
        {"kind": kind, **record},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def report_sha256(report: dict[str, Any]) -> str:
    """Hash canonical report content independently of JSON whitespace."""
    payload = json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _finding_item(finding: dict[str, object]) -> dict[str, str]:
    identity = {
        key: str(finding.get(key, ""))
        for key in ("code", "severity", "path", "location", "evidence", "message")
    }
    return {
        "item_id": _item_id("finding", identity),
        "kind": "finding",
        "priority": identity["severity"],
        "code_or_status": identity["code"],
        "path": identity["path"],
        "location": identity["location"],
        "required_action": identity["message"],
    }


def _coverage_item(entry: dict[str, object]) -> dict[str, str]:
    identity = {
        key: str(entry.get(key, ""))
        for key in ("path", "entry_type", "status", "reason")
    }
    return {
        "item_id": _item_id("coverage_gap", identity),
        "kind": "coverage_gap",
        "priority": "review",
        "code_or_status": identity["status"],
        "path": identity["path"],
        "location": identity["entry_type"],
        "required_action": (
            f"{identity['reason']}. Review with a format-aware tool or document "
            "why this coverage gap is acceptable."
        ),
    }


def review_items(
    report: dict[str, Any],
    *,
    include_information: bool,
) -> list[dict[str, str]]:
    """Return deterministic redacted review items from one report."""
    items = []
    for finding in report["findings"]:
        if not isinstance(finding, dict):
            raise ValueError("Each finding must be an object")
        severity = str(finding.get("severity", ""))
        if severity not in {"high", "review", "info"}:
            raise ValueError("Finding severity is invalid")
        if include_information or severity in {"high", "review"}:
            items.append(_finding_item(finding))
    for entry in report["coverage"]:
        if not isinstance(entry, dict):
            raise ValueError("Each coverage entry must be an object")
        if entry.get("status") in {"unsupported_manual_review", "not_traversed"}:
            items.append(_coverage_item(entry))
    return sorted(
        items,
        key=lambda item: (
            _PRIORITY_ORDER[item["priority"]],
            item["kind"],
            item["path"],
            item["location"],
            item["code_or_status"],
            item["item_id"],
        ),
    )


def _spreadsheet_safe(value: object) -> str:
    text = str(value).replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    stripped = text.lstrip()
    if stripped.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def render_checklist_tsv(report: dict[str, Any]) -> str:
    """Render a no-overwrite curator checklist without detected evidence."""
    report = _validate_report(report)
    if not _integrity_ok(report):
        raise ValueError("Checklist requires both integrity rechecks to pass")
    source_hash = report_sha256(report)
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(_CHECKLIST_COLUMNS)
    for item in review_items(report, include_information=False):
        row = (
            source_hash,
            item["item_id"],
            item["kind"],
            item["priority"],
            item["code_or_status"],
            item["path"],
            item["location"],
            item["required_action"],
            "",
            "",
            "",
            "",
            "",
        )
        writer.writerow(_spreadsheet_safe(value) for value in row)
    return output.getvalue()


def _integrity_ok(report: dict[str, Any]) -> bool:
    summary = report["summary"]
    return bool(
        summary.get("manifest_recheck_passed")
        and summary.get("release_tree_recheck_passed")
    )


def _release_paths(report: dict[str, Any]) -> set[str]:
    return {
        str(entry.get("path", ""))
        for entry in report["coverage"]
        if isinstance(entry, dict) and entry.get("path")
    }


def _release_state(report: dict[str, Any]) -> str:
    if not _integrity_ok(report):
        return "stop_integrity"
    if any(finding["severity"] == "high" for finding in report["findings"]):
        return "hold_high"
    if any(finding["severity"] == "review" for finding in report["findings"]):
        return "hold_review"
    if any(
        entry["status"] in {"unsupported_manual_review", "not_traversed"}
        for entry in report["coverage"]
    ):
        return "hold_coverage"
    return "no_automated_hold"


def compare_reports(
    baseline: dict[str, Any],
    current: dict[str, Any],
    *,
    same_dataset_confirmed: bool,
) -> dict[str, object]:
    """Compare two redacted reports and classify review items."""
    baseline = _validate_report(baseline)
    current = _validate_report(current)
    if not same_dataset_confirmed:
        raise ValueError("The curator must confirm both reports are for one dataset")
    if not _integrity_ok(baseline) or not _integrity_ok(current):
        raise ValueError("Both reports must pass both integrity rechecks")
    if baseline["schema_version"] != current["schema_version"]:
        raise ValueError("Audit reports use different schema versions")
    baseline_paths = _release_paths(baseline)
    current_paths = _release_paths(current)
    shared_paths = baseline_paths.intersection(current_paths)
    if not baseline_paths or not current_paths or not shared_paths:
        raise ValueError("Audit reports have no shared release paths")

    baseline_items = {
        item["item_id"]: item
        for item in review_items(baseline, include_information=True)
    }
    current_items = {
        item["item_id"]: item
        for item in review_items(current, include_information=True)
    }
    rows = []
    for item_id in baseline_items.keys() | current_items.keys():
        if item_id in baseline_items and item_id in current_items:
            state = "remaining"
            item = current_items[item_id]
        elif item_id in current_items:
            state = "new"
            item = current_items[item_id]
        else:
            state = "resolved"
            item = baseline_items[item_id]
        rows.append({"state": state, **item})
    rows.sort(
        key=lambda item: (
            _STATE_ORDER[item["state"]],
            _PRIORITY_ORDER[item["priority"]],
            item["kind"],
            item["path"],
            item["location"],
            item["code_or_status"],
            item["item_id"],
        )
    )
    counts = {
        state: sum(item["state"] == state for item in rows)
        for state in ("new", "remaining", "resolved")
    }
    return {
        "comparison_schema_version": "1",
        "baseline": {
            "report_schema_version": str(baseline["schema_version"]),
            "scanner_version": str(baseline["scanner_version"]),
            "report_sha256": report_sha256(baseline),
            "release_state": _release_state(baseline),
        },
        "current": {
            "report_schema_version": str(current["schema_version"]),
            "scanner_version": str(current["scanner_version"]),
            "report_sha256": report_sha256(current),
            "release_state": _release_state(current),
        },
        "dataset_identity": {
            "curator_confirmed_same_dataset": True,
            "baseline_entries": len(baseline_paths),
            "current_entries": len(current_paths),
            "shared_entries": len(shared_paths),
        },
        "summary": counts,
        "items": rows,
    }


def render_comparison_json(comparison: dict[str, object]) -> str:
    return json.dumps(
        comparison,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _markdown_text(value: object) -> str:
    text = (
        escape(str(value), quote=False)
        .replace("\\", "\\\\")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )
    return re.sub(r"([`*_\[\]()!|])", r"\\\1", text)


def render_comparison_markdown(comparison: dict[str, object]) -> str:
    summary = comparison["summary"]
    current = comparison["current"]
    dataset_identity = comparison["dataset_identity"]
    lines = [
        "# NeuroData audit comparison",
        "",
        (
            "This compares already masked audit records. A resolved item is no "
            "longer reported; it is not proof of anonymity, compliance or "
            "scientific equivalence."
        ),
        (
            "Keep this comparison private. Unrecognized identifying text may "
            "remain in relative paths or locations."
        ),
        "",
        "## Summary",
        "",
        f"- Current release state: `{current['release_state']}`",
        (
            "- Dataset identity: curator confirmed; "
            f"{dataset_identity['shared_entries']} shared release "
            f"path{'s' if dataset_identity['shared_entries'] != 1 else ''}"
        ),
        f"- New: {summary['new']}",
        f"- Remaining: {summary['remaining']}",
        f"- Resolved: {summary['resolved']}",
        "",
        "## Review items",
        "",
    ]
    items = comparison["items"]
    if not items:
        lines.append("No review items in either report.")
    else:
        lines.extend(
            [
                "| State | Priority | Type | Code or status | Path | "
                "Location | Required action |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for item in items:
            values = (
                item["state"],
                item["priority"],
                item["kind"],
                item["code_or_status"],
                item["path"],
                item["location"],
                item["required_action"],
            )
            lines.append(
                "| "
                + " | ".join(_markdown_text(value) for value in values)
                + " |"
            )
    return "\n".join(lines) + "\n"


def write_text_new(path: Path, content: str) -> None:
    """Write one new UTF-8 artifact without replacing an existing file."""
    write_texts_new({path: content})


def write_texts_new(outputs: dict[Path, str]) -> None:
    """Atomically publish related UTF-8 artifacts without replacing any path."""
    targets: list[tuple[Path, str]] = []
    for supplied, content in outputs.items():
        expanded = supplied.expanduser().absolute()
        if os.path.lexists(expanded):
            raise FileExistsError("Output path already exists")
        expanded.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target = expanded.parent.resolve(strict=True) / expanded.name
        targets.append((target, content))

    paths = [path for path, _ in targets]
    if len(set(paths)) != len(paths):
        raise ValueError("Output paths must be different")
    if any(os.path.lexists(path) for path in paths):
        raise FileExistsError("Output path already exists")

    prepared: list[tuple[Path, Path, tuple[int, int]]] = []
    published: list[tuple[Path, Path, tuple[int, int]]] = []
    try:
        for target, content in targets:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{target.name}.",
                suffix=".tmp",
                dir=target.parent,
            )
            temporary = Path(temporary_name)
            try:
                os.fchmod(descriptor, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                metadata = temporary.lstat()
                prepared.append(
                    (target, temporary, (metadata.st_dev, metadata.st_ino))
                )
            except BaseException:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
                temporary.unlink(missing_ok=True)
                raise

        if any(os.path.lexists(target) for target, _, _ in prepared):
            raise FileExistsError("Output path already exists")
        for target, temporary, identity in prepared:
            os.link(temporary, target, follow_symlinks=False)
            published.append((target, temporary, identity))
            _fsync_directory(target.parent)
    except BaseException:
        for target, _, identity in reversed(published):
            _unlink_if_identity(target, identity)
        raise
    finally:
        for _, temporary, _ in prepared:
            temporary.unlink(missing_ok=True)
            _fsync_directory(temporary.parent)


def _unlink_if_identity(path: Path, identity: tuple[int, int]) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    if (metadata.st_dev, metadata.st_ino) == identity:
        path.unlink()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
