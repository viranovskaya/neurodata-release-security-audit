"""Read format metadata without loading EEG samples."""

from __future__ import annotations

import io
import re
import struct
import zipfile
import zlib
from collections.abc import Mapping
from datetime import date, datetime
from math import prod
from numbers import Number
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from xml.etree import ElementTree

from .detectors import (
    BIRTH_DATE_MESSAGE, KnownTermMatcher, participant_name_finding, redacted, scan_text,
)
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
_OFFICE_MAX_MEMBERS = 1000
_OFFICE_MAX_MEMBER_BYTES = 2 * 1024 * 1024
_OFFICE_MAX_TEXT_BYTES = 8 * 1024 * 1024
_OFFICE_XML_DECLARATIONS = (b"<!DOCTYPE", b"<!ENTITY")
_MATLAB_MAX_TEXT_ELEMENTS = 10000
_MATLAB_MAX_TEXT_VARIABLES = 100
_MATLAB_MAX_TEXT_BYTES = 64 * 1024
_MAT5_MAX_INFLATED_BYTES = 8 * 1024 * 1024
_MAT5_MAX_NODES = 1000
_MAT5_MAX_DEPTH = 8


def _read_mat5_text(path: Path) -> tuple[list[tuple[tuple[str, ...], str | None]], bool] | None:
    """Read bounded Level-5 text only; None delegates older MAT versions.

    Numeric payloads are skipped by offset, never converted to arrays. Compressed
    blocks need bounded inflation, which can contain raw signal bytes. Nested
    text inspection does not cover numeric metadata, objects or signal content.
    """
    fields: list[tuple[tuple[str, ...], str | None]] = []
    limited = False
    nodes = text_elements = text_bytes = inspected_bytes = inflated_bytes = compressed_bytes = 0
    with path.open("rb") as source:
        header = source.read(128)
        if len(header) != 128 or header[126:128] not in {b"IM", b"MI"}:
            if header.startswith(b"MATLAB 5.0 MAT-file"):
                return fields, False
            return None
        endian = "<" if header[126:128] == b"IM" else ">"
        if struct.unpack(endian + "H", header[124:126])[0] != 0x0100:
            return fields, False
        limited = any(header[116:124])  # A subsystem workspace is not inspected.
        size = source.seek(0, 2)
        if size == 128:
            return fields, False
        source.seek(128)

        def take(stream, count: int) -> bytes:
            nonlocal inspected_bytes
            if count < 0 or count > _MATLAB_MAX_TEXT_BYTES:
                raise ValueError("MAT metadata read budget")
            inspected_bytes += count
            if inspected_bytes > 4 * _MATLAB_MAX_TEXT_BYTES:
                raise ValueError("MAT metadata read budget")
            value = stream.read(count)
            if len(value) != count:
                raise ValueError("Truncated MAT metadata")
            return value

        def tag(stream, boundary: int):
            if stream.tell() + 8 > boundary:
                raise ValueError("Truncated MAT tag")
            raw = take(stream, 8)
            word, count = struct.unpack(endian + "II", raw)
            if word >> 16:
                count, kind = word >> 16, word & 0xffff
                if count > 4:
                    raise ValueError("Invalid small MAT tag")
                return kind, count, raw[4:4 + count], stream.tell()
            end = stream.tell() + count
            # miCOMPRESSED is not padded in files written by SciPy/MATLAB.
            finish = end if word == 15 else end + (-count % 8)
            if finish > boundary:
                raise ValueError("MAT element outside container")
            return word, count, None, finish

        def blob(stream, boundary: int, allowed: set[int], maximum: int) -> bytes:
            kind, count, inline, finish = tag(stream, boundary)
            if kind not in allowed or count > maximum:
                raise ValueError("Unsupported MAT metadata element")
            value = inline if inline is not None else take(stream, count)
            stream.seek(finish)
            return value

        def matrix(stream, end: int, parents: tuple[str, ...], depth: int) -> None:
            nonlocal limited, nodes, text_elements, text_bytes
            nodes += 1
            if nodes > _MAT5_MAX_NODES or depth > _MAT5_MAX_DEPTH:
                raise ValueError("MAT structure budget")
            flags = blob(stream, end, {6}, 8)
            if len(flags) != 8:
                raise ValueError("Invalid MAT flags")
            flags_word = struct.unpack(endian + "II", flags)[0]
            kind = flags_word & 0xff
            dims = blob(stream, end, {5}, 32)
            if len(dims) < 8 or len(dims) % 4:
                raise ValueError("Invalid MAT dimensions")
            shape = struct.unpack(endian + "i" * (len(dims) // 4), dims)
            if any(n < 0 for n in shape):
                raise ValueError("Negative MAT dimension")
            count = prod(shape)
            name = blob(stream, end, {1, 2, 16}, 256).decode("utf-8").rstrip("\x00")
            location = parents or (name,)
            if not parents and not name:
                raise ValueError("Unnamed MAT variable")
            if kind != 4:
                fields.append((location, None))
            if kind in {1, 2}:
                limited = True  # Text only, not all nested metadata semantics.
                if count > _MAT5_MAX_NODES:
                    raise ValueError("MAT container budget")
                names = [None]
                if kind == 2:
                    width_data = blob(stream, end, {5}, 4)
                    if len(width_data) != 4:
                        raise ValueError("Invalid MAT field width")
                    width = struct.unpack(endian + "i", width_data)[0]
                    if not 1 <= width <= 256:
                        raise ValueError("Invalid MAT field width")
                    raw_names = blob(stream, end, {1}, 100 * 256)
                    if len(raw_names) % width:
                        raise ValueError("Invalid MAT field table")
                    names = [part.split(b"\x00", 1)[0].decode("utf-8")
                             for part in (raw_names[i:i + width]
                                          for i in range(0, len(raw_names), width))]
                    if len(names) > 100 or len(set(names)) != len(names) or not all(names):
                        raise ValueError("Ambiguous MAT field table")
                if count * len(names) > _MAT5_MAX_NODES:
                    raise ValueError("MAT container budget")
                for _ in range(count):
                    for field in names:
                        child_kind, length, inline, finish = tag(stream, end)
                        if child_kind != 14 or inline is not None:
                            raise ValueError("Invalid MAT child matrix")
                        matrix(stream, stream.tell() + length,
                               location + (field,) if field is not None else location, depth + 1)
                        stream.seek(finish)
            elif kind == 4:
                if count + text_elements > _MATLAB_MAX_TEXT_ELEMENTS or len(shape) != 2:
                    limited = True
                    stream.seek(end)
                    return
                char_kind, length, inline, finish = tag(stream, end)
                if length + text_bytes > _MATLAB_MAX_TEXT_BYTES:
                    limited = True
                    stream.seek(end)
                    return
                encoding = {1: "ascii", 2: "ascii", 4: "utf-16-le" if endian == "<" else "utf-16-be",
                            16: "utf-8", 17: "utf-16-le" if endian == "<" else "utf-16-be",
                            18: "utf-32-le" if endian == "<" else "utf-32-be"}.get(char_kind)
                if encoding is None:
                    raise ValueError("Unsupported MAT character encoding")
                text = (inline if inline is not None else take(stream, length)).decode(encoding)
                stream.seek(finish)
                if len(text) != count:
                    raise ValueError("MAT character dimensions do not match")
                text_elements += count
                text_bytes += length
                # Empty arrays may have a huge row dimension but no text to emit.
                if count:
                    for row in range(shape[0]):
                        fields.append((location, text[row::shape[0]].rstrip("\x00 ")))
            elif kind in {5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15}:
                stream.seek(end)  # Never read/construct numeric or sparse arrays.
                return
            else:
                limited = True  # Objects, functions and opaque workspaces.
                stream.seek(end)
                return
            if stream.tell() != end:
                raise ValueError("Unconsumed MAT matrix content")

        try:
            while source.tell() < size:
                kind, count, inline, finish = tag(source, size)
                if inline is not None:
                    raise ValueError("Invalid top-level MAT element")
                if kind == 14:
                    matrix(source, source.tell() + count, (), 0)
                elif kind == 15:
                    remaining = _MAT5_MAX_INFLATED_BYTES - inflated_bytes
                    if (count + compressed_bytes > _MAT5_MAX_INFLATED_BYTES
                            or remaining <= 0):
                        limited = True
                        source.seek(finish)
                        continue
                    # Bound both input and output. No unbounded decompress()/flush().
                    compressed = source.read(count)
                    compressed_bytes += count
                    if len(compressed) != count:
                        raise ValueError("Truncated compressed MAT element")
                    decoder = zlib.decompressobj()
                    raw = decoder.decompress(compressed, remaining + 1)
                    inflated_bytes += len(raw)
                    if len(raw) > remaining:
                        limited = True
                        source.seek(finish)
                        continue
                    if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                        raise ValueError("Invalid compressed MAT stream")
                    with io.BytesIO(raw) as unpacked:
                        inner_kind, length, inner_inline, inner_finish = tag(unpacked, len(raw))
                        if inner_kind != 14 or inner_inline is not None or inner_finish != len(raw):
                            raise ValueError("Invalid compressed MAT matrix")
                        matrix(unpacked, unpacked.tell() + length, (), 0)
                else:
                    limited = True
                source.seek(finish)
        except (ValueError, UnicodeError, struct.error, zlib.error):
            limited = True
    return fields, not limited


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
    if code == "SUBJECT_NAME_FIELD":
        return participant_name_finding(text, path=path, location=location, kind=kind)
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
            message=BIRTH_DATE_MESSAGE,
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

    variable_info = {
        name: (shape, class_name)
        for name, shape, class_name in whosmat(path, chars_as_strings=False)
    }
    variables = set(variable_info)
    complete = "EEG" not in variables and "ALLEEG" not in variables
    metadata: dict[str, list[str]] = {}
    if not complete:
        selected = _read_mat5_text(path)
        if selected is not None:
            for field_path, value in selected[0]:
                if len(field_path) > 1 and value:
                    field = field_path[-1]
                    if field == "data" and not (
                        len(field_path) == 1 or
                        len(field_path) == 2 and field_path[0] in {"EEG", "ALLEEG"}
                    ):
                        field = "nested_data"
                    metadata.setdefault(field, []).append(value)
        # Keep the original flat-field pass independent of nested parsing budgets.
        # Text selection does not make nested numeric metadata fully inspected.
    available: list[str] = []
    elements_selected = 0
    for name in sorted(variables & (_EEGLAB_TEXT_FIELDS | {"data"})):
        shape, class_name = variable_info[name]
        # Numeric data is deliberately never loaded. Text data names a linked file.
        if name == "data" and class_name != "char":
            continue
        elements = prod(shape) if shape else 1
        if elements == 0:
            continue
        if name == "session" and elements == 1 and class_name in {
            "double", "single", "int8", "uint8", "int16", "uint16",
            "int32", "uint32", "int64", "uint64", "logical",
        }:
            # A numeric session index has no text to inspect; do not load it.
            continue
        if class_name != "char" or elements_selected + elements > _MATLAB_MAX_TEXT_ELEMENTS:
            complete = False
            continue
        available.append(name)
        elements_selected += elements
    if available:
        document = loadmat(
            path,
            variable_names=available,
            squeeze_me=True,
            struct_as_record=False,
        )
        for field in available:
            metadata.setdefault(field, []).extend(_plain_text_values(document.get(field)))
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
        matlab_class = item.attrs.get("MATLAB_class", b"")
        if isinstance(matlab_class, bytes):
            matlab_class = matlab_class.decode("ascii", errors="ignore")
        dtype = item.dtype
        if matlab_class == "char":
            data = item[()]
            chars = [chr(int(value)) for value in data.reshape(-1, order="F") if int(value)]
            text = "".join(chars).strip()
            if text:
                values.append(text)
            return
        if dtype.kind in {"S", "U"}:
            data = item[()]
            values.extend(_plain_text_values(data, limit - len(values)))
            return
        if dtype.kind == "O":
            data = item[()]
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
            text = value if field in {"comments", "history"} else f"{field}: {value}"
            findings.extend(scan_text(text + "\n", relative_path, known_terms))
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
                evidence="<incomplete-eeglab-metadata>",
                message=(
                    "Selected text may have been checked, but nested numeric metadata, "
                    "objects, references or oversized fields remain outside this pass. "
                    "Review incomplete coverage manually; compressed blocks may require "
                    "bounded byte decompression, but signal arrays are not constructed."
                ),
            )
        )
    return findings


