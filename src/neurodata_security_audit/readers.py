"""Format-aware metadata readers that never load EEG samples."""

from __future__ import annotations

import re
from pathlib import Path

from .detectors import redacted, scan_text
from .models import Finding

_EDF_HEADER_BYTES = 256
_EDF_BIRTH_DATE = re.compile(r"\b\d{2}-[A-Z]{3}-\d{4}\b", re.I)
_EDF_DATE = re.compile(r"\d{2}\.\d{2}\.\d{2}")
_PLACEHOLDER_DATES = {"01.01.01", "01.01.85", "00.00.00"}
_BRAINVISION_FILE_REFERENCE = re.compile(
    r"^\s*(DataFile|MarkerFile)\s*=\s*(.*?)\s*$",
    re.I,
)


def decode_small_text(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def inspect_brainvision(text: str, relative_path: str) -> list[Finding]:
    """Check that linked files no longer expose pre-release source names."""

    expected_stem = Path(relative_path).stem
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = _BRAINVISION_FILE_REFERENCE.match(line)
        if match is None:
            continue
        value = match.group(2).strip().strip('"\'')
        if not value:
            continue
        referenced_stem = Path(value.replace("\\", "/")).stem
        if referenced_stem != expected_stem:
            findings.append(
                Finding(
                    code="SOURCE_FILENAME",
                    severity="review",
                    path=relative_path,
                    location=f"line {line_number}, {match.group(1)}",
                    evidence=redacted("brainvision-file-reference", value),
                    message=(
                        "A BrainVision file reference does not match the released filename "
                        "and may preserve a source-system name."
                    ),
                )
            )
    return findings


def inspect_edf_header(header: bytes, relative_path: str) -> list[Finding]:
    if len(header) < _EDF_HEADER_BYTES:
        return [
            Finding(
                code="MALFORMED_HEADER",
                severity="review",
                path=relative_path,
                location="EDF common header",
                evidence=f"<header-bytes:{len(header)}>",
                message="The EDF/BDF common header is shorter than 256 bytes.",
            )
        ]

    patient = header[8:88].decode("latin-1", errors="replace").strip()
    recording = header[88:168].decode("latin-1", errors="replace").strip()
    start_date = header[168:176].decode("ascii", errors="replace").strip()
    findings = scan_text(
        f"patient field: {patient}\nrecording field: {recording}\n",
        relative_path,
    )

    if patient and patient.upper() not in {"X", "X X X X"}:
        findings.append(
            Finding(
                code="SUBJECT_FIELD_POPULATED",
                severity="review",
                path=relative_path,
                location="EDF patient field",
                evidence=f"<redacted:edf-patient-field,length={len(patient)}>",
                message="The EDF/BDF patient field is populated and needs manual review.",
            )
        )

    birth_date = _EDF_BIRTH_DATE.search(patient)
    if birth_date:
        findings.append(
            Finding(
                code="BIRTH_DATE_FIELD",
                severity="high",
                path=relative_path,
                location="EDF patient field",
                evidence=f"<redacted:edf-birth-date,length={len(birth_date.group(0))}>",
                message="The EDF/BDF patient field contains a full date of birth.",
            )
        )

    parts = patient.split()
    if len(parts) >= 4 and (parts[2].upper() == "X" or _EDF_BIRTH_DATE.fullmatch(parts[2])):
        patient_name = parts[3]
        if patient_name.upper() not in {"X", "N/A", "NA", "NONE"}:
            findings.append(
                Finding(
                    code="SUBJECT_NAME_FIELD",
                    severity="high",
                    path=relative_path,
                    location="EDF patient field",
                    evidence=f"<redacted:edf-patient-name,length={len(patient_name)}>",
                    message="The EDF+ patient-name position is populated.",
                )
            )

    if recording and recording.upper() not in {"X", "STARTDATE X X X X"}:
        findings.append(
            Finding(
                code="RECORDING_INFO_FIELD",
                severity="review",
                path=relative_path,
                location="EDF recording field",
                evidence=f"<redacted:edf-recording-field,length={len(recording)}>",
                message="The EDF/BDF recording-information field needs manual review.",
            )
        )

    if _EDF_DATE.fullmatch(start_date) and start_date not in _PLACEHOLDER_DATES:
        findings.append(
            Finding(
                code="EXACT_RECORDING_DATE",
                severity="review",
                path=relative_path,
                location="EDF start-date field",
                evidence="<redacted:edf-start-date>",
                message="The EDF/BDF start date does not use a recognised placeholder value.",
            )
        )
    return findings
