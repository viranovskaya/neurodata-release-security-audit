"""Walk a dataset and run the relevant checks."""

from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from typing import BinaryIO

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
    inspect_matlab_metadata,
    inspect_mne_format,
    inspect_office_metadata,
)
from .references import (
    inspect_bids_json_references,
    inspect_brainvision_references,
)
from .structured import inspect_delimited, inspect_json, inspect_xml

_TEXT_SUFFIXES = {
    ".bash",
    ".bval",
    ".bvec",
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
    ".bidsignore",
    ".env",
    ".gitattributes",
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
    "license",
    "license.txt",
    "makefile",
    "readme",
    "authorized_keys",
}
_PUBLIC_CONTACT_NAMES = {
    "authors",
    "authors.txt",
    "changes",
    "citation.cff",
    "dataset_description.json",
    "readme",
    "readme.md",
    "readme.txt",
}
_SIGNAL_PAYLOAD_SUFFIXES = {".eeg", ".fdt"}
_IMAGE_PAYLOAD_SUFFIXES = {".img"}
_EDF_SUFFIXES = {".edf", ".bdf"}
_DICOM_SUFFIXES = {".dcm", ".dicom", ".ima"}
_OFFICE_FORMATS = {".docx": "docx", ".xlsx": "xlsx"}
_MNE_FILE_FORMATS = {
    ".con": "kit",
    ".fif": "fif",
    ".set": "eeglab",
    ".sqd": "kit",
}
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


@dataclass(frozen=True)
class _FileToken:
    device: int
    inode: int
    size: int
    modified_ns: int


def _token_from_stat(metadata: os.stat_result) -> _FileToken:
    if not stat.S_ISREG(metadata.st_mode):
        raise OSError("Release entry is not a regular file")
    return _FileToken(
        device=metadata.st_dev,
        inode=metadata.st_ino,
        size=metadata.st_size,
        modified_ns=metadata.st_mtime_ns,
    )


def _regular_file_token(path: Path) -> _FileToken:
    """Return a non-following identity token for one regular release file."""
    return _token_from_stat(path.lstat())


def _open_regular_file(path: Path, expected: _FileToken) -> BinaryIO:
    """Open the exact regular file represented by ``expected`` without symlinks."""
    if _regular_file_token(path) != expected:
        raise OSError("Release file identity changed before it was opened")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = _token_from_stat(os.fstat(descriptor))
        current = _regular_file_token(path)
        if opened != expected or current != expected:
            raise OSError("Release file identity changed while it was opened")
        return os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise


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
    for code, severity, kind, value, message in find_sensitive_path_values(
        relative_path
    ):
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
        or lower_name.startswith((".env.", "credentials.", "secret.", "secrets."))
        or lower_name.endswith(".env")
    )


def _is_public_contact_path(relative_path: str) -> bool:
    return Path(relative_path).name.lower() in _PUBLIC_CONTACT_NAMES


