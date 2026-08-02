"""Read format metadata without loading EEG samples."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, datetime
from numbers import Number
from pathlib import Path, PureWindowsPath
from typing import Any

from .detectors import KnownTermMatcher, redacted, scan_text
from .models import Finding, ReferenceEntry, Severity
from .references import inspect_local_reference

_EDF_HEADER_BYTES = 256
_GIT_LFS_PREFIX = b"version https://git-lfs.github.com/spec/v1"
_EDF_BIRTH_DATE = re.compile(r"\b\d{2}-[A-Z]{3}-\d{4}\b", re.I)
_EDF_DATE = re.compile(r"\d{2}\.\d{2}\.\d{2}")
_PLACEHOLDER_DATES = {"01.01.01", "01.01.85", "00.00.00"}
_BRAINVISION_FILE_REFERENCE = re.compile(
    r"^\s*(DataFile|MarkerFile)\s*=\s*(.*?)\s*$",
    re.I,
)
_PLACEHOLDER_VALUES = {"", "n/a", "na", "none", "null", "unknown", "x"}
_EEGLAB_TEXT_FIELDS = {
    "comments",
    "condition",
    "filename",
    "filepath",
    "group",
    "history",
    "session",
    "setname",
    "subject",
}


class FormatReaderUnavailable(RuntimeError):
    """Raised when an optional format reader is not installed."""


def _load_mne():
    try:
        import mne
    except ImportError as error:
        raise FormatReaderUnavailable(
            "Install the 'formats' extra to inspect FIF, EEGLAB SET and EGI MFF metadata"
        ) from error
    return mne


def _metadata_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        text = value.isoformat()
    else:
        text = str(value).strip()
    if text.casefold() in _PLACEHOLDER_VALUES:
        return None
    return text


def _metadata_finding(
    *,
    code: str,
    severity: Severity,
    path: str,
    location: str,
    kind: str,
    value: object,
    message: str,
) -> Finding | None:
    text = _metadata_value(value)
    if text is None:
        return None
    return Finding(
        code=code,
        severity=severity,
        path=path,
        location=location,
        evidence=redacted(kind, text),
        message=message,
    )


def _has_nonzero_identifier(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(_has_nonzero_identifier(child) for child in value.values())
    if isinstance(value, (list, tuple)):
        return any(_has_nonzero_identifier(child) for child in value)
    if isinstance(value, Number):
        return value != 0
    if hasattr(value, "reshape"):
        return any(
            _has_nonzero_identifier(child.item() if hasattr(child, "item") else child)
            for child in value.reshape(-1)
        )
    return _metadata_value(value) is not None


def _named_metadata_values(
    value: object,
    parents: tuple[str, ...] = (),
):
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = (*parents, str(key))
            yield path, child
            yield from _named_metadata_values(child, path)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _named_metadata_values(child, parents)


def inspect_mne_info(
    info: Mapping[str, Any],
    relative_path: str,
    known_terms: KnownTermMatcher | None = None,
) -> list[Finding]:
    """Check privacy-relevant fields exposed through an MNE Info object."""

    known_terms = known_terms or KnownTermMatcher()
    findings: list[Finding] = []
    subject = info.get("subject_info")
    if isinstance(subject, Mapping):
        for key in ("first_name", "middle_name", "last_name"):
            value = subject.get(key)
            finding = _metadata_finding(
                code="SUBJECT_NAME_FIELD",
                severity="high",
                path=relative_path,
                location=f"MNE Info subject_info.{key}",
                kind="subject-name",
                value=value,
                message="Remove or replace this participant name before release.",
            )
            if finding is not None:
                findings.append(finding)
            text = _metadata_value(value)
            if text is not None:
                findings.extend(
                    scan_text(f"subject_info.{key}: {text}\n", relative_path, known_terms)
                )
        finding = _metadata_finding(
            code="BIRTH_DATE_FIELD",
            severity="high",
            path=relative_path,
            location="MNE Info subject_info.birthday",
            kind="birth-date",
            value=subject.get("birthday"),
            message="Remove this date of birth or replace it according to the release policy.",
        )
        if finding is not None:
            findings.append(finding)
        for key in ("his_id", "id"):
            value = subject.get(key)
            finding = _metadata_finding(
                code="LINKED_SOURCE_ID",
                severity="review",
                path=relative_path,
                location=f"MNE Info subject_info.{key}",
                kind="linked-source-id",
                value=value,
                message=(
                    "Confirm this identifier is an approved pseudonym and cannot "
                    "reconnect the release to a source system."
                ),
            )
            if finding is not None:
                findings.append(finding)
            text = _metadata_value(value)
            if text is not None:
                findings.extend(
                    scan_text(f"subject_info.{key}: {text}\n", relative_path, known_terms)
                )

    finding = _metadata_finding(
        code="EXACT_RECORDING_DATE",
        severity="review",
        path=relative_path,
        location="MNE Info meas_date",
        kind="recording-date",
        value=info.get("meas_date"),
        message="Confirm this date is allowed or has been shifted as required.",
    )
    if finding is not None:
        findings.append(finding)
    experimenter = _metadata_value(info.get("experimenter"))
    if experimenter is not None:
        findings.extend(
            scan_text(f"experimenter: {experimenter}\n", relative_path, known_terms)
        )

    finding = _metadata_finding(
        code="PERSONNEL_FIELD",
        severity="review",
        path=relative_path,
        location="MNE Info experimenter",
        kind="personnel-field",
        value=info.get("experimenter"),
        message="Confirm this staff name is intended for the release.",
    )
    if finding is not None:
        findings.append(finding)

    device = info.get("device_info")
    if isinstance(device, Mapping):
        for key in ("serial", "site"):
            value = device.get(key)
            finding = _metadata_finding(
                code="DEVICE_IDENTIFIER",
                severity="review",
                path=relative_path,
                location=f"MNE Info device_info.{key}",
                kind="device-identifier",
                value=value,
                message="Confirm this acquisition-device identifier is safe to share.",
            )
            if finding is not None:
                findings.append(finding)
            text = _metadata_value(value)
            if text is not None:
                findings.extend(
                    scan_text(f"device_info.{key}: {text}\n", relative_path, known_terms)
                )

    identifier_fields = [
        key
        for key in ("file_id", "meas_id")
        if isinstance(info.get(key), Mapping)
        and _has_nonzero_identifier(info.get(key, {}).get("machid"))
    ]
    if identifier_fields:
        findings.append(
            Finding(
                code="ACQUISITION_SYSTEM_ID",
                severity="review",
                path=relative_path,
                location="MNE Info " + "/".join(identifier_fields),
                evidence=f"<redacted:fiff-identifier-fields,count={len(identifier_fields)}>",
                message=(
                    "Confirm these acquisition-system identifiers were reset by the "
                    "release anonymisation step."
                ),
            )
        )

    for key in ("proj_id", "proj_name"):
        finding = _metadata_finding(
            code="PROJECT_IDENTIFIER",
            severity="review",
            path=relative_path,
            location=f"MNE Info {key}",
            kind="project-identifier",
            value=info.get(key),
            message="Confirm this internal project identifier is intended for the release.",
        )
        if finding is not None:
            findings.append(finding)

    for container_name in ("proc_history", "helium_info"):
        for path, value in _named_metadata_values(info.get(container_name)):
            key = path[-1].casefold()
            location = f"MNE Info {container_name}.{key}"
            if key in {"date", "meas_date", "measurement_date"}:
                finding = _metadata_finding(
                    code="EXACT_RECORDING_DATE",
                    severity="review",
                    path=relative_path,
                    location=location,
                    kind="processing-date",
                    value=value,
                    message="Confirm this processing date is allowed or was shifted as required.",
                )
            elif key == "experimenter":
                finding = _metadata_finding(
                    code="PERSONNEL_FIELD",
                    severity="review",
                    path=relative_path,
                    location=location,
                    kind="personnel-field",
                    value=value,
                    message="Confirm this staff name is intended for the release.",
                )
            elif key in {"machid", "orig_file_guid"}:
                finding = _metadata_finding(
                    code="ACQUISITION_SYSTEM_ID",
                    severity="review",
                    path=relative_path,
                    location=location,
                    kind="acquisition-system-id",
                    value=value,
                    message="Confirm this acquisition-system identifier is safe to share.",
                )
            else:
                finding = None
            if finding is not None:
                findings.append(finding)

    for key in ("description", "proj_name", "working_dir", "meas_file", "mri_file"):
        value = _metadata_value(info.get(key))
        if value is not None:
            findings.extend(
                scan_text(f"{key}: {value}\n", relative_path, known_terms)
            )
            if key == "description":
                findings.append(
                    Finding(
                        code="FREE_TEXT_METADATA",
                        severity="review",
                        path=relative_path,
                        location="MNE Info description",
                        evidence=redacted("free-text-metadata", value),
                        message="Review this free-text description for names and private details.",
                    )
                )
    return findings


def _plain_text_values(value: object, limit: int = 100) -> list[str]:
    """Return small string values without expanding numeric arrays."""

    values: list[str] = []

    def visit(item: object) -> None:
        if len(values) >= limit or item is None:
            return
        if isinstance(item, str):
            text = item.strip()
            if text:
                values.append(text)
            return
        if isinstance(item, bytes):
            text = item.decode("utf-8", errors="replace").strip()
            if text:
                values.append(text)
            return
        if isinstance(item, Mapping):
            for child in item.values():
                visit(child)
            return
        if isinstance(item, (list, tuple)):
            for child in item:
                visit(child)
            return
        dtype = getattr(item, "dtype", None)
        if dtype is not None and getattr(dtype, "kind", "") in {"O", "S", "U"}:
            for child in item.reshape(-1)[:limit]:
                visit(child.item() if hasattr(child, "item") else child)

    visit(value)
    return values


def _read_classic_eeglab_metadata(path: Path) -> tuple[dict[str, list[str]], bool]:
    try:
        from scipy.io import loadmat, whosmat
    except ImportError as error:
        raise FormatReaderUnavailable(
            "Install the 'formats' extra to inspect EEGLAB metadata"
        ) from error

    variable_info = {name: class_name for name, _, class_name in whosmat(path)}
    variables = set(variable_info)
    available = sorted(variables & _EEGLAB_TEXT_FIELDS)
    metadata: dict[str, list[str]] = {}
    if available:
        document = loadmat(
            path,
            variable_names=available,
            squeeze_me=True,
            struct_as_record=False,
        )
        for field in available:
            metadata[field] = _plain_text_values(document.get(field))
    if variable_info.get("data") == "char":
        document = loadmat(
            path,
            variable_names=["data"],
            squeeze_me=True,
            struct_as_record=False,
        )
        metadata["data"] = _plain_text_values(document.get("data"))
    complete = "EEG" not in variables and "ALLEEG" not in variables
    return metadata, complete


def _hdf5_text_values(node: object, h5py, limit: int = 100) -> list[str]:
    values: list[str] = []
    visited: set[int] = set()

    def visit(item: object) -> None:
        if len(values) >= limit:
            return
        if isinstance(item, h5py.Group):
            try:
                address = int(h5py.h5o.get_info(item.id).addr)
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
                address = id(item)
            if address in visited:
                return
            visited.add(address)
            for name in sorted(item.keys()):
                if name.casefold() == "data":
                    continue
                link = item.get(name, getlink=True)
                if isinstance(link, h5py.HardLink):
                    visit(item[name])
            return
        if not isinstance(item, h5py.Dataset) or item.size > 10000:
            return
        data = item[()]
        matlab_class = item.attrs.get("MATLAB_class", b"")
        if isinstance(matlab_class, bytes):
            matlab_class = matlab_class.decode("ascii", errors="ignore")
        if matlab_class == "char" and getattr(data, "dtype", None) is not None:
            chars = [chr(int(value)) for value in data.reshape(-1, order="F") if int(value)]
            text = "".join(chars).strip()
            if text:
                values.append(text)
            return
        dtype = getattr(data, "dtype", None)
        if dtype is not None and dtype.kind in {"S", "U"}:
            values.extend(_plain_text_values(data, limit - len(values)))
            return
        if dtype is not None and dtype.kind == "O":
            for reference in data.reshape(-1)[:limit]:
                if reference:
                    visit(item.file[reference])

    visit(node)
    return values


def _read_hdf5_eeglab_metadata(path: Path) -> tuple[dict[str, list[str]], bool]:
    try:
        import h5py
    except ImportError as error:
        raise FormatReaderUnavailable(
            "Install the 'formats' extra to inspect MATLAB 7.3 EEGLAB metadata"
        ) from error

    metadata: dict[str, list[str]] = {}
    with h5py.File(path, "r") as document:
        roots = [document]
        if "EEG" in document:
            link = document.get("EEG", getlink=True)
            if isinstance(link, h5py.HardLink) and isinstance(
                document["EEG"], h5py.Group
            ):
                roots.append(document["EEG"])
            elif isinstance(link, h5py.ExternalLink):
                metadata.setdefault("external_reference", []).append(link.filename)
        for field in sorted(_EEGLAB_TEXT_FIELDS):
            for root in roots:
                if field in root:
                    link = root.get(field, getlink=True)
                    if isinstance(link, h5py.HardLink):
                        metadata.setdefault(field, []).extend(
                            _hdf5_text_values(root[field], h5py)
                        )
                    elif isinstance(link, h5py.ExternalLink):
                        metadata.setdefault("external_reference", []).append(
                            link.filename
                        )
        for root in roots:
            if "data" not in root:
                continue
            link = root.get("data", getlink=True)
            if isinstance(link, h5py.ExternalLink):
                metadata.setdefault("external_reference", []).append(link.filename)
    return metadata, False


def _read_eeglab_metadata(path: Path) -> tuple[dict[str, list[str]], bool]:
    with path.open("rb") as stream:
        prefix = stream.read(8)
    if prefix == b"\x89HDF\r\n\x1a\n":
        return _read_hdf5_eeglab_metadata(path)
    return _read_classic_eeglab_metadata(path)


def inspect_eeglab_metadata(
    path: Path,
    relative_path: str,
    known_terms: KnownTermMatcher | None = None,
    dataset_root: Path | None = None,
    reference_entries: list[ReferenceEntry] | None = None,
) -> list[Finding]:
    """Inspect EEGLAB fields that MNE Info does not preserve."""

    known_terms = known_terms or KnownTermMatcher()
    metadata, complete = _read_eeglab_metadata(path)
    findings: list[Finding] = []
    root = (dataset_root or path.parent).resolve()
    for field, values in sorted(metadata.items()):
        for index, value in enumerate(values, start=1):
            location = f"EEGLAB field {field}"
            if len(values) > 1:
                location += f"[{index}]"
            findings.extend(scan_text(f"{field}: {value}\n", relative_path, known_terms))
            if field == "data":
                reference_inspection = inspect_local_reference(
                    root=root,
                    source_file=path,
                    source_path=relative_path,
                    value=value,
                    location=location,
                )
                findings.extend(reference_inspection.findings)
                if reference_entries is not None:
                    reference_entries.extend(reference_inspection.entries)
            if field == "external_reference":
                normalised = value.replace("\\", "/")
                windows_path = PureWindowsPath(value)
                candidate = Path(normalised)
                outside = windows_path.is_absolute() or candidate.is_absolute()
                if not outside:
                    try:
                        (path.parent / candidate).resolve().relative_to(root)
                    except ValueError:
                        outside = True
                if outside or field == "external_reference":
                    findings.append(
                        Finding(
                            code="EXTERNAL_DATA_REFERENCE",
                            severity="review",
                            path=relative_path,
                            location=location,
                            evidence=redacted("external-data-reference", value),
                            message=(
                                "Move this referenced data inside the release directory or "
                                "review the EEGLAB file manually."
                            ),
                        )
                    )
                    if reference_entries is not None:
                        reference_entries.append(
                            ReferenceEntry(
                                source_path=relative_path,
                                location=location,
                                target="<external-hdf5-reference>",
                                status="external",
                                reason=(
                                    "EEGLAB metadata uses an external HDF5 reference"
                                ),
                            )
                        )
            if field in {"comments", "history"}:
                findings.append(
                    Finding(
                        code="FREE_TEXT_METADATA",
                        severity="review",
                        path=relative_path,
                        location=location,
                        evidence=redacted("free-text-metadata", value),
                        message=(
                            "Review this EEGLAB free-text field for participant details and "
                            "private processing paths."
                        ),
                    )
                )
            if field == "subject":
                findings.append(
                    Finding(
                        code="LINKED_SOURCE_ID",
                        severity="review",
                        path=relative_path,
                        location=location,
                        evidence=redacted("linked-source-id", value),
                        message=(
                            "Confirm this subject label is an approved pseudonym and cannot "
                            "reconnect the release to a source system."
                        ),
                    )
                )
            elif field == "filename":
                if Path(value.replace("\\", "/")).name != Path(relative_path).name:
                    findings.append(
                        Finding(
                            code="SOURCE_FILENAME",
                            severity="review",
                            path=relative_path,
                            location=location,
                            evidence=redacted("eeglab-file-reference", value),
                            message=(
                                "Confirm this source filename is intended; otherwise replace it "
                                "with the released filename."
                            ),
                        )
                    )
    if not complete:
        findings.append(
            Finding(
                code="EEGLAB_METADATA_COVERAGE_LIMIT",
                severity="review",
                path=relative_path,
                location="EEGLAB MATLAB structure",
                evidence="<nested-matlab-structure>",
                message=(
                    "Review this legacy nested EEGLAB structure manually; loading it without "
                    "the signal data is not supported by this metadata pass."
                ),
            )
        )
    return findings


def _read_mne_info(path: Path, format_name: str):
    mne = _load_mne()
    if format_name == "fif":
        return mne.io.read_info(path, verbose="ERROR"), None
    if format_name == "eeglab":
        raw = mne.io.read_raw_eeglab(path, preload=False, verbose="ERROR")
        return raw.info, raw
    if format_name == "mff":
        raw = mne.io.read_raw_egi(
            path,
            preload=False,
            events_as_annotations=True,
            verbose="ERROR",
        )
        return raw.info, raw
    if format_name == "kit":
        raw = mne.io.read_raw_kit(path, preload=False, verbose="ERROR")
        return raw.info, raw
    raise ValueError(f"Unknown format reader: {format_name}")


def inspect_mne_format(
    path: Path,
    relative_path: str,
    format_name: str,
    known_terms: KnownTermMatcher | None = None,
) -> list[Finding]:
    """Read format metadata through MNE without preloading signal samples."""

    info, raw = _read_mne_info(path, format_name)
    try:
        if raw is not None and bool(getattr(raw, "preload", False)):
            return [
                Finding(
                    code="FORMAT_PRELOADED_SIGNAL",
                    severity="review",
                    path=relative_path,
                    location=f"{format_name.upper()} reader",
                    evidence="<reader-preloaded-data>",
                    message=(
                        "Review this file manually; the reader loaded signal data instead "
                        "of metadata only."
                    ),
                )
            ]
        return inspect_mne_info(info, relative_path, known_terms)
    finally:
        close = getattr(raw, "close", None)
        if callable(close):
            close()


def decode_small_text(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def _looks_like_person_name(value: str) -> bool:
    parts = [part for part in re.split(r"[_-]+", value.strip()) if part]
    return bool(parts) and all(part.isalpha() for part in parts)


def inspect_brainvision(text: str, relative_path: str) -> list[Finding]:
    """Check file references left inside BrainVision metadata."""

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
                        "Confirm this BrainVision reference is intended; otherwise rename it "
                        "to match the released file."
                    ),
                )
            )
    return findings


def inspect_edf_header(
    header: bytes,
    relative_path: str,
    known_terms: KnownTermMatcher | None = None,
) -> list[Finding]:
    if not header:
        return [
            Finding(
                code="EMPTY_PLACEHOLDER",
                severity="info",
                path=relative_path,
                location="file content",
                evidence="<bytes:0>",
                message=(
                    "Confirm this empty fixture is intentional; no EDF/BDF header was checked."
                ),
            )
        ]
    if header.startswith(_GIT_LFS_PREFIX):
        return [
            Finding(
                code="GIT_LFS_POINTER",
                severity="info",
                path=relative_path,
                location="file content",
                evidence="<git-lfs-pointer>",
                message="Fetch the Git LFS payload before relying on this audit.",
            )
        ]
    if len(header) < _EDF_HEADER_BYTES:
        return [
            Finding(
                code="MALFORMED_HEADER",
                severity="review",
                path=relative_path,
                location="EDF common header",
                evidence=f"<header-bytes:{len(header)}>",
                message="Repair or replace this file; its EDF/BDF header was not checked.",
            )
        ]

    patient = header[8:88].decode("latin-1", errors="replace").strip()
    recording = header[88:168].decode("latin-1", errors="replace").strip()
    start_date = header[168:176].decode("ascii", errors="replace").strip()
    findings = scan_text(
        f"patient field: {patient}\nrecording field: {recording}\n",
        relative_path,
        known_terms,
    )

    if patient and patient.upper() not in {"X", "X X X X"}:
        findings.append(
            Finding(
                code="SUBJECT_FIELD_POPULATED",
                severity="review",
                path=relative_path,
                location="EDF patient field",
                evidence=f"<redacted:edf-patient-field,length={len(patient)}>",
                message="Confirm this patient field contains only approved pseudonymous metadata.",
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
                message="Remove this date of birth or replace it according to the release policy.",
            )
        )

    parts = patient.split()
    if len(parts) >= 4 and (parts[2].upper() == "X" or _EDF_BIRTH_DATE.fullmatch(parts[2])):
        patient_name = parts[3]
        if patient_name.upper() not in {"X", "N/A", "NA", "NONE"} and _looks_like_person_name(
            patient_name
        ):
            findings.append(
                Finding(
                    code="SUBJECT_NAME_FIELD",
                    severity="high",
                    path=relative_path,
                    location="EDF patient field",
                    evidence=f"<redacted:edf-patient-name,length={len(patient_name)}>",
                    message="Remove or replace this participant name before release.",
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
                message="Confirm this recording field contains no identifying information.",
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
                message="Confirm this date is allowed or has been shifted as required.",
            )
        )
    return findings
