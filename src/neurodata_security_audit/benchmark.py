"""Evaluate the scanner on labelled synthetic releases."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .benchmark_builders import build_case_data
from .html_report import render_html
from .reporting import render_json, render_markdown
from .scanner import ScanPolicy, scan_dataset


_FINDING_CLASSES = {
    "personal_identity": {
        "BIRTH_DATE_FIELD",
        "DIRECT_EMAIL",
        "DIRECT_PERSONAL_ID",
        "DIRECT_PHONE",
        "POSTAL_ADDRESS_FIELD",
        "SUBJECT_FIELD_POPULATED",
        "SUBJECT_NAME_FIELD",
    },
    "linked_identity": {
        "KNOWN_IDENTIFIER",
        "LINKED_SOURCE_ID",
        "PROJECT_IDENTIFIER",
    },
    "dates_and_demographics": {
        "DEMOGRAPHIC_FIELD",
        "EXACT_RECORDING_DATE",
    },
    "site_device_and_staff": {
        "ACQUISITION_SYSTEM_ID",
        "DEVICE_IDENTIFIER",
        "DICOM_UID",
        "PERSONNEL_FIELD",
        "RECORDING_INFO_FIELD",
        "SITE_IDENTIFIER",
    },
    "secrets_and_paths": {
        "LOCAL_PATH",
        "NETWORK_PATH",
        "POTENTIAL_SECRET",
        "SENSITIVE_CONFIG_DIRECTORY",
        "SENSITIVE_CONFIG_FILE",
        "SUBJECT_KEY_FILE",
    },
    "free_text_and_sources": {
        "FREE_TEXT_METADATA",
        "SOURCE_FILENAME",
    },
    "release_structure": {
        "ARCHIVE_LINK_PATH_TRAVERSAL",
        "ARCHIVE_MEMBER_PATH_TRAVERSAL",
        "ARCHIVE_SPECIAL_MEMBER",
        "CASE_COLLIDING_RELEASE_PATH",
        "CASE_MISMATCHED_REFERENCE",
        "EXTERNAL_DATA_REFERENCE",
        "MISSING_DATA_REFERENCE",
        "SPECIAL_FILESYSTEM_ENTRY",
        "UNEXPECTED_DIRECTORY",
        "UNEXPECTED_FILE",
    },
    "embedded_content": {
        "BURNED_IN_ANNOTATION",
        "DICOM_PIXEL_DATA_PRESENT",
        "ENCAPSULATED_DOCUMENT_PRESENT",
        "NIFTI_EXTENSION_PRESENT",
    },
}


def _finding_class(code: str) -> str:
    for name, codes in _FINDING_CLASSES.items():
        if code in codes:
            return name
    return "coverage_or_other"


def _load_specification(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="utf-8"))
    case_files = document.get("case_files")
    if case_files is None:
        return document

    cases: list[dict[str, object]] = []
    for relative_path in case_files:
        case_path = path.parent / _relative_path(relative_path)
        case_document = json.loads(case_path.read_text(encoding="utf-8"))
        if case_document.get("schema_version") != document.get("schema_version"):
            raise ValueError("Benchmark case files must use the suite schema version")
        cases.extend(case_document.get("cases", []))
    return {
        "schema_version": document["schema_version"],
        "cases": cases,
    }


def _relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError("Benchmark file paths must stay inside their case directory")
    return path


def _matches(expected: dict[str, str], actual: dict[str, str]) -> bool:
    for field, value in expected.items():
        if field.endswith("_contains"):
            actual_field = field.removesuffix("_contains")
            if value not in actual[actual_field]:
                return False
        elif actual.get(field) != value:
            return False
    return True


def _finding_identity(finding: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        finding["code"],
        finding["severity"],
        finding["path"],
        finding["location"],
    )


def _score_case(case: dict[str, object], root: Path) -> dict[str, object]:
    for relative_path, content in case["files"].items():
        path = root / _relative_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    if case.get("builder") is not None:
        build_case_data(root, case["builder"])

    policy = ScanPolicy(sensitive_terms=tuple(case["sensitive_terms"]))
    report = scan_dataset(root, policy)
    finding_groups: dict[
        tuple[str, str, str, str],
        list[dict[str, str]],
    ] = {}
    report_data = report.to_dict()
    for finding in report_data["findings"]:
        finding_groups.setdefault(_finding_identity(finding), []).append(finding)
    actual = [group[0] for group in finding_groups.values()]
    duplicate_findings = [
        {
            "identity": {
                "code": identity[0],
                "severity": identity[1],
                "path": identity[2],
                "location": identity[3],
            },
            "extra_count": len(group) - 1,
        }
        for identity, group in finding_groups.items()
        if len(group) > 1
    ]
    matched_indices: set[int] = set()
    expected_results: list[dict[str, object]] = []

    for expected in case["expected_findings"]:
        match = next(
            (
                index
                for index, finding in enumerate(actual)
                if index not in matched_indices and _matches(expected, finding)
            ),
            None,
        )
        if match is not None:
            matched_indices.add(match)
        expected_results.append({"expected": expected, "matched": match is not None})

    unexpected = [
        finding
        for index, finding in enumerate(actual)
        if index not in matched_indices
    ]
    expected_reference_results: list[dict[str, object]] = []
    matched_reference_indices: set[int] = set()
    expected_references = case.get("expected_references")
    if expected_references is not None:
        for expected in expected_references:
            match = next(
                (
                    index
                    for index, reference in enumerate(report_data["references"])
                    if index not in matched_reference_indices
                    and _matches(expected, reference)
                ),
                None,
            )
            if match is not None:
                matched_reference_indices.add(match)
            expected_reference_results.append(
                {"expected": expected, "matched": match is not None}
            )
    unexpected_references = (
        [
            reference
            for index, reference in enumerate(report_data["references"])
            if index not in matched_reference_indices
        ]
        if expected_references is not None
        else []
    )

    expected_container_results: list[dict[str, object]] = []
    matched_container_indices: set[int] = set()
    expected_container_members = case.get("expected_container_members")
    if expected_container_members is not None:
        for expected in expected_container_members:
            match = next(
                (
                    index
                    for index, member in enumerate(report_data["container_members"])
                    if index not in matched_container_indices
                    and _matches(expected, member)
                ),
                None,
            )
            if match is not None:
                matched_container_indices.add(match)
            expected_container_results.append(
                {"expected": expected, "matched": match is not None}
            )
    unexpected_container_members = (
        [
            member
            for index, member in enumerate(report_data["container_members"])
            if index not in matched_container_indices
        ]
        if expected_container_members is not None
        else []
    )

    expected_coverage_results: list[dict[str, object]] = []
    for expected in case.get("expected_coverage", []):
        matched = any(
            _matches(expected, coverage)
            for coverage in report_data["coverage"]
        )
        expected_coverage_results.append(
            {"expected": expected, "matched": matched}
        )
    rendered = "\n".join(
        (render_json(report), render_markdown(report), render_html(report))
    )
    masking_failures = [
        value for value in case["seeded_values"] if value in rendered
    ]

    return {
        "case_id": case["case_id"],
        "split": case["split"],
        "format": case["format"],
        "expected": expected_results,
        "unexpected_findings": unexpected,
        "duplicate_findings": duplicate_findings,
        "expected_references": expected_reference_results,
        "unexpected_references": unexpected_references,
        "expected_container_members": expected_container_results,
        "unexpected_container_members": unexpected_container_members,
        "expected_coverage": expected_coverage_results,
        "masking_failures": masking_failures,
        "integrity_passed": (
            report.manifest_recheck_passed
            and report.release_tree_recheck_passed
        ),
    }


def _group_summary(
    results: list[dict[str, object]],
    field: str,
) -> dict[str, dict[str, int | float | None]]:
    groups: dict[str, dict[str, object]] = {}
    for result in results:
        name = str(result[field])
        group = groups.setdefault(
            name,
            {
                "cases": 0,
                "expected_findings": 0,
                "matched_findings": 0,
                "unexpected_findings": 0,
                "duplicate_findings": 0,
                "control_cases": 0,
                "clean_controls": 0,
            },
        )
        group["cases"] += 1
        group["expected_findings"] += len(result["expected"])
        group["matched_findings"] += sum(
            item["matched"] for item in result["expected"]
        )
        group["unexpected_findings"] += len(result["unexpected_findings"])
        group["duplicate_findings"] += sum(
            item["extra_count"] for item in result["duplicate_findings"]
        )
        if not result["expected"]:
            group["control_cases"] += 1
            group["clean_controls"] += not result["unexpected_findings"]

    output: dict[str, dict[str, int | float | None]] = {}
    for name, group in sorted(groups.items()):
        expected = int(group["expected_findings"])
        matched = int(group["matched_findings"])
        unexpected = int(group["unexpected_findings"])
        controls = int(group["control_cases"])
        output[name] = {
            **group,
            "target_recall": matched / expected if expected else None,
            "labelled_precision": (
                matched / (matched + unexpected)
                if matched + unexpected
                else None
            ),
            "control_specificity": (
                int(group["clean_controls"]) / controls if controls else None
            ),
        }
    return output


def _class_summary(
    results: list[dict[str, object]],
) -> dict[str, dict[str, int | float | None]]:
    groups: dict[str, dict[str, int]] = {}
    for result in results:
        for item in result["expected"]:
            name = _finding_class(item["expected"]["code"])
            group = groups.setdefault(
                name,
                {
                    "expected_findings": 0,
                    "matched_findings": 0,
                    "unexpected_findings": 0,
                },
            )
            group["expected_findings"] += 1
            group["matched_findings"] += item["matched"]
        for finding in result["unexpected_findings"]:
            name = _finding_class(finding["code"])
            group = groups.setdefault(
                name,
                {
                    "expected_findings": 0,
                    "matched_findings": 0,
                    "unexpected_findings": 0,
                },
            )
            group["unexpected_findings"] += 1

    output: dict[str, dict[str, int | float | None]] = {}
    for name, group in sorted(groups.items()):
        expected = group["expected_findings"]
        matched = group["matched_findings"]
        unexpected = group["unexpected_findings"]
        output[name] = {
            **group,
            "target_recall": matched / expected if expected else None,
            "labelled_precision": (
                matched / (matched + unexpected)
                if matched + unexpected
                else None
            ),
        }
    return output


def run_benchmark(cases_path: Path) -> dict[str, object]:
    specification = _load_specification(cases_path)
    results: list[dict[str, object]] = []
    seen_case_ids: set[str] = set()

    with tempfile.TemporaryDirectory(prefix="neurodata-benchmark-") as directory:
        workspace = Path(directory)
        for case in specification["cases"]:
            case_id = case["case_id"]
            if Path(case_id).name != case_id or case_id in {"", ".", ".."}:
                raise ValueError("Benchmark case IDs must be single directory names")
            if case_id in seen_case_ids:
                raise ValueError(f"Duplicate benchmark case ID: {case_id}")
            seen_case_ids.add(case_id)
            case_root = workspace / case_id
            case_root.mkdir()
            results.append(_score_case(case, case_root))

    expected_total = sum(len(result["expected"]) for result in results)
    expected_matched = sum(
        expected["matched"]
        for result in results
        for expected in result["expected"]
    )
    unexpected_total = sum(
        len(result["unexpected_findings"]) for result in results
    )
    duplicate_total = sum(
        item["extra_count"]
        for result in results
        for item in result["duplicate_findings"]
    )
    masking_failures = sum(
        len(result["masking_failures"]) for result in results
    )
    control_results = [result for result in results if not result["expected"]]
    clean_controls = sum(
        not result["unexpected_findings"] for result in control_results
    )
    precision_denominator = expected_matched + unexpected_total
    expected_reference_total = sum(
        len(result["expected_references"]) for result in results
    )
    matched_reference_total = sum(
        item["matched"]
        for result in results
        for item in result["expected_references"]
    )
    unexpected_reference_total = sum(
        len(result["unexpected_references"]) for result in results
    )
    expected_container_total = sum(
        len(result["expected_container_members"]) for result in results
    )
    matched_container_total = sum(
        item["matched"]
        for result in results
        for item in result["expected_container_members"]
    )
    unexpected_container_total = sum(
        len(result["unexpected_container_members"]) for result in results
    )
    expected_coverage_total = sum(
        len(result["expected_coverage"]) for result in results
    )
    matched_coverage_total = sum(
        item["matched"]
        for result in results
        for item in result["expected_coverage"]
    )

    result = {
        "schema_version": specification["schema_version"],
        "summary": {
            "cases": len(results),
            "expected_findings": expected_total,
            "matched_findings": expected_matched,
            "unexpected_findings": unexpected_total,
            "duplicate_findings": duplicate_total,
            "cases_with_duplicates": sum(
                bool(result["duplicate_findings"]) for result in results
            ),
            "target_recall": (
                expected_matched / expected_total if expected_total else None
            ),
            "labelled_precision": (
                expected_matched / precision_denominator
                if precision_denominator
                else None
            ),
            "control_cases": len(control_results),
            "clean_controls": clean_controls,
            "control_specificity": (
                clean_controls / len(control_results)
                if control_results
                else None
            ),
            "expected_references": expected_reference_total,
            "matched_references": matched_reference_total,
            "unexpected_references": unexpected_reference_total,
            "expected_container_members": expected_container_total,
            "matched_container_members": matched_container_total,
            "unexpected_container_members": unexpected_container_total,
            "expected_coverage": expected_coverage_total,
            "matched_coverage": matched_coverage_total,
            "masking_failures": masking_failures,
            "integrity_failures": sum(
                not result["integrity_passed"] for result in results
            ),
        },
        "cases": results,
    }
    result["by_format"] = _group_summary(results, "format")
    result["by_finding_class"] = _class_summary(results)
    return result


def _format_rate(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def render_benchmark_markdown(result: dict[str, object]) -> str:
    summary = result["summary"]
    lines = [
        "# Leak-detection benchmark",
        "",
        "This benchmark uses labelled synthetic cases. It does not prove that a "
        "dataset is anonymous or legally compliant.",
        "",
        "## Summary",
        "",
        f"- Cases: {summary['cases']}",
        (
            f"- Expected findings matched: {summary['matched_findings']} / "
            f"{summary['expected_findings']}"
        ),
        f"- Unexpected findings: {summary['unexpected_findings']}",
        f"- Duplicate findings: {summary['duplicate_findings']}",
        f"- Target recall: {summary['target_recall']:.3f}",
        f"- Labelled precision: {summary['labelled_precision']:.3f}",
        (
            f"- Clean controls: {summary['clean_controls']} / "
            f"{summary['control_cases']}"
        ),
        (
            f"- Expected references matched: {summary['matched_references']} / "
            f"{summary['expected_references']}"
        ),
        f"- Unexpected references: {summary['unexpected_references']}",
        (
            "- Expected archive members matched: "
            f"{summary['matched_container_members']} / "
            f"{summary['expected_container_members']}"
        ),
        (
            "- Unexpected archive members: "
            f"{summary['unexpected_container_members']}"
        ),
        (
            f"- Expected coverage states matched: {summary['matched_coverage']} / "
            f"{summary['expected_coverage']}"
        ),
        f"- Masking failures: {summary['masking_failures']}",
        f"- Integrity failures: {summary['integrity_failures']}",
        "",
        "## Cases",
        "",
        (
            "| Case | Split | Format | Expected matched | Unexpected | "
            "Duplicates | References | Archive | Coverage | Masking failures |"
        ),
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for case in result["cases"]:
        lines.append(
            "| {case_id} | {split} | {format} | {matched}/{expected} | "
            "{unexpected} | {duplicates} | {references} | {archive} | {coverage} | "
            "{masking} |".format(
                case_id=case["case_id"],
                split=case["split"],
                format=case["format"],
                matched=sum(item["matched"] for item in case["expected"]),
                expected=len(case["expected"]),
                unexpected=len(case["unexpected_findings"]),
                duplicates=sum(
                    item["extra_count"] for item in case["duplicate_findings"]
                ),
                references="{}/{}".format(
                    sum(item["matched"] for item in case["expected_references"]),
                    len(case["expected_references"]),
                ),
                archive="{}/{}".format(
                    sum(
                        item["matched"]
                        for item in case["expected_container_members"]
                    ),
                    len(case["expected_container_members"]),
                ),
                coverage="{}/{}".format(
                    sum(item["matched"] for item in case["expected_coverage"]),
                    len(case["expected_coverage"]),
                ),
                masking=len(case["masking_failures"]),
            )
        )
    lines.extend(
        [
            "",
            "## By format",
            "",
            "| Format | Cases | Matched | Unexpected | Recall | Precision |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for name, group in result["by_format"].items():
        lines.append(
            "| {name} | {cases} | {matched}/{expected} | {unexpected} | "
            "{recall} | {precision} |".format(
                name=name,
                cases=group["cases"],
                matched=group["matched_findings"],
                expected=group["expected_findings"],
                unexpected=group["unexpected_findings"],
                recall=_format_rate(group["target_recall"]),
                precision=_format_rate(group["labelled_precision"]),
            )
        )
    lines.extend(
        [
            "",
            "## By finding class",
            "",
            "| Class | Matched | Unexpected | Recall | Precision |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for name, group in result["by_finding_class"].items():
        lines.append(
            "| {name} | {matched}/{expected} | {unexpected} | "
            "{recall} | {precision} |".format(
                name=name,
                matched=group["matched_findings"],
                expected=group["expected_findings"],
                unexpected=group["unexpected_findings"],
                recall=_format_rate(group["target_recall"]),
                precision=_format_rate(group["labelled_precision"]),
            )
        )
    return "\n".join(lines) + "\n"
