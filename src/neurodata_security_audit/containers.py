"""Read archive directories without extracting member payloads."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
import stat
import tarfile
import zipfile

from .detectors import (
    KnownTermMatcher,
    find_emails,
    find_sensitive_path_values,
    redacted,
)
from .models import ContainerMember, ContainerMemberType, Finding

_ARCHIVE_SUFFIXES = (
    ".7z",
    ".rar",
    ".tar",
    ".tar.bz2",
    ".tar.gz",
    ".tar.xz",
    ".tar.zst",
    ".tbz",
    ".tbz2",
    ".tgz",
    ".txz",
    ".zip",
)
_SUPPORTED_ARCHIVE_SUFFIXES = (
    ".tar",
    ".tar.bz2",
    ".tar.gz",
    ".tar.xz",
    ".tbz",
    ".tbz2",
    ".tgz",
    ".txz",
    ".zip",
)
_LARGE_ARCHIVE_BYTES = 50 * 1024 * 1024 * 1024
_HIGH_RATIO_MIN_BYTES = 100 * 1024 * 1024
_HIGH_COMPRESSION_RATIO = 1000


@dataclass(frozen=True)
class ArchiveInspection:
    members: tuple[ContainerMember, ...]
    findings: tuple[Finding, ...]
    complete: bool
    reason: str


def is_archive_path(path: Path) -> bool:
    lower_name = path.name.lower()
    return lower_name.endswith(_SUPPORTED_ARCHIVE_SUFFIXES)


def _is_nested_archive(name: str) -> bool:
    return name.lower().endswith(_ARCHIVE_SUFFIXES)


def _unsafe_member_path(name: str) -> bool:
    normalised = name.replace("\\", "/")
    posix_path = PurePosixPath(normalised)
    windows_path = PureWindowsPath(name)
    return (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or ".." in posix_path.parts
        or "\x00" in name
        or any(ord(character) < 32 for character in name)
    )


def _member_path_findings(
    container_path: str,
    member_path: str,
    member_index: int,
    known_terms: KnownTermMatcher,
) -> list[Finding]:
    location = f"archive member {member_index}"
    findings: list[Finding] = []
    if _unsafe_member_path(member_path):
        findings.append(
            Finding(
                code="ARCHIVE_MEMBER_PATH_TRAVERSAL",
                severity="high",
                path=container_path,
                location=location,
                evidence=redacted("unsafe-archive-member", member_path),
                message=(
                    "Remove this absolute, parent-traversing or control-character "
                    "archive member."
                ),
            )
        )
    for email in find_emails(member_path):
        findings.append(
            Finding(
                code="DIRECT_EMAIL",
                severity="high",
                path=container_path,
                location=location,
                evidence=redacted("archive-member-email", email),
                message="Rename this archive member to remove the email address.",
            )
        )
    for term in known_terms.matches(member_path):
        findings.append(
            Finding(
                code="KNOWN_IDENTIFIER",
                severity="high",
                path=container_path,
                location=location,
                evidence=redacted("archive-member-known-identifier", term),
                message="Rename this archive member to remove the known identifier.",
            )
        )
    for code, severity, kind, value, message in find_sensitive_path_values(member_path):
        findings.append(
            Finding(
                code=code,
                severity=severity,
                path=container_path,
                location=location,
                evidence=redacted(f"archive-member-{kind}", value),
                message=message,
            )
        )
    if _is_nested_archive(member_path):
        findings.append(
            Finding(
                code="NESTED_ARCHIVE",
                severity="review",
                path=container_path,
                location=location,
                evidence="<nested-archive-member>",
                message=(
                    "Review this nested archive separately; its member payload was not opened."
                ),
            )
        )
    return findings


def _safe_member_name(name: str, member_index: int, max_name_chars: int) -> str:
    if len(name) <= max_name_chars:
        return name
    return f"<archive-member-name-too-long-{member_index:05d}>"


def _zip_member_type(info: zipfile.ZipInfo) -> ContainerMemberType:
    if info.is_dir():
        return "directory"
    mode = info.external_attr >> 16
    file_type = stat.S_IFMT(mode)
    if file_type == stat.S_IFLNK:
        return "symlink"
    if file_type and file_type != stat.S_IFREG:
        return "special"
    return "file"


def _tar_member_type(info: tarfile.TarInfo) -> ContainerMemberType:
    if info.isdir():
        return "directory"
    if info.isfile():
        return "file"
    if info.issym():
        return "symlink"
    if info.islnk():
        return "hardlink"
    if info.isdev() or info.isfifo():
        return "special"
    return "unknown"


def _collision_findings(
    container_path: str,
    member_paths: list[str],
) -> list[Finding]:
    findings: list[Finding] = []
    seen: dict[str, tuple[int, str]] = {}
    reported: set[str] = set()
    for index, member_path in enumerate(member_paths, start=1):
        key = member_path.replace("\\", "/").casefold()
        previous = seen.get(key)
        if previous is None:
            seen[key] = (index, member_path)
            continue
        if key in reported:
            continue
        reported.add(key)
        previous_index, previous_path = previous
        exact = previous_path == member_path
        findings.append(
            Finding(
                code=(
                    "DUPLICATE_ARCHIVE_MEMBER"
                    if exact
                    else "CASE_COLLIDING_ARCHIVE_MEMBER"
                ),
                severity="review",
                path=container_path,
                location=f"archive members {previous_index} and {index}",
                evidence="<archive-member-name-collision>",
                message=(
                    "Remove or rename colliding archive members before release."
                ),
            )
        )
    return findings


def inspect_archive(
    path: Path,
    relative_path: str,
    known_terms: KnownTermMatcher | None = None,
    *,
    max_members: int = 10000,
    max_name_chars: int = 4096,
) -> ArchiveInspection:
    """Inspect ZIP or TAR member tables without extracting files."""
    known_terms = known_terms or KnownTermMatcher()
    members: list[ContainerMember] = []
    findings: list[Finding] = []
    member_paths: list[str] = []
    complete = True
    reason = "Archive member table was inspected; member payloads were not opened"

    def add_member(
        member_path: str,
        member_type: ContainerMemberType,
        size_bytes: int,
        compressed_bytes: int,
        encrypted: bool,
    ) -> bool:
        nonlocal complete, reason
        member_index = len(member_paths) + 1
        if member_index > max_members:
            complete = False
            reason = "Archive member count exceeded the configured safety limit"
            findings.append(
                Finding(
                    code="ARCHIVE_MEMBER_LIMIT",
                    severity="review",
                    path=relative_path,
                    location="archive directory",
                    evidence=f"<members:>{max_members}>",
                    message=(
                        "Review this archive manually or raise the limit after "
                        "checking its source."
                    ),
                )
            )
            return False

        member_paths.append(member_path)
        if len(member_path) > max_name_chars:
            findings.append(
                Finding(
                    code="ARCHIVE_MEMBER_NAME_LIMIT",
                    severity="review",
                    path=relative_path,
                    location=f"archive member {member_index}",
                    evidence=f"<name-chars:>{max_name_chars}>",
                    message="Rename this unusually long archive member before release.",
                )
            )
        safe_name = _safe_member_name(member_path, member_index, max_name_chars)
        members.append(
            ContainerMember(
                container_path=relative_path,
                member_path=safe_name,
                member_type=member_type,
                size_bytes=max(0, int(size_bytes)),
                compressed_bytes=max(0, int(compressed_bytes)),
                encrypted=encrypted,
            )
        )
        findings.extend(
            _member_path_findings(
                relative_path,
                member_path,
                member_index,
                known_terms,
            )
        )
        if member_type in {"symlink", "hardlink", "special", "unknown"}:
            findings.append(
                Finding(
                    code="ARCHIVE_SPECIAL_MEMBER",
                    severity="review",
                    path=relative_path,
                    location=f"archive member {member_index}",
                    evidence=f"<archive-member-type:{member_type}>",
                    message=(
                        "Review or remove this link or special archive member; "
                        "it was not followed."
                    ),
                )
            )
        return True

    if path.name.lower().endswith(".zip"):
        encrypted_members = 0
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                encrypted = bool(info.flag_bits & 0x1)
                if encrypted:
                    encrypted_members += 1
                if not add_member(
                    info.filename,
                    _zip_member_type(info),
                    info.file_size,
                    info.compress_size,
                    encrypted,
                ):
                    break
        if encrypted_members:
            complete = False
            reason = "Encrypted archive member payloads were not accessible"
            findings.append(
                Finding(
                    code="ENCRYPTED_ARCHIVE",
                    severity="high",
                    path=relative_path,
                    location="ZIP directory",
                    evidence=f"<encrypted-members:{encrypted_members}>",
                    message=(
                        "Remove encryption or review this archive separately before release."
                    ),
                )
            )
    else:
        with tarfile.open(path, mode="r:*") as archive:
            for info in archive:
                if not add_member(
                    info.name,
                    _tar_member_type(info),
                    info.size,
                    0,
                    False,
                ):
                    break
                if info.issym() or info.islnk():
                    member_index = len(member_paths)
                    if _unsafe_member_path(info.linkname):
                        findings.append(
                            Finding(
                                code="ARCHIVE_LINK_PATH_TRAVERSAL",
                                severity="high",
                                path=relative_path,
                                location=f"archive member {member_index}",
                                evidence=redacted(
                                    "unsafe-archive-link",
                                    info.linkname,
                                ),
                                message=(
                                    "Remove this archive link because its target is unsafe."
                                ),
                            )
                        )

    findings.extend(_collision_findings(relative_path, member_paths))
    total_size = sum(member.size_bytes for member in members)
    total_compressed = sum(member.compressed_bytes for member in members)
    high_ratio = (
        total_size >= _HIGH_RATIO_MIN_BYTES
        and total_compressed > 0
        and total_size / total_compressed >= _HIGH_COMPRESSION_RATIO
    )
    if total_size >= _LARGE_ARCHIVE_BYTES or high_ratio:
        findings.append(
            Finding(
                code="ARCHIVE_EXPANSION_RISK",
                severity="review",
                path=relative_path,
                location="archive directory",
                evidence=f"<declared-uncompressed-bytes:{total_size}>",
                message=(
                    "Review this archive separately; its declared expansion size "
                    "or compression ratio is unusually large."
                ),
            )
        )
    return ArchiveInspection(
        members=tuple(members),
        findings=tuple(findings),
        complete=complete,
        reason=reason,
    )
