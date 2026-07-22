"""Deterministic detectors for small text metadata files."""

from __future__ import annotations

import re

from .models import Finding

_EMAIL = re.compile(r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])", re.I)
_LABELLED_PHONE = re.compile(
    r"\b(?:phone|telephone|tel|mobile)\s*[:=]\s*(\+?[0-9][0-9 ()-]{7,}[0-9])",
    re.I,
)
_LOCAL_PATHS = (
    re.compile(r"/(?:Users|home)/[^\s\"'<>]+"),
    re.compile(r"[A-Z]:\\Users\\[^\s\"'<>]+", re.I),
)
_BIRTH_DATE = re.compile(
    r"\b(?:date[ _-]*of[ _-]*birth|birth[ _-]*date|birthday|dob)\b\s*[:=,\t]\s*"
    r"(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|"
    r"\d{1,2}-[A-Z]{3}-\d{4})",
    re.I,
)
_SUBJECT_NAME = re.compile(
    r"^\s*(?:subject|patient|participant)[ _-]*name\s*[:=,\t]\s*(?!x\b|n/?a\b|none\b).+",
    re.I,
)
_ACQUISITION_DATE = re.compile(
    r"^\s*(?:acquisition|recording|measurement)[ _-]*(?:date|datetime)\s*[:=,\t]",
    re.I,
)
_BRAINVISION_NEW_SEGMENT = re.compile(
    r"^Mk\d+=New Segment,.*?,\d+,\d+,\d+,(\d{14,20})\s*$",
    re.I,
)
_SECRET_PATTERNS = (
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("bearer-token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}={0,2}\b", re.I)),
)


def redacted(kind: str, value: str) -> str:
    return f"<redacted:{kind},length={len(value)}>"


def scan_text(text: str, relative_path: str) -> list[Finding]:
    findings: list[Finding] = []
    suffix = relative_path.lower()
    for line_number, line in enumerate(text.splitlines(), start=1):
        location = f"line {line_number}"
        for match in _EMAIL.finditer(line):
            findings.append(
                Finding(
                    code="DIRECT_EMAIL",
                    severity="high",
                    path=relative_path,
                    location=location,
                    evidence=redacted("email", match.group(0)),
                    message="An email address should be reviewed before release.",
                )
            )
        for match in _LABELLED_PHONE.finditer(line):
            value = match.group(1)
            findings.append(
                Finding(
                    code="DIRECT_PHONE",
                    severity="high",
                    path=relative_path,
                    location=location,
                    evidence=redacted("phone", value),
                    message="A labelled phone number should be reviewed before release.",
                )
            )
        for pattern in _LOCAL_PATHS:
            for match in pattern.finditer(line):
                findings.append(
                    Finding(
                        code="LOCAL_PATH",
                        severity="review",
                        path=relative_path,
                        location=location,
                        evidence=redacted("local-path", match.group(0)),
                        message="A local computer path can reveal user or institution details.",
                    )
                )
        for match in _BIRTH_DATE.finditer(line):
            findings.append(
                Finding(
                    code="BIRTH_DATE_FIELD",
                    severity="high",
                    path=relative_path,
                    location=location,
                    evidence=redacted("birth-date-field", match.group(0)),
                    message="A labelled date of birth should not be released without review.",
                )
            )
        match = _SUBJECT_NAME.search(line)
        if match:
            findings.append(
                Finding(
                    code="SUBJECT_NAME_FIELD",
                    severity="high",
                    path=relative_path,
                    location=location,
                    evidence=redacted("subject-name-field", match.group(0)),
                    message="A populated participant-name field should be reviewed before release.",
                )
            )
        if _ACQUISITION_DATE.search(line):
            findings.append(
                Finding(
                    code="EXACT_RECORDING_DATE",
                    severity="review",
                    path=relative_path,
                    location=location,
                    evidence="<redacted:recording-date-field>",
                    message="An exact acquisition date may require shifting before release.",
                )
            )
        if suffix.endswith(".vmrk") and _BRAINVISION_NEW_SEGMENT.search(line):
            findings.append(
                Finding(
                    code="EXACT_RECORDING_DATE",
                    severity="review",
                    path=relative_path,
                    location=location,
                    evidence="<redacted:brainvision-timestamp>",
                    message="A BrainVision New Segment marker contains an exact timestamp.",
                )
            )
        for secret_kind, pattern in _SECRET_PATTERNS:
            for match in pattern.finditer(line):
                findings.append(
                    Finding(
                        code="POTENTIAL_SECRET",
                        severity="high",
                        path=relative_path,
                        location=location,
                        evidence=redacted(secret_kind, match.group(0)),
                        message="A credential-shaped value should be removed or verified.",
                    )
                )
    return findings
