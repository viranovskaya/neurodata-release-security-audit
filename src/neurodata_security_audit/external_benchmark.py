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


def _directory_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(b"neurodata-directory-sha256-v1\0")
    for item in sorted(
        path.rglob("*"),
        key=lambda child: child.relative_to(path).as_posix(),
    ):
        relative = item.relative_to(path).as_posix()
        if item.is_symlink():
            raise ValueError("Fixture directories must not contain symlinks")
        if item.is_dir():
            digest.update(b"directory\0")
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            continue
        if not item.is_file():
            raise ValueError(
                "Fixture directories must contain only files and directories"
            )
        digest.update(b"file\0")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(item.stat().st_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(_sha256(item).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _source_hash(path: Path, kind: str) -> str:
    if kind == "file":
        if not path.is_file():
            raise ValueError("Fixture source is not a file")
        return _sha256(path)
    if kind == "directory":
        if not path.is_dir():
            raise ValueError("Fixture source is not a directory")
        return _directory_sha256(path)
    raise ValueError("Fixture source_kind must be 'file' or 'directory'")


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
        "source_kind": fixture.get("source_kind", "file"),
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
    source_kind = str(fixture.get("source_kind", "file"))
    try:
        source = _fixture_source(fixture_root, relative)
    except ValueError:
        return _failed_fixture(fixture, "source_path_contains_symlink")
    if not source.exists():
        return _failed_fixture(fixture, "source_missing")

    try:
        source_hash = _source_hash(source, source_kind)
    except ValueError:
        return _failed_fixture(fixture, "source_kind_or_contents_invalid")
    if source_hash != fixture["sha256"]:
        return _failed_fixture(fixture, "source_hash_mismatch")

    with tempfile.TemporaryDirectory(prefix="neurodata-format-fixture-") as directory:
        case_root = Path(directory)
        target = case_root / source.name
        if source_kind == "directory":
            shutil.copytree(source, target)
        else:
            shutil.copyfile(source, target)
        if _source_hash(target, source_kind) != fixture["sha256"]:
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
    try:
        source_unchanged = _source_hash(source, source_kind) == source_hash
    except ValueError:
        source_unchanged = False
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
        "source_kind": source_kind,
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
