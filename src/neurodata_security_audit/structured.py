"""Check named fields in JSON, TSV and CSV files."""

from __future__ import annotations

import csv
import io
import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path

from .detectors import redacted
from .models import Finding

_DOB_KEYS = {"date_of_birth", "birth_date", "birthdate", "birthday", "dob"}
_PHONE_KEYS = {"phone", "phone_number", "telephone", "tel", "mobile"}
_NAME_KEYS = {
    "family_name",
    "first_name",
    "first_given_name",
    "forename",
    "given_name",
    "last_name",
    "last_family_name",
    "middle_name",
    "surname",
    "subject_name",
    "patient_name",
    "participant_name",
}
_DIRECT_ID_KEYS = {
    "medical_record_number",
    "medical_record_id",
    "mrn",
    "national_id",
    "national_identifier",
    "passport_number",
    "social_security_number",
    "ssn",
    "nhs_number",
    "health_insurance_number",
    "health_insurance_id",
    "health_id",
    "driver_license_number",
    "driver_licence_number",
    "driver_license_id",
    "driver_licence_id",
    "tax_id",
    "taxpayer_id",
    "personal_number",
}
_LINKED_ID_KEYS = {
    "genetic_id",
    "hospital_id",
    "legacy_id",
    "original_id",
    "original_subject_id",
    "patient_id",
    "source_id",
    "source_participant_id",
    "source_subject_id",
}
_ADDRESS_KEYS = {
    "home_address",
    "postal_address",
    "street_address",
}
_CONTEXT_ADDRESS_KEYS = {"address", "postal_code", "postcode", "zip_code"}
_HOST_KEYS = {"host", "hostname", "computer_name", "machine_name", "workstation"}
_NETWORK_ADDRESS_KEYS = {"ip", "ip_address", "host_ip", "server_ip"}
_DEVICE_ADDRESS_KEYS = {"mac", "mac_address", "device_address"}
_ACCOUNT_KEYS = {"account_name", "login", "user", "username"}
_PERSONNEL_KEYS = {"experimenter", "operator", "physician", "technician"}
_DEVICE_IDENTIFIER_KEYS = {"device_id", "device_serial", "serial_number"}
_FREE_TEXT_KEYS = {"comment", "comments", "patient_history", "patient_state"}
_RECORDING_DATE_KEYS = {
    "acq_date",
    "acq_datetime",
    "acq_time",
    "acquisition_date",
    "acquisition_date_time",
    "acquisition_datetime",
    "acquisition_time",
    "recording_date",
    "recording_date_time",
    "recording_datetime",
    "recording_time",
    "record_date",
    "record_datetime",
    "record_time",
    "measurement_date",
    "measurement_date_time",
    "measurement_datetime",
    "measurement_time",
    "meas_date",
    "scan_date",
    "scan_datetime",
}
_PLACEHOLDERS = {"", "n/a", "na", "none", "null", "unknown", "x"}
_TECHNICAL_PLACEHOLDERS = {"0.0.0.0", "127.0.0.1", "example", "localhost"}
_PERSON_CONTEXT_PARTS = {
    "participant",
    "participants",
    "patient",
    "patients",
    "subject",
    "subjects",
}
_SAFE_LOCATION_KEYS = (
    _DOB_KEYS
    | _PHONE_KEYS
    | _NAME_KEYS
    | _DIRECT_ID_KEYS
    | _LINKED_ID_KEYS
    | _ADDRESS_KEYS
    | _CONTEXT_ADDRESS_KEYS
    | _HOST_KEYS
    | _NETWORK_ADDRESS_KEYS
    | _DEVICE_ADDRESS_KEYS
    | _ACCOUNT_KEYS
    | _PERSONNEL_KEYS
    | _DEVICE_IDENTIFIER_KEYS
    | _FREE_TEXT_KEYS
    | _RECORDING_DATE_KEYS
    | _PERSON_CONTEXT_PARTS
    | {
        "address",
        "demographics",
        "device_info",
        "full_name",
        "his_id",
        "id",
        "info",
        "metadata",
        "name",
        "record",
        "records",
        "runtime",
        "subject_info",
    }
)


def _normalise_key(key: object) -> str:
    text = str(key).strip()
    text = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", text)
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", text)
    text = re.sub(r"[^a-z0-9]+", "_", text.lower())
    return text.strip("_")


def _safe_location_key(key: object) -> str:
    normalised = _normalise_key(key)
    return normalised if normalised in _SAFE_LOCATION_KEYS else "<field>"


