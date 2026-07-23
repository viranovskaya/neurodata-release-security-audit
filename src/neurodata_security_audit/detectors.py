"""Scan small text metadata files."""

from __future__ import annotations

import re

from .models import Finding, Severity

_EMAIL = re.compile(r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])", re.I)
_LABELLED_PHONE = re.compile(
    r"\b(?:phone|telephone|tel|mobile)\s*[:=]\s*(\+?[0-9][0-9 ()-]{7,}[0-9])",
    re.I,
)
_LOCAL_PATHS = (
    re.compile(r"/(?:Users|home)/[^\s\"'<>]+"),
    re.compile(r"[A-Z]:\\Users\\[^\s\"'<>]+", re.I),
)
_NETWORK_PATHS = (
    re.compile(r"\\\\[A-Za-z0-9._-]+\\[^\s\"'<>]+"),
    re.compile(
        r"(?<![A-Za-z0-9:])/(?:Volumes|mnt|media|srv|scratch|cluster|data|tmp)/"
        r"[^\s\"'<>]+"
    ),
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
_DIRECT_PERSONAL_ID = re.compile(
    r"^\s*(?:medical[ _-]*record[ _-]*(?:number|id)|mrn|national[ _-]*(?:id|identifier)|"
    r"passport[ _-]*number|driver[ _-]*licen[cs]e[ _-]*(?:number|id)|"
    r"tax(?:payer)?[ _-]*id|personal[ _-]*number|social[ _-]*security[ _-]*number|"
    r"ssn|nhs[ _-]*number|health[ _-]*(?:insurance[ _-]*(?:number|id)|id))"
    r"\s*[:=,\t]\s*(?!x\b|n/?a\b|none\b).+",
    re.I,
)
_LINKED_SOURCE_ID = re.compile(
    r"^\s*(?:original|source|legacy|hospital)[ _-]*"
    r"(?:subject|participant|patient)?[ _-]*id\s*[:=,\t]\s*"
    r"(?!x\b|n/?a\b|none\b).+",
    re.I,
)
_SUBJECT_ADDRESS = re.compile(
    r"^\s*(?:subject|patient|participant)[ _-]*"
    r"(?:(?:home|postal|street)[ _-]*)?address\s*[:=,\t]\s*"
    r"(?!x\b|n/?a\b|none\b).+",
    re.I,
)
_ACQUISITION_DATE = re.compile(
    r"^\s*(?:(?:acq|acquisition|recording|measurement|scan)[ _-]*"
    r"(?:date|datetime|time)|meas[ _-]*date)\s*[:=,\t]",
    re.I,
)
_LABELLED_HOST = re.compile(
    r"\b(?:host|hostname|computer|workstation|machine)\s*[:=]\s*"
    r"[\"']?([A-Za-z0-9][A-Za-z0-9._-]{1,252})",
    re.I,
)
_IP_OCTET = r"(?:25[0-5]|2[0-4]\d|1?\d?\d)"
_LABELLED_IP = re.compile(
    rf"\b(?:ip|ip[ _-]*address|host[ _-]*ip|server[ _-]*ip)\s*[:=]\s*"
    rf"[\"']?({_IP_OCTET}(?:\.{_IP_OCTET}){{3}})",
    re.I,
)
_LABELLED_MAC = re.compile(
    r"\b(?:mac|mac[ _-]*address|device[ _-]*address)\s*[:=]\s*"
    r"[\"']?([0-9A-F]{2}(?::[0-9A-F]{2}){5})",
    re.I,
)
_LABELLED_ACCOUNT = re.compile(
    r"\b(?:login|user|username|account[ _-]*name)\s*[:=]\s*"
    r"[\"']?([A-Za-z0-9][A-Za-z0-9._-]{1,127})",
    re.I,
)
_BRAINVISION_NEW_SEGMENT = re.compile(
    r"^Mk\d+=New Segment,.*?,\d+,\d+,\d+,(\d{14,20})\s*$",
    re.I,
)
_SECRET_PATTERNS = (
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("gitlab-token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    (
        "sk-prefixed-token",
        re.compile(r"\bsk-(?:(?:proj|svcacct)-)?[A-Za-z0-9_-]{20,}\b"),
    ),
    (
        "jwt",
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."
            r"[A-Za-z0-9_-]{10,}\b"
        ),
    ),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("bearer-token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}={0,2}\b", re.I)),
    (
        "credential-assignment",
        re.compile(
            r"(?:^|[\s,{])[\"']?(?:api[_-]?key|client[_-]?secret|password|passwd|"
            r"access[_-]?token|auth[_-]?token|id[_-]?token|refresh[_-]?token|"
            r"session[_-]?token|webhook[_-]?secret|aws[_-]?secret[_-]?access[_-]?key|"
            r"private[_-]?key|secret[_-]?key)[\"']?\s*[:=]\s*"
            r"[\"']?[^\s\"'#,;]{8,}",
            re.I,
        ),
    ),
    (
        "database-credential",
        re.compile(
            r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://"
            r"[^:\s/@]+:[^@\s/]+@[^\s\"'<>]+",
            re.I,
        ),
    ),
    (
        "http-basic-auth",
        re.compile(
            r"\bhttps?://[^:\s/@]+:[^@\s/]+@[^\s\"'<>]+",
            re.I,
        ),
    ),
)
_TECHNICAL_PLACEHOLDERS = {
    "0.0.0.0",
    "127.0.0.1",
    "example",
    "localhost",
    "n/a",
    "na",
    "none",
    "null",
    "unknown",
}
_PATH_PHONE = re.compile(
    r"(?:phone|telephone|tel|mobile)[ _-]*(\+?[0-9][0-9 ()-]{7,}[0-9])",
    re.I,
)
_PATH_PERSONAL_ID = re.compile(
    r"(?:mrn|ssn|passport|nhs|driver[ _-]*licen[cs]e|tax[ _-]*id|health[ _-]*id)"
    r"[ _-]*([A-Za-z0-9][A-Za-z0-9._-]{3,})",
    re.I,
)
_PATH_BIRTH_DATE = re.compile(
    r"(?:dob|birth[ _-]*date|date[ _-]*of[ _-]*birth)[ _=-]*"
    r"(?:\d{4}[-.]\d{1,2}[-.]\d{1,2}|\d{1,2}[-.]\d{1,2}[-.]\d{2,4})",
    re.I,
)
_PATH_RECORDING_DATE = re.compile(
    r"(?:acq|acquisition|recording|scan)[ _-]*(?:date|time)?[ _=-]*"
    r"\d{4}[-.]\d{1,2}[-.]\d{1,2}",
    re.I,
)


