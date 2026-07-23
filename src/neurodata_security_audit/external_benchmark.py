"""Run format smoke checks on hash-pinned public files."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from .scanner import scan_dataset


def _relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError("Fixture paths must stay inside the fixture root")
    return path


def _fixture_source(root: Path, relative: Path) -> Path:
    source = root / relative
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Fixture paths must not contain symlinks")
    return source


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _failed_fixture(
    fixture: dict[str, object],
    reason: str,
) -> dict[str, object]:
    return {
        "fixture_id": fixture["fixture_id"],
        "dataset_id": fixture["dataset_id"],
        "format": fixture["format"],
        "doi": fixture["doi"],
        "source_url": fixture["source_url"],
        "source_commit": fixture["source_commit"],
        "source_path": fixture["source_path"],
        "source_sha256": fixture["sha256"],
        "source_hash_matched": False,
        "source_unchanged": False,
        "coverage": None,
        "finding_codes": {},
        "forbidden_codes": [],
        "integrity_passed": False,
        "passed": False,
        "failure": reason,
    }


def _run_fixture(
    fixture: dict[str, object],
    fixture_root: Path,
) -> dict[str, object]:
    relative = _relative_path(str(fixture["source_path"]))
    try:
        source = _fixture_source(fixture_root, relative)
    except ValueError:
        return _failed_fixture(fixture, "source_path_contains_symlink")
    if not source.is_file():
        return _failed_fixture(fixture, "source_missing")

    source_hash = _sha256(source)
    if source_hash != fixture["sha256"]:
        return _failed_fixture(fixture, "source_hash_mismatch")

    with tempfile.TemporaryDirectory(prefix="neurodata-format-fixture-") as directory:
        case_root = Path(directory)
        target = case_root / source.name
        shutil.copyfile(source, target)
        if _sha256(target) != fixture["sha256"]:
            return _failed_fixture(fixture, "copied_fixture_hash_mismatch")
        report = scan_dataset(case_root)

    finding_counts = Counter(item.code for item in report.findings)
    coverage = next(
        (
            item.status
            for item in report.coverage
            if item.path == source.name
        ),
        None,
    )
    forbidden = sorted(
        set(fixture.get("forbidden_codes", [])) & set(finding_counts)
    )
    source_unchanged = _sha256(source) == source_hash
    passed = bool(
        source_unchanged
        and coverage == fixture["expected_coverage"]
        and not forbidden
        and report.manifest_recheck_passed
        and report.release_tree_recheck_passed
    )
    return {
        "fixture_id": fixture["fixture_id"],
        "dataset_id": fixture["dataset_id"],
        "format": fixture["format"],
        "doi": fixture["doi"],
        "source_url": fixture["source_url"],
        "source_commit": fixture["source_commit"],
        "source_path": fixture["source_path"],
        "source_sha256": source_hash,
        "source_hash_matched": True,
        "source_unchanged": source_unchanged,
        "coverage": coverage,
        "finding_codes": dict(sorted(finding_counts.items())),
        "forbidden_codes": forbidden,
        "integrity_passed": (
            report.manifest_recheck_passed
            and report.release_tree_recheck_passed
        ),
        "passed": passed,
        "failure": None if passed else "format_check_failed",
    }


def run_external_format_checks(
    manifest_path: Path,
    fixture_root: Path,
) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = [
        _run_fixture(fixture, fixture_root)
        for fixture in manifest["fixtures"]
    ]
    return {
        "schema_version": manifest["schema_version"],
        "suite_name": manifest["suite_name"],
        "summary": {
            "fixtures": len(results),
            "passed": sum(item["passed"] for item in results),
            "failed": sum(not item["passed"] for item in results),
            "unscored_formats": len(manifest.get("unscored_formats", [])),
        },
        "fixtures": results,
        "unscored_formats": manifest.get("unscored_formats", []),
    }


def render_external_format_markdown(result: dict[str, object]) -> str:
    summary = result["summary"]
    lines = [
        "# Public format fixture checks",
        "",
        "These checks confirm reader execution and coverage on hash-pinned public "
        "files. They do not provide privacy ground truth.",
        "",
        f"- Fixtures: {summary['fixtures']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Unscored formats: {summary['unscored_formats']}",
        "",
        "| Fixture | Dataset | Format | Coverage | Finding codes | Result |",
        "|---|---|---|---|---|---|",
    ]
    for fixture in result["fixtures"]:
        findings = ", ".join(fixture["finding_codes"]) or "none"
        lines.append(
            "| {fixture_id} | {dataset_id} | {format} | {coverage} | "
            "{findings} | {status} |".format(
                fixture_id=fixture["fixture_id"],
                dataset_id=fixture["dataset_id"],
                format=fixture["format"],
                coverage=fixture["coverage"] or "—",
                findings=findings,
                status="pass" if fixture["passed"] else fixture["failure"],
            )
        )
    if result["unscored_formats"]:
        lines.extend(["", "## Unscored formats", ""])
        for item in result["unscored_formats"]:
            lines.append(f"- **{item['format']}** — {item['reason']}")
    return "\n".join(lines) + "\n"
