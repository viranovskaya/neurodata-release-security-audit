"""Check named fields in JSON, TSV and CSV files."""

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
}
_RECORDING_DATE_KEYS = {
    "acquisition_date",
    "acquisition_date_time",
    "acquisition_datetime",
    "recording_date",
    "recording_date_time",
    "recording_datetime",
    "measurement_date",
    "measurement_date_time",
    "measurement_datetime",
    "meas_date",
}
_PLACEHOLDERS = {"", "n/a", "na", "none", "null", "unknown", "x"}
_PERSON_CONTEXT_PARTS = {
    "participant",
    "participants",
    "patient",
    "patients",
    "subject",
    "subjects",
}


def _normalise_key(key: object) -> str:
    text = str(key).strip()
    text = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", text)
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", text)
    text = re.sub(r"[^a-z0-9]+", "_", text.lower())
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
            message="Remove this date of birth or replace it according to the release policy.",
        )
    if normalised in _PHONE_KEYS:
        return Finding(
            code="DIRECT_PHONE",
            severity="high",
            path=relative_path,
            location=location,
            evidence=redacted("phone", text),
            message="Confirm this phone number is intentionally public; otherwise remove it.",
        )
    if normalised in _NAME_KEYS or (
        allow_plain_name and normalised in {"name", "full_name"}
    ):
        return Finding(
            code="SUBJECT_NAME_FIELD",
            severity="high",
            path=relative_path,
            location=location,
            evidence=redacted("subject-name", text),
            message="Remove or replace this participant name before release.",
        )
    if normalised in _RECORDING_DATE_KEYS:
        return Finding(
            code="EXACT_RECORDING_DATE",
            severity="review",
            path=relative_path,
            location=location,
            evidence=redacted("recording-date", text),
            message="Confirm this date is allowed or has been shifted as required.",
        )
    return None


def _json_fields(
    value: object,
    parents: tuple[object, ...] = (),
) -> Iterator[tuple[tuple[object, ...], object, object]]:
    if isinstance(value, dict):
        for key, child in value.items():
            path = (*parents, key)
            yield path, key, child
            yield from _json_fields(child, path)
    elif isinstance(value, list):
        for child in value:
            yield from _json_fields(child, parents)


def _is_person_context(path: tuple[object, ...]) -> bool:
    for key in path:
        if set(_normalise_key(key).split("_")) & _PERSON_CONTEXT_PARTS:
            return True
    return False


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
                message="Repair this JSON file; its named fields were not checked.",
            )
        ]

    findings: list[Finding] = []
    for path, key, value in _json_fields(document):
        field_path = ".".join(_normalise_key(part) for part in path)
        finding = _finding_for_field(
            key,
            value,
            relative_path,
            f"JSON field {field_path}",
            allow_plain_name=_is_person_context(path[:-1]),
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
                message="Repair this table; its named fields were not checked.",
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
