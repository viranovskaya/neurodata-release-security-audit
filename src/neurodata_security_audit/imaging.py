"""Metadata-only readers for imaging files."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .detectors import KnownTermMatcher, redacted, scan_text
from .models import Finding
from .readers import FormatReaderUnavailable

_NIFTI_TEXT_FIELDS = ("descrip", "aux_file", "intent_name", "db_name")


def _load_nibabel():
    try:
        import nibabel
    except ImportError as error:
        raise FormatReaderUnavailable("nibabel is not installed") from error
    return nibabel


def _header_text(value: object) -> str | None:
    if hasattr(value, "tobytes"):
        raw = value.tobytes()
    elif isinstance(value, bytes):
        raw = value
    else:
        text = str(value).strip()
        return text or None
    raw = raw.rstrip(b"\x00 ")
    if not raw:
        return None
    for encoding in ("utf-8", "latin-1"):
        try:
            return raw.decode(encoding).strip() or None
        except UnicodeDecodeError:
            continue
    return None


def _field_finding(
    field: str,
    value: str,
    relative_path: str,
) -> Finding | None:
    location = f"NIfTI header {field}"
    if field == "descrip":
        return Finding(
            code="FREE_TEXT_METADATA",
            severity="review",
            path=relative_path,
            location=location,
            evidence=redacted("nifti-description", value),
            message="Review this NIfTI description for participant or site details.",
        )
    if field == "aux_file":
        return Finding(
            code="SOURCE_FILENAME",
            severity="review",
            path=relative_path,
            location=location,
            evidence=redacted("nifti-aux-file", value),
            message="Confirm this auxiliary filename or path belongs in the release.",
        )
    if field == "db_name":
        return Finding(
            code="LINKED_SOURCE_ID",
            severity="review",
            path=relative_path,
            location=location,
            evidence=redacted("nifti-database-name", value),
            message="Confirm this source database value cannot reconnect the release.",
        )
    return None


def inspect_nifti_metadata(
    path: Path,
    relative_path: str,
    known_terms: KnownTermMatcher | None = None,
) -> list[Finding]:
    """Inspect a NIfTI header without reading its voxel array."""
    nibabel = _load_nibabel()
    image = nibabel.load(str(path), mmap=False, keep_file_open=False)
    header = image.header
    findings: list[Finding] = []

    for field in _NIFTI_TEXT_FIELDS:
        try:
            raw_value = header[field]
        except (KeyError, TypeError, ValueError):
            continue
        value = _header_text(raw_value)
        if value is None:
            continue
        location = f"NIfTI header {field}"
        findings.extend(
            replace(item, location=location)
            for item in scan_text(value, relative_path, known_terms)
        )
        field_finding = _field_finding(field, value, relative_path)
        if field_finding is not None:
            findings.append(field_finding)

    extensions = getattr(header, "extensions", ())
    for index, extension in enumerate(extensions, start=1):
        try:
            extension_code = int(extension.get_code())
        except (AttributeError, TypeError, ValueError):
            extension_code = -1
        findings.append(
            Finding(
                code="NIFTI_EXTENSION_PRESENT",
                severity="review",
                path=relative_path,
                location=f"NIfTI extension {index}",
                evidence=f"<nifti-extension-code:{extension_code}>",
                message=(
                    "Review this NIfTI extension separately; its content was not "
                    "interpreted by the metadata-only reader."
                ),
            )
        )
    return findings