def inspect_matlab_metadata(
    path: Path,
    relative_path: str,
    known_terms: KnownTermMatcher | None = None,
) -> list[Finding]:
    """Inspect MATLAB variable metadata and small text values, not arrays."""

    known_terms = known_terms or KnownTermMatcher()
    findings: list[Finding] = []
    limited_layouts = 0
    oversized_texts = 0
    with path.open("rb") as stream:
        prefix = stream.read(8)
    if prefix == b"\x89HDF\r\n\x1a\n":
        try:
            import h5py
        except ImportError as error:
            raise FormatReaderUnavailable(
                "Install the 'formats' extra to inspect MATLAB 7.3 metadata"
            ) from error
        selected_text_elements = 0
        selected_text_variables = 0
        selected_text_bytes = 0
        with h5py.File(path, "r") as document:
            for name in sorted(document.keys()):
                link = document.get(name, getlink=True)
                if isinstance(link, h5py.ExternalLink):
                    findings.append(
                        Finding(
                            code="EXTERNAL_DATA_REFERENCE",
                            severity="review",
                            path=relative_path,
                            location="MATLAB external variable",
                            evidence=redacted("external-hdf5-reference", link.filename),
                            message=(
                                "Move this referenced data inside the release or "
                                "review it manually."
                            ),
                        )
                    )
                    continue
                node = document[name]
                matlab_class = node.attrs.get("MATLAB_class", b"")
                if isinstance(matlab_class, bytes):
                    matlab_class = matlab_class.decode("ascii", errors="ignore")
                findings.extend(
                    scan_text(
                        f"variable: {name}; class: {matlab_class}; "
                        f"dimensions: {getattr(node, 'ndim', 0)}\n",
                        relative_path,
                        known_terms,
                    )
                )
                if isinstance(node, h5py.Group) or (
                    isinstance(node, h5py.Dataset) and node.dtype.kind == "O"
                ):
                    limited_layouts += 1
                    values = []
                else:
                    is_text_dataset = isinstance(node, h5py.Dataset) and (
                        matlab_class == "char" or node.dtype.kind in {"S", "U"}
                    )
                    elements = int(getattr(node, "size", 0))
                    text_bytes = int(getattr(node, "nbytes", elements))
                    if is_text_dataset and (
                        elements > _MATLAB_MAX_TEXT_ELEMENTS
                        or selected_text_elements + elements
                        > _MATLAB_MAX_TEXT_ELEMENTS
                        or selected_text_variables >= _MATLAB_MAX_TEXT_VARIABLES
                        or text_bytes > _MATLAB_MAX_TEXT_BYTES
                        or selected_text_bytes + text_bytes > _MATLAB_MAX_TEXT_BYTES
                    ):
                        oversized_texts += 1
                        values = []
                    elif is_text_dataset:
                        selected_text_elements += elements
                        selected_text_variables += 1
                        selected_text_bytes += text_bytes
                        values = _hdf5_text_values(node, h5py)
                    else:
                        values = []
                for value in values:
                    findings.extend(
                        scan_text(
                            f"{name}: {value}\n",
                            relative_path,
                            known_terms,
                        )
                    )
    else:
        try:
            from scipy.io import loadmat, whosmat
        except ImportError as error:
            raise FormatReaderUnavailable(
                "Install the 'formats' extra to inspect MATLAB metadata"
            ) from error
        # Keep character dimensions: the default collapses a long string to (1,).
        variables = whosmat(path, chars_as_strings=False)
        limited_layouts = sum(
            class_name in {"cell", "function", "object", "opaque", "struct", "unknown"}
            for _, _, class_name in variables
        )
        if limited_layouts:
            selected = _read_mat5_text(path)
            if selected is not None:
                for field_path, value in selected[0]:
                    if len(field_path) > 1 and value:
                        field = field_path[-1]
                        text = value if field in {"comments", "history", "notes"} else f"{field}: {value}"
                        findings.extend(scan_text(text + "\n", relative_path, known_terms))
        text_names: list[str] = []
        selected_text_elements = 0
        for name, shape, class_name in variables:
            if class_name not in {"char", "string"}:
                continue
            elements = prod(shape) if shape else 1
            if (
                elements > _MATLAB_MAX_TEXT_ELEMENTS
                or selected_text_elements + elements > _MATLAB_MAX_TEXT_ELEMENTS
                or len(text_names) >= _MATLAB_MAX_TEXT_VARIABLES
            ):
                oversized_texts += 1
                continue
            text_names.append(name)
            selected_text_elements += elements
        for name, shape, class_name in variables:
            findings.extend(
                scan_text(
                    f"variable: {name}; class: {class_name}; dimensions: {len(shape)}\n",
                    relative_path,
                    known_terms,
                )
            )
        if text_names:
            document = loadmat(
                path,
                variable_names=text_names,
                squeeze_me=True,
                struct_as_record=False,
            )
            for name in text_names:
                for value in _plain_text_values(document.get(name)):
                    findings.extend(
                        scan_text(
                            f"{name}: {value}\n",
                            relative_path,
                            known_terms,
                        )
                    )
    if limited_layouts:
        findings.append(
            Finding(
                code="MATLAB_METADATA_COVERAGE_LIMIT",
                severity="review",
                path=relative_path,
                location="MATLAB variable structure",
                evidence=f"<nested-or-reference-variables,count={limited_layouts}>",
                message=(
                    "Selected nested text may have been checked, but numeric metadata, "
                    "objects and reference-backed content were not fully inspected. "
                    "Review these variables manually; no signal arrays were constructed."
                ),
            )
        )
    if oversized_texts:
        findings.append(
            Finding(
                code="MATLAB_METADATA_COVERAGE_LIMIT",
                severity="review",
                path=relative_path,
                location="MATLAB text variables",
                evidence=f"<oversized-text-variables,count={oversized_texts}>",
                message=(
                    "Review these oversized text variables manually; their values were not "
                    "loaded by this bounded metadata pass."
                ),
            )
        )
    return findings