def _redact_report_paths(
    report: ScanReport, known_terms: KnownTermMatcher
) -> ScanReport:
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
        return sensitive_path_terms.redact(email_terms.redact(known_terms.redact(path)))

    return ScanReport(
        scanner_version=report.scanner_version,
        schema_version=report.schema_version,
        files_inspected=[redact_path(path) for path in report.files_inspected],
        skipped_files=[
            replace(item, path=redact_path(item.path)) for item in report.skipped_files
        ],
        coverage=[
            replace(item, path=redact_path(item.path)) for item in report.coverage
        ],
        manifest=[
            replace(item, path=redact_path(item.path)) for item in report.manifest
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
            replace(item, path=redact_path(item.path)) for item in report.findings
        ],
        manifest_recheck_passed=report.manifest_recheck_passed,
        release_tree_recheck_passed=report.release_tree_recheck_passed,
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
                        inside_ignored or entry.name.lower() in _IGNORED_DIRECTORIES
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


def _tree_signature(root: Path) -> dict[str, tuple[EntryType, str]]:
    signature: dict[str, tuple[EntryType, str]] = {}
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            entries = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError:
            relative_path = directory.relative_to(root).as_posix() or "."
            signature[relative_path] = ("unreadable", "")
            continue
        subdirectories: list[Path] = []
        for entry in entries:
            relative_path = entry.relative_to(root).as_posix()
            try:
                if entry.is_symlink():
                    try:
                        link_target = os.readlink(entry)
                        target_signature = hashlib.sha256(
                            os.fsencode(link_target)
                        ).hexdigest()
                    except OSError:
                        target_signature = "<unreadable-target>"
                    signature[relative_path] = ("symlink", target_signature)
                elif entry.is_dir():
                    signature[relative_path] = ("directory", "")
                    subdirectories.append(entry)
                elif entry.is_file():
                    signature[relative_path] = ("file", "")
                else:
                    signature[relative_path] = ("other", "")
            except OSError:
                signature[relative_path] = ("unreadable", "")
        pending.extend(reversed(subdirectories))
    return signature


def _mne_format_for_path(path: Path) -> str | None:
    if path.name.lower().endswith(".fif.gz"):
        return "fif"
    return _MNE_FILE_FORMATS.get(path.suffix.lower())


def _is_nifti_path(path: Path) -> bool:
    lower_name = path.name.lower()
    return lower_name.endswith(".nii.gz") or path.suffix.lower() in {".nii", ".hdr"}


def _is_dicom_path(path: Path, prefix: bytes) -> bool:
    if path.suffix.lower() in _DICOM_SUFFIXES:
        return True
    if path.suffix:
        return False
    return len(prefix) == 132 and prefix[128:132] == b"DICM"


def _symlink_review(path: Path, relative_path: str, root: Path) -> Finding:
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
                message = "Remove or replace this symlink because it points outside the dataset."
    except (OSError, RuntimeError):
        code = "UNRESOLVED_SYMLINK"
        message = "Fix or remove this symlink because its target could not be classified safely."
    return Finding(
        code=code,
        severity="review",
        path=relative_path,
        location="filesystem entry",
        evidence="<redacted:symlink-target>",
        message=message,
    )


def _sha256_file(
    path: Path,
    expected: _FileToken,
    chunk_size: int = 1024 * 1024,
) -> str:
    digest = hashlib.sha256()
    with _open_regular_file(path, expected) as stream:
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
        basename_groups.setdefault(Path(item.path).name.casefold(), []).append(
            item.path
        )

    for paths in path_groups.values():
        if len(set(paths)) < 2:
            continue
        findings.append(
            Finding(
                code="CASE_COLLIDING_RELEASE_PATH",
                severity="review",
                path=min(paths),
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


_CoverageRecorder = Callable[[str, EntryType, CoverageStatus, str], None]


def _recheck_manifest(
    root: Path,
    report: ScanReport,
    manifest_by_path: dict[str, ManifestEntry],
    record_coverage: _CoverageRecorder,
) -> None:
    for relative_path, initial in sorted(manifest_by_path.items()):
        try:
            current_path = root / relative_path
            current_token = _regular_file_token(current_path)
            current_size = current_token.size
            current_hash = _sha256_file(current_path, current_token)
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
        if current_size == initial.size_bytes and current_hash == initial.sha256:
            continue
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


def _recheck_release_tree(
    root: Path,
    report: ScanReport,
    initial_tree: dict[str, tuple[EntryType, str]],
    record_coverage: _CoverageRecorder,
) -> None:
    final_tree = _tree_signature(root)
    for relative_path in sorted(set(initial_tree) | set(final_tree)):
        before = initial_tree.get(relative_path)
        after = final_tree.get(relative_path)
        if before == after:
            continue
        report.release_tree_recheck_passed = False
        if before is None:
            change = "added"
            entry_type: EntryType = after[0] if after is not None else "unreadable"
        elif after is None:
            change = "removed"
            entry_type = "unreadable"
        else:
            change = (
                "symlink-target-changed"
                if before[0] == after[0] == "symlink"
                else "type-changed"
            )
            entry_type = after[0]
        report.findings.append(
            Finding(
                code="RELEASE_TREE_CHANGED_DURING_SCAN",
                severity="review",
                path=relative_path,
                location="release inventory",
                evidence=f"<tree-entry:{change}>",
                message="Rerun the audit after the release tree stops changing.",
            )
        )
        record_coverage(
            relative_path,
            entry_type,
            "unsupported_manual_review",
            f"Release entry was {change} while the audit was running",
        )


def scan_dataset(
    dataset_root: str | Path, policy: ScanPolicy | None = None
) -> ScanReport:
    policy = policy or ScanPolicy()
    root = Path(dataset_root).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"Dataset directory does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Dataset path is not a directory: {root}")
    root = root.resolve()
    report = ScanReport(scanner_version=__version__)
    known_terms = KnownTermMatcher(policy.sensitive_terms)
    initial_tree = _tree_signature(root)
    coverage_by_path: dict[str, CoverageEntry] = {}
    manifest_by_path: dict[str, ManifestEntry] = {}
    file_tokens: dict[str, _FileToken] = {}

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

    def record_skip(
        relative_path: str,
        skipped_reason: str,
        coverage_reason: str,
        *,
        entry_type: EntryType = "file",
        status: CoverageStatus = "unsupported_manual_review",
    ) -> None:
        report.skipped_files.append(SkippedFile(relative_path, skipped_reason))
        record_coverage(relative_path, entry_type, status, coverage_reason)

    def record_problem(
        relative_path: str,
        *,
        code: str,
        location: str,
        evidence: str,
        message: str,
        skipped_reason: str,
        coverage_reason: str,
        entry_type: EntryType = "file",
        status: CoverageStatus = "unsupported_manual_review",
    ) -> None:
        report.findings.append(
            Finding(
                code=code,
                severity="review",
                path=relative_path,
                location=location,
                evidence=evidence,
                message=message,
            )
        )
        record_skip(
            relative_path,
            skipped_reason,
            coverage_reason,
            entry_type=entry_type,
            status=status,
        )

    def reader_unavailable(
        relative_path: str,
        *,
        location: str,
        message: str,
        skipped_reason: str,
        coverage_reason: str,
        code: str = "FORMAT_READER_UNAVAILABLE",
        entry_type: EntryType = "file",
        status: CoverageStatus = "unsupported_manual_review",
    ) -> None:
        record_problem(
            relative_path,
            code=code,
            location=location,
            evidence="<optional-reader-unavailable>",
            message=message,
            skipped_reason=skipped_reason,
            coverage_reason=coverage_reason,
            entry_type=entry_type,
            status=status,
        )

    def metadata_unreadable(
        relative_path: str,
        error: Exception,
        *,
        location: str,
        message: str,
        skipped_reason: str,
        coverage_reason: str,
        code: str = "FORMAT_METADATA_UNREADABLE",
        entry_type: EntryType = "file",
    ) -> None:
        record_problem(
            relative_path,
            code=code,
            location=location,
            evidence=f"<error:{type(error).__name__}>",
            message=message,
            skipped_reason=skipped_reason,
            coverage_reason=coverage_reason,
            entry_type=entry_type,
        )

    def inspect_optional_metadata(
        relative_path: str,
        reader: Callable[[], list[Finding]],
        *,
        success_reason: str,
        location: str,
        unavailable_message: str,
        unavailable_skipped_reason: str,
        unavailable_coverage_reason: str,
        failure_message: str,
        failure_label: str,
        failure_reason: str,
        entry_type: EntryType = "file",
        success_status: CoverageStatus = "header_or_structure_only",
        unavailable_status: CoverageStatus = "unsupported_manual_review",
    ) -> bool:
        try:
            report.findings.extend(reader())
        except FormatReaderUnavailable:
            reader_unavailable(
                relative_path,
                location=location,
                message=unavailable_message,
                skipped_reason=unavailable_skipped_reason,
                coverage_reason=unavailable_coverage_reason,
                entry_type=entry_type,
                status=unavailable_status,
            )
            return False
        except Exception as error:  # noqa: BLE001 - optional readers vary by backend
            metadata_unreadable(
                relative_path,
                error,
                location=location,
                message=failure_message,
                skipped_reason=f"{failure_label}: {type(error).__name__}",
                coverage_reason=failure_reason,
                entry_type=entry_type,
            )
            return False
        report.files_inspected.append(relative_path)
        record_coverage(
            relative_path,
            entry_type,
            success_status,
            success_reason,
        )
        return True

    def inventory_file(path: Path, relative_path: str) -> bool:
        try:
            token = _regular_file_token(path)
            manifest_by_path[relative_path] = ManifestEntry(
                path=relative_path,
                size_bytes=token.size,
                sha256=_sha256_file(path, token),
            )
            file_tokens[relative_path] = token
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
            record_skip(
                relative_path,
                "File checksum could not be calculated",
                "The file could not be added to the integrity manifest",
                entry_type="unreadable",
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
            inspect_optional_metadata(
                relative_path,
                partial(inspect_mne_format, path, relative_path, "mff", known_terms),
                success_reason=(
                    "Recording metadata was inspected without loading the signal"
                ),
                location="MFF recording metadata",
                unavailable_message=(
                    "Install the 'formats' extra to inspect the MFF recording as a whole. "
                    "Its bounded XML files are still checked separately."
                ),
                unavailable_skipped_reason=(
                    "MFF recording reader is unavailable; XML files are still inspected"
                ),
                unavailable_coverage_reason=(
                    "Directory structure and bounded XML are covered; "
                    "the format reader is unavailable"
                ),
                failure_message=(
                    "Review this MFF recording manually; its recording metadata could "
                    "not be read. Bounded XML files are still checked separately."
                ),
                failure_label="Could not inspect MFF recording metadata",
                failure_reason="The recording metadata reader failed",
                entry_type="format_directory",
                success_status="fully_inspected_metadata",
                unavailable_status="header_or_structure_only",
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
            report.findings.append(_symlink_review(path, relative_path, root))
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
        file_token = file_tokens[relative_path]
        try:
            with _open_regular_file(path, file_token) as stream:
                prefix = stream.read(132)
            format_placeholder = (
                suffix
                in (_EDF_SUFFIXES | _SIGNAL_PAYLOAD_SUFFIXES | _IMAGE_PAYLOAD_SUFFIXES)
                or mne_format is not None
                or _is_nifti_path(path)
                or _is_dicom_path(path, prefix)
                or is_archive_path(path)
            )
            if not prefix and format_placeholder:
                report.files_inspected.append(relative_path)
                report.skipped_files.append(
                    SkippedFile(
                        relative_path,
                        "The expected format content is absent",
                    )
                )
                record_coverage(
                    relative_path,
                    "file",
                    "unsupported_manual_review",
                    "The file is empty, so no format metadata or payload was checked",
                )
                report.findings.append(
                    Finding(
                        code="EMPTY_PLACEHOLDER",
                        severity="info",
                        path=relative_path,
                        location="file content",
                        evidence="<bytes:0>",
                        message=(
                            "Confirm this empty fixture is intentional; no format "
                            "metadata was checked."
                        ),
                    )
                )
                continue
            if prefix.startswith(b"version https://git-lfs.github.com/spec/v1"):
                report.files_inspected.append(relative_path)
                report.skipped_files.append(
                    SkippedFile(
                        relative_path,
                        "The Git LFS payload is absent",
                    )
                )
                record_coverage(
                    relative_path,
                    "file",
                    "unsupported_manual_review",
                    "Only the Git LFS pointer was inspected; the payload is absent",
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
            if (
                suffix in _TEXT_SUFFIXES
                or path.name.lower() in _TEXT_NAMES
                or _is_sensitive_config_name(path.name.lower())
            ):
                size = file_token.size
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
                        SkippedFile(
                            relative_path, "Text file exceeds configured scan limit"
                        )
                    )
                    record_coverage(
                        relative_path,
                        "file",
                        "unsupported_manual_review",
                        "Text file exceeds the configured parsing limit",
                    )
                    continue
                with _open_regular_file(path, file_token) as stream:
                    data = stream.read()
                text = decode_small_text(data)
                report.files_inspected.append(relative_path)
                record_coverage(
                    relative_path,
                    "file",
                    "fully_inspected_metadata",
                    "The complete text or structured metadata file was inspected",
                )
                if suffix == ".json":
                    report.findings.extend(
                        inspect_json(
                            text,
                            relative_path,
                            known_terms,
                            public_contact_context=_is_public_contact_path(
                                relative_path
                            ),
                        )
                    )
                    references = inspect_bids_json_references(
                        text,
                        path,
                        relative_path,
                        root,
                    )
                    report.references.extend(references.entries)
                    report.findings.extend(references.findings)
                else:
                    report.findings.extend(
                        scan_text(
                            text,
                            relative_path,
                            known_terms,
                            public_contact_context=_is_public_contact_path(
                                relative_path
                            ),
                        )
                    )
                if suffix == ".tsv":
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
                with _open_regular_file(path, file_token) as stream:
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
                inspect_optional_metadata(
                    relative_path,
                    partial(inspect_nifti_metadata, path, relative_path, known_terms),
                    success_reason=(
                        "NIfTI header metadata was inspected; voxels were not loaded"
                    ),
                    location="NIfTI metadata",
                    unavailable_message=(
                        "Install the 'imaging' extra to inspect this NIfTI header."
                    ),
                    unavailable_skipped_reason=(
                        "Optional NIfTI metadata reader is unavailable"
                    ),
                    unavailable_coverage_reason=(
                        "The optional NIfTI metadata reader is unavailable"
                    ),
                    failure_message=(
                        "Review this file manually; its NIfTI header was not read."
                    ),
                    failure_label="Could not inspect NIfTI metadata",
                    failure_reason="The NIfTI metadata reader failed",
                )
            elif _is_dicom_path(path, prefix):
                try:
                    dicom_findings = inspect_dicom_metadata(
                        path,
                        relative_path,
                        known_terms,
                    )
                    report.findings.extend(dicom_findings)
                    report.files_inspected.append(relative_path)
                    if any(
                        item.code == "DICOM_METADATA_LIMIT" for item in dicom_findings
                    ):
                        report.skipped_files.append(
                            SkippedFile(
                                relative_path,
                                "DICOM metadata exceeded a configured inspection limit",
                            )
                        )
                        record_coverage(
                            relative_path,
                            "file",
                            "unsupported_manual_review",
                            "Only part of the DICOM metadata was inspected",
                        )
                    else:
                        record_coverage(
                            relative_path,
                            "file",
                            "header_or_structure_only",
                            "DICOM metadata before Pixel Data was inspected; "
                            "pixels were not opened",
                        )
                except FormatReaderUnavailable:
                    reader_unavailable(
                        relative_path,
                        location="DICOM metadata",
                        message="Install the 'imaging' extra to inspect this DICOM file.",
                        skipped_reason="Optional DICOM metadata reader is unavailable",
                        coverage_reason=(
                            "The optional DICOM metadata reader is unavailable"
                        ),
                    )
                except Exception as error:  # noqa: BLE001 - fail closed on reader errors
                    metadata_unreadable(
                        relative_path,
                        error,
                        location="DICOM metadata",
                        message="Review this file manually; its DICOM metadata was not read.",
                        skipped_reason=(
                            f"Could not inspect DICOM metadata: {type(error).__name__}"
                        ),
                        coverage_reason="The DICOM metadata reader failed",
                    )
            elif suffix == ".mat":
                inspect_optional_metadata(
                    relative_path,
                    partial(inspect_matlab_metadata, path, relative_path, known_terms),
                    success_reason=(
                        "MATLAB variable metadata and small text values were inspected; "
                        "arrays were not loaded"
                    ),
                    location="MATLAB metadata",
                    unavailable_message=(
                        "Install the 'formats' extra to inspect this MATLAB file."
                    ),
                    unavailable_skipped_reason=(
                        "Optional MATLAB metadata reader is unavailable"
                    ),
                    unavailable_coverage_reason=(
                        "The optional MATLAB metadata reader is unavailable"
                    ),
                    failure_message=(
                        "Review this file manually; its MATLAB metadata was not read."
                    ),
                    failure_label="Could not inspect MATLAB metadata",
                    failure_reason="The MATLAB metadata reader failed",
                )
            elif suffix in _OFFICE_FORMATS:
                try:
                    report.findings.extend(
                        inspect_office_metadata(
                            path,
                            relative_path,
                            _OFFICE_FORMATS[suffix],
                            known_terms,
                        )
                    )
                    report.files_inspected.append(relative_path)
                    record_coverage(
                        relative_path,
                        "file",
                        "header_or_structure_only",
                        "Bounded Office text and document metadata were inspected; "
                        "embedded objects were not opened",
                    )
                except Exception as error:  # noqa: BLE001 - fail closed on reader errors
                    metadata_unreadable(
                        relative_path,
                        error,
                        location=f"{_OFFICE_FORMATS[suffix].upper()} metadata",
                        message="Review this file manually; its Office metadata was not read.",
                        skipped_reason=(
                            f"Could not inspect Office metadata: {type(error).__name__}"
                        ),
                        coverage_reason="The Office metadata reader failed",
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
                except Exception as error:  # noqa: BLE001 - fail closed on reader errors
                    metadata_unreadable(
                        relative_path,
                        error,
                        code="ARCHIVE_UNREADABLE",
                        location="archive directory",
                        message=(
                            "Review this archive manually; its member table "
                            "could not be read safely."
                        ),
                        skipped_reason=(
                            f"Could not inspect archive directory: {type(error).__name__}"
                        ),
                        coverage_reason="The archive member table could not be read",
                    )
            elif mne_format is not None:
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
                    except Exception as error:  # noqa: BLE001 - fail closed safely
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
                metadata_read = inspect_optional_metadata(
                    relative_path,
                    partial(
                        inspect_mne_format,
                        path,
                        relative_path,
                        mne_format,
                        known_terms,
                    ),
                    success_reason=(
                        "Format metadata was inspected without loading the signal"
                    ),
                    location=f"{mne_format.upper()} metadata",
                    unavailable_message=(
                        "Install the 'formats' extra to inspect this file's metadata."
                    ),
                    unavailable_skipped_reason="Optional format reader is unavailable",
                    unavailable_coverage_reason=(
                        "The optional metadata reader is unavailable"
                    ),
                    failure_message=(
                        "Review this file manually; its format metadata was not read."
                    ),
                    failure_label="Could not inspect format metadata",
                    failure_reason="The format metadata reader failed",
                )
                if metadata_read and eeglab_metadata_reader_unavailable:
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
                    SkippedFile(
                        relative_path,
                        "No safe metadata reader is implemented for this file type",
                    )
                )
                record_coverage(
                    relative_path,
                    "file",
                    "unsupported_manual_review",
                    "No safe metadata reader is available for this file type",
                )
        except (OSError, UnicodeError) as error:
            report.skipped_files.append(
                SkippedFile(
                    relative_path, f"Could not inspect file: {type(error).__name__}"
                )
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
    _recheck_manifest(root, report, manifest_by_path, record_coverage)
    _recheck_release_tree(root, report, initial_tree, record_coverage)

    report.coverage = list(coverage_by_path.values())
    report.manifest = list(manifest_by_path.values())
    report.findings.extend(_release_collision_findings(report.manifest))
    return _redact_report_paths(report, known_terms).normalized()
