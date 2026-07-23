"""Validate cross-file references without following external paths or symlinks."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from urllib.parse import urlsplit

from .detectors import redacted
from .models import Finding, ReferenceEntry

_BRAINVISION_REFERENCE = re.compile(
    r"^\s*(DataFile|MarkerFile)\s*=\s*(.*?)\s*$",
    re.IGNORECASE,
)
_BIDS_REFERENCE_KEYS = {
    "intendedfor",
    "associatedemptyroom",
    "sources",
    "rawsources",
}


@dataclass(frozen=True)
class ReferenceInspection:
    entries: tuple[ReferenceEntry, ...]
    findings: tuple[Finding, ...]


def _external_reference(value: str) -> bool:
    split = urlsplit(value)
    return bool(
        split.scheme
        and split.scheme.lower() not in {"bids"}
        or PureWindowsPath(value).is_absolute()
        or PurePosixPath(value.replace("\\", "/")).is_absolute()
    )


def _symlink_component(root: Path, candidate: Path) -> bool:
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return True
    current = root
    for part in relative.parts:
        current = current / part
        try:
            if current.is_symlink():
                return True
        except OSError:
            return True
    return False


def _reference_finding(
    code: str,
    source_path: str,
    location: str,
    value: str,
    message: str,
) -> Finding:
    return Finding(
        code=code,
        severity="review",
        path=source_path,
        location=location,
        evidence=redacted("file-reference", value),
        message=message,
    )


def inspect_local_reference(
    *,
    root: Path,
    source_file: Path,
    source_path: str,
    value: str,
    location: str,
    base: Path | None = None,
) -> ReferenceInspection:
    """Classify one reference without opening the target."""
    root = root.resolve()
    source_file = source_file.resolve(strict=False)
    if base is not None:
        base = base.resolve(strict=False)
    original = value.strip().strip("\"'")
    if not original:
        return ReferenceInspection((), ())

    if _external_reference(original):
        return ReferenceInspection(
            (
                ReferenceEntry(
                    source_path=source_path,
                    location=location,
                    target="<external-reference>",
                    status="external",
                    reason="Reference points outside the selected release",
                ),
            ),
            (
                _reference_finding(
                    "EXTERNAL_DATA_REFERENCE",
                    source_path,
                    location,
                    original,
                    "Move this target inside the release or review the reference manually.",
                ),
            ),
        )

    normalised = original.replace("\\", "/")
    if normalised.startswith("bids::"):
        normalised = normalised.removeprefix("bids::")
        base = root
    elif normalised.startswith("bids:"):
        return ReferenceInspection(
            (
                ReferenceEntry(
                    source_path=source_path,
                    location=location,
                    target="<external-bids-reference>",
                    status="external",
                    reason="Reference uses a named external BIDS dataset",
                ),
            ),
            (
                _reference_finding(
                    "EXTERNAL_DATA_REFERENCE",
                    source_path,
                    location,
                    original,
                    "Confirm this external BIDS dataset reference is intentional.",
                ),
            ),
        )

    relative_target = PurePosixPath(normalised)
    if ".." in relative_target.parts:
        return ReferenceInspection(
            (
                ReferenceEntry(
                    source_path=source_path,
                    location=location,
                    target="<parent-traversing-reference>",
                    status="external",
                    reason="Reference contains a parent traversal",
                ),
            ),
            (
                _reference_finding(
                    "EXTERNAL_DATA_REFERENCE",
                    source_path,
                    location,
                    original,
                    "Replace this parent-traversing reference with an internal path.",
                ),
            ),
        )

    candidate = Path(
        os.path.abspath((base or source_file.parent) / Path(normalised))
    )
    try:
        target_relative = candidate.relative_to(root).as_posix()
    except ValueError:
        return inspect_local_reference(
            root=root,
            source_file=source_file,
            source_path=source_path,
            value=f"/{normalised}",
            location=location,
            base=root,
        )

    if _symlink_component(root, candidate):
        return ReferenceInspection(
            (
                ReferenceEntry(
                    source_path=source_path,
                    location=location,
                    target="<symlinked-reference>",
                    status="through_symlink",
                    reason="Reference reaches a symlink and was not followed",
                ),
            ),
            (
                _reference_finding(
                    "REFERENCE_THROUGH_SYMLINK",
                    source_path,
                    location,
                    original,
                    "Replace this symlinked target with a regular file inside the release.",
                ),
            ),
        )

    try:
        parent_names = {entry.name for entry in candidate.parent.iterdir()}
    except OSError:
        parent_names = set()
    if candidate.name not in parent_names:
        case_matches = {
            name for name in parent_names if name.casefold() == candidate.name.casefold()
        }
        if case_matches:
            return ReferenceInspection(
                (
                    ReferenceEntry(
                        source_path=source_path,
                        location=location,
                        target="<case-mismatched-reference>",
                        status="case_mismatch",
                        reason="Reference spelling does not match the released filename",
                    ),
                ),
                (
                    _reference_finding(
                        "CASE_MISMATCHED_REFERENCE",
                        source_path,
                        location,
                        original,
                        "Match the reference spelling to the released filename exactly.",
                    ),
                ),
            )

    try:
        target_is_file = candidate.is_file()
    except OSError:
        target_is_file = False
    if not candidate.exists():
        return ReferenceInspection(
            (
                ReferenceEntry(
                    source_path=source_path,
                    location=location,
                    target="<missing-reference>",
                    status="missing",
                    reason="Referenced file is missing from the release",
                ),
            ),
            (
                _reference_finding(
                    "MISSING_DATA_REFERENCE",
                    source_path,
                    location,
                    original,
                    "Add the referenced file or correct this path before release.",
                ),
            ),
        )
    if not target_is_file:
        return ReferenceInspection(
            (
                ReferenceEntry(
                    source_path=source_path,
                    location=location,
                    target="<non-file-reference>",
                    status="not_regular_file",
                    reason="Reference target is not a regular file",
                ),
            ),
            (
                _reference_finding(
                    "INVALID_DATA_REFERENCE",
                    source_path,
                    location,
                    original,
                    "Replace this target with a regular file inside the release.",
                ),
            ),
        )
    return ReferenceInspection(
        (
            ReferenceEntry(
                source_path=source_path,
                location=location,
                target=target_relative,
                status="valid_internal",
                reason="Reference resolves to a regular file inside the release",
            ),
        ),
        (),
    )


def inspect_brainvision_references(
    text: str,
    path: Path,
    relative_path: str,
    root: Path,
) -> ReferenceInspection:
    entries: list[ReferenceEntry] = []
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = _BRAINVISION_REFERENCE.match(line)
        if match is None:
            continue
        inspection = inspect_local_reference(
            root=root,
            source_file=path,
            source_path=relative_path,
            value=match.group(2),
            location=f"line {line_number}, {match.group(1)}",
        )
        entries.extend(inspection.entries)
        findings.extend(inspection.findings)
    return ReferenceInspection(tuple(entries), tuple(findings))


def _subject_root(root: Path, source_file: Path) -> Path:
    try:
        relative = source_file.relative_to(root)
    except ValueError:
        return root
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        if part.startswith("sub-"):
            return current
    return root


def inspect_bids_json_references(
    text: str,
    path: Path,
    relative_path: str,
    root: Path,
) -> ReferenceInspection:
    try:
        value = json.loads(text)
    except (json.JSONDecodeError, UnicodeError):
        return ReferenceInspection((), ())
    entries: list[ReferenceEntry] = []
    findings: list[Finding] = []

    def visit(item: object, parents: tuple[str, ...] = ()) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                key_text = str(key)
                visit(child, parents + (key_text,))
            return
        if isinstance(item, list):
            for child in item:
                visit(child, parents)
            return
        if not parents or parents[-1].replace("_", "").casefold() not in {
            key.replace("_", "").casefold() for key in _BIDS_REFERENCE_KEYS
        }:
            return
        if not isinstance(item, str):
            return

        base = root if item.startswith(("bids::", "sub-")) else _subject_root(root, path)
        location = f"JSON field {parents[-1]}"
        inspection = inspect_local_reference(
            root=root,
            source_file=path,
            source_path=relative_path,
            value=item,
            location=location,
            base=base,
        )
        entries.extend(inspection.entries)
        findings.extend(inspection.findings)

    visit(value)
    return ReferenceInspection(tuple(entries), tuple(findings))
