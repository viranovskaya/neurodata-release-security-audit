"""Field-aware checks for JSON and delimited metadata."""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Iterator
from pathlib import Path

from .detectors import redacted
from .models import Finding

_DOB_KEYS = {"date_of_birth", "birth_date", "birthdate", "birthday", "dob"}
_PHONE_KEYS = {"phone", "phone_number", "telephone", "tel", "mobile"}
_NAME_KEYS = {
    "subject_name",
    "patient_name",
    "participant_name",
    "full_name",
}
_RECORDING_DATE_KEYS = {
    "acquisition_date",
    "acquisition_datetime",
    "recording_date",
    "recording_datetime",
    "measurement_date",
    "measurement_datetime",
    "meas_date",
}
_PLACEHOLDERS = {"", "n/a", "na", "none", "null", "unknown", "x"}


def _normalise_key(key: object) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(key).strip().lower())
    return text.strip("_")


def _display_value(value: object) -> str | None:
    if value is None or isinstance(value, (dict, list)):
        return None
    text = str(value).strip()
    if text.lower() in _PLACEHOLDERS:
        return None
    return text


def _finding_for_field(
    key: object,
    value: object,
    relative_path: str,
    location: str,
    *,
    allow_plain_name: bool = False,
) -> Finding | None:
    normalised = _normalise_key(key)
    text = _display_value(value)
    if text is None:
        return None

    if normalised in _DOB_KEYS:
        return Finding(
            code="BIRTH_DATE_FIELD",
            severity="high",
            path=relative_path,
            location=location,
            evidence=redacted("birth-date", text),
            message="A date-of-birth field is populated and should not be released without review.",
        )
    if normalised in _PHONE_KEYS:
        return Finding(
            code="DIRECT_PHONE",
            severity="high",
            path=relative_path,
            location=location,
            evidence=redacted("phone", text),
            message="A phone field is populated and should be reviewed before release.",
        )
    if normalised in _NAME_KEYS or (allow_plain_name and normalised == "name"):
        return Finding(
            code="SUBJECT_NAME_FIELD",
            severity="high",
            path=relative_path,
            location=location,
            evidence=redacted("subject-name", text),
            message="A participant-name field is populated and should be reviewed before release.",
        )
    if normalised in _RECORDING_DATE_KEYS:
        return Finding(
            code="EXACT_RECORDING_DATE",
            severity="review",
            path=relative_path,
            location=location,
            evidence=redacted("recording-date", text),
            message="An exact acquisition date may require shifting before release.",
        )
    return None


def _json_fields(value: object) -> Iterator[tuple[object, object]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from _json_fields(child)
    elif isinstance(value, list):
        for child in value:
            yield from _json_fields(child)


def inspect_json(text: str, relative_path: str) -> list[Finding]:
    try:
        document = json.loads(text)
    except (json.JSONDecodeError, UnicodeError):
        return [
            Finding(
                code="MALFORMED_JSON",
                severity="review",
                path=relative_path,
                location="JSON document",
                evidence="<redacted:parse-error>",
                message="The JSON file could not be parsed for field-aware checks.",
            )
        ]

    findings: list[Finding] = []
    for key, value in _json_fields(document):
        finding = _finding_for_field(
            key,
            value,
            relative_path,
            f"JSON field {_normalise_key(key)}",
        )
        if finding is not None:
            findings.append(finding)
    return findings


def inspect_delimited(text: str, relative_path: str, delimiter: str) -> list[Finding]:
    try:
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        if reader.fieldnames is None:
            return []
        rows = list(reader)
    except (csv.Error, UnicodeError):
        return [
            Finding(
                code="MALFORMED_TABLE",
                severity="review",
                path=relative_path,
                location="delimited table",
                evidence="<redacted:parse-error>",
                message="The table could not be parsed for field-aware checks.",
            )
        ]

    filename = Path(relative_path).name.lower()
    allow_plain_name = any(term in filename for term in ("participant", "subject", "patient"))
    findings: list[Finding] = []
    for row_number, row in enumerate(rows, start=2):
        for key, value in row.items():
            finding = _finding_for_field(
                key,
                value,
                relative_path,
                f"row {row_number}, column {_normalise_key(key)}",
                allow_plain_name=allow_plain_name,
            )
            if finding is not None:
                findings.append(finding)
    return findings
