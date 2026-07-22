"""Walk a dataset and run the relevant checks."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

from . import __version__
from .detectors import (
    KnownTermMatcher,
    find_emails,
    find_sensitive_path_values,
    redacted,
    scan_text,
)
from .models import Finding, ScanReport, SkippedFile
from .readers import (
    FormatReaderUnavailable,
    decode_small_text,
    inspect_brainvision,
    inspect_edf_header,
    inspect_eeglab_metadata,
    inspect_mne_format,
)
from .structured import inspect_delimited, inspect_json, inspect_xml

_TEXT_SUFFIXES = {
    ".bash",
    ".cfg",
    ".conf",
    ".csv",
    ".html",
    ".ini",
    ".ipynb",
    ".js",
    ".json",
    ".key",
    ".log",
    ".m",
    ".md",
    ".pem",
    ".ps1",
    ".py",
    ".r",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsv",
    ".txt",
    ".vhdr",
    ".vmrk",
    ".xml",
    ".yaml",
    ".yml",
    ".zsh",
}
_TEXT_NAMES = {
    ".env",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "CHANGES",
    "Dockerfile",
    "id_ed25519",
    "id_rsa",
    "Makefile",
    "README",
}
_SIGNAL_PAYLOAD_SUFFIXES = {".eeg", ".fdt"}
_EDF_SUFFIXES = {".edf", ".bdf"}
_MNE_FILE_FORMATS = {".fif": "fif", ".set": "eeglab"}
_UNEXPECTED_SUFFIXES = {
    ".7z",
    ".bak",
    ".key",
    ".ods",
    ".old",
    ".orig",
    ".p12",
    ".pem",
    ".pfx",
    ".rar",
    ".rej",
    ".swo",
    ".swp",
    ".tmp",
    ".xls",
    ".xlsx",
    ".zip",
}
_SENSITIVE_CONFIG_NAMES = {
    ".env",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "credentials.json",
    "id_ed25519",
    "id_rsa",
    "secrets.json",
}
_OS_METADATA_NAMES = {".ds_store", "desktop.ini", "thumbs.db"}
_IGNORED_DIRECTORIES = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
_KEY_TERMS = ("participant", "subject", "patient", "identifier", "identity")
_MAPPING_TERMS = ("key", "map", "mapping", "link", "lookup", "names")


@dataclass(frozen=True)
class ScanPolicy:
    max_text_bytes: int = 2 * 1024 * 1024
    sensitive_terms: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        terms: list[str] = []
        seen: set[str] = set()
        for value in self.sensitive_terms:
            term = value.strip()
            folded = term.casefold()
            if term and folded not in seen:
                terms.append(term)
                seen.add(folded)
        if len(terms) > 1000:
            raise ValueError("Sensitive term lists are limited to 1000 entries")
        if any(len(term) < 3 for term in terms):
            raise ValueError("Sensitive terms must contain at least three characters")
        object.__setattr__(self, "sensitive_terms", tuple(terms))


def _unexpected_file_findings(
    relative_path: str,
    known_terms: KnownTermMatcher,
) -> list[Finding]:
    path = Path(relative_path)
    lower_name = path.name.lower()
    findings: list[Finding] = []
    for email in find_emails(relative_path):
        findings.append(
            Finding(
                code="DIRECT_EMAIL",
                severity="high",
                path=relative_path,
                location="filename",
                evidence=redacted("email", email),
                message="Confirm this email is intentionally public; otherwise rename the path.",
            )
        )
    for term in known_terms.matches(relative_path):
        findings.append(
            Finding(
                code="KNOWN_IDENTIFIER",
                severity="high",
                path=relative_path,
                location="filename",
                evidence=redacted("known-identifier", term),
                message="Rename this path to remove the known name or identifier.",
            )
        )
    for code, kind, value, message in find_sensitive_path_values(relative_path):
        findings.append(
            Finding(
                code=code,
                severity="high",
                path=relative_path,
                location="filename",
                evidence=redacted(kind, value),
                message=message,
            )
        )
    if path.suffix.lower() in _UNEXPECTED_SUFFIXES:
        findings.append(
            Finding(
                code="UNEXPECTED_FILE",
                severity="review",
                path=relative_path,
                location="filename",
                evidence=f"<file-extension:{path.suffix.lower() or 'none'}>",
                message="Confirm this file belongs in the release; otherwise remove it.",
            )
        )
    if lower_name in _SENSITIVE_CONFIG_NAMES or lower_name.startswith(".env."):
        findings.append(
            Finding(
                code="SENSITIVE_CONFIG_FILE",
                severity="review",
                path=relative_path,
                location="filename",
                evidence="<sensitive-config-file>",
                message="Confirm this configuration file contains no credential or private path.",
            )
        )
    if lower_name in _OS_METADATA_NAMES:
        findings.append(
            Finding(
                code="OS_METADATA_FILE",
                severity="review",
                path=relative_path,
                location="filename",
                evidence="<os-metadata-file>",
                message="Remove this operating-system metadata file from the release.",
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
                message="Keep participant identity keys outside the release directory.",
            )
        )
    return findings


def _redact_report_paths(report: ScanReport, known_terms: KnownTermMatcher) -> ScanReport:
    paths = (
        report.files_inspected
        + [item.path for item in report.skipped_files]
        + [item.path for item in report.findings]
    )
    path_emails = tuple(
        sorted(
            {email for path in paths for email in find_emails(path)},
            key=str.casefold,
        )
    )
    email_terms = KnownTermMatcher(path_emails, label="email")
    sensitive_path_values = tuple(
        sorted(
            {
                value
                for path in paths
                for _, _, value, _ in find_sensitive_path_values(path)
            },
            key=str.casefold,
        )
    )
    sensitive_path_terms = KnownTermMatcher(
        sensitive_path_values,
        label="sensitive-path",
    )
    if (
        not known_terms.terms
        and not email_terms.terms
        and not sensitive_path_terms.terms
    ):
        return report

    def redact_path(path: str) -> str:
        return sensitive_path_terms.redact(
            email_terms.redact(known_terms.redact(path))
        )

    return ScanReport(
        scanner_version=report.scanner_version,
        schema_version=report.schema_version,
        files_inspected=[redact_path(path) for path in report.files_inspected],
        skipped_files=[
            replace(item, path=redact_path(item.path))
            for item in report.skipped_files
        ],
        findings=[
            replace(item, path=redact_path(item.path))
            for item in report.findings
        ],
    )


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
                    if entry.name in _IGNORED_DIRECTORIES:
                        yield "ignored_directory", entry, relative_path
                    else:
                        if entry.suffix.lower() == ".mff":
                            yield "format_directory", entry, relative_path
                        subdirectories.append(entry)
                elif entry.is_file():
                    yield "file", entry, relative_path
            except OSError:
                yield "entry_error", entry, relative_path
        pending.extend(reversed(subdirectories))


def _mne_format_for_path(path: Path) -> str | None:
    if path.name.lower().endswith(".fif.gz"):
        return "fif"
    return _MNE_FILE_FORMATS.get(path.suffix.lower())


def scan_dataset(dataset_root: str | Path, policy: ScanPolicy | None = None) -> ScanReport:
    policy = policy or ScanPolicy()
    root = Path(dataset_root).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"Dataset directory does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Dataset path is not a directory: {root}")
    root = root.resolve()
    report = ScanReport(scanner_version=__version__)
    known_terms = KnownTermMatcher(policy.sensitive_terms)

    for kind, path, relative_path in _walk(root):
        if kind in {"directory_error", "entry_error"}:
            report.findings.append(
                Finding(
                    code=(
                        "UNREADABLE_DIRECTORY"
                        if kind == "directory_error"
                        else "UNREADABLE_ENTRY"
                    ),
                    severity="review",
                    path=relative_path,
                    location="filesystem traversal",
                    evidence="<redacted:filesystem-error>",
                    message="Review this entry manually and fix its access before release.",
                )
            )
            report.skipped_files.append(
                SkippedFile(relative_path, "Filesystem entry could not be inspected")
            )
            continue

        if kind == "ignored_directory":
            report.findings.append(
                Finding(
                    code="UNEXPECTED_DIRECTORY",
                    severity="review",
                    path=relative_path,
                    location="directory name",
                    evidence=f"<directory:{path.name}>",
                    message=(
                        "Remove this development directory from the release or "
                        "review it manually."
                    ),
                )
            )
            report.skipped_files.append(
                SkippedFile(relative_path, "Development directory is not inspected")
            )
            continue

        if kind == "format_directory":
            try:
                report.findings.extend(
                    inspect_mne_format(path, relative_path, "mff", known_terms)
                )
                report.files_inspected.append(relative_path)
            except FormatReaderUnavailable:
                report.findings.append(
                    Finding(
                        code="FORMAT_READER_UNAVAILABLE",
                        severity="review",
                        path=relative_path,
                        location="MFF recording metadata",
                        evidence="<optional-reader-unavailable>",
                        message=(
                            "Install the 'formats' extra to inspect the MFF recording as a whole. "
                            "Its bounded XML files are still checked separately."
                        ),
                    )
                )
                report.skipped_files.append(
                    SkippedFile(
                        relative_path,
                        "MFF recording reader is unavailable; XML files are still inspected",
                    )
                )
            except Exception as error:
                report.findings.append(
                    Finding(
                        code="FORMAT_METADATA_UNREADABLE",
                        severity="review",
                        path=relative_path,
                        location="MFF recording metadata",
                        evidence=f"<error:{type(error).__name__}>",
                        message=(
                            "Review this MFF recording manually; its recording metadata could "
                            "not be read. Bounded XML files are still checked separately."
                        ),
                    )
                )
                report.skipped_files.append(
                    SkippedFile(
                        relative_path,
                        f"Could not inspect MFF recording metadata: {type(error).__name__}",
                    )
                )
            continue

        if kind == "symlink":
            try:
                link_value = path.readlink()
                target = link_value if link_value.is_absolute() else path.parent / link_value
                target = Path(os.path.abspath(target))
                if target == path:
                    code = "UNRESOLVED_SYMLINK"
                    message = "Fix or remove this self-referencing symlink."
                else:
                    try:
                        target.relative_to(root)
                        code = "SYMLINK_REVIEW"
                        message = "Review this symlink manually; the scanner did not follow it."
                    except ValueError:
                        code = "EXTERNAL_SYMLINK"
                        message = (
                            "Remove or replace this symlink because it points outside "
                            "the dataset."
                        )
            except (OSError, RuntimeError):
                code = "UNRESOLVED_SYMLINK"
                message = (
                    "Fix or remove this symlink because its target could not be "
                    "classified safely."
                )
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

        report.findings.extend(_unexpected_file_findings(relative_path, known_terms))
        suffix = path.suffix.lower()
        mne_format = _mne_format_for_path(path)
        try:
            if (
                suffix in _TEXT_SUFFIXES
                or path.name in _TEXT_NAMES
                or path.name.lower().startswith(".env.")
            ):
                size = path.stat().st_size
                if size > policy.max_text_bytes:
                    report.findings.append(
                        Finding(
                            code="TEXT_FILE_TOO_LARGE",
                            severity="review",
                            path=relative_path,
                            location="file size",
                            evidence=f"<bytes:{size}>",
                            message=(
                                "Review this file manually or raise the limit after "
                                "checking its format."
                            ),
                        )
                    )
                    report.skipped_files.append(
                        SkippedFile(relative_path, "Text file exceeds configured scan limit")
                    )
                    continue
                data = path.read_bytes()
                text = decode_small_text(data)
                report.files_inspected.append(relative_path)
                report.findings.extend(scan_text(text, relative_path, known_terms))
                if suffix == ".json":
                    report.findings.extend(inspect_json(text, relative_path))
                elif suffix == ".tsv":
                    report.findings.extend(inspect_delimited(text, relative_path, "\t"))
                elif suffix == ".csv":
                    report.findings.extend(inspect_delimited(text, relative_path, ","))
                elif suffix == ".xml":
                    report.findings.extend(inspect_xml(text, relative_path))
                if suffix in {".vhdr", ".vmrk"}:
                    report.findings.extend(inspect_brainvision(text, relative_path))
            elif suffix in _EDF_SUFFIXES:
                with path.open("rb") as stream:
                    header = stream.read(256)
                report.files_inspected.append(relative_path)
                report.findings.extend(
                    inspect_edf_header(header, relative_path, known_terms)
                )
            elif mne_format is not None:
                with path.open("rb") as stream:
                    prefix = stream.read(128)
                if not prefix:
                    report.files_inspected.append(relative_path)
                    report.findings.append(
                        Finding(
                            code="EMPTY_PLACEHOLDER",
                            severity="info",
                            path=relative_path,
                            location="file content",
                            evidence="<bytes:0>",
                            message=(
                                "Confirm this empty fixture is intentional; no format metadata "
                                "was checked."
                            ),
                        )
                    )
                    continue
                if prefix.startswith(b"version https://git-lfs.github.com/spec/v1"):
                    report.files_inspected.append(relative_path)
                    report.findings.append(
                        Finding(
                            code="GIT_LFS_POINTER",
                            severity="info",
                            path=relative_path,
                            location="file content",
                            evidence="<git-lfs-pointer>",
                            message="Fetch the Git LFS payload before relying on this audit.",
                        )
                    )
                    continue
                eeglab_metadata_reader_unavailable = False
                eeglab_skip_mne = False
                if mne_format == "eeglab":
                    try:
                        eeglab_findings = inspect_eeglab_metadata(
                            path,
                            relative_path,
                            known_terms,
                            root,
                        )
                        report.findings.extend(eeglab_findings)
                        eeglab_skip_mne = any(
                            finding.code
                            in {
                                "EEGLAB_METADATA_COVERAGE_LIMIT",
                                "EXTERNAL_DATA_REFERENCE",
                            }
                            for finding in eeglab_findings
                        )
                    except FormatReaderUnavailable:
                        eeglab_metadata_reader_unavailable = True
                    except Exception as error:
                        report.findings.append(
                            Finding(
                                code="EEGLAB_METADATA_UNREADABLE",
                                severity="review",
                                path=relative_path,
                                location="EEGLAB MATLAB metadata",
                                evidence=f"<error:{type(error).__name__}>",
                                message=(
                                    "Review this EEGLAB file manually; its private text fields "
                                    "could not be inspected safely."
                                ),
                            )
                        )
                if eeglab_skip_mne:
                    report.files_inspected.append(relative_path)
                    report.skipped_files.append(
                        SkippedFile(
                            relative_path,
                            "EEGLAB signal-safe metadata coverage is incomplete; "
                            "the MNE reader was not called",
                        )
                    )
                    continue
                try:
                    report.findings.extend(
                        inspect_mne_format(
                            path,
                            relative_path,
                            mne_format,
                            known_terms,
                        )
                    )
                    report.files_inspected.append(relative_path)
                    if eeglab_metadata_reader_unavailable:
                        report.findings.append(
                            Finding(
                                code="EEGLAB_METADATA_READER_UNAVAILABLE",
                                severity="review",
                                path=relative_path,
                                location="EEGLAB MATLAB metadata",
                                evidence="<optional-reader-unavailable>",
                                message=(
                                    "Install the 'formats' extra before relying on the audit of "
                                    "EEGLAB comments, history and source-file fields."
                                ),
                            )
                        )
                except FormatReaderUnavailable:
                    report.findings.append(
                        Finding(
                            code="FORMAT_READER_UNAVAILABLE",
                            severity="review",
                            path=relative_path,
                            location=f"{mne_format.upper()} metadata",
                            evidence="<optional-reader-unavailable>",
                            message="Install the 'formats' extra to inspect this file's metadata.",
                        )
                    )
                    report.skipped_files.append(
                        SkippedFile(relative_path, "Optional format reader is unavailable")
                    )
                except Exception as error:
                    report.findings.append(
                        Finding(
                            code="FORMAT_METADATA_UNREADABLE",
                            severity="review",
                            path=relative_path,
                            location=f"{mne_format.upper()} metadata",
                            evidence=f"<error:{type(error).__name__}>",
                            message="Review this file manually; its format metadata was not read.",
                        )
                    )
                    report.skipped_files.append(
                        SkippedFile(
                            relative_path,
                            f"Could not inspect format metadata: {type(error).__name__}",
                        )
                    )
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
                    message="Review this file manually and fix its access before release.",
                )
            )
    return _redact_report_paths(report, known_terms).normalized()