def redacted(kind: str, value: str) -> str:
    return f"<redacted:{kind},length={len(value)}>"


class KnownTermMatcher:
    def __init__(
        self,
        terms: tuple[str, ...] = (),
        label: str = "known-identifier",
        *,
        bounded: bool = True,
    ) -> None:
        self.terms = terms
        self.label = label
        ordered = sorted(enumerate(terms), key=lambda item: (-len(item[1]), item[0]))
        alternatives = "|".join(
            f"(?P<t{index}>{re.escape(term)})" for index, term in ordered
        )
        if alternatives and bounded:
            alternatives = rf"(?<![^\W_])(?:{alternatives})(?![^\W_])"
        self.pattern = re.compile(alternatives, re.I) if alternatives else None

    def matches(self, value: str) -> tuple[str, ...]:
        if self.pattern is None:
            return ()
        indexes = {int(match.lastgroup[1:]) for match in self.pattern.finditer(value)}
        return tuple(self.terms[index] for index in sorted(indexes))

    def redact(self, value: str) -> str:
        if self.pattern is None:
            return value

        def replacement(match: re.Match[str]) -> str:
            index = int(match.lastgroup[1:]) + 1
            return f"<redacted:{self.label}-{index:03d}>"

        return self.pattern.sub(replacement, value)


def find_emails(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(match.group(0) for match in _EMAIL.finditer(value)))


def find_sensitive_path_values(
    value: str,
) -> tuple[tuple[str, Severity, str, str, str], ...]:
    matches: list[tuple[str, Severity, str, str, str]] = []
    for match in _PATH_PHONE.finditer(value):
        matches.append(
            (
                "DIRECT_PHONE",
                "high",
                "phone",
                match.group(0),
                "Rename this path to remove the phone number.",
            )
        )
    for match in _PATH_PERSONAL_ID.finditer(value):
        matches.append(
            (
                "DIRECT_PERSONAL_ID",
                "high",
                "personal-id",
                match.group(0),
                "Rename this path to remove the direct personal identifier.",
            )
        )
    for match in _PATH_BIRTH_DATE.finditer(value):
        matches.append(
            (
                "BIRTH_DATE_FIELD",
                "high",
                "birth-date",
                match.group(0),
                "Rename this path to remove the date of birth.",
            )
        )
    for match in _PATH_RECORDING_DATE.finditer(value):
        matches.append(
            (
                "EXACT_RECORDING_DATE",
                "review",
                "recording-date",
                match.group(0),
                "Rename this path if the exact recording date is not allowed.",
            )
        )
    for pattern in _LOCAL_PATHS:
        for match in pattern.finditer(value):
            matches.append(
                (
                    "LOCAL_PATH",
                    "review",
                    "local-path",
                    match.group(0),
                    "Rename this path to remove the local computer path.",
                )
            )
    for pattern in _NETWORK_PATHS:
        for match in pattern.finditer(value):
            matches.append(
                (
                    "NETWORK_PATH",
                    "review",
                    "network-path",
                    match.group(0),
                    "Rename this path to remove the network location.",
                )
            )
    for secret_kind, pattern in _SECRET_PATTERNS:
        for match in pattern.finditer(value):
            matches.append(
                (
                    "POTENTIAL_SECRET",
                    "high",
                    secret_kind,
                    match.group(0),
                    "Rename this path and rotate the value if it is a real credential.",
                )
            )
    return tuple(matches)