def _office_member_is_text(format_name: str, name: str) -> bool:
    lower = name.casefold()
    if lower.startswith("docprops/") and lower.endswith(".xml"):
        return True
    if lower.endswith(".rels"):
        return True
    if format_name == "xlsx":
        return (
            lower in {"xl/sharedstrings.xml", "xl/workbook.xml"}
            or lower.startswith("xl/comments")
            or lower.startswith("xl/persons/")
        ) and lower.endswith(".xml")
    return (
        lower == "word/document.xml"
        or lower.startswith("word/header")
        or lower.startswith("word/footer")
        or lower in {
            "word/comments.xml",
            "word/commentspeople.xml",
            "word/footnotes.xml",
            "word/endnotes.xml",
        }
    ) and lower.endswith(".xml")


def inspect_office_metadata(
    path: Path,
    relative_path: str,
    format_name: str,
    known_terms: KnownTermMatcher | None = None,
) -> list[Finding]:
    """Inspect bounded text metadata in XLSX or DOCX packages."""

    if format_name not in {"xlsx", "docx"}:
        raise ValueError(f"Unsupported Office format: {format_name}")
    known_terms = known_terms or KnownTermMatcher()
    findings: list[Finding] = []
    total_text_bytes = 0
    with zipfile.ZipFile(path) as document:
        members = document.infolist()
        if len(members) > _OFFICE_MAX_MEMBERS:
            raise ValueError("Office package contains too many members")
        names = {member.filename.casefold() for member in members}
        required = "xl/workbook.xml" if format_name == "xlsx" else "word/document.xml"
        if "[content_types].xml" not in names or required not in names:
            raise ValueError("Office package is missing a required document part")
        for member in members:
            lower = member.filename.casefold()
            posix_name = PurePosixPath(member.filename.replace("\\", "/"))
            windows_name = PureWindowsPath(member.filename)
            if (
                posix_name.is_absolute()
                or windows_name.is_absolute()
                or ".." in posix_name.parts
            ):
                findings.append(
                    Finding(
                        code="OFFICE_MEMBER_PATH_TRAVERSAL",
                        severity="high",
                        path=relative_path,
                        location="Office package member table",
                        evidence=redacted("unsafe-office-member", member.filename),
                        message="Remove this absolute or parent-traversing package member.",
                    )
                )
            if lower.endswith("vbaproject.bin") or lower.endswith("vbadata.xml"):
                findings.append(
                    Finding(
                        code="OFFICE_MACRO_CONTENT",
                        severity="review",
                        path=relative_path,
                        location="Office package member table",
                        evidence="<office-macro-content>",
                        message="Remove the macro or review its code and embedded data manually.",
                    )
                )
            if not _office_member_is_text(format_name, member.filename):
                continue
            if member.file_size > _OFFICE_MAX_MEMBER_BYTES:
                raise ValueError("Office metadata member exceeds the parsing limit")
            total_text_bytes += member.file_size
            if total_text_bytes > _OFFICE_MAX_TEXT_BYTES:
                raise ValueError("Office metadata exceeds the parsing limit")
            data = document.read(member)
            upper = data.upper()
            if any(marker in upper for marker in _OFFICE_XML_DECLARATIONS):
                raise ValueError("Office metadata contains a forbidden XML declaration")
            root = ElementTree.fromstring(data)
            if lower.endswith(".rels"):
                for relationship in root.iter():
                    if relationship.attrib.get("TargetMode", "").casefold() != "external":
                        continue
                    target = relationship.attrib.get("Target", "")
                    findings.append(
                        Finding(
                            code="EXTERNAL_DATA_REFERENCE",
                            severity="review",
                            path=relative_path,
                            location="Office external relationship",
                            evidence=redacted("office-external-reference", target),
                            message=(
                                "Remove this external link or confirm it is intended "
                                "for release."
                            ),
                        )
                    )
                continue
            text = "\n".join(part.strip() for part in root.itertext() if part.strip())
            if text:
                findings.extend(
                    scan_text(
                        text,
                        relative_path,
                        known_terms,
                        public_contact_context=lower.startswith("docprops/"),
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
                message=BIRTH_DATE_MESSAGE,
            )
        )

    parts = patient.split()
    if len(parts) >= 4 and (parts[2].upper() == "X" or _EDF_BIRTH_DATE.fullmatch(parts[2])):
        patient_name = parts[3]
        if patient_name.upper() not in {"X", "N/A", "NA", "NONE"} and (
            _looks_like_person_name(patient_name)
            or re.fullmatch(r"sub-[0-9]+", patient_name, re.I)
        ):
            findings.append(
                participant_name_finding(
                    patient_name,
                    path=relative_path,
                    location="EDF patient field",
                    kind="edf-patient-name",
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
