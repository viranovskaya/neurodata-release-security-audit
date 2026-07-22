"""Safe dataset traversal and format dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .detectors import scan_text
from .models import Finding, ScanReport, SkippedFile
from .readers import decode_small_text, inspect_brainvision, inspect_edf_header
from .structured import inspect_delimited, inspect_json

_TEXT_SUFFIXES = {".tsv", ".json", ".txt", ".md", ".csv", ".log", ".vhdr", ".vmrk"}
_TEXT_NAMES = {"README", "CHANGES"}
_SIGNAL_PAYLOAD_SUFFIXES = {".eeg"}
_EDF_SUFFIXES = {".edf", ".bdf"}
_UNEXPECTED_SUFFIXES = {".xlsx", ".xls", ".ods", ".bak", ".old", ".tmp", ".zip", ".7z", ".rar"}
_IGNORED_DIRECTORIES = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
_KEY_TERMS = ("participant", "subject", "patient", "identifier", "identity")
_MAPPING_TERMS = ("key", "map", "mapping", "link", "lookup", "names")


@dataclass(frozen=True)
class ScanPolicy:
    max_text_bytes: int = 2 * 1024 * 1024


def _unexpected_file_findings(relative_path: str) -> list[Finding]:
    path = Path(relative_path)
    lower_name = path.name.lower()
    findings: list[Finding] = []
    if path.suffix.lower() in _UNEXPECTED_SUFFIXES:
        findings.append(
            Finding(
                code="UNEXPECTED_FILE",
                severity="review",
                path=relative_path,
                location="filename",
                evidence=f"<file-extension:{path.suffix.lower() or 'none'}>",
                message="This file type is unusual in a public EEG/BIDS release.",
            )
        )
    if any(term in lower_name for term in _KEY_TERMS) and any(
        term in lower_name for term in _MAPPING_TERMS
    ):
        findings.append(
            Finding(
                code="SUBJECT_KEY_FILE",
                severity="high",
                path=relative_path,
                location="filename",
                evidence="<redacted:participant-key-filename>",
                message="The filename suggests a participant identity mapping file.",
            )
        )
    return findings


def _walk(root: Path):
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            entries = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError:
            relative_path = directory.relative_to(root).as_posix() or "."
            yield "directory_error", directory, relative_path
            continue
        subdirectories: list[Path] = []
        for entry in entries:
            relative_path = entry.relative_to(root).as_posix()
            try:
                if entry.is_symlink():
                    yield "symlink", entry, relative_path
                elif entry.is_dir():
                    if entry.name not in _IGNORED_DIRECTORIES:
                        subdirectories.append(entry)
                elif entry.is_file():
                    yield "file", entry, relative_path
            except OSError:
                yield "entry_error", entry, relative_path
        pending.extend(reversed(subdirectories))


def scan_dataset(dataset_root: str | Path, policy: ScanPolicy | None = None) -> ScanReport:
    policy = policy or ScanPolicy()
    root = Path(dataset_root).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"Dataset directory does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Dataset path is not a directory: {root}")
    root = root.resolve()
    report = ScanReport(scanner_version=__version__)

    for kind, path, relative_path in _walk(root):
        if kind in {"directory_error", "entry_error"}:
            report.findings.append(
                Finding(
                    code="UNREADABLE_DIRECTORY" if kind == "directory_error" else "UNREADABLE_ENTRY",
                    severity="review",
                    path=relative_path,
                    location="filesystem traversal",
                    evidence="<redacted:filesystem-error>",
                    message="The scanner could not inspect this filesystem entry.",
                )
            )
            report.skipped_files.append(
                SkippedFile(relative_path, "Filesystem entry could not be inspected")
            )
            continue

        if kind == "symlink":
            try:
                path.stat()
                target = path.resolve(strict=False)
                try:
                    target.relative_to(root)
                    code = "SYMLINK_REVIEW"
                    message = "A symlink is present and was not followed."
                except ValueError:
                    code = "EXTERNAL_SYMLINK"
                    message = "A symlink points outside the dataset and was not followed."
            except (OSError, RuntimeError):
                code = "UNRESOLVED_SYMLINK"
                message = "A symlink target could not be resolved and was not followed."
            report.findings.append(
                Finding(
                    code=code,
                    severity="review",
                    path=relative_path,
                    location="filesystem entry",
                    evidence="<redacted:symlink-target>",
                    message=message,
                )
            )
            report.skipped_files.append(
                SkippedFile(relative_path, "Symlinks are not followed")
            )
            continue

        report.findings.extend(_unexpected_file_findings(relative_path))
        suffix = path.suffix.lower()
        try:
            if suffix in _TEXT_SUFFIXES or path.name in _TEXT_NAMES:
                size = path.stat().st_size
                if size > policy.max_text_bytes:
                    report.findings.append(
                        Finding(
                            code="TEXT_FILE_TOO_LARGE",
                            severity="review",
                            path=relative_path,
                            location="file size",
                            evidence=f"<bytes:{size}>",
                            message="The text file exceeds the configured scan limit.",
                        )
                    )
                    report.skipped_files.append(
                        SkippedFile(relative_path, "Text file exceeds configured scan limit")
                    )
                    continue
                data = path.read_bytes()
                text = decode_small_text(data)
                report.files_inspected.append(relative_path)
                report.findings.extend(scan_text(text, relative_path))
                if suffix == ".json":
                    report.findings.extend(inspect_json(text, relative_path))
                elif suffix == ".tsv":
                    report.findings.extend(inspect_delimited(text, relative_path, "\t"))
                elif suffix == ".csv":
                    report.findings.extend(inspect_delimited(text, relative_path, ","))
                if suffix in {".vhdr", ".vmrk"}:
                    report.findings.extend(inspect_brainvision(text, relative_path))
            elif suffix in _EDF_SUFFIXES:
                with path.open("rb") as stream:
                    header = stream.read(256)
                report.files_inspected.append(relative_path)
                report.findings.extend(inspect_edf_header(header, relative_path))
            elif suffix in _SIGNAL_PAYLOAD_SUFFIXES:
                report.skipped_files.append(
                    SkippedFile(relative_path, "EEG signal payload is outside the MVP scope")
                )
            else:
                report.skipped_files.append(
                    SkippedFile(relative_path, "File format is not inspected by the MVP")
                )
        except (OSError, UnicodeError) as error:
            report.skipped_files.append(
                SkippedFile(relative_path, f"Could not inspect file: {type(error).__name__}")
            )
            report.findings.append(
                Finding(
                    code="UNREADABLE_FILE",
                    severity="review",
                    path=relative_path,
                    location="file read",
                    evidence=f"<error:{type(error).__name__}>",
                    message="The scanner could not inspect this file.",
                )
            )
    return report.normalized()
