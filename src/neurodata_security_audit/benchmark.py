"""Evaluate the scanner on labelled synthetic releases."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .html_report import render_html
from .reporting import render_json, render_markdown
from .scanner import ScanPolicy, scan_dataset


def _relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError("Benchmark file paths must stay inside their case directory")
    return path


def _matches(expected: dict[str, str], actual: dict[str, str]) -> bool:
    for field in ("code", "severity", "path", "location"):
        value = expected.get(field)
        if value is not None and actual[field] != value:
            return False
    location = expected.get("location_contains")
    return location is None or location in actual["location"]


def _score_case(case: dict[str, object], root: Path) -> dict[str, object]:
    for relative_path, content in case["files"].items():
        path = root / _relative_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    policy = ScanPolicy(sensitive_terms=tuple(case["sensitive_terms"]))
    report = scan_dataset(root, policy)
    actual = report.to_dict()["findings"]
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
        "masking_failures": masking_failures,
        "integrity_passed": (
            report.manifest_recheck_passed
            and report.release_tree_recheck_passed
        ),
    }


def run_benchmark(cases_path: Path) -> dict[str, object]:
    specification = json.loads(cases_path.read_text(encoding="utf-8"))
    results: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix="neurodata-benchmark-") as directory:
        workspace = Path(directory)
        for case in specification["cases"]:
            case_id = case["case_id"]
            if Path(case_id).name != case_id or case_id in {"", ".", ".."}:
                raise ValueError("Benchmark case IDs must be single directory names")
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
    masking_failures = sum(
        len(result["masking_failures"]) for result in results
    )
    control_results = [result for result in results if not result["expected"]]
    clean_controls = sum(
        not result["unexpected_findings"] for result in control_results
    )
    precision_denominator = expected_matched + unexpected_total

    return {
        "schema_version": specification["schema_version"],
        "summary": {
            "cases": len(results),
            "expected_findings": expected_total,
            "matched_findings": expected_matched,
            "unexpected_findings": unexpected_total,
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
            "masking_failures": masking_failures,
            "integrity_failures": sum(
                not result["integrity_passed"] for result in results
            ),
        },
        "cases": results,
    }


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
        f"- Target recall: {summary['target_recall']:.3f}",
        f"- Labelled precision: {summary['labelled_precision']:.3f}",
        (
            f"- Clean controls: {summary['clean_controls']} / "
            f"{summary['control_cases']}"
        ),
        f"- Masking failures: {summary['masking_failures']}",
        f"- Integrity failures: {summary['integrity_failures']}",
        "",
        "## Cases",
        "",
        "| Case | Split | Format | Expected matched | Unexpected | Masking failures |",
        "|---|---|---|---:|---:|---:|",
    ]
    for case in result["cases"]:
        lines.append(
            "| {case_id} | {split} | {format} | {matched}/{expected} | "
            "{unexpected} | {masking} |".format(
                case_id=case["case_id"],
                split=case["split"],
                format=case["format"],
                matched=sum(item["matched"] for item in case["expected"]),
                expected=len(case["expected"]),
                unexpected=len(case["unexpected_findings"]),
                masking=len(case["masking_failures"]),
            )
        )
    return "\n".join(lines) + "\n"
