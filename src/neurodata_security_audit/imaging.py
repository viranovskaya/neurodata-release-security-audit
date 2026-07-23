"""Metadata-only readers for imaging files."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .detectors import KnownTermMatcher, redacted, scan_text
from .models import Finding
from .readers import FormatReaderUnavailable

_NIFTI_TEXT_FIELDS = ("descrip", "aux_file", "intent_name", "db_name")
_DICOM_TEXT_VRS = {
    "AE",
    "AS",
    "CS",
    "DA",
    "DS",
    "DT",
    "IS",
    "LO",
    "LT",
    "PN",
    "SH",
    "ST",
    "TM",
    "UC",
    "UI",
    "UR",
    "UT",
}
_DICOM_PIXEL_FIELDS = {
    "PixelData",
    "FloatPixelData",
    "DoubleFloatPixelData",
}
_DICOM_DOCUMENT_FIELDS = {
    "EncapsulatedDocument",
    "EncapsulatedDocumentLength",
}
_DICOM_UID_FIELDS = {
    "MediaStorageSOPInstanceUID",
    "ImplementationClassUID",
    "StudyInstanceUID",
    "SeriesInstanceUID",
    "SOPInstanceUID",
    "FrameOfReferenceUID",
    "SynchronizationFrameOfReferenceUID",
    "ConcatenationUID",
}
_DICOM_RULES = {
    "PatientName": (
        "SUBJECT_NAME_FIELD",
        "high",
        "dicom-patient-name",
        "Remove or replace this patient name before release.",
    ),
    "PatientBirthDate": (
        "BIRTH_DATE_FIELD",
        "high",
        "dicom-birth-date",
        "Remove this date of birth or replace it according to the release policy.",
    ),
    "PatientAddress": (
        "POSTAL_ADDRESS_FIELD",
        "high",
        "dicom-patient-address",
        "Remove this patient address before release.",
    ),
    "PatientTelephoneNumbers": (
        "DIRECT_PHONE",
        "high",
        "dicom-phone",
        "Remove this patient phone number before release.",
    ),
}
_DICOM_LINKED_ID_FIELDS = {
    "PatientID",
    "IssuerOfPatientID",
    "OtherPatientIDs",
    "MedicalRecordLocator",
    "AccessionNumber",
    "StudyID",
    "AdmissionID",
}
_DICOM_DATE_FIELDS = {
    "StudyDate",
    "SeriesDate",
    "AcquisitionDate",
    "ContentDate",
    "InstanceCreationDate",
    "AcquisitionDateTime",
}
_DICOM_PERSONNEL_FIELDS = {
    "ReferringPhysicianName",
    "PerformingPhysicianName",
    "OperatorsName",
    "PhysiciansOfRecord",
    "NameOfPhysiciansReadingStudy",
}
_DICOM_SITE_FIELDS = {
    "InstitutionName",
    "InstitutionAddress",
    "InstitutionalDepartmentName",
}
_DICOM_DEVICE_FIELDS = {
    "DeviceSerialNumber",
    "StationName",
    "GantryID",
    "DetectorID",
    "PlateID",
    "ImplementationVersionName",
    "SourceApplicationEntityTitle",
    "SendingApplicationEntityTitle",
    "ReceivingApplicationEntityTitle",
}
_DICOM_FREE_TEXT_FIELDS = {
    "StudyDescription",
    "SeriesDescription",
    "ProtocolName",
    "PatientComments",
    "ImageComments",
    "PerformedProcedureStepDescription",
}
_DICOM_DEMOGRAPHIC_FIELDS = {
    "PatientAge",
    "PatientSex",
    "PatientSize",
    "PatientWeight",
    "EthnicGroup",
    "Occupation",
}


def _load_nibabel():
    try:
        import nibabel
    except ImportError as error:
        raise FormatReaderUnavailable("nibabel is not installed") from error
    return nibabel


def _load_pydicom():
    try:
        import pydicom
    except ImportError as error:
        raise FormatReaderUnavailable("pydicom is not installed") from error
    return pydicom


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


def _dicom_rule(keyword: str):
    if keyword in _DICOM_RULES:
        return _DICOM_RULES[keyword]
    if keyword in _DICOM_LINKED_ID_FIELDS:
        return (
            "LINKED_SOURCE_ID",
            "review",
            "dicom-linked-id",
            "Confirm this source identifier cannot reconnect the release.",
        )
    if keyword in _DICOM_DATE_FIELDS:
        return (
            "EXACT_RECORDING_DATE",
            "review",
            "dicom-date",
            "Confirm this date is allowed or has been shifted as required.",
        )
    if keyword in _DICOM_PERSONNEL_FIELDS:
        return (
            "PERSONNEL_FIELD",
            "review",
            "dicom-personnel",
            "Confirm this staff name is intended for the release.",
        )
    if keyword in _DICOM_SITE_FIELDS:
        return (
            "SITE_IDENTIFIER",
            "review",
            "dicom-site",
            "Confirm this institution or department value is safe to share.",
        )
    if keyword in _DICOM_DEVICE_FIELDS:
        return (
            "DEVICE_IDENTIFIER",
            "review",
            "dicom-device",
            "Confirm this acquisition-device identifier is safe to share.",
        )
    if keyword in _DICOM_FREE_TEXT_FIELDS:
        return (
            "FREE_TEXT_METADATA",
            "review",
            "dicom-free-text",
            "Review this free-text field for participant or site details.",
        )
    if keyword in _DICOM_DEMOGRAPHIC_FIELDS:
        return (
            "DEMOGRAPHIC_FIELD",
            "review",
            "dicom-demographic",
            "Confirm this demographic value is allowed by the release policy.",
        )
    if keyword in _DICOM_UID_FIELDS:
        return (
            "DICOM_UID",
            "review",
            "dicom-uid",
            "Confirm this DICOM UID was retained or replaced according to policy.",
        )
    return None


def inspect_dicom_metadata(
    path: Path,
    relative_path: str,
    known_terms: KnownTermMatcher | None = None,
    *,
    max_elements: int = 10000,
    max_depth: int = 16,
    max_text_chars: int = 4096,
) -> list[Finding]:
    """Inspect DICOM metadata while stopping before pixel data."""
    pydicom = _load_pydicom()
    dataset = pydicom.dcmread(
        str(path),
        stop_before_pixels=True,
        force=False,
        defer_size=1024 * 1024,
    )
    findings: list[Finding] = []
    elements_seen = 0
    limit_reported = False

    def add_limit_finding(message: str) -> None:
        nonlocal limit_reported
        if limit_reported:
            return
        limit_reported = True
        findings.append(
            Finding(
                code="DICOM_METADATA_LIMIT",
                severity="review",
                path=relative_path,
                location="DICOM metadata",
                evidence="<dicom-metadata-limit>",
                message=message,
            )
        )

    def visit(current: object, depth: int) -> None:
        nonlocal elements_seen
        if depth > max_depth:
            add_limit_finding(
                "Nested DICOM metadata exceeded the safe depth limit; review it manually."
            )
            return
        for element in current:
            elements_seen += 1
            if elements_seen > max_elements:
                add_limit_finding(
                    "DICOM metadata exceeded the element limit; review it manually."
                )
                return

            keyword = str(getattr(element, "keyword", "") or "")
            tag = getattr(element, "tag", None)
            if bool(getattr(tag, "is_private", False)):
                group = int(getattr(tag, "group", 0))
                element_number = int(getattr(tag, "element", 0))
                findings.append(
                    Finding(
                        code="DICOM_PRIVATE_TAG",
                        severity="review",
                        path=relative_path,
                        location="DICOM private tag",
                        evidence=f"<private-tag:{group:04x},{element_number:04x}>",
                        message=(
                            "Review or remove this private DICOM element before release."
                        ),
                    )
                )
                continue

            location = f"DICOM {keyword}" if keyword else "DICOM metadata field"
            if keyword in _DICOM_PIXEL_FIELDS:
                findings.append(
                    Finding(
                        code="DICOM_PIXEL_DATA_PRESENT",
                        severity="review",
                        path=relative_path,
                        location=location,
                        evidence="<pixel-data-not-opened>",
                        message="Pixel data was not opened and needs a separate image review.",
                    )
                )
                continue
            if keyword in _DICOM_DOCUMENT_FIELDS:
                findings.append(
                    Finding(
                        code="ENCAPSULATED_DOCUMENT_PRESENT",
                        severity="high",
                        path=relative_path,
                        location=location,
                        evidence="<encapsulated-document-not-opened>",
                        message=(
                            "Remove or separately review this encapsulated document "
                            "before release."
                        ),
                    )
                )
                continue

            vr = str(getattr(element, "VR", ""))
            if vr == "SQ":
                visit(element.value, depth + 1)
                if elements_seen > max_elements:
                    return
                continue
            if vr not in _DICOM_TEXT_VRS:
                continue

            value = str(element.value).strip()
            if not value:
                continue
            if len(value) > max_text_chars:
                value = value[:max_text_chars]
                findings.append(
                    Finding(
                        code="DICOM_TEXT_TRUNCATED",
                        severity="review",
                        path=relative_path,
                        location=location,
                        evidence=f"<text-chars:>{max_text_chars}>",
                        message=(
                            "This DICOM text value exceeded the safe inspection limit; "
                            "review it manually."
                        ),
                    )
                )

            findings.extend(
                replace(item, location=location)
                for item in scan_text(value, relative_path, known_terms)
            )
            rule = _dicom_rule(keyword)
            if rule is not None:
                code, severity, kind, message = rule
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

            if keyword in {
                "BurnedInAnnotation",
                "RecognizableVisualFeatures",
            } and value.upper() not in {
                "NO",
                "N",
                "FALSE",
                "0",
            }:
                findings.append(
                    Finding(
                        code="BURNED_IN_ANNOTATION",
                        severity="high",
                        path=relative_path,
                        location=location,
                        evidence=(
                            "<burned-in-annotation-present>"
                            if keyword == "BurnedInAnnotation"
                            else "<recognizable-visual-features-present>"
                        ),
                        message=(
                            (
                                "Pixel annotations may contain identifying text; "
                                if keyword == "BurnedInAnnotation"
                                else "The image may contain recognizable visual features; "
                            )
                            + "perform a separate image review before release."
                        ),
                    )
                )
            if keyword == "PatientIdentityRemoved" and value.upper() not in {
                "YES",
                "Y",
                "TRUE",
                "1",
            }:
                findings.append(
                    Finding(
                        code="DICOM_IDENTITY_NOT_REMOVED",
                        severity="high",
                        path=relative_path,
                        location=location,
                        evidence="<identity-removed:not-confirmed>",
                        message=(
                            "The DICOM file says patient identity was not removed; "
                            "stop and review the export."
                        ),
                    )
                )

    file_meta = getattr(dataset, "file_meta", None)
    if file_meta is not None:
        visit(file_meta, 0)
    visit(dataset, 0)
    return findings
