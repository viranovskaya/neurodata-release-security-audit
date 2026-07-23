"""Walk a dataset and run the relevant checks."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, replace
from pathlib import Path

from . import __version__
from .containers import inspect_archive, is_archive_path
from .detectors import (
    KnownTermMatcher,
    find_emails,
    find_sensitive_path_values,
    redacted,
    scan_text,
)
from .imaging import inspect_dicom_metadata, inspect_nifti_metadata
from .models import (
    CoverageEntry,
    CoverageStatus,
    EntryType,
    Finding,
    ManifestEntry,
    ScanReport,
    SkippedFile,
)
from .readers import (
    FormatReaderUnavailable,
    decode_small_text,
    inspect_brainvision,
    inspect_edf_header,
    inspect_eeglab_metadata,
    inspect_mne_format,
)
from .references import (
    inspect_bids_json_references,
    inspect_brainvision_references,
)
from .structured import inspect_delimited, inspect_json, inspect_xml

_TEXT_SUFFIXES = {
    ".bash",
    ".cfg",
    ".code-workspace",
    ".conf",
    ".csv",
    ".diff",
    ".env",
    ".html",
    ".ini",
    ".ipynb",
    ".js",
    ".json",
    ".key",
    ".log",
    ".m",
    ".md",
    ".patch",
    ".pem",
    ".ps1",
    ".py",
    ".r",
    ".sh",
    ".sql",
    ".sublime-project",
    ".sublime-workspace",
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
    ".git-credentials",
    ".htpasswd",
    ".my.cnf",
    ".netrc",
    ".npmrc",
    ".pgpass",
    ".pypirc",
    "changes",
    "config",
    "credentials",
    "dockerfile",
    "id_ed25519",
    "id_ecdsa",
    "id_rsa",
    "known_hosts",
    "makefile",
    "readme",
    "authorized_keys",
}
_SIGNAL_PAYLOAD_SUFFIXES = {".eeg", ".fdt"}
_IMAGE_PAYLOAD_SUFFIXES = {".img"}
_EDF_SUFFIXES = {".edf", ".bdf"}
_DICOM_SUFFIXES = {".dcm", ".dicom", ".ima"}
_MNE_FILE_FORMATS = {".fif": "fif", ".set": "eeglab"}
_UNEXPECTED_SUFFIXES = {
    ".7z",
    ".bak",
    ".backup",
    ".diff",
    ".key",
    ".ods",
    ".old",
    ".orig",
    ".patch",
    ".p12",
    ".pem",
    ".pfx",
    ".rar",
    ".rej",
    ".save",
    ".code-workspace",
    ".sublime-project",
    ".sublime-workspace",
    ".swo",
    ".swp",
    ".tmp",
    ".tar",
    ".tbz",
    ".tbz2",
    ".tgz",
    ".txz",
    ".xls",
    ".xlsx",
    ".zip",
}
_COMPOUND_ARCHIVE_SUFFIXES = (".tar.bz2", ".tar.gz", ".tar.xz", ".tar.zst")
_SENSITIVE_CONFIG_NAMES = {
    ".env",
    ".git-credentials",
    ".htpasswd",
    ".my.cnf",
    ".netrc",
    ".npmrc",
    ".pgpass",
    ".pypirc",
    "application_default_credentials.json",
    "auth.json",
    "authorized_keys",
    "credentials",
    "credentials.ini",
    "credentials.json",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
    "known_hosts",
    "secrets.json",
    "service-account.json",
    "token.json",
}
_OS_METADATA_NAMES = {".ds_store", "desktop.ini", "thumbs.db"}
_SENSITIVE_DIRECTORIES = {".aws", ".azure", ".docker", ".gnupg", ".kube", ".ssh"}
_IGNORED_DIRECTORIES = {
    ".cache",
    ".git",
    ".fseventsd",
    ".hg",
    ".idea",
    ".ipynb_checkpoints",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".spotlight-v100",
    ".svn",
    ".tox",
    ".trashes",
    ".venv",
    ".vscode",
    "__pycache__",
    "node_modules",
    "system volume information",
}
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


def _sensitive_path_findings(
    relative_path: str,
    known_terms: KnownTermMatcher,
    location: str,
) -> list[Finding]:
    findings: list[Finding] = []
    for email in find_emails(relative_path):
        findings.append(
            Finding(
                code="DIRECT_EMAIL",
                severity="high",
                path=relative_path,
                location=location,
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
                location=location,
                evidence=redacted("known-identifier", term),
                message="Rename this path to remove the known name or identifier.",
            )
        )
    for code, severity, kind, value, message in find_sensitive_path_values(relative_path):
        findings.append(
            Finding(
                code=code,
                severity=severity,
                path=relative_path,
                location=location,
                evidence=redacted(kind, value),
                message=message,
            )
        )
    return findings


def _looks_like_subject_key(path: Path) -> bool:
    lower_name = path.name.lower()
    return any(term in lower_name for term in _KEY_TERMS) and any(
        term in lower_name for term in _MAPPING_TERMS
    )


def _unexpected_file_findings(
    relative_path: str,
    known_terms: KnownTermMatcher,
) -> list[Finding]:
    path = Path(relative_path)
    lower_name = path.name.lower()
    findings = _sensitive_path_findings(relative_path, known_terms, "filename")
    if (
        path.suffix.lower() in _UNEXPECTED_SUFFIXES
        or lower_name.endswith(_COMPOUND_ARCHIVE_SUFFIXES)
        or lower_name.endswith("~")
        or lower_name.startswith(".#")
    ):
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
    if _is_sensitive_config_name(lower_name):
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
    if _looks_like_subject_key(path):
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


def _unexpected_directory_findings(
    relative_path: str,
    known_terms: KnownTermMatcher,
) -> list[Finding]:
    path = Path(relative_path)
    findings = _sensitive_path_findings(relative_path, known_terms, "directory name")
    if _looks_like_subject_key(path):
        findings.append(
            Finding(
                code="SUBJECT_KEY_FILE",
                severity="high",
                path=relative_path,
                location="directory name",
                evidence="<redacted:participant-key-directory>",
                message="Keep participant identity keys outside the release directory.",
            )
        )
    if path.name.lower() in _SENSITIVE_DIRECTORIES:
        findings.append(
            Finding(
                code="SENSITIVE_CONFIG_DIRECTORY",
                severity="review",
                path=relative_path,
                location="directory name",
                evidence="<sensitive-config-directory>",
                message=(
                    "Remove this private configuration directory from the release or "
                    "review every file inside it."
                ),
            )
        )
    return findings


def _is_sensitive_config_name(lower_name: str) -> bool:
    return (
        lower_name in _SENSITIVE_CONFIG_NAMES
        or lower_name.startswith(".env.")
        or lower_name.endswith(".env")
        or lower_name.startswith(("credentials.", "secret.", "secrets."))
    )


def _redact_report_paths(report: ScanReport, known_terms: KnownTermMatcher) -> ScanReport:
    paths = (
        report.files_inspected
        + [item.path for item in report.skipped_files]
        + [item.path for item in report.coverage]
        + [item.path for item in report.manifest]
        + [item.container_path for item in report.container_members]
        + [item.member_path for item in report.container_members]
        + [item.source_path for item in report.references]
        + [item.target for item in report.references]
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
                for _, _, _, value, _ in find_sensitive_path_values(path)
            },
            key=str.casefold,
        )
    )
    sensitive_path_terms = KnownTermMatcher(
        sensitive_path_values,
        label="sensitive-path",
        bounded=False,
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
        coverage=[
            replace(item, path=redact_path(item.path))
            for item in report.coverage
        ],
        manifest=[
            replace(item, path=redact_path(item.path))
            for item in report.manifest
        ],
        container_members=[
            replace(
                item,
                container_path=redact_path(item.container_path),
                member_path=redact_path(item.member_path),
            )
            for item in report.container_members
        ],
        references=[
            replace(
                item,
                source_path=redact_path(item.source_path),
                target=redact_path(item.target),
            )
            for item in report.references
        ],
        findings=[
            replace(item, path=redact_path(item.path))
            for item in report.findings
        ],
        manifest_recheck_passed=report.manifest_recheck_passed,
    )


def _walk(root: Path):
    pending = [(root, False)]
    while pending:
        directory, inside_ignored = pending.pop()
        try:
            entries = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError:
            relative_path = directory.relative_to(root).as_posix() or "."
            yield "directory_error", directory, relative_path
            continue
        subdirectories: list[tuple[Path, bool]] = []
        for entry in entries:
            relative_path = entry.relative_to(root).as_posix()
            try:
                if entry.is_symlink():
                    yield (
                        "ignored_symlink" if inside_ignored else "symlink",
                        entry,
                        relative_path,
                    )
                elif entry.is_dir():
                    entry_is_ignored = (
                        inside_ignored
                        or entry.name.lower() in _IGNORED_DIRECTORIES
                    )
                    if entry_is_ignored:
                        yield "ignored_directory", entry, relative_path
                    else:
                        if entry.suffix.lower() == ".mff":
                            yield "format_directory", entry, relative_path
                        else:
                            yield "directory", entry, relative_path
                    subdirectories.append((entry, entry_is_ignored))
                elif entry.is_file():
                    yield (
                        "ignored_file" if inside_ignored else "file",
                        entry,
                        relative_path,
                    )
                else:
                    yield (
                        "ignored_other" if inside_ignored else "other",
                        entry,
                        relative_path,
                    )
            except OSError:
                yield "entry_error", entry, relative_path
        pending.extend(reversed(subdirectories))


def _mne_format_for_path(path: Path) -> str | None:
    if path.name.lower().endswith(".fif.gz"):
        return "fif"
    return _MNE_FILE_FORMATS.get(path.suffix.lower())


def _is_nifti_path(path: Path) -> bool:
    lower_name = path.name.lower()
    return lower_name.endswith(".nii.gz") or path.suffix.lower() in {".nii", ".hdr"}


def _is_dicom_path(path: Path) -> bool:
    if path.suffix.lower() in _DICOM_SUFFIXES:
        return True
    if path.suffix:
        return False
    with path.open("rb") as stream:
        prefix = stream.read(132)
    return len(prefix) == 132 and prefix[128:132] == b"DICM"


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _release_collision_findings(
    manifest: list[ManifestEntry],
) -> list[Finding]:
    findings: list[Finding] = []
    path_groups: dict[str, list[str]] = {}
    basename_groups: dict[str, list[str]] = {}
    for item in manifest:
        path_groups.setdefault(item.path.casefold(), []).append(item.path)
        basename_groups.setdefault(Path(item.path).name.casefold(), []).append(item.path)

    for paths in path_groups.values():
        if len(set(paths)) < 2:
            continue
        findings.append(
            Finding(
                code="CASE_COLLIDING_RELEASE_PATH",
                severity="review",
                path=sorted(paths)[0],
                location="release inventory",
                evidence=f"<case-colliding-paths:{len(paths)}>",
                message=(
                    "Rename these entries so the release is unambiguous on "
                    "case-insensitive filesystems."
                ),
            )
        )

    for paths in basename_groups.values():
        unique_paths = sorted(set(paths))
        if len(unique_paths) < 2:
            continue
        exact_names = {Path(path).name for path in unique_paths}
        findings.append(
            Finding(
                code=(
                    "DUPLICATE_BASENAME"
                    if len(exact_names) == 1
                    else "CASE_COLLIDING_BASENAME"
                ),
                severity="info" if len(exact_names) == 1 else "review",
                path=unique_paths[0],
                location="release inventory",
                evidence=f"<repeated-basename,count={len(unique_paths)}>",
                message=(
                    "Confirm these repeated filenames are intentional and all "
                    "references use explicit relative paths."
                ),
            )
        )
    return findings


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
    coverage_by_path: dict[str, CoverageEntry] = {}
    manifest_by_path: dict[str, ManifestEntry] = {}

    def record_coverage(
        relative_path: str,
        entry_type: EntryType,
        status: CoverageStatus,
        reason: str,
    ) -> None:
        coverage_by_path[relative_path] = CoverageEntry(
            path=relative_path,
            entry_type=entry_type,
            status=status,
            reason=reason,
        )

    def inventory_file(path: Path, relative_path: str) -> bool:
        try:
            size = path.stat().st_size
            manifest_by_path[relative_path] = ManifestEntry(
                path=relative_path,
                size_bytes=size,
                sha256=_sha256_file(path),
            )
            return True
        except OSError as error:
            report.manifest_recheck_passed = False
            report.findings.append(
                Finding(
                    code="MANIFEST_UNREADABLE",
                    severity="review",
                    path=relative_path,
                    location="release manifest",
                    evidence=f"<error:{type(error).__name__}>",
                    message="Fix access to this file before relying on the release manifest.",
                )
            )
            report.skipped_files.append(
                SkippedFile(relative_path, "File checksum could not be calculated")
            )
            record_coverage(
                relative_path,
                "unreadable",
                "unsupported_manual_review",
                "The file could not be added to the integrity manifest",
            )
            return False

    for kind, path, relative_path in _walk(root):
        if kind in {"directory_error", "entry_error"}:
            report.findings.extend(
                _sensitive_path_findings(
                    relative_path,
                    known_terms,
                    "filesystem entry",
                )
            )
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
            record_coverage(
                relative_path,
                "unreadable",
                "unsupported_manual_review",
                "The filesystem entry could not be classified safely",
            )
            continue

        if kind == "ignored_directory":
            report.findings.extend(
                _sensitive_path_findings(
                    relative_path,
                    known_terms,
                    "directory name",
                )
            )
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
            record_coverage(
                relative_path,
                "directory",
                "not_traversed",
                "Development-directory contents are inventoried but not parsed",
            )
            continue

        if kind == "ignored_file":
            report.findings.extend(
                _unexpected_file_findings(relative_path, known_terms)
            )
            if inventory_file(path, relative_path):
                record_coverage(
                    relative_path,
                    "file",
                    "not_traversed",
                    "The file is inside a development directory and was not parsed",
                )
            continue

        if kind == "ignored_symlink":
            report.findings.extend(
                _sensitive_path_findings(
                    relative_path,
                    known_terms,
                    "symlink name",
                )
            )
            report.skipped_files.append(
                SkippedFile(
                    relative_path,
                    "Symlink inside a development directory is not followed",
                )
            )
            record_coverage(
                relative_path,
                "symlink",
                "not_traversed",
                "The symlink is inside a development directory and was not followed",
            )
            continue

        if kind == "ignored_other":
            report.skipped_files.append(
                SkippedFile(
                    relative_path,
                    "Special filesystem entry inside a development directory is not opened",
                )
            )
            record_coverage(
                relative_path,
                "other",
                "not_traversed",
                "The special entry is inside a development directory and was not opened",
            )
            continue

        if kind == "format_directory":
            report.findings.extend(
                _unexpected_directory_findings(relative_path, known_terms)
            )
            try:
                report.findings.extend(
                    inspect_mne_format(path, relative_path, "mff", known_terms)
                )
                report.files_inspected.append(relative_path)
                record_coverage(
                    relative_path,
                    "format_directory",
                    "fully_inspected_metadata",
                    "Recording metadata was inspected without loading the signal",
                )
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
                record_coverage(
                    relative_path,
                    "format_directory",
                    "header_or_structure_only",
                    "Directory structure and bounded XML are covered; "
                    "the format reader is unavailable",
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
                record_coverage(
                    relative_path,
                    "format_directory",
                    "unsupported_manual_review",
                    "The recording metadata reader failed",
                )
            continue

        if kind == "directory":
            report.findings.extend(
                _unexpected_directory_findings(relative_path, known_terms)
            )
            record_coverage(
                relative_path,
                "directory",
                "header_or_structure_only",
                "Directory name and release-tree position were inspected",
            )
            continue

        if kind == "symlink":
            report.findings.extend(
                _sensitive_path_findings(
                    relative_path,
                    known_terms,
                    "symlink name",
                )
            )
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
            record_coverage(
                relative_path,
                "symlink",
                "header_or_structure_only",
                "The link was classified without following its target",
            )
            continue

        if kind == "other":
            report.findings.extend(
                _sensitive_path_findings(
                    relative_path,
                    known_terms,
                    "filesystem entry",
                )
            )
            report.findings.append(
                Finding(
                    code="SPECIAL_FILESYSTEM_ENTRY",
                    severity="review",
                    path=relative_path,
                    location="filesystem entry",
                    evidence="<special-filesystem-entry>",
                    message="Remove this entry or review it manually before release.",
                )
            )
            report.skipped_files.append(
                SkippedFile(relative_path, "Special filesystem entries are not opened")
            )
            record_coverage(
                relative_path,
                "other",
                "unsupported_manual_review",
                "The entry is not a regular file, directory or symlink",
            )
            continue

        report.findings.extend(_unexpected_file_findings(relative_path, known_terms))
        if not inventory_file(path, relative_path):
            continue
        suffix = path.suffix.lower()
        mne_format = _mne_format_for_path(path)
        try:
            if (
                suffix in _TEXT_SUFFIXES
                or path.name.lower() in _TEXT_NAMES
                or _is_sensitive_config_name(path.name.lower())
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
                    record_coverage(
                        relative_path,
                        "file",
                        "unsupported_manual_review",
                        "Text file exceeds the configured parsing limit",
                    )
                    continue
                data = path.read_bytes()
                text = decode_small_text(data)
                report.files_inspected.append(relative_path)
                record_coverage(
                    relative_path,
                    "file",
                    "fully_inspected_metadata",
                    "The complete text or structured metadata file was inspected",
                )
                report.findings.extend(scan_text(text, relative_path, known_terms))
                if suffix == ".json":
                    report.findings.extend(inspect_json(text, relative_path))
                    references = inspect_bids_json_references(
                        text,
                        path,
                        relative_path,
                        root,
                    )
                    report.references.extend(references.entries)
                    report.findings.extend(references.findings)
                elif suffix == ".tsv":
                    report.findings.extend(inspect_delimited(text, relative_path, "\t"))
                elif suffix == ".csv":
                    report.findings.extend(inspect_delimited(text, relative_path, ","))
                elif suffix == ".xml":
                    report.findings.extend(inspect_xml(text, relative_path))
                if suffix in {".vhdr", ".vmrk"}:
                    report.findings.extend(inspect_brainvision(text, relative_path))
                    references = inspect_brainvision_references(
                        text,
                        path,
                        relative_path,
                        root,
                    )
                    report.references.extend(references.entries)
                    report.findings.extend(references.findings)
            elif suffix in _EDF_SUFFIXES:
                with path.open("rb") as stream:
                    header = stream.read(256)
                report.files_inspected.append(relative_path)
                record_coverage(
                    relative_path,
                    "file",
                    "header_or_structure_only",
                    "The EDF or BDF header was inspected; signal samples were not loaded",
                )
                report.findings.extend(
                    inspect_edf_header(header, relative_path, known_terms)
                )
            elif _is_nifti_path(path):
                try:
                    report.findings.extend(
                        inspect_nifti_metadata(path, relative_path, known_terms)
                    )
                    report.files_inspected.append(relative_path)
                    record_coverage(
                        relative_path,
                        "file",
                        "header_or_structure_only",
                        "NIfTI header metadata was inspected; voxels were not loaded",
                    )
                except FormatReaderUnavailable:
                    report.findings.append(
                        Finding(
                            code="FORMAT_READER_UNAVAILABLE",
                            severity="review",
                            path=relative_path,
                            location="NIfTI metadata",
                            evidence="<optional-reader-unavailable>",
                            message=(
                                "Install the 'imaging' extra to inspect this NIfTI header."
                            ),
                        )
                    )
                    report.skipped_files.append(
                        SkippedFile(
                            relative_path,
                            "Optional NIfTI metadata reader is unavailable",
                        )
                    )
                    record_coverage(
                        relative_path,
                        "file",
                        "unsupported_manual_review",
                        "The optional NIfTI metadata reader is unavailable",
                    )
                except Exception as error:
                    report.findings.append(
                        Finding(
                            code="FORMAT_METADATA_UNREADABLE",
                            severity="review",
                            path=relative_path,
                            location="NIfTI metadata",
                            evidence=f"<error:{type(error).__name__}>",
                            message=(
                                "Review this file manually; its NIfTI header was not read."
                            ),
                        )
                    )
                    report.skipped_files.append(
                        SkippedFile(
                            relative_path,
                            f"Could not inspect NIfTI metadata: {type(error).__name__}",
                        )
                    )
                    record_coverage(
                        relative_path,
                        "file",
                        "unsupported_manual_review",
                        "The NIfTI metadata reader failed",
                    )
            elif _is_dicom_path(path):
                try:
                    report.findings.extend(
                        inspect_dicom_metadata(path, relative_path, known_terms)
                    )
                    report.files_inspected.append(relative_path)
                    record_coverage(
                        relative_path,
                        "file",
                        "header_or_structure_only",
                        "DICOM metadata before Pixel Data was inspected; "
                        "pixels were not opened",
                    )
                except FormatReaderUnavailable:
                    report.findings.append(
                        Finding(
                            code="FORMAT_READER_UNAVAILABLE",
                            severity="review",
                            path=relative_path,
                            location="DICOM metadata",
                            evidence="<optional-reader-unavailable>",
                            message=(
                                "Install the 'imaging' extra to inspect this DICOM file."
                            ),
                        )
                    )
                    report.skipped_files.append(
                        SkippedFile(
                            relative_path,
                            "Optional DICOM metadata reader is unavailable",
                        )
                    )
                    record_coverage(
                        relative_path,
                        "file",
                        "unsupported_manual_review",
                        "The optional DICOM metadata reader is unavailable",
                    )
                except Exception as error:
                    report.findings.append(
                        Finding(
                            code="FORMAT_METADATA_UNREADABLE",
                            severity="review",
                            path=relative_path,
                            location="DICOM metadata",
                            evidence=f"<error:{type(error).__name__}>",
                            message=(
                                "Review this file manually; its DICOM metadata was not read."
                            ),
                        )
                    )
                    report.skipped_files.append(
                        SkippedFile(
                            relative_path,
                            f"Could not inspect DICOM metadata: {type(error).__name__}",
                        )
                    )
                    record_coverage(
                        relative_path,
                        "file",
                        "unsupported_manual_review",
                        "The DICOM metadata reader failed",
                    )
            elif is_archive_path(path):
                try:
                    archive = inspect_archive(
                        path,
                        relative_path,
                        known_terms,
                    )
                    report.findings.extend(archive.findings)
                    report.container_members.extend(archive.members)
                    report.files_inspected.append(relative_path)
                    if archive.complete:
                        record_coverage(
                            relative_path,
                            "file",
                            "header_or_structure_only",
                            archive.reason,
                        )
                    else:
                        report.skipped_files.append(
                            SkippedFile(relative_path, archive.reason)
                        )
                        record_coverage(
                            relative_path,
                            "file",
                            "unsupported_manual_review",
                            archive.reason,
                        )
                except Exception as error:
                    report.findings.append(
                        Finding(
                            code="ARCHIVE_UNREADABLE",
                            severity="review",
                            path=relative_path,
                            location="archive directory",
                            evidence=f"<error:{type(error).__name__}>",
                            message=(
                                "Review this archive manually; its member table "
                                "could not be read safely."
                            ),
                        )
                    )
                    report.skipped_files.append(
                        SkippedFile(
                            relative_path,
                            f"Could not inspect archive directory: {type(error).__name__}",
                        )
                    )
                    record_coverage(
                        relative_path,
                        "file",
                        "unsupported_manual_review",
                        "The archive member table could not be read",
                    )
            elif mne_format is not None:
                with path.open("rb") as stream:
                    prefix = stream.read(128)
                if not prefix:
                    report.files_inspected.append(relative_path)
                    record_coverage(
                        relative_path,
                        "file",
                        "fully_inspected_metadata",
                        "The file is empty and contains no metadata or signal payload",
                    )
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
                    record_coverage(
                        relative_path,
                        "file",
                        "fully_inspected_metadata",
                        "The complete Git LFS pointer was inspected; the payload is absent",
                    )
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
                    eeglab_references = []
                    try:
                        eeglab_findings = inspect_eeglab_metadata(
                            path,
                            relative_path,
                            known_terms,
                            root,
                            reference_entries=eeglab_references,
                        )
                        report.findings.extend(eeglab_findings)
                        report.references.extend(eeglab_references)
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
                    record_coverage(
                        relative_path,
                        "file",
                        "header_or_structure_only",
                        "Safe EEGLAB metadata was inspected; signal loading was refused",
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
                    record_coverage(
                        relative_path,
                        "file",
                        "header_or_structure_only",
                        "Format metadata was inspected without loading the signal",
                    )
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
                    record_coverage(
                        relative_path,
                        "file",
                        "unsupported_manual_review",
                        "The optional metadata reader is unavailable",
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
                    record_coverage(
                        relative_path,
                        "file",
                        "unsupported_manual_review",
                        "The format metadata reader failed",
                    )
            elif suffix in _SIGNAL_PAYLOAD_SUFFIXES | _IMAGE_PAYLOAD_SUFFIXES:
                report.skipped_files.append(
                    SkippedFile(
                        relative_path,
                        "Signal or image payload is not parsed or loaded",
                    )
                )
                record_coverage(
                    relative_path,
                    "file",
                    "payload_not_opened",
                    "Signal or image payload was hashed but not parsed or loaded",
                )
            else:
                report.skipped_files.append(
                    SkippedFile(relative_path, "File format is not inspected by the MVP")
                )
                record_coverage(
                    relative_path,
                    "file",
                    "unsupported_manual_review",
                    "No safe metadata reader is available for this file type",
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
            record_coverage(
                relative_path,
                "file",
                "unsupported_manual_review",
                "The file could not be parsed safely",
            )
    for relative_path, initial in sorted(manifest_by_path.items()):
        try:
            current_path = root / relative_path
            current_size = current_path.stat().st_size
            current_hash = _sha256_file(current_path)
        except OSError as error:
            report.manifest_recheck_passed = False
            report.findings.append(
                Finding(
                    code="MANIFEST_RECHECK_FAILED",
                    severity="review",
                    path=relative_path,
                    location="release manifest",
                    evidence=f"<error:{type(error).__name__}>",
                    message=(
                        "The file could not be rechecked after scanning; "
                        "rerun on a stable release tree."
                    ),
                )
            )
            record_coverage(
                relative_path,
                "unreadable",
                "unsupported_manual_review",
                "The file could not be rechecked after scanning",
            )
            continue
        if current_size != initial.size_bytes or current_hash != initial.sha256:
            report.manifest_recheck_passed = False
            report.findings.append(
                Finding(
                    code="FILE_CHANGED_DURING_SCAN",
                    severity="review",
                    path=relative_path,
                    location="release manifest",
                    evidence="<file-changed>",
                    message="Rerun the audit after the release tree stops changing.",
                )
            )
            record_coverage(
                relative_path,
                "file",
                "unsupported_manual_review",
                "The file changed while the audit was running",
            )

    report.coverage = list(coverage_by_path.values())
    report.manifest = list(manifest_by_path.values())
    report.findings.extend(_release_collision_findings(report.manifest))
    return _redact_report_paths(report, known_terms).normalized()