def _safe_location_path(path: tuple[object, ...]) -> str:
    return ".".join(_safe_location_key(part) for part in path)


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
    allow_context_address: bool = False,
    allow_context_id: bool = False,
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
    if normalised in _DIRECT_ID_KEYS:
        return Finding(
            code="DIRECT_PERSONAL_ID",
            severity="high",
            path=relative_path,
            location=location,
            evidence=redacted("personal-id", text),
            message="Remove or replace this direct personal identifier before release.",
        )
    if normalised in _LINKED_ID_KEYS or (
        allow_context_id and normalised in {"id", "his_id"}
    ):
        return Finding(
            code="LINKED_SOURCE_ID",
            severity="review",
            path=relative_path,
            location=location,
            evidence=redacted("linked-source-id", text),
            message=(
                "Confirm this linked identifier is an approved pseudonym and cannot "
                "reconnect the release to a source system."
            ),
        )
    if normalised in _ADDRESS_KEYS or (
        allow_context_address and normalised in _CONTEXT_ADDRESS_KEYS
    ):
        return Finding(
            code="POSTAL_ADDRESS_FIELD",
            severity="high",
            path=relative_path,
            location=location,
            evidence=redacted("postal-address", text),
            message="Remove this participant address before release.",
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
    for keys, code, kind, message in (
        (
            _HOST_KEYS,
            "LOCAL_HOSTNAME",
            "hostname",
            "Replace this local host name with a generic value.",
        ),
        (
            _NETWORK_ADDRESS_KEYS,
            "NETWORK_ADDRESS",
            "ip-address",
            "Confirm this network address is safe to share or replace it.",
        ),
        (
            _DEVICE_ADDRESS_KEYS,
            "DEVICE_ADDRESS",
            "device-address",
            "Remove this device address unless it is required and safe to share.",
        ),
        (
            _ACCOUNT_KEYS,
            "ACCOUNT_NAME",
            "account-name",
            "Replace this local account name with a generic value.",
        ),
    ):
        if normalised in keys:
            if text.casefold() in _TECHNICAL_PLACEHOLDERS:
                return None
            return Finding(
                code=code,
                severity="review",
                path=relative_path,
                location=location,
                evidence=redacted(kind, text),
                message=message,
            )
    if normalised in _PERSONNEL_KEYS:
        return Finding(
            code="PERSONNEL_FIELD",
            severity="review",
            path=relative_path,
            location=location,
            evidence=redacted("personnel-field", text),
            message="Confirm this staff name is intended for the release.",
        )
    if normalised in _DEVICE_IDENTIFIER_KEYS:
        return Finding(
            code="DEVICE_IDENTIFIER",
            severity="review",
            path=relative_path,
            location=location,
            evidence=redacted("device-identifier", text),
            message="Confirm this acquisition-device identifier is safe to share.",
        )
    if normalised in _FREE_TEXT_KEYS:
        return Finding(
            code="FREE_TEXT_METADATA",
            severity="review",
            path=relative_path,
            location=location,
            evidence=redacted("free-text-metadata", text),
            message="Review this free-text field for participant details and private paths.",
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
    except (json.JSONDecodeError, RecursionError, UnicodeError):
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
    try:
        for path, key, value in _json_fields(document):
            finding = _finding_for_field(
                key,
                value,
                relative_path,
                f"JSON field {_safe_location_path(path)}",
                allow_plain_name=_is_person_context(path[:-1]),
                allow_context_address=_is_person_context(path[:-1]),
                allow_context_id=_is_person_context(path[:-1]),
            )
            if finding is not None:
                findings.append(finding)
    except RecursionError:
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
                f"row {row_number}, column {_safe_location_key(key)}",
                allow_plain_name=allow_plain_name,
                allow_context_address=allow_plain_name,
                allow_context_id=allow_plain_name,
            )
            if finding is not None:
                findings.append(finding)
    return findings


def _xml_tag(tag: object) -> str:
    return str(tag).rsplit("}", 1)[-1]


def inspect_xml(text: str, relative_path: str) -> list[Finding]:
    """Check named XML fields without resolving document types or entities."""

    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I):
        return [
            Finding(
                code="UNSAFE_XML_DECLARATION",
                severity="review",
                path=relative_path,
                location="XML document",
                evidence="<redacted:xml-declaration>",
                message="Review this XML manually; document types and entities are not parsed.",
            )
        ]
    try:
        root = ET.fromstring(text)
    except (ET.ParseError, UnicodeError):
        return [
            Finding(
                code="MALFORMED_XML",
                severity="review",
                path=relative_path,
                location="XML document",
                evidence="<redacted:parse-error>",
                message="Repair this XML file; its named fields were not checked.",
            )
        ]

    findings: list[Finding] = []

    def visit(element: ET.Element, parents: tuple[object, ...]) -> None:
        tag = _xml_tag(element.tag)
        path = (*parents, tag)
        context = _is_person_context(path[:-1])
        if _normalise_key(tag) == "field":
            children = {
                _normalise_key(_xml_tag(child.tag)): (child.text or "").strip()
                for child in element
            }
            label = children.get("name", "")
            value = children.get("data", "")
            if label and value:
                finding = _finding_for_field(
                    label,
                    value,
                    relative_path,
                    "XML dynamic field "
                    + _safe_location_path(path),
                    allow_plain_name=context,
                    allow_context_address=context,
                    allow_context_id=context,
                )
                if finding is not None:
                    findings.append(finding)
            return
        text_value = (element.text or "").strip()
        if text_value and not list(element):
            finding = _finding_for_field(
                tag,
                text_value,
                relative_path,
                "XML field " + _safe_location_path(path),
                allow_plain_name=context,
                allow_context_address=context,
                allow_context_id=context,
            )
            if finding is not None:
                findings.append(finding)
        for key, value in element.attrib.items():
            finding = _finding_for_field(
                _xml_tag(key),
                value,
                relative_path,
                "XML attribute "
                + _safe_location_path((*path, key)),
                allow_plain_name=_is_person_context(path),
                allow_context_address=_is_person_context(path),
                allow_context_id=_is_person_context(path),
            )
            if finding is not None:
                findings.append(finding)
        for child in element:
            visit(child, path)

    try:
        visit(root, ())
    except RecursionError:
        return [
            Finding(
                code="MALFORMED_XML",
                severity="review",
                path=relative_path,
                location="XML document",
                evidence="<redacted:parse-error>",
                message="Repair this XML file; its named fields were not checked.",
            )
        ]
    return findings