def scan_text(
    text: str,
    relative_path: str,
    known_terms: KnownTermMatcher | None = None,
    *,
    email_severity: Severity = "high",
) -> list[Finding]:
    known_terms = known_terms or KnownTermMatcher()
    findings: list[Finding] = []
    suffix = relative_path.lower()
    for line_number, line in enumerate(text.splitlines(), start=1):
        location = f"line {line_number}"
        for term in known_terms.matches(line):
            findings.append(
                Finding(
                    code="KNOWN_IDENTIFIER",
                    severity="high",
                    path=relative_path,
                    location=location,
                    evidence=redacted("known-identifier", term),
                    message="Remove or replace this known name or identifier before release.",
                )
            )
        for match in _EMAIL.finditer(line):
            findings.append(
                Finding(
                    code="DIRECT_EMAIL",
                    severity=email_severity,
                    path=relative_path,
                    location=location,
                    evidence=redacted("email", match.group(0)),
                    message="Confirm this email is intentionally public; otherwise remove it.",
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
                    message=(
                        "Confirm this phone number is intentionally public; "
                        "otherwise remove it."
                    ),
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
                        message=(
                            "Replace this local computer path with a relative or generic path."
                        ),
                    )
                )
        for pattern in _NETWORK_PATHS:
            for match in pattern.finditer(line):
                findings.append(
                    Finding(
                        code="NETWORK_PATH",
                        severity="review",
                        path=relative_path,
                        location=location,
                        evidence=redacted("network-path", match.group(0)),
                        message=(
                            "Replace this network or mounted-volume path with a relative "
                            "or generic path."
                        ),
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
                    message=(
                        "Remove this date of birth or replace it according to "
                        "the release policy."
                    ),
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
                    message="Remove or replace this participant name before release.",
                )
            )
        match = _DIRECT_PERSONAL_ID.search(line)
        if match:
            findings.append(
                Finding(
                    code="DIRECT_PERSONAL_ID",
                    severity="high",
                    path=relative_path,
                    location=location,
                    evidence=redacted("personal-id-field", match.group(0)),
                    message="Remove or replace this direct personal identifier before release.",
                )
            )
        match = _LINKED_SOURCE_ID.search(line)
        if match:
            findings.append(
                Finding(
                    code="LINKED_SOURCE_ID",
                    severity="review",
                    path=relative_path,
                    location=location,
                    evidence=redacted("linked-source-id-field", match.group(0)),
                    message=(
                        "Confirm this linked identifier is an approved pseudonym and "
                        "cannot reconnect the release to a source system."
                    ),
                )
            )
        match = _SUBJECT_ADDRESS.search(line)
        if match:
            findings.append(
                Finding(
                    code="POSTAL_ADDRESS_FIELD",
                    severity="high",
                    path=relative_path,
                    location=location,
                    evidence=redacted("postal-address-field", match.group(0)),
                    message="Remove this participant address before release.",
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
                    message="Confirm this date is allowed or has been shifted as required.",
                )
            )
        for pattern, code, kind, message in (
            (
                _LABELLED_HOST,
                "LOCAL_HOSTNAME",
                "hostname",
                "Replace this local host name with a generic value.",
            ),
            (
                _LABELLED_IP,
                "NETWORK_ADDRESS",
                "ip-address",
                "Confirm this network address is safe to share or replace it.",
            ),
            (
                _LABELLED_MAC,
                "DEVICE_ADDRESS",
                "device-address",
                "Remove this device address unless it is required and safe to share.",
            ),
            (
                _LABELLED_ACCOUNT,
                "ACCOUNT_NAME",
                "account-name",
                "Replace this local account name with a generic value.",
            ),
        ):
            match = pattern.search(line)
            if match and match.group(1).casefold() not in _TECHNICAL_PLACEHOLDERS:
                findings.append(
                    Finding(
                        code=code,
                        severity="review",
                        path=relative_path,
                        location=location,
                        evidence=redacted(kind, match.group(1)),
                        message=message,
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
                    message="Confirm this timestamp is allowed or has been shifted as required.",
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
                        message="If this is a real credential, remove it and rotate it.",
                    )
                )
    return findings
